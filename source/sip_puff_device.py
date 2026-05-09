"""Top-level coordinator for the T-Rex Sip-N-Puff device.

Wires the four building blocks together:

    PressureSensor → BreathClassifier → EncoderEmulator + XacOutput

In ``run`` mode the loop is:

    1. read pressure (oversampled, baseline-zeroed)
    2. feed it to the breath classifier
    3. dispatch the resulting event to encoder + XAC outputs

In ``diagnostic`` mode no outputs are driven; the loop instead
streams sensor + state info to the serial console for benchtop
calibration and threshold tuning.

Mapping from breath events to outputs:

    "puff"        → encoder CW click  + XAC puff pulse
    "puff_repeat" → encoder CW click  (held puff scrolling — opto skipped)
    "double_puff" → encoder button    + XAC puff double-pulse
    "sip"         → encoder CCW click + XAC sip pulse
    "sip_repeat"  → encoder CCW click (held sip scrolling — opto skipped)
    "double_sip"  →                    XAC sip double-pulse
                    (no encoder action — keeps "select" reserved for
                    double-puff per the original project spec)
"""

import time

from hardware_config import load_config, _pin
from pressure_sensor import PressureSensor
from breath_classifier import BreathClassifier
from encoder_emulator import EncoderEmulator
from xac_output import XacOutput
from display_manager import DisplayManager
from lps28_sensor import LPS28Sensor


