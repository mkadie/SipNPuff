# Sip and Puff Rubber Chicken Edition - Schematics

> **Dual Sensor PCB Strategy:** Initial PCBs include footprints for both the LPS28DFWTR (SMD, I²C — default) and the MPX5010DP (through-hole, analog — alternative). Only one sensor is populated at a time. After real-world testing, separate PCB variants will be spun. Sections below document both wiring options clearly.

## Hardware Schematic Overview

```
                    SIP AND PUFF RUBBER CHICKEN EDITION — TOP-LEVEL OVERVIEW

          DEFAULT SENSOR                      ALTERNATIVE SENSOR
    ┌──────────────────────┐           ┌──────────────────────┐
    │   LPS28DFWTR (SMD)   │           │  MPX5010DP (TH)      │
    │   I²C digital        │           │  Analog output        │
    │   GPIO 4 (SDA)       │           │  GPIO 26 (ADC0)       │
    │   GPIO 5 (SCL)       │           │  (one or the other    │
    │   GPIO 6 (INT, opt.) │           │   is populated)       │
    └──────────┬───────────┘           └──────────┬────────────┘
               │  I²C / ADC                        │
               └──────────────┬────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │                    │
                    │   Pico W / RP2040  │
                    │   Microcontroller  │
                    │                    │
                    │  GPIO 0 → SIP_ENABLE (OUT) │  → PC817 opto → TRRS jack
                    │  GPIO 1 → PUF_ENABLE (OUT) │  → PC817 opto → TRRS jack
                    │  GPIO 2 → Status LED       │
                    │  GPIO 4 → I²C SDA          │  (LPS28DFWTR default)
                    │  GPIO 5 → I²C SCL          │  (LPS28DFWTR default)
                    │  GPIO 6 → INT_DRDY         │  (LPS28DFWTR optional)
                    │  GPIO 26 → ADC0            │  (MPX5010DP alternative)
                    │                    │
                    └─────────┬──────────┘
                              │
          ┌───────────────────┼──────────────┐
          │                   │              │
    ┌─────▼──────────┐  ┌─────▼───────────┐  ┌───▼────────────┐
    │ SIP_ENABLE out │  │ PUF_ENABLE out  │  │  Status LED    │
    │ → PC817 opto   │  │ → PC817 opto    │  │  GPIO 2        │
    │ → TRRS 3.5mm   │  │ → TRRS 3.5mm   │  └────────────────┘
    │   (XAC output) │  │   (XAC output)  │
    └────────────────┘  └─────────────────┘

    ⚠ NOTE: Sip/puff is DETECTED by the pressure sensor (LPS28DFWTR
    via I²C or MPX5010DP via ADC). GPIO 0/1 are OUTPUTS — they
    signal a detected sip/puff event to an external XAC or AT
    device via PC817 optocoupler-isolated TRRS 3.5mm jacks.
```

## DEFAULT Sensor Schematic — LPS28DFWTR (SMD, I²C)

```
    LPS28DFWTR — CCLGA-7L PINOUT (bottom view)
    ┌──────────────────────────────────────────────────┐
    │  Pin 1  SDA      → Pico W GPIO 4  (I2C0 SDA)    │
    │  Pin 2  SA0      → GND           (addr = 0x5C)  │
    │                    or VDD        (addr = 0x5D)  │
    │  Pin 3  SCL      → Pico W GPIO 5  (I2C0 SCL)    │
    │  Pin 4  INT_DRDY → Pico W GPIO 6  (optional IRQ) │
    │  Pin 5  GND      → GND                          │
    │  Pin 6  VDD      → 3.3V                         │
    │  Pin 7  PAD2LID  → GND  (or float)              │
    └──────────────────────────────────────────────────┘

    I²C PULL-UP RESISTORS (required):
    ┌────────────────────────────────────────────────────┐
    │  SDA (GPIO 4) ──┬── 10kΩ ── 3.3V                 │
    │  SCL (GPIO 5) ──┴── 10kΩ ── 3.3V                 │
    │                                                    │
    │  Note: Pico W internal pull-ups are weak (~50kΩ); │
    │  external 10kΩ resistors are required for        │
    │  reliable I²C at 400 kHz.                         │
    └────────────────────────────────────────────────────┘

    DECOUPLING CAPACITOR (required):
    ┌────────────────────────────────────────────────────┐
    │  100nF ceramic cap between VDD (pin 6) and GND    │
    │  placed as close to the sensor as possible        │
    └────────────────────────────────────────────────────┘

                    LPS28DFWTR I²C CONNECTION
                    ┌─────────────────────────────┐
                    │                             │
                    │   LPS28DFWTR (CCLGA-7L SMD) │
                    │   ┌─────────────────────┐   │
                    │   │                     │   │
                    │   │  VDD  ────── 3.3V   │   │
                    │   │  GND  ────── GND    │   │
                    │   │  SDA  ────── GPIO 4 │   │
                    │   │  SCL  ────── GPIO 5 │   │
                    │   │  SA0  ────── GND    │   │  (I²C addr 0x5C)
                    │   │  INT_DRDY ── GPIO 6 │   │  (optional)
                    │   │  PAD2LID ── GND     │   │
                    │   │                     │   │
                    │   └─────────────────────┘   │
                    │                             │
                    │   I²C Pull-ups:             │
                    │   GPIO 4 ──10kΩ── 3.3V    │
                    │   GPIO 5 ──10kΩ── 3.3V    │
                    │   Decoupling: 100nF VDD–GND │
                    │                             │
                    └─────────────────────────────┘

    KEY SPECS (from DS13317 Rev 1):
    • Pressure range:  260–1260 hPa (Mode 1) / 260–4060 hPa (Mode 2)
    • Noise:           0.32 Pa RMS (Mode 1 @ 25°C)
    • Resolution:      24-bit
    • ODR:             1–200 Hz (software selectable)
    • Supply:          1.7–3.6 V  →  3.3V nominal
    • Current:         1.7 µA typical (AVG=4, ODR=1 Hz)
    • Water-resistant: potting gel, rated 10 ATM
    • Factory calibrated — no user calibration required
    • I²C addresses:   0x5C (SA0=GND) or 0x5D (SA0=VDD)
```

