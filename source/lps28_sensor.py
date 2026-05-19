"""LPS28DFWTR digital pressure sensor driver.

This is the second pressure sensor on this prototype's I2C bus
(GP4 SDA / GP5 SCL, address 0x5C). It's a STMicroelectronics
24-bit absolute pressure sensor — water-resistant potting gel,
0.32 Pa noise, 260-1260 hPa range in default Mode 1.

The MPX5010DP analog sensor (PressureSensor in pressure_sensor.py)
remains the primary input for the breath classifier. This module
exposes the LPS28 reading purely for cross-comparison and serial
diagnostic output.

Register map (subset, from ST DS13317):
    0x0F WHO_AM_I       -> 0xB4
    0x10 CTRL_REG1      bits 6:3 ODR, bits 2:0 AVG
    0x11 CTRL_REG2      IF_ADD_INC etc; default 0x10
    0x28-2A PRESS_OUT   little-endian 24-bit
    0x2B-2C TEMP_OUT    little-endian 16-bit

Pressure formula in Mode 1: P_hPa = signed24(raw) / 4096.
1 hPa = 0.1 kPa.
"""

import time


_REG_WHO_AM_I    = 0x0F
_REG_CTRL_REG1   = 0x10
_REG_CTRL_REG2   = 0x11
_REG_PRESS_OUT   = 0x28

_WHO_AM_I_VALUE  = 0xB4

# CTRL_REG1: ODR=0100 (25 Hz), AVG=000 (no averaging) -> 0x20
_CTRL_REG1_25HZ  = 0x20

# 1 LSB = 1/4096 hPa in Mode 1.
_HPA_PER_LSB = 1.0 / 4096.0


class LPS28Sensor:
    """LPS28DFWTR pressure sensor over a shared busio.I2C bus.

    Args:
        i2c: a fully-locked busio.I2C (the caller must NOT have it
            locked when constructing — the constructor handles its
            own lock cycles).
        addr: I2C address — 0x5C if SA0=GND (default), 0x5D if SA0=VDD.
        verbose: print extra diagnostics on init/read errors.
    """

    def __init__(self, i2c, addr=0x5C, verbose=False):
        self._i2c = i2c
        self._addr = addr
        self._verbose = bool(verbose)
        self._available = False
        self._baseline_kpa = 0.0

        if i2c is None:
            print("LPS28: no I2C bus provided")
            return

        # Verify the chip ID before configuring.
        try:
            who = self._read_reg(_REG_WHO_AM_I, 1)[0]
        except Exception as e:
            print("LPS28: WHO_AM_I read failed at 0x{:02X} ({})".format(
                addr, e))
            return

        if who != _WHO_AM_I_VALUE:
            print("LPS28: wrong WHO_AM_I = 0x{:02X} (expected 0x{:02X})".format(
                who, _WHO_AM_I_VALUE))
            return

        # Enable continuous output at 25 Hz, no averaging.
        try:
            self._write_reg(_REG_CTRL_REG1, _CTRL_REG1_25HZ)
        except Exception as e:
            print("LPS28: CTRL_REG1 write failed ({})".format(e))
            return

        # Give the chip a few cycles to produce its first sample.
        time.sleep(0.05)
        self._available = True
        print("LPS28: ready at 0x{:02X} (ODR=25Hz)".format(addr))

    @property
    def available(self):
        """True if WHO_AM_I matched and CTRL_REG1 was written successfully."""
        return self._available

    @property
    def baseline_kpa(self):
        """Currently learned baseline pressure, in kPa (absolute)."""
        return self._baseline_kpa

    # --- Public reads --------------------------------------------

    def read_pressure_hpa(self):
        """Absolute pressure in hPa (millibar)."""
        if not self._available:
            return 0.0
        try:
            buf = self._read_reg(_REG_PRESS_OUT, 3)
        except Exception as e:
            if self._verbose:
                print("LPS28: pressure read failed ({})".format(e))
            return 0.0
        # 24-bit little-endian, signed.
        raw = buf[0] | (buf[1] << 8) | (buf[2] << 16)
        if raw & 0x800000:
            raw -= 0x1000000
        return raw * _HPA_PER_LSB

    def read_pressure_kpa(self):
        """Absolute pressure in kPa."""
        return self.read_pressure_hpa() * 0.1

    def gauge_kpa(self):
        """Pressure relative to the learned baseline, in kPa."""
        return self.read_pressure_kpa() - self._baseline_kpa

    # --- Calibration ---------------------------------------------

    def recenter_now(self):
        """Snap the baseline so the next gauge_kpa() reads ~0.

        Reads one fresh absolute sample and stores it as the new
        baseline — much cheaper than rerunning calibrate_baseline()
        when the user just wants to clear an accumulated drift.

        Safe to call any time after init. Returns the new baseline.
        """
        if not self._available:
            return self._baseline_kpa
        new_baseline = self.read_pressure_kpa()
        if new_baseline != 0.0:
            self._baseline_kpa = new_baseline
            if self._verbose:
                print("LPS28: recenter -> baseline={:.4f}kPa".format(
                    self._baseline_kpa))
        return self._baseline_kpa

    def calibrate_baseline(self, duration_s=1.5):
        """Average readings over duration_s and store as baseline."""
        if not self._available:
            return
        start = time.monotonic()
        n = 0
        total = 0.0
        kmin = None
        kmax = None
        while time.monotonic() - start < duration_s:
            k = self.read_pressure_kpa()
            total += k
            kmin = k if kmin is None else min(kmin, k)
            kmax = k if kmax is None else max(kmax, k)
            n += 1
            time.sleep(0.04)   # ~25 Hz, matching ODR
        if n == 0:
            return
        self._baseline_kpa = total / n
        ptp = (kmax - kmin) if (kmin is not None and kmax is not None) else 0.0
        print("LPS28: baseline={:.4f}kPa noise(p2p)={:.4f}kPa "
              "samples={}".format(self._baseline_kpa, ptp, n))

    # --- Internals -----------------------------------------------

    def _read_reg(self, reg, n):
        buf = bytearray(n)
        while not self._i2c.try_lock():
            pass
        try:
            self._i2c.writeto_then_readfrom(self._addr, bytes([reg]), buf)
        finally:
            self._i2c.unlock()
        return buf

    def _write_reg(self, reg, value):
        while not self._i2c.try_lock():
            pass
        try:
            self._i2c.writeto(self._addr, bytes([reg, value]))
        finally:
            self._i2c.unlock()
