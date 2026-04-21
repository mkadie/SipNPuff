# Sip and Puff Rubber Chicken Edition


## Project Overview

This project implements a functional sip and puff switch interface that serves as both a demonstration system (using rubber chickens) and a working, low-cost ($25-50) sip and puff device for accessibility applications. The core functionality focuses on creating a reliable, accessible interface while using the rubber chicken concept as an engaging demonstration tool for normally abled users.

---

## ⭐ Primary Claim to Fame: One Build, Many Purposes — Text File Configuration

> **The defining characteristic of this project is flexibility.**

Most open-source sip and puff devices are purpose-built for a single output: a USB mouse, a keyboard emulator, or a specific AT protocol. Changing what the device *does* means reflashing firmware or editing code. This project takes a different approach: **a single hardware build and a single firmware image that can be reconfigured for completely different tasks by editing a plain text configuration file** — no compiler, no IDE, no programmer required.

A clinician, caregiver, or technically capable user can open the config file (accessible as a USB drive when the device is plugged in) and change:
- What a sip or puff event maps to (keypress, mouse button, joystick axis, HID consumer control, serial command, etc.)
- Sensitivity thresholds for sip and puff, independently
- Operating mode (USB HID mouse, USB HID keyboard, XAC gamepad output, serial AT command relay, etc.)
- Head-tracking parameters (dead zone, speed curve, re-centre trigger gesture)
- Display content and feedback behaviour

The same physical device can serve as:
- A USB mouse (head tracking + sip/puff clicks)
- A two-switch keyboard input (sip = one key, puff = another)
- An Xbox Adaptive Controller input (via the onboard TRRS jacks)
- A demonstration interface (rubber chicken mode for Maker faires)
- A research data collection tool (with optional microSD logging)

No other project in the open-source sip and puff space offers this level of reconfigurability without touching firmware. This is intentional and is the core design goal that drives decisions about display hardware, the EXTERNAL_IO connector, STEMMA QT expansion, and the overall software architecture.

---

## Project Stage

Early, rapid development for prototype by Maker event, which one ... hopefully the next one :)

## Core Mission

### Primary Focus: Flexibility Through Text File Configuration
The defining goal is a single hardware and software build that can be reconfigured for a wide range of tasks by editing a plain text config file — no reflashing, no coding skills required. The same device adapts to the user, rather than requiring the user to adapt to a fixed device behavior.

### Secondary Focus: Functional Accessibility Interface
The main objective is to develop a robust, affordable sip and puff switch system that can be used for:
- Assistive technology for individuals with motor disabilities
- Accessibility solutions for communication devices
- Research in human-computer interaction
- Educational demonstrations in accessibility technology

### Tertiary Focus: Demonstration and Engagement
The rubber chicken concept serves as an engaging demonstration tool for:
- Maker faires and community events
- Educational outreach programs
- Public demonstrations of accessibility technology
- Engaging users in the concept of assistive interfaces

## Hardware Design

### Primary Components

#### Sensors

> **PCB Strategy:** Initial PCBs support both sensor footprints simultaneously. After real-world testing, separate PCB variants (SMD-only and through-hole) will be produced.

##### Default Sensor: LPS28DFWTR (SMD — I²C digital)
- **Part:** STMicroelectronics LPS28DFWTR
- **Package:** CCLGA-7L, 2.8 × 2.8 × 1.95 mm — SMD only, requires reflow or hot-air soldering
- **Why it's default:** Water-resistant package (potting gel, rated 10 ATM), 24-bit resolution, ultra-low noise (0.32 Pa), factory-calibrated, I²C interface, embedded FIFO, interrupt output, and 1.7 µA idle current
- **Interface:** I²C (up to 400 kHz fast mode; 1 MHz fast mode+) — connects directly to Pico W I²C bus
- **I²C address:** 0x5C (SA0 pin → GND) or 0x5D (SA0 pin → VDD) — selectable via PCB solder bridge
- **Pressure range:** Mode 1: 260–1260 hPa (optimised for sip/puff); Mode 2: 260–4060 hPa
- **Pressure noise:** 0.32 Pa RMS (Mode 1) — more than sufficient for breath detection
- **Accuracy:** ±0.5 hPa absolute, ±0.015 hPa relative
- **ODR:** 1–200 Hz (software configurable)
- **Supply voltage:** 1.7 to 3.6 V (3.3V from Pico W is within spec)
- **Interrupt:** INT_DRDY pin — data-ready interrupt for efficient polling
- **Datasheet:** DS13317 Rev 1, December 2021 (ST Microelectronics)
- **Sensor Placement:** Positioned in breath path between mouthpiece filter and PCB; water-resistant package tolerates condensation exposure

