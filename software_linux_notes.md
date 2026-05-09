# T-Rex Sip-N-Puff — Linux Software Development Notes

## Project Overview

CircuitPython firmware for the T-Rex Sip-N-Puff HID: a Raspberry Pi Pico-based sip and puff human interface device targeting the Xbox Adaptive Controller (XAC). Core function is reading a differential pressure sensor, classifying breath events (sip/puff/double-puff), and driving isolated dry-contact outputs to the XAC via optocouplers. Optional I2C display for status/feedback.

---

## Hardware Pin Map

| GPIO | Board Const | Function | Notes |
|------|-------------|----------|-------|
| GP4  | `board.GP4`  | I2C SDA | Optional display |
| GP5  | `board.GP5`  | I2C SCL | Optional display |
| GP16 | `board.GP16` | XAC_PUFF output | PC817 opto, drives 3.5mm jack tip |
| GP17 | `board.GP17` | XAC_SEL output | PC817 opto, drives second 3.5mm jack |
| GP18 | `board.GP18` | ENC_A | Rotary encoder phase A |
| GP19 | `board.GP19` | ENC_B | Rotary encoder phase B |
| GP20 | `board.GP20` | ENC_BTN | Encoder push button |
| GP26 | `board.GP26` | ADC0 — pressure in | MPX5010DP via 10kΩ/20kΩ voltage divider |

### Voltage Divider (pressure sensor protection)
MPX5010DP Vout max = 4.7V; Pico ADC max = 3.3V.
- Sensor VOUT → 10kΩ → GP26 → 20kΩ → GND
- Scales 4.7V → ~3.13V. Safe for RP2040 ADC.

### XAC Optocoupler Wiring (PC817)
- GP16/GP17 → 220Ω → PC817 pin 1 (Anode)
- PC817 pin 2 (Cathode) → GND
- PC817 pin 4 (Collector) → 3.5mm Tip
- PC817 pin 3 (Emitter) → 3.5mm Sleeve
- XAC sees a dry-contact switch closure — no voltage from Pico side crosses to XAC side.

---

## Toolchain Setup (one-time, on the Linux machine)

```bash
# Flash tool and library manager
sudo pip3 install mpremote circup

# Serial port access — add your user to dialout, then log out/in
sudo usermod -a -G dialout $USER

# Verify
mpremote --version
circup --version

# Check device appears when Pico is plugged in
ls -la /dev/ttyACM*
# Expected: crw-rw---- 1 root dialout ... /dev/ttyACM0
```

### Flashing CircuitPython Firmware (first time only)
1. Hold BOOTSEL on Pico while plugging in USB → mounts as `RPI-RP2`
2. Download latest CircuitPython UF2 for Raspberry Pi Pico from https://circuitpython.org/board/raspberry_pi_pico/
3. Copy UF2 to the RPI-RP2 drive — Pico reboots, mounts as `CIRCUITPY`
4. **Target CircuitPython 9.x** — 8.x has known ADC stability regressions on RP2040

---

## Core Libraries Needed

Install via `circup` once CircuitPython is on the device:

```bash
circup install adafruit_hid
circup install adafruit_debouncer
circup install adafruit_ssd1306        # if using OLED display
circup install adafruit_displayio_ssd1306  # alternative OLED driver
circup install adafruit_st7789         # if using TFT display
circup install adafruit_display_text
```

> **Library compatibility warning:** Adafruit display libraries have had breaking API changes across CircuitPython versions. If a display library fails to import or throws AttributeError, check the library version with `circup list` and try pinning to an older version. The `adafruit_ssd1306` vs `adafruit_displayio_ssd1306` split is a known source of confusion — which one works depends on your CircuitPython version.

---

## Development Workflow

### Single board — flash and monitor
```bash
# Copy code.py and open serial REPL immediately
mpremote connect /dev/ttyACM0 fs cp code.py :code.py + repl

# Copy a whole lib folder
mpremote connect /dev/ttyACM0 fs cp -r lib :lib

# Just monitor serial (Ctrl+] to exit)
mpremote connect /dev/ttyACM0 repl

# Soft reset without reflashing
# In REPL: Ctrl+D
```

### Two boards simultaneously
Second Pico appears as `/dev/ttyACM1`. Both can be monitored at once with a simple Python script:

```python
import serial, threading, datetime

def monitor(port, label):
    with serial.Serial(port, 115200, timeout=1) as s:
        while True:
            line = s.readline().decode('utf-8', errors='replace').strip()
            if line:
                ts = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{ts}] {label}: {line}")

t0 = threading.Thread(target=monitor, args=('/dev/ttyACM0', 'BOARD-A'), daemon=True)
t1 = threading.Thread(target=monitor, args=('/dev/ttyACM1', 'BOARD-B'), daemon=True)
t0.start(); t1.start()
input("Monitoring both boards. Enter to stop.\n")
```

