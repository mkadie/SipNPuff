"""Hardware configuration for the T-Rex Sip-N-Puff device.

Pin map, sensor coefficients, and tunable thresholds are kept here.
Run-time-tunable values (thresholds, timings, mode) are overlaid by
config.txt at startup via _load_user_config().

Pin names are stored as strings (e.g. "GP26") and resolved at init
time with _pin() so the same config dict can be sanity-printed
without touching hardware.
"""

import board


def _pin(name):
    """Resolve a pin name string (e.g. "GP26") to a board pin object.

    Returns None when name is None so optional pins can be omitted
    from the config without special-casing each call site.
    """
    if name is None:
        return None
    return getattr(board, name)


# --- Variant definitions -----------------------------------------

# pico2_mpx5010dp:
#   Raspberry Pi Pico 2 (RP2350) with MPX5010DP analog pressure sensor.
#   This is the through-hole "Maker Faire" build variant.
VARIANTS = {
    "pico2_mpx5010dp": {
        # --- Sensor: MPX5010DP analog, voltage-divider'd to ADC ---
        "pressure_pin": "GP26",
        "pressure_supply_v": 5.0,        # MPX5010DP nominal VS
        "pressure_divider_ratio": 1.5,   # (10k+20k)/20k — undo at ADC
        # MPX5010DP transfer fn: Vout = VS * (0.09 * P_kPa + 0.04)
        "mpx_offset": 0.04,
        "mpx_slope": 0.09,
        # ADC oversampling — RP2040/RP2350 ADCs have a noise floor
        # so averaging is mandatory for stable thresholding.
        "pressure_oversample": 16,

        # --- Encoder emulation outputs ---
        "enc_a_pin":   "GP18",
        "enc_b_pin":   "GP19",
        "enc_btn_pin": "GP20",
        # Second momentary-button output: short sip in encoder mode.
        # Wired as a sibling of enc_btn — tie host-side as another
        # button-to-GND switch with its own pull-up.
        "enc_btn2_pin": "GP21",
        # Quadrature half-period: time spent in each of the 4 phases
        # of one click. 2 ms gives a 4 ms click — well below typical
        # mechanical encoder rates and easy for any host to capture.
        "encoder_phase_s": 0.002,
        # Active-low button: idle = high, pressed = low (matches a
        # typical encoder shaft switch with internal pull-up on host).
        "encoder_button_active_low": True,
        "encoder_button_press_s": 0.05,

        # --- Xbox Adaptive Controller dry-contact outputs ---
        # Two independent PC817 optocouplers — one per breath direction.
        # Each Pico GPIO drives the opto's anode through a 220 Ω resistor.
        "xac_puff_pin": "GP1",   # Puff_enable -> 220R -> PC817 anode
        "xac_sip_pin":  "GP0",   # Sip_enable  -> 220R -> PC817 anode
        # PC817 forward-biased = signal asserted to XAC.
        # Pico GPIO HIGH lights the LED → XAC sees switch closed.
        "xac_active_low": False,
        "xac_pulse_s": 0.05,
        # Gap between the two pulses of a double-tap. Must be long
        # enough that the host registers two distinct closures.
        "xac_double_gap_s": 0.05,

        # --- Breath thresholds (kPa above baseline) ---
        # Tuned for an unloaded MPX5010DP and a rubber-chicken bellows.
        # Override these in config.txt after benchtop calibration.
        "puff_on_kpa":  0.30,
        "puff_off_kpa": 0.20,   # hysteresis: must drop below this to release
        "sip_on_kpa":  -0.30,
        "sip_off_kpa": -0.20,

        # --- Event timings ---
        # Two puffs whose release-to-press gap is below this window
        # are treated as a "double puff" (== select).
        "double_puff_window_s": 0.45,
        # Symmetric for sip — kept independent so puff and sip can
        # be tuned to a user's asymmetric breath profile.
        "double_sip_window_s": 0.45,
        # Hold-to-scroll: after this much continuous puff, start
        # emitting repeat ticks at a pressure-scaled rate.
        "hold_to_repeat_s": 0.40,
        "repeat_min_hz":  3.0,    # tick rate at puff_on_kpa
        "repeat_max_hz": 20.0,    # tick rate at repeat_full_scale_kpa
        "repeat_full_scale_kpa": 3.0,

        # --- Optional 1.8" SPI color LCD (ST7735R, 128x160) ---
        # Wiring matches J2 connector in project reference doc 10.5.
        # XAC optos now live on GP0 / GP1 (see above), so the LCD
        # backlight on GP16 has no pin conflict to worry about.
        "display_enabled":     True,
        "display_controller":  "st7735r",
        "display_width":       128,
        "display_height":      160,
        "display_rotation":    270,         # landscape, USB at the right
        # 4 MHz is the safe-bet first-light value for cheap modules
        # on unshielded leads. Once the panel is proven, raise to
        # 12–24 MHz from config.txt.
        "display_baudrate":    4_000_000,
        "display_sck_pin":     "GP10",
        "display_mosi_pin":    "GP11",
        "display_miso_pin":    "GP12",      # not used by ST7735, but claimed by busio.SPI
        "display_cs_pin":      "GP13",
        "display_dc_pin":      "GP14",
        "display_reset_pin":   "GP15",
        "display_backlight_pin": "GP16",    # set to None if tied to 3.3V
        # I2C bus for OLED variants (J1 connector — Section 10.5 of
        # the project reference doc). Shared with pressure sensor and
        # any future IMU.
        "display_i2c_sda_pin": "GP4",
        "display_i2c_scl_pin": "GP5",
        "display_i2c_address": 0x3C,        # 0x3C default, 0x3D alternative
        # 100 kHz is the safe-bet first-light value. Many cheap
        # SSD1306 modules ETIMEDOUT during init at 400 kHz on
        # unshielded jumper wires; once you've confirmed the panel
        # works, raise to 400 kHz for a snappier refresh.
        "display_i2c_frequency": 100_000,
        "display_update_hz":   10,          # throttle redraws
        # Tab-type offsets. Aliexpress 1.8" panels are most often
        # the "GreenTab" variant: visible pixels start at column 2,
        # row 1 within the controller's framebuffer. If the screen
        # stays blank or shows garbage at the edge, try:
        #   RedTab:    colstart=0, rowstart=0, bgr=False
        #   BlackTab:  colstart=0, rowstart=0, bgr=True
        #   M5Stack:   colstart=0, rowstart=0, invert=True
        "display_colstart":  2,
        "display_rowstart":  1,
        "display_bgr":       False,
        "display_invert":    False,
        # Boot-time R/G/B/W flash so a wiring or driver problem is
        # visible immediately. Set false once you trust the display.
        "display_test_pattern": True,
        "display_bg_color":    0x000000,
        "display_text_color":  0xFFFFFF,
        "display_puff_color":  0xFF6020,    # warm orange
        "display_sip_color":   0x2080FF,    # cool blue
        "display_threshold_color": 0x808080,

        # --- Modes & misc ---
        # "run":         normal sip/puff → encoder + XAC outputs
        # "diagnostic":  stream raw sensor values, no outputs driven
        "mode": "run",
        "verbose": True,
        # Auto-calibrate baseline at startup using the first N seconds
        # of "no breath" readings.
        "baseline_calibrate_s": 1.5,
        # Main loop poll period — short enough to catch a sharp puff
        # edge but slow enough to leave headroom for I/O.
        "poll_period_s": 0.005,
    },
}


