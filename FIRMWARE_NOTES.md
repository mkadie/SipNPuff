# SipNPuff Firmware Notes

**Date of last update:** 2026-05-18
**Source tree:** `~/claude/coder/SipAndPuff/source/`
**Verified hardware:** RP2350 Pico 2 (UID `977F4E5A5C8CEE36`),
RP2040 Pico (UID `E4624881D3163931`). Both run CircuitPython 10.2.0.

This document captures the firmware state after the bring-up work
done in May 2026 — pressure-sensor fusion, IMU pointing, adaptive
threshold tuning, the 4-cell event-indicator HUD, the direct-kPa
repeat-rate map, LPS28 baseline auto-rezero, per-direction signal
scaling, and a configurable encoder drive mode.

---

## 1. Hardware variants the firmware understands

Only one variant key today: **`pico2_mpx5010dp`** (defined in
`hardware_config.VARIANTS`). The name is historical — it works on
both Pico (RP2040) and Pico 2 (RP2350) boards. Pin map:

| Function                | Pin       | Notes                             |
|------------------------|-----------|-----------------------------------|
| MPX5010DP ADC          | `GP26`    | analog differential, 0-10 kPa **unidirectional** |
| Encoder A / B / btn    | `GP18` / `GP19` / `GP20` | quadrature + shaft pushbutton |
| Encoder button 2       | `GP21`    | short-sip → momentary closure     |
| XAC opto puff / sip    | `GP1` / `GP0` | dry-contact pulse outputs    |
| I²C SDA / SCL          | `GP4` / `GP5` | J1 connector                  |
| Display SPI            | `GP10–GP16` | J2; ST7735R or other LCDs    |

**I²C peripherals on J1** (auto-detected on boot):

- **SSD1306 OLED** at `0x3C` — monochrome, 128×64.
- **LPS28DFW** at `0x5C` — absolute pressure, 260–1260 hPa,
  ±~60 kPa from atmospheric. Bidirectional. **This is the sensor
  the classifier reads from by default.**
- **BNO08x IMU** at `0x4A` or `0x4B` — for head-tracking mouse mode.
- (Future: BNO055 at `0x28`/`0x29` — driver included, not used here.)

---

## 2. Pressure sensing — why we don't use the MPX for sip

The on-board MPX5010DP is a **0–10 kPa unidirectional** sensor. Below
0 kPa its output voltage saturates near its offset, which decodes
to roughly **−0.3 to −0.4 kPa apparent pressure regardless of how
hard the user sips**. Documented at length in
`~/.claude/projects/.../memory/project_mpx5010dp_sip_limit.md`.

**Current solution:** the LPS28DFW is plumbed to the mouthpiece, and
the classifier reads both branches from it:

```
puff_from_lps28 = true
sip_from_lps28  = true
```

Internally, `sip_puff_device._run_normal` builds a fused signal:

```python
classifier_p = max(puff_branch, 0) + min(sip_branch, 0)
```

…where each *branch* independently picks MPX or LPS28 based on the
two flags. With both true, `classifier_p == lps_gauge`. With only
`sip_from_lps28 = true`, MPX drives puff and LPS28 drives sip
(historical "fusion" mode).

The MPX is still read every loop and shown on the display so the
operator can spot a sensor failure, but it doesn't feed the event
classifier in the current configuration.

### Per-direction signal scaling

Empirically puff takes ≈ 2× the lung effort of sip on this plumbing,
so the firmware applies a per-direction scale **before** the
classifier sees the value:

```
classifier_p = max(puff_branch, 0) * puff_signal_scale
             + min(sip_branch,  0) * sip_signal_scale
```

Defaults: `puff_signal_scale = 2.0`, `sip_signal_scale = 1.0`. The
display threshold-tick on the puff bargraph is moved to
`puff_on_kpa / puff_signal_scale` so the visual tick matches where
the firmware actually triggers.

A planned **user-calibration mode** would derive these scales from
a guided "do your hardest puff / hardest sip" sequence — see the
memory `project_signal_scale_calibration.md`.