Save as `monitor_two.py` and run with `python3 monitor_two.py`.

### Iterating on bad/undocumented libraries
When a library behaves unexpectedly:
```bash
# Drop into live REPL and probe the object
mpremote connect /dev/ttyACM0 repl
# Then:
import adafruit_somethingbad
dir(adafruit_somethingbad)           # see what's actually exported
help(adafruit_somethingbad.Thing)    # docstring if present
```

---

## Starting Point: code.py

Minimal skeleton that initializes all hardware and prints sensor readings to serial. Start here and build up:

```python
import board
import analogio
import digitalio
import time

# --- Hardware Init ---

pressure_sensor = analogio.AnalogIn(board.GP26)

enc_a   = digitalio.DigitalInOut(board.GP18)
enc_b   = digitalio.DigitalInOut(board.GP19)
enc_btn = digitalio.DigitalInOut(board.GP20)
enc_a.direction   = digitalio.Direction.INPUT
enc_b.direction   = digitalio.Direction.INPUT
enc_btn.direction = digitalio.Direction.INPUT
enc_a.pull   = digitalio.Pull.UP
enc_b.pull   = digitalio.Pull.UP
enc_btn.pull = digitalio.Pull.UP

xac_puff = digitalio.DigitalInOut(board.GP16)
xac_sel  = digitalio.DigitalInOut(board.GP17)
xac_puff.direction = digitalio.Direction.OUTPUT
xac_sel.direction  = digitalio.Direction.OUTPUT
xac_puff.value = False
xac_sel.value  = False

# --- ADC Helpers ---

def raw_to_voltage(raw):
    """16-bit ADC raw → actual voltage at GP26 pin."""
    return (raw / 65535) * 3.3

def voltage_to_pressure_kpa(v):
    """
    Undo the voltage divider (10k/20k), recover sensor output,
    then apply MPX5010DP transfer function.
    Sensor Vout = v * (10k+20k)/20k = v * 1.5
    MPX5010DP: Vout = VS * (0.09 * P_kPa + 0.04), VS=5V
    Solving for P: P = (Vout/VS - 0.04) / 0.09
    """
    sensor_vout = v * 1.5        # undo divider
    p_kpa = (sensor_vout / 5.0 - 0.04) / 0.09
    return max(0.0, p_kpa)

# --- Main Loop ---

print("T-Rex Sip-N-Puff starting up")

while True:
    raw = pressure_sensor.value
    v   = raw_to_voltage(raw)
    kpa = voltage_to_pressure_kpa(v)

    print(f"raw={raw:5d}  v={v:.3f}V  p={kpa:.3f}kPa  "
          f"encA={enc_a.value} encB={enc_b.value} btn={not enc_btn.value}")

    time.sleep(0.1)
```

> **Calibration note:** The pressure-to-kPa formula assumes VS=5V (from VBUS). If you're powering the sensor from a regulated 5V rail that dips under load, the reading will drift. Add a 0.1µF decoupling cap on the sensor's VS pin if you see noise.

---

## Known Issues / Watch Points

- **ADC noise on RP2040:** The internal ADC has a known noise floor issue. Averaging 8–16 samples per reading significantly improves stability. The `analogio` library doesn't do this for you.
- **CircuitPython vs MicroPython:** These are different. Most Adafruit libraries target CircuitPython. MicroPython uses `machine.ADC`, not `analogio`. Don't mix them.
- **CIRCUITPY drive not mounting:** If the drive doesn't appear, the Pico may be in a crash loop. Hold BOOTSEL while plugging in to force bootloader mode, then re-flash CircuitPython UF2.
- **`mpremote` device permissions:** If `mpremote` returns "permission denied", your user isn't in `dialout` yet, or you haven't logged out/in since adding it. Quick workaround: `sudo mpremote ...` until you log back in.
- **Two boards same USB hub:** udev assigns ACM numbers by enumeration order. If both boards are plugged in at the same time the assignment can swap between reboots. Use udev rules keyed to USB serial number for stable naming in production.

---

## Files in This Repo

| Path | Description |
|------|-------------|
| `T-Rex_Sip_N_Puff.md` | Full project spec, use cases, BOM |
| `T-Rex_Sip_N_Puff_Hardware_Defitions.md` | Pin table and sub-circuit wiring detail |
| `T-Rex_Sip_N_Puff_Schematic.pdf` | Visual schematic (A3 landscape) for manual CAD entry |
| `T-Rex_Sip_N_Puff.kicad_sch` | KiCad 7 schematic (self-contained, all symbols embedded) |
| `photos/` | First article prototype build photos |
| `3d/` | STEP model of prototype assembly |
| `software_linux_notes.md` | This file |