DEFAULT_VARIANT = "pico2_mpx5010dp"


# --- English-readable display aliases ---------------------------
#
# Values accepted by the user-facing ``display = ...`` key in
# config.txt. Whitespace and case are normalised before lookup, so
# all of these resolve identically:
#
#     display = SSD1306 OLED 128x64
#     display = ssd1306_oled_128x64
#     display = ssd1306-oled-128x64
#
# The right-hand side is the existing DISPLAY_PRESETS key.
DISPLAY_ALIASES = {
    "none":                              "none",
    "off":                               "none",
    "disabled":                          "none",
    "ssd1306 oled 128x64":               "ssd1306_128x64_i2c",
    "ssd1306 oled 128x32":               "ssd1306_128x32_i2c",
    "st7735r color lcd 128x160 greentab": "st7735r_128x160_greentab",
    "st7735r color lcd 128x160 redtab":   "st7735r_128x160_redtab",
    "st7735r color lcd 128x160 blacktab": "st7735r_128x160_blacktab",
    "st7735r color lcd 128x128":         "st7735r_128x128",
    "st7735r color lcd 80x160":          "st7735r_80x160",
    "st7789 color lcd 240x240":          "st7789_240x240",
    "st7789 color lcd 240x320":          "st7789_240x320",
    "st7789 color lcd 135x240":          "st7789_135x240",
    "ili9341 color lcd 240x320":         "ili9341_240x320",
    "gc9a01 color lcd 240x240 round":    "gc9a01_240x240_round",
}