### LPS28 baseline auto-rezero

The LPS28 baseline captured at boot can drift over minutes — room
pressure, thermal settling, slow mouthpiece leaks. The firmware now
watches for a stable-idle interval and re-snaps the baseline when:

- `state == "idle"` continuously for `lps_auto_rezero_idle_s` (default 30 s)
- LPS gauge spread (max − min) over that window is < 100 Pa
- Mean drift exceeds `lps_auto_rezero_threshold_kpa` (default 0.5 kPa)

When all three hold, `LPS28Sensor.recenter_now()` is invoked and a
line like `LPS28: auto-rezero (idle 30.0s, drift -1.640kPa,
spread 0.016kPa)` is printed. Setting `lps_auto_rezero_idle_s = 0`
disables the feature. The `recenter_now()` method is also callable
from the REPL for manual triggering.

---

## 3. Breath-event state machine (`breath_classifier.py`)

States: `IDLE → PUFF_ON / SIP_ON → PUFF_PEND / SIP_PEND → IDLE`.

Hysteresis is **static** (`puff_off_kpa` / `sip_off_kpa`) since we
moved to the LPS28. The adaptive-release scheme is wired in for
reference but disabled by default:

```
adaptive_release_enabled = false
```

It fired false releases when a held breath's noise dipped below
peak − min_gap; the static hysteresis is robust at the ±0.7 kPa
release threshold against ±0.02 kPa noise.

### Event semantics

| Event           | Trigger                                                    | Encoder mode               | Mouse mode      |
|-----------------|------------------------------------------------------------|---------------------------|-----------------|
| `puff`          | Quick puff, released within `puff_hold_to_repeat_s`        | `enc.press()` (GP20)      | left click      |
| `sip`           | Quick sip, released within `sip_hold_to_repeat_s`          | `enc.press2()` (GP21)     | right click     |
| `puff_repeat`   | Held puff past hold-window, fires at pressure-scaled rate  | one CW click per tick     | scroll up tick  |
| `sip_repeat`    | Held sip, same idea                                        | one CCW click per tick    | scroll down tick|
| `double_puff`   | Two puffs within `double_puff_window_s`                    | CW + double XAC pulse     | middle click    |
| `double_sip`    | Two sips within `double_sip_window_s`                      | double XAC sip pulse only | (no-op)         |

XAC opto pulses fire in encoder mode alongside every CW/CCW
rotation tick as well as the short puff/sip presses — so a wired
XAC consumer sees the same activity as the encoder consumer.

### Post-scroll release-suppression

When the user releases after a sustained scroll, the classifier
**suppresses** the `puff`/`sip` event so they don't get a spurious
"select" at the end of every scroll. Tracked via `_repeat_emitted`
in the state machine: True after any `*_repeat` fires, reset on
the next state entry.

### Per-direction tap window

`puff_hold_to_repeat_s` and `sip_hold_to_repeat_s` are independent.
Both default to **0.5 s** since the LPS28 gives symmetric clean
readings. Raise one if accidental scrolls happen during deliberate
taps; lower for earlier scroll trigger.

---

## 4. Repeat-rate map — 1 : 1 kPa → Hz

Rewritten on 2026-05-17. Per-tick rate is now:

```
rate_hz = clamp(magnitude_kpa * repeat_rate_factor,
                repeat_min_hz, repeat_max_hz)
```

…with `magnitude_kpa` clamped above by `repeat_full_scale_kpa`.

Defaults give a clean 1 : 1 mapping:

- 1 kPa held breath → 1 Hz
- 5 kPa → 5 Hz
- 10 kPa → 10 Hz
- ≥10 kPa → 10 Hz (clamped)

Bump `repeat_rate_factor` above 1 for faster scrolling per kPa of
effort. A **logarithmic** option is planned (`repeat_rate_curve`)
but not yet implemented — see the inline TODO in
`breath_classifier._tick_period` and the
`project_log_repeat_curve.md` memory.