## ALTERNATIVE Sensor Schematic — MPX5010DP (Through-Hole, Analog)

> **Note:** The MPX5010DP outputs an **analog voltage** (not I²C). It must connect to a Pico ADC pin (GPIO 26/27/28), not to the SDA/SCL I²C bus. Earlier documentation incorrectly described this as "Digital I²C" — that was an error and has been corrected.

```
    MPX5010DP CONNECTIONS (when populated instead of LPS28DFWTR):
    ┌──────────────────────────────────────────────────────┐
    │  Pin 1  (V+)   → 5V   (VBUS)                        │
    │  Pin 2  (V-)   → GND                                │
    │  Pin 3  (Vout) → R5 (10kΩ) → Pico W GPIO 26 (ADC0) │
    │  Pin 4  (not connected or GND per datasheet)        │
    │  Pin 5  (Vs)   → 5V   (VBUS)                        │
    │  Pin 6  (GND)  → GND                                │
    └──────────────────────────────────────────────────────┘

    ⚠ VOLTAGE DIVIDER REQUIRED: MPX5010DP is supplied from 5V.
    At 5V supply, Vout range is 0.2V–4.7V — exceeds the Pico W
    ADC maximum of 3.3V. R5 (10kΩ) is the top leg of a voltage
    divider on the Vout line to protect GPIO 26 (ADC0).
    A pull-down resistor to GND completes the divider to bring
    the maximum ADC input voltage to ≤ 3.3V.
    Divider target: Vout_max (4.7V) × R_bottom / (10k + R_bottom) ≤ 3.3V
    → R_bottom ≈ 20kΩ gives 4.7V × 20/30 = 3.13V ✓

    DECOUPLING:
    ┌────────────────────────────────────────────────────┐
    │  100nF + 10µF caps on supply pins                 │
    └────────────────────────────────────────────────────┘

                    MPX5010DP ANALOG CONNECTION
                    ┌─────────────────────────────┐
                    │                             │
                    │   MPX5010DP (Through-Hole)  │
                    │   ┌─────────────────────┐   │
                    │   │                     │   │
                    │   │  V+   ────── 5V (VBUS)          │   │
                    │   │  V-   ────── GND               │   │
                    │   │  Vout ── R5 (10kΩ) ── GPIO 26  │   │  (ADC0 — via divider)
                    │   │  Vs   ────── 5V (VBUS)          │   │
                    │   │  GND  ────── GND               │   │
                    │   │                     │   │
                    │   └─────────────────────┘   │
                    │                             │
                    │   Decoupling:               │
                    │   100nF + 10µF on V+ / GND  │
                    │   (NO I²C pull-ups needed)  │
                    │                             │
                    └─────────────────────────────┘

    KEY SPECS:
    • Pressure range:  0–10 kPa differential
    • Output:          Analog voltage (0.2V–4.7V @ 5V supply)
    • Accuracy:        ±1.5% FS
    • Supply:          5V (VBUS) — do not use 3.3V (degrades output range)
    • Package:         Through-hole SIP — hand-solderable
    • Interface:       ADC (not I²C)
    • ADC protection:  R5 (10kΩ) + ~20kΩ to GND voltage divider on Vout
                       → scales 4.7V max to ~3.1V safe for Pico W ADC
```

## Detailed Circuit Schematic

```
                           SIP AND PUFF SYSTEM
                          ┌─────────────────────────────┐
                          │                             │
                          │  PRESSURE SENSOR (choose 1) │
                          │                             │
                          │  DEFAULT: LPS28DFWTR (SMD)  │
                          │   VDD  ────── 3.3V          │
                          │   GND  ────── GND           │
                          │   SDA  ────── GPIO 4        │
                          │   SCL  ────── GPIO 5        │
                          │   SA0  ────── GND (0x5C)    │
                          │   INT_DRDY ── GPIO 6 (opt.) │
                          │                             │
                          │  ALT: MPX5010DP (TH analog) │
                          │   V+   ────── 5V (VBUS)     │
                          │   Vout ── R5 10kΩ ── GPIO 26│  (ADC, via divider)
                          │   GND  ────── GND           │
                          │                             │
                          └─────────────────────────────┘
                                    │
                                    │
                            ┌───────▼───────┐
                            │               │
                            │   RP2040      │
                            │   Microcontroller│
                            │               │
                            │   GPIO 0 ────┬─┤
                            │   GPIO 1 ────┬─┤
                            │   GPIO 2 ────┬─┤
                            │   GPIO 3 ────┬─┤
                            │   GPIO 4 ────┬─┤
                            │   GPIO 5 ────┬─┤
                            │   GPIO 6 ────┬─┤
                            │   GPIO 7 ────┬─┤
                            │   GPIO 8 ────┬─┤
                            │   GPIO 9 ────┬─┤
                            │   GPIO 10 ───┬─┤
                            │   GPIO 11 ───┬─┤
                            │   GPIO 12 ───┬─┤
                            │   GPIO 13 ───┬─┤
                            │   GPIO 14 ───┬─┤
                            │   GPIO 15 ───┬─┤
                            │   GPIO 16 ───┬─┤
                            │   GPIO 17 ───┬─┤
                            │   GPIO 18 ───┬─┤
                            │   GPIO 19 ───┬─┤
                            │   GPIO 20 ───┬─┤
                            │   GPIO 21 ───┬─┤
                            │   GPIO 22 ───┬─┤
                            │   GPIO 23 ───┬─┤
                            │   GPIO 24 ───┬─┤
                            │   GPIO 25 ───┬─┤
                            │   GPIO 26 ───┬─┤
                            │   GPIO 27 ───┬─┤
                            │   GPIO 28 ───┬─┤
                            │   GPIO 29 ───┬─┤
                            │   GPIO 30 ───┬─┤
                            │   GPIO 31 ───┬─┤
                            │               │
                            │   VBUS ──────┬─┤
                            │   VSYS ──────┬─┤
                            │   GND ───────┬─┤
                            │   VREGIN ────┬─┤
                            │               │
                            └───────────────┘
                                    │
                                    │
                            ┌───────▼───────┐
                            │               │
                            │   Power Supply│
                            │   (3.3V Reg)  │
                            │               │
                            │   VIN ────────┤
                            │   VOUT ───────┤
                            │   GND ────────┤
                            │               │
                            └───────────────┘
                                    │
                                    │
                            ┌───────▼───────┐
                            │               │
                            │   Rubber      │
                            │   Chicken     │
                            │   Sip         │
                            │   Interface   │
                            │   (Demonstr.) │
                            │               │
                            └───────────────┘
                                    │
                                    │
                            ┌───────▼───────┐
                            │               │
                            │   Rubber      │
                            │   Chicken     │
                            │   Puff        │
                            │   Interface   │
                            │   (Demonstr.) │
                            │               │
                            └───────────────┘
                                    │
                                    │
                            ┌───────▼───────┐
                            │               │
                            │   Rubber      │
                            │   Chicken     │
                            │   Status      │
                            │   Indicator   │
                            │   (Demonstr.) │
                            │               │
                            └───────────────┘
```

