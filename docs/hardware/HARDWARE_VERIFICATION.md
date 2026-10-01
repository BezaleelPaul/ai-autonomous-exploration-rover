# Hardware Verification & Specification Matrix

**Document ID:** DOC-HW-001  
**Project:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Status:** Verification In Progress — Pending Physical Verification  
**Standard Compliance:** Strict Engineering Classification (`[VERIFIED IN CODE]`, `[TO VERIFY]`, `[ASSUMPTION]`, `[DESIGN DECISION]`, `[MEASURED]`)

---

## 1. Executive Status & Critical Blockers

```
================================================================================
                         HARDWARE INFORMATION REQUIRED
================================================================================
[!] CRITICAL: Exact ESP32 Board Revision and PSRAM capacity.
    - Code identifies board as AI-Thinker ESP32-CAM [VERIFIED IN CODE].
    - Exact chip (ESP32-D0WDQ6-V3 vs ESP32-S3), flash size (4MB vs 8MB),
      and PSRAM availability (none, 2MB, 4MB, 8MB) dictates whether on-device
      edge AI inference is technically feasible or requires external acceleration.

[!] CRITICAL: Keep the ESP32<->Arduino data link ABSENT (power-only ESP32).
    - Design wiring: ESP32-CAM gets 5V + GND only; video leaves as Wi-Fi MJPEG
      and commands go laptop -> Arduino over USB serial (9600 baud).
    - NEVER jumper Arduino 5V TX to a 3.3V ESP32 GPIO (permanent damage).
      If a wired UART is ever added, fit a level shifter first.

[!] CRITICAL: Power Distribution & Ground Loop Decoupling.
    - L298N motor driver voltage drop is 1.8V to 3.2V (bipolar Vce(sat)).
    - Motor inductive noise causes severe brownout resets on ESP32 & Arduino.
    - Dedicated buck converter or dual-battery isolation required.
================================================================================
```

---

## 2. Hardware Subsystem Specifications

### 2.1 Arduino Microcontroller Subsystem

| Parameter | Specification | Status / Source | Notes |
| :--- | :--- | :--- | :--- |
| **Exact Board Model** | Arduino UNO R3 (ATmega328P DIP/SMD) | `[VERIFIED IN CODE]` (`rover_controller.ino`, `README.md`) | Standard 16 MHz 8-bit AVR architecture |
| **Operating Voltage** | 5.0 V DC | `[VERIFIED DATASHEET]` | Microcontroller VCC |
| **Input Voltage (VIN / Barrel)** | 7.0 V – 12.0 V DC | `[ASSUMPTION]` | Via on-board linear regulator (NCP1117ST50) |
| **Flash Memory** | 32 KB (0.5 KB used by bootloader) | `[VERIFIED DATASHEET]` | Firmware footprint ~4.2 KB (13%) |
| **SRAM** | 2 KB | `[VERIFIED DATASHEET]` | Dynamic memory usage ~320 bytes (16%) |
| **EEPROM** | 1 KB | `[VERIFIED DATASHEET]` | Not currently utilized |
| **Clock Frequency** | 16.0 MHz (Ceramic Resonator / Crystal) | `[VERIFIED DATASHEET]` | Base clock for PWM timers |
| **PWM Pins Allocated** | Pin 5 (Timer0 PWM0B, ~976 Hz) - ENA<br>Pin 10 (Timer1 PWM1B, ~490 Hz) - ENB | `[VERIFIED IN CODE]` (`rover_controller.ino:13,18`) | Hardware PWM pins controlling motor enable lines |
| **Digital GPIO Allocated** | Pin 6 (IN1), Pin 7 (IN2), Pin 8 (IN3), Pin 9 (IN4)<br>Pin 11 (TRIG), Pin 12 (ECHO) | `[VERIFIED IN CODE]` (`rover_controller.ino:14-17,21-22`) | Direction control and ultrasonic timing |
| **Hardware Serial Interface** | Pin 0 (RX), Pin 1 (TX) at 9600 baud, 8-N-1 | `[VERIFIED IN CODE]` (`rover_controller.ino:35`) | Currently connected via USB-UART bridge to PC |

---

### 2.2 ESP32 Edge Perception Subsystem

