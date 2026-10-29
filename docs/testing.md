# Testing

Run: `python -m pytest tests -q` (810 tests, hardware-independent via mocks).
- test_detector: parsing, thresholds, zones, tracker selection
- test_steering: position->command mapping, anti-oscillation hold, states, P-steering speed, search rotation
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
- test_perception_node: two-tier node — three-zone geometry and the
  bounding-box-area proximity policy (no target/close target → `S`,
  L/C/R steering), IP Webcam URL validation (a bare `http://ip:8080` origin is
  completed to `/video`, `/videofeed` passes through, garbage is refused), USB
  vs Bluetooth port
  resolution, `SerialLink` whitelist/reconnect/write-failure handling, HUD
  rendering, heartbeat vs cooldown emission, stream-loss → `S`, CLI `--once`
  smoke run, split `--mock-camera`/`--mock-serial` flags, and the
  `bench.py` sender (whitelist, open failure, telemetry print, exit codes)
- test_two_tier_firmware: ESP32 BT bridge (SPP name `AI_Rover_Control`,
  GPIO17 TX2, 9600 8N1, motion whitelist, bounded drain, non-blocking loop)
  and Arduino motion/safety (D2/D3 + D9/D10 pin map, 15 cm gate synced to
  `config.yaml`/`thresholds.yaml`, forward-only override + alert, invalid
  echo blocks forward, noise chunk → STOP, boot STOP, non-blocking
   `millis()`/`micros()` ultrasonic state machine, and the USB bench
  fallback sharing the same whitelist (`drainSource(Serial)`)); plus the WiFi
  web bridge (camera stream panel + `/cam` endpoint that validates and persists
  the phone IP Webcam URL, station credentials left as placeholders, and the
  regression pinning the HTML page in `page_html.h` — a raw-string page inside
  the .ino makes the sketch preprocessor emit `function send(c);`, which does
  not compile)
- test_dashboard_controls: localhost control deck — `ArduinoLink` on the USB
  port (whitelist validation against the `.ino` source of truth, firmware
  telemetry folding incl. invalid echo → no distance, read loop over a scripted
  serial, heartbeat that re-sends only while a motion key is held so the
  firmware comm watchdog stays fed, open failure and clean close), the
  game-style page (WASD/arrows/SPACE keycaps, pad buttons, release → `S`), and
  the Flask routes (`/`, `/video_feed`, `/api/state`, `/api/cmd` 200/400/503),
  feed source selection (`resolve_source`: `--mock`/`--esp32` beat the stream
  URL, `--ip-webcam` with no URL falls back to `perception.stream_url`, an
  unusable URL raises before a camera opens) and the network-source branch
  handing the URL to the IP Webcam client
- test_mjpeg_reader: pure-Python MJPEG reader — split markers across TCP
  chunks, latest-wins frame skip, SOI/EOI resync after a corrupt frame, no
  buffered backlog, loopback HTTP server source, and `open_ip_webcam` routing
  http(s) to the reader
- test_ai_explainer: CLIP explainer — backend factory order (clip before
  open_clip), label scoring, empty-frame 503 path, and the gated
  `/api/explain` route (no-CLIP → 503, caption opt-in)
- test_plugins: plugin framework — `load_plugins` name sanitisation, a
  failing plugin being logged + skipped rather than raised, per-hook
  isolation + timing, `merge_timings`, the shipped `plugins.enabled`
  configuration, and `LiveFeed` state surfacing plugin ms + stats
- test_world_model: world model + scenesense plugin — side/band helpers,
  track-pruned history, approaching motion from box growth and depth delta,
  `ON` containment (accepted at equal depth, rejected when depth diverges),
  depth-banded objects from a synthetic depth map, center-near blocked-path
  verdict, depth-score normalisation, cadence gating (2 of 4 passes), and
  geometry-only degradation when the depth model fails to load
- test_dashboard_deck: Mission Deck routes — `/api/mode` arm/disarm +
  strict-guard rejections, `/api/recording` start/stop/summary,
  `/api/events` ring, `POST /api/stream` URL validation + `set_source`
  hot-swap, multi-detection chips payload, `feed.world` surfacing, and the
  page's camurl bar / chips row / SURROUNDINGS / CLIP tokens
- test_dashboard_pilot: `MissionPilot` — MODES gating, why-chain assembly,
  motors_for steering, and on_tick recorder hook
- test_dashboard_recorder: `RunRecorder` — CSV flush, trigger capture,
  summary.json aggregation, and frame/decision counts
- test_kalman: constant-velocity Kalman filter — velocity convergence on
  approach (CWNA process noise), stationary rejection, centre-velocity from
  lateral motion, coasting sigma inflation, correct-reduces-sigma,
  Mahalanobis outlier detection, and box readback
- test_stl_monitor: quantitative Signal Temporal Logic — predicate
  robustness as signed distance, Not/And/Or on robustness values, Always =
  min over window, Eventually = max over window, unknown on missing signal,
  three-state classify, and the clear-path spec matching the world model
- test_world_model (extended): inverse-depth calibrator (pair/spread
  gating, line recovery, range rejection, live ultrasonic seeding),
  metric interval emission, ground-plane pinhole fallback (floor hit,
  horizon miss, height-0 disabled), watchdog stale-world flagging, STL
  violated/satisfied on ultrasonic margin, and interval fallback when
  ultrasonic is silent
- test_autotune: auto-tune (README section 9d) — the
  explore→commit→monitor→re-arm algorithm (bounded search spaces, anchor
  tie-breaks, re-arm on degrade *and* on improve, seed rejection outside a
  space), the online realtime governor (largest budget-closing interval,
  interval-one under load, no candidate applied while exploring, re-arm then
  re-stabilise when the host slows), config wiring (dials bounded and
  validated, shipped anchors), the learned overlay (allow-listed sections
  only, atomic write, broken overlay dropped fail-open, environment still
  wins), the `LiveFeed` interval gate, and `scripts/autotune_detection.py`
  (coordinate sweep, fixed-point convergence, H4-gated cost, dry-run never
  writes)
- test_journal: the explorer journal (software/ai/journal.py) — fail-soft with
  no `GEMINI_API_KEY` (nothing written, tick/stop are no-ops), disabled config
  never opens a run, construction survives garbage config, the interval
  throttle, scene-vs-pilot fingerprinting (the power-on entry is the scene
  baseline, the first pilot decision is adopted silently, then only real
  changes narrate), continuity (the opening entry quotes the previous
  journal's tail), timestamped markdown entries, consecutive-failure back-off
  (no retry storm), the measured-facts block (ultrasonic, detections, path
  verdict, DEGRADED note — the model is never allowed to invent a sensor
  reading), and the injected-transport client (parses 200, raises on HTTP
  errors and empty completions so the journal can back off). No test reaches
  the network.


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
Calibrate the detector's operating point (README section 9d) with
`py -3.12 scripts/autotune_detection.py` — a bounded coordinate sweep of
`ai.confidence_threshold`, `ai.min_box_px` and `ai.iou_threshold` over the
same labelled images, each candidate scored by F1 with a hard penalty when it
breaks the H4 closure, repeated until the values stop changing. `--write`
persists the committed values to `config/learned.yaml` (git-ignored; merged in
by `load_config` as file < learned < environment), without it the run is a
dry report and touches nothing. It never touches `rover`, `safety`, `serial`,
`navigation` or `thresholds`.