def _normalize_alias(value):
    """Lowercase + collapse [_-] into spaces + squeeze whitespace.
    Lets the user write `SSD1306 OLED 128x64`, `ssd1306-oled-128x64`,
    or `ssd1306_oled_128x64` interchangeably.
    """
    s = str(value).strip().lower().replace("_", " ").replace("-", " ")
    return " ".join(s.split())


# --- I2C device names ------------------------------------------
#
# Values accepted by ``i2c_pressure`` and ``i2c_imu_1..4`` in
# config.txt. The optional ``@0xNN`` suffix locks an address; without
# it the driver auto-detects across the chip's strap options.
I2C_DEVICE_KINDS = {
    "lps28":   {"driver": "lps28",   "default_addrs": (0x5C, 0x5D)},
    "bno085":  {"driver": "bno08x",  "default_addrs": (0x4A, 0x4B)},
    "bno086":  {"driver": "bno08x",  "default_addrs": (0x4A, 0x4B)},
    "bno080":  {"driver": "bno08x",  "default_addrs": (0x4A, 0x4B)},
    "bno055":  {"driver": "bno055",  "default_addrs": (0x28, 0x29)},
}

# Slots whose value is parsed as a device-spec ("kind[@0xNN]") rather
# than coerced. Listing them here lets the parser keep the raw string
# instead of munging it through _coerce.
_I2C_SLOT_KEYS = (
    "i2c_pressure",
    "i2c_imu_1", "i2c_imu_2", "i2c_imu_3", "i2c_imu_4",
)


def parse_i2c_device_spec(spec):
    """Parse 'kind' or 'kind@0xNN' into (driver, addr_or_None).
    Returns (None, None) for 'none' / blank / unknown kind so the
    caller can simply skip the slot.
    """
    if spec is None:
        return (None, None)
    s = str(spec).strip().lower()
    if not s or s in ("none", "off", "disabled"):
        return (None, None)
    kind, _, tail = s.partition("@")
    kind = kind.strip()
    info = I2C_DEVICE_KINDS.get(kind)
    if info is None:
        print("I2C: unknown device kind '{}'".format(kind))
        return (None, None)
    addr = None
    tail = tail.strip()
    if tail:
        try:
            addr = int(tail, 0)
        except ValueError:
            print("I2C: bad address '{}' for {}; using auto-detect".format(
                tail, kind))
    return (info["driver"], addr)


# --- LCD panel presets -------------------------------------------