class SipPuffDevice:
    """Main coordinator object. Instantiate once and call run().

    Args:
        variant: variant key from hardware_config.VARIANTS, or None
            to use DEFAULT_VARIANT.
        config_path: path to optional user config.txt overlay.
    """

    def __init__(self, variant=None, config_path="/config.txt"):
        self._config = load_config(variant=variant, user_path=config_path)
        print("SipPuff: variant={}".format(self._config.get("_variant")))

        self._poll_period = float(self._config["poll_period_s"])
        self._mode        = self._config.get("mode", "run")
        self._verbose     = bool(self._config.get("verbose", False))

        self._sensor    = PressureSensor(self._config)
        self._classifier = BreathClassifier(self._config)

        # Shared I2C bus. The LPS28 (always wanted) and the SSD1306
        # OLED (when display_controller=ssd1306) live on the same
        # GP4/GP5 pair at distinct addresses (0x5C and 0x3C). Earlier
        # builds gave LPS28 exclusive ownership of the bus and
        # skipped it entirely on OLED variants; that was wrong — we
        # just need to call busio.I2C() once and hand the same object
        # to both subsystems.
        self._i2c = self._make_shared_i2c()
        self._lps28 = self._init_lps28(self._i2c)

        # Display claims SPI1 + GP10–16 for the LCD variant, or the
        # shared I2C bus for the OLED variant.
        self._display = DisplayManager(self._config, {
            "puff_on":    self._config["puff_on_kpa"],
            "sip_on":     self._config["sip_on_kpa"],
            "full_scale": self._config["repeat_full_scale_kpa"],
        }, i2c=self._i2c)
        self._encoder    = EncoderEmulator(self._config)
        self._xac        = XacOutput(self._config)

        self._sensor.calibrate_baseline()
        if self._lps28 is not None and self._lps28.available:
            self._lps28.calibrate_baseline()

    def _make_shared_i2c(self):
        """Bring up one busio.I2C bus on GP4/GP5 (or whatever
        display_i2c_*_pin says) and return it.

        Called once at startup; the same bus object is shared between
        the LPS28 and an SSD1306 OLED display when both are present.
        Returns None if the bus can't be brought up so callers can
        gracefully run without I2C devices.
        """
        try:
            import busio
            import digitalio
            sda_name = self._config.get("display_i2c_sda_pin", "GP4")
            scl_name = self._config.get("display_i2c_scl_pin", "GP5")
            sda = _pin(sda_name)
            scl = _pin(scl_name)

            # Drive both lines HIGH briefly to satisfy busio.I2C's
            # pull-up sanity check on a board without external
            # 10 kΩ pull-ups. The pad's pull-up bit persists across
            # the function-mux change long enough for busio.I2C to
            # see HIGH on its 10 µs sample.
            for pin in (sda, scl):
                io = digitalio.DigitalInOut(pin)
                io.direction = digitalio.Direction.OUTPUT
                io.value = True
                time.sleep(0.05)
                io.deinit()

            freq = int(self._config.get("display_i2c_frequency", 100_000))
            i2c = busio.I2C(scl, sda, frequency=freq)
            print("I2C: shared bus up on SDA={} SCL={} freq={}".format(
                sda_name, scl_name, freq))
            return i2c
        except Exception as e:
            print("I2C: shared bus init failed ({})".format(e))
            return None

    def _init_lps28(self, i2c):
        """Bring up the LPS28 on the shared I2C bus (or skip)."""
        if i2c is None:
            print("LPS28: skipped — no I2C bus")
            return None
        try:
            return LPS28Sensor(i2c, addr=0x5C, verbose=self._verbose)
        except Exception as e:
            print("LPS28: init failed ({})".format(e))
            return None

    @property
    def config(self):
        """Resolved runtime config dict (read-only by convention)."""
        return self._config

    # --- Entry points --------------------------------------------

    def run(self):
        """Main loop. Dispatches based on configured mode.

        Catches and reports any unexpected exception so the device
        does not crash hard during a Maker Faire demo.
        """
        try:
            if self._mode == "diagnostic":
                self._run_diagnostic()
            else:
                self._run_normal()
        except KeyboardInterrupt:
            print("SipPuff: interrupted by user")
        except Exception as e:
            print("SipPuff: FATAL ({})".format(e))
        finally:
            self._xac.all_release()

    # --- Run modes -----------------------------------------------

    def _run_normal(self):
        print("SipPuff: entering RUN mode")
        last_log = time.monotonic()
        # Default 1 Hz on the serial console — the LCD shows live
        # values, so the serial line is just a backup tape. Override
        # with heartbeat_period_s in config.txt for finer-grained
        # logging during calibration.
        log_period = float(self._config.get("heartbeat_period_s", 1.0))

        while True:
            p = self._sensor.gauge_kpa()
            event = self._classifier.poll(p)
            if event is not None:
                self._dispatch(event)

            # Display is throttled internally to display_update_hz —
            # safe to call every loop iteration. LPS28 gauge value is
            # passed through so its pair of bargraphs render alongside
            # the MPX bars; None when the sensor wasn't found at boot.
            lps_g = (self._lps28.gauge_kpa()
                     if (self._lps28 is not None
                         and self._lps28.available)
                     else None)
            self._display.update(p, self._classifier.state, lps_g)

            # --- Sensor stream ---------------------------------------
            now = time.monotonic()
            if (now - last_log) >= log_period:
                last_log = now
                self._print_sensor_line(p, now)

            time.sleep(self._poll_period)

    def _print_sensor_line(self, mpx_gauge_kpa, now):
        """Print one CSV-ish line with both sensors.

        Format:
            t=12.345 mpx=+0.012 mpx_abs=99.412 lps=99.408 lps_g=+0.005 state=idle

        mpx       baseline-zeroed reading from the analog MPX5010DP
        mpx_abs   absolute-pressure reading from the MPX5010DP
        lps       absolute reading from the LPS28DFWTR (kPa)
        lps_g     baseline-zeroed reading from the LPS28DFWTR
        """
        mpx_abs = self._sensor.pressure_kpa()
        if self._lps28 is not None and self._lps28.available:
            lps_abs = self._lps28.read_pressure_kpa()
            lps_g   = lps_abs - self._lps28.baseline_kpa
            print("t={:.2f} mpx={:+.3f}kPa mpx_abs={:.3f}kPa "
                  "lps={:.3f}kPa lps_g={:+.4f}kPa state={}".format(
                      now, mpx_gauge_kpa, mpx_abs,
                      lps_abs, lps_g, self._classifier.state))
        else:
            print("t={:.2f} mpx={:+.3f}kPa mpx_abs={:.3f}kPa "
                  "(lps unavailable) state={}".format(
                      now, mpx_gauge_kpa, mpx_abs,
                      self._classifier.state))

    def _run_diagnostic(self):
        # Diagnostic loop is implemented in diagnostic.py to keep
        # this file focused on the production code path. We import
        # lazily so the import doesn't run on production boots.
        print("SipPuff: entering DIAGNOSTIC mode")
        import diagnostic
        diagnostic.run(self._sensor, self._classifier, self._config,
                       display=self._display)

    # --- Event dispatch ------------------------------------------

    def _dispatch(self, event):
        """Translate a breath event into encoder + XAC actions."""
        if self._verbose:
            print("Event: {}".format(event))

        if event == "puff":
            self._encoder.click_cw()
            self._xac.pulse_puff()
            return

        if event == "puff_repeat":
            # Opto pulse skipped on repeat: a 50 ms pulse at the
            # repeat rate would either stretch into a held closure
            # (on fast repeats) or stall the loop. The encoder tick
            # carries the repeat semantics already.
            self._encoder.click_cw()
            return

        if event == "double_puff":
            self._encoder.press()
            self._xac.pulse_puff_double()
            return

        if event == "sip":
            self._encoder.click_ccw()
            self._xac.pulse_sip()
            return

        if event == "sip_repeat":
            self._encoder.click_ccw()
            return

        if event == "double_sip":
            # XAC-only — encoder shaft button stays reserved for the
            # double-puff "select" gesture from the original spec.
            self._xac.pulse_sip_double()
            return

        # Unknown event — log and ignore rather than crashing.
        print("SipPuff: unknown event '{}'".format(event))
