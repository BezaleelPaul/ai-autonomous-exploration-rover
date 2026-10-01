# AI Visual Smart Rover — SEE → UNDERSTAND → DECIDE → ACT → STAY SAFE

Low-cost academic proof-of-concept: ESP32-CAM (video) + Laptop (AI/vision/decisions)
+ Arduino UNO (motors/ultrasonic safety) + L298N + HC-SR04. No SLAM/LiDAR/ROS/training.

## 1. Overview / Architecture
See docs/architecture.md. Closed loop PERCEPTION→DECISION→SAFETY→CONTROL→FEEDBACK.
Every autonomous command passes through SafetyManager; Arduino enforces its own stop.

## 2. Hardware
ESP32-CAM AI-Thinker, Arduino UNO, L298N, 2x DC motors, HC-SR04 front, optional SG90.

## 3. Software stack
Python 3.10+, OpenCV, NumPy, PySerial, PyYAML; AI: ultralytics YOLO (primary) or
torch+transformers (DETR, accuracy option) or no-model modes (mock/color).
Arduino C++ / ESP32 Arduino. Optional Flask dashboard.

## 4. Installation
```
pip install -r requirements.txt
cp .env.example .env   # set ports/URLs
```

## 5. Python / Model setup
Primary (control loop): `yolo11s.pt` behind `BaseDetector` interface
(label/score/bbox + center_x/y/width/height). Weights ship in the repo root —
fully offline, no download:
```
python scripts/benchmark.py --runs 10    # latency/FPS/CPU/RAM -> logs/benchmark.json
```
Measured (CPU, imgsz 320, `logs/benchmark.json`): p50 211 ms @640x480 (3.8 FPS),
119 ms @320x240, load 0.4 s. With `inference_interval: 2` the detection refresh
(~0.5 s worst case) stays under the 1.0 s target-lock, so visual servoing closes
in real time (red-team H4 — enforced by `tests/test_redteam_h4_realtime.py`).

Multi-object accuracy is benchmarked on labelled COCO128 images with
`python scripts/eval_detection.py`. Shipping `confidence_threshold 0.25` +
`min_box_px 8` (with `yolo_imgsz` held at 320 for the realtime gate) measured
recall 0.352→0.477, multi-object recall 0.347→0.471, F1 0.509→0.601 and
mAP@0.5 0.618→0.640 — evidence in `logs/detection_baseline.json` vs
`logs/detection_final.json`. Latency is load-sensitive: p50 184 ms at 50 % CPU
load (0.37 s refresh, H4 green) but 534–685 ms at 100 % CPU load (1.07–1.37 s
refresh, H4 red), so the realtime gate is run with the host at ≤~60 % load.
imgsz 480 measured better (recall 0.559) but breaks the 1.0 s lock on a loaded
host (p50 577 ms at 100 % CPU), so it was rejected; `ai.target_confidence: 0.5`
keeps the driving gate at its original value while the detector reports more.
Swap models via config only (`ai.yolo_model`, `ai.backend`) — no nav/safety/serial
changes. `backend: hf` keeps `facebook/detr-resnet-50` (measured ~5.1 s/infer —
accuracy/offline use, NOT realtime; DETR numbers in `logs/benchmark_detr.json`).
`backend: mock` (no weights) and `color` (opencv green-blob) fallbacks kept.

## 6. ESP32 setup
Flash esp32/camera_stream/camera_stream.ino (set WIFI_SSID/PASS), note IP,
set config.yaml camera.esp32_url. Verify in browser.

## 7. Arduino setup
Flash arduino/rover_controller/rover_controller.ino, set config.yaml serial.port.

## 8. Configuration
config/config.yaml (all subsystems) + config/thresholds.yaml (calibration values).

## 9. Running
```
python software/main.py --mock --mode observe            # no hardware
python software/main.py --mode manual                    # W/A/S/D + SPACE, Q quit
python software/main.py --mode observe --target bottle
python software/main.py --mode search --target bottle
python software/main.py --mode scan360 --target bottle
python software/main.py --mode observe --dashboard       # + web status
```

