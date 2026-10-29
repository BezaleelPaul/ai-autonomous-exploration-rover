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
config/config.yaml (all subsystems, including the `autotune:` dials in
section 9d) + config/thresholds.yaml (calibration values) +
config/learned.yaml (remembered auto-tune values; git-ignored runtime
artifact, recreated on demand — see section 9d).

## 9. Running
```
python software/main.py --mock --mode observe            # no hardware
python software/main.py --mode manual                    # W/A/S/D + SPACE, Q quit
python software/main.py --mode observe --target bottle
python software/main.py --mode search --target bottle
python software/main.py --mode scan360 --target bottle
python software/main.py --mode observe --dashboard       # + web status
```
> **Legacy headless path.** `software/main.py` is a secondary, deprecated entry
> point: its autonomous modes (observe/search/scan360) emit a
> `DeprecationWarning`. The canonical autonomous rover is the **Mission Deck**
> (`python scripts/dashboard.py --auto` / `--explore`), which uses one shared
> `SteeringPolicy` brain and one shared `CommandEmitter`. `--mode manual` stays
> supported.

## 9b. Two-tier stack (phone IP Webcam + Bluetooth bridge)
A second, self-contained pipeline — laptop tier + embedded tier — that shares
no state with the ESP32-CAM loop above (details: docs/TWO_TIER_STACK.md):
```
python -m software.perception_node --mock --once                       # no hardware
python -m software.perception_node --url http://<PHONE_IP>:8080/video   # IP Webcam app
python -m software.perception_node --serial-mode bluetooth --port COM5  # BT virtual COM
python -m software.perception_node --mock-camera --serial-mode bluetooth --port COM5 --once
python -m software.perception_node.bench COM5 F --listen 5              # send F, print telemetry
python -m software.perception_node.bench COM8 --listen 5                # listen-only (phone drives)
python software/perception_node/cli.py --help                           # all flags
```
Flash `esp32/bt_bridge/bt_bridge.ino` (SPP name `AI_Rover_Control`,
ESP32 GPIO17 TX2 -> Arduino D4) and `arduino/motion_safety/motion_safety.ino`
(TB6612FNG build: PWMA D5, AIN1 D6, AIN2 D7, PWMB D9, BIN1 D8, BIN2 D10,
STBY->5V; HC-SR04 TRIG D2 / ECHO D3; SoftwareSerial D4 RX; 15 cm forward
gate; 500 ms link watchdog). Wheel bring-up: flash
`arduino/wheel_test/wheel_test.ino` and follow its Serial output
(`py -3.12 tools/hw_check.py flash --target wheels`).
YOLOv8n + the three-zone HUD emit `F/L/R/S`; `q` quits, `p` pauses, `h` hides
the HUD. Config lives under `perception:` in config/config.yaml.

For a WiFi pad instead of Bluetooth, flash `esp32/wifi_bridge/wifi_bridge.ino`
(soft-AP `AI_Rover_Control` → http://192.168.4.1/). Its CAMERA panel takes the
phone IP Webcam URL (`GET /cam?u=http://<PHONE_IP>:8080/video`, stored in NVS so
it survives a reboot) and plays that stream beside the drive pad — while the
laptop does the actual YOLO analysis with `--ip-webcam`. `STA_SSID`/`STA_PASS`
are placeholders in the repo; fill them in locally before flashing.

## 9c. Localhost control deck (AI video + drive pad)
A browser pad that drives the same Arduino over USB with game-style feedback:
WASD/arrow keycaps and pad buttons light up while held, a centred flash glyph
shows every keypress, and the keystroke log records each send. Hold to drive,
release stops (`S`); the link re-sends on a heartbeat so the firmware's 3 s
comm watchdog stays fed. Telemetry (distance, GO/BLOCKED, obstacle alerts)
comes back on the same cable.
```
python scripts/dashboard.py --controls                 # auto-detect the board
python scripts/dashboard.py --controls --arduino COM8  # explicit port
python scripts/dashboard.py --controls --mock-serial   # no hardware
python scripts/dashboard.py --backend mock --controls  # no camera / weights
python scripts/dashboard.py --ip-webcam                # phone stream from config
python scripts/dashboard.py --ip-webcam http://<PHONE_IP>:8080/video
```
Open http://127.0.0.1:5000 (host/port from `dashboard:` in config/config.yaml).
Close the Arduino Serial Monitor first — the deck owns the port.

**IP Webcam (Android) settings that matter:** start the server on the phone and
use the address it prints — a bare `http://<PHONE_IP>:8080` is accepted and
completed to `/video`, and the app's `/videofeed` alias works too (the ESP32
page retries it on its own when `/video` doesn't paint, and says why if neither
does). Leave authentication off, set the frame rate to 5 fps or higher (the
frozen-frame detector gives up after 3 s), and keep the phone on the same
network as whoever is watching: the ESP32 only relays the URL — the browser
doing the fetching is what actually pulls the frames.

