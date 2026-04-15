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
                    │  GPIO 0 → SIP in   │
                    │  GPIO 1 → PUFF in  │
                    │  GPIO 2 → Status LED│
                    │  GPIO 4 → I²C SDA  │  (LPS28DFWTR default)
                    │  GPIO 5 → I²C SCL  │  (LPS28DFWTR default)
                    │  GPIO 6 → INT_DRDY │  (LPS28DFWTR optional)
                    │  GPIO 26 → ADC0    │  (MPX5010DP alternative)
                    │                    │
                    └─────────┬──────────┘
                              │
               ┌──────────────┼──────────────┐
               │              │              │
    ┌──────────▼───┐  ┌───────▼──────┐  ┌───▼────────────┐
    │  Sip Input   │  │  Puff Input  │  │  Status LED    │
    │  (Suction)   │  │  (Blow)      │  │  Indicator     │
    │  GPIO 0      │  │  GPIO 1      │  │  GPIO 2        │
    └──────────────┘  └──────────────┘  └────────────────┘
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
    │  Pin 1  (V+)   → 3.3V  (note: rated 5V; see below) │
    │  Pin 2  (V-)   → GND                                │
    │  Pin 3  (Vout) → Pico W GPIO 26 (ADC0)              │
    │  Pin 4  (not connected or GND per datasheet)        │
    │  Pin 5  (Vs)   → 3.3V                               │
    │  Pin 6  (GND)  → GND                                │
    └──────────────────────────────────────────────────────┘

    ⚠ VOLTAGE NOTE: MPX5010DP is rated for 5V supply.
    At 3.3V the output range is reduced (~0.13V–3.05V
    vs 0.2V–4.7V at 5V). ADC resolution is preserved
    but verify firmware thresholds accordingly.
    If 5V supply is used, add a voltage divider on Vout
    to keep ADC input ≤ 3.3V before connecting to GPIO 26.

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
                    │   │  V+   ────── 3.3V   │   │
                    │   │  V-   ────── GND    │   │
                    │   │  Vout ────── GPIO 26│   │  (ADC0 — analog read)
                    │   │  Vs   ────── 3.3V   │   │
                    │   │  GND  ────── GND    │   │
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
    • Output:          Analog voltage (0.2–4.7V @ 5V supply)
    • Accuracy:        ±1.5% FS
    • Supply:          2.7–5.5V
    • Package:         Through-hole SIP — hand-solderable
    • Interface:       ADC (not I²C)
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
                          │   V+   ────── 3.3V          │
                          │   Vout ────── GPIO 26 (ADC) │
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
                    │   │  V+   ────────── 3.3V        │   │
                    │   │  GND  ────────── GND         │   │
                    │   │  Vout ────────── GPIO 26     │   │
                    │   │                  (ADC0)      │   │
                    │   └──────────────────────────────┘   │
                    │  Decoupling: 100nF + 10µF on V+–GND  │
                    │                                      │
                    └──────────────────────────────────────┘