| Parameter | Specification | Status / Source | Notes |
| :--- | :--- | :--- | :--- |
| **Exact Board Model** | AI-Thinker ESP32-CAM module | `[VERIFIED IN CODE]` (`camera_stream.ino:2`, `README.md:11`) | Standard commercial clone module |
| **Core SoC Chip** | ESP32-D0WD / ESP32-D0WDQ6 (Xtensa dual-core 32-bit LX6) | `[TO VERIFY]` | Physical chip markings must be verified on module |
| **CPU Frequency** | 240 MHz (Configured in Arduino IDE board profile) | `[ASSUMPTION]` | Required for JPEG compression throughput |
| **Internal SRAM** | 520 KB (328 KB allocatable heap) | `[VERIFIED DATASHEET]` | Shared between Wi-Fi stack and user tasks |
| **External PSRAM** | 4 MB / 8 MB (typically AP_Memory 3.3V/1.8V) | `[TO VERIFY]` | Critical: required for frame buffer allocation (`fb_count=2`) |
| **Flash Memory** | 4 MB SPI Flash (typically Winbond 25Q32) | `[TO VERIFY]` | Limits firmware partition size |
| **Camera Sensor** | OmniVision OV2640 (2 Megapixel CMOS image sensor) | `[VERIFIED IN CODE]` (`camera_stream.ino:12-28`) | AI-Thinker default pin definition |
| **Camera Interface** | 8-bit DVP (Digital Video Port) parallel + SCCB (I2C) | `[VERIFIED IN CODE]` | Consumes GPIO 0, 5, 18, 19, 21, 22, 23, 25, 34-39 |
| **Active Camera Resolution** | VGA (640 $\times$ 480) | `[VERIFIED IN CODE]` (`camera_stream.ino:66`) | Framerate ~12-15 FPS in JPEG mode |
| **Pixel Format** | `PIXFORMAT_JPEG` | `[VERIFIED IN CODE]` (`camera_stream.ino:65`) | Compressed in hardware by OV2640 DSP |
| **Supported AI Framework** | ESP-DL, TensorFlow Lite for Microcontrollers (TFLM), Edge Impulse | `[DESIGN DECISION]` | **Cannot run DETR, ResNet, or YOLOv8 natively on chip** |
| **Available Spare GPIOs** | GPIO 1 (U0TXD), GPIO 3 (U0RXD), GPIO 16 (U2RXD/Flash), GPIO 33 (LED) | `[TO VERIFY]` | ESP32-CAM has extremely limited free I/O due to DVP |

---

### 2.3 DC Motors & Drivetrain

| Parameter | Specification | Status / Source | Notes |
| :--- | :--- | :--- | :--- |
| **Motor Type** | Dual TT Yellow Gearbox DC Motors | `[ASSUMPTION]` | Standard dual-shaft hobby robot motors |
| **Operating Voltage** | 3.0 V – 6.0 V DC (Nominal 6.0 V) | `[TO VERIFY]` | Higher voltage increases RPM and torque |
| **Gear Reduction Ratio** | 1:48 (common) or 1:120 | `[TO VERIFY]` | Directly affects angular velocity and stall torque |
| **No-Load Current** | ~70 mA – 150 mA per motor | `[ASSUMPTION]` | Measured at 6.0 V |
| **Stall Current** | ~800 mA – 1.2 A per motor at 6.0 V | `[TO VERIFY]` | Peak current during motor stall or direction reversal |
| **Wheel Diameter ($2r$)** | 65 mm (0.065 m) | `[ASSUMPTION]` | Standard plastic rim with rubber tread tire |
| **Wheel Radius ($r$)** | 32.5 mm (0.0325 m) | `[ASSUMPTION]` | Used in kinematic equations |
| **Track Width ($L$)** | 180 mm (0.18 m) | `[VERIFIED IN CODE]` (`config.yaml:55`, `thresholds.yaml:21`) | Center-to-center distance between driving wheels |
| **Wheel Encoders** | None present in baseline hardware | `[VERIFIED IN CODE]` (`rover_controller.ino`) | Open-loop PWM control only |

---

### 2.4 Motor Driver Subsystem

| Parameter | Specification | Status / Source | Notes |
| :--- | :--- | :--- | :--- |
| **Driver IC / Module** | L298N Dual Full-Bridge Driver Module | `[VERIFIED IN CODE]` (`rover_controller.ino:12-18`) | Multiwatt15 package on red breakout board |
| **Driver Topology** | Bipolar junction transistor (BJT) H-bridge | `[VERIFIED DATASHEET]` | STMicroelectronics L298N |
| **Motor Supply Voltage ($V_S$)**| 7.4 V – 12.0 V DC | `[TO VERIFY]` | Connected to L298N 12V terminal block |
| **Logic Supply Voltage ($V_{SS}$)**| 5.0 V DC | `[VERIFIED DATASHEET]` | Via on-board 78M05 regulator or Arduino 5V |
| **Internal Voltage Drop** | 1.8 V (typical at 1A) to 3.2 V (max at 2A) | `[VERIFIED DATASHEET]` | Inherent BJT saturation loss ($V_{CE(sat)}$) |
| **Max Continuous Current** | 2.0 A per channel (with heatsink) | `[VERIFIED DATASHEET]` | Sufficient for TT motors |
| **Control Logic Inputs** | IN1, IN2 (Motor A), IN3, IN4 (Motor B), 5V TTL | `[VERIFIED IN CODE]` | Direct 5V logic from Arduino UNO |
| **PWM Speed Pins** | ENA, ENB (jumpers removed, connected to PWM) | `[VERIFIED IN CODE]` | Controlled via `analogWrite(5/10, speed)` |