## Power Supply Circuit

```
                    POWER SUPPLY CIRCUIT
                    ┌─────────────────────────────┐
                    │                             │
                    │   VIN (5V)                  │
                    │   ┌─────────────────────┐   │
                    │   │                     │   │
                    │   │  3.3V REGULATOR     │   │
                    │   │  (LDO)              │   │
                    │   │                     │   │
                    │   │  VOUT ────┬─── 3.3V  │   │
                    │   │  GND ─────┴─── GND   │   │
                    │   │                     │   │
                    │   └─────────────────────┘   │
                    │                             │
                    │   VBUS ────┬─── 5V          │
                    │   VSYS ────┴─── 5V          │
                    │                             │
                    └─────────────────────────────┘
```

## Signal Processing Circuit

```
                    SIGNAL PROCESSING CIRCUIT
                    ┌──────────────────────────────────────┐
                    │                                      │
                    │  DEFAULT: LPS28DFWTR (I²C digital)  │
                    │   ┌──────────────────────────────┐   │
                    │   │  VDD ────────── 3.3V         │   │
                    │   │  GND ────────── GND          │   │
                    │   │  SDA ────────── GPIO 4       │   │
                    │   │  SCL ────────── GPIO 5       │   │
                    │   │  SA0 ────────── GND (0x5C)   │   │
                    │   │  INT_DRDY ────── GPIO 6 (opt)│   │
                    │   │  PAD2LID ─────── GND         │   │
                    │   └──────────────────────────────┘   │
                    │                                      │
                    │  I²C Pull-up Resistors (required):   │
                    │   GPIO 4 (SDA) ──10kΩ── 3.3V       │
                    │   GPIO 5 (SCL) ──10kΩ── 3.3V       │
                    │  Decoupling: 100nF on VDD–GND        │
                    │                                      │
                    │  ALTERNATIVE: MPX5010DP (analog ADC) │
                    │   ┌──────────────────────────────┐   │
                    │   │  V+   ────────── 5V (VBUS)   │   │
                    │   │  GND  ────────── GND         │   │
                    │   │  Vout ── R5 10kΩ ── GPIO 26  │   │  (divider req.)
                    │   │
                    │   │                  (ADC0)      │   │
                    │   └──────────────────────────────┘   │
                    │  Decoupling: 100nF + 10µF on V+–GND  │
                    │                                      │
                    └──────────────────────────────────────┘
```

## XAC / AT Output Circuit (GPIO 0 & 1)

> **Important:** GPIO 0 and GPIO 1 are **outputs**, not inputs. Sip/puff is detected by
> the pressure sensor. These GPIOs signal a detected event to an external XAC (Xbox
> Adaptive Controller) or AT device via PC817 optocouplers and TRRS 3.5mm jacks.

```
                    XAC OUTPUT CIRCUIT — SIP_ENABLE (GPIO 0) & PUF_ENABLE (GPIO 1)
                    ┌──────────────────────────────────────────────────┐
                    │                                                  │
                    │   SIP_ENABLE (GPIO 0)                            │
                    │   ┌───────────────────────────────────────────┐  │
                    │   │                                           │  │
                    │   │  GPIO 0 ─── R (current limit) ──┐        │  │
                    │   │                                  ▼        │  │
                    │   │                    PC817SC OPTO  │        │  │
                    │   │                    ┌──────────┐  │        │  │
                    │   │                    │ LED anode│◄─┘        │  │
                    │   │                    │ LED cath ├── GND     │  │
                    │   │                    │          │           │  │
                    │   │                    │ Collector├── SIP_TIP1│  │  → TRRS TIP
                    │   │                    │ Emitter  ├── GND_SIP │  │  → TRRS GND
                    │   │                    └──────────┘           │  │
                    │   │                                           │  │
                    │   └───────────────────────────────────────────┘  │
                    │                                                  │
                    │   PUF_ENABLE (GPIO 1) — identical circuit        │
                    │   → separate PC817SC → separate TRRS 3.5mm jack  │
                    │                                                  │
                    │   TRRS JACK PINOUT (TRRS_2SWITCH_PJ332A):        │
                    │     TIP   = switch signal (from opto collector)  │
                    │     RING1 = MICDET                               │
                    │     RING2 = switch signal                        │
                    │     SLEEVE = GND                                 │
                    │                                                  │
                    └──────────────────────────────────────────────────┘
```

