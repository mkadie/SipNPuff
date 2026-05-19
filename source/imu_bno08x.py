"""BNO08x IMU driver wrapper (BNO080 / BNO085 / BNO086 family).

Sits on the same I2C bus as the LPS28 + SSD1306. The Adafruit
``adafruit_bno08x`` driver does the heavy lifting — this module
adds:

  * tolerant init (auto-detect 0x4A vs 0x4B; survives a missing
    library or an absent chip without bricking the boot sequence)
  * a single ``poll()`` that returns a snapshot dict, so the main
    loop doesn't talk to multiple bno properties per iteration
  * a ``Pointing`` helper that converts the quaternion + gyro
    stream into:
        - relative dx/dy from yaw/pitch *rate* (head-mouse style)
        - absolute yaw/pitch zeroed at boot (re-centerable)

Conventions: gyro in rad/s, accel in m/s², mag in µT, quaternion
as (i, j, k, real). Pointing scaling is configurable via
``imu_pointing_gain`` / ``imu_pointing_deadband_dps`` in config.txt.
"""

import math
import time


_BNO08X_ADDRS = (0x4A, 0x4B)


def _try_import():
    """Lazy-import the Adafruit driver. Returns (BNO08X_I2C, reports)
    or (None, None) if the library isn't installed.
    """
    try:
        import adafruit_bno08x
        from adafruit_bno08x.i2c import BNO08X_I2C
        reports = (
            adafruit_bno08x.BNO_REPORT_ACCELEROMETER,
            adafruit_bno08x.BNO_REPORT_GYROSCOPE,
            adafruit_bno08x.BNO_REPORT_MAGNETOMETER,
            adafruit_bno08x.BNO_REPORT_ROTATION_VECTOR,
        )
        return BNO08X_I2C, reports
    except ImportError as e:
        print("IMU: adafruit_bno08x not installed ({})".format(e))
        return None, None


def _quat_to_euler(qi, qj, qk, qr):
    """Convert quaternion (i, j, k, real) to (yaw, pitch, roll) radians.

    Standard aerospace ZYX intrinsic decomposition. Yaw wraps to
    [-pi, pi]; pitch is clamped at +/-pi/2 by the asin domain.
    """
    sinr_cosp = 2.0 * (qr * qi + qj * qk)
    cosr_cosp = 1.0 - 2.0 * (qi * qi + qj * qj)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * (qr * qj - qk * qi)
    if sinp >= 1.0:
        pitch = math.pi / 2.0
    elif sinp <= -1.0:
        pitch = -math.pi / 2.0
    else:
        pitch = math.asin(sinp)

    siny_cosp = 2.0 * (qr * qk + qi * qj)
    cosy_cosp = 1.0 - 2.0 * (qj * qj + qk * qk)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return yaw, pitch, roll


def _wrap_pi(angle):
    """Wrap a radian angle to [-pi, pi]. Used for yaw deltas across
    the ±pi seam.
    """
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def _resolve_axis(spec):
    """Parse 'z', '-z', '+x' etc. into (axis_index, sign).
    Bare 'x'/'y'/'z' defaults to positive sign.
    """
    s = str(spec).strip().lower()
    sign = 1.0
    if s.startswith("-"):
        sign = -1.0
        s = s[1:]
    elif s.startswith("+"):
        s = s[1:]
    idx = _AXIS_INDEX.get(s)
    if idx is None:
        raise ValueError("bad axis '{}', expect one of x/y/z (with optional +/-)".format(spec))
    return idx, sign


