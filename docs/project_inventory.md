# Project Inventory & Codebase Audit

**Project:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Audit Date:** 2026-09-23  
**Status:** Baseline Codebase Inspected (Phase 0 Complete)

---

## 1. Executive Summary

This inventory documents all existing assets, software modules, firmware, configuration files, test data, and physical hardware specifications present in the repository prior to generating the automated documentation pipeline.

The repository currently contains a complete, working, unit-tested **proof-of-concept software prototype** where the ESP32-CAM streams video over Wi-Fi, a laptop executes AI perception (DETR / YOLOv8-World / Color / Mock) and decision logic in Python, and an Arduino UNO executes motor control and low-level ultrasonic safety override.

> [!IMPORTANT]
> **Core Architectural Gap Identified:**  
> The target specification in `GEMINI_MASTER_DOCUMENTATION_PROMPT.md` requires **all AI inference, visual perception, target position estimation, and decision making to reside directly on the ESP32**, with the Arduino executing safety/motor control, and the laptop restricted to development/telemetry/documentation only.  
> In contrast, the current codebase implements a **Laptop-in-the-loop** architecture. Running large transformer models (DETR ~41M params, ~1GB RAM) on an ESP32 microcontroller is computationally impossible. A tiny quantized edge model (e.g., TFLite Micro, Edge Impulse FOMO, ESP-DL) or hardware upgrade (ESP32-S3) is required for full edge autonomy.

---

## 2. File-by-File Inventory