## Status LED Circuit

```
                    STATUS LED CIRCUIT
                    ┌─────────────────────────────┐
                    │                             │
                    │   STATUS LED                │
                    │   ┌─────────────────────┐   │
                    │   │                     │   │
                    │   │  GPIO 2 ────┬─── 220Ω │   │
                    │   │  VCC ───────┴─── 3.3V │   │
                    │   │  GND ───────┴─── GND   │   │
                    │   │                     │   │
                    │   └─────────────────────┘   │
                    │                             │
                    │   LED COLOR: GREEN          │
                    │   (Optional: RED or BLUE)   │
                    │                             │
                    └─────────────────────────────┘
```

## Complete System Schematic

```
                    COMPLETE SYSTEM SCHEMATIC
                    ┌─────────────────────────────────────────────────────────────┐
                    │                                                             │
                    │                    POWER SUPPLY                             │
                    │                    ┌─────────────────────────────┐          │
                    │                    │                             │          │
                    │                    │   VIN (5V)                    │          │
                    │                    │   ┌─────────────────────┐     │          │
                    │                    │   │                     │     │          │
                    │                    │   │  3.3V REGULATOR     │     │          │
                    │                    │   │  (LDO)              │     │          │
                    │                    │   │                     │     │          │
                    │                    │   │  VOUT ────┬─── 3.3V   │     │          │
                    │                    │   │  GND ─────┴─── GND     │     │          │
                    │                    │   │                     │     │          │
                    │                    │   └─────────────────────┘     │          │
                    │                    │                             │          │
                    │                    │   VBUS ────┬─── 5V          │          │
                    │                    │   VSYS ────┴─── 5V          │          │
                    │                    │                             │          │
                    │                    └─────────────────────────────┘          │
                    │                                                             │
                    │                    MICROCONTROLLER                          │
                    │                    ┌─────────────────────────────┐          │
                    │                    │                             │          │
                    │                    │   RP2040                      │          │
                    │                    │   ┌─────────────────────┐     │          │
                    │                    │   │                     │     │          │
                    │                    │                    │   │  GPIO 0 ────┬─── SIP_ENABLE  │     │          │
                    │                    │   │  GPIO 1 ────┬─── PUF_ENABLE  │     │          │
                    │                    │   │  GPIO 2 ────┬─── LED         │     │          │
                    │                    │   │  GPIO 4 ────┬─── I²C SDA     │     │          │
                    │                    │   │  GPIO 5 ────┬─── I²C SCL     │     │          │
                    │                    │   │  GPIO 6 ────┬─── INT_DRDY(opt│     │          │
                    │                    │   │  GPIO 26 ───┬─── ADC0 (alt)  │     │          │
                    │                    │   │  VCC ───────┴─── 3.3V        │     │          │
                    │                    │   │  GND ───────┴─── GND         │     │          │
                    │                    │   │                     │     │          │
                    │                    │   └─────────────────────┘     │          │
                    │                    │                             │          │
                    │                    └─────────────────────────────┘          │
                    │                                                             │
                    │                    SENSOR (populate ONE option)              │
                    │                    ┌─────────────────────────────┐          │
                    │                    │                             │          │
                    │                    │  DEFAULT: LPS28DFWTR (SMD)    │          │
                    │                    │   ┌─────────────────────┐     │          │
                    │                    │   │  VDD ────── 3.3V    │     │          │
                    │                    │   │  GND ────── GND     │     │          │
                    │                    │   │  SDA ────── GPIO 4  │     │          │
                    │                    │   │  SCL ────── GPIO 5  │     │          │
                    │                    │   │  SA0 ────── GND(0x5C│     │          │
                    │                    │   │  INT ────── GPIO 6  │     │          │
                    │                    │   └─────────────────────┘     │          │
                    │                    │  Pull-ups: 10kΩ SDA/SCL     │          │
                    │                    │  Decoupling: 100nF VDD–GND   │          │
                    │                    │                             │          │
                    │                    │  ALTERNATIVE: MPX5010DP (TH)  │          │
                    │                    │   ┌─────────────────────┐     │          │
                    │                    │   │  V+   ───── 5V(VBUS)│     │          │
                    │                    │   │  GND  ───── GND     │     │          │
                    │                    │   │  Vout─R5 10kΩ─GPIO26│     │          │
                    │                    │   │      (ADC0, divider) │     │          │
                    │                    │   └─────────────────────┘     │          │
                    │                    │  Decoupling: 100nF+10µF      │          │
                    │                    │                             │          │
                    │                    └─────────────────────────────┘          │
                    │                                                             │
                    │                    XAC / AT OUTPUTS                          │
                    │                    ┌─────────────────────────────┐          │
                    │                    │                             │          │
                    │                    │   SIP_ENABLE (GPIO 0 OUT)     │          │
                    │                    │   ┌─────────────────────┐     │          │
                    │                    │   │  GPIO 0 → PC817 opto│     │          │
                    │                    │   │  → TRRS 3.5mm jack  │     │          │
                    │                    │   │    (XAC/AT output)  │     │          │
                    │                    │   └─────────────────────┘     │          │
                    │                    │                             │          │
                    │                    │   PUF_ENABLE (GPIO 1 OUT)     │          │
                    │                    │   ┌─────────────────────┐     │          │
                    │                    │   │  GPIO 1 → PC817 opto│     │          │
                    │                    │   │  → TRRS 3.5mm jack  │     │          │
                    │                    │   │    (XAC/AT output)  │     │          │
                    │                    │   └─────────────────────┘     │          │
                    │                    │                             │          │
                    │                    └─────────────────────────────┘          │
                    │                                                             │
                    │                    STATUS LED                               │
                    │                    ┌─────────────────────────────┐          │
                    │                    │                             │          │
                    │                    │   STATUS LED                  │          │
                    │                    │   ┌─────────────────────┐     │          │
                    │                    │   │                     │     │          │
                    │                    │   │  GPIO 2 ────┬─── 220Ω │     │          │
                    │                    │   │  VCC ───────┴─── 3.3V │     │          │
                    │                    │   │  GND ───────┴─── GND   │     │          │
                    │                    │   │                     │     │          │
                    │                    │   └─────────────────────┘     │          │
                    │                    │                             │          │
                    │                    └─────────────────────────────┘          │
                    │                                                             │
                    └─────────────────────────────────────────────────────────────┘
```