## 10-14. Modes
Manual (safety-gated), Observe (align+approach), Target Search (rotate≤timeout/
rotations then report), 360° scan (scan360), obstacle safety demo (AI GO vs
ultrasonic STOP → STOP wins).

## 15. Safety
Priority: emergency latch > sensor > comms > validity > confidence > objective.
Camera/serial loss, invalid sensor, low confidence → STOP. See docs/edge_cases.md.

## 16. Testing
`python -m pytest tests -q` → 311 passed (mock, no hardware, Python 3.12).
Both run commands work: `python software/main.py ...` and
`python -m software.main ...`. Scenarios in
tests/test_scenarios.py (22 cases). Docs: docs/testing.md.

The firmware also runs in the Wokwi simulator (project in `diagrams/wokwi/`,
guard tests in `tests/test_wokwi_sim.py`):
```
python tools/build_wokwi_firmware.py                     # arduino-cli -> diagrams/wokwi/build/
python tools/run_wokwi_sim.py --scenario scenarios/safety.yaml
python tools/run_wokwi_sim.py --scenario scenarios/obstacle_gate.yaml
```
Measured 2026-09-27 (wokwi-cli v0.27.1): both scenarios PASS — boot = STOP,
`X` rejected with `STATUS:ERROR`, `F` actuates the bridge, 3 s watchdog →
`STATUS:STOP` + bridge released, and at 10 cm the firmware refuses `F`
(`STATUS:STOP`, IN1 stays low). Needs `wokwi-cli` and a free
`WOKWI_CLI_TOKEN` (https://wokwi.com/dashboard/ci); without them
`run_wokwi_sim.py` stops with that exact instruction instead of pretending
to simulate.

Fast dev loop (ruff + pytest in ~25 s):
```
python tools/dev.py              # gates once; --quick = pytest -x
python tools/dev.py --watch      # re-run gates on every file change
python tools/dev.py --hw         # gates + hardware checks (board attached)
```
Real-circuit checks (board attached; auto-detects the COM port):
`python tools/hw_check.py ports|flash|serial|mon|esp32|all` — exits 0/1/2
(pass/fail/skip). Serial port auto-detects on connect, so a stale
`serial.port` in config/config.yaml cannot brick the session.

Post-run analysis of the collected telemetry:
`python scripts/evaluate.py` (reads logs/events.csv, checks 10 protocol/safety
invariants, writes logs/eval.json; `--strict` fails the run on a violation).

Detection accuracy against labelled ground truth:
`python scripts/eval_detection.py` (COCO128, 128 images; precision/recall/F1,
multi-object recall, mAP@0.5, latency + H4 check → logs/detection_eval.json).

Detection and driving are deliberately separate dials: `ai.confidence_threshold`
(0.25) sets which objects are *reported*, `ai.target_confidence` (0.5) sets
which ones the rover steers toward and drives forward on (`LOW_CONFIDENCE`
safety gate). Lowering the first improves multi-object recall without letting
the rover approach weaker detections.

## 17. Troubleshooting
See docs/troubleshooting.md.

## 18. Known limitations
Single camera (no depth; size≈proximity heuristic only), HC-SR04 narrow FOV,
lighting-sensitive detection, no SLAM/localization/GPS/encoders, motor asymmetry,
approximate gap check. Proof-of-concept, not collision-free; never claim 100%.

## 19. Future work
Consolidated in [`docs/future-work/30_FUTURE_WORK.md`](docs/future-work/30_FUTURE_WORK.md)
— odometry/PID (started), proportional steering, IMU, battery telemetry,
dashboard/eval harness, TinyML, self-balancing study.

## 20. Documentation & Report Generation System (Python Automated Pipeline)
The project includes a publication-grade, fully deterministic technical documentation suite and report generation engine built in Python 3.12:

### Tooling Commands (`tools/`)
```bash
# 1. Run kinematic control theory simulation (Kp gain sweep)
python tools/simulate_control.py

# 2. Generate all publication vector & raster diagrams (300 DPI)
python tools/generate_diagrams.py
python tools/generate_figures.py

# 3. Generate Bill of Materials (BOM.csv, BOM.xlsx, BILL_OF_MATERIALS.md)
python tools/create_bom.py

# 4. Generate 32 test cases & experimental data sheets (test_results.csv, test_results.xlsx)
python tools/create_test_templates.py

# 4b. Code-defined wiring schematic (power + signal chain, firmware pin truth)
python tools/generate_wiring_schemdraw.py   # -> diagrams/ and figures/wiring_schemdraw.{png,svg}

# 4c. Wokwi simulation firmware build (arduino-cli -> diagrams/wokwi/build/)
python tools/build_wokwi_firmware.py
python tools/run_wokwi_sim.py               # headless sim; needs wokwi-cli + WOKWI_CLI_TOKEN

# 5. Generate technical tables (AI comparison, pinouts, wiring, FMEA, power budget)
python tools/generate_tables.py

# 6. Generate the complete 35-chapter markdown documentation suite
python tools/generate_docs.py

# 7. Compile Final Editable Report (DOCX) & Publication PDF
python tools/generate_report.py
python tools/generate_pdf.py

# 8. Run Automated Documentation Validation Suite
python tools/validate_docs.py

# 9. Evaluate a collected telemetry run (dataset eval harness)
python scripts/evaluate.py            # -> logs/eval.json
python scripts/evaluate.py --strict   # exit 1 on an invariant violation

# 10. Score multi-object detection accuracy on labelled images (COCO128)
python scripts/eval_detection.py                                    # -> logs/detection_eval.json
python scripts/eval_detection.py --set ai.yolo_imgsz=640            # override any config key
python scripts/eval_detection.py --compare logs/detection_baseline.json
```

### Key Deliverables Generated
- **Final Report (Word DOCX):** [`reports/AI_Rover_Final_Report.docx`](reports/AI_Rover_Final_Report.docx)
- **Final Report (Print-Ready PDF):** [`reports/AI_Rover_Final_Report.pdf`](reports/AI_Rover_Final_Report.pdf)
- **Wiring & Breadboard Guide (PDF):** [`reports/AI_Rover_Wiring_and_Breadboard.pdf`](reports/AI_Rover_Wiring_and_Breadboard.pdf)
- **Process Walkthrough / Team Guide (PDF):** [`reports/AI_Rover_Process_Walkthrough.pdf`](reports/AI_Rover_Process_Walkthrough.pdf) ([source](docs/PROCESS_WALKTHROUGH.md), regen: `py -3.12 tools\generate_process_pdf.py`)
- **Wiring schematic (regenerable):** [`figures/wiring_schemdraw.png`](figures/wiring_schemdraw.png) | [`diagrams/wiring_schemdraw.svg`](diagrams/wiring_schemdraw.svg)
- **Wokwi simulation project:** [`diagrams/wokwi/`](diagrams/wokwi/) (`diagram.json`, `wokwi.toml`, `sketch.ino`)
- **Bill of Materials:** [`BOM.xlsx`](BOM.xlsx) | [`BOM.csv`](BOM.csv) | [`docs/31_BILL_OF_MATERIALS.md`](docs/31_BILL_OF_MATERIALS.md)
- **Testing Log & Protocols:** [`data/test_results.xlsx`](data/test_results.xlsx) | [`docs/25_TEST_PLAN.md`](docs/25_TEST_PLAN.md)
- **Diagrams (19 figures):** [`figures/`](figures/) | [`diagrams/`](diagrams/)
- **Engineering Risk Audit:** [`docs/FINAL_AUDIT.md`](docs/FINAL_AUDIT.md)
- **Hardware Verification Matrix:** [`docs/hardware/HARDWARE_VERIFICATION.md`](docs/hardware/HARDWARE_VERIFICATION.md)