---

### 2.5 Ultrasonic Distance Sensor Subsystem

| Parameter | Specification | Status / Source | Notes |
| :--- | :--- | :--- | :--- |
| **Sensor Model** | HC-SR04 Ultrasonic Ranging Module | `[VERIFIED IN CODE]` (`rover_controller.ino:20-22`) | Standard 40 kHz transducer pair |
| **Operating Voltage** | 5.0 V DC | `[VERIFIED DATASHEET]` | Requires 5V; unstable below 4.5V |
| **Operating Current** | 15 mA (quiescent < 2 mA) | `[VERIFIED DATASHEET]` | Powered from Arduino 5V rail |
| **Ranging Range** | 2.0 cm – 400.0 cm | `[VERIFIED IN CODE]` (`thresholds.yaml:9-10`) | Effective cone angle ~15 degrees |
| **Resolution** | 0.3 cm | `[VERIFIED DATASHEET]` | Acoustic pulse timing resolution |
| **Trigger Pin** | Arduino Digital Pin 11 | `[VERIFIED IN CODE]` (`rover_controller.ino:21`) | 10 µs HIGH pulse emitted |
| **Echo Pin** | Arduino Digital Pin 12 | `[VERIFIED IN CODE]` (`rover_controller.ino:22`) | 5V TTL return pulse, timed via `pulseIn()` |
| **Measurement Timeout** | 30,000 µs (~5.14 m max range) | `[VERIFIED IN CODE]` (`rover_controller.ino:47`) | Prevents CPU lockup on echo loss |
| **Emergency Stop Distance** | 15.0 cm | `[VERIFIED IN CODE]` (`rover_controller.ino:25`) | Hard threshold: immediate motor cutoff |

---

### 2.6 Power Supply & Energy Storage

| Parameter | Specification | Status / Source | Notes |
| :--- | :--- | :--- | :--- |
| **Battery Chemistry** | 2S 18650 Li-ion / 3S Li-ion / 6xAA NiMH | `[TO VERIFY]` | Physical pack not documented in repo |
| **Nominal Pack Voltage** | 7.4 V (2S) or 11.1 V (3S) | `[TO VERIFY]` | Determines available motor torque & regulator headroom |
| **Pack Capacity** | 2000 mAh – 3000 mAh | `[ASSUMPTION]` | Estimated runtime ~45–75 minutes |
| **Maximum Discharge Current**| $\ge 5.0$ A (2C continuous) | `[ASSUMPTION]` | Required to absorb dual motor stall spikes |
| **Voltage Regulation (Logic)** | Step-down Buck Converter (e.g. LM2596 / MP1584) to 5.0V | `[DESIGN DECISION]` | Required to supply clean 5V/2A to ESP32 & Arduino |
| **Voltage Regulation (Motors)**| Unregulated battery rail or 6V dedicated buck | `[DESIGN DECISION]` | Isolates motor switching spikes from microcontroller |

---

## 3. Physical Verification Checklist for Student/Engineer

```
================================================================================
                    HARDWARE INFORMATION REQUIRED CHECKLIST
================================================================================
Please inspect the physical robot assembly and record the following:

[ ] 1. ESP32 Board & Module:
       - Exact chip label: _________________________________________
       - PSRAM present (ESP32-CAM AI-Thinker usually has 4MB/8MB): __
       - Flash size (MB): __________________________________________

[ ] 2. Power Source:
       - Exact battery chemistry: [ ] 2S Li-ion  [ ] 3S Li-ion  [ ] 4xAA  [ ] 6xAA
       - Nominal battery voltage (V): _______________________________
       - Rated capacity (mAh): ______________________________________
       - Voltage regulator module used for 5V logic: ________________

[ ] 3. Drive Motors & Mechanical:
       - Motor model / color: [ ] Yellow TT Gearbox  [ ] Other: _____
       - Gear ratio: [ ] 1:48  [ ] 1:120  [ ] Other: ________________
       - Measured wheel diameter (mm): _____________________________
       - Measured track width between wheel centers (mm): ___________
       - Measured chassis overall length (mm): ______________________

[ ] 4. ESP32 Wiring Is Power-Only (No UART Link):
       - Is the ESP32-CAM connected ONLY to 5V and GND? [ ] YES  [ ] NO
       - Are Arduino D0/D1 free of any jumper (USB serial only)? [ ] YES  [ ] NO
       - If a wired UART was added anyway, is a level shifter fitted? [ ] YES  [ ] NO

[ ] 5. Sensor Mounting:
       - Height of HC-SR04 from ground (cm): _______________________
       - Forward tilt angle of ESP32-CAM (degrees): ________________
================================================================================
```