**Optional low-latency proxy (not a dependency):** if the phone's raw MJPEG
adds lag, [go2rtc](https://github.com/AlexxIT/go2rtc) (MIT) can run as a local
sidecar — point it at the IP Webcam URL and set `perception.stream_url` to
go2rtc's own stream endpoint. Nothing in the rover code requires it; the
built-in lag-free `MjpegReader` (latest-wins, zero frame buffering) is the
default path.

**Mission Deck (plugin + world-model extensions):** the control deck's AI
video panel is driven by a plugin system (`software/plugins/`) loaded from
`plugins.enabled` in config/config.yaml. The shipped default is **one
detector pass**: the COCO control model runs per frame and `scenesense`
estimates a relative monocular depth map (Depth-Anything small) that feeds a
short-term `WorldModel` (`software/ai/world_model.py`). The world model tracks
each detection's side (left/center/right), distance band (near/mid/far),
motion trend (approaching/receding/still) and simple containment relations
("cup on table"). The result is surfaced on the deck as a SURROUNDINGS card
(scene summary, one-line facts, path verdict, STL robustness margin) and as
`feed.world` in `/api/state`. The world model is advisory only — it never
commands motors; the ultrasonic/safety chain stays the tier-1 authority.
`world` (YOLO-World open-vocab, adds pen/watch/keys that COCO-80 cannot name)
is an **opt-in** second detector: enable it in `plugins.enabled` only when the
extra CPU is affordable — on the 2-core host it re-detects every frame and
starves the realtime loop. `scenesense` is cadence-gated
(`scenesense_every_n`) and runs on a dedicated worker thread beside the
realtime detector (`plugins.slow_interval_s` sets its breather), so the extra
CPU cost is a dial and a slow plugin can never freeze video, boxes or control;
a failing plugin
degrades only its own quality (logged, never crashes the pipeline).

**Hardened world model (uncertainty-aware):** the heuristic box-log was
replaced with mathematically grounded estimators (`software/ai/kalman.py`,
`software/ai/stl_monitor.py`):
- **Kalman tracking** — one constant-velocity KF per object (CWNA process
  noise); the posterior position sigma is the principled uncertainty, and
  `size_rate` (px/s growth) is the KF-grounded "approaching" signal
- **metric scale** — the ultrasonic ranger calibrates monocular depth via
  recursive least squares on `(depth-score, 1/distance)` pairs; the fit
  residual becomes the metric sigma. Optional ground-plane pinhole fallback
  (`camera.ground_plane.height_m`) gives a geometric distance for
  floor-standing objects before calibration is ready
- **interval-valued facts** — every object carries `[lo, hi] = estimate ±
  k·sigma` instead of a point value; facts render as
  `bottle left d=1.2±0.4m conf=0.81`
- **three-state path verdict** — CLEAR (all intervals above margin),
  UNCERTAIN (some interval straddles it), BLOCKED (some interval fully
  inside) — interval arithmetic instead of a binary gate
- **STL spec** — `always (ultrasonic > world_clear_m)` evaluated with
  quantitative robustness (ρ > 0 satisfied, ρ < 0 violated, reported live);
  falls back to the nearest metric interval's lower bound when ultrasonic
  is silent
- **watchdog** — world age is checked against `plugins.world_deadline_s`;
  stale perception reports DEGRADED on the deck instead of failing open

## 9d. Auto-tune (measure → explore → commit → monitor → re-arm)
Some dials cannot be hand-measured once and forgotten: inference latency
depends on how busy the laptop is *right now* (README section 5), and the
detector's operating point depends on the room it is pointed at. Auto-tune
lets a value find its own setting and then **stabilise**:

1. **EXPLORE** — measure every candidate of a small, explicitly bounded set
   (the space is enumerated, so exploration always terminates).
2. **COMMIT** — keep the cheapest candidate that satisfies its constraint;
   ties fall back to the value this project ships with, so a window with no
   signal can never drift a dial away from a known-good setting.
3. **MONITOR** — keep scoring the committed value while it stays right.
4. **RE-ARM** — a cost that degrades (or improves) past its band throws the
   dial back to EXPLORE and discards the stale measurements, so the system
   re-finds its optimum on its own when the world changes.

Two tuners, one algorithm (`software/autotune/`):

| | online (runs with the deck) | offline (calibration run) |
|---|---|---|
| dial | `ai.inference_interval` | `ai.confidence_threshold`, `ai.min_box_px`, `ai.iou_threshold` |
| signal | measured loop latency vs the H4 freshness budget | labelled COCO128 F1, gated on H4 closure |
| persisted | no (host load is session-local) | yes → `config/learned.yaml` |

Online (`LiveFeed`): the governor keeps detection refresh inside
`autotune.budget_margin × navigation.target_lock_duration_s` (0.25 × 2.0 s =
0.5 s, the "~0.5 s refresh" target above) and, subject to that, spends the
leftover headroom on the *largest* interval so the slow world-model plugins
keep a CPU budget of their own. It explores **analytically** — one latency
sample predicts every candidate — so no candidate is ever applied to the live
loop while it is deciding. Live state is on the deck as `feed.autotune`
(`explore`/`commit`, the committed interval, its cost and the budget).

Offline (operator-run, minutes, labelled images only):
```
py -3.12 scripts/autotune_detection.py --limit 40          # dry run: report only
py -3.12 scripts/autotune_detection.py --limit 40 --write  # persist the result
```
Precedence is **file < learned < environment**: `config/learned.yaml` is
merged in by `load_config` on every later session, environment variables still
win, and an overlay that would fail validation is dropped wholesale rather
than bricking a session. Only `ai`/`camera`/`plugins` are ever written —
`rover`, `safety`, `serial`, `navigation` and `thresholds` describe the
physical machine and the safety envelope, so no tuner can touch them. Set
`autotune.enabled: false` to freeze everything at the shipped values.

## 9e. Explorer journal (Gemini narration, advisory only)

On power-on the rover looks at the scene and writes a journal entry; from then
on it appends an entry only when something actually changed — a new object
class, a new path verdict, a new mode — and closes with a journey summary on
shutdown. It continues whatever the previous session left behind, so the log
reads as one journey across power cycles.

```
py -3.12 scripts/dashboard.py --controls --journal   # needs GEMINI_API_KEY
```

**MEASURED 2026-10-19, this host (gemini-2.5-flash, thinking off): 6.9 s and
325 in / 241 out tokens per entry.** That is 14× the 0.50 s H4 freshness
budget, so the journal is *structurally* incapable of sitting in the control
loop — it is a background worker thread, and the pilot's 4 Hz tick never
waits on it. It reads one downscaled (≤640 px) JPEG per entry, not the stream.

Three rules, matching the rest of the stack:

- **The key never enters the repo.** `GEMINI_API_KEY` is read from the
  environment at call time — never from config, never written to disk.
- **The model may not invent measurements.** Every entry is grounded in a
  `MEASURED` block (ultrasonic cm, detections with confidence and range, path
  verdict, the DEGRADED flag) and the prompt orders it to treat that block as
  ground truth and to label anything inferred from the image as an estimate.
- **Fail-soft, like the CLIP explainer.** No key, a dead network, or three
  consecutive failures leaves `available=False` with a reason and the journal
  goes quiet; the deck, the pilot and the safety chain are untouched.

Journal entries land in `data/journal/<timestamp>/journal.md`; the deck serves
them at `GET /api/journal` (add `?format=md` for the markdown). The measured,
deterministic mission report is still `report.md` / `GET /api/report` — that
one needs no network and no key. `explorer.enabled: false` (the default)
freezes the whole thing off.

## 10-14. Modes
Manual (safety-gated), Observe (align+approach), Target Search (rotate≤timeout/
rotations then report), 360° scan (scan360), obstacle safety demo (AI GO vs
ultrasonic STOP → STOP wins).

## 15. Safety
Priority: emergency latch > sensor > comms > validity > confidence > objective.
Camera/serial loss, invalid sensor, low confidence → STOP. See docs/edge_cases.md.

## 16. Testing
`python -m pytest tests -q` → 810 passed (mock, no hardware, Python 3.12).
Both run commands work: `python software/main.py ...` and
`python -m software.main ...`. Scenarios in
tests/test_scenarios.py (22 cases). Docs: docs/testing.md.
Auto-tune is covered in tests/test_autotune.py (algorithm, governor, overlay,
config wiring, safety-out-of-scope).

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

