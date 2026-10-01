# Testing

Run: `python -m pytest tests -q` (311 tests, hardware-independent via mocks).
- test_detector: parsing, thresholds, zones, tracker selection
- test_decision_engine: L/C/R, anti-oscillation hold, states, P-steering speed
- test_safety: emergency/comm/camera/confidence overrides, gap levels
- test_navigation: search timeout/rotations, 360 scan, very-close, center_error
- test_serial_protocol: command validation, telemetry parsing (incl. TICKS),
  Protocol v2 speed-suffix encoding + validation
- test_pid: Phase 9+ PID (anti-windup, dt<=0) + odometry math + config factories
- test_firmware_contract: YAML↔firmware constants (incl. velocity loop),
  protocol prefixes, pins
- test_firmware_host: 21 SIMULATED scenarios incl. speed suffix + velocity loop
- test_scenarios: 22 end-to-end Decision->Avoid->Safety scenarios + gap cases
- test_event_eval: dataset eval harness — telemetry parsing/validation, range
  and distribution stats, run segmentation, 10 safety/protocol invariants,
  CLI exit codes
- test_detection_metrics: multi-object detection scoring — IoU, greedy
  confidence-ordered matching, precision/recall/F1, duplicate counting,
  multi-object recall, interpolated AP, operating-point pruning
- test_confidence_split: detection bar vs act-on bar — config declares both,
  `ObjectTracker` ignores detections below `target_confidence`,
  `SafetyManager` blocks forward below it (turns still allowed), `RoverApp`
  wires the two keys separately
- test_eval_harness: `scripts/eval_detection.py` class-name discovery — the
  Ultralytics `.names` convention, the Hugging Face `_pipe` + `config.id2label`
  convention, string keys, and the empty-model case (regression for the bug
  that made every `ai.backend: hf` model unbenchmarkable)
- test_frame_manager: single-slot latest-frame buffer — observe/consume
  round-trip, dropped-frame counting when a stored frame is replaced before it
  is read, frame age (None when capture time is unknown, staleness past the
  3.0 s FM-03 threshold), interval throttling incl. the interval-0 clamp, and
  reset
- test_hf_detector: `ai.model_dir` shadowing `ai.model_name` — warns when the
  local directory cannot be the requested checkpoint, silent when it matches,
  falls back to `model_name` when the directory is absent
- test_camera_collector: 15-condition capture plan, argument validation,
  mock-source capture → manifest rows, SIMULATED labelling with no `labels/`
  output without `--auto-label`, and `main()` writing the stats file
- test_esp32_stream: the stream client must pass
  `CAP_PROP_OPEN_TIMEOUT_MSEC` to the FFmpeg backend (a dead camera used to
  block 93.5 s), must fall back when that overload is unsupported, must
  honour `config.yaml camera.reconnect_timeout_s` as a backoff instead of
  re-contacting the camera on every read, and must leave the mock path
  untouched
- test_wokwi_sim: Wokwi project ↔ firmware pin map (8 signal wires, D0/D1
  never wired, L298N dependency pinned), `wokwi.toml` pointing at the
  arduino-cli build artifacts, `tools/run_wokwi_sim.py` failing with the
  right exit code when the build, the CLI or `WOKWI_CLI_TOKEN` is missing,
  and the automation scenarios (valid YAML, real part ids, `value:` — never
  the no-op `expected:` — plus coverage of startup STOP, protocol rejection,
  the 3 s watchdog and the 10 cm obstacle gate)
- test_wiring_schemdraw: wiring schematic outputs present and identical in
  `diagrams/` + `figures/`, generator labels matching the firmware pin map,
  and the published `reports/AI_Rover_Wiring_and_Breadboard.pdf` (skipped
  when the PDF has not been generated)

Wokwi simulation (needs `arduino-cli`, `wokwi-cli` and a free
`WOKWI_CLI_TOKEN`):
`python tools/build_wokwi_firmware.py` then
`python tools/run_wokwi_sim.py --scenario scenarios/safety.yaml` (or
`scenarios/obstacle_gate.yaml`) — builds
`diagrams/wokwi/build/rover_controller.ino.{hex,elf}`, lints `diagram.json`,
and drives the simulated firmware.
**MEASURED 2026-09-27, wokwi-cli v0.27.1:**
- lint → `✓ No issues found`
- plain run → `DIST:100.3 / STATUS:OK / TICKS:0,0`, `--expect-text DIST:` PASS
- `scenarios/safety.yaml` → *Scenario completed successfully*: drivers
  released at boot (IN1/IN3 low), `X` → `STATUS:ERROR` with no actuation,
  `F` → IN1/IN3 high, 3.6 s silence → watchdog `STATUS:STOP` and both
  bridges released, then recovery on the next `F` and `S`
- `scenarios/obstacle_gate.yaml` → *Scenario completed successfully*: sonar
  moved to 10 cm (< `EMERGENCY_STOP_CM` 15), `F` → `STATUS:STOP` and IN1
  stays low — the emergency gate blocks translation in simulation too

Hardware smoke tests: scripts/test_camera.py, test_serial.py, test_detector.py
all accept --mock. Model: scripts/benchmark.py (latency/FPS/CPU/RAM sweep over
resolutions + frame-skip projection, benchmarks the configured ai.backend and
writes logs/benchmark.json).
Shipped default (CPU, yolo11s @ imgsz 320): p50 184 ms at 50 % host CPU load
(`logs/detection_baseline.json`); the imgsz-320 sweep in
`logs/benchmark.json` measured p50 119-211 ms (~3.8-6.7 FPS), load 0.4 s.
`inference_interval` 2 keeps detection refresh at 0.37 s under the
1.0 s target-lock (H4, enforced by tests/test_redteam_h4_realtime.py).
Latency is load-sensitive: the same config measures p50 534-685 ms at
100 % host CPU load (`logs/detection_cand_yolo11s.json`,
`logs/detection_final.json`), i.e. 1.07-1.37 s refresh and H4 red.
imgsz 480 was evaluated and rejected: p50 577 ms at 100 % host CPU load,
i.e. H4 red on a busy machine; H4 is load-sensitive, so run the realtime
gate with the host at <=~60 % load.
DETR baseline (hf option): ~5.1 s mean, 0.2 FPS, ~1 GB RSS, load ~27 s —
logs/benchmark_detr.json; accuracy/offline use only, NOT realtime.
Calibration: scripts/calibration.py + config/thresholds.yaml.
Logs: logs/events.csv collects timestamp/mode/target/conf/position/dist/decision/safety/latency.
Evaluate a collected run with `python scripts/evaluate.py` (optionally `--strict`)
— reads logs/events.csv, prints mode/decision/safety distributions, confidence
and latency percentiles, oscillation and safety-intervention rates, checks 10
protocol/safety invariants and writes logs/eval.json.
Score detection accuracy against labelled data with
`python scripts/eval_detection.py` — downloads COCO128 (128 labelled images)
to datasets/, runs the shipped detector, and reports operating-point
precision/recall/F1, multi-object recall, duplicate count and mAP@0.5 next to
p50/p95 latency and an H4 closure check; writes logs/detection_eval.json
(`--set ai.yolo_imgsz=640` overrides config, `--compare` diffs a baseline).