---

## 5. Display HUD layout

LCD path (color, via `displayio` + `adafruit_st7735r` etc.):

```
+-------------------------------------------------------+
|  T-Rex Sip-N-Puff               state: idle           |
|                                                       |
|  MPX P [█████------------]  3.42                      |
|  MPX S [█----------------]  0.00                      |
|  LPS P [██████-----------]  4.10                      |
|  LPS S [█----------------]  0.00                      |
|                                                       |
|    UP    DN    SIP   PUF                              |
|   [▓▓]  [▓▓]  [▓▓]  [▓▓]                              |
+-------------------------------------------------------+
```

Mono path (SSD1306): same four rows of MPX P / MPX S / LPS P / LPS S
without the event-box row.

### Fill bars: vectorio.Rectangle, NOT display_shapes.Rect

Important gotcha: `adafruit_display_shapes.Rect` in current bundle
releases has a **read-only** `.width`. Trying to mutate it silently
fails and the bars stay frozen at 1 px. Fix landed in
`_build_color_scene._build_row`: the *outline* is still a `Rect`,
but the *fill* is a `vectorio.Rectangle` whose `.width` is mutable.

### Event-indicator boxes

The four bottom boxes are driven by `display.flash(name)` calls from
the dispatcher in `sip_puff_device.py`. Visibility rules:

| Box        | Trigger event              | Visibility                                 |
|------------|----------------------------|--------------------------------------------|
| `puff_click` | `puff`, `double_puff`    | Solid for `_box_click_on_s` (1 s) after the event. |
| `sip_click`  | `sip`, `double_sip`      | Same.                                      |
| `up`         | `puff_repeat`            | **Toggles** state per event. Forced off after `_box_stream_off_s` (0.5 s) of silence. |
| `down`       | `sip_repeat`             | Same toggle behavior.                      |

The toggle gives **≈50 % off-time naturally** at any rate the
display refresh can keep up with. At extremely high repeat rates
(>~10 Hz with a 10 Hz refresh), the toggle can blur — that's a
known limit, called out in the inline comment.

### Hardware-specific display overrides

The ST7735R 1.8" panel on the RP2040 prototype needs three extra
lines in its `/CIRCUITPY/config.txt`:

```
display_rotation = 90        # 180° from variant default of 270
display_width    = 160       # adafruit_st7735r returns native portrait dims
display_height   = 128       # — force the scene math to the rotated landscape
display_lps_full_scale_kpa = 10.0   # was 0.1, way too tight for real plumbing
```

These are **per-device** and are appended to `config.txt` at deploy
time on that device only. The source `config.txt` defaults to
`display = none` so a fresh CIRCUITPY drive doesn't try to talk to
hardware that isn't there.

---

## 5b. Encoder output drive mode

Configurable via `encoder_drive_mode`:

| Value              | High state | Low state | Notes |
|--------------------|------------|-----------|-------|
| `push_pull` (default) | Actively driven to 3.3 V | Actively driven to 0 V | Stiff output; fights any host pull-up. Works against any host. |
| `simulated_pullup` | Internal pull-up (~50 kΩ to 3.3 V), high-Z otherwise | Actively driven to 0 V | Emulates a real mechanical encoder switch — line idles high via the soft pull-up, snaps low only while pressed. |
| `open_drain`       | High-Z, no internal pull | Actively driven to 0 V | Host must supply its own pull-up. Safer interop with a 5 V host. |

Applies to all four encoder output lines (A, B, BTN, BTN2). The
`simulated_pullup` and `open_drain` paths don't rely on
CircuitPython's `DriveMode.OPEN_DRAIN` — they manage high-Z by
flipping `direction` between `OUTPUT` (low) and `INPUT` (high-Z),
because the documented `DriveMode.OPEN_DRAIN` on RP2040 has been
observed leaving the line in an undefined state for the "low" half
of the cycle on this CP build. See the `_OpenDrainOutput` class in
`encoder_emulator.py`.