## Optional Display Connectors

> Both display connectors are unpopulated by default. Footprints are provided on the PCB so either or both can be added without rework. The I²C OLED shares the existing I²C bus with the LPS28DFWTR sensor (no address conflict). The SPI color LCD uses SPI1 hardware peripheral on dedicated GPIO pins.

---

### J1 — I²C OLED Display (1", 128×64, SSD1306 or compatible)

**Connector: 4-pin 2.54 mm Dupont / JST-XH, pin order top-to-bottom**

```
    J1 — I²C OLED CONNECTOR (4-pin Dupont)
    ┌────┬──────────┬────────────────────────────────────────────┐
    │ 1  │  GND     │  Ground                                    │
    │ 2  │  VCC     │  3.3V                                      │
    │ 3  │  SCL     │  GPIO 5 — I²C bus clock (shared)          │
    │ 4  │  SDA     │  GPIO 4 — I²C bus data (shared)           │
    └────┴──────────┴────────────────────────────────────────────┘

    SHARED I²C BUS NOTE:
    ┌─────────────────────────────────────────────────────────────┐
    │  LPS28DFWTR  ──┬──  GPIO 4/5  ──┬──  J1 OLED              │
    │                │                │                          │
    │                └────────────────┴──  STEMMA QT             │
    │                                                             │
    │  I²C addresses:                                             │
    │    LPS28DFWTR: 0x5C (SA0=GND) or 0x5D (SA0=VDD)           │
    │    SSD1306 OLED: 0x3C (default) or 0x3D (ADDR pin=VCC)    │
    │    STEMMA QT devices: address depends on connected device  │
    │    → Verify no address conflicts before connecting device  │
    │                                                             │
    │  Pull-ups: 10kΩ on SDA and SCL are shared (already placed) │
    └─────────────────────────────────────────────────────────────┘

                    J1 WIRING DIAGRAM
                    ┌─────────────────────────────┐
                    │                             │
                    │   J1 (4-pin Dupont)         │
                    │   ┌─────────────────────┐   │
                    │   │                     │   │
                    │   │  GND  ────── GND    │   │
                    │   │  VCC  ────── 3.3V   │   │
                    │   │  SCL  ────── GPIO 5 │   │  (I²C0 SCL, shared)
                    │   │  SDA  ────── GPIO 4 │   │  (I²C0 SDA, shared)
                    │   │                     │   │
                    │   └─────────────────────┘   │
                    │                             │
                    │  Display: 1" 128×64 OLED    │
                    │  Controller: SSD1306         │
                    │  Supply: 3.3V               │
                    │                             │
                    └─────────────────────────────┘
```

---

### STEMMA QT — I²C Expansion Port (Adafruit STEMMA QT / Qwiic compatible)

**Connector: JST-SH 4-pin (1.0 mm pitch) — standard Adafruit STEMMA QT / SparkFun Qwiic**

```
    STEMMA QT CONNECTOR (JST-SH 4-pin, 1.0mm pitch)
    ┌────┬──────────┬────────────────────────────────────────────────┐
    │ 1  │  GND     │  Ground                                        │
    │ 2  │  V+      │  3.3V — via R8 (10kΩ series on power line)    │
    │ 3  │  SDA     │  GPIO 4 — I²C0 SDA (shared bus)              │
    │ 4  │  SCL     │  GPIO 5 — I²C0 SCL (shared bus)              │
    └────┴──────────┴────────────────────────────────────────────────┘

    R8 NOTE: A 10kΩ resistor is placed in series on the V+ power line.
    This limits inrush current and provides soft power protection for
    connected STEMMA QT breakout boards. It is not a pull-up resistor —
    the I²C pull-ups (10kΩ on SDA/SCL) are separate and already placed.

                    STEMMA QT WIRING DIAGRAM
                    ┌─────────────────────────────┐
                    │                             │
                    │   STEMMA QT (JST-SH 4-pin)  │
                    │   ┌─────────────────────┐   │
                    │   │                     │   │
                    │   │  GND  ────── GND    │   │
                    │   │  V+   ─ R8(10kΩ) ─ 3.3V│  (current-limited 3.3V)
                    │   │  SDA  ────── GPIO 4 │   │  (I²C0 SDA, shared)
                    │   │  SCL  ────── GPIO 5 │   │  (I²C0 SCL, shared)
                    │   │                     │   │
                    │   └─────────────────────┘   │
                    │                             │
                    │  Compatible: any Adafruit   │
                    │  STEMMA QT or SparkFun      │
                    │  Qwiic I²C breakout board   │
                    │  (3.3V logic, I²C)          │
                    │                             │
                    └─────────────────────────────┘

    USE CASES:
    • Plug-and-play I²C sensor expansion (IMU, RTC, colour sensor, etc.)
    • Future MPU6050 IMU connection for head-tracking (Section 10.3)
    • Any Adafruit STEMMA QT or SparkFun Qwiic module
    • Verify I²C address of connected device against bus address table
```

