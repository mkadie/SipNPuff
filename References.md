## Component Datasheets

### Default Pressure Sensor: LPS28DFWTR
- **Manufacturer**: STMicroelectronics
- **Description**: MEMS nano pressure sensor — water-resistant, 24-bit, I²C, 0.32 Pa noise, CCLGA-7L SMD package (2.8 × 2.8 × 1.95 mm), rated 10 ATM, 1.7 µA idle current
- **Document**: DS13317 Rev 1, December 2021
- **Datasheet**: [ST Product Page & Datasheet (DS13317)](https://www.st.com/en/mems-and-sensors/lps28dfw.html)
- **Direct PDF**: [DS13317 Datasheet PDF](https://www.st.com/resource/en/datasheet/lps28dfw.pdf)
- **Key parameters for this project**:
  - I²C address: 0x5C (SA0 → GND) or 0x5D (SA0 → VDD)
  - GPIO connections: SDA → GPIO 4, SCL → GPIO 5, INT_DRDY → GPIO 6 (optional)
  - Pull-ups: 10 kΩ on SDA and SCL to 3.3V
  - Decoupling: 100 nF ceramic cap between VDD and GND

### Alternative Pressure Sensor: MPX5010DP
- **Manufacturer**: NXP Semiconductors (formerly Freescale)
- **Description**: Integrated silicon pressure sensor, 0–10 kPa differential, analog voltage output, through-hole SIP-6 package
- **Datasheet**: [MPX5010 Series Datasheet](https://www.nxp.com/docs/en/data-sheet/MPX5010.pdf)
- **Key parameters for this project**:
  - Output: Analog voltage (0.2–4.7V at 5V; scales at 3.3V) — connects to GPIO 26 (ADC0)
  - **NOT I²C** — analog only
  - Accuracy: ±1.5% FS

---

## Related Open Source Projects

This project builds upon and is inspired by several existing open source sip and puff implementations. The following projects have influenced the design and functionality of this system:

### SipNPuff_Mouse
- **Description**: A mouse interface for individuals with quadriplegia that utilizes sip and puff technology
- **Key Features**: 
  - Mouse control functionality for computer navigation
  - Open source hardware and software design
  - Accessible interface for users with limited hand function
- **Link**: [GitHub Repository](https://share.google/a5RVRMyr3VZOHK2lp)

### Sup - Mouse for People With Quadriplegia
- **Description**: Low cost and open source mouse solution specifically designed for individuals with quadriplegia
- **Key Features**: 
  - Step-by-step construction guide
  - Cost-effective implementation
  - Accessible technology demonstration
- **Link**: [Instructables Project](https://share.google/5HzDPzcItnGSA3f4j)

### FLipMouse
- **Description**: Finger and LipMouse - an open source mouse alternative that uses lip and finger movements
- **Key Features**: 
  - Multi-modal input system
  - Open source hardware and software
  - Accessible computer control
- **Link**: [GitHub Repository](https://share.google/WR0RQ19SlAwgkmR7u)

### LipSync
- **Description**: An open-source mouth operated sip and puff joystick that enables people with limited hand function to emulate a mouse on their computer and/or smartphone
- **Key Features**: 
  - Mouth-operated joystick interface
  - Computer mouse emulation
  - Smartphone compatibility
- **Link**: [GitHub Repository](https://share.google/8IbFtTts3j5iU0bZs)

### openSipPuff
- **Description**: Simple, low-cost "sip and puff" USB interface for expressive interactions, enabling breath-based control of keypresses, mouse actions and much more using USB HID
- **Key Features**: 
  - USB HID compatibility
  - Expressive interaction capabilities
  - Breath-based control system
  - Multi-function USB interface
- **Link**: [GitHub Repository](https://share.google/UcRl67BSX3mFsHV2P)

### Community Contributions
This project aims to be compatible with and contribute to the broader accessibility technology community. We encourage integration with other open source assistive technology projects and welcome contributions from the maker community.

These projects represent the collaborative spirit of the open source accessibility community and demonstrate the potential for shared development in assistive technology. They have collectively contributed to advancing accessible technology solutions and have informed the development of this system's modular and scalable approach.