##### Alternative Sensor: MPX5010DP (Through-Hole — Analog output)
- **Part:** NXP/Freescale MPX5010DP
- **Package:** Through-hole SIP-6 — can be hand-soldered without SMD equipment
- **Why it's an alternative:** Easier to hand-solder for early prototypes and events; no SMD tools required
- **Interface:** **Analog voltage output** (0.2V–4.7V at 5V supply) — connects to a Pico ADC pin, **NOT I²C**
- **Pressure range:** 0–10 kPa differential
- **Supply voltage:** 2.7–5.5V (note: at 3.3V supply the output range scales; verify output headroom in firmware)
- **Accuracy:** ±1.5% FS
- **Power consumption:** ~6 mA typical (significantly higher than LPS28DFWTR)
- **Sensor Placement:** Same breath-path position; analog output wire routes to GPIO 26 (ADC0) on Pico W

#### Microcontroller
- **Raspberry Pi RP2040**: Chosen for its cost-effectiveness ($4), dual-core ARM Cortex-M0+ processor, and sufficient processing power for signal conditioning
- **Alternative Options**: 
  - ESP32 for WiFi connectivity
  - Arduino Nano for simpler implementations
  - STM32 for higher performance applications
- **Processing Requirements**: Signal filtering, input classification, and output protocol handling

#### Mechanical Interface
- **Primary Sip/Puff Mechanism**: 
  - Standard straw or tube for suction input
  - Blow tube for pressure input
  - Ergonomic design for comfortable use
- **Alternative Interfaces**: 
  - Custom 3D printed mouthpieces
  - Commercial sip/puff devices
  - Modular interface system for different user needs
- **Enclosure Design**: 
  - Durable, medical-grade materials
  - Easy-to-clean surfaces
  - Ergonomic housing for various user groups
- **Interface Options**: 
  - Standard straw configuration
  - Bellows system for precise suction detection
  - Custom mouthpiece designs

#### Optional Display Connectors

> Both connectors are unpopulated PCB footprints — built-in hardware support with no board redesign needed to add displays later.

##### J1 — I²C OLED Display (1", 128×64)
- **Connector**: 4-pin 2.54 mm Dupont header on PCB
- **Display type**: 1" 128×64 OLED, SSD1306 controller (or compatible)
- **Interface**: I²C — shares existing GPIO 4 (SDA) / GPIO 5 (SCL) bus with the LPS28DFWTR sensor
- **I²C address**: 0x3C (default) or 0x3D — no conflict with LPS28DFWTR at 0x5C/0x5D
- **Supply**: 3.3V
- **Pin order (1→4)**: GND → VCC → SCL → SDA
- **Use case**: Status readout, sip/puff feedback, pressure level bar graph

##### J2 — SPI Color LCD Display (2"–4")
- **Connector**: 9-pin 2.54 mm Dupont header on PCB
- **Display type**: 2"–4" color TFT LCD, ST7789 or ILI9341 controller (or compatible)
- **Interface**: SPI1 hardware peripheral on dedicated non-analog GPIO pins
- **GPIO assignments**:
  - GPIO 10 — SCK (SPI1 clock)
  - GPIO 11 — MOSI / SDI (SPI1 TX)
  - GPIO 12 — MISO / SDO (SPI1 RX, optional)
  - GPIO 13 — CS (chip select, active low)
  - GPIO 14 — DC/RS (high = data, low = command)
  - GPIO 15 — RESET (active low)
  - GPIO 16 — LED (backlight PWM; solder bridge for always-on 3.3V)