# Picking the right driver + offsets + RGB/BGR/invert combo for a
# random Aliexpress/Amazon LCD by trial-and-error is painful. This
# table captures the well-known good combos for the most commonly
# sold panels. The user just sets ``display_preset = <key>`` in
# config.txt; the matching dict is overlaid onto the variant config.
#
# If your panel isn't listed, copy the closest entry and tune
# colstart/rowstart/bgr/invert by editing config.txt and watching
# the boot self-test colors.
DISPLAY_PRESETS = {
    # === ST7735R (1.44" / 1.8" 128x160 / 0.96" 80x160) ============
    # Most Aliexpress "1.8 inch SPI TFT" listings ship one of these
    # three sub-variants; the printed 'tab' colour on the protective
    # film identifies it. Default to GreenTab — by far the most common.
    "st7735r_128x160_greentab": {
        "display_controller": "st7735r",
        "display_width": 128, "display_height": 160,
        "display_colstart": 2, "display_rowstart": 1,
        "display_bgr": False, "display_invert": False,
    },
    "st7735r_128x160_redtab": {
        "display_controller": "st7735r",
        "display_width": 128, "display_height": 160,
        "display_colstart": 0, "display_rowstart": 0,
        "display_bgr": False, "display_invert": False,
    },
    "st7735r_128x160_blacktab": {
        "display_controller": "st7735r",
        "display_width": 128, "display_height": 160,
        "display_colstart": 0, "display_rowstart": 0,
        "display_bgr": True, "display_invert": False,
    },
    # 1.44" square — same controller, smaller area, different offsets
    "st7735r_128x128": {
        "display_controller": "st7735r",
        "display_width": 128, "display_height": 128,
        "display_colstart": 2, "display_rowstart": 3,
        "display_bgr": False, "display_invert": False,
    },
    # 0.96" wide — used on Pi Zero, ESP32 dev boards, etc.
    "st7735r_80x160": {
        "display_controller": "st7735r",
        "display_width": 80, "display_height": 160,
        "display_colstart": 26, "display_rowstart": 1,
        "display_bgr": True, "display_invert": True,
    },

    # === ST7789 (1.3" / 1.5" / 1.8" / 2.0" / 2.4" IPS) ===========
    # Many "1.8 inch" listings shipped after ~2023 are actually
    # ST7789 panels — same connector, different controller. If a
    # solid-white screen survives the ST7735R presets, try these.
    "st7789_240x240": {
        "display_controller": "st7789",
        "display_width": 240, "display_height": 240,
        "display_colstart": 0, "display_rowstart": 0,
        "display_bgr": False, "display_invert": False,
    },
    "st7789_240x320": {
        "display_controller": "st7789",
        "display_width": 240, "display_height": 320,
        "display_colstart": 0, "display_rowstart": 0,
        "display_bgr": False, "display_invert": False,
    },
    # 1.14" wide — common Pico Display variant
    "st7789_135x240": {
        "display_controller": "st7789",
        "display_width": 135, "display_height": 240,
        "display_colstart": 53, "display_rowstart": 40,
        "display_bgr": False, "display_invert": False,
    },

    # === ILI9341 (2.2" / 2.4" / 2.8" / 3.2" 240x320) =============
    "ili9341_240x320": {
        "display_controller": "ili9341",
        "display_width": 240, "display_height": 320,
        "display_colstart": 0, "display_rowstart": 0,
        "display_bgr": False, "display_invert": False,
    },

    # === GC9A01 (1.28" round 240x240) ============================
    "gc9a01_240x240_round": {
        "display_controller": "gc9a01",
        "display_width": 240, "display_height": 240,
        "display_colstart": 0, "display_rowstart": 0,
        "display_bgr": False, "display_invert": False,
    },

    # === SSD1306 (monochrome OLED, I2C) ==========================
    # 1" / 0.96" / 1.3" panels — by far the most common cheap I2C
    # OLED. Uses GP4/GP5 (I2C0) instead of the SPI bus. Controller
    # is auto-handled — no offsets/bgr/invert needed. The scene is
    # rendered in monochrome.
    "ssd1306_128x64_i2c": {
        "display_controller": "ssd1306",
        "display_width": 128, "display_height": 64,
    },
    "ssd1306_128x32_i2c": {
        "display_controller": "ssd1306",
        "display_width": 128, "display_height": 32,
    },

    # Explicit no-op — keep the variant defaults / individual fields.
    "none": {},
}


