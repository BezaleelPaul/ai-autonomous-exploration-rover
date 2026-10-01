# Engineering Feasibility & Project Risk Audit

**Document ID:** AUDIT-001  
**Project:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Audit Phase:** Initial Inspection & Baseline Verification  
**Audit Standard:** Strict Engineering Risk Classification (No subjective or marketing ratings)

---

## 1. Technical Feasibility Analysis

### 1.1 Core Architecture Evaluation
The project objective is a distributed edge-robotic platform where:
1. High-level visual perception and target estimation run on an ESP32 microcontroller.
2. Low-level motor actuation, safety override, and sensor watchdogs run on an Arduino UNO.
3. The rover operates completely autonomously without tethering to a laptop for live inference.

**Feasibility Verdict:** **FEASIBLE WITH CONSTRAINTS**.  
Distributed dual-microcontroller architectures (sensor/perception coprocessor + motor/safety supervisor) are industry-standard in robotics. However, feasibility hinges entirely on the computational limits of the perception coprocessor (ESP32) and the communication interface.

---

## 2. Hardware Feasibility

| Item | Physical Assessment | Engineering Feasibility & Risk |
| :--- | :--- | :--- |
| **Arduino UNO R3** | 16 MHz ATmega328P, 2KB SRAM, 32KB Flash | **FEASIBLE**. Ample headroom for 2-channel PWM generation, HC-SR04 pulse timing, and 9600 baud state machine. |
| **L298N Dual H-Bridge** | Dual bipolar H-bridge with internal ~2V drop | **FEASIBLE BUT INEFFICIENT**. Bipolar transistor drop generates heat and reduces motor voltage. Acceptable for low-cost student rovers, but MOSFET-based drivers (e.g. TB6612FNG) would be far more efficient. |
| **HC-SR04 Ultrasonic** | 40 kHz acoustic ranging, 2cm–400cm range | **FEASIBLE**. Direct line-of-sight safety barrier. Narrow 15° beam angle leaves lateral blind spots. |
| **ESP32-CAM (AI-Thinker)**| 240 MHz dual-core LX6, 520KB SRAM + 4MB external PSRAM | **FEASIBLE FOR TINY CNN / COLOR BLOBS; INFEASIBLE FOR TRANSFORMERS/YOLO**. External PSRAM over SPI bandwidth (~40 MHz) limits frame processing throughput. |
| **Electrical Interconnect** | ESP32 (3.3V logic) to Arduino UNO (5V logic) | **CRITICAL RISK IF UNPROTECTED**. Arduino TX (5V) will overvolt ESP32 RX (3.3V max). Level shifting is mandatory. |
| **Power Distribution** | Single battery vs Dual rail | **HIGH BROWNOUT RISK**. DC motor inductive spikes and stall currents pull rail voltage below 4.5V, resetting Arduino and causing ESP32 Wi-Fi/brownout aborts. |

---

## 3. AI Feasibility (The Core Engineering Reality)

### 3.1 Existing Repository State vs. Target Specification
- **In Current Repository:** AI inference runs in Python on a laptop; shipped default (`ai.backend: yolo`) is `yolo11s.pt` (Ultralytics), with `facebook/detr-resnet-50` retained as the `hf` accuracy option. Measured CPU benchmarks:
  - **yolo11s (shipped, imgsz 320):** load **0.4 s**, p50 **119-211 ms/frame** (~3.8-6.7 FPS), RSS ~450 MB — `logs/benchmark.json`; closes the 1.0 s target-lock at `inference_interval: 2`.
  - **DETR-ResNet-50 (`hf`, prior baseline):** load **26.7 s**, mean **5.14 s/frame** (0.2 FPS), RSS **983.2 MB** — `logs/benchmark_detr.json`; offline accuracy runs only (NOT realtime).
- **Target Specification:** Autonomous edge AI running directly on the ESP32 without laptop involvement.

### 3.2 Quantitative Feasibility Analysis of Edge AI on ESP32

```
+---------------------------+-------------------+-----------------+-----------------------+
| Model / Pipeline          | Memory Footprint  | Target Platform | Feasibility on ESP32  |
+---------------------------+-------------------+-----------------+-----------------------+
| DETR-ResNet-50            | ~980 MB           | Workstation / PC| IMPOSSIBLE (Exceeds   |
| (HF accuracy option)      |                   |                 | PSRAM by 245x)        |
+---------------------------+-------------------+-----------------+-----------------------+
| YOLOv8n / YOLO11n         | ~12 MB - 25 MB    | Jetson / RPi    | INFEASIBLE on ESP32   |
| (PyTorch float32)         |                   |                 | (Insufficient SRAM)   |
+---------------------------+-------------------+-----------------+-----------------------+
| Edge Impulse FOMO         | ~150 KB - 300 KB  | ESP32-CAM       | FEASIBLE              |
| (int8 quantized)          |                   | (PSRAM / SRAM)  | (~3 - 7 FPS at 96x96) |
+---------------------------+-------------------+-----------------+-----------------------+
| MobileNetV1 0.25 (TFLM)   | ~300 KB - 500 KB  | ESP32-CAM       | FEASIBLE              |
| (int8 quantized)          |                   | (PSRAM)         | (~1 - 3 FPS at 96x96) |
+---------------------------+-------------------+-----------------+-----------------------+
| Color-Blob / Centroid     | < 50 KB           | ESP32-CAM       | HIGHLY FEASIBLE       |
| Visual Servoing (HSV)     |                   | (Internal SRAM) | (15 - 25 FPS at QVGA) |
+---------------------------+-------------------+-----------------+-----------------------+
```