| Path | File / Module | Purpose | Status | Reusable in Target Doc / System | Missing / Incomplete Info | Risks / Technical Debt |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/` | `README.md` | Academic proof-of-concept overview and CLI quickstart | Existing | High (architecture principles & calibration) | Lacks detailed mathematical derivations | Documents laptop-in-the-loop architecture |
| `/` | `requirements.txt` | Python runtime dependencies | Existing | High (needs docs stack additions: `python-docx`, `reportlab`, etc.) | Doc tools not yet included | Heavy ML dependencies (`torch`, `transformers`) tied to PC execution |
| `/` | `.env.example` | Network & COM port configuration | Existing | High | COM port varies per OS/machine | Port conflicts |
| `/` | `yolo11n.pt`, `yolo11s.pt`, `yolov8m-worldv2.pt`, `yolov8s-worldv2.pt` | Local PyTorch weights for YOLO / YOLO-World | Existing | Medium (for laptop baseline comparison) | None (weights present) | Large file sizes; cannot execute directly on ESP32 |
| `/weights/clip/` | `ViT-B-32.pt` | OpenAI CLIP ViT-B/32 weights for YOLO-World zero-shot text encoder | Existing | Low (PC only) | None | 353 MB; strictly PC only |
| `arduino/rover_controller/` | `rover_controller.ino` | Arduino UNO firmware for motor control, HC-SR04 sensing, timeout watchdog | Existing | Very High (fully functional) | Exact motor gear ratio & encoder support | Hardcoded 200 PWM default; no closed-loop wheel encoder feedback |
| `esp32/camera_stream/` | `camera_stream.ino` | ESP32-CAM firmware: OV2640 initialization, Wi-Fi MJPEG HTTP server on port 81 | Existing | High (for camera capture) | On-chip inference code; UART comm to Arduino | Currently only streams video to PC over Wi-Fi; does not send commands to Arduino |
| `config/` | `config.yaml` | Master system configuration (camera, AI, rover, serial, safety, nav) | Existing | High | Physical wheel diameter, motor current limits | Pinouts defined in code, not centralized |
| `config/` | `thresholds.yaml` | Physical calibration thresholds (ultrasonic zones, vision margins) | Existing | High | Real physical validation on rover chassis | Values marked as safe initial guesses [ASSUMPTION] |
| `docs/` | `architecture.md` | High-level data flow diagram (ASCII) | Existing | High (needs formal vector diagrams) | Detailed electrical & state diagrams | Outlines PC-in-the-loop flow |
| `docs/` | `edge_cases.md` | Perception, camera, nav, comm, and power failure modes | Existing | High | Formal FMEA table with RPN scores | Needs quantitative failure modes |
| `docs/` | `hardware_protocol.md`| ASCII specification of 9600 baud serial protocol | Existing | High | CRC / Checksum byte, packet framing | Raw single-char commands lack error-correction |
| `docs/` | `testing.md` | Unit test description & CPU benchmark summary | Existing | High | Hardware-in-the-loop (HIL) test plans | Benchmarks run on PC CPU only |
| `docs/` | `troubleshooting.md` | Common setup & communication failure resolution | Existing | High | Power rail brownout diagnosis | Brief qualitative guide |
| `software/` | `main.py` | Rover central coordination loop | Existing | High (for reference / PC bridge) | ESP32 firmware equivalent | Executes on laptop |
| `software/hardware/` | `arduino_serial.py` | Serial driver with reconnect & command validation | Existing | High | Direct UART ESP32-to-Arduino bridge | Laptop-hosted serial driver |
| `software/hardware/` | `esp32_stream.py` | MJPEG video stream decoder with watchdog | Existing | High | Local frame capture on ESP32 bus | Wi-Fi network latency overhead |
| `software/hardware/` | `frame_manager.py` | Multi-threaded image acquisition & enhancement (CLAHE) | Existing | High | On-chip ESP32 ISP equivalent | High memory footprint on PC |
| `software/perception/` | `detector.py`, `object_tracker.py`, `position_estimator.py`, `scene_analyzer.py` | Vision pipeline (HuggingFace DETR, Color blob, ByteTrack) | Existing | High (algorithmic reference) | Quantized TFLite Micro / ESP-DL model | DETR takes ~5.1s per frame on PC CPU; cannot run on ESP32 |
| `software/navigation/` | `decision_engine.py`, `gap_assessment.py`, `obstacle_avoidance.py`, `target_search.py` | Navigation state machine and steering commands | Existing | High (logic easily ported to C++/ESP32) | Continuous proportional control (currently discrete F/L/R/S) | Discrete commands cause oscillatory motion |
| `software/safety/` | `safety_manager.py`, `failsafe.py` | Multi-tier command validation and priority latching | Existing | High | Hardware interlock | Purely software-gated |
| `software/telemetry/` | `event_logger.py` | Telemetry logger to CSV and console | Existing | High | Flash/SD logging on rover | Writes to PC filesystem |
| `software/telemetry/` | `event_eval.py` | Dataset eval harness: telemetry parsing/validation, run segmentation, statistics, 10 safety/protocol invariants | Existing | High (analysing onboard logs) | Read-only analysis of PC-side logs | Reads `logs/events.csv`; proves nothing physical |
| `software/ai/` | `detection_metrics.py` | Pure multi-object scoring: IoU, confidence-ordered matching, precision/recall/F1, duplicate detection counting, multi-object recall, 101-point interpolated mAP@0.5 | Existing | High (offline detection gate) | Detection accuracy regression check | Scores labelled stills (`datasets/coco128`), not live video |
| `scripts/` | `benchmark.py` | CPU latency/RAM/FPS benchmark for the configured detector (ai.backend) | Existing | High | ESP32 micro-benchmark | Benchmarks PC only |
| `scripts/` | `evaluate.py` | CLI over `logs/events.csv`: report + `logs/eval.json`, exit 1 on invariant violation with `--strict` | Existing | High | Post-run log analysis on the rover | Software evidence only |
| `scripts/` | `eval_detection.py` | Labelled multi-object accuracy benchmark (COCO128): precision/recall/F1, multi-object recall, mAP@0.5, latency + H4 check → `logs/detection_eval.json` | Existing | High | Detection regression gate | Offline images, not on-robot |
| `scripts/` | `calibration.py` | Interactive terminal calibration instructions | Existing | High | Automated tuning script | Manual CLI prompts |
| `scripts/` | `dashboard.py` | Web UI for live stream & rover state | Existing | Medium | On-board rover telemetry display | Flask server running on PC |
| `tests/` | 26 test suites (`test_*.py`) | 288 pytest unit & scenario tests (all passing) | Existing | High | Physical hardware test harnesses | Tests run against mock objects |
| `logs/` | `benchmark.json` | Measured yolo11s CPU benchmark results (shipped default; DETR baseline in logs/benchmark_detr.json) | Existing | High | Edge AI benchmark data | p50 119-211 ms @320 closes the 1.0 s target-lock (H4) |
| `logs/` | `eval.json` | Dataset eval harness output for the collected run | Existing | Medium | On-rover run reports | ANALYSIS OF LOGGED DATA |
| `logs/` | `events.csv` | Sample telemetry logs | Existing | Medium | Comprehensive test flight records | Sample placeholder data |

---

## 3. Reusable Components for the Target System

1. **State Machine Logic (`decision_engine.py`):**
   - States: `IDLE`, `MANUAL`, `OBSERVE`, `SEARCHING`, `ALIGNING`, `APPROACHING`, `AVOIDING`, `STOPPED`, `EMERGENCY_STOP`, `ERROR`.
   - Clear transition rules based on normalized bounding box coordinates ($x_{center}$, $width_{ratio}$).
2. **Safety Hierarchy (`safety_manager.py` & `rover_controller.ino`):**
   - Dual-tier safety architecture: High-level software validation + Low-level independent microcontroller watchdog and ultrasonic emergency stop.
3. **Arduino Motor Controller (`rover_controller.ino`):**
   - Verified pin configuration for L298N dual H-bridge and HC-SR04 ultrasonic sensor.
   - Built-in 3000 ms communication watchdog.
4. **Physical Geometric Model & Zones:**
   - 3-Zone horizontal partitioning (Left: 0.0â€“0.33, Center: 0.33â€“0.66, Right: 0.66â€“1.0) with configurable tolerance ($\pm 0.06$).
   - Stop condition based on bounding box width ratio ($> 0.45$).
5. **Comprehensive Test Fixtures (`tests/test_scenarios.py`):**
   - 22 end-to-end scenarios covering obstacle intrusion, target loss, sensor disconnect, and comms timeout.

---

## 4. Missing Information & Verification Checklist

- [ ] **Exact ESP32 Board Model:** Documented as "AI-Thinker ESP32-CAM" in `.ino` and `README.md`, but chip revision, exact PSRAM size (2MB vs 4MB vs 8MB), and flash size need verification.
- [ ] **ESP32 Edge AI Model & Framework:** No TFLite Micro, Edge Impulse, or ESP-DL model currently exists in the repository. All AI runs in Python on PC.
- [ ] **ESP32-to-Arduino Physical Interconnect:** Currently communicates via PC (Wi-Fi to PC, USB Serial PC to Arduino). For true edge autonomy, direct hardware UART (ESP32 TX/RX $\leftrightarrow$ Arduino RX/TX with 3.3V/5V logic level shifting) must be physically wired and specified.
- [ ] **Motor Specifications:** Stall current, no-load current, rated voltage (e.g., standard TT yellow gear motors 3-6V, 1:48 gear ratio), and wheel diameter (typically 65mm).
- [ ] **Battery & Power Distribution:** Exact battery pack (e.g., 2S 18650 Li-ion 7.4V vs 3S 11.1V vs 4xAA), buck converter model (e.g., LM2596 / MP1584), and power decoupling.
- [ ] **Chassis Dimensions:** Currently assumed as 18 cm width, 22 cm length `[ASSUMPTION]`.

---

## 5. Risk Assessment

1. **AI Feasibility on Edge (Critical Risk):**
   - Attempting to run DETR or standard YOLO on an ESP32 microcontroller will result in out-of-memory crashes or freeze the processor.
   - *Mitigation:* Document the architectural reality transparently. Provide a dedicated comparative analysis (`AI_MODEL_COMPARISON.md`) contrasting PC-tethered deep learning models with edge-capable quantized micro-models (FOMO, MobileNetV1 0.25 int8, ESP-DL) and classical color-thresholding.
2. **Logic Level Mismatch (Hardware Risk - not applicable to this build):**
   - ESP32 GPIO operates at **3.3V logic**, whereas Arduino UNO operates at **5V logic** - but there is **no wired data link** between them (ESP32 is power-only: 5V/GND; video is Wi-Fi MJPEG; control is laptop USB serial).
   - Only if a direct ESP32-to-Arduino wire is ever added would a voltage divider (1k / 2k) or bidirectional logic level shifter be required; never jumper Arduino 5V TX straight into a 3.3V ESP32 GPIO.
3. **Power Rail Brownout (Hardware Risk):**
   - L298N driving inductive DC motor loads causes voltage sags that reset the Arduino UNO and cause ESP32 Wi-Fi/camera brownouts if powered from the same unfiltered 5V rail.
   - *Mitigation:* Document mandatory separate power rails / dedicated buck converters with common ground.
