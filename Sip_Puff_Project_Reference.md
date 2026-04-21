# Sip-and-Puff / Mouth-Operated Input: Open-Source Project Reference

*A living reference covering four open-source assistive input projects — what each solved, what remains unsolved, the technical methods chosen, and springboard insights for forward development.*

**Compiled:** April 2026

---

## Contents

1. [Purpose of This Document](#1-purpose-of-this-document)
2. [Quick Comparison Matrix](#2-quick-comparison-matrix)
3. [Project 1 — openSipPuff (jasonwebb)](#3-project-1--opensippuff-jasonwebb)
4. [Project 2 — The 'Sup / SipNPuff_Mouse (Bobcatmodder)](#4-project-2--the-sup--sipnpuff_mouse-bobcatmodder)
5. [Project 3 — FLipMouse (asterics)](#5-project-3--flipmouse-asterics)
6. [Project 4 — LipSync (Makers Making Change)](#6-project-4--lipsync-makers-making-change)
7. [Cross-Project Patterns and Lessons](#7-cross-project-patterns-and-lessons)
   - [7.6 Configuration Requires a Computer or a Developer — Always](#76-configuration-requires-a-computer-or-a-developer--always)
   - [7.7 ESD / Circuit Protection Is Almost Universally Absent](#77-esd--circuit-protection-is-almost-universally-absent)
8. [Springboard: Gaps to Exploit in Your Project](#8-springboard-gaps-to-exploit-in-your-project)
9. [Reference Links](#9-reference-links)
10. [Lessons Learned and To Be Implemented](#10-lessons-learned-and-to-be-implemented)
    - [10.1 Breath Hygiene Filtering](#101-breath-hygiene-filtering)
    - [10.2 Wireless Connectivity — Bluetooth Implementation](#102-wireless-connectivity--bluetooth-implementation)
    - [10.3 Joystick / Cursor Movement — IMU-Based Head Tracking](#103-joystick--cursor-movement--imu-based-head-tracking)
    - [10.4 Pressure Sensor Selection — LPS28DFWTR as Default](#104-pressure-sensor-selection--lps28dfwtr-as-default)
    - [10.5 Optional Display Hardware — Built-in PCB Support](#105-optional-display-hardware--built-in-pcb-support)
    - [10.6 Circuit Protection — SP724AHTG on External I/O Lines](#106-circuit-protection--sp724ahtg-on-external-io-lines)
    - [10.7 Medical Certification Pathway — Redundant Sensor and Safety CPU](#107-medical-certification-pathway--redundant-sensor-and-safety-cpu)

---

## 1. Purpose of This Document

This document serves as a permanent, self-contained reference that eliminates the need to re-read the original GitHub repositories and Instructables pages. It distills the design decisions, technical approaches, solved problems, and known limitations from four significant open-source sip-and-puff / mouth-operated assistive input projects. The goal is to give you and a future AI session an immediate, actionable picture of the landscape so your project can leap forward from the best of what already exists.

Each project is summarised under consistent headings so direct comparison is easy. Section 7 synthesises cross-cutting patterns, and Section 8 maps the gaps your project can fill.

---

## 2. Quick Comparison Matrix

| Feature | openSipPuff (jasonwebb) | The 'Sup (Bobcatmodder) | FLipMouse (asterics) | LipSync (MMC) | Gap / Your Potential |
|---|---|---|---|---|---|
| **MCU** | ATmega32u4 | Arduino Pro Micro | Arduino Nano RP2040 | Arduino platform | Your choice |
| **Position sensing** | None (breath only) | Analog joystick | Strain gauges (4×DMS) | Hall-effect 3D magnet | **Post-Maker-Faire: BNO055 9-DOF IMU — Mode A: head strap/glasses mount; Mode B: straw collar tongue joystick. Same hardware, config-file switch. Hall-effect stick as further stretch goal.** |
| **Pressure sensor** | MPXV7007GP (analog) | MPXV7002DP | Dedicated sensor | LPS33HW + LPS22 (I²C) | **✓ LPS28DFWTR (I²C, water-resistant, 24-bit) — default; MPX5010DP through-hole alternative** |
| **USB HID** | ✓ kbd/mouse/MIDI | ✓ mouse | ✓ mouse/kbd/gamepad | ✓ mouse/gamepad | ✓ (table stakes) |
| **Bluetooth** | ✗ | ✗ | ✓ (RP2040 + ESP32) | ✓ (module, retired) | ✓ — critical gap |
| **Joystick + sip unified** | ✗ | ✓ (3D-printed) | ✓ (mouthpiece) | ✓ (Joystick unit) | ✓ |
| **Separate sip/puff threshold** | ✗ | ✗ | ✓ | ✓ | ✓ must-have |
| **Config slots** | ✗ | ✗ | ✓ (EEPROM) | ✓ (Hub display) | ✓ with display |
| **Text file config** | ✗ | ✗ | ✗ (WebGUI only) | ✗ (Hub only) | **✓ — primary differentiator: USB mass storage config file, no reflashing, no PC app required** |
| **Display / UI** | ✗ | ✗ | Web GUI (PC only) | Hub OLED | **✓ J1: 1" 128×64 I²C OLED (SSD1306) + J2: 2–4" SPI color LCD (ST7789/ILI9341) — PCB connectors built in** |
| **External switches** | ✗ | ✗ | 2× 3.5 mm jack | 3× 3.5 mm jack | 3+ jacks |
| **IR env. control** | ✗ | ✗ | ✓ (record+replay) | ✗ | Nice-to-have |
| **Hygiene filter** | ✗ | ✗ (noted risk) | ✓ | ✓ | ✓ required |
| **OSHWA certified** | ✗ | ✗ | ✗ | ✓ CA000046 | Consider |
| **Approx. build cost** | $60–100 target | < $50 | ~$100–150 est. | $175–325 | Target < $150 |
| **Project status** | Stalled ~2014 | Active (2017+) | Actively maintained | Actively maintained | — |

---

## 3. Project 1 — openSipPuff (jasonwebb)

**GitHub:** https://github.com/jasonwebb/openSipPuff

### 3.1 Overview

openSipPuff is a minimalist, standalone sip-and-puff USB interface designed around the philosophy of keeping part count and assembly steps to an absolute minimum while maximising creative expressiveness. Created by Jason Webb around 2013, it targets breath-based control of keypresses, mouse actions, MIDI, and any other USB HID function — all without requiring special drivers on the host computer.

### 3.2 Hardware

- **MCU:** ATmega32u4 running the Arduino Leonardo bootloader. Native USB HID — no LUFA, no additional USB chip.
- **Pressure sensor:** MPXV7007GP (NXP/Freescale). Analog output, ±7 kPa range, normalised to 0.5 V–4.5 V. Rests at ~2.5 V; positive pressure drives voltage up, negative (sip) drives it down.
- **I²C expansion port:** 4-pin header (VCC, GND, SDA, SCL) exposes the processed analog data stream — lets other boards tap into breath data.
- **Form factor:** Custom PCB (OSH Park, Rev B). No onboard joystick or directional sensor.

### 3.3 What It Solved

- **Driverless USB HID:** The ATmega32u4 appears as a standard mouse/keyboard/MIDI device on any OS immediately.
- **Low part count:** Reduced BOM to MCU + single pressure sensor + passives. Very replicable.
- **Analog breath resolution:** Unlike binary switch-based designs, the MPXV7007GP provides a continuous 0–1023 analog value, enabling variable-speed scrolling, velocity-sensitive MIDI notes, or proportional mouse speed.
- **Expansion via I²C:** Other microcontrollers or modules can read the breath data directly without duplicating the sensor circuit.
- **Target cost:** Designed to stay under $60–$100 retail, far below commercial equivalents.
- **MIDI as first-class output:** Explicitly planned as a creative tool, not just a clinical AT device.

### 3.4 What It Did NOT Solve / Known Limitations

- **No directional / cursor movement:** openSipPuff is breath-only. There is no joystick, trackball, or gyroscope — the device cannot move a cursor by itself.
- **Binary sip vs. puff only in practice:** Although analog values are available, the reference firmware exposed only threshold-based events, not continuous values, to the USB HID layer.
- **No Bluetooth:** USB-only. Cannot drive a smartphone or tablet wirelessly.
- **No configuration UI:** No display, no on-device settings. Changes require firmware re-flashing.
- **No hygiene filter:** No provision for saliva capture or breath filtration.
- **Project stalled ~2014:** After Rev B prototype boards were built and tested, the project lost momentum due to "a few small problems" and never shipped commercially or reached end users systematically. Last commit activity circa 2013–2014.
- **No external switch inputs:** No 3.5 mm jack provisions for external assistive switches.

### 3.5 Technical Method & Springboard Value

The key insight here is the MPXV7007GP pressure sensor paired with an ATmega32u4. The sensor's ±7 kPa range covers the full human breath force range, and the analog output wires directly to an ADC pin — the simplest possible sip/puff circuit. The I²C tap-out idea is ahead of its time: it allows a modular architecture where a separate board handles position tracking while openSipPuff handles breath.

**For your project:** Adopt this sensor pattern (or the water-resistant LPS33HW as an upgrade), keep the ATmega32u4 or RP2040 for USB HID, and add the missing pieces (joystick, display, BT) on top.

> **Note:** The MPXV7007GP has been superseded. Consider NXP MPXV7007DP (dual-port) or Adafruit LPS33HW for a water-resistant I²C alternative.

---

## 4. Project 2 — The 'Sup / SipNPuff_Mouse (Bobcatmodder)

**GitHub:** https://github.com/Bobcatmodder/SipNPuff_Mouse  
**Instructables:** https://www.instructables.com/The-Sup-a-Mouse-for-Quadriplegics-Low-Cost-and-Ope/

### 4.1 Overview

Created in spring 2017 by a high-school maker (Bobcatmodder) for a friend named Allen who became quadriplegic after a mountain-biking accident. The 'Sup (SUP = Sip/pUff/Puff) combines sip-and-puff input with a two-axis joystick in a single 3D-printed mouthpiece, allowing cursor movement via mouth angle plus left/right click and scroll via breath. It won an Instructables contest and was featured on Hackaday.

### 4.2 Hardware

- **MCU:** Arduino Pro Micro (ATmega32u4). Native USB HID mouse without extra libraries.
- **Pressure sensor:** MPXV7002DP on a breakout board. Analog output, ±2 kPa range — adequate for human sip/puff.
- **Position sensor:** Off-the-shelf two-axis analog joystick module (thumb-stick type).
- **Mouthpiece:** 3D-printed in PLA. Hollow body acts simultaneously as a joystick handle (user grips with lips/teeth) and air channel (tubing runs through it to the pressure sensor).
- **Build cost:** Under $50 USD. Commercial equivalents: $500–$1,500.

### 4.3 What It Solved

- **Joystick + sip/puff in one mouthpiece:** The elegant 3D-printed design integrates the joystick module inside the mouthpiece housing. Users move the joystick by moving their head/mouth while simultaneously using breath for clicks. This is the key mechanical insight of the project.
- **Extreme affordability:** < $50 is the lowest build cost of all reviewed projects by a wide margin.
- **Native USB HID mouse:** The Arduino Pro Micro presents as a standard USB mouse — plug in, no drivers.
- **Three-tier pressure mapping:** Hard sip/puff = left/right click; soft breath = scroll. Maps well to the most common mouse actions.
- **Fully open source:** All STL files, wiring diagrams, and firmware on GitHub.

### 4.4 What It Did NOT Solve / Known Limitations

- **No hygiene/breath filter:** Explicitly noted as a concern. Saliva or moisture can reach the pressure sensor over time, causing drift or sensor failure. No filter housing was designed.
- **PLA mouthpiece durability:** Standard PLA will not withstand cleaning protocols (alcohol, autoclave) that a medical-grade mouthpiece needs.
- **No Bluetooth:** USB-only. The device cannot control a smartphone or tablet wirelessly.
- **No configuration interface:** Thresholds for sip/puff levels are hardcoded. Users cannot adjust sensitivity without re-flashing firmware.
- **Single threshold for all breath actions:** Sip and puff use the same absolute pressure threshold, which may not work for users with asymmetric breath strength.
- **No external switch inputs:** No provision for connecting external assistive switches.
- **No cursor acceleration or speed profiles:** Mouse speed is fixed in firmware.
- **Joystick module wear:** The off-the-shelf thumb-stick joystick has relatively high activation force and wear characteristics that may not suit long-duration use.

### 4.5 Technical Method & Springboard Value

The most valuable take-away is the physical architecture: a 3D-printed mouthpiece that doubles as a joystick handle and air conduit — the simplest possible way to unify position and breath sensing. The MPXV7002DP's ±2 kPa range is actually better suited than the wider ±7 kPa of the openSipPuff part, since most users only generate 1–3 kPa.

**For your project:** Adopt this mouthpiece-as-joystick-handle concept but upgrade the joystick to a Hall-effect sensor (like the LipSync does), replace PLA with PETG or ASA for chemical resistance, and add a breath filter housing.

> **Note:** The Arduino Pro Micro is a direct drop-in; but the RP2040 offers more RAM, dual-core processing, and native USB plus Bluetooth co-processor options (see FLipMouse section).

---

## 5. Project 3 — FLipMouse (asterics)

**GitHub:** https://github.com/asterics/FLipMouse  
**Organisation:** https://www.asterics-foundation.org/projects/the-flipmouse/

### 5.1 Overview

The FLipMouse (Finger- and Lip Mouse) is the most fully-featured open-source alternative input device in this review. Developed and actively maintained by the AsTeRICS Foundation (Austria), it targets users who can apply only very small forces to a mouthpiece using lips, tongue, fingers, or other body parts. It replaces a standard PC mouse, keyboard, and joystick simultaneously, and includes Bluetooth for smartphone/tablet control and infrared for home appliance control.

### 5.2 Hardware

- **MCU (V3):** Arduino Nano RP2040 Connect. The RP2040 (ARM Cortex-M0+) runs the main firmware; an onboard ESP32 handles Bluetooth and WiFi. Single board = two processors.
- **Earlier versions:** FLipMouse V2 used a separate ESP32 add-on module for Bluetooth. V1 used an ATmega32u4.
- **Position sensing:** Four strain gauges (DMS — Dehnungsmessstreifen) arranged to measure X/Y forces on the mouthpiece tip. Extremely low force detection — users who cannot operate a thumb-stick can often operate this.
- **Pressure sensor:** Dedicated sensor for sip/puff detection (separate from the strain gauge array). Exact part varies by version.
- **External switches:** 2× 3.5 mm mono jack inputs for external momentary switches.
- **Infrared:** IR receiver + IR LED on PCB. Can record and replay arbitrary remote control codes — allows TV, AC, and smart-home control.
- **PCB design:** KiCad (open source EDA). Schematic and layout fully published.
- **Configuration storage:** EEPROM module. Up to 5+ named slots, each with independent sensor calibration, action mappings, and speed curves.
- **Configuration interface:** Browser-based WebGUI (connects over USB serial). No display on the device itself.

### 5.3 What It Solved

- **Most comprehensive input coverage:** Mouse, keyboard, joystick, gamepad (6 axes), Bluetooth mouse/keyboard, IR remote — all from one device.
- **Ultra-low force sensing via strain gauges:** Force sensitivity is far below what analog joystick modules achieve. Suitable for users with ALS, high-level SCI, or severe motor impairment.
- **Multiple configuration slots:** Different profiles (e.g., fast cursor, slow cursor, WASD gaming, on-screen keyboard) stored in device memory and switchable by the user in real time.
- **Bluetooth for smartphones/tablets:** Pairs wirelessly. Enables iOS and Android access without a USB OTG adapter.
- **IR environmental control:** Record any IR remote signal; play it back via button press. Replaces a dedicated environmental control unit.
- **Web-based GUI:** Non-technical users and clinicians can adjust all settings via a browser — no firmware reflashing required.
- **Serial command interface:** Full device control via ASCII commands over USB serial — enables software automation, AT framework integration, and scripting.
- **Cross-platform, no drivers:** Presents as standard HID on Windows, macOS, and Linux.
- **Actively maintained:** Regular firmware releases, responsive GitHub issues, community support.

### 5.4 What It Did NOT Solve / Known Limitations

- **No on-device display:** Users cannot adjust settings without a connected PC/Mac running the WebGUI. Significant usability gap for independent use.
- **Strain gauge complexity:** Strain gauges require careful mechanical mounting and calibration. Harder to source and assemble than Hall-effect sensors — not a beginner-friendly build.
- **Higher build complexity overall:** PCB includes many components (strain gauge bridge, instrumentation amplifier, IR circuit, multiple connectors).
- **No on-the-go profile switching feedback:** While config slots exist, switching requires the user to remember a button sequence with no visual feedback on the device.
- **Bluetooth reliability tied to ESP32 firmware:** The separate ESP32 Bluetooth firmware (esp32_mouse_keyboard repo) has its own update cycle. Version mismatch between RP2040 and ESP32 firmware has been a known source of issues.
- **Some documentation is German-only:** Creates a barrier for non-German speakers navigating advanced documentation.

### 5.5 Technical Method & Springboard Value

The FLipMouse demonstrates the full ceiling of what this category of device can do. Its architecture — RP2040 main processor + ESP32 Bluetooth co-processor + strain-gauge position sensing + pressure sip/puff + EEPROM config + WebGUI — is the gold standard.

**For your project:** Borrow the RP2040 + ESP32 dual-processor pattern for Bluetooth. Borrow the serial command interface concept so your device is programmable from software. The gap FLipMouse leaves is an on-device display and a simpler joystick mechanism — add an OLED and use a Hall-effect sensor (lower force, easier assembly) and you outperform FLipMouse on usability.

> **Note:** The FLipMouse WebGUI is open source at https://github.com/asterics/Addon-Bluetooth-WebGUI — worth studying for configuration UX patterns even if you build your own GUI.

---

## 6. Project 4 — LipSync (Makers Making Change)

**GitHub:** https://github.com/makersmakingchange/LipSync  
**Product page:** https://www.makersmakingchange.com/product/lipsync/

### 6.1 Overview

LipSync is the most production-ready open-source mouth-operated joystick in this review. Developed by the Neil Squire Society's Makers Making Change program (Canada) and OSHWA certified (CA000046), LipSync 4.1 is a two-piece device: a Joystick unit (held in the mouth) connected to a Hub unit (sits on the desk or wheelchair tray). The Hub has a graphical display for on-device configuration. It supports USB HID mouse, USB HID gamepad, and Bluetooth mouse modes.

### 6.2 Hardware

- **MCU:** Arduino-compatible platform (Adafruit Feather M0 or similar ARM Cortex-M0 in earlier versions; updated hardware in V4).
- **Joystick sensor:** Adafruit TLV493D 3D Triple-Axis Hall-Effect Magnetometer. A small magnet on the joystick tip moves relative to the sensor. Operating force: ~20 grams (down from ~200 g with original FSR design).
- **Pressure sensors:** Adafruit LPS33HW (water-resistant, I²C) + Adafruit LPS22 for sip and puff respectively. Separate thresholds per action.
- **External switches:** 3× 3.5 mm mono jack inputs on the Hub for external assistive switches.
- **Display:** OLED/LCD on Hub provides graphical settings interface — completely independent of a computer.
- **Bluetooth:** SparkFun Bluetooth Mate Silver (retired 2021). Updated LipSync X under development with new BT hardware.
- **Architecture:** Two-unit split: Joystick (mouth end) contains sensors only; Hub contains MCU, display, connectors, and USB/BT interface.
- **OSHWA:** Certified Open Source Hardware — UID CA000046.
- **Build cost:** $175–$325 per unit depending on quantity. Production runs closer to $175.

### 6.3 What It Solved — Including Lessons from Previous Versions

- **Eliminated cursor drift:** Original LipSync V1–V2 used Force-Sensing Resistors (FSRs) for joystick position. FSRs drifted with temperature, moisture, and age. Replacing them with the TLV493D Hall-effect magnetometer eliminated drift entirely.
- **Ultra-low operating force:** Hall-effect joystick requires only ~20 g force vs. ~200 g for the FSR design. Opens the device to users with very limited lip or tongue strength.
- **Separate sip and puff thresholds:** Earlier versions used one threshold for both. LipSync 4+ allows individual calibration, accommodating users who sip strongly but puff weakly (or vice versa).
- **On-device configuration via Hub display:** Users and clinicians can adjust cursor speed, sip/puff thresholds, and mode settings directly on the Hub without a computer.
- **Three external switch inputs:** More switch inputs than any other reviewed project — important for AAC device integration or scanning navigation.
- **USB HID gamepad mode:** Enables gaming and game-based therapy programs.
- **Modular Joystick+Hub design:** The two-piece approach keeps the mouth-end small and light while moving electronics and connectors to the Hub. Replacement of the Joystick unit (wear item) is inexpensive.
- **Water-resistant pressure sensor (LPS33HW):** Reduces failure from moisture contamination.
- **OSHWA certification and full documentation:** Build manuals, BOM, PCB files, and firmware all published. Volunteer maker network actively builds and distributes units.

### 6.4 What It Did NOT Solve / Known Limitations

- **Bluetooth hardware is retired:** The SparkFun Bluetooth Mate Silver module was discontinued in 2021. The current LipSync 4.1 does not have a supported Bluetooth solution; LipSync X is in development.
- **Cost remains high for individual builders:** $175–$325 is still a significant barrier compared to The 'Sup's $50. Cost comes largely from the custom PCB, OLED Hub, and Adafruit sensors.
- **Two separate units require cable management:** The joystick-to-hub cable can be a nuisance in day-to-day use, especially on a power wheelchair.
- **No infrared environmental control:** Unlike FLipMouse, LipSync has no IR capability.
- **Complex build process:** Requires soldering a custom PCB, 3D printing, and firmware flashing. Not accessible to all makers.
- **No serial command interface:** Device cannot be fully controlled programmatically from software (unlike FLipMouse's ASCII serial interface).

### 6.5 Technical Method & Springboard Value

LipSync is the most user-centred design: every hardware decision traces back to a specific user need revealed by testing with real users across multiple version iterations. The TLV493D + LPS33HW sensor pairing is a proven, I²C-native stack that eliminates the two biggest failure modes (drift and moisture damage).

**For your project:** Adopt the TLV493D + LPS33HW sensor stack. Add the Hub display concept but consider integrating Hub and joystick into one unit to eliminate the cable. The Bluetooth gap is your clearest opportunity — solve it cleanly and your device surpasses LipSync on connectivity.

> **Note:** Makers Making Change also has spin-off repos: LipSync-Gaming (gamepad firmware), LipSync-Macro, LipLoft (drone control). These demonstrate the extensibility of the core platform.

---

## 7. Cross-Project Patterns and Lessons

### 7.1 Hardware Convergence

All four projects converge on the ATmega32u4 / Arduino Pro Micro / RP2040 lineage for USB HID — this is effectively settled technology. The critical hardware evolution across projects has been in the joystick sensor:

**Analog potentiometer → FSR → Strain gauge → Hall-effect magnetometer**

Hall-effect (TLV493D) wins on every axis: lowest force, no mechanical wear, no drift, no moisture sensitivity.

### 7.2 The Hygiene Problem Is Universally Acknowledged, Rarely Solved

Every project that includes a mouthpiece mentions saliva and breath moisture as a risk. Only LipSync and FLipMouse address it with a water-resistant pressure sensor (LPS33HW) and/or filter provisions. This is a clinical must-have for any device intended for prolonged daily use — and it differentiates medical-grade from hobby builds.

### 7.3 Configuration UX Is the Biggest Unsolved UX Problem

openSipPuff and The 'Sup require firmware reflashing for any threshold change. FLipMouse requires a connected PC and WebGUI. Only LipSync 4+ offers truly independent on-device configuration via the Hub display. **There is no project in this set that combines on-device configuration with Bluetooth AND stays under $150.**

### 7.4 Bluetooth Is an Active Gap

openSipPuff and The 'Sup have no Bluetooth. FLipMouse has Bluetooth but via an ESP32 co-processor that needs its own firmware. LipSync's Bluetooth module is retired. For any new project targeting smartphone/tablet users (the majority of power wheelchair users today), robust Bluetooth is non-negotiable.

### 7.5 Separate Sip and Puff Thresholds Are Non-Negotiable

This is a lesson learned the hard way by LipSync. Having a single pressure threshold for both sip and puff excludes users who cannot sip and puff with equal force. Separate, independently calibrated thresholds are a must-have from day one.

### 7.6 Configuration Requires a Computer or a Developer — Always

Every reviewed project locks its behaviour into firmware. Changing what the device does — even something as simple as adjusting a sip threshold — requires either reflashing (openSipPuff, The 'Sup), running a PC application (FLipMouse WebGUI), or a separate dedicated Hub unit (LipSync). There is no project in the reviewed set where a non-technical caregiver or user can independently reconfigure the device using only the device itself and a text editor. This represents a meaningful accessibility barrier within the field of assistive technology: the tool meant to grant independence requires a technical intermediary to configure.

Text file configuration — device as USB mass storage, config as a plain readable/editable file — is a well-established pattern in the CircuitPython ecosystem and in some commercial AT devices, but it has not been applied to open-source sip and puff devices. It is the primary design goal of this project and is documented as Gap 7 in Section 8.

### 7.7 ESD / Circuit Protection Is Almost Universally Absent

None of the four reviewed projects include explicit ESD or transient overvoltage protection on their external I/O lines. This is one of the most common omissions in open-source hardware — including assistive technology projects — and it matters more here than in typical hobby builds because:

- Devices are handled repeatedly by users with limited motor control, increasing connector plug/unplug cycles and the chance of accidental contact with charged surfaces
- Clinical and institutional environments often have different grounding characteristics than a maker's bench
- A latent GPIO damage event may present as intermittent behavior that is very difficult to diagnose in the field

TVS diode arrays (e.g., SP724AHTG) cost under $0.50 per IC and can protect multiple signal lines simultaneously with negligible impact on signal integrity. The barrier to inclusion is awareness, not cost or complexity. This project explicitly addresses the gap — see Section 10.6.

### 7.7 Cost vs. Completeness Trade-off

There is a near-perfect inverse correlation between cost and completeness across these projects:

| Project | Cost | Completeness |
|---|---|---|
| The 'Sup | < $50 | Minimal viable |
| openSipPuff | $60–100 | Breath-only proof of concept |
| FLipMouse | ~$100–150 | Full-featured, complex build |
| LipSync | $175–325 | Most complete clinically |

The sweet spot your project can own is **~$100–$150 with Bluetooth, an on-device display, Hall-effect joystick, and hygiene filter.**

---

## 8. Springboard: Gaps to Exploit in Your Project

Based on the analysis above, the following gaps represent the clearest opportunities for your project to advance the state of the art:

### Gap 1: Reliable, Modern Bluetooth (Critical)

Use the RP2040 + ESP32-C3 or nRF52840. The RP2040 handles USB HID; the nRF52840 provides BLE HID natively without a separate co-processor firmware update cycle. **Adafruit Feather nRF52840 Express** is a proven, single-board solution that supports both USB and BLE HID simultaneously.

### Gap 2: Hall-Effect Joystick (Proven Path)

Use the **TLV493D** (LipSync's choice) or MLX90393. Both are I²C, 3D, and available on Adafruit breakout boards. Target < 20 g activation force. The FLipMouse's strain gauge approach achieves lower force but is harder to build — Hall-effect is the better DIY / small-production trade-off.

### Gap 3: On-Device Display + Independent Configuration (UX Differentiator) ✅ Hardware Addressed

A small **SSD1306 OLED (128×64, I²C)** on the device itself — not a separate Hub unit — would allow the user to see current mode, adjust thresholds, and switch profiles without a computer. **No existing project achieves this in a single integrated unit.**

> **Status — April 2026:** PCB now includes built-in hardware support for both display options with no board redesign required (see Section 10.5):
> - **J1:** 4-pin Dupont header — 1" 128×64 I²C OLED (SSD1306), shares GPIO 4/5 bus with pressure sensor.
> - **J2:** 9-pin Dupont header — 2–4" SPI color LCD (ST7789/ILI9341) on dedicated SPI1 hardware (GPIO 10–16) with backlight PWM.
> Display software (rendering, threshold bar graph, mode indicator, config UI) remains to be implemented.

### Gap 4: Water-Resistant Pressure Sensor + Hygiene Filter Housing ✅ Sensor Addressed / Filter Designed

Use the **LPS33HW** (water-resistant, I²C, Adafruit breakout). Design a 3D-printed filter housing with a standard HME (Heat-Moisture Exchanger) filter or a simple in-line hydrophobic PTFE filter. This is a clinical requirement that every project acknowledges but only partially addresses.

> **Status — April 2026:** Sensor gap closed — **LPS28DFWTR** (STMicroelectronics, CCLGA-7L SMD, I²C, 24-bit, 0.32 Pa noise, 10 ATM water-resistant potting gel) selected as the default pressure sensor; MPX5010DP retained as through-hole alternative on dual-footprint PCBs. Filter strategy designed as a two-stage inline stack (see Section 10.1 and Section 10.4).

### Gap 5: Separate Sip/Puff Thresholds with Visual Feedback

Implement two independent pressure thresholds stored in non-volatile memory. Show a **real-time pressure bar graph on the OLED** during calibration mode so the user or clinician can set thresholds visually. LipSync does this on the Hub display — bring it into the main unit.

### Gap 6: Serial Command Interface for Integration

Implement an ASCII serial command protocol (like FLipMouse's) over USB CDC. This allows your device to be controlled by AAC software, switch access software, or scripts. It also enables over-the-air configuration without a custom app.

### Gap 7: Text File Reconfigurability — One Build, Many Purposes ⭐ Primary Design Goal

Every project reviewed requires firmware reflashing or a connected PC application to change what the device does. openSipPuff and The 'Sup require code edits and a recompile. FLipMouse requires the WebGUI on a tethered PC. LipSync's Hub display allows threshold adjustment but not mode switching or output remapping. **No project offers configuration that a non-technical caregiver, clinician, or user can perform independently without software tools.**

This project's primary differentiator is that **the device exposes a plain text configuration file over USB mass storage**. Plugging the device into any computer shows it as a USB drive; editing the config file and unplugging is all that is needed to:
- Remap sip and puff events to any HID output (keypress, mouse button, joystick axis, consumer control)
- Switch operating modes (USB mouse, USB keyboard, XAC gamepad, serial AT relay, Maker faire demo)
- Adjust sensitivity thresholds for each breath direction independently
- Configure head-tracking parameters (dead zone, speed curve, re-centre gesture)
- Change display content and feedback behaviour

The same physical hardware — with no firmware change — can serve as a two-switch keyboard, a USB mouse, an XAC gamepad input, a demonstration toy, or a research data logger. This is the design decision that drives the choice of display hardware, the EXTERNAL_IO connector, the STEMMA QT expansion port, and the overall software architecture. No other reviewed project comes close to this capability.

### Gap 8: Cost Target of < $150 for a Complete Solution

Use a single-board MCU with native USB + BLE (nRF52840), Hall-effect joystick, LPS33HW pressure sensor, SSD1306 OLED, and 3× 3.5 mm switch jacks. BOM should land at **$80–$120 in single-unit quantities** — well below LipSync's $175–$325 while exceeding it on Bluetooth and display integration.

### Gap 9: Medical Certification Pathway — Redundant Sensor + Safety CPU

None of the reviewed projects address medical device certification. All four are maker/open-source builds intended for personal or research use. A device used daily by someone with ALS, high-level SCI, or advanced MS is in practice a primary communication and environmental control interface — a failure is not merely inconvenient. Formal certification (FDA Class II, CE marking under MDR, IEC 62304 software lifecycle) would require hardware and software changes beyond the current design, but it is worth noting the architectural direction a certified variant would take:

- **Redundant pressure sensor:** A second LPS28DFWTR on the same I²C bus (at the alternate address 0x5D) cross-checks the primary (0x5C). Significant discrepancy between the two readings flags a sensor fault and triggers a safe-state response rather than silently producing erroneous output.
- **Safety CPU / supervisory MCU:** A second microcontroller — either a dedicated safety MCU (e.g. TI TMS570 series, Renesas RH850) or a simpler supervisory MCU (e.g. STM32 with hardware watchdog) — independently monitors the primary RP2040. If the primary fails to service the watchdog within the required interval, the safety CPU halts outputs and alerts the user or caregiver.
- **Firmware scope:** IEC 62304 Class B or C software lifecycle processes — formal requirements tracing, hazard analysis (ISO 14971), unit testing with coverage targets, change control. This is a significant undertaking and is not planned for the current open-source prototype.

The current design does not preclude this path. The dual I²C address support on the LPS28DFWTR (SA0 solder bridge) means a second sensor can be added to the existing PCB without layout changes. The STEMMA QT and EXTERNAL_IO connectors provide expansion points. A future PCB revision could add a small supervisory MCU in a QFN package alongside the Pico W without changing the overall form factor significantly.

> **Current status:** Not planned. Noted here as the intended architectural direction for any future medically certified variant, and to ensure design decisions made now do not close off that path unnecessarily.

---

## 9. Reference Links

### Primary GitHub Repositories

| Project | URL |
|---|---|
| openSipPuff (jasonwebb) | https://github.com/jasonwebb/openSipPuff |
| SipNPuff_Mouse / The 'Sup (Bobcatmodder) | https://github.com/Bobcatmodder/SipNPuff_Mouse |
| FLipMouse (asterics) | https://github.com/asterics/FLipMouse |
| FLipMouse V2 (asterics) | https://github.com/asterics/FLipMouse-v2 |
| LipSync (Makers Making Change) | https://github.com/makersmakingchange/LipSync |
| LipSync Classic | https://github.com/makersmakingchange/LipSync-Classic |
| LipSync Gaming | https://github.com/makersmakingchange/LipSync-Gaming |
| LipSync Wireless | https://github.com/makersmakingchange/LipSync-Wireless |
| esp32_mouse_keyboard (asterics BLE) | https://github.com/asterics/esp32_mouse_keyboard |
| FLipPad (related asterics project) | https://github.com/asterics/FLipPad |
| FLipMouse WebGUI | https://github.com/asterics/Addon-Bluetooth-WebGUI |

### Supplemental Resources

| Resource | URL |
|---|---|
| The 'Sup — Instructables Build Guide | https://www.instructables.com/The-Sup-a-Mouse-for-Quadriplegics-Low-Cost-and-Ope/ |
| FLipMouse User Manual (asterics.eu) | https://www.asterics.eu/manuals/flipmouse/ |
| FLipMouse — AsTeRICS Foundation | https://www.asterics-foundation.org/projects/the-flipmouse/ |
| LipSync — Makers Making Change Product Page | https://www.makersmakingchange.com/product/lipsync/ |
| openSip+Puff — Jason Webb Blog (Rev B) | https://www.jasonwebb.io/2013/08/opensippuff-rev-b-prototype-boards-built-and-tested/ |
| Hackaday — The 'Sup feature article | https://hackaday.com/2018/04/27/an-open-source-sip-and-puff-mouse-for-affordable-accessibility/ |
| LipSync — 5 Years Retrospective (MMC) | https://makersmakingchange.com/happy-pi-day-a-look-at-five-years-of-lipsync-builds-and-the-future-of-the-lipsync/ |
| MPXV7007GP Datasheet (NXP) | https://www.nxp.com/docs/en/data-sheet/MPXV7007.pdf |
| Adafruit LPS33HW + CircuitPython Sip & Puff Tutorial | https://learn.adafruit.com/st-lps33-and-circuitpython-sip-and-puff/overview |

### Peer-Reviewed Scholarly Articles

*The following references are academic papers subject to peer review. They carry greater methodological rigour than project READMEs and should be weighted accordingly when making design decisions.*

| # | Citation | DOI / URL |
|---|---|---|
| [S1] | Duarte, R.; Lopes, N.V.; Coelho, P.J. "A Low-Cost Head-Controlled and Sip-and-Puff Mouse: System Design and Preliminary Findings." *Electronics* (MDPI) 2025, 14(24), 4953. | https://doi.org/10.3390/electronics14244953 · [Full text](https://www.mdpi.com/2079-9292/14/24/4953) |

---

## 10. Lessons Learned and To Be Implemented

*This section is a living scratchpad — updated as decisions are made and new information comes in. It captures what the prior-art review taught us and translates it directly into implementation choices for this project.*

---

### 10.1 Breath Hygiene Filtering

Every reviewed project acknowledged the saliva/moisture problem; few solved it well. This section documents the filter options evaluated and the chosen path forward.

#### Option A — AT-Specific Sip/Puff Anti-Contamination Filters
Purpose-built for sip/puff systems. Drop-in fit, no adapter needed.

| Attribute | Detail |
|---|---|
| Filter media | 0.2µm PTFE hydrophobic membrane |
| Tubing fit | Native 1/8" ID barb — direct fit to standard sip/puff tubing |
| Filtration | 99.9% bacteria & virus, blocks moisture and saliva |
| Replacement interval | Every 3–6 months (light use), or when resistance noticeably increases |
| Pack sizes | 6-pack and 20-pack |
| Pros | Perfect fit, purpose-made, no adapter, proven in the field |
| Cons | Sold through AT suppliers only — no open datasheet, risk of discontinuation |
| Where to buy | [Amazon 6-pack](https://www.amazon.com/Sip-Puff-Switches-Accessories-Contaminator/dp/B007GBBXZW) · [Enabling Devices](https://enablingdevices.com/product/anti-contamination-filters/) · [Inclusive Inc kit](https://inclusiveinc.org/products/sip-n-puff-tubing-kit) |

#### Option B — Foxx Life Sciences EZFlow PTFE Vent Filters ⭐ Recommended
Lab/biotech grade, fully open spec, widely available, cheap in bulk. Best choice for a documented open-source build.

| Attribute | Detail |
|---|---|
| Filter media | 0.22µm hydrophobic PTFE membrane |
| Barb size | 1/4"–1/2" stepped barb (requires short 3D-printed 1/4"→1/8" adapter collar) |
| Flow rate | ≥ 2.0 L/min @ 10 kPa — well within human breath range |
| Autoclavable | Yes, up to 60°C |
| Pack sizes | 2-pack, 5-pack, 25-pack |
| Pros | Open spec, fully documented, autoclavable, reproducible BOM, cheap in quantity |
| Cons | Needs a simple 3D-printed adapter to step down to 1/8" sip/puff tubing |
| Where to buy | [Amazon 2-pack (0.22µm, 1/4" barb)](https://www.amazon.com/Hydrophobic-Filters-Containers-Silicone-Non-Sterile/dp/B00HSDTDK0) · [Foxx Life Sciences direct](https://www.foxxlifesciences.com/products/ezbio-hp-vent-filter-0-22-m-hydrophobic-ptfe-50mm-1-4-1-2-stepped-barb-5-cs) |

#### Option C — Industrial Miniature Inline Filters (Air Logic / ITW Fastex)
Cheap pneumatic filters with native 1/8" barbs. Good as a first-stage saliva trap only.

| Attribute | Detail |
|---|---|
| Filter media | Polypropylene mesh |
| Pore sizes available | 10µm–150µm |
| Barb size | Native 1/8" — perfect fit, no adapter |
| Price | Cents each in quantity |
| Pros | Cheapest option, perfect tubing fit, catches bulk liquid and particulates |
| Cons | Does NOT filter bacteria (0.2–1µm) or viruses — not sufficient alone for a hygienically shared device |
| Best use | Pre-filter upstream of Option A or B to extend membrane filter life |
| Where to buy | [Air Logic barbed filters](https://air-logic.com/viewitems/filters/barbed-inline-filters) · [Industrial Spec 10µm](https://www.industrialspec.com/shop/filters/itw-fastex-filtration/small-plastic-inline-filters/85160-00-110.html) |

#### Option D — HME Tracheostomy Filters (Thermovent T, Intersurgical, Passy Muir)
Medical-grade heat-and-moisture exchangers. Correct filtration spec but wrong connector for this application.

| Attribute | Detail |
|---|---|
| Connector | 15mm ISO tracheostomy standard — much larger than sip/puff tubing |
| Filtration | Bacterial + viral + humidity exchange |
| Replacement | Single use, every 24 hours |
| Cost per unit | ~$3–8 |
| Pros | Gold-standard medical filtration, widely available through medical suppliers |
| Cons | Requires custom 3D-printed 15mm→1/8" adapter housing; daily replacement cost adds up |
| Best use | Only if warmth/humidity retention is clinically required (trach patients); overkill for standard sip/puff |
| Where to buy | [Thermovent T (ICU Medical)](https://www.icumed.com/products/airway-management/respiratory/filtration-and-humidification/thermovent-t-heat-and-moisture-exchanger-hme-with-15-mm-female-connector/) · [Intersurgical Hydro-Trach](https://www.intersurgical.com/products/airway-management/hydrotrach-t-range) · [Passy-Muir HME](https://www.passy-muir.com/pm-hme/) |

#### Recommended Implementation Strategy

Use a **two-stage inline filter stack** in the breath tube between the mouthpiece and pressure sensor:

1. **Stage 1 (upstream):** Option C industrial polypropylene mesh filter (10µm, 1/8" barb) — catches saliva droplets and bulk moisture, protects Stage 2.
2. **Stage 2 (downstream):** Option B Foxx EZFlow 0.22µm PTFE filter via 3D-printed adapter — provides true bacterial/viral filtration, keeps the sensor dry.

Option A (AT-specific filters) is a valid drop-in alternative for users who prefer a single off-the-shelf part and don't need an open BOM.

> **Design note:** The 3D-printed filter housing/adapter for Stage 2 should be designed for tool-free filter swap — a twist-lock or press-fit cap so clinicians and users can replace it without tools.

---

### 10.2 Wireless Connectivity — Bluetooth Implementation

#### Hardware Decision
Use the **Raspberry Pi Pico W** or **Raspberry Pi Pico 2 W** as the primary microcontroller. Both include onboard CYW43439 Wi-Fi/Bluetooth (Classic + BLE) via the Infineon chip, eliminating the need for a separate Bluetooth module or co-processor.

| | Pico W | Pico 2 W |
|---|---|---|
| MCU | RP2040 (dual Cortex-M0+, 133 MHz) | RP2350 (dual Cortex-M33, 150 MHz) |
| RAM | 264 KB | 520 KB |
| Flash | 2 MB | 4 MB |
| Bluetooth | BLE + Classic (CYW43439) | BLE + Classic (CYW43439) |
| USB | Native USB HID | Native USB HID |
| Price | ~$6 | ~$7 |
| Availability | Widely available (Adafruit, Pimoroni, DigiKey, Mouser) | Widely available |
| Recommendation | Good starting point | **Preferred** — more headroom for display, config, sensor polling |

#### Software Requirements
*To be refined as implementation progresses.*

- **USB HID mouse** — straightforward; well-supported in MicroPython (`usb-hid` library) and C/C++ SDK. This is the first milestone.
- **Bluetooth HID mouse** — BLE HID profile; supported via the Pico SDK's BTstack integration. Requires pairing flow and profile management. To be designed.
- **USB HID gamepad** — secondary mode; similar complexity to mouse. To be designed.
- **Serial command interface** — ASCII protocol over USB CDC for programmatic control and configuration (following FLipMouse's approach). To be designed.
- **On-device configuration** — settings stored in flash (not EEPROM); read/write via MicroPython or C SDK. To be designed.

#### Sip/Puff Input — Tentative Implementation: Rotary Encoder Mapping

*Tentative — subject to revision after sensor and threshold testing.*

The current thinking is to map processed sip/puff pressure readings to **rotary encoder-style events** in the HID layer:

- A sustained **puff** above threshold → emits scroll-up encoder ticks (or right-click, depending on mode)
- A sustained **sip** above threshold → emits scroll-down encoder ticks (or left-click, depending on mode)
- Pressure magnitude → tick rate (light breath = slow scroll, hard breath = fast scroll)

This approach maps naturally to the USB HID Consumer Control or relative axis model without needing custom drivers on the host. It is analogous to how some commercial AAC devices encode breath as a counted input rather than a held state, which avoids the "stuck key" failure mode if the breath signal is lost mid-action.

> **To be refined:** Threshold values, tick rate curves, debounce timing, and the mapping between pressure magnitude and output rate all need empirical testing with the actual sensor and real users.

---

### 10.3 Joystick / Cursor Movement — IMU-Based Head Tracking

> **Implementation timeline:** This section is planned as a **post-Maker-Faire upgrade** once the core sip/puff functionality has been validated in real-world demonstration. Mouse functionality is the first software milestone (straightforward). IMU head-tracking will follow as Phase 2. No hardware changes to the PCB are required to begin — the BNO055 connects to the shared I²C bus (GPIO 4/5) via the STEMMA QT port.

#### Background

The prior-art review identified a clear evolution in joystick sensing: analog potentiometer → force-sensing resistor → strain gauge → Hall-effect magnetometer. All four approaches share a common limitation — they are **contact-force** sensors, requiring the user to physically deflect a stick with their lips, tongue, or teeth. This is appropriate for many users, but for users with very limited oral motor control (high-level SCI, ALS, advanced MS) even a 20 g Hall-effect stick may be too demanding.

A peer-reviewed 2025 study [S1] demonstrates a compelling alternative: **head movement tracked via IMU**, combined with sip/puff for clicks. This decouples cursor movement entirely from mouth mechanics and relocates it to head orientation — a control site with much larger range of motion and lower fatigue.

#### Scholarly Reference

> **[S1]** Duarte, R.; Lopes, N.V.; Coelho, P.J. "A Low-Cost Head-Controlled and Sip-and-Puff Mouse: System Design and Preliminary Findings." *Electronics* (MDPI) 2025, 14(24), 4953.
> DOI: [10.3390/electronics14244953](https://doi.org/10.3390/electronics14244953) · [Full text](https://www.mdpi.com/2079-9292/14/24/4953)
>
> *Peer-reviewed open-access article. Evaluated by occupational therapy professionals. Published December 2025.*

#### What [S1] Did

| Element | Detail |
|---|---|
| **MCU** | ESP32-S3 — native BLE HID + USB OTG, no co-processor needed |
| **IMU** | MPU6050 — 6 DOF (3-axis accelerometer + 3-axis gyroscope), I²C |
| **IMU sample rate** | 100 Hz |
| **Orientation algorithm** | Complementary filter — fuses accelerometer (low-freq) and gyroscope (high-freq) data to produce stable pitch/roll angles with reduced jitter |
| **Pressure sensor** | LPS33HW (same water-resistant I²C sensor family used in LipSync 4+) |
| **Click mapping** | Sip and puff gestures detected by threshold crossing → left/right click |
| **Cursor mapping** | Head pitch/roll → relative mouse X/Y movement |
| **Connectivity** | BLE HID mouse (wireless to any paired host) |
| **Validation** | Preliminary testing with occupational therapy professionals; usability rated comparable to commercial devices |
| **Limitations noted** | Preliminary only — no controlled user study with individuals who have actual motor impairments yet |

#### IMU Sensor Evaluation

Four candidates were evaluated for this use case. All support I²C and 3.3V logic:

| Sensor | DOF | Typical Price | Interface | Unique Characteristic | Head-Tracking Suitability |
|---|---|---|---|---|---|
| **MPU-6050** | 6 | ~$3–5 | I²C | Massive community support; some breakouts have 5V pull-ups (verify) | Viable; needs software complementary/Kalman filter; yaw drifts |
| **BMI270** | 6 | ~$6–8 | I²C / SPI | Ultra-low power (685 µA); built-in gesture recognition | Good for battery builds; same yaw drift limitation as MPU-6050 |
| **LSM6DSOX** | 6 | ~$8–12 | I²C / SPI | Embedded Machine Learning Core; high stability, low noise | Strong option; still needs software AHRS; yaw drift without magnetometer |
| **BNO055** ⭐ | 9 | ~$30–35 | I²C | **On-board sensor fusion processor**; outputs clean Euler angles (heading, roll, pitch) and quaternions; built-in magnetometer eliminates yaw drift; automatic background calibration | **Selected — see decision below** |

**Key distinction for head-tracking:** The 6-DOF sensors (MPU-6050, BMI270, LSM6DSOX) all require a software sensor-fusion algorithm (Madgwick, Mahony, or Kalman filter) running on the microcontroller to produce stable orientation. Without a magnetometer (9th DOF), yaw (left/right heading) will drift over time, requiring the user to periodically trigger a re-centre action. For a head mouse used over hours, this is a real usability burden. The BNO055's internal fusion processor and magnetometer eliminate both of these issues entirely at the cost of ~$25 over a basic IMU.

#### Sensor Decision: BNO055 ✅

**The BNO055 is selected as the target IMU for this project.**

The $30–35 cost is acceptable in context. Replacement hygiene filters (Section 10.1) are a recurring consumable cost; the IMU is a one-time addition. The BNO055's built-in sensor fusion and absolute orientation output significantly reduce firmware complexity and eliminate the yaw drift problem without any code-level workaround. For an assistive technology device intended for prolonged daily use, removing a source of user frustration (the re-centre requirement) is worth the cost delta over a bare 6-DOF IMU.

**Connection:** STEMMA QT / Qwiic connector on the main PCB → flexible I²C cable routed along the tube → BNO055 breakout at end-user-chosen placement location (see mounting section below).

#### Mounting Strategy — I²C Along the Tube

The BNO055 is **not mounted on the main PCB**. It is a remote sensor connected via I²C wires routed along the sip/puff tube to wherever the end user (or clinician/therapist fitting the device) finds it most effective. Two primary mounting modes are planned, each using identical hardware but configured differently via the text config file:

---

##### Mode A — Head Strap / Glasses Mount

The sensor is attached to the user's head and tracks head orientation. Cursor movement is driven by head nods (pitch → Y) and head turns or tilts (roll → X).

Suitable mounting locations:
- **Glasses frame** — near the temple, oriented to catch pitch and roll of head nod/tilt
- **Forehead strap** — central placement for symmetric pitch/roll response
- **Ear clip or headband** — low-profile behind the ear

**Movement scale:** Large — typical head movements span 15–45° for comfortable cursor travel. Dead zone of ±2–3° around neutral to suppress tremor. Moderate sensitivity setting in config.

**Calibration:** User sits in neutral head position; long sip gesture sets the zero point. The BNO055 magnetometer prevents yaw drift over long sessions.

**Best for:** Users with good head mobility but limited oral/limb motor control (high-level SCI, ALS, advanced MS).

---

##### Mode B — Straw / Tongue Joystick Mount

The sensor is attached to the sip/puff tube near the mouthpiece, so that **tongue movement deflects the tube and the BNO055 detects that angular change**. The straw itself becomes the joystick lever — pushed left, right, up, or down by the tongue.

**Mounting:** A small 3D-printed clip or collar attaches the BNO055 breakout to the tube a short distance from the mouthpiece tip. The clip holds the sensor flush against the tube so tube deflection translates directly into angular change. The I²C wires run back along the tube to the main PCB's STEMMA QT connector, same as in Mode A.

**Movement scale:** Small — tongue deflections of a few degrees translate to meaningful stick input. High sensitivity setting and tight dead zone required in config. The straw's natural resting position when held loosely in the mouth defines the centre point.

**Axis orientation:** The sensor's pitch and roll axes need to be re-mapped in config relative to how the clip is oriented on the tube (tube is horizontal, not vertical like a head-mounted unit). This is a config file parameter, not a firmware change.

**Best for:** Users with good tongue or lip control but limited head movement — a different motor profile than Mode A. Also useful as a lower-fatigue alternative for users who can do both, since tongue control requires no neck muscle effort.

**Relationship to FLipMouse:** The FLipMouse uses strain gauges on a mouthpiece stick to achieve a similar input concept. This implementation replaces the strain gauge assembly with a single BNO055 breakout clipped to the tube — simpler to build, easier to 3D print the collar, same functional result.

**Reducing required activation force:** Because the BNO055 detects angular deflection of the tube rather than measuring physical force directly, the amount of tongue effort needed to produce a usable input signal can be reduced through two complementary approaches:

- **Mechanical:** The collar position along the tube acts as a lever. Placing the sensor closer to the mouthpiece tip shortens the lever arm and requires more deflection for the same angular change; placing it further back lengthens the lever arm, meaning a smaller tongue push produces a larger angular signal at the sensor. Tube material also matters — a softer, more flexible tube deflects more easily under the same tongue force than rigid tubing, lowering the effort threshold. These are physical design choices made when printing and assembling the collar.

- **Software:** Sensitivity and dead zone parameters in the config file can be tuned so that very small angular changes (minimal force) register as valid input. Increasing sensitivity means a lighter touch moves the cursor; the dead zone prevents that sensitivity from making the cursor jittery at rest. Together, a properly tuned collar geometry and config file can bring the effective activation force down to a level accessible to users with very limited tongue or lip strength.

This is a meaningful advantage over strain-gauge implementations like FLipMouse, where the activation force is largely fixed by the physical spring constant of the stick mechanism and requires hardware modification to change. Here, the clinician or user can adjust force requirements through a combination of collar placement and a text file edit.

> **The two modes use identical hardware.** Switching between head-strap tracking and tongue-joystick mode is purely a matter of physically repositioning the sensor clip and updating three parameters in the text config file (sensitivity, dead zone, axis orientation). No firmware change, no reflashing.

---

The I²C bus runs at 400 kHz standard mode. At typical tube lengths (up to ~1 m) with 10 kΩ pull-ups already present on the PCB, signal integrity is adequate without additional buffering. If longer runs are needed, a PCA9517 I²C buffer can be added inline.

The BNO055 breakout (Adafruit #4646 or equivalent STEMMA QT format) connects via JST-SH to the STEMMA QT port on the main PCB. Use flexible silicone-coated wire along the tube in both modes — stiff wire creates mechanical noise in the sensor data and is uncomfortable for head-mounted use.

> **End-user flexibility is intentional.** Different users have different residual movement profiles. A clinician fitting the device should be able to switch modes, reposition the sensor, and re-run calibration without opening the enclosure or touching the PCB.

#### Implementation Notes

**Jitter and tremor suppression:** The BNO055's internal fusion already smooths much of this, but a software dead zone and non-linear speed curve should still be applied in both modes. The dead zone and sensitivity values differ significantly between modes and are exposed as config file parameters.

**Calibration:** The BNO055 calibrates automatically in the background. On first power-up a brief routine is recommended — slow figure-8 motion for the magnetometer, tilting in each axis for the accelerometer. Calibration state can be read via I²C and displayed on the OLED (J1). For tongue-joystick mode, the calibration motion is simply moving the straw through its range rather than moving the head.

**Weight and comfort:** The BNO055 in STEMMA QT breakout format (Adafruit #4646) weighs approximately 1.8 g. For head-mounted use, insulate the back of the PCB (Kapton tape or 3D-printed cover) to prevent skin contact and protect against perspiration. For tube-mount use, the 3D-printed collar provides natural insulation.

**Firmware approach (common to both modes):**
1. Poll BNO055 at 100 Hz via I²C — read Euler angles directly from fusion output registers
2. Apply dead zone: discard movement below ±N degrees from calibrated centre (N from config)
3. Map axis A → mouse X; axis B → mouse Y (axis assignment from config — allows Mode A and Mode B to use different physical orientations)
4. Apply sensitivity scaling and non-linear speed curve (parameters from config)
5. Sip/puff threshold crossings from LPS28DFWTR → left/right click events
6. Long sip gesture → re-centre (reset zero point to current orientation)

> **Three-way hybrid mode (future stretch goal):** Head-tracking (Mode A), tongue-joystick (Mode B), and Hall-effect mouthpiece stick as three user-selectable input modes on the same hardware, switchable via config file or long-gesture. No existing reviewed project offers even two of these three options.

> **To be refined:** Dead-zone size, speed curve shape, tongue-joystick collar geometry, and axis orientation for tube-mount all need empirical testing. The [S1] paper provides a useful baseline for head-tracking parameters; tongue-joystick parameters will need independent user testing.

---

### 10.4 Pressure Sensor Selection — LPS28DFWTR as Default

#### Decision Summary

After initial prototyping began with the MPX5010DP (through-hole, analog), the sensor selection was revisited against the project's core requirements: water resistance, digital interface (reduces ADC noise floor), low power, and PCB miniaturisation. The **LPS28DFWTR** (STMicroelectronics DS13317) was selected as the new default.

#### Sensor Comparison

| Attribute | LPS28DFWTR ⭐ Default | MPX5010DP (Alternative) |
|---|---|---|
| **Package** | CCLGA-7L SMD (2.8 × 2.8 × 1.95 mm) | Through-hole SIP-6 |
| **Soldering** | SMD — requires reflow or hot-air | Hand-solderable |
| **Interface** | I²C (400 kHz / 1 MHz fast mode) | Analog voltage → ADC pin |
| **Resolution** | 24-bit | 12-bit (Pico W ADC) |
| **Noise** | 0.32 Pa RMS | ~±1.5% FS (~150 Pa) |
| **Water resistance** | Potting gel, rated 10 ATM | None |
| **Idle current** | 1.7 µA (AVG=4, ODR=1 Hz) | ~6 mA typical |
| **Factory calibrated** | Yes | No |
| **Pressure range** | 260–1260 hPa (Mode 1); 260–4060 hPa (Mode 2) | 0–10 kPa differential |
| **Supply** | 1.7–3.6 V (3.3V nominal) | 2.7–5.5 V (rated 5V; scales at 3.3V) |
| **I²C address** | 0x5C (SA0=GND) or 0x5D (SA0=VDD) | N/A — analog only |
| **Datasheet** | DS13317 Rev 1, December 2021 | NXP MPX5010 series |
| **Cost (single unit)** | ~$4–6 | ~$3–5 |

#### PCB Strategy

Initial PCBs include footprints for **both sensors simultaneously** — only one is populated at build time. After real-world testing determines which sensor performs best for the sip/puff application, separate PCB variants will be spun:
- **PCB Rev A (SMD):** LPS28DFWTR only
- **PCB Rev B (Through-hole):** MPX5010DP only — lower cost, no SMD tools required, suitable for hands-on educational/maker builds

#### Wiring — LPS28DFWTR (Default)

| Signal | GPIO | Notes |
|---|---|---|
| SDA | GPIO 4 | I²C0 SDA — shared bus with OLED (J1) and future IMU |
| SCL | GPIO 5 | I²C0 SCL — shared bus |
| INT_DRDY | GPIO 6 | Optional data-ready interrupt; can poll instead |
| SA0 | GND | I²C address = 0x5C (bridge to VDD for 0x5D) |
| VDD | 3.3V | |
| PAD2LID | GND | Or float |
| Pull-ups | 10 kΩ each on SDA and SCL to 3.3V | External required; Pico W internal ~50 kΩ too weak |
| Decoupling | 100 nF ceramic between VDD and GND | Place as close to sensor as possible |

#### Wiring — MPX5010DP (Alternative)

| Signal | GPIO | Notes |
|---|---|---|
| Vout | GPIO 26 (ADC0) | Analog read; at 3.3V supply output range is reduced |
| V+ / Vs | 3.3V | Rated 5V — firmware thresholds must account for scaled output |
| GND | GND | |
| Decoupling | 100 nF + 10 µF on supply | |

> **Critical correction from earlier documentation:** Earlier drafts incorrectly described the MPX5010DP as having "Digital I²C output." It is **analog only** — Vout connects to an ADC pin, not SDA/SCL. All project files have been corrected.

#### Relationship to Filter Stack (Section 10.1)

The LPS28DFWTR's 10 ATM water-resistant potting gel provides a last-resort barrier against moisture that reaches the PCB despite the two-stage filter stack. This defence-in-depth approach — mechanical filter + hydrophobic membrane + water-resistant sensor — addresses the hygiene failure mode that caused sensor degradation in The 'Sup and openSipPuff.

---

### 10.5 Optional Display Hardware — Built-in PCB Support

#### Overview

Both display connectors are included on the PCB as unpopulated footprints. This means display support is **designed into the hardware now** but can be added in firmware incrementally — nothing stops a minimal build from shipping without a display populated, then gaining display functionality via firmware update.

The display hardware was selected to fill **Gap 3** from Section 8: no existing reviewed project combines on-device display, Bluetooth, and sub-$150 build cost in a single unit.

---

#### J1 — I²C OLED Display (1", 128×64, SSD1306)

**Connector:** 4-pin 2.54 mm Dupont header

| Pin | Signal | Connection |
|---|---|---|
| 1 | GND | Ground |
| 2 | VCC | 3.3V |
| 3 | SCL | GPIO 5 — I²C0 SCL (shared bus) |
| 4 | SDA | GPIO 4 — I²C0 SDA (shared bus) |

**Key details:**
- I²C address: 0x3C (default) or 0x3D — no conflict with LPS28DFWTR (0x5C/0x5D) or MPU6050 IMU (0x68/0x69)
- Shares the existing I²C bus and 10 kΩ pull-ups already placed for the pressure sensor — zero additional passive components
- Controller: SSD1306 (most common 1" OLED module); also compatible with SH1106
- Libraries: Adafruit SSD1306 (CircuitPython / MicroPython), or `pico-ssd1306` for C SDK

**Planned use cases:**
- Real-time pressure bar graph during sip/puff calibration
- Current mode indicator (USB HID / BLE HID / Gamepad)
- Threshold confirmation screen (show value when crossing detection boundary)
- Future: on-device config menu (matching the LipSync Hub experience but in one integrated unit)

---

#### J2 — SPI Color LCD Display (2"–4", ST7789 / ILI9341)

**Connector:** 9-pin 2.54 mm Dupont header

| Pin | Signal | GPIO | Notes |
|---|---|---|---|
| 1 | VCC | 3.3V | |
| 2 | GND | GND | |
| 3 | CS | GPIO 13 | SPI1 CSn, active low |
| 4 | RESET | GPIO 15 | Active low |
| 5 | DC/RS | GPIO 14 | High = data, low = command |
| 6 | SDI / MOSI | GPIO 11 | SPI1 TX |
| 7 | SCK | GPIO 10 | SPI1 SCK |
| 8 | LED | GPIO 16 | Backlight PWM (or solder bridge → 3.3V always-on) |
| 9 | SDO / MISO | GPIO 12 | SPI1 RX — optional, can leave open |

**Key details:**
- Uses SPI1 hardware peripheral — entirely separate from the I²C bus; no bus contention with pressure sensor or OLED
- All 7 control GPIO pins (10–16) are consecutive non-analog pins — clean PCB routing
- GPIO 16 backlight: a PCB solder bridge defaults to GPIO 16 for PWM dimming; bridge can be cut and re-bridged to 3.3V for always-on if firmware is not ready
- Compatible controllers: ST7789 (most 2"–3.2" modules), ILI9341 (common 2.8"–3.2"), GC9A01 (round 1.28" variant)

**Planned use cases:**
- Full-color rubber chicken demonstration game UI (Maker Faire primary use)
- Animated pressure visualisation (colour-coded sip vs. puff)
- Future: configuration screens with touch overlay (if resistive/capacitive touch panel added — most 3.2" ILI9341 modules include a touch controller)

---

#### I²C Bus Coexistence Summary

All I²C devices share GPIO 4 (SDA) and GPIO 5 (SCL) with a single pair of 10 kΩ pull-ups:

| Device | I²C Address | Status |
|---|---|---|
| LPS28DFWTR (pressure sensor) | 0x5C or 0x5D | Populated (default build) |
| SSD1306 OLED (J1) | 0x3C or 0x3D | Optional — J1 connector |
| MPU6050 IMU (future — Section 10.3) | 0x68 or 0x69 | Future breakout on shared bus |

No address conflicts exist across any combination of populated devices.

---

---

### 10.6 Circuit Protection — SP724AHTG on External I/O Lines

#### The Problem

Open-source assistive technology projects almost universally skip ESD (electrostatic discharge) and transient overvoltage protection on their external I/O lines. This is not unique to AT — it is endemic to maker and open-source hardware broadly. The cost is negligible; the awareness is not. The consequences of omitting it are latent GPIO damage that may not manifest immediately but can cause intermittent faults that are extremely hard to diagnose, especially in field-deployed devices used by people who depend on them.

For a device like this one — handled by users with limited motor control, plugged and unplugged frequently, potentially used in clinical environments with atypical grounding — the risk is higher than average.

#### What Was Done

SP724AHTG TVS (transient voltage suppressor) diode array ICs (STMicroelectronics) were added to all external-facing I/O lines that are **not** already protected by the PC817SC opto-isolators on the XAC output circuit.

| Protected Lines | Interface | IC Placement |
|---|---|---|
| BUTTON (GPIO 20), ROT_A (GPIO 18), ROT_B (GPIO 19) | EXTERNAL_IO connector | SP724AHTG near connector |
| SDA (GPIO 4), SCL (GPIO 5) | EXTERNAL_IO + STEMMA QT + J1 OLED | SP724AHTG on I²C lines |
| SPI lines GPIO 10–16 | J2 color LCD connector | SP724AHTG near J2 |

**Not needed on:** GPIO 0 (SIP_ENABLE) and GPIO 1 (PUF_ENABLE) — already opto-isolated by PC817SC before reaching the TRRS jacks.

#### Why SP724AHTG

- Low capacitance — does not degrade I²C (400 kHz) or SPI signal integrity
- Protects multiple lines per IC — reduces BOM count
- Small package (SOT-23-6 or similar) — fits close to connectors
- ~$0.30–0.50 per unit — cost-negligible at this project scale
- Well-documented by STMicroelectronics with application notes for exactly this use case

#### Note for Builders and Forks

If you fork this project or adapt the schematic, **do not remove the SP724AHTG ICs to simplify the BOM.** The per-unit savings are under $1. The risk of a user's device failing in the field because a GPIO was damaged by a static discharge during a mouthpiece connector swap is not worth it.

---

---

### 10.7 Medical Certification Pathway — Redundant Sensor and Safety CPU

#### Context

The current build is an open-source maker prototype. It is not a certified medical device and makes no claim to be one. However, the device is designed for use by people who may depend on it as a primary communication or environmental control interface — a population for whom device failure carries real consequences. This section documents the hardware and process changes a future certified variant would require, and confirms that the current design does not unnecessarily foreclose that path.

#### Regulatory Framework (Brief Overview)

| Jurisdiction | Relevant Standard | Device Class |
|---|---|---|
| USA (FDA) | 21 CFR Part 820, IEC 62304 | Class II (likely) — premarket notification 510(k) |
| EU | MDR 2017/745, IEC 62304, ISO 13485 | Class IIa or IIb depending on intended use |
| Software lifecycle | IEC 62304 | Class B (moderate harm) or Class C (serious harm) |
| Risk management | ISO 14971 | Required for all classes |

#### Redundant Pressure Sensor

The LPS28DFWTR supports two I²C addresses via the SA0 solder bridge (0x5C or 0x5D). A second sensor at the alternate address can be placed in the same breath path — either in the same enclosure or immediately adjacent in the tube stack — and polled alongside the primary sensor at runtime.

The firmware cross-checks both readings on every sample. A configurable discrepancy threshold (e.g. >5 hPa sustained for >100 ms) flags a sensor fault, halts sip/puff output, and alerts the user via the display and an audible or tactile indicator. The device enters a safe state — no spurious commands — rather than silently producing incorrect output.

The current PCB does not include a populated second sensor footprint, but the dual I²C address support means a second LPS28DFWTR can be wired to the existing I²C bus (GPIO 4/5) via the STEMMA QT connector or a solder bridge on a future PCB revision without any layout-level redesign.

**Estimated added cost:** ~$4–6 (second LPS28DFWTR) + minor PCB area.

#### Safety CPU / Supervisory MCU

A dedicated supervisory microcontroller monitors the primary RP2040 and forces a safe state on failure:

- **Hardware watchdog pattern:** The RP2040 firmware services a watchdog signal to the safety MCU on a fixed interval (e.g. every 100 ms). If the safety MCU does not receive the signal within the timeout window — indicating a crash, hang, or runaway loop — it asserts a hardware reset or output-disable line, cutting the sip/puff outputs before any erroneous command reaches the XAC or AT device.
- **Suitable ICs:** A small supervisory MCU such as an STM32G0 series (QFN-20, ~$1–2) running minimal watchdog firmware is sufficient for this role. A full safety-rated MCU (TI TMS570, Renesas RH850) would be required for IEC 61508 SIL-rated applications but is likely overkill for a Class II AT device.
- **PCB footprint:** A QFN-20 supervisory MCU adds modest PCB area and could be accommodated in a future PCB revision alongside the existing Pico W.

**Estimated added cost:** ~$2–5 (supervisory MCU) + programming header + PCB area.

#### Firmware and Process Scope (IEC 62304)

Moving to a certified build requires not just hardware additions but a software development process:

- Formal software requirements specification
- Hazard analysis (ISO 14971) covering failure modes of both sensors, the MCU, the I²C bus, and the output circuit
- Unit and integration testing with documented coverage targets (IEC 62304 Class B: statement coverage; Class C: branch coverage)
- Change control and version traceability
- Clinical evaluation or usability testing (IEC 62366)

This is a substantial undertaking, estimated at months of engineering effort for a small team. It is not planned for the current open-source prototype. The open-source codebase can serve as the starting point for a certified variant, with the process artefacts built around it.

#### Design Decisions That Preserve the Certification Path

The following choices made in the current design do not close off the certification pathway:

- LPS28DFWTR supports dual I²C addressing — second sensor can be added without PCB redesign
- Opto-isolated XAC outputs (PC817SC) provide a clean electrical boundary for fault containment
- STEMMA QT and EXTERNAL_IO connectors provide expansion points for a supervisory MCU interface
- Open-source firmware is fully accessible for process wrapping — no black-box components

> **Current status:** Not planned for prototype. Noted to ensure that architectural decisions made now keep the certified variant viable, and to give the community a documented roadmap if anyone chooses to pursue it.

#### Project Author's Prior FDA Experience

The lead designer of this project has prior hands-on involvement in the design and manufacture of an FDA-regulated medical device — a lithium battery system for power wheelchairs, developed in conjunction with an established power wheelchair manufacturer. That collaboration provided direct exposure to FDA quality system requirements (21 CFR Part 820), design controls, risk management processes, and the realities of regulated manufacturing. The certification pathway described in this section is informed by that experience — the kinds of hardware decisions that preserve or foreclose a future certification path are familiar territory. If the project generates sufficient community interest, a certified variant is a realistic rather than purely aspirational goal.

---

*Last updated: April 2026. Section 10.7 added — medical certification pathway documented. Section 10.6 added — circuit protection documented. Sections 10.4 and 10.5 added — sensor decision and display hardware documented. Section 10.3 IMU timeline updated to post-Maker-Faire.*

---

*This document was compiled in April 2026 from publicly available GitHub READMEs, project websites, and community articles. Verify specific technical details against the upstream repositories before relying on them in production.*