**Conclusion on AI:**  
The documentation must strictly distinguish between the **Laptop-hosted prototyping harness** (demonstrated in the existing code) and the **Embedded Edge deployment architecture** (which requires int8 quantized micro-models such as FOMO or MobileNetV1 on TFLite Micro / ESP-DL).

---

## 4. Software Feasibility

- **State Machine (`decision_engine.py`):** Clean separation of states (`IDLE`, `MANUAL`, `OBSERVE`, `SEARCHING`, `ALIGNING`, `APPROACHING`, `AVOIDING`, `STOPPED`, `EMERGENCY_STOP`, `ERROR`). Easily implemented in C++ on ESP32.
- **Safety Manager (`safety_manager.py`):** Well-structured multi-priority latching.
- **Arduino Firmware (`rover_controller.ino`):** Fully operational, non-blocking timing with `millis()`, local 3-second watchdog, and 200ms telemetry output.
- **Test Suite:** 35 passing pytest unit tests covering edge cases, state transitions, and mock perception.

---

## 5. Safety Architecture Evaluation

1. **Hardware / Microcontroller Priority (Tier 1):**
   - Obstacle $< 15$ cm $\rightarrow$ Immediate motor cutoff.
   - Comm timeout $> 3000$ ms $\rightarrow$ Immediate motor cutoff.
   - Unknown command $\rightarrow$ Return error and maintain stop.
2. **Software Priority (Tier 2):**
   - Camera frame frozen $> 3.0$ s $\rightarrow$ Stop.
   - Target confidence $< 0.50$ $\rightarrow$ Reject tracking, fallback to search.
   - Bounding box width ratio $> 0.45$ $\rightarrow$ Target reached stop.

**Safety Verdict:** **STRONG ARCHITECTURE**. Dual-layer independence guarantees that a failure of the perception coprocessor or serial link defaults safely to `STOP`.

---

## 6. Research & Documentation Quality

- Academic rigor: Requires strict avoidance of unsupported marketing claims.
- All unmeasured hardware values must be explicitly classified as `[ASSUMPTION]` or `[TO VERIFY]`.
- All simulated control responses must be explicitly watermarked as `SIMULATION — NOT MEASURED HARDWARE DATA`.

---

## 7. Time & Cost Risk Assessment

- **Time Risk (High):** Porting complete neural network inference firmware to ESP-IDF / Arduino C++ on ESP32 requires model quantization, calibration, and memory partition management.
- **Cost Risk (Very Low):** All hardware components (ESP32-CAM, Arduino UNO, L298N, HC-SR04, TT Motors) are commodity educational components with total bill of materials $< \$35$ USD.

---

## 8. Engineering Risk Classification

### CRITICAL BLOCKERS (Must Resolve Before Real-World Autonomous Edge Operation)
1. **Clarify AI Deployment Reality:**
   - Acknowledge that current repo code runs heavy AI models (DETR/YOLO) on the Laptop via Wi-Fi stream.
   - For autonomous on-ESP32 AI, specify the target edge runtime: int8 quantized TinyML (Edge Impulse / TFLM / ESP-DL) or color-centroid visual servoing.
2. **Verify Physical ESP32 Board & PSRAM:**
   - Confirm whether the physical ESP32 module has external PSRAM operational. Without PSRAM, even frame buffering at VGA is constrained.
3. **Logic Level Shifting:**
   - Ensure a 5V-to-3.3V divider is used on the Arduino TX $\rightarrow$ ESP32 RX UART line to prevent hardware destruction.

### HIGH PRIORITY (Must Resolve for Document & Code Completeness)
1. Physical measurement of TT motor stall current and battery pack chemistry.
2. Installation and wiring of hardware serial link between ESP32 and Arduino UNO (bypassing PC).
3. Calibration of ultrasonic distance thresholds against ground reflection angles.

### MEDIUM PRIORITY
1. Transition from open-loop timed turns (`turning_duration_s: 0.5`) to closed-loop wheel encoder feedback or IMU (e.g. MPU6050) — **moved to [`future-work/30_FUTURE_WORK.md`](future-work/30_FUTURE_WORK.md)** (started 2026-09-25).
2. Replacement of L298N with high-efficiency MOSFET driver (TB6612FNG) to prevent 2V drop.

### OPTIONAL EXTENSIONS
**Moved to [`future-work/30_FUTURE_WORK.md`](future-work/30_FUTURE_WORK.md):** 360-degree discrete panoramic scanning with servo-mounted camera; two-wheel inverted pendulum self-balancing study.