# --- User config overlay -----------------------------------------

# Whitelist: only these keys may be overridden by config.txt. Pin
# assignments are intentionally NOT user-tunable — wrong pins can
# brick the device.
_USER_OVERRIDABLE = (
    "puff_on_kpa", "puff_off_kpa",
    "sip_on_kpa", "sip_off_kpa",
    "double_puff_window_s", "double_sip_window_s",
    "hold_to_repeat_s",
    "repeat_min_hz", "repeat_max_hz", "repeat_full_scale_kpa",
    "encoder_phase_s", "encoder_button_press_s",
    "xac_pulse_s", "xac_double_gap_s",
    "mode", "verbose",
    "baseline_calibrate_s", "poll_period_s",
    "pressure_oversample",
    "display_enabled", "display_update_hz", "display_rotation",
    "display_preset", "display_controller",
    "display_colstart", "display_rowstart",
    "display_bgr", "display_invert",
    "display_test_pattern", "display_baudrate",
    "display_width", "display_height",
    "display_i2c_address", "display_i2c_frequency",
    "display_lps_full_scale_kpa",
    # Pin overrides for the I2C bus only — whitelisted because
    # different prototype boards wire the OLED to different pin
    # pairs. (Other pin assignments stay locked to avoid bricks.)
    "display_i2c_sda_pin", "display_i2c_scl_pin",
    # English-readable display selector and non-display I2C slots.
    "display",
    "i2c_pressure",
    "i2c_imu_1", "i2c_imu_2", "i2c_imu_3", "i2c_imu_4",
    # Pointing tunables for IMU-as-mouse builds.
    "imu_pointing_gain", "imu_pointing_deadband_dps",
    "imu_pointing_alpha", "imu_pointing_accel_expo",
    "imu_pointing_max_per_tick", "imu_pointing_stillness_recenter_s",
    "imu_yaw_axis", "imu_pitch_axis",
    # Heartbeat rate of the live serial-stream line.
    "heartbeat_period_s",
    # Output mode: "encoder" (default, drives wired encoder + buttons)
    # or "mouse" (drives USB HID mouse).
    "output_mode",
    # Mouse-mode tunables.
    "mouse_motion_min_per_tick", "mouse_scroll_per_repeat",
    # Repeat-scroll multipliers: emit N CW/CCW clicks per puff_repeat /
    # sip_repeat event. Asymmetric defaults handy when one direction
    # of the breath is physically harder than the other.
    "puff_repeat_multiplier", "sip_repeat_multiplier",
    # Per-direction hold-to-repeat thresholds. Override the symmetric
    # hold_to_repeat_s for asymmetric breath profiles — typically the
    # sip side gets a longer tap window because sips ramp up slower
    # than puffs and tend to overshoot 0.4 s.
    "puff_hold_to_repeat_s", "sip_hold_to_repeat_s",
    # Adaptive release — release threshold scales with how deep the
    # current breath went past its on-threshold, so a deliberate tap
    # exits state quickly even when the user can't snap-release.
    "adaptive_release_enabled",
    "adaptive_release_fraction",
    "adaptive_release_min_gap_kpa",
    # When true (and LPS28 is on the bus), use LPS28's signed gauge
    # for the *sip* branch of the classifier — the MPX5010DP can't
    # measure below 0 kPa so it caps the sip signal at the sensor's
    # saturation floor.
    "sip_from_lps28",
    # Symmetric switch for the puff branch. With both true, classifier
    # inputs come exclusively from the LPS28.
    "puff_from_lps28",
    # Repeat-rate map: rate_hz = magnitude_kpa * repeat_rate_factor,
    # clamped to [repeat_min_hz, repeat_max_hz]. See breath_classifier
    # for the formula and the planned logarithmic alternative.
    "repeat_rate_factor", "repeat_rate_curve",
    # LPS28 auto-rezero: after N s of stable idle, snap the baseline
    # so the gauge reads zero again. 0 disables.
    "lps_auto_rezero_idle_s", "lps_auto_rezero_threshold_kpa",
    # Per-direction signal scaling — multiplies the gauge signal on
    # that side before the classifier sees it. Compensates for
    # asymmetric breath effort.
    "puff_signal_scale", "sip_signal_scale",
    # Drive mode for the encoder A/B/BTN/BTN2 lines:
    # "push_pull" (default) drives high and low actively;
    # "open_drain" sinks low, floats high (host pull-up required).
    "encoder_drive_mode",
)


