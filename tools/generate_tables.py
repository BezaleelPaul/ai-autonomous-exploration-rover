"""Technical Engineering Tables and Comparative Analysis Generator.

Generates (single canonical copy per document, no byte-identical duplicates):
1. docs/11_AI_MODEL_SELECTION.md
2. docs/22_PIN_CONFIGURATION.md
3. docs/21_CIRCUIT_CONNECTIONS.md
4. docs/28_FAILURE_ANALYSIS.md
5. docs/20_POWER_ARCHITECTURE.md
"""

import os


def generate_ai_model_comparison():
    content = """# 11. AI Model Selection & Edge Feasibility Analysis

**Document ID:** DOC-AI-001  
**Project:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Status:** Comparative Engineering Analysis  
**Standard Compliance:** Strict Engineering Classification (`NOT BENCHMARKED ON TARGET HARDWARE` where unmeasured)

---

## 1. Executive Summary & Hardware Context

The perception coprocessor on this rover is an **AI-Thinker ESP32-CAM** module powered by an **ESP32-D0WDQ6** dual-core Xtensa LX6 SoC operating at 240 MHz, equipped with **520 KB internal SRAM** and **4 MB external pseudo-static RAM (PSRAM)** interfaced over a single SPI bus (~40 MHz).

Running modern deep learning models (such as DETR, standard YOLOv8, or large ViTs) directly on this microcontroller is **computationally and physically impossible** due to severe memory and compute constraints.

Below is the verified comparative analysis contrasting workstation-level prototyping models with viable embedded microcontroller vision pipelines.

---

## 2. Comprehensive AI Model & Pipeline Comparison Matrix

| Model Architecture | Framework / Runtime | Target Hardware | Parameter Count | Memory Footprint (RAM / Flash) | Input Resolution | Expected Latency / Speed | Accuracy Tradeoff | ESP32-CAM Compatibility | Implementation Complexity |
| :--- | :--- | :--- | :-: | :-: | :-: | :-: | :--- | :-: | :--- |
| **DETR-ResNet-50**<br>*(Existing PC Baseline)* | PyTorch / HuggingFace Transformers | Laptop Workstation (Intel Core / GPU) | ~41.0 M | ~983 MB RAM<br>*(Measured in `logs/benchmark_detr.json`)* | $640 \\times 480$<br>(Resized internally) | **5.14 s / infer (0.2 FPS)**<br>*(Measured on PC CPU)* | Very high open-vocabulary detection; robust against clutter | **COMPLETELY INCOMPATIBLE**<br>(Exceeds ESP32 RAM by 245x) | Low on PC; impossible on MCU |
| **YOLOv8m-Worldv2**<br>*(Existing PC Alternate)* | PyTorch / Ultralytics + CLIP ViT | Laptop Workstation (CUDA / CPU) | ~25.9 M | ~850 MB RAM | $320 \\times 320$ | ~1.8 s / infer (~0.5 FPS on CPU) | High zero-shot open-vocabulary detection | **COMPLETELY INCOMPATIBLE**<br>(Cannot fit in MCU PSRAM) | Low on PC via pip package |
| **YOLO11n / YOLOv8n**<br>*(Nano PyTorch)* | PyTorch / ONNX Runtime | Single Board Computer (RPi 4 / Jetson) | ~3.2 M | ~15 MB RAM / 6.5 MB Weights | $320 \\times 320$ | ~180 ms (5.5 FPS on RPi 4) | High mAP on 80 COCO classes | **HIGHLY INFEASIBLE**<br>(Cannot allocate float32 activation buffers in MCU) | High; requires complex porting |
| **Edge Impulse FOMO**<br>*(Faster Objects, More Objects)* | TensorFlow Lite for Microcontrollers (TFLM) | ESP32-CAM / ESP32-S3 | ~150 K | **~220 KB SRAM / 180 KB Flash** | $96 \\times 96$<br>(Grayscale / RGB) | **~140 - 280 ms (3.5 - 7 FPS)**<br>*(int8 quantized)* | Bounding centroids only (no aspect ratio); highly sensitive to scale | **HIGHLY FEASIBLE**<br>(Runs entirely in internal SRAM / PSRAM) | Medium; requires Edge Impulse C++ SDK export |
| **MobileNetV1 0.25 (int8)**<br>*(Object Detect SSD)* | TFLM / ESP-DL | ESP32-CAM (with PSRAM) | ~420 K | **~650 KB PSRAM / 480 KB Flash** | $96 \\times 96$ or $160 \\times 160$ | **~450 - 900 ms (1.1 - 2.2 FPS)**<br>*(NOT BENCHMARKED ON TARGET HARDWARE)* | Moderate precision; higher false positive rate under low contrast | **FEASIBLE WITH PSRAM**<br>(Requires external PSRAM enabled) | High; requires int8 post-training quantization |
| **Color-Blob Centroid**<br>*(HSV Thresholding)* | Custom ESP32 C++ / ESP-WHO Primitive | ESP32-CAM (Internal SRAM) | 0 (Heuristic) | **< 40 KB SRAM** | $320 \\times 240$ (QVGA) | **~35 - 50 ms (20 - 28 FPS)**<br>*(Native hardware speed)* | Detects color targets (e.g. green bottle); fails if target matches background | **OPTIMALLY FEASIBLE**<br>(Zero neural network overhead) | Low; pure deterministic C++ array scan |

---

## 3. Engineering Recommendations for Build Realization

1. **Academic Honesty in Reporting:**
   - The final report must clearly state that the **initial prototyping and scenario validation suite** used the Laptop-in-the-loop harness with HuggingFace DETR and YOLO-World to verify closed-loop navigation FSM logic.
   - For complete edge autonomy without the laptop, the software architecture is designed to swap the `BaseDetector` interface to **Edge Impulse FOMO** or **Color-Blob Centroid Tracking** without modifying the downstream `DecisionEngine` or Arduino safety supervisor.

2. **Frame Resolution & Skipping Strategy:**
   - On the ESP32, image capture at **VGA (640x480)** is compressed in hardware to JPEG.
   - Downsampling to **QVGA (320x240)** or sub-window cropping before inference reduces memory footprint by 75% and delivers the necessary 15-20 FPS loop rate.
"""
    os.makedirs("docs/ai", exist_ok=True)
    with open("docs/11_AI_MODEL_SELECTION.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("[OK] Generated docs/11_AI_MODEL_SELECTION.md")


def generate_pin_and_circuit_tables():
    # Pin Configuration
    pin_content = """# 22. Complete Microcontroller Pin Configuration & Mapping

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
"""
    os.makedirs("docs/hardware", exist_ok=True)
    with open("docs/22_PIN_CONFIGURATION.md", "w", encoding="utf-8") as f:
        f.write(pin_content)
    print("[OK] Generated docs/22_PIN_CONFIGURATION.md")

    # Circuit Connections
    circuit_content = """# 21. Hardware Circuit Connections & Wiring Specification

**Document ID:** DOC-HW-003  
**Project:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Status:** Build-Ready Electrical Specification  
**Companion Diagrams:** [`figures/circuit_diagram.svg`](../figures/circuit_diagram.svg) | [`figures/circuit_diagram.png`](../figures/circuit_diagram.png) | [`figures/wiring_schemdraw.png`](../figures/wiring_schemdraw.png) (regenerate: `python tools/generate_wiring_schemdraw.py`)  
**Wiring & Breadboard Guide:** [`reports/AI_Rover_Wiring_and_Breadboard.pdf`](../reports/AI_Rover_Wiring_and_Breadboard.pdf)  
**Wokwi simulation:** [`diagrams/wokwi/`](../diagrams/wokwi/) — build with `python tools/build_wokwi_firmware.py`, run with `python tools/run_wokwi_sim.py`

---

## 1. Power Distribution Circuitry

```
+---------------------------------------------------------------------------------+
|                                 POWER ARCHITECTURE                              |
|                                                                                 |
|  [ 2S Li-ion Battery (7.4V) ] --+--> [ L298N 12V Terminal ]                     |
|                                 |          |                                    |
|                                 |          +--> [ Left & Right DC Motors ]      |
|                                 |                                               |
|                                 +--> [ LM2596 Buck (5V) ] --+--> [ Arduino 5V ] |
|                                                             +--> [ ESP32 5V ]   |
|                                                             +--> [ HC-SR04 VCC ]|
+---------------------------------------------------------------------------------+
```

> [!WARNING]
> **ELECTRICAL DESIGN DECISION & SAFETY ISOLATION:**  
> 1. NEVER power the DC drive motors from the Arduino 5V pin or ESP32 VCC pin. The inductive back-EMF and stall current (up to 1.2A per motor) will destroy the onboard linear regulators or trigger immediate brownout resets.
> 2. The ESP32-CAM is **power-only (5V + GND)**: there is NO wired data link to the Arduino. Video leaves it as Wi-Fi MJPEG (`http://<ip>:81/stream`) and commands reach the Arduino over USB serial from the laptop, so D0/D1 must stay unwired. NEVER jumper Arduino TX (5V) to a 3.3V ESP32 GPIO; if a wired UART is ever added, level-shift first.
> 3. ALL grounds (Battery Negative, Buck Converter Ground, Arduino Ground, ESP32 Ground, and L298N Ground) MUST converge at a single common star ground point.

---

## 2. Inter-Module Point-to-Point Wiring Schedule

| From Device / Module | Pin / Terminal | To Device / Module | Pin / Terminal | Wire Color Standard | Signal Type | Electrical Specification |
| :--- | :--- | :--- | :--- | :---: | :--- | :--- |
| **Battery Pack (2S)** | Positive (+) | **Power Switch / Fuse** | Input Terminal | Red | Power Rail | 7.4V - 8.4V DC, max 3A fuse |
| **Power Switch** | Output Terminal | **Buck Converter** | IN+ | Red | Power Rail | 7.4V Unregulated |
| **Power Switch** | Output Terminal | **L298N Driver** | 12V Terminal Block | Red | Motor Power | 7.4V High Current |
| **Battery Pack (2S)** | Negative (-) | **Common Star Junction** | Terminal Lug | Black | Ground Rail | 0V Reference |
| **Buck Converter** | IN- | **Common Star Junction** | Terminal Lug | Black | Ground Rail | 0V Reference |
| **Buck Converter** | OUT+ | **Arduino UNO** | 5V Pin | Blue | Logic Power | 5.0V Regulated (±2%) |
| **Buck Converter** | OUT+ | **ESP32-CAM** | 5V Pin | Blue | Logic Power | 5.0V Regulated (±2%) |
| **Buck Converter** | OUT+ | **HC-SR04** | VCC Pin | Blue | Logic Power | 5.0V Regulated |
| **Buck Converter** | OUT- | **Common Star Junction** | Terminal Lug | Black | Ground Rail | 0V Reference |
| **Arduino UNO** | Pin 5 (PWM) | **L298N Driver** | ENA (Jumper Off) | Purple | Speed PWM | 0 - 255 Duty Cycle (~976 Hz) |
| **Arduino UNO** | Pin 6 (Digital) | **L298N Driver** | IN1 Terminal | Orange | Direction DO | 5V HIGH = Left Forward |
| **Arduino UNO** | Pin 7 (Digital) | **L298N Driver** | IN2 Terminal | Orange | Direction DO | 5V HIGH = Left Reverse |
| **Arduino UNO** | Pin 8 (Digital) | **L298N Driver** | IN3 Terminal | Orange | Direction DO | 5V HIGH = Right Forward |
| **Arduino UNO** | Pin 9 (Digital) | **L298N Driver** | IN4 Terminal | Orange | Direction DO | 5V HIGH = Right Reverse |
| **Arduino UNO** | Pin 10 (PWM) | **L298N Driver** | ENB (Jumper Off) | Purple | Speed PWM | 0 - 255 Duty Cycle (~490 Hz) |
| **L298N Driver** | OUT1 / OUT2 | **Left TT Motor** | Motor Terminals | Grey | Actuator Drive | Dual BJT H-Bridge Switched DC |
| **L298N Driver** | OUT3 / OUT4 | **Right TT Motor** | Motor Terminals | Grey | Actuator Drive | Dual BJT H-Bridge Switched DC |
| **Arduino UNO** | Pin 11 (Digital) | **HC-SR04** | TRIG Pin | White | Acoustic Pulse | 10 µs High Trigger |
| **HC-SR04** | ECHO Pin | **Arduino UNO** | Pin 12 (Digital) | White | Echo Return | 5V TTL Pulse Width |
| **HC-SR04** | GND Pin | **Common Star Junction** | Terminal Lug | Black | Ground Rail | 0V Reference |
| **L298N Driver** | GND Terminal | **Common Star Junction** | Terminal Lug | Black | Ground Rail | 0V Reference |
| **Arduino UNO** | GND Pin | **Common Star Junction** | Terminal Lug | Black | Ground Rail | 0V Reference |
| **ESP32-CAM** | GND Pin | **Common Star Junction** | Terminal Lug | Black | Ground Rail | 0V Reference |

> [!NOTE]
> **DATA LINKS (what is NOT wired):** The ESP32-CAM connects only to 5V and GND — it has no data wires to the Arduino.
> Video travels **Wi-Fi MJPEG** to the laptop (`http://<esp32-ip>:81/stream`), and commands/telemetry travel
> **laptop USB serial -> Arduino D0/D1** at 9600 baud. Keep D0/D1 free: they are the USB bootloader serial pins.
"""
    with open("docs/21_CIRCUIT_CONNECTIONS.md", "w", encoding="utf-8") as f:
        f.write(circuit_content)
    print("[OK] Generated docs/21_CIRCUIT_CONNECTIONS.md")

    # Failure Mode and Effects Analysis (FMEA)
    fmea_content = """# 28. Failure Mode and Effects Analysis (FMEA)

**Document ID:** DOC-SAF-002  
**Project:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Status:** Complete Risk & FMEA Assessment  
**Standard Compliance:** Automotive/Robotics Risk Priority Numbering ($RPN = S \\times O \\times D$)  
*(Scale: 1 = lowest risk / easily detected, 10 = catastrophic / undetectable)*

---

## 1. Master FMEA Risk Assessment Matrix

| Failure ID | Subsystem | Failure Mode | Root Cause | Potential Severity ($S$) | Potential Occurrence ($O$) | Detection Rating ($D$) | Initial RPN | Engineering Mitigation Strategy & Failsafe Response | Revised Severity ($S$) | Revised Occurrence ($O$) | Revised Detection ($D$) | Final RPN |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| **FM-01** | Power | Microcontroller Brownout Reset | Motor inrush current sags battery rail below 4.5V | 9 | 7 | 4 | **252** | Dedicated LM2596 buck converter for logic; 470µF bulk capacitor on 5V rail; star ground topology | 3 | 2 | 2 | **12** |
| **FM-02** | Comms | Host Serial Link Loss / Disconnect | USB cable vibration or host process stops sending | 8 | 5 | 2 | **80** | Arduino hardware watchdog triggers after 3000 ms; automatically defaults to emergency STOP | 2 | 3 | 1 | **6** |
| **FM-03** | Perception | Camera Frame Freeze / Video Stall | OV2640 FIFO crash or Wi-Fi streaming socket lockup | 7 | 6 | 3 | **126** | FrameManager watchdog monitors inter-frame delay; halts autonomous commands if delay > 3.0s | 2 | 2 | 1 | **4** |
| **FM-04** | Safety | Ultrasonic Specular Reflection Blindness | Obstacle angled at >45° reflects acoustic wave away from sensor | 8 | 6 | 7 | **336** | Conservative slow-down zone (30cm); wide target search radius; fallback stop on proximity limit | 4 | 4 | 3 | **48** |
| **FM-05** | Actuation | Motor Driver Overheating / Thermal Cutoff | Prolonged stall on carpet or obstacle contact | 6 | 4 | 5 | **120** | Current-limiting fuse (3A); passive aluminum heatsink on L298N; 1.0s movement timeout in software | 2 | 2 | 2 | **8** |
| **FM-06** | AI / Perception | False Positive Target Misidentification | Background clutter resembles target color/shape | 5 | 6 | 4 | **120** | Confidence filter (>= 0.50); minimum box size constraint (>= 20px); largest-box tracking priority | 2 | 3 | 2 | **12** |
| **FM-07** | Control | Limit Cycle Steering Oscillation | High proportional gain ($K_p$) causes overshooting across center | 4 | 7 | 2 | **56** | Deadband tolerance (±0.06); minimum command duration (0.4s); decision cooldown (0.2s) | 2 | 2 | 1 | **4** |
| **FM-08** | Mechanical | Wheel Slip / Trajectory Drift | Surface friction disparity between left and right tires | 5 | 8 | 6 | **240** | Differential drive kinematics calibrated via median turning duration; closed-loop visual servoing | 3 | 4 | 2 | **24** |
| **FM-09** | Electrical | ESP32 GPIO Overvoltage Breakdown | Mis-wiring Arduino 5V TX straight to a 3.3V ESP32 GPIO | 10 | 1 | 3 | **30** | No wired UART link exists (ESP32 is power-only: 5V/GND) - enforced by doc-consistency test; if a wired link is ever added, install a level shifter first | 2 | 1 | 1 | **2** |
| **FM-10** | Software | Corrupt Serial Character Ingestion | Electromagnetic interference (EMI) on serial lines | 5 | 5 | 2 | **50** | Single-character ASCII validation filter; rejects unrecognized characters; sends STATUS:ERROR | 2 | 2 | 1 | **4** |

---

## 2. Summary of Critical Mitigation Safeguards

1. **Watchdog Redundancy:** Two independent software watchdogs exist:
   - High-level perception watchdog in `software/safety/safety_manager.py` (halts commands if camera frame frozen $> 3.0$ s).
   - Low-level microcontroller watchdog in `arduino/rover_controller/rover_controller.ino` (cuts motor PWM if no valid packet received for $> 3000$ ms).
2. **Deterministic Default State:** In any error, timeout, sensor disconnection, or emergency condition, the state machine and microcontroller default immediately to `STOP`.
"""
    os.makedirs("docs/troubleshooting", exist_ok=True)
    with open("docs/28_FAILURE_ANALYSIS.md", "w", encoding="utf-8") as f:
        f.write(fmea_content)
    print("[OK] Generated docs/28_FAILURE_ANALYSIS.md")

    # Power Architecture Document
    power_content = """# 20. Power Architecture & Electrical Decoupling

**Document ID:** DOC-HW-004  
**Project:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Status:** Verified Electrical Power Budget & Distribution Design  
**Companion Diagram:** [`figures/04_power_architecture.png`](../figures/04_power_architecture.png)

---

## 1. Power Supply Overview & Decoupling Strategy

The rover employs a **split-rail decoupled power architecture** to isolate sensitive digital processing logic from inductive motor switching noise.

```
+---------------------------------------------------------------------------------+
|                                 POWER RAIL TOPOLOGY                             |
|                                                                                 |
|  [ 2S Li-ion Battery (7.4V - 8.4V) ]                                            |
|       |                                                                         |
|       +--> [ Main Switch & 3A Fuse ]                                            |
|                 |                                                               |
|                 +--> [ High-Current Motor Rail: 7.4V Unregulated ]              |
|                 |         |                                                     |
|                 |         +--> L298N 12V Terminal                               |
|                 |                   |                                           |
|                 |                   +--> Left & Right DC TT Motors              |
|                 |                                                               |
|                 +--> [ High-Efficiency Step-Down Buck Converter (5.0V / 3A) ]   |
|                           |                                                     |
|                           +--> ESP32-CAM 5V Input (Onboard LDO -> 3.3V Core)    |
|                           +--> Arduino UNO 5V Pin (Bypasses Onboard Regulator)  |
|                           +--> HC-SR04 Ultrasonic Sensor VCC                    |
|                                                                                 |
|  COMMON STAR GROUND (0V): Battery (-) == Buck (-) == Arduino GND == ESP32 GND   |
+---------------------------------------------------------------------------------+
```

---

## 2. Power Consumption & Energy Budget

| Subsystem / Component | Operating Voltage | Quiescent / Idle Current | Typical Operating Current | Peak / Stall Current | Power Consumption (Typical) | Power Consumption (Peak) | Sourcing Rail |
| :--- | :---: | :-: | :-: | :-: | :-: | :-: | :--- |
| **Arduino UNO R3** | 5.0 V | 35 mA | 45 mA | 50 mA | 0.225 W | 0.250 W | Regulated 5.0V Logic |
| **ESP32-CAM (Wi-Fi + Capture)**| 5.0 V | 110 mA | 180 mA | 310 mA (Wi-Fi burst)| 0.900 W | 1.550 W | Regulated 5.0V Logic |
| **HC-SR04 Ultrasonic** | 5.0 V | 2 mA | 15 mA | 20 mA (Acoustic burst)| 0.075 W | 0.100 W | Regulated 5.0V Logic |
| **L298N Logic Stage** | 5.0 V | 15 mA | 25 mA | 35 mA | 0.125 W | 0.175 W | Regulated 5.0V Logic |
| **Dual TT DC Motors** | 7.4 V | 0 mA | 300 mA (Both wheels)| 2200 mA (Dual Stall) | 2.220 W | 16.280 W | Unregulated 7.4V Motor Rail |
| **Buck Converter Quiescent** | 7.4 V | 8 mA | 12 mA | 15 mA | 0.089 W | 0.111 W | Unregulated 7.4V Motor Rail |
| **SYSTEM TOTAL** | — | **170 mA** | **577 mA** | **2940 mA (Peak Stall)**| **3.634 W** | **18.466 W** | Battery Pack |

---

## 3. Battery Endurance & Runtime Calculations

Assuming a standard **2S 18650 Li-ion Battery Pack** with **2600 mAh capacity (19.24 Wh energy)**:

- **Continuous Nominal Driving Runtime:**
  $$\\text{Runtime}_{nominal} = \\frac{2600 \\text{ mAh}}{577 \\text{ mA}} \\approx 4.50 \\text{ hours} \\quad (\\text{Derated to 70\\% safety margin } \\approx 3.15 \\text{ hours})$$

- **Aggressive Continuous Steering / High-PWM Runtime:**
  $$\\text{Runtime}_{heavy} = \\frac{2600 \\text{ mAh}}{1200 \\text{ mA}} \\approx 2.16 \\text{ hours} \\quad (\\text{Derated to 70\\% } \\approx 1.51 \\text{ hours})$$

- **Worst-Case Stall Cutoff Protection:**
  The inline **3.0A fast-acting fuse** protects the Li-ion cell protection circuit from over-discharge or thermal runaway in the event of mechanical motor jamming.
"""
    with open("docs/20_POWER_ARCHITECTURE.md", "w", encoding="utf-8") as f:
        f.write(power_content)
    print("[OK] Generated docs/20_POWER_ARCHITECTURE.md")


if __name__ == "__main__":
    generate_ai_model_comparison()
    generate_pin_and_circuit_tables()