Boot log prints the active mode:

```
Encoder: A=GP18 B=GP19 BTN=GP20 (phase=0.0020s, drive=push_pull, protocol=pulse_encoder)
```

## 5c. Encoder click protocol

Configurable via `encoder_protocol`:

| Value              | CW click action | CCW click action |
|--------------------|-----------------|------------------|
| `pulse_encoder` (default) | Pulses **A only** low for `encoder_button_press_s` (50 ms) | Pulses **B only** low for the same window |
| `5_phase_encoder` | Full gray-code quadrature sequence on A+B (5 phases × `encoder_phase_s`) | Mirror sequence |

`pulse_encoder` is the default because the **Xbox Adaptive
Controller and similar dry-contact hosts read each wire as an
independent momentary switch** — they don't decode rotary-encoder
quadrature. Each click becomes one button press on the destination
wire. For hosts that *do* decode quadrature (the T-Rex Talker's
encoder header, generic encoder breakouts), switch to
`5_phase_encoder`.

BTN and BTN2 are always pulsed regardless of protocol.

### Folding BTN2 onto BTN

For hosts with only **one** "select" input, set
`map_both_clicks_to_encoder_button = true`. Then `press2()` (short
sip) drives BTN (GP20) instead of BTN2 (GP21) — both short-puff and
short-sip register as the same press. Default `false`.

---

## 6. IMU pointing (mouse-mode only)

`imu_bno08x.py` (and parallel `imu_bno055.py`) drive an optional
9-DoF sensor. In mouse mode the gyro produces relative
`(dx, dy)` deltas, and the quaternion provides absolute yaw/pitch.

Tuning lives under the `imu_pointing_*` keys in `config.txt`:

- `imu_pointing_gain` — overall scale (default 400)
- `imu_pointing_alpha` — IIR LP on the rate stream (0.4)
- `imu_pointing_accel_expo` — power-curve exponent (1.0 = linear)
- `imu_pointing_max_per_tick` — clamp (60, ≤ HID int8 range)
- `imu_yaw_axis` / `imu_pitch_axis` — which gyro axis is which,
  with optional `+`/`-` sign prefix (e.g. `-z`)
- `imu_pointing_stillness_recenter_s` — auto re-zero after idle

The IMU isn't connected on either current bench device; the lines
in the heartbeat read `imu1=ABSENT …` and the firmware doesn't
fire mouse motion.

---

## 7. Heartbeat line on USB-CDC

Column-aligned, default cadence 2 s. Width ≈ 230 chars — needs a
wide terminal. Fields, in order:

```
t=NNNNN.NN | mpx=±N.NNN abs=±N.NNN | lps=NNN.NNN g=±N.NNNN
| peak(puf=±NN.NN,sip=±NN.NN)  ← max/min classifier input
                                 since the previous heartbeat
| imu1=… | rate(±NNN,±NNN) abs(±NNN.NN,±NNN.NN) | state=NAME
```

Set `heartbeat_period_s = 0.2` for benchtop tuning, `10–30` for
long monitors.

---

## 8. Config-key reference (selected)

Whitelist lives in `hardware_config._USER_OVERRIDABLE`. New keys
added during this work, grouped:

### Mode + I/O
- `output_mode = encoder | mouse`
- `mouse_motion_min_per_tick`, `mouse_scroll_per_repeat`

### Sensor source
- `i2c_pressure = lps28`
- `i2c_imu_1..4 = bno085 | bno086 | bno080 | bno055 | none[@0xNN]`
- `puff_from_lps28`, `sip_from_lps28` — fusion switches
- `puff_signal_scale`, `sip_signal_scale` — per-direction effort scale
- `lps_auto_rezero_idle_s` (default 30), `lps_auto_rezero_threshold_kpa` (0.5) — LPS baseline self-correction

### Display
- `display = ssd1306 oled 128x64 | st7735r color lcd 128x160 greentab | … | none`
- `display_lps_full_scale_kpa` — bar full-scale for LPS row