class Pointing:
    """Quaternion + gyro → cursor-deltas helper.

    Two outputs in parallel:
      * rate_dx, rate_dy        — integrated gyro yaw/pitch *rate*,
                                  optionally low-pass filtered, run
                                  through an acceleration curve,
                                  fractionally accumulated, and
                                  clamped to HID range. Suits a
                                  head-mouse.
      * abs_yaw_deg, abs_pitch_deg — quaternion-derived absolute
                                  angles relative to a zero pose.
                                  Suits a "re-center to look straight
                                  ahead" scheme. The zero pose is
                                  set on first call and refreshed
                                  whenever ``recenter()`` is called
                                  (or automatically after the IMU
                                  has been still for
                                  ``stillness_recenter_s`` seconds,
                                  if that's enabled).

    Args:
        gain: linear scale on rate-based deltas.
        deadband_dps: rates below this (deg/s) read as zero — kills
            stationary gyro jitter.
        alpha: IIR low-pass on rate dps (0 < alpha ≤ 1). 1.0 = no
            filter. Default 0.4 ≈ 30 Hz cutoff at a 25 ms tick.
        accel_expo: power-curve exponent applied to |rate_dps|. 1.0
            (default) = linear. >1.0 boosts large motions for fast
            traverse; <1.0 boosts small motions for fine control.
        max_per_tick: clamp output |dx|, |dy| to this. Defaults to
            60 — well under the int8 range of HID mouse, even at
            sustained slow-tick rates.
        yaw_axis / pitch_axis: which gyro axis maps to yaw / pitch.
            Strings 'x'/'y'/'z' with optional sign, e.g. '-z'. The
            default axis assignment matches an Adafruit-mounted
            BNO085 with the chip's +Z up; rotate / mirror for other
            mountings without rewriting code.
        stillness_recenter_s: re-zero the absolute pose when the
            filtered rate magnitude has been below deadband for at
            least this many seconds. 0 (default) disables.
    """

    def __init__(self, gain=400.0, deadband_dps=1.5,
                 alpha=0.4, accel_expo=1.0,
                 max_per_tick=60.0,
                 yaw_axis="-z", pitch_axis="-x",
                 stillness_recenter_s=0.0):
        self._gain = float(gain)
        self._deadband_dps = float(deadband_dps)
        self._alpha = max(0.001, min(1.0, float(alpha)))
        self._accel_expo = float(accel_expo)
        self._max_per_tick = float(max_per_tick)
        self._yaw_idx,   self._yaw_sign   = _resolve_axis(yaw_axis)
        self._pitch_idx, self._pitch_sign = _resolve_axis(pitch_axis)
        self._stillness_s = float(stillness_recenter_s)

        self._last_t = None
        self._zero_yaw = None
        self._zero_pitch = None
        self._fyaw_dps = 0.0
        self._fpitch_dps = 0.0
        self._dx_carry = 0.0
        self._dy_carry = 0.0
        self._still_since = None

    def recenter(self, yaw, pitch):
        """Mark current absolute orientation as the new zero pose."""
        self._zero_yaw = yaw
        self._zero_pitch = pitch

    @staticmethod
    def _curve(dps, expo, gain, dt):
        """Apply acceleration curve: sign * |dps|^expo * gain * dt."""
        if dps == 0.0:
            return 0.0
        if expo == 1.0:
            return dps * gain * dt
        sign = 1.0 if dps > 0.0 else -1.0
        return sign * (abs(dps) ** expo) * gain * dt

    def _split_int_carry(self, value, carry):
        """Add ``value`` to ``carry``, return (int_delta, new_carry).
        Output is rounded toward zero so the cursor stops cleanly when
        the input rate hits zero — `int(value)` would round 0.999
        down to 0 and lose drift; banker's-style truncation toward
        zero keeps us symmetric.
        """
        total = carry + value
        # int() in MicroPython truncates toward zero; matches our
        # symmetric-around-0 expectation for both positive and
        # negative deltas.
        whole = int(total)
        return whole, (total - whole)

    def update(self, gyro, quat, now=None):
        """Feed one sample, returns
        (rate_dx, rate_dy, abs_yaw_deg, abs_pitch_deg).

        gyro: (gx, gy, gz) rad/s, sensor-frame.
        quat: (i, j, k, real) unit quaternion, sensor-frame.
        """
        if now is None:
            now = time.monotonic()
        dt = 0.0 if self._last_t is None else (now - self._last_t)
        self._last_t = now

        yaw_dps_raw   = math.degrees(gyro[self._yaw_idx])   * self._yaw_sign
        pitch_dps_raw = math.degrees(gyro[self._pitch_idx]) * self._pitch_sign

        # IIR low-pass on rate. alpha=1 short-circuits to raw value.
        if self._alpha >= 1.0:
            self._fyaw_dps   = yaw_dps_raw
            self._fpitch_dps = pitch_dps_raw
        else:
            a = self._alpha
            self._fyaw_dps   += a * (yaw_dps_raw   - self._fyaw_dps)
            self._fpitch_dps += a * (pitch_dps_raw - self._fpitch_dps)

        yaw_dps   = self._fyaw_dps   if abs(self._fyaw_dps)   >= self._deadband_dps else 0.0
        pitch_dps = self._fpitch_dps if abs(self._fpitch_dps) >= self._deadband_dps else 0.0

        rdx_raw = self._curve(yaw_dps,   self._accel_expo, self._gain, dt)
        rdy_raw = self._curve(pitch_dps, self._accel_expo, self._gain, dt)

        rdx_int, self._dx_carry = self._split_int_carry(rdx_raw, self._dx_carry)
        rdy_int, self._dy_carry = self._split_int_carry(rdy_raw, self._dy_carry)

        cap = self._max_per_tick
        if rdx_int >  cap: rdx_int =  cap
        if rdx_int < -cap: rdx_int = -cap
        if rdy_int >  cap: rdy_int =  cap
        if rdy_int < -cap: rdy_int = -cap

        # Absolute orientation from quaternion.
        yaw, pitch, _roll = _quat_to_euler(*quat)
        if self._zero_yaw is None:
            self.recenter(yaw, pitch)

        # Optional auto-recenter after sustained stillness.
        if self._stillness_s > 0.0:
            if yaw_dps == 0.0 and pitch_dps == 0.0:
                if self._still_since is None:
                    self._still_since = now
                elif (now - self._still_since) >= self._stillness_s:
                    self.recenter(yaw, pitch)
                    self._still_since = now  # arm next interval
            else:
                self._still_since = None

        abs_yaw = _wrap_pi(yaw - self._zero_yaw)
        abs_pitch = pitch - self._zero_pitch

        return rdx_int, rdy_int, math.degrees(abs_yaw), math.degrees(abs_pitch)