---

### J2 — SPI Color LCD Display (2"–4", ST7789 / ILI9341 or compatible)

**Connector: 9-pin 2.54 mm Dupont / JST-XH, pin order matches display pinout table**

**GPIO assignment — SPI1 hardware peripheral, non-analog pins:**

```
    J2 — SPI COLOR LCD CONNECTOR (9-pin Dupont)
    ┌────┬──────────────┬────────────────────────────────────────┐
    │ 1  │  VCC         │  3.3V power                            │
    │ 2  │  GND         │  Ground                                │
    │ 3  │  CS          │  GPIO 13 — SPI1 CSn (active low)      │
    │ 4  │  RESET       │  GPIO 15 — LCD reset (active low)     │
    │ 5  │  DC/RS       │  GPIO 14 — data/command select        │
    │ 6  │  SDI (MOSI)  │  GPIO 11 — SPI1 TX                    │
    │ 7  │  SCK         │  GPIO 10 — SPI1 SCK                   │
    │ 8  │  LED         │  GPIO 16 — backlight PWM (or 3.3V)    │
    │ 9  │  SDO (MISO)  │  GPIO 12 — SPI1 RX (optional)        │
    └────┴──────────────┴────────────────────────────────────────┘

    NOTE: If read-back from the display is not needed, pin 9 (SDO/MISO)
    can be left unconnected on both the PCB header and the display side.

    LED (pin 8) options:
      • Connect to GPIO 16 for software-controlled PWM brightness
      • Connect directly to 3.3V to keep backlight always on (no GPIO needed)
      PCB has solder bridge: default routes to GPIO 16; bridge for always-on.

                    J2 WIRING DIAGRAM
                    ┌─────────────────────────────────┐
                    │                                 │
                    │   J2 (9-pin Dupont)             │
                    │   ┌─────────────────────────┐   │
                    │   │                         │   │
                    │   │  VCC   ────── 3.3V      │   │
                    │   │  GND   ────── GND       │   │
                    │   │  CS    ────── GPIO 13   │   │  (SPI1 CSn)
                    │   │  RESET ────── GPIO 15   │   │  (active low)
                    │   │  DC/RS ────── GPIO 14   │   │  (data/cmd)
                    │   │  MOSI  ────── GPIO 11   │   │  (SPI1 TX)
                    │   │  SCK   ────── GPIO 10   │   │  (SPI1 SCK)
                    │   │  LED   ────── GPIO 16   │   │  (backlight PWM)
                    │   │  MISO  ────── GPIO 12   │   │  (SPI1 RX, opt.)
                    │   │                         │   │
                    │   └─────────────────────────┘   │
                    │                                 │
                    │  Display: 2"–4" color TFT LCD   │
                    │  Controller: ST7789 / ILI9341   │
                    │  Supply: 3.3V                   │
                    │  SPI bus: SPI1 hardware          │
                    │                                 │
                    └─────────────────────────────────┘

    SPI1 HARDWARE PINS SUMMARY:
    ┌───────────────────────────────────────────────────────────┐
    │  GPIO 10 ── SCK    (SPI1 SCK)                            │
    │  GPIO 11 ── MOSI   (SPI1 TX)                             │
    │  GPIO 12 ── MISO   (SPI1 RX)   optional                  │
    │  GPIO 13 ── CS     (SPI1 CSn)  driven by firmware        │
    │  GPIO 14 ── DC/RS  (GPIO out)  high=data, low=command    │
    │  GPIO 15 ── RESET  (GPIO out)  pulse low to reset        │
    │  GPIO 16 ── LED    (PWM out)   backlight brightness       │
    │                                                           │
    │  All pins are non-analog. GPIO 26–29 (ADC) are free.    │
    └───────────────────────────────────────────────────────────┘
```

---

### EXTERNAL_IO — Rotary Encoder / Button / I²C Expansion Header

**Connector: 7-pin 2.54 mm header (MA06-1 footprint)**

This connector consolidates the rotary encoder signals, push button, and I²C bus into a single header for connecting an external encoder+OLED module or control panel. The rotary encoder channels are named ROT_A/SIP and ROT_B/PUFF reflecting their firmware role — channel A triggers on sip detection, channel B on puff detection.

```
    EXTERNAL_IO CONNECTOR (7-pin 2.54mm header)
    ┌────┬──────────────┬────────────────────────────────────────────┐
    │ 1  │  BUTTON      │  GPIO 20 — rotary encoder push button     │
    │ 2  │  ROT_A/SIP   │  GPIO 18 — rotary encoder channel A       │
    │ 3  │  ROT_B/PUFF  │  GPIO 19 — rotary encoder channel B       │
    │ 4  │  SCL         │  GPIO 5  — I²C0 SCL (shared bus)         │
    │ 5  │  SDA         │  GPIO 4  — I²C0 SDA (shared bus)         │
    │ 6  │  3.3V        │  3.3V power                               │
    │ 7  │  GND         │  Ground                                   │
    └────┴──────────────┴────────────────────────────────────────────┘

                    EXTERNAL_IO WIRING DIAGRAM
                    ┌──────────────────────────────────────┐
                    │                                      │
                    │   EXTERNAL_IO (7-pin header)         │
                    │   ┌────────────────────────────┐     │
                    │   │                            │     │
                    │   │  BUTTON ────── GPIO 20     │     │  (active low, pull-up in fw)
                    │   │  ROT_A  ────── GPIO 18     │     │  (SIP channel)
                    │   │  ROT_B  ────── GPIO 19     │     │  (PUFF channel)
                    │   │  SCL    ────── GPIO 5      │     │  (I²C shared)
                    │   │  SDA    ────── GPIO 4      │     │  (I²C shared)
                    │   │  3.3V   ────── 3.3V        │     │
                    │   │  GND    ────── GND         │     │
                    │   │                            │     │
                    │   └────────────────────────────┘     │
                    │                                      │
                    │  Typical use: rotary encoder module  │
                    │  with integrated push button and     │
                    │  I²C OLED (SSD1306) on same header   │
                    │                                      │
                    └──────────────────────────────────────┘

    ROTARY ENCODER NOTES:
    • ROT_A (GPIO 18) and ROT_B (GPIO 19) are quadrature encoder inputs
    • Channel naming (SIP/PUFF) reflects firmware mapping —
      clockwise rotation = sip-direction events, CCW = puff-direction
    • BUTTON (GPIO 20) is the encoder shaft push button — configure
      with internal pull-up in firmware (active low)
    • I²C pins (4 & 5) on this connector share the bus with
      LPS28DFWTR, J1 OLED, and STEMMA QT — verify address of
      any device connected here
```