### Breath thresholds + timing
- `puff_on_kpa`, `puff_off_kpa`, `sip_on_kpa`, `sip_off_kpa`
- `puff_hold_to_repeat_s`, `sip_hold_to_repeat_s` (per-direction)
- `puff_repeat_multiplier`, `sip_repeat_multiplier`
- `adaptive_release_enabled`, `adaptive_release_fraction`,
  `adaptive_release_min_gap_kpa`

### Repeat-rate map (new)
- `repeat_min_hz` (1.0), `repeat_max_hz` (10.0)
- `repeat_full_scale_kpa` (10.0)
- `repeat_rate_factor` (1.0)
- `repeat_rate_curve` (`linear` / future `logarithmic`)

### Encoder outputs
- `encoder_drive_mode = push_pull | simulated_pullup | open_drain` (default `push_pull`)
- `encoder_protocol = pulse_encoder | 5_phase_encoder` (default `pulse_encoder`)
- `map_both_clicks_to_encoder_button = true | false` (default `false`)

### Pointing (mouse mode)
- `imu_pointing_gain`, `imu_pointing_alpha`,
  `imu_pointing_accel_expo`, `imu_pointing_max_per_tick`,
  `imu_pointing_stillness_recenter_s`,
  `imu_yaw_axis`, `imu_pitch_axis`

---

## 9. Known limits / next steps

- **Logarithmic repeat-rate curve** — config stub exists; formula
  sketched in `_tick_period`; not implemented. See
  `project_log_repeat_curve.md` memory.
- **IMU plumbing** — neither bench unit has a BNO08x wired in
  right now. Mouse mode is functional in code but un-exercised on
  the bench since 2026-05-10.
- **MPX5010DP retirement** — once the LPS28 plumbing is the
  permanent solution, the MPX could be dropped entirely or
  swapped for a **bidirectional MPXV7007DP** (±7 kPa, pin-compatible).
- **Box-row at very high event rates** — the toggle scheme on
  UP/DN can blur at >10 Hz events. Acceptable per user feedback;
  could enforce a min-cycle if needed.
- **Single hardware variant** — the variant key only branches on
  pin map / sensor defaults right now. If we add the MPXV7007DP
  build it'll become a second `VARIANTS` entry.

---

## 10. Deploy workflow

```bash
DEST=/media/trex/CIRCUITPY      # or CIRCUITPY1 — whichever the device mounts as
SRC=~/claude/coder/SipAndPuff/source
BUNDLE=~/adafruit-circuitpython-bundle-10.x-mpy-20260317

# Libraries (only if missing)
cp -r $BUNDLE/lib/adafruit_hid    $DEST/lib/
cp -r $BUNDLE/lib/adafruit_bno08x $DEST/lib/
cp    $BUNDLE/lib/adafruit_bno055.mpy $DEST/lib/
# (plus adafruit_lps28.mpy, adafruit_displayio_ssd1306.mpy, etc.
# depending on which display + sensors are on the unit)

# Modules + config + code.py last so the reload sees a complete tree
for f in hardware_config.py pressure_sensor.py breath_classifier.py \
         encoder_emulator.py xac_output.py display_manager.py \
         lps28_sensor.py imu_bno08x.py imu_bno055.py mouse_output.py \
         mini_st7735.py diagnostic.py sip_puff_device.py; do
    cp "$SRC/$f" "$DEST/$f"
done
cp "$SRC/config.txt" "$DEST/config.txt"

# Per-device overrides (LCD vs OLED, rotation, etc.) — sed in-place
# at deploy time. See section 5 above.

cp "$SRC/code.py" "$DEST/code.py"
sync
```

After deploy, soft-reboot via REPL (`\x02\x03\x04`) and watch
`/dev/ttyACM*` for the boot banner. The `Config: NN user override(s)
applied` line tells you how many config keys took effect — if it's
lower than expected, a key is misspelled or not whitelisted.
