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


def _clamp(v, lo, hi):
    """Clamp v to [lo, hi]."""
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def _deadband_signed(v, db):
    """Subtract a symmetric deadband, preserving sign and keeping the
    response continuous at the deadband edge (no jump from 0 to db).
    Returns 0.0 inside [-db, db].
    """
    if v > db:
        return v - db
    if v < -db:
        return v + db
    return 0.0


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

    The cursor deltas (rate_dx, rate_dy) are produced by one of two
    selectable movement types (``mode``):

      * ``"fusion"`` (default) — tilt-as-joystick. The fused
        quaternion gives the unit's absolute tilt relative to a zero
        ("level") pose; cursor *velocity* scales with how far it's
        tilted. Forward/back tilt (pitch) drives up/down, tipping
        side to side (roll) drives left/right. Tilt-and-hold keeps
        the cursor gliding; returning to level stops it. This is the
        recommended scheme for a hand-held BNO08x because both axes
        are gravity-referenced (no yaw drift).

      * ``"rate"`` — gyro air-mouse. Cursor velocity tracks the
        instantaneous yaw/pitch *angular rate*; the cursor only
        moves while the unit is rotating. Suits a head-mouse.

    Either way the drive value is run through an acceleration curve,
    fractionally accumulated (sub-pixel motion preserved across
    ticks), and clamped to HID range.

    A third output, ``abs_yaw_deg`` / ``abs_pitch_deg`` (quaternion
    angles relative to the zero pose), is always returned for the
    diagnostic heartbeat. The zero pose is set on the first call and
    refreshed by ``recenter()`` (or automatically after the cursor
    has been stationary for ``stillness_recenter_s`` seconds).

    Args:
        gain: linear scale on rate-mode deltas.
        deadband_dps: rate-mode rates below this (deg/s) read as zero.
        alpha: IIR low-pass on rate dps (0 < alpha ≤ 1). 1.0 = no
            filter. Default 0.4 ≈ 30 Hz cutoff at a 25 ms tick.
        accel_expo: power-curve exponent applied to the drive value
            in BOTH modes. 1.0 (default) = linear. >1.0 boosts large
            motions for fast traverse; <1.0 boosts small motions for
            fine control.
        max_per_tick: clamp output |dx|, |dy| to this (both modes).
        yaw_axis / pitch_axis: rate-mode gyro axis → yaw / pitch.
            Strings 'x'/'y'/'z' with optional sign, e.g. '-z'.
        stillness_recenter_s: re-zero the pose when the cursor has
            been stationary at least this many seconds. 0 disables.
        mode: "fusion" (default) or "rate" — see above.
        tilt_deadband_deg: fusion-mode tilt below this (deg from the
            level pose) reads as zero — keeps the cursor still when
            the unit is roughly level.
        tilt_gain: fusion-mode speed scale (cursor units per second
            per degree of tilt past the deadband).
        tilt_max_deg: fusion-mode tilt is clamped to this magnitude
            before scaling, so a big flip doesn't fling the cursor.
        invert_x / invert_y: flip fusion-mode left/right or up/down
            to match how the unit is held.
    """

    def __init__(self, gain=400.0, deadband_dps=1.5,
                 alpha=0.4, accel_expo=1.0,
                 max_per_tick=60.0,
                 yaw_axis="-z", pitch_axis="-x",
                 stillness_recenter_s=0.0,
                 mode="fusion",
                 tilt_deadband_deg=4.0, tilt_gain=25.0,
                 tilt_max_deg=35.0,
                 invert_x=False, invert_y=False):
        self._gain = float(gain)
        self._deadband_dps = float(deadband_dps)
        self._alpha = max(0.001, min(1.0, float(alpha)))
        self._accel_expo = float(accel_expo)
        self._max_per_tick = float(max_per_tick)
        self._yaw_idx,   self._yaw_sign   = _resolve_axis(yaw_axis)
        self._pitch_idx, self._pitch_sign = _resolve_axis(pitch_axis)
        self._stillness_s = float(stillness_recenter_s)

        self._mode = str(mode).strip().lower()
        if self._mode not in ("fusion", "rate"):
            print("Pointing: unknown mode '{}', using 'fusion'".format(
                self._mode))
            self._mode = "fusion"
        self._tilt_deadband_deg = float(tilt_deadband_deg)
        self._tilt_gain = float(tilt_gain)
        self._tilt_max_deg = float(tilt_max_deg)
        self._invert_x = bool(invert_x)
        self._invert_y = bool(invert_y)

        self._last_t = None
        self._zero_yaw = None
        self._zero_pitch = None
        self._zero_roll = None
        self._fyaw_dps = 0.0
        self._fpitch_dps = 0.0
        self._dx_carry = 0.0
        self._dy_carry = 0.0
        self._still_since = None

    @property
    def mode(self):
        return self._mode

    def recenter(self, yaw, pitch, roll):
        """Mark current absolute orientation as the new zero pose."""
        self._zero_yaw = yaw
        self._zero_pitch = pitch
        self._zero_roll = roll

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

    def _rate_drive(self, gyro, dt):
        """Gyro air-mouse: cursor velocity from yaw/pitch angular rate.
        Returns (rdx_raw, rdy_raw) pre-carry, pre-clamp.
        """
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

        return (self._curve(yaw_dps,   self._accel_expo, self._gain, dt),
                self._curve(pitch_dps, self._accel_expo, self._gain, dt))

    def _tilt_drive(self, abs_pitch_rad, abs_roll_rad, dt):
        """Tilt-as-joystick: cursor velocity from how far the unit is
        tilted off level. Forward/back tilt (pitch) → y, tipping side
        to side (roll) → x. Returns (rdx_raw, rdy_raw).
        """
        # Clamp magnitude first so a big flip saturates rather than
        # flings, then remove the near-level deadband.
        ex = _clamp(math.degrees(abs_roll_rad),
                    -self._tilt_max_deg, self._tilt_max_deg)
        ey = _clamp(math.degrees(abs_pitch_rad),
                    -self._tilt_max_deg, self._tilt_max_deg)
        ex = _deadband_signed(ex, self._tilt_deadband_deg)
        ey = _deadband_signed(ey, self._tilt_deadband_deg)

        rdx = self._curve(ex, self._accel_expo, self._tilt_gain, dt)
        rdy = self._curve(ey, self._accel_expo, self._tilt_gain, dt)
        if self._invert_x:
            rdx = -rdx
        if self._invert_y:
            rdy = -rdy
        return rdx, rdy

    def update(self, gyro, quat, now=None):
        """Feed one sample, returns
        (cursor_dx, cursor_dy, abs_yaw_deg, abs_pitch_deg).

        cursor_dx/dy come from whichever ``mode`` is active.

        gyro: (gx, gy, gz) rad/s, sensor-frame.
        quat: (i, j, k, real) unit quaternion, sensor-frame.
        """
        if now is None:
            now = time.monotonic()
        dt = 0.0 if self._last_t is None else (now - self._last_t)
        self._last_t = now

        # Absolute orientation from the fused quaternion. The zero pose
        # is captured on the first sample.
        yaw, pitch, roll = _quat_to_euler(*quat)
        if self._zero_yaw is None:
            self.recenter(yaw, pitch, roll)
        abs_yaw   = _wrap_pi(yaw  - self._zero_yaw)
        abs_pitch = pitch - self._zero_pitch
        abs_roll  = _wrap_pi(roll - self._zero_roll)

        if self._mode == "rate":
            rdx_raw, rdy_raw = self._rate_drive(gyro, dt)
        else:
            rdx_raw, rdy_raw = self._tilt_drive(abs_pitch, abs_roll, dt)

        rdx_int, self._dx_carry = self._split_int_carry(rdx_raw, self._dx_carry)
        rdy_int, self._dy_carry = self._split_int_carry(rdy_raw, self._dy_carry)

        cap = self._max_per_tick
        rdx_int = _clamp(rdx_int, -cap, cap)
        rdy_int = _clamp(rdy_int, -cap, cap)

        # Auto-recenter once the cursor has been stationary a while —
        # works for both modes since it keys off the emitted delta
        # (rate: not rotating; fusion: held near level).
        if self._stillness_s > 0.0:
            if rdx_int == 0 and rdy_int == 0:
                if self._still_since is None:
                    self._still_since = now
                elif (now - self._still_since) >= self._stillness_s:
                    self.recenter(yaw, pitch, roll)
                    self._still_since = now  # arm next interval
            else:
                self._still_since = None

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
