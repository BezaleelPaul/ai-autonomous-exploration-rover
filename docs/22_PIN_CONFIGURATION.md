# 22. Complete Microcontroller Pin Configuration & Mapping

**Document ID:** DOC-HW-002  
**Project:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Status:** Verified Pin Allocation Matrix  
**Standard Compliance:** Verified against `arduino/rover_controller/rover_controller.ino` and `esp32/camera_stream/camera_stream.ino`

---

## 1. Arduino UNO R3 Complete Pin Mapping

| Pin Designation | Physical Pin Type | Subsystem Assigned | Target Device Pin | Functional Role & Electrical Protocol | Source File Reference |
| :---: | :---: | :---: | :---: | :--- | :--- |
| **D0** | Digital / RXD | Communication | Laptop (USB Serial) | Host Command Ingest, 9600 baud 5V TTL (never jumpered to ESP32) | `rover_controller.ino:35` |
| **D1** | Digital / TXD | Communication | Laptop (USB Serial) | Host Telemetry Out, 9600 baud 5V TTL (never jumpered to ESP32) | `rover_controller.ino:35` |
| **D2** | Digital I/O | Odometry | Wheel Encoder L (INT0) | Wheel Encoder Left Interrupt (`encISR_L` tick counter → `TICKS:<l>,<r>` telemetry) | `rover_controller.ino` (Phase 9+) |
| **D3** | PWM / Digital | Odometry | Wheel Encoder R (INT1) | Wheel Encoder Right Interrupt (`encISR_R` tick counter → `TICKS:<l>,<r>` telemetry) | `rover_controller.ino` (Phase 9+) |
| **D4** | Digital I/O | Unassigned | Reserved | Optional Status LED / Beeper | Available for Expansion |
| **D5** | Timer0 PWM | Motor Driver | L298N ENA Terminal | Left Motor Speed Modulation (PWM ~976 Hz) | `rover_controller.ino:13` |
| **D6** | Digital Output | Motor Driver | L298N IN1 Terminal | Left Motor Forward Logic Gate (5V HIGH) | `rover_controller.ino:14` |
| **D7** | Digital Output | Motor Driver | L298N IN2 Terminal | Left Motor Reverse Logic Gate (5V HIGH) | `rover_controller.ino:15` |
| **D8** | Digital Output | Motor Driver | L298N IN3 Terminal | Right Motor Forward Logic Gate (5V HIGH) | `rover_controller.ino:16` |
| **D9** | Digital Output | Motor Driver | L298N IN4 Terminal | Right Motor Reverse Logic Gate (5V HIGH) | `rover_controller.ino:17` |
| **D10** | Timer1 PWM | Motor Driver | L298N ENB Terminal | Right Motor Speed Modulation (PWM ~490 Hz) | `rover_controller.ino:18` |
| **D11** | Digital Output | Ultrasonic | HC-SR04 TRIG Pin | 10 µs High Ultrasonic Trigger Pulse | `rover_controller.ino:21` |
| **D12** | Digital Input | Ultrasonic | HC-SR04 ECHO Pin | Acoustic Return Pulse Width Timing (30ms timeout)| `rover_controller.ino:22` |
| **D13** | Digital Output | Status Indicator | Onboard LED | System Heartbeat Indicator | Arduino Hardware |
| **5V** | Power In/Out | Power Subsystem | Buck Converter 5V Out | Logic Power Supply (Nominal 5.0V DC) | Decoupled Power Rail |
| **GND** | Power Ground | Power Subsystem | Common Star Junction | Zero-Volt Reference Plane | Common Ground |

---

## 2. ESP32-CAM AI-Thinker Pin Mapping

| GPIO Pin | Function | Peripheral Connection | Signal Voltage | Sourcing / Design Notes |
| :---: | :---: | :---: | :---: | :--- |
| **GPIO 1** | U0TXD | Debug/flash UART - NOT WIRED | 3.3V CMOS | `Serial` debug prints (115200); no link to Arduino in this build |
| **GPIO 3** | U0RXD | Debug/flash UART - NOT WIRED | 3.3V CMOS | Not connected; video leaves over Wi-Fi MJPEG instead |
| **GPIO 32** | Output | OV2640 PWDN | 3.3V CMOS | Camera Hardware Power-Down Control (`camera_stream.ino:12`) |
| **GPIO 0** | Output | OV2640 XCLK | 3.3V CMOS | Camera Master System Clock (20 MHz) |
| **GPIO 26** | Output | OV2640 SIOD | 3.3V CMOS | SCCB (I2C) Data Bus for Camera Configuration |
| **GPIO 27** | Output | OV2640 SIOC | 3.3V CMOS | SCCB (I2C) Clock Bus for Camera Configuration |
| **GPIO 35** | Input | OV2640 Y9 | 3.3V CMOS | Video DVP Data Bit 7 (MSB) |
| **GPIO 34** | Input | OV2640 Y8 | 3.3V CMOS | Video DVP Data Bit 6 |
| **GPIO 39** | Input | OV2640 Y7 | 3.3V CMOS | Video DVP Data Bit 5 |
| **GPIO 36** | Input | OV2640 Y6 | 3.3V CMOS | Video DVP Data Bit 4 |
| **GPIO 21** | Input | OV2640 Y5 | 3.3V CMOS | Video DVP Data Bit 3 |
| **GPIO 19** | Input | OV2640 Y4 | 3.3V CMOS | Video DVP Data Bit 2 |
| **GPIO 18** | Input | OV2640 Y3 | 3.3V CMOS | Video DVP Data Bit 1 |
| **GPIO 5** | Input | OV2640 Y2 | 3.3V CMOS | Video DVP Data Bit 0 (LSB) |
| **GPIO 25** | Input | OV2640 VSYNC | 3.3V CMOS | Vertical Frame Synchronization Pulse |
| **GPIO 23** | Input | OV2640 HREF | 3.3V CMOS | Horizontal Reference Line Timing |
| **GPIO 22** | Input | OV2640 PCLK | 3.3V CMOS | Pixel Data Clock |
| **GPIO 4** | Output | Onboard Flash LED | 3.3V High Current | High-brightness white LED (Illumination) |
| **GPIO 33** | Output | Red Status LED | 3.3V Active Low | Small rear diagnostic indicator |
| **5V** | Power In | Buck Converter 5V Out | 5.0V DC | Feeds onboard 3.3V LDO regulator (AMS1117-3.3) |
| **GND** | Ground | Common Star Junction | 0V Reference | Common Ground Rail |