def _coerce(value):
    """Convert a config.txt string value to bool/float/int/str.

    Integers with an explicit base prefix (0x/0o/0b) are accepted —
    handy for I2C addresses written as ``0x3C``.
    """
    s = value.strip()
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    try:
        if "." in s or "e" in low:
            return float(s)
        # base=0 lets Python pick base from a 0x/0o/0b prefix.
        return int(s, 0)
    except ValueError:
        return s


def _load_user_config(path="/config.txt"):
    """Parse a simple key=value config file. Lines starting with #
    or empty lines are ignored. Returns a dict — never raises; on
    any I/O error returns {} so the device falls back to defaults.
    """
    out = {}
    try:
        with open(path, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                if key in _USER_OVERRIDABLE:
                    # I2C slot values are parsed downstream as
                    # 'kind[@0xNN]' specs — keep them raw so we don't
                    # accidentally coerce '0x4A' to int(74).
                    if key in _I2C_SLOT_KEYS:
                        out[key] = val.strip()
                    else:
                        out[key] = _coerce(val)
    except OSError:
        # No config.txt present — defaults are fine.
        pass
    except Exception as e:
        print("Config: load error ({})".format(e))
    return out


def load_config(variant=None, user_path="/config.txt"):
    """Build the runtime config dict for the chosen variant.

    Returns a fresh dict — variant defaults overlaid with whitelisted
    user-config values. Caller is free to mutate.
    """
    name = variant or DEFAULT_VARIANT
    if name not in VARIANTS:
        print("Config: unknown variant '{}', using '{}'".format(
            name, DEFAULT_VARIANT))
        name = DEFAULT_VARIANT
    cfg = dict(VARIANTS[name])
    user = _load_user_config(user_path)

    # The English-readable ``display = ...`` key takes precedence
    # over the legacy ``display_preset = ...`` key — it's what new
    # config.txt files use. Both resolve to the same DISPLAY_PRESETS
    # entry; the alias is normalised (case + separators) before lookup.
    if "display" in user:
        normalized = _normalize_alias(user["display"])
        preset_key = DISPLAY_ALIASES.get(normalized)
        if preset_key is None:
            print("Display: unknown 'display = {}'. Known: {}".format(
                user["display"], ", ".join(sorted(DISPLAY_ALIASES.keys()))))
        elif preset_key == "none":
            cfg["display_enabled"] = False
            print("Display: disabled (display = none)")
        else:
            user.setdefault("display_preset", preset_key)
            cfg["display_enabled"] = True

    # Apply LCD preset BEFORE individual user overrides so a single
    # preset name in config.txt sets the controller + dimensions +
    # offsets in one stroke, but the user can still override any
    # specific field below by listing it explicitly.
    preset_name = user.get("display_preset")
    if preset_name and str(preset_name).lower() != "none":
        key = str(preset_name).lower()
        preset = DISPLAY_PRESETS.get(key)
        if preset:
            cfg.update(preset)
            print("Display: preset '{}' applied".format(key))
        else:
            available = ", ".join(sorted(DISPLAY_PRESETS.keys()))
            print("Display: unknown preset '{}'. Available: {}".format(
                preset_name, available))

    if user:
        cfg.update(user)
        print("Config: {} user override(s) applied".format(len(user)))
    cfg["_variant"] = name
    return cfg