---

### Full GPIO Allocation Map (updated)

```
    PICO W GPIO ALLOCATION
    ┌────────┬──────────────────────────────────────────────────┐
    │ GPIO 0 │  SIP_ENABLE output → PC817 opto → TRRS 3.5mm jack (XAC/AT) │
    │ GPIO 1 │  PUF_ENABLE output → PC817 opto → TRRS 3.5mm jack (XAC/AT) │
    │ GPIO 2 │  Status LED (onboard / external)                 │
    │ GPIO 3 │  [reserved]                                      │
    │ GPIO 4 │  I²C0 SDA — LPS28DFWTR + J1 OLED + STEMMA QT (shared bus) │
    │ GPIO 5 │  I²C0 SCL — LPS28DFWTR + J1 OLED + STEMMA QT (shared bus) │
    │ GPIO 6 │  INT_DRDY — LPS28DFWTR interrupt (optional)     │
    │ GPIO 7 │  [reserved]                                      │
    │ GPIO 8 │  [reserved]                                      │
    │ GPIO 9 │  [reserved]                                      │
    │ GPIO 10│  SPI1 SCK  — J2 color LCD SCK                   │
    │ GPIO 11│  SPI1 TX   — J2 color LCD MOSI/SDI              │
    │ GPIO 12│  SPI1 RX   — J2 color LCD MISO/SDO (optional)   │
    │ GPIO 13│  SPI1 CSn  — J2 color LCD CS                    │
    │ GPIO 14│  GPIO out  — J2 color LCD DC/RS                  │
    │ GPIO 15│  GPIO out  — J2 color LCD RESET                  │
    │ GPIO 16│  PWM out   — J2 color LCD backlight LED          │
    │ GPIO 17│  [reserved]                                      │
    │ GPIO 18│  ROT_A/SIP  — rotary encoder channel A (EXTERNAL_IO pin 2) │
    │ GPIO 19│  ROT_B/PUFF — rotary encoder channel B (EXTERNAL_IO pin 3) │
    │ GPIO 20│  BUTTON     — rotary encoder push button (EXTERNAL_IO pin 1) │
    │GPIO 21-│                                                  │
    │GPIO 25 │  [reserved for future expansion]                 │
    │ GPIO 26│  ADC0 — MPX5010DP analog (alternative sensor) via R5 10kΩ │
    │ GPIO 27│  ADC1 — [reserved]                               │
    │ GPIO 28│  ADC2 — [reserved]                               │
    │ GPIO 29│  ADC3 — [reserved / VSYS sense on Pico W]       │
    └────────┴──────────────────────────────────────────────────┘
```

---

## Component List

### Power Supply Components:
- **3.3V LDO Regulator** (e.g., LM1117-3.3 or similar)
- **Input Voltage (VIN)**: 5V
- **Output Voltage**: 3.3V
- **Capacitors**: 100μF (input), 10μF (output)

### Microcontroller Components:
- **Raspberry Pi Pico W** (RP2040 + CYW43439)
- **GPIO Pins used**: 0 (SIP_ENABLE out), 1 (PUF_ENABLE out), 2 (LED), 4 (I²C SDA), 5 (I²C SCL), 6 (INT_DRDY opt.), 10–16 (SPI color LCD), 18 (ROT_A/SIP), 19 (ROT_B/PUFF), 20 (BUTTON), 26 (ADC0 alt.)
- **Power Pins**: VBUS, VSYS, GND

### Sensor Components (populate ONE — both footprints on initial PCB):

**DEFAULT — LPS28DFWTR (SMD, I²C):**
- **LPS28DFWTR** CCLGA-7L, STMicroelectronics
- **Interface**: I²C — GPIO 4 (SDA), GPIO 5 (SCL)
- **I²C address**: 0x5C (SA0 → GND) or 0x5D (SA0 → VDD)
- **INT_DRDY**: GPIO 6 (optional data-ready interrupt)
- **Pull-up Resistors**: 10kΩ on SDA and SCL to 3.3V
- **Decoupling Cap**: 100nF ceramic between VDD and GND
- **Supply**: 3.3V (1.7–3.6V range)

**ALTERNATIVE — MPX5010DP (Through-Hole, Analog):**
- **MPX5010DP** SIP-6, NXP/Freescale
- **Interface**: Analog voltage → R5 (10kΩ) → GPIO 26 (ADC0); **NOT I²C**
- **Supply**: **5V (VBUS)** — full output range 0.2V–4.7V
- **Voltage divider**: R5 (10kΩ, top leg) + ~20kΩ pull-down to GND scales Vout to ≤3.3V for ADC safety
- **Decoupling Caps**: 100nF + 10µF on supply pins