class BNO08xSensor:
    """One BNO08x on a shared busio.I2C bus.

    Args:
        i2c: shared busio.I2C (bus is locked internally by the
            Adafruit driver — caller must not be holding the lock).
        addr: 0x4A (default), 0x4B (alt strap), or None to auto-detect.
        verbose: print extra lines on init/read failures.
        slot_label: short tag (e.g. "imu1") shown in log lines.
    """

    def __init__(self, i2c, addr=None, verbose=False, slot_label="imu"):
        self._i2c = i2c
        self._verbose = bool(verbose)
        self._label = slot_label
        self._available = False
        self._addr = None
        self._bno = None

        if i2c is None:
            print("{}: no I2C bus".format(slot_label))
            return

        cls, reports = _try_import()
        if cls is None:
            return

        candidates = (addr,) if addr is not None else _BNO08X_ADDRS
        for cand in candidates:
            try:
                bno = cls(i2c, address=cand)
                for r in reports:
                    bno.enable_feature(r)
                self._bno = bno
                self._addr = cand
                self._available = True
                print("{}: BNO08x ready at 0x{:02X}".format(slot_label, cand))
                return
            except Exception as e:
                if self._verbose or addr is not None:
                    print("{}: 0x{:02X} init failed ({})".format(
                        slot_label, cand, e))

        print("{}: no BNO08x found at {}".format(
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
        """One snapshot. Returns dict with accel/gyro/mag/quat tuples,
        or None if the sensor is unavailable or the read failed.
        """
        if not self._available:
            return None
        try:
            return {
                "accel": self._bno.acceleration,
                "gyro":  self._bno.gyro,
                "mag":   self._bno.magnetic,
                "quat":  self._bno.quaternion,
            }
        except Exception as e:
            if self._verbose:
                print("{}: poll failed ({})".format(self._label, e))
            return None
