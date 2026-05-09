"""MPX5010DP pressure sensor driver.

Reads the analog output of a Freescale MPX5010DP differential
pressure sensor through a 10k/20k voltage divider on the Pico's
ADC. Provides:

  * raw_average() — oversampled 16-bit ADC reading
  * voltage()     — actual voltage at the ADC pin
  * sensor_v()    — voltage at the sensor output (divider undone)
  * pressure_kpa()— differential pressure, kPa, signed
  * gauge_kpa()   — pressure relative to learned baseline

The baseline is auto-calibrated at startup by sampling for
``baseline_calibrate_s`` seconds while the user is told to leave
the mouthpiece alone. Subsequent gauge_kpa() readings are
zero-referenced — this is what the BreathClassifier consumes.
"""

import time
import analogio

from hardware_config import _pin


_ADC_FULL_SCALE = 65535
_ADC_REF_V = 3.3


class PressureSensor:
    """Oversampled MPX5010DP reader with auto-baseline.

    Args:
        config: variant config dict from hardware_config.load_config().
    """

    def __init__(self, config):
        self._supply_v   = config["pressure_supply_v"]
        self._divider    = config["pressure_divider_ratio"]
        self._mpx_offset = config["mpx_offset"]
        self._mpx_slope  = config["mpx_slope"]
        self._oversample = max(1, int(config["pressure_oversample"]))
        self._baseline_s = float(config["baseline_calibrate_s"])
        self._verbose    = bool(config.get("verbose", False))

        try:
            self._adc = analogio.AnalogIn(_pin(config["pressure_pin"]))
            self._available = True
            print("Pressure: ADC on {} ({}x oversampling)".format(
                config["pressure_pin"], self._oversample))
        except Exception as e:
            print("Pressure: ADC init failed ({})".format(e))
            self._adc = None
            self._available = False

        self._baseline_kpa = 0.0

    @property
    def available(self):
        """True if the ADC initialised successfully."""
        return self._available

    @property
    def baseline_kpa(self):
        """Currently learned zero-pressure baseline, in kPa."""
        return self._baseline_kpa

    # --- Raw conversions ----------------------------------------

    def raw_average(self):
        """Oversampled raw 16-bit ADC value. Returns 0 if ADC missing."""
        if not self._available:
            return 0
        n = self._oversample
        total = 0
        for _ in range(n):
            total += self._adc.value
        return total // n

    def voltage(self, raw=None):
        """Convert (or read+convert) raw ADC to volts at the pin."""
        if raw is None:
            raw = self.raw_average()
        return (raw / _ADC_FULL_SCALE) * _ADC_REF_V

    def sensor_v(self, raw=None):
        """Voltage at the sensor's Vout (undoes the 10k/20k divider)."""
        return self.voltage(raw) * self._divider

    def pressure_kpa(self, raw=None):
        """Absolute differential pressure in kPa (signed).

        For the MPX5010DP this is positive for a puff and negative
        when used as a differential sensor with a sip pulled across
        port 2 — at rest both ports see ambient and Vout sits near
        VS * mpx_offset.
        """
        v_sensor = self.sensor_v(raw)
        # Vout = VS * (mpx_slope * P + mpx_offset)  →  solve for P.
        return (v_sensor / self._supply_v - self._mpx_offset) / self._mpx_slope

    def gauge_kpa(self, raw=None):
        """Pressure relative to the learned baseline."""
        return self.pressure_kpa(raw) - self._baseline_kpa

    # --- Baseline calibration -----------------------------------

    def calibrate_baseline(self, duration_s=None):
        """Sample with no breath applied and learn the zero point.

        Blocks for ``duration_s`` seconds. The user must NOT touch the
        mouthpiece during this window. Stores the mean as the baseline
        and prints a noise estimate so the operator can sanity-check
        the divider and decoupling before trusting thresholds.

        Returns:
            (mean_kpa, peak_to_peak_kpa) — useful for picking
            sensible threshold values.
        """
        if not self._available:
            print("Pressure: skipping baseline (ADC unavailable)")
            self._baseline_kpa = 0.0
            return (0.0, 0.0)

        dur = float(duration_s if duration_s is not None else self._baseline_s)
        if self._verbose:
            print("Pressure: calibrating baseline for {:.2f}s "
                  "— do not touch mouthpiece".format(dur))

        start = time.monotonic()
        n = 0
        total = 0.0
        kmin = None
        kmax = None
        while time.monotonic() - start < dur:
            k = self.pressure_kpa()
            total += k
            kmin = k if kmin is None else min(kmin, k)
            kmax = k if kmax is None else max(kmax, k)
            n += 1
            time.sleep(0.005)

        if n == 0:
            self._baseline_kpa = 0.0
            return (0.0, 0.0)

        mean = total / n
        ptp = (kmax - kmin) if (kmin is not None and kmax is not None) else 0.0
        self._baseline_kpa = mean
        print("Pressure: baseline={:.3f}kPa noise(p2p)={:.3f}kPa "
              "samples={}".format(mean, ptp, n))
        return (mean, ptp)