### XAC / AT Output Components:
- **SIP_ENABLE output**: GPIO 0 → PC817SC optocoupler → TRRS 3.5mm jack (SIP output to XAC or AT device)
- **PUF_ENABLE output**: GPIO 1 → PC817SC optocoupler → TRRS 3.5mm jack (PUFF output to XAC or AT device)
- **Optocouplers**: 2× PC817SC / DPC817S-X-TRSL-4 (one per channel)
- **TRRS Jacks**: 2× TRRS_2SWITCH_PJ332A (3.5mm, TRRS)
- **Note**: Sip/puff is **detected** by the pressure sensor (LPS28DFWTR or MPX5010DP), not by these GPIOs

### Output Components:
- **Status LED**: GPIO 2
- **Current Limiting Resistor**: 220Ω
- **LED Color**: Green (optional: Red or Blue)

### EXTERNAL_IO Connector Components:
- **Connector**: 7-pin 2.54 mm header (MA06-1)
- **BUTTON**: GPIO 20 — rotary encoder push button (active low, firmware pull-up)
- **ROT_A/SIP**: GPIO 18 — rotary encoder channel A
- **ROT_B/PUFF**: GPIO 19 — rotary encoder channel B
- **SCL / SDA**: GPIO 5 / GPIO 4 — I²C shared bus
- **Power**: 3.3V and GND

### STEMMA QT I²C Expansion Connector:
- **Connector**: JST-SH 4-pin (1.0 mm pitch) — STEMMA QT / Qwiic standard
- **Interface**: I²C shared bus — GPIO 4 (SDA), GPIO 5 (SCL)
- **Power**: 3.3V via R8 (10kΩ series resistor for inrush protection)
- **Compatible with**: Any Adafruit STEMMA QT or SparkFun Qwiic I²C module (3.3V logic)
- **Planned use**: IMU (MPU6050) for head-tracking expansion (see Section 10.3 of reference doc)

### Optional Display Connector Components:

**J1 — I²C OLED (4-pin Dupont, unpopulated by default):**
- **Connector**: 4-pin 2.54 mm Dupont / JST-XH header on PCB
- **Display**: 1" 128×64 OLED (SSD1306 or compatible)
- **Interface**: I²C shared bus — GPIO 4 (SDA), GPIO 5 (SCL)
- **I²C address**: 0x3C (default) or 0x3D
- **Supply**: 3.3V

**J2 — SPI Color LCD (9-pin Dupont, unpopulated by default):**
- **Connector**: 9-pin 2.54 mm Dupont / JST-XH header on PCB
- **Display**: 2"–4" color TFT LCD (ST7789 / ILI9341 or compatible)
- **Interface**: SPI1 hardware — GPIO 10 (SCK), 11 (MOSI), 12 (MISO), 13 (CS), 14 (DC/RS), 15 (RESET), 16 (LED/backlight)
- **Supply**: 3.3V
- **Backlight**: GPIO 16 (PWM) or solder bridge to always-on 3.3V

### Rubber Chicken Interface Components:
- **Sip Interface**: Mechanical connection for suction
- **Blow Interface**: Mechanical connection for blowing
- **Status Indicator**: LED for system status

## Key Features:

1. **Power Management**: 5V input to 3.3V output
2. **Dual Sensor Support**: LPS28DFWTR (SMD, I²C default) or MPX5010DP (through-hole, analog ADC alternative) — both footprints on initial PCBs
3. **I²C Communication**: LPS28DFWTR on GPIO 4 (SDA) / GPIO 5 (SCL) at address 0x5C — 24-bit, 0.32 Pa noise, water-resistant
4. **ADC Input (alternative)**: MPX5010DP analog Vout on GPIO 26 (ADC0)
5. **XAC / AT Outputs**: GPIO 0 (SIP_ENABLE) and GPIO 1 (PUF_ENABLE) drive PC817SC optocouplers → TRRS 3.5mm jacks for Xbox Adaptive Controller or AT device integration; sip/puff detection is done by the pressure sensor, not these GPIOs
6. **Status Output**: LED indicator on GPIO 2
7. **EXTERNAL_IO Connector**: 7-pin header combining rotary encoder (GPIO 18 ROT_A/SIP, GPIO 19 ROT_B/PUFF), push button (GPIO 20), and I²C bus (GPIO 4/5) + 3.3V/GND — connects rotary encoder module with optional integrated OLED
8. **STEMMA QT I²C Expansion Port**: JST-SH 4-pin connector on shared I²C bus (GPIO 4/5); 3.3V power via R8 (10kΩ); compatible with any Adafruit STEMMA QT or SparkFun Qwiic module — primary expansion point for future IMU head-tracking
9. **Optional I²C OLED Display (J1)**: 4-pin Dupont connector; 1" 128×64 SSD1306 shares I²C bus with LPS28DFWTR (addresses 0x3C vs 0x5C — no conflict)
10. **Optional SPI Color LCD (J2)**: 9-pin Dupont connector; 2"–4" ST7789/ILI9341 on dedicated SPI1 hardware pins (GPIO 10–16); backlight PWM on GPIO 16
11. **Rubber Chicken Interface**: Mechanical connections for sip/puff demonstration
10. **Low Power Consumption**: LPS28DFWTR idles at 1.7 µA; overall system target < 10 mA standby (displays off)
11. **Real-time Processing**: Pico W RP2040 handles I²C polling, ADC sampling, signal filtering, USB HID output, and optional display rendering

This schematic documents both sensor options in a dual-footprint design. The LPS28DFWTR I²C sensor is the default for production use; the MPX5010DP through-hole option remains available for prototyping without SMD tooling. Both display connectors (J1 I²C OLED and J2 SPI color LCD) are built into the PCB hardware but unpopulated — enabling future display support without board redesign.