```

## Input Signal Circuit

```
                    INPUT SIGNAL CIRCUIT
                    ┌─────────────────────────────┐
                    │                             │
                    │   SIP INPUT (Suction)       │
                    │   ┌─────────────────────┐   │
                    │   │                     │   │
                    │   │  GPIO 0 ────┬─── 10kΩ │   │
                    │   │  VCC ───────┴─── 3.3V │   │
                    │   │  GND ───────┴─── GND   │   │
                    │   │                     │   │
                    │   └─────────────────────┘   │
                    │                             │
                    │   PUFF INPUT (Blow)         │
                    │   ┌─────────────────────┐   │
                    │   │                     │   │
                    │   │  GPIO 1 ────┬─── 10kΩ │   │
                    │   │  VCC ───────┴─── 3.3V │   │
                    │   │  GND ───────┴─── GND   │   │
                    │   │                     │   │
                    │   └─────────────────────┘   │
                    │                             │
                    └─────────────────────────────┘
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
                    │                    │   │  GPIO 0 ────┬─── SIP         │     │          │
                    │                    │   │  GPIO 1 ────┬─── PUFF        │     │          │
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
                    │                    │   │  V+   ───── 3.3V    │     │          │
                    │                    │   │  GND  ───── GND     │     │          │
                    │                    │   │  Vout ───── GPIO 26 │     │          │
                    │                    │   │         (ADC0-analog│     │          │
                    │                    │   └─────────────────────┘     │          │
                    │                    │  Decoupling: 100nF+10µF      │          │
                    │                    │                             │          │
                    │                    └─────────────────────────────┘          │
                    │                                                             │
                    │                    INPUT SIGNALS                            │
                    │                    ┌─────────────────────────────┐          │
                    │                    │                             │          │
                    │                    │   SIP INPUT (Suction)         │          │
                    │                    │   ┌─────────────────────┐     │          │
                    │                    │   │                     │     │          │
                    │                    │   │  GPIO 0 ────┬─── 10kΩ │     │          │
                    │                    │   │  VCC ───────┴─── 3.3V │     │          │
                    │                    │   │  GND ───────┴─── GND   │     │          │
                    │                    │   │                     │     │          │
                    │                    │   └─────────────────────┘     │          │
                    │                    │                             │          │
                    │                    │   PUFF INPUT (Blow)           │          │
                    │                    │   ┌─────────────────────┐     │          │
                    │                    │   │                     │     │          │
                    │                    │   │  GPIO 1 ────┬─── 10kΩ │     │          │
                    │                    │   │  VCC ───────┴─── 3.3V │     │          │
                    │                    │   │  GND ───────┴─── GND   │     │          │
                    │                    │   │                     │     │          │
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

## Component List

### Power Supply Components:
- **3.3V LDO Regulator** (e.g., LM1117-3.3 or similar)
- **Input Voltage (VIN)**: 5V
- **Output Voltage**: 3.3V
- **Capacitors**: 100μF (input), 10μF (output)

### Microcontroller Components:
- **Raspberry Pi Pico W** (RP2040 + CYW43439)
- **GPIO Pins used**: 0 (SIP), 1 (PUFF), 2 (LED), 4 (I²C SDA), 5 (I²C SCL), 6 (INT_DRDY opt.), 26 (ADC0 alt.)
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
- **Interface**: Analog voltage → GPIO 26 (ADC0); **NOT I²C**
- **Supply**: 3.3V (rated 5V; output range scales accordingly)
- **Decoupling Caps**: 100nF + 10µF on supply pins

### Input Signal Components:
- **SIP Input**: GPIO 0
- **PUFF Input**: GPIO 1
- **Pull-up Resistors**: 10kΩ
- **VCC**: 3.3V

### Output Components:
- **Status LED**: GPIO 2
- **Current Limiting Resistor**: 220Ω
- **LED Color**: Green (optional: Red or Blue)

### Rubber Chicken Interface Components:
- **Sip Interface**: Mechanical connection for suction
- **Blow Interface**: Mechanical connection for blowing
- **Status Indicator**: LED for system status

## Key Features:

1. **Power Management**: 5V input to 3.3V output
2. **Dual Sensor Support**: LPS28DFWTR (SMD, I²C default) or MPX5010DP (through-hole, analog ADC alternative) — both footprints on initial PCBs
3. **I²C Communication**: LPS28DFWTR on GPIO 4 (SDA) / GPIO 5 (SCL) at address 0x5C — 24-bit, 0.32 Pa noise, water-resistant
4. **ADC Input (alternative)**: MPX5010DP analog Vout on GPIO 26 (ADC0)
5. **Digital Input**: SIP (GPIO 0) and PUFF (GPIO 1) inputs
6. **Status Output**: LED indicator on GPIO 2
7. **Rubber Chicken Interface**: Mechanical connections for sip/puff demonstration
8. **Low Power Consumption**: LPS28DFWTR idles at 1.7 µA; overall system target < 10 mA standby
9. **Real-time Processing**: Pico W RP2040 handles I²C polling, ADC sampling, signal filtering, and USB HID output

This schematic documents both sensor options in a dual-footprint design. The LPS28DFWTR I²C sensor is the default for production use; the MPX5010DP through-hole option remains available for prototyping without SMD tooling. After real-world testing, separate PCB variants will be spun for each sensor.