- **Pin order (1→9)**: VCC → GND → CS → RESET → DC/RS → MOSI → SCK → LED → MISO
- **Supply**: 3.3V
- **Use case**: Full-color rubber chicken game interface, animated demo display

#### Circuit Protection

> **A commonly overlooked step in open-source hardware projects, including many assistive technology designs.** External-facing I/O lines that connect to the real world — connectors, encoder inputs, expansion ports — are exposed to ESD events and electrical transients. Protecting the microcontroller's GPIO pins from these events is straightforward and inexpensive; skipping it is a common cause of latent damage in both hobby and clinical builds.

- **IC:** SP724AHTG — low-capacitance TVS (transient voltage suppressor) diode array, STMicroelectronics
- **Coverage:** All external-facing I/O lines **not** already protected by opto-isolation:
  - EXTERNAL_IO connector: BUTTON (GPIO 20), ROT_A (GPIO 18), ROT_B (GPIO 19), SDA (GPIO 4), SCL (GPIO 5)
  - STEMMA QT expansion port (SDA, SCL)
  - Display connectors J1 and J2 signal lines as applicable
- **Not needed on:** GPIO 0 (SIP_ENABLE) and GPIO 1 (PUF_ENABLE) — these are already isolated by PC817SC optocouplers before reaching the TRRS jacks
- **Why SP724AHTG:** Low capacitance preserves signal integrity on I²C and SPI lines; small package; single IC can protect multiple lines simultaneously; ~$0.30–0.50 per IC in single-unit quantities

#### Power Supply
- **Battery Option**: PCB designed to accommodate battery but not populated (user-selectable)
- **Optional LDO Power Supply**: For chair-based installations at events
- **Power Management**: 
  - Standalone operation with optional power expansion
  - Low power consumption design for battery operation
  - USB charging capability for convenience
- **Power Requirements**: 
  - Standby: <10mA
  - Active: <50mA
  - Battery life: >20 hours continuous operation

### Cost Analysis

