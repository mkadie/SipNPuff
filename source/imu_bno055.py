"""BNO055 IMU driver wrapper.

Bosch BNO055 9-DoF IMU on the shared I2C bus. Different chip,
different protocol, different default address from the BNO085 —
but the wrapper exposes the **same** ``poll()`` snapshot dict
(accel / gyro / mag / quat) so the same `Pointing` helper drives
either sensor with no branching.

Default I2C addresses are 0x28 (SA0/COM3 = GND) or 0x29 (SA0 = VDD).

Quaternion-order normalization
------------------------------
Adafruit's `adafruit_bno055.quaternion` returns ``(w, x, y, z)``.
The BNO08x driver returns ``(x, y, z, w)`` (== (i, j, k, real)).
We normalize to the BNO08x order in this wrapper so downstream
math is uniform.
"""

import time


_BNO055_ADDRS = (0x28, 0x29)
_NDOF_MODE = 0x0C   # 9-DoF fused output (built-in sensor fusion)


def _try_import():
    """Lazy-import. Returns the BNO055_I2C class or None."""
    try:
        import adafruit_bno055
        return adafruit_bno055.BNO055_I2C
    except ImportError as e:
        print("IMU: adafruit_bno055 not installed ({})".format(e))
        return None


class BNO055Sensor:
    """One BNO055 on a shared busio.I2C bus.

    Args:
        i2c: shared busio.I2C.
        addr: 0x28 (default), 0x29 (alt strap), or None to auto-detect.
        verbose: print extra lines on init/read failures.
        slot_label: short tag (e.g. "imu1") shown in log lines.
    """

    def __init__(self, i2c, addr=None, verbose=False, slot_label="imu"):
        self._i2c = i2c
        self._verbose = bool(verbose)
        self._label = slot_label
        self._available = False
        self._addr = None
        self._sensor = None

        if i2c is None:
            print("{}: no I2C bus".format(slot_label))
            return

        cls = _try_import()
        if cls is None:
            return

        candidates = (addr,) if addr is not None else _BNO055_ADDRS
        for cand in candidates:
            try:
                bno = cls(i2c, address=cand)
                # Force NDOF (9-DoF fused) so quaternion + heading are
                # populated. The driver default is usually NDOF, but
                # explicit keeps us robust to library version drift.
                try:
                    bno.mode = _NDOF_MODE
                except Exception:
                    pass
                # Brief settle so the first read isn't garbage.
                time.sleep(0.05)
                self._sensor = bno
                self._addr = cand
                self._available = True
                print("{}: BNO055 ready at 0x{:02X}".format(slot_label, cand))
                return
            except Exception as e:
                if self._verbose or addr is not None:
                    print("{}: 0x{:02X} init failed ({})".format(
                        slot_label, cand, e))

        print("{}: no BNO055 found at {}".format(
            slot_label,
            ", ".join("0x{:02X}".format(a) for a in candidates)))

    @property
    def available(self):
        return self._available

    @property
    def address(self):
        return self._addr

    @property
    def label(self):
        return self._label

    def poll(self):
        """One snapshot. Tuple components are normalised to the BNO08x
        convention so the consuming Pointing helper is sensor-agnostic.
        Returns None if a read fails or one of the channels is None
        (BNO055 returns ``None`` for a not-yet-ready value early in
        startup — propagating that would crash the math).
        """
        if not self._available:
            return None
        try:
            accel = self._sensor.acceleration   # (x, y, z) m/s²
            gyro  = self._sensor.gyro           # (x, y, z) rad/s
            mag   = self._sensor.magnetic       # (x, y, z) µT
            quat_wxyz = self._sensor.quaternion # (w, x, y, z)
        except Exception as e:
            if self._verbose:
                print("{}: poll failed ({})".format(self._label, e))
            return None
        if (accel is None or gyro is None or mag is None
                or quat_wxyz is None):
            return None
        if any(c is None for c in accel) or any(c is None for c in gyro):
            return None
        if any(c is None for c in mag) or any(c is None for c in quat_wxyz):
            return None
        qw, qx, qy, qz = quat_wxyz
        return {
            "accel": tuple(accel),
            "gyro":  tuple(gyro),
            "mag":   tuple(mag),
            "quat":  (qx, qy, qz, qw),   # (i, j, k, real) order
        }
