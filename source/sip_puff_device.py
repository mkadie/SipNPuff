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

from hardware_config import load_config, _pin, parse_i2c_device_spec
from pressure_sensor import PressureSensor
from breath_classifier import BreathClassifier
from encoder_emulator import EncoderEmulator
from xac_output import XacOutput
from display_manager import DisplayManager
from lps28_sensor import LPS28Sensor
from imu_bno08x import BNO08xSensor, Pointing
from imu_bno055 import BNO055Sensor
from mouse_output import MouseOutput


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

        # Shared I2C bus. LPS28, SSD1306 OLED, and any BNO08x IMU(s)
        # all live on GP4/GP5 at distinct addresses; one busio.I2C
        # is constructed and handed to each subsystem.
        self._i2c = self._make_shared_i2c()
        self._scan_i2c_bus(self._i2c)

        # Configured I2C peripherals — driven by the i2c_pressure /
        # i2c_imu_1..4 slots in config.txt.
        self._lps28 = self._init_lps28_from_slot(self._i2c)
        self._imus  = self._init_imu_slots(self._i2c)

        # Pointing helper: feeds quaternion + gyro from imu_1.
        self._pointing = Pointing(
            gain=float(self._config.get("imu_pointing_gain", 400.0)),
            deadband_dps=float(
                self._config.get("imu_pointing_deadband_dps", 1.5)),
            alpha=float(self._config.get("imu_pointing_alpha", 0.4)),
            accel_expo=float(self._config.get("imu_pointing_accel_expo", 1.0)),
            max_per_tick=float(
                self._config.get("imu_pointing_max_per_tick", 60.0)),
            yaw_axis=str(self._config.get("imu_yaw_axis", "-z")),
            pitch_axis=str(self._config.get("imu_pitch_axis", "-x")),
            stillness_recenter_s=float(self._config.get(
                "imu_pointing_stillness_recenter_s", 0.0)),
        )

        # Display claims SPI1 + GP10–16 for the LCD variant, or the
        # shared I2C bus for the OLED variant. Disabled entirely
        # when ``display = none``.
        #
        # Threshold ticks are passed as the **effective raw-signal**
        # trigger point — i.e. puff_on_kpa / puff_signal_scale — so
        # the on-screen tick lines up with where a bar actually
        # needs to reach for the classifier to fire.
        puff_scale_cfg = max(0.001, float(
            self._config.get("puff_signal_scale", 1.0)))
        sip_scale_cfg = max(0.001, float(
            self._config.get("sip_signal_scale",  1.0)))
        self._display = DisplayManager(self._config, {
            "puff_on":    self._config["puff_on_kpa"] / puff_scale_cfg,
            "sip_on":     self._config["sip_on_kpa"]  / sip_scale_cfg,
            "full_scale": self._config["repeat_full_scale_kpa"],
        }, i2c=self._i2c)
        self._encoder    = EncoderEmulator(self._config)
        self._xac        = XacOutput(self._config)

        # Output mode: drives both the dispatch table for breath
        # events and whether a HID mouse is brought up at boot.
        self._output_mode = str(
            self._config.get("output_mode", "encoder")).strip().lower()
        if self._output_mode not in ("encoder", "mouse"):
            print("Output: unknown output_mode '{}', defaulting to 'encoder'"
                  .format(self._output_mode))
            self._output_mode = "encoder"
        self._mouse = MouseOutput(verbose=self._verbose) \
            if self._output_mode == "mouse" else None
        # Pull motion-rate gating threshold from config.
        self._mouse_motion_min = int(
            self._config.get("mouse_motion_min_per_tick", 1))
        self._mouse_scroll_amount = int(
            self._config.get("mouse_scroll_per_repeat", 1))
        # Per-direction repeat multipliers — emit N clicks (or N scroll
        # ticks in mouse mode) per puff_repeat / sip_repeat event. Lets
        # the user compensate for asymmetric puff/sip strength.
        self._puff_repeat_mult = max(
            1, int(self._config.get("puff_repeat_multiplier", 1)))
        self._sip_repeat_mult  = max(
            1, int(self._config.get("sip_repeat_multiplier", 1)))
        print("Output: mode={}".format(self._output_mode))

        if self._sensor.available:
            self._sensor.calibrate_baseline()
        else:
            print("Pressure: MPX5010DP absent — sip/puff column will read 0")
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

    def _scan_i2c_bus(self, i2c):
        """Print every responding I2C address. Doubles as a wiring
        sanity check before we try to drive specific peripherals.
        """
        if i2c is None:
            return
        try:
            while not i2c.try_lock():
                pass
            try:
                addrs = i2c.scan()
            finally:
                i2c.unlock()
            if addrs:
                print("I2C: scan found {}".format(
                    ", ".join("0x{:02X}".format(a) for a in addrs)))
            else:
                print("I2C: scan found no devices")
        except Exception as e:
            print("I2C: scan failed ({})".format(e))

    def _init_lps28_from_slot(self, i2c):
        """Bring up the LPS28 if i2c_pressure = lps28[@0xNN]."""
        if i2c is None:
            return None
        driver, addr = parse_i2c_device_spec(
            self._config.get("i2c_pressure"))
        if driver != "lps28":
            print("LPS28: not configured (i2c_pressure)")
            return None
        try:
            return LPS28Sensor(i2c, addr=addr or 0x5C, verbose=self._verbose)
        except Exception as e:
            print("LPS28: init failed ({})".format(e))
            return None

    def _init_imu_slots(self, i2c):
        """Walk i2c_imu_1..4 and instantiate the right driver for
        each non-empty slot. Slots can mix BNO08x and BNO055 freely.
        Returns a list of sensor instances that came up successfully.
        """
        out = []
        if i2c is None:
            return out
        for n in range(1, 5):
            slot_key = "i2c_imu_{}".format(n)
            spec = self._config.get(slot_key)
            driver, addr = parse_i2c_device_spec(spec)
            if driver is None:
                continue
            label = "imu{}".format(n)
            if driver == "bno08x":
                sensor = BNO08xSensor(i2c, addr=addr,
                                      verbose=self._verbose,
                                      slot_label=label)
            elif driver == "bno055":
                sensor = BNO055Sensor(i2c, addr=addr,
                                      verbose=self._verbose,
                                      slot_label=label)
            else:
                print("{}: unsupported driver '{}'".format(slot_key, driver))
                continue
            if sensor.available:
                out.append(sensor)
        return out

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
            if self._mouse is not None and self._mouse.available:
                self._mouse.release_all()

    # --- Run modes -----------------------------------------------

    def _run_normal(self):
        print("SipPuff: entering RUN mode")
        last_log = time.monotonic()
        # The live serial line is the primary observation surface for
        # IMU-as-mouse builds. Default 5 s — the column-aligned line
        # is wide, and once-every-5-seconds reads naturally in a
        # terminal. Override with heartbeat_period_s in config.txt.
        log_period = float(self._config.get("heartbeat_period_s", 5.0))

        # Per-direction pressure source selection. Each of puff_branch
        # and sip_branch independently picks MPX or LPS28. classifier
        # sees max(puff_branch, 0) + min(sip_branch, 0) — only one
        # branch is non-zero at any given moment, so the two sources
        # don't cross-contaminate.
        #
        # Common combinations:
        #   neither flag set        → classic MPX-only behavior
        #   sip_from_lps28 only     → MPX for puff, LPS28 for sip
        #                             (use when the sip side of MPX
        #                              is unusable; "fusion" mode)
        #   both flags set          → LPS28 drives both directions
        #                             (use when LPS28 is plumbed to
        #                              the mouthpiece and you want
        #                              symmetric bidirectional input)
        lps_available = (self._lps28 is not None and self._lps28.available)
        use_lps_sip  = bool(self._config.get("sip_from_lps28",  False)) and lps_available
        use_lps_puff = bool(self._config.get("puff_from_lps28", False)) and lps_available
        # Per-direction signal scaling — multiplies each branch before
        # the classifier sees it. Compensates for asymmetric breath
        # effort: e.g., puff_signal_scale = 2 means a 0.5 kPa raw puff
        # already crosses a 1.0 kPa configured threshold.
        puff_scale = float(self._config.get("puff_signal_scale", 1.0))
        sip_scale  = float(self._config.get("sip_signal_scale",  1.0))
        print("Pressure: source puff={}(x{:.2f}) sip={}(x{:.2f})".format(
            "lps28" if use_lps_puff else "mpx", puff_scale,
            "lps28" if use_lps_sip  else "mpx", sip_scale))

        # Per-heartbeat peak tracking — tells the user how hard the
        # current breaths are pushing/pulling.
        peak_pos = 0.0
        peak_neg = 0.0

        # LPS28 auto-rezero. After ``lps_auto_rezero_idle_s`` seconds
        # of continuous state=idle with low variance in the LPS gauge,
        # snap the baseline so the gauge reads ~0 again. Catches slow
        # thermal / room-pressure drift between boot and now.
        rezero_idle_s = float(self._config.get(
            "lps_auto_rezero_idle_s", 30.0))
        rezero_threshold = float(self._config.get(
            "lps_auto_rezero_threshold_kpa", 0.5))
        idle_start_t = None
        idle_gauge_min = 0.0
        idle_gauge_max = 0.0
        idle_gauge_sum = 0.0
        idle_gauge_n   = 0

        while True:
            mpx_gauge = (self._sensor.gauge_kpa()
                         if self._sensor.available else 0.0)
            lps_gauge = (self._lps28.gauge_kpa() if lps_available else None)

            if use_lps_puff or use_lps_sip:
                puff_branch = (lps_gauge if use_lps_puff else mpx_gauge)
                sip_branch  = (lps_gauge if use_lps_sip  else mpx_gauge)
                classifier_p = (max(puff_branch, 0.0) * puff_scale
                                + min(sip_branch, 0.0) * sip_scale)
            else:
                # Single-source path — still apply the scales so the
                # asymmetry knob works in MPX-only setups too.
                classifier_p = (max(mpx_gauge, 0.0) * puff_scale
                                + min(mpx_gauge, 0.0) * sip_scale)

            if classifier_p > peak_pos:
                peak_pos = classifier_p
            if classifier_p < peak_neg:
                peak_neg = classifier_p

            if (self._sensor.available
                    or use_lps_sip or use_lps_puff):
                event = self._classifier.poll(classifier_p)
                if event is not None:
                    self._dispatch(event)

            # Auto-rezero accounting. Only meaningful when the LPS28
            # is on the bus and the classifier just transitioned to /
            # stayed in idle. Any non-idle state resets the window.
            if (rezero_idle_s > 0.0 and lps_gauge is not None
                    and self._classifier.state == "idle"):
                now_t = time.monotonic()
                if idle_start_t is None:
                    idle_start_t = now_t
                    idle_gauge_min = lps_gauge
                    idle_gauge_max = lps_gauge
                    idle_gauge_sum = lps_gauge
                    idle_gauge_n   = 1
                else:
                    if lps_gauge < idle_gauge_min: idle_gauge_min = lps_gauge
                    if lps_gauge > idle_gauge_max: idle_gauge_max = lps_gauge
                    idle_gauge_sum += lps_gauge
                    idle_gauge_n   += 1
                idle_dur = now_t - idle_start_t
                if idle_dur >= rezero_idle_s:
                    spread = idle_gauge_max - idle_gauge_min
                    mean = idle_gauge_sum / idle_gauge_n
                    if (spread < 0.10           # stable: <100 Pa spread
                            and abs(mean) > rezero_threshold):
                        print("LPS28: auto-rezero (idle {:.1f}s, "
                              "drift {:+.3f}kPa, spread {:.3f}kPa)"
                              .format(idle_dur, mean, spread))
                        self._lps28.recenter_now()
                    # Restart window either way so we don't spam.
                    idle_start_t = None
            elif idle_start_t is not None:
                idle_start_t = None

            # Pointing is updated every loop so the gyro integral has
            # the smallest possible dt. The first IMU drives the cursor.
            pointing = self._update_pointing()

            # In mouse mode, push the integer rate-deltas to the HID
            # mouse on every loop tick. The Pointing helper already
            # applies the deadband + acceleration curve + clamp, so we
            # just emit non-zero deltas.
            if (self._output_mode == "mouse"
                    and self._mouse is not None
                    and self._mouse.available
                    and pointing[1] is not None):
                rdx, rdy, _ay, _ap = pointing[1]
                if abs(rdx) >= self._mouse_motion_min or \
                        abs(rdy) >= self._mouse_motion_min:
                    self._mouse.move(rdx, rdy)

            # MPX bars show MPX gauge, LPS bars show LPS gauge — each
            # row tracks the actual sensor reading on that hardware
            # channel, not the fused classifier input.
            self._display.update(mpx_gauge, self._classifier.state,
                                 lps_gauge)

            now = time.monotonic()
            if (now - last_log) >= log_period:
                last_log = now
                self._print_sensor_line(mpx_gauge, now, pointing,
                                        peak_pos, peak_neg)
                peak_pos = 0.0
                peak_neg = 0.0

            time.sleep(self._poll_period)

    def _update_pointing(self):
        """Pull a fresh sample from imu_1 and update the Pointing helper.
        Returns ``(snapshot_or_None, (rate_dx, rate_dy, abs_yaw_deg, abs_pitch_deg) or None)``.
        """
        if not self._imus:
            return (None, None)
        snap = self._imus[0].poll()
        if snap is None:
            return (None, None)
        return (snap, self._pointing.update(snap["gyro"], snap["quat"]))

    def _print_sensor_line(self, mpx_gauge_kpa, now, pointing,
                           peak_pos=0.0, peak_neg=0.0):
        """Print one fixed-width status line.

        Every cell is the same width whether or not its sensor is
        present, so successive heartbeats line up column-for-column
        in a monospace terminal and changes in any single number are
        easy to spot at a glance. Default cadence is 5 s
        (heartbeat_period_s in config.txt).

        Layout (≈220 cols, all on one line):

          t=NNNNN.NN | mpx=±N.NNN abs=±N.NNN | lps=NNN.NNN g=±N.NNNN |
          imu1@0xNN a(±NN.NN,±NN.NN,±NN.NN) g(±N.NN,±N.NN,±N.NN)
            m(±NNN.N,±NNN.N,±NNN.N) q(±N.NNN,±N.NNN,±N.NNN,±N.NNN) |
          rate(±NNN,±NNN) abs(±NNN.NN,±NNN.NN) | state=NAME
        """
        t_cell = "t={:08.2f}".format(now)

        if self._sensor.available:
            mpx_abs = self._sensor.pressure_kpa()
            sip_cell = "mpx={:+0.3f} abs={:+0.3f}".format(
                mpx_gauge_kpa, mpx_abs)
        else:
            sip_cell = "mpx= ABSENT  abs= ABSENT "

        if self._lps28 is not None and self._lps28.available:
            lps_abs = self._lps28.read_pressure_kpa()
            lps_g   = lps_abs - self._lps28.baseline_kpa
            lps_cell = "lps={:7.3f} g={:+.4f}".format(lps_abs, lps_g)
        else:
            lps_cell = "lps=  ABSENT g=  ABSENT"

        # Max/min gauge value seen since the previous heartbeat — lets
        # the user see at a glance how hard they're pushing the
        # classifier input in each direction.
        peak_cell = "peak(puf={:+05.2f},sip={:+05.2f})".format(
            peak_pos, peak_neg)

        snap, ptr = pointing
        if self._imus and snap is not None:
            imu = self._imus[0]
            ax, ay, az = snap["accel"]
            gx, gy, gz = snap["gyro"]
            mx, my, mz = snap["mag"]
            qi, qj, qk, qr = snap["quat"]
            imu_cell = (
                "imu1@0x{addr:02X} "
                "a({ax:+06.2f},{ay:+06.2f},{az:+06.2f}) "
                "g({gx:+05.2f},{gy:+05.2f},{gz:+05.2f}) "
                "m({mx:+06.1f},{my:+06.1f},{mz:+06.1f}) "
                "q({qi:+06.3f},{qj:+06.3f},{qk:+06.3f},{qr:+06.3f})"
            ).format(addr=imu.address,
                     ax=ax, ay=ay, az=az,
                     gx=gx, gy=gy, gz=gz,
                     mx=mx, my=my, mz=mz,
                     qi=qi, qj=qj, qk=qk, qr=qr)
        elif self._imus:
            # IMU is configured but the last poll returned None.
            imu_cell = (
                "imu1@0x{addr:02X} a( STALE, STALE, STALE) "
                "g( STAL, STAL, STAL) "
                "m( STALE, STALE, STALE) "
                "q( STALE, STALE, STALE, STALE)"
            ).format(addr=self._imus[0].address)
        else:
            imu_cell = (
                "imu1=ABSENT  a(------,------,------) "
                "g(-----,-----,-----) "
                "m(------,------,------) "
                "q(------,------,------,------)"
            )

        if ptr is not None:
            rdx, rdy, ayaw, apitch = ptr
            ptr_cell = "rate({:+04d},{:+04d}) abs({:+07.2f},{:+07.2f})".format(
                int(rdx), int(rdy), ayaw, apitch)
        else:
            ptr_cell = "rate(----,----) abs(-------,-------)"

        state_cell = "state={:<12s}".format(self._classifier.state)

        print(" | ".join((t_cell, sip_cell, lps_cell, peak_cell,
                          imu_cell, ptr_cell, state_cell)))

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
        """Translate a breath event into output actions, branching on
        ``output_mode``. XAC opto pulses fire in encoder mode as a
        parallel side-channel for hosts that consume them — they do
        not interfere with the new GPIO encoder/button outputs.

        Encoder mode mapping:
            "puff"        → encoder pushbutton (GP20) + XAC puff pulse
            "puff_repeat" → encoder CW click + XAC puff pulse
            "double_puff" → encoder CW click + XAC puff double-pulse
                            (kept as today's "select" gesture)
            "sip"         → button 2 (GP21) + XAC sip pulse
            "sip_repeat"  → encoder CCW click + XAC sip pulse
            "double_sip"  → XAC sip double-pulse only

        Caveat: at the default ``repeat_max_hz = 20`` and
        ``xac_pulse_s = 0.05``, the XAC pulse fills the entire 50 ms
        repeat period. Pulses still toggle (so an edge-triggered host
        sees each one), but a level-triggered host sees a continuous
        closure. Either lower ``xac_pulse_s`` or ``repeat_max_hz``
        in config.txt if your XAC consumer needs a visible idle gap
        between pulses.

        Mouse mode mapping:
            "puff"        → HID left click
            "puff_repeat" → HID scroll wheel up
            "double_puff" → HID middle click
            "sip"         → HID right click
            "sip_repeat"  → HID scroll wheel down
            "double_sip"  → (no-op; reserved for future)
        """
        if self._verbose:
            print("Event: {}".format(event))

        if self._output_mode == "mouse":
            self._dispatch_mouse(event)
            return
        self._dispatch_encoder(event)

    def _dispatch_encoder(self, event):
        if event == "puff":
            self._encoder.press()
            self._xac.pulse_puff()
            self._display.flash("puff_click")
            return
        if event == "puff_repeat":
            for _ in range(self._puff_repeat_mult):
                self._encoder.click_cw()
                self._xac.pulse_puff()
            self._display.flash("up")
            return
        if event == "double_puff":
            # Reserve "double_puff" as the legacy SELECT gesture so
            # users coming from the old firmware don't lose it.
            self._encoder.click_cw()
            self._xac.pulse_puff_double()
            self._display.flash("up")
            return
        if event == "sip":
            self._encoder.press2()
            self._xac.pulse_sip()
            self._display.flash("sip_click")
            return
        if event == "sip_repeat":
            for _ in range(self._sip_repeat_mult):
                self._encoder.click_ccw()
                self._xac.pulse_sip()
            self._display.flash("down")
            return
        if event == "double_sip":
            self._xac.pulse_sip_double()
            self._display.flash("down")
            return
        print("SipPuff: unknown event '{}'".format(event))

    def _dispatch_mouse(self, event):
        if self._mouse is None or not self._mouse.available:
            # Fall through silently — the diagnostic heartbeat still
            # shows that the events are being classified.
            return
        if event == "puff":
            self._mouse.click_left()
            self._display.flash("puff_click")
            return
        if event == "puff_repeat":
            self._mouse.scroll(
                +self._mouse_scroll_amount * self._puff_repeat_mult)
            self._display.flash("up")
            return
        if event == "double_puff":
            self._mouse.click_middle()
            self._display.flash("puff_click")
            return
        if event == "sip":
            self._mouse.click_right()
            self._display.flash("sip_click")
            return
        if event == "sip_repeat":
            self._mouse.scroll(
                -self._mouse_scroll_amount * self._sip_repeat_mult)
            self._display.flash("down")
            return
        if event == "double_sip":
            self._display.flash("sip_click")
            return
        print("SipPuff: unknown event '{}'".format(event))