| Component | Cost (single unit) | Notes |
|---|---|---|
| Pressure sensor — LPS28DFWTR | ~$4–6 | **Primary / default.** STMicroelectronics CCLGA-7L SMD; I²C, 24-bit, 0.32 Pa noise, water-resistant potting gel. Requires reflow or hot-air soldering. |
| Microcontroller | ~$4 | Raspberry Pi Pico W (RP2040 + CYW43439) |
| XAC output circuit | ~$2–3 | 2× PC817SC optocouplers + 2× TRRS jacks |
| Circuit protection | ~$1–2 | SP724AHTG TVS array ICs × 2–3 units; protects all I/O lines not covered by opto-isolators |
| Mechanical components | ~$5–10 | Tube, mouthpiece, connectors |
| Enclosure materials | ~$5–10 | 3D-printed or off-the-shelf housing |
| Miscellaneous | ~$5–10 | Resistors, caps, PCB, hardware |
| **Base build total** | **~$21–45** | Functional sip/puff device with XAC output and ESD protection |
| **Optional — MPX5010DP sensor** | **+~$3–5** | Through-hole analog alternative to the LPS28DFWTR; hand-solderable, no SMD tools required. *Depending on performance testing of the LPS28DFWTR vs MPX5010DP, this may remain a supported alternative or be retired from the design.* PCB includes footprint for both — only one is populated. |
| **Optional — BNO055 IMU** | **+~$30–35** | Bosch BNO055 on STEMMA QT breakout (e.g. Adafruit #4646); adds head-tracking (Mode A) and/or tongue-joystick cursor control (Mode B). Post-Maker-Faire upgrade — not required for core sip/puff functionality. Sensor alone costs more than the rest of the BOM combined at single-unit prices. |
| **Optional — display(s)** | **+~$5–15** | J1: 1" SSD1306 OLED ~$3–5; J2: 2–4" color LCD ~$8–15; PCB connectors already present |
| **Optional — hygiene filters** | **~$0.50–2 each** | Recurring consumable; see Section 10.1 of reference doc for filter options |
| **Full build with IMU + display** | **~$56–95** | Still well below comparable commercial AT devices ($175–$325+) |
| **Future / Medical-grade — redundant hardware** | **+~$15–30 est.** | For a medically certified build: a second LPS28DFWTR pressure sensor (cross-checks primary; flags discrepancy as fault condition) plus a second or dedicated safety CPU (hardware watchdog / supervisory MCU to monitor the primary RP2040 and force a safe state on failure). Required for IEC 62304 / FDA Class II pathway. Significant increase in PCB complexity and firmware scope. Not planned for current prototype — noted here as the architectural direction a certified variant would take. The lead designer has prior involvement in the design and manufacture of an FDA-regulated medical device (a lithium battery system for power wheelchairs, developed in conjunction with an established powerchair manufacturer), making this a realistic rather than purely aspirational future direction. See Section 10.7 of the reference doc for full detail. |

- **Manufacturing Considerations**: 
  - Scalable production design
  - Component sourcing for cost optimization
  - Quality control procedures

## Software Architecture

### Core Functionality

The system operates as a reliable, functional sip and puff interface with the following core features:

1. **Pressure Sensing**: Continuous monitoring of pressure sensor data with filtering — I²C polling (LPS28DFWTR default) or ADC sampling (MPX5010DP alternative)
2. **Input Classification**: Distinguishing between sip and puff actions with threshold detection
3. **Signal Processing**: Debouncing and smoothing of pressure readings
4. **Command Generation**: Converting pressure inputs into actionable commands
5. **Output Protocol**: Providing standardized outputs for various applications

### Input/Output Processing

#### Input Detection
- **Suction Detection**: Threshold detection for negative pressure (sip)
- **Blow Detection**: Threshold detection for positive pressure (puff)
- **Hold Detection**: Continuous pressure monitoring for extended commands
- **Debouncing**: Filtering for false triggers and noise reduction

#### Output Protocols
- **Digital Outputs**: 
  - Binary signals for on/off commands
  - Multi-level outputs for different command types
  - Serial communication for complex data transfer
- **Analog Outputs**: 
  - Voltage level representation of pressure
  - Proportional response for advanced applications
- **Communication Protocols**: 
  - I2C for LPS28DFWTR sensor communication (default); ADC for MPX5010DP (alternative)
  - UART for serial data transfer
  - USB for PC connectivity

### Command Structure
- **Basic Commands**: 
  - Sip (negative pressure)
  - Puff (positive pressure)
  - Hold (extended pressure)
- **Advanced Commands**: 
  - Double tap
  - Long press
  - Pattern recognition
- **Customizable Mapping**: 
  - User-defined command associations
  - Application-specific command sets

## Technical Specifications

### Electrical Specifications
- **Supply Voltage**: 3.3V or 5V (user selectable)
- **Current Consumption**: <50mA (standby), <100mA (active)
- **Operating Temperature**: -20°C to +70°C
- **Humidity Range**: 5% to 95% RH (non-condensing)
- **Input Impedance**: High impedance for sensor compatibility
- **Output Impedance**: Low impedance for reliable signal transmission

### Mechanical Specifications
- **Dimensions**: 150mm × 100mm × 50mm (approximate)
- **Weight**: <200g (excluding power source)
- **Input Force Range**: -500Pa to +500Pa
- **Response Time**: <100ms for pressure changes
- **Interface Materials**: Medical-grade, non-toxic materials
- **Durability**: >100,000 cycles of operation

### Performance Metrics
- **Accuracy**: ±2% for pressure measurements
- **Repeatability**: ±1% across multiple readings
- **Detection Threshold**: 50Pa for both suction and blowing
- **Operating Life**: >100,000 cycles
- **Reliability**: 99.5% uptime under normal conditions
- **Noise Resistance**: >60dB signal-to-noise ratio

## Accessibility Applications

### User Groups
- **Motor Disabled Individuals**: 
  - Spinal cord injury patients
  - Cerebral palsy users
  - ALS patients
  - Stroke recovery patients
- **Communication Needs**: 
  - Augmentative and alternative communication (AAC)
  - Voice output communication aids
  - Environmental control systems
- **Research Applications**: 
  - Motor function assessment
  - Rehabilitation technology
  - User interface studies

### Integration Capabilities
- **Communication Devices**: 
  - Text-to-speech systems
  - Voice synthesis units
  - Communication boards
- **Environmental Control**: 
  - Home automation systems
  - Lighting controls
  - Temperature regulation
- **Assistive Technology**: 
  - Wheelchair controls
  - Computer interface systems
  - Mobile device control

## Demonstration System (Rubber Chicken Concept)

### Purpose
- **Engagement Tool**: Make accessibility technology approachable and fun
- **Educational Aid**: Demonstrate principles of sip and puff technology
- **Community Outreach**: Attract attention to accessibility needs
- **Public Awareness**: Showcase assistive technology capabilities

### Demonstration Features
- **Rubber Chicken Interface**: 
  - Visual representation of the technology
  - Engaging user experience
  - Easy to understand concept
- **Interactive Gameplay**: 
  - Educational quiz system
  - Game-based learning
  - User engagement metrics
- **Public Display**: 
  - Maker faire setup
  - Educational booth
  - Community demonstration

### Technical Integration
- **Dual Functionality**: 
  - Real sip/puff system for actual use
  - Demonstration system for public engagement
- **Switching Mechanism**: 
  - User-selectable modes
  - Automatic mode detection
  - Context-aware operation

## Open Source Philosophy

### Documentation
- **Hardware**: Complete schematics, PCB layouts, BOM
- **Software**: Full source code with detailed comments
- **Assembly**: Step-by-step instructions
- **Calibration**: Testing and validation procedures
- **Applications**: Usage examples and integration guides

### Community Engagement
- **GitHub Repository**: Collaborative development environment
- **Issue Tracking**: Feature requests and bug reporting
- **Contribution Guidelines**: Clear development standards
- **Version Control**: Stable releases and development branches
- **Integration Tools**: Compatibility with maker ecosystem

## Research and Development Applications

### Academic Potential
- **Human-Computer Interaction**: 
  - Accessible interface design
  - User experience studies
  - Motor disability research
- **Assistive Technology**: 
  - Device development
  - User testing protocols
  - Technology evaluation
- **Engineering Education**: 
  - Hands-on learning projects
  - Design methodology
  - Prototyping techniques

### Publication Goals
- **IEEE Venues**: 
  - Accessibility technology papers
  - Human-computer interaction research
  - Assistive device development
- **Conference Presentations**: 
  - Maker faire demonstrations
  - Educational outreach
  - Research findings
- **Academic Papers**: 
  - Technical specifications
  - Performance analysis
  - User study results

## Scalability and Future Development

### Modular Design
- **Interface Expansion**: 
  - Different mechanical configurations
  - Customizable user interfaces
  - Modular component system
- **Protocol Support**: 
  - Multiple output standards
  - Integration with existing systems
  - Future-proof architecture
- **Upgrade Path**: 
  - Hardware improvements
  - Software enhancements
  - Feature additions

### Market Applications
- **Educational Institutions**: 
  - STEM learning tools
  - Engineering design projects
  - Accessibility education
- **Healthcare Providers**: 
  - Assistive technology solutions
  - Rehabilitation equipment
  - Clinical research tools
- **Research Labs**: 
  - Human-computer interaction studies
  - Device development
  - User interface research

## Conclusion

The Sip and Puff Rubber Chicken Edition represents a dual-purpose system that successfully balances accessibility functionality with community engagement. While the core focus remains on creating a reliable, affordable sip and puff interface for individuals with motor disabilities, the rubber chicken demonstration serves as an effective tool for public education and community outreach.

This approach ensures that the technology serves its primary purpose of supporting accessibility needs while also generating interest and understanding in the broader community. The system's modular design, open source nature, and focus on affordability position it well for both immediate practical applications and long-term research and development opportunities.

The project demonstrates how maker culture can contribute meaningfully to accessibility technology, creating solutions that are not only functional but also engaging and educational. By maintaining focus on the core sip and puff functionality while using the rubber chicken concept for demonstration, this system successfully bridges the gap between serious assistive technology and community engagement.

## Future

Taking inspiration from other sip and puff open source projects we will attempt to integrate mouse functionality after Maker Faire as time and schedule permit. The mouse feature is a software extension and should be comparatively easy.

### Head-Tracking via IMU (Phase 2 — Post-Maker-Faire)

The longer-term plan is to add **head-movement-based cursor control** using an IMU sensor, combining it with sip/puff for mouse clicks. This approach was validated in a peer-reviewed 2025 study ([S1] in the Reference doc) and is well-suited to users with high-level spinal cord injury or other conditions where oral motor control is limited.

**Selected sensor: Bosch BNO055** (~$30–35 on a STEMMA QT breakout)

The BNO055 was chosen over cheaper 6-DOF alternatives (MPU-6050, BMI270, LSM6DSOX) because it includes an on-board sensor fusion processor that outputs clean Euler angles and quaternions directly — no Kalman or Madgwick filter to implement. Its built-in magnetometer (9 DOF) also eliminates the yaw drift problem that affects 6-axis-only sensors during prolonged use, which is a real usability burden for a head mouse used over hours. The cost premium (~$25 over a basic IMU) is justified in context — it is a one-time addition, comparable in scale to a few rounds of replacement hygiene filters.

**Two mounting modes — same hardware, different placement:**

**Mode A — Head Strap / Glasses Mount:** The BNO055 is clipped to a glasses frame, forehead strap, or ear clip. Head nods and tilts move the cursor. Best for users with good head mobility. I²C wires run from the STEMMA QT port along the tube to the sensor on the head.

**Mode B — Tongue Joystick via Straw Attachment:** A small 3D-printed collar clips the BNO055 to the sip/puff tube near the mouthpiece. The user deflects the straw with their tongue — left, right, up, down — and the BNO055 detects the angular change of the tube. The straw becomes the joystick lever. Best for users with good tongue or lip control but limited head movement. Same hardware as Mode A, just repositioned.

With proper configuration the required activation force can be significantly reduced. The collar's position along the tube acts as a lever — moving it further from the tip lengthens the lever arm so a lighter tongue push produces a larger angular signal. Tube material flexibility also plays a role. On the software side, the sensitivity and dead zone settings in the config file can be tuned so that very small movements register as valid input without making the cursor jittery at rest. This makes Mode B viable for users with very limited tongue or lip strength, and gives clinicians a way to adjust force requirements without any hardware changes.

Switching between modes is a config file change (sensitivity, dead zone, and axis orientation parameters) — no reflashing required. This is a direct expression of the project's core flexibility goal.

**Hardware readiness:** No PCB changes are needed. The STEMMA QT expansion port (GPIO 4/5 I²C bus) is already present on the board for exactly this purpose. The BNO055's I²C address (0x28 or 0x29) does not conflict with any other device on the shared bus.

A three-way hybrid — head tracking, tongue joystick, and Hall-effect mouthpiece stick as selectable modes on the same hardware — is a longer-term stretch goal. No existing reviewed open-source project offers even two of these three options.