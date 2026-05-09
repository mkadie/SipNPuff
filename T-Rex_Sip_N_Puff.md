# Project Documentation: The Sip-and-Puff "Rubber Chicken" Edition

## 1. Project Vision & Mission
The **Sip-and-Puff Rubber Chicken Edition** is a low-cost, open-source assistive technology bridge designed to convert breath pressure into digital control signals (rotary encoder and button inputs). It serves a dual-purpose role:
* **Primary Focus:** A robust, affordable sip-and-puff switch system for individuals with motor disabilities, such as spinal cord injuries, ALS, or cerebral palsy.
* **Secondary Focus:** An engaging "maker-grade" demonstration tool using rubber chickens as bellows to make assistive technology approachable for the general public at events like Maker Faires.

---

## 2. Core Operational Logic
The system emulates a rotary encoder with an integrated push-button using pressure sensor input.

### Input Mapping
| Action | Hardware Emulation | Behavior |
| :--- | :--- | :--- |
| **Single Puff** | Rotary Increment (+1) | Mimics one "click" of a rotary encoder. |
| **Puff and Hold** | Continuous Scroll | Increments repeatedly; higher pressure results in a faster increment rate. |
| **Double Puff** | Button Press / Select | Interpreted as the "click" of the encoder shaft to select an item. |
| **Sip (Optional)** | Negative Increment (-1) | Decrements values (supported by differential sensors like the MPX5010DP). |

---

## 3. Maker Faire Engagement: The "Chicken Challenge" Game
To showcase the technology, a dedicated game station will be featured at the booth.

### Hardware Setup
* **T-Rex Talker Station:** A standalone AAC unit with a 320x240 color screen.
* **Interface:** The T-Rex Sip-and-Puff is plugged directly into the station.
* **Display Layout:** The lower 320x200 section of the screen displays 8 selectable communication categories.

### Gameplay Mechanics
* **The Start:** A player squeezes the rubber chicken once to initiate a run.
* **The Quiz:** 10 questions appear sequentially. Players must map "real-world" feelings to the correct AAC category (e.g., if the screen asks "I drank too much soda?", the player must select the "I need to use the bathroom" section).
* **Feedback:** The device speaks the selected phrase aloud after every choice before proceeding to the next question.
* **Scoring:** * The total score is the time taken to complete all 10 questions.
    * **Penalty:** A 30-second penalty is added for each incorrect selection.
    * **Timer Logic:** The timer pauses while the device is speaking to ensure users are not penalized for the system's vocal processing time.
* **Leaderboard:** The station tracks the "Best Time" between rounds, with prizes awarded for the lowest overall time.
* **Educational Context:** A large poster behind the station with graphics will explain the mechanics and the importance of accessible interfaces.

---

## 4. Hardware & Power Specifications

### Microcontroller & Sensors
* **Microcontroller:** Raspberry Pi Pico / RP2040, chosen for cost-effectiveness and dual-core processing.
* **Pressure Sensor:** MPX5010DP Differential Pressure Sensor (0-100 kPa range).

### Power & Battery Life (500 mAh Basis)
* **Default Operation:** ~50mA draw (Pico + Sensor + LEDs), providing roughly 10 hours of continuous use.
* **Low-Power Architecture:** For portable versions, the system can transition to an **RP2350** or **TI MSPM0**.
* **Deep Sleep Logic:** The sensor can be powered down during idleness. To wake the device, a user must perform a prolonged sip or puff (exceeding the configurable sleep timer), allowing the sensor time to reach reading stability.

### Safety & Processor Selection
* **Standard Version:** Raspberry Pi RP2040 for maker environments.
* **Medical/Safety Version:** For applications seeking **FDA safety certification**, the design requires:
    * **Redundancy:** Dual processors cross-verifying signals.
    * **Certified Hardware:** A safety-qualified processor such as the **TI Hercules (TMS570)** or the **STM32 Silicon Functional Safety** line.

---

## 5. Integration Use Cases

### Use Case 1: T-Rex Talker Integration
* **1a: I2C Polling:** Host device polls the Pico for state changes.
* **1b: Encoder Input:** Plugs directly into the T-Rex Talker’s rotary encoder port.
* **1c: I2C with Data Ready:** Uses the **'Button/Int' line** as a hardware interrupt to signal the software when data is ready for retrieval.

### Use Case 2: Xbox Adaptive Controller (XAC)
* Connects via 3.5mm mono jacks using **optocouplers (PC817)** to mimic "dry contact" switches.

---

## 6. Goals and Research Objectives

1.  **Global Accessibility:** Create an affordable sip-and-puff switch for worldwide use, targeting a **$25-$50** price point.
2.  **Open Source Philosophy:** Provide full documentation and code to the community.
3.  **HCI Research:** Serve as a platform for studying accessible interface design and user experience.
4.  **Academic Publication:** Establish a foundation for research papers in IEEE accessibility venues.
5.  **Engineering Education:** Provide a hands-on STEM project for learning about sensors and assistive design.

---
*Created for Maker Faire 2026 Demonstration.*