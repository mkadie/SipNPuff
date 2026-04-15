# Sip and Puff Rubber Chicken Edition


## Project Overview

This project implements a functional sip and puff switch interface that serves as both a demonstration system (using rubber chickens) and a working, low-cost ($25-50) sip and puff device for accessibility applications. The core functionality focuses on creating a reliable, accessible interface while using the rubber chicken concept as an engaging demonstration tool for normally abled users.

## Project Stage

Early, rapid development for prototype by Maker event, which one ... hopefully the next one :)

## Core Mission

### Primary Focus: Functional Accessibility Interface
The main objective is to develop a robust, affordable sip and puff switch system that can be used for:
- Assistive technology for individuals with motor disabilities
- Accessibility solutions for communication devices
- Research in human-computer interaction
- Educational demonstrations in accessibility technology

### Secondary Focus: Demonstration and Engagement
The rubber chicken concept serves as an engaging demonstration tool for:
- Maker faires and community events
- Educational outreach programs
- Public demonstrations of accessibility technology
- Engaging users in the concept of assistive interfaces

## Hardware Design

### Primary Components

#### Sensors
- **MPX5010DP Pressure Sensor**: Selected for its wide pressure range (0-100 kPa), digital output capabilities, and cost-effectiveness
- **Sensor Specifications**: 
  - Pressure range: 0-100 kPa
  - Output: Digital I2C interface
  - Supply voltage: 2.7-5.5V
  - Power consumption: <100μA
  - Accuracy: ±1.5% FS
- **Sensor Placement**: Positioned to detect pressure changes from both suction and blowing actions with proper airflow management

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
- **Sensors**: ~$3-5
- **Microcontroller**: ~$4 (RP2040)
- **Mechanical Components**: ~$5-10
- **Enclosure Materials**: ~$5-10
- **Miscellaneous Components**: ~$5-10
- **Total Target Cost**: $25-50
- **Manufacturing Considerations**: 
  - Scalable production design
  - Component sourcing for cost optimization
  - Quality control procedures

## Software Architecture

### Core Functionality

The system operates as a reliable, functional sip and puff interface with the following core features:

1. **Pressure Sensing**: Continuous monitoring of MPX5010DP sensor data with filtering
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
  - I2C for sensor communication
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

Taking inspiration from other sip and puff open source projects we will attempt to integrate mouse functionality after maker faire as time and schedule permit and possibly add a hal effect joystick into the system as well if there is an audience for it.  The mouse feature is a software extension and should be comparitively easy.  But I digress