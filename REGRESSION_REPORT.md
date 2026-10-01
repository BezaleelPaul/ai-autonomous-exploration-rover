# Regression Report — Red-Team Fix Round

**Date:** 2026-09-25
**Scope:** Re-run every test after fixing the 25 failing tests reported in
[`TEST_REPORT.md`](TEST_REPORT.md) (independent red-team, BUILD gate), plus the
follow-up **H4 fix round** (realtime backend switch), the **Phase 9+
future-work session** (encoders/PID foundation, doc reorg) and the
**Protocol v2 session** (velocity loop + P-steering), same day.
**Method labels:** PASS / FAIL = software evidence. Physical behaviour is
**HARDWARE REQUIRED / NOT TESTED** — no result in this report proves anything
about the unpowered rover.

---

## 1. Verdict

| Gate | Baseline (red-team) | After fixes | Status |
|---|---|---|---|
| `pytest tests -q` | 137 passed / 25 failed (162) | **311 passed / 0 failed** (162 + 2 H4 + 22 Phase 9 + 13 Protocol v2 + 33 eval harness + 25 detection metrics + 7 confidence split + 3 eval-harness class names + 8 frame buffer + 2 model_dir shadow + 5 camera collector + 6 ESP32 stream + 15 Wokwi/wiring guards + 6 data-link docs guards + 2 port auto-detect guards) | **PASS** |
| `ruff check software tests` | PASS | PASS (All checks passed) | PASS |
| `arduino-cli compile` UNO `rover_controller` | 4642 B (14%) | **5526 B (17%)** (Phase 9 encoders +422 B, Protocol v2 velocity loop +462 B) | PASS |
| `arduino-cli compile` ESP32 `camera_stream` | 1026129 B (32%) | **1026129 B (32%)** | PASS |
| Firmware-host harness (21 scenarios) | FAIL (C1, H3) | **PASS** | PASS |
| Mock smoke, 4 modes (`--mock`) | scan360/search issued 0 rotations | **observe/search/scan360/manual run, no crash** | SIMULATED |
| Release gate (TEST_REPORT §14) | NOT READY | software defects addressed; hardware gate unchanged | see §5 |

Previously passing features did not break: the 137 baseline passes are still
passing (no test was deleted, weakened, or skipped; only one precondition
assertion was corrected in `test_redteam_safety_chain.py:228` with an inline
comment, after C1 changed dead-sensor health semantics).

---

## 2. Findings fixed (finding → change)

| ID | Finding | Change |
|---|---|---|
| C1 | Sensor-failure fail-safe returned GO at both layers | Firmware: `sensorBad` forces `blocked`, `STATUS:STOP` (`rover_controller.ino`). Python: `Telemetry.sensor_fault`, `RECOGNISED_STATUS` gate, `is_healthy()` returns False on dead sensor (`arduino_serial.py`) |
| C1b | Red-team precondition encoded the bug | `test_redteam_safety_chain.py:228` precondition corrected to the fixed contract (commented) |
| H1 | `search` mode never rotated (`LOW_CONFIDENCE` blocked `R`) | Confidence gate now applies to forward motion only (`safety_manager.py`) |
| H2 | `scan360` never scanned / never approached | Scan auto-starts, restarts when idle, and `engine.decide` runs when the target is visible (`main.py`) |
| H3 | Firmware actuated on any single byte / corrupt tail | `handleSerial()` chunk framing: execute only one distinct command char, else `S` + ≤4×`STATUS:ERROR`; `sensorBad`/`blocked` include `'F'/'B'` translations |
| H4 | AI loop cannot close (4135 ms/frame DETR) | **FIXED (H4 round)** — shipped default switched to realtime backend: `ai.backend: yolo` (yolo11s, **measured p50 119–211 ms** @ imgsz 320, `logs/benchmark.json`; DETR numbers preserved in `logs/benchmark_detr.json`), `inference_interval` 4→2 (refresh ~0.42 s < 1.0 s lock), startup preloads any loadable detector, `--mock` now forces `MockDetector` (tests never load weights), `scripts/benchmark.py` benches the configured backend. Enforced by `tests/test_redteam_h4_realtime.py` (2 tests, MEASURED) |
| M1 | Autonomous path bypassed the R4 emergency latch | `step()` runs `SafetyManager` **before** `ObstacleAvoidance` (`main.py`) |
| M2 | Unknown command alphabet passed through | `SafetyManager.check` rejects to `S` (`INVALID_COMMAND`) |
| M3 | Unrecognised `STATUS:` refreshed heartbeat | `RECOGNISED_STATUS = (OK, STOP, ERROR)` gate |
| M4 | STOP delayed by oscillation hold | `decide()` bypasses `_can_switch` for `S`; `emergency()` no longer corrupts the command clock (`decision_engine.py`) |
| M5 | Confidence gate skipped the slow zone | Gate moved above the slow-zone return, forward motion only (`safety_manager.py`) |
| M6 | Unused config keys / `thresholds.yaml` never read | Safety cutoffs consumed from `cfg["thresholds"]["ultrasonic"]`; remaining documented keys wired (iou, sensor_invalid_limit, reconnect_attempts, enhance, env overrides, dashboard.enabled, log_frames, fps/jpeg camera keys) or range-validated in `validate_config` |
| M8 | `.env.example` keys unread | `config_loader` env overrides: `ESP32_STREAM_URL`, `ARDUINO_PORT`, `ARDUINO_BAUD`, `AI_MODEL_NAME`, `TARGET_CLASS`, `LOG_LEVEL` |
| M9 | Doc/config inconsistencies | README/docs test counts → 162; docs/18 host names corrected (laptop↔Arduino); docs/19 `AVOIDING`/`EMERGENCY_STOP`/`SEARCHING` now entered by code (`main.py` engine wiring); `docs/27_RESULTS_TEMPLATE.md` rewritten as a distinct template |
| L1-L5, docs/config remainder | Unreferenced requirements, duplicate docs, unreachable states | `timm`/`networkx`/`qrcode` removed from `requirements.txt`; 8 byte-identical doc pairs deduplicated (single canonical copy, generators updated to stop dual-writing); `engine.emergency()` / `engine.to_search()` wired |
| — | `max_search_rotations` unreachable | `search_rotation_duration_s` 20→10 s (30 s / 10 s = 3 ≥ cap 2) |
| — | Target flickered between throttled inferences | `ObjectTracker` now holds the last detection for `lock_duration_s` (hysteresis the class already documented) |

## 3. Supporting fixes (found while fixing the above)

- `min_obstacle_distance_cm` validation direction corrected (it is a desired
  clearance target ≥ emergency distance, not a sensor lower bound).
- `load_config()` now guarantees `cfg["thresholds"]` always exists so safety
  code can read it directly.

---

## 4. Full regression evidence (this round)

```
pytest tests -q            -> 311 passed (incl. test_pid, TICKS, speed suffix,
                              velocity host, eval harness, detection metrics,
                              confidence split, Wokwi project + wiring guards)
ruff check software tests  -> All checks passed
arduino-cli compile UNO    -> Sketch uses 5526 bytes (17%) of program storage
arduino-cli compile ESP32  -> Sketch uses 1026129 bytes (32%) of program storage
firmware-host harness      -> 21/21 PASS (framing, flood, watchdog, sensor, encoders,
                              speed suffix, velocity loop)
wokwi-cli lint             -> No issues found (v0.27.1)
tools/run_wokwi_sim.py     -> build ok (5526 B) + 3 runs exit 0: plain,
                              scenarios/safety.yaml, scenarios/obstacle_gate.yaml
                              ("Scenario completed successfully"; logs/wokwi_serial*.log)
scripts/benchmark.py       -> yolo11s p50 119-211 ms @320, load 0.4 s (logs/benchmark.json)
scripts/evaluate.py        -> 8550 rows, 10 invariants PASS, logs/eval.json
--mock observe/search/scan360 (6 s each) -> no traceback, DEC/SAFETY logged
--mock manual (quit 'q')   -> exit 0, auto-stop guard path exercised by unit tests
tools/validate_docs.py     -> DOCUMENTATION INTEGRITY VERIFIED (PASS, 0 broken links)
```

Test inventory: `test_redteam_docs_config` 22, `test_redteam_safety_chain` 21,
`test_redteam_firmware_host` 21, `test_redteam_serial_fuzz` 18, `test_pid` 17,
`test_event_eval` 33, `test_detection_metrics` 25, `test_confidence_split` 7,
`test_eval_harness` 3,
`test_redteam_property` 13,
`test_redteam_watchdog` 13, `test_safety` 13, `test_firmware_contract` 13,
`test_decision_engine` 8, `test_serial_protocol` 11, `test_navigation` 6,
`test_manual_guard` 6, `test_detector` 5, `test_enhance` 4, `test_hf_detector` 5,
`test_regression_fixes` 3, `test_scenarios` 2, `test_redteam_h4_realtime` 2,
`test_frame_manager` 8, `test_camera_collector` 5, `test_esp32_stream` 6,
`test_wokwi_sim` 11, `test_wiring_schemdraw` 4, `test_docs_data_links` 6
= **311**.

---

## 5. Still NOT covered by this regression

| Item | Label | Note |
|---|---|---|
| Motor direction, PWM, stop distance on the ground | **HARDWARE REQUIRED / NOT TESTED** | Battery + buck converter not purchased; rover never powered |
| ESP32 live stream, real COM port, voltage/current measurement | **NOT TESTED** | No hardware |
| Wokwi firmware simulation | **SIMULATED (PASS)** | `diagrams/wokwi/{diagram.json,wokwi.toml,sketch.ino,scenarios/}`, `wokwi-cli lint` clean, 3 headless runs green (boot STOP, protocol reject, 3 s watchdog, 10 cm obstacle gate) — see §10. Physical rover still HARDWARE REQUIRED |
| All 13 hardware-plan test cases (`docs/25_TEST_PLAN.md`) | **HARDWARE REQUIRED** | Blank physical results only |

**H4 is CLOSED on the host** (MEASURED: 232/232 including the freshness test);
on-robot AI confirmation is part of the hardware gate above.

**Next gate (MASTER_TEST_PROMPT §25 Hardware Readiness):** firmware compiles ✅,
startup = STOP ✅ (unit-tested), watchdog ✅ (unit-tested), safety ✅
(unit-tested), pinout ✅ (`docs/PINOUT.md`), voltage ❌, motor driver ❌,
serial-with-real-board ❌ — the last three require the battery purchase.

---

## 6. Phase 9+ future-work session (2026-09-25)

Operator directive: move all future-work material into `docs/future-work/` and
start implementing it. Landed (all software evidence, **SIMULATED / math only**):

- **Doc reorg** — `docs/future-work/30_FUTURE_WORK.md` now holds README §19,
  FINAL_AUDIT optional/medium items and INTEGRATION_PLAN Phase 9+; pointers left
  in place; `generate_docs.py` / `generate_pdf.py` / `validate_docs.py` paths
  updated; `generate_tables.py` re-synced (all 5 outputs byte-identical).
- **PID + odometry foundations** — `software/control/{pid,odometry}.py` with
  anti-windup PID and tick→distance math, `control:` config section (range-
  validated), wired into `RoverApp` (not yet applied to motors).
- **Firmware encoder telemetry** — D2/D3 ISRs count ticks, `TICKS:<l>,<r>`
  emitted with each telemetry frame (inert until encoders are fitted);
  `arduino_serial.py` parses into `Telemetry.encoder_ticks` and never treats it
  as a heartbeat (M3 preserved).
- **+22 tests** (17 PID/odometry, 3 TICKS protocol, 1 host encoders scenario,
  1 pin/telemetry contract) → 186 passed / 0 failed at that checkpoint;
  docs counts updated (superseded by §7).

Still **HARDWARE REQUIRED**: physical tick counts, closed-loop straight-line
driving, and any gain tuning (defaults in `config/config.yaml` are TUNING
REQUIRED — `docs/future-work/30_FUTURE_WORK.md` §2).

---

## 7. Protocol v2 session — velocity loop + P-steering (2026-09-25)

Operator directive: implement the two deferred control items (firmware P
velocity loop, laptop P-steering) on top of a Protocol v2 speed channel.
All software evidence, **SIMULATED / math only**:

- **Protocol v2** — optional PWM suffix `0..255` on `F/B/L/R/S` (`F180`);
  digit bytes never refresh the 3 s watchdog; overspeed (`>255`), mixed
  commands or unknown bytes force STOP + `STATUS:ERROR` (H3 semantics kept);
  bare commands keep the sticky `activeSpeed` (boot = `rover.max_speed_pwm`).
  `ArduinoSerial.send(cmd, speed=...)` encodes and range-validates the suffix.
- **Firmware P velocity loop** — per-wheel correction toward
  `control.velocity_target_tps` while `F/B` with `encodersEnabled`
  (`VEL_KP`/`VEL_TARGET_TPS`/`VEL_PWM_FF`/`VEL_PERIOD_MS` contract-synced to
  yaml); 6 silent encoder periods fall back to open-loop `activeSpeed`, so a
  dead sensor can never pin PWM at the limit.
- **P-steering** — `SceneResult.center_error` (cx−0.5) feeds
  `Decision.speed = clamp(round(steering_kp·|err|), steering_min_pwm, 255)`
  on `L/R` only; `main.py` appends the suffix only while the final command
  still equals the steering decision (safety/avoid overrides downgrade to a
  bare command).
- **+13 tests** (2 serial speed, 4 decision steering, 1 scene center-error,
  2 host scenarios, 3 firmware contract, 1 config validation) →
  **199 passed / 0 failed**; host **21/21**; UNO **5526 B** (+462 B); docs
  counts updated.

Still **HARDWARE REQUIRED**: real encoder ticks/s, closed-loop straight-line
driving, and every gain (`velocity_kp`, `steering_kp`, `steering_min_pwm`) —
shipped defaults are **TUNING REQUIRED**
(`docs/future-work/30_FUTURE_WORK.md` §2).

---

## 8. Dataset eval harness session (2026-09-26)

Operator directive: continue with the only backlog item that has no hardware
blocker — *"dataset eval harness, `logs/events.csv` already collected"*.
Software evidence only; labels **ANALYSIS OF LOGGED DATA** (nothing here
measures the unpowered rover).

- **`software/telemetry/event_eval.py`** — frozen `EventRow` / `EventDataset`,
  strict header validation (missing columns or zero parseable rows →
  `EvalError`), per-row defects counted instead of fatal. Pure statistics:
  `describe` (mean/p50/p95/min/max), `distribution` (count + share, sorted),
  `split_runs` (gap-segmented sessions), `check_invariants`.
- **10 invariants** derived from `SafetyManager.check` +
  `ObstacleAvoidance.override` (which only downgrades F/B → S) and from how
  `RoverApp.step` fills the log: protocol alphabet, blocking-reason ⇒ STOP,
  turn-only reasons never translate, slow-zone ⇒ forward, no-target ⇒ zero
  confidence and no position, confidence in [0,1], latency/FPS non-negative,
  timestamps monotonic, usable distance required for translation.
- **Distance-state classification** instead of silently dropping cells:
  `ok / absent / non_finite / negative / zero / unparseable`.
- **`scripts/evaluate.py`** — CLI with `--csv/--out/--min-rows/--strict/
  --json/--no-write`; exit `0` ok, `1` invariant violation (`--strict`),
  `2` input error; writes `logs/eval.json`, prints a fixed-width report.
- **+33 tests** (`tests/test_event_eval.py`: input validation, classification,
  statistics, run splitting, every invariant, CLI exit codes, plus a
  regression test over the shipped `logs/events.csv`) → **232 passed / 0
  failed** at that point (257 after the detection-accuracy session, §9);
  `ruff` clean; docs counts updated.

Findings on the collected dataset (`logs/events.csv`, **ANALYSIS OF LOGGED
DATA**): 8550 rows / 0 malformed, 12 runs spanning 2026-09-18 → 2026-09-26;
modes observe 6938 / scan360 829 / search 783; decision F 76.5% vs S 23.2%
(L 7, R 19); safety SAFE 92.6% with 7.4% interventions; detection rate 78.8%,
confidence p50 0.5; command-switch rate 0.062. **All 10 invariants PASS.**
Data-quality defects surfaced: 146 rows have an unusable `distance_cm`
(24 absent, 44 `nan`/`inf`, 24 negative, 34 zero, 20 unparseable including the
literal `True`) — every one of them logged `S`, i.e. safety held; and
inference timing is present on only 33 rows (0.4% coverage), so latency
percentiles from this file are **INDICATIVE, not MEASURED** — the MEASURED
latency evidence remains `logs/benchmark.json`.

Still **HARDWARE REQUIRED**: everything physical. The remaining dashboard
backlog item (`docs/future-work/30_FUTURE_WORK.md` §3) is untouched.

## 9. Multi-object detection accuracy session (2026-09-26)

Operator directive: *reuse open-source code from GitHub and increase the
accuracy of detecting multiple objects on camera*, with the hard constraint
**accuracy must not break realtime (H4 gate stays green)**.

There was previously no labelled data to measure against, so the first step
was a benchmark rather than a claim:

- **`software/ai/detection_metrics.py`** — pure, dependency-free scoring:
  IoU, greedy confidence-ordered one-to-one matching per class, precision /
  recall / F1, **duplicate detections** (a prediction overlapping an already
  claimed ground truth — the exact "reports N-1 / double-counts one" failure),
  **multi-object recall** (restricted to images with ≥2 ground truths, so
  single-object frames cannot dilute it), and 101-point interpolated
  mAP@IoU. `evaluate()` prunes predictions to the operating confidence for
  P/R/F1 while AP uses the full low-confidence curve.
- **`tests/test_detection_metrics.py`** — 25 tests (IoU edge cases,
  class mismatch, duplicate vs miss, confidence ordering, multi-object
  isolation, AP penalisation, operating-point pruning, input validation).
- **`scripts/eval_detection.py`** — CLI (`--data/--config/--set/--out/
  --limit/--iou/--ap-conf/--latency-frames/--compare/--json/--no-write`).
  Fetches **COCO128** (128 labelled images, 6.98 MB, ultralytics/yolov5
  release asset) into `datasets/coco128/` when absent, runs the *shipped*
  detector over it, and reports operating-point metrics + mAP@0.5 alongside
  p50/p95 latency, an explicit CPU-load reading and an H4 closure check.

Results (**MEASURED**, 128 images / 929 objects / 71 classes with ground
truth, 114 images holding ≥2 objects; accuracy is independent of host load):

| Config (`ai.*`) | recall | multi-obj recall | F1 | mAP@0.5 | precision | verdict |
|---|---|---|---|---|---|---|
| shipped before (conf .5, min_box 20, imgsz 320) | 0.352 | 0.347 | 0.509 | 0.618 | 0.919 | baseline |
| conf 0.25 only | 0.454 | 0.448 | 0.584 | 0.618 | 0.816 | tried |
| min_box 8 only | 0.362 | 0.357 | 0.519 | 0.640 | 0.921 | tried |
| iou 0.7 only | 0.352 | 0.347 | 0.509 | 0.618 | 0.916 | tried — NMS was not the bottleneck |
| **shipped now (conf .25, min_box 8, imgsz 320)** | **0.477** | **0.471** | **0.601** | **0.640** | 0.813 | **chosen** |
| conf .25, min_box 8, imgsz 480 | 0.559 | 0.553 | 0.661 | 0.694 | 0.810 | rejected — breaks H4 on a loaded host |
| conf .35, min_box 8, imgsz 480 | 0.506 | 0.501 | 0.639 | 0.694 | 0.869 | rejected — lower recall than 480@.25 at 2× the latency |
| conf .25, min_box 8, imgsz 640 | 0.604 | 0.600 | 0.688 | 0.719 | 0.800 | rejected — accuracy ceiling, only 1.33× latency headroom |

Realtime (**MEASURED**, 2 × p50 must close under the 1.0 s target-lock):

| `yolo_imgsz` | p50, quiet host | p50 at 97–100 % host load | refresh @load | H4 @load |
|---|---|---|---|---|
| **320 (shipped)** | 107 ms | 334 ms (sweep) / 534–685 ms (benchmark) | 0.67 s at 334 ms, 1.07–1.37 s at 534–685 ms | **green ≤~60 % load, red at ~100 %** |
| 384 | — | 434 ms | 0.87 s | green, but only 1.15× margin |
| 416 | — | 509 ms | 1.02 s | **red** |
| 480 | 174 ms | 577 ms | 1.15 s | **red** |

Caveat, stated plainly: unrelated processes (browser, an LLM daemon, a second
`pytest` run) held the host at ~100 % CPU for part of this session; under that
degenerate condition even imgsz 320 measures 560–944 ms and H4 fails, so H4 is
load-sensitive by construction. The shipped config passes H4 at ≤~60 % host
load — `2 passed` twice in a row at 56–58 %. imgsz 320 is chosen because it is
the only size that still closes the loop on a busy machine; 416 and 480 do not
close it at all, which is why the measured-accuracy win at 480 was given up.

**Shipped change** (`config/config.yaml`): `confidence_threshold 0.5 → 0.25`,
`min_box_px 20 → 8`, `yolo_imgsz` **held at 320** (480 measured +20.7 pts
recall but was rejected for the realtime gate above). Net effect: recall
**+12.5 pts**, multi-object recall **+12.4 pts**, F1 **+9.2 pts**, mAP@0.5
**+2.2 pts**, at p50 107–184 ms under ≤50 % CPU load → `2 × p50` = 0.21–0.37 s
refresh vs the 1.0 s target-lock, and p50 534–685 ms at 100 % load → 1.07–1.37 s
(red) — see the load caveat above. Evidence: `logs/detection_baseline.json`
(p50 184 ms @50 % load) → `logs/detection_final.json` (p50 685 ms @100 % load)
(all runs in `logs/detection_*.json`).

### Confidence-gate split (safety follow-up)

`ai.confidence_threshold` was doing three jobs at once: the detector's cut,
`ObjectTracker.select()`'s bar, and `SafetyManager`'s `min_confidence` for
forward motion (both wired in `software/main.py`). Lowering it to 0.25
therefore also let the rover steer toward — and *drive forward on* —
0.25-confidence targets, where measured precision is ~0.81 (about 1 in 5
reported detections wrong). That silently relaxed the forward-motion safety
bar, and no test covered it.

Resolved by splitting the key (operator-approved):

- `ai.confidence_threshold: 0.25` — **what is reported**; the recall dial above.
- `ai.target_confidence: 0.5` — **what is acted on**: `ObjectTracker` target
  selection *and* the `SafetyManager` `LOW_CONFIDENCE` gate. Both keep the
  exact value they had before the accuracy work, so driving behaviour is
  unchanged while the extra low-confidence objects stay visible downstream and
  on the dashboard. Wired once as `RoverApp.target_confidence` and range-checked
  in `validate_config`.
- `MockDetector` now anchors its simulated confidence to `target_confidence`
  instead of the detection bar — anchored to the detection bar it reported
  0.25, produced no drivable target, and broke 3 red-team tests
  (`CAMERA_UNHEALTHY` reason, R4 latch release → `F`, scan360 approach).

- **Model benchmark (COCO128, 128 images, conf 0.25, min_box 8, host CPU
  97–100% — `logs/detection_cand_*.json`):** the shipped incumbent `yolo11s`
  @320 is the accuracy best of every eligible candidate (recall 0.4769 /
  multi-object 0.4711 / F1 0.6011 / mAP50 0.640). Those runs measured p50
  **534 ms → 1.07 s refresh at ~100 % CPU load, i.e. H4 red under
  saturation**; the same config clears the lock at ≤~60 % load (p50 184 ms
  @50 % → 0.37 s, `logs/detection_baseline.json`). `yolo26n` (2.57 M params)
  and `yolo11n` are ~4x faster (126 / 124 ms p50, 0.25 s refresh even
  saturated) but give up ~13 recall points (0.3541 / 0.3423). `yolo26s`
  matches the incumbent on recall (0.4726) yet is not faster (452 ms) and is
  weaker on mAP (0.5941). **No candidate beats the incumbent on accuracy, so
  no model change was made.**
- **`PekingU/rtdetr_v2_r18vd` @640 (`ai.backend: hf`):** the strongest raw
  detector measured — recall 0.8827, multi-object 0.8811, mAP50 0.8145 — but
  precision collapses to 0.2828 with **283 duplicate detections** (NMS-free
  300-query head) and p50 **3427 ms** → 6.85 s refresh vs the 1.0 s lock.
  **Rejected as latency-dead by ~6.8x**, and unusable as-is on precision.
- **Bug fixed:** `scripts/eval_detection.py::_build_detector` read only
  `detector._model.names` (the Ultralytics convention), so `ai.backend: hf`
  loaded successfully and then died with `detector exposed no class names` —
  every HF model was unbenchmarkable. `_class_names()` now also reads the HF
  `_pipe` tuple and falls back to `config.id2label`; HF detectors also take
  class names from `config.id2label`. Regression coverage:
  `tests/test_eval_harness.py` (3).
- **Harness gotcha:** `HFDetector._source()` prefers `ai.model_dir` over
  `ai.model_name`, so a HF benchmark run that changes only `ai.model_name`
  silently keeps evaluating the local `models/detr-resnet-50` snapshot. Clear
  `ai.model_dir` as well — the RT-DETR row above is only valid with both
  `--set ai.model_name=…` **and** `--set ai.model_dir=`.

- **+35 tests → 267 passed / 0 failed** (25 detection metrics + 7 confidence
  split + 3 eval-harness class names), then **+21 → 288** (8 frame-buffer +
  2 `model_dir`-shadow + 5 camera-collector + 6 ESP32-stream regression);
  `ruff check software
  tests` clean; `tools/validate_docs.py` PASS (0 errors / 0 warnings); README
  and `docs/testing.md` counts updated to 288.
- **Camera connection stall (found by running the collector with no camera on
  the network):** `ESP32Stream.open()` called `cv2.VideoCapture(url)` with no
  open timeout, so the FFmpeg backend retried the TCP connect for **93.5 s**
  before the tool printed `error: could not open … (is the ESP32-CAM on?)`.
  `open()` now selects the FFmpeg backend and passes
  `CAP_PROP_OPEN_TIMEOUT_MSEC` (falling back to the plain constructor if that
  overload is unavailable), and the previously **dead** `reconnect_timeout_s`
  config key — read from `config.yaml` and passed in by `RoverApp` but never
  referenced — is now honoured as a backoff so a failed read does not pay the
  connect timeout again. Measured after the fix: **7.2 s** total (5.1 s
  bounded connect + interpreter/model import), exit code 2, same error text.
  Regression coverage: `tests/test_esp32_stream.py` (6).
- **Late additions (same session):** `software/camera/frame_manager.py` gained
  a single-slot latest-frame buffer with dropped-frame counting and frame age
  (wired into `RoverApp.step`, defensive against camera stubs that expose no
  `stats`); `HFDetector` now warns when `ai.model_dir` shadows a mismatched
  `ai.model_name`; class-name discovery moved to
  `software.ai.detector.detector_class_names` so the benchmark harness and the
  new collector share one implementation. Deliverables added:
  `docs/MODEL_SELECTION.md`, `scripts/collect_camera_dataset.py` (15-condition
  capture plan; mock source must never be quoted as camera evidence),
  `tests/test_camera_collector.py` (5, mock-source only).
- **Runtime axis measured — ONNX wins, OpenVINO regresses.** `onnx 1.23.0` and
  `openvino 2026.4.0` installed, `yolo11s` exported both ways, each arm run
  through the same harness at **matched 160 frames, back-to-back at 100 % CPU
  load**. **ONNX: p50 181 ms vs PyTorch 435 ms (2.4× faster), p95 290 vs
  982 ms, refresh 0.36 s vs 0.87 s** — realtime headroom 1.15× → 2.75× with
  accuracy columns identical between the two fp32 exports. **OpenVINO:
  461 ms — slower than PyTorch on this 2C/4T host, rejected on measurement.**
  The shipped config **stays on `.pt`** (a fresh checkout has no `.onnx`; export
  is one command, documented). Evidence: `logs/detection_yolo11s_{pt,onnx,openvino}.json`,
  `reports/MODEL_BENCHMARK.md` §6, `docs/MODEL_SELECTION.md` §4.
- **Attribution:** COCO128 added to `THIRD_PARTY.md` (CC BY 4.0). The harness
  reuses the already-declared `ultralytics` / `opencv-python` and stdlib only.
  Two **export-only** packages were installed for the runtime axis
  (`onnx 1.23.0`, `openvino 2026.4.0`): neither is imported by rover code and
  deliberately neither is added to `requirements.txt`, because that file is
  gated on "every entry must be imported by code".
- **Latency caveat:** the accuracy-row runs above were taken while host CPU
  load varied between 10% and 77%, so cross-row latency there is indicative;
  the runtime-axis runs were all taken at 100 % load. The authoritative
  realtime evidence is still the H4 test, which passes with the shipped config
  (`tests/test_redteam_h4_realtime.py`, 2 passed in 9.9 s) — re-run it with
  the host at ≤~60 % load.
- **Still HARDWARE REQUIRED:** COCO128 is an offline COCO subset, not this
  rover's camera. On-robot confirmation of the new operating point
  (confidence 0.25 accepts more borderline boxes) belongs in the hardware
  gate — `confidence_threshold` is the dial to turn back up if the rover
  chases false positives.

---

## 10. Wokwi simulation + wiring documentation session (2026-09-27)

Operator directive: continue the session that produced the Wokwi project and
the wiring deliverables. All software evidence; the only MEASURED claim is
noted as such.

- **Wokwi project completed** (`diagrams/wokwi/`): `diagram.json` (UNO +
  L298N + HC-SR04 + four direction LEDs, `chip-l298n` pinned `@1.0.5`),
  `sketch.ino` (verbatim firmware copy, diff-guarded), and the previously
  missing **`wokwi.toml`**, which points Wokwi at the compiled firmware —
  without it the project could not be started at all.
- **`tools/build_wokwi_firmware.py`** — compiles the *shipping*
  `arduino/rover_controller/rover_controller.ino` with arduino-cli into
  `diagrams/wokwi/build/` and verifies the exact artifacts `wokwi.toml`
  declares (the build reads the config instead of hardcoding names).
  **MEASURED:** exit 0, `rover_controller.ino.hex` 15563 B, `.elf` 44412 B,
  5526 B (17%) flash / 288 B (14%) RAM.
- **`tools/run_wokwi_sim.py`** — one command: build → `wokwi-cli lint` →
  headless simulation with `--expect-text DIST:` and a serial log in
  `logs/wokwi_serial.log`. Distinct exit codes (1 build, 2 CLI missing,
  3 token missing, 4 simulation failed) so an absent prerequisite can never
  be mistaken for a pass.
- **Wiring schematic** (`tools/generate_wiring_schemdraw.py`) — power +
  signal chain drawn from the firmware pin map → `diagrams/` **and**
  `figures/wiring_schemdraw.{png,svg}` (byte-identical copies); the printed
  4-page reference is `reports/AI_Rover_Wiring_and_Breadboard.pdf`.
- **+15 tests** (11 in `test_wokwi_sim` — pin wires, `wokwi.toml` contract,
  build-script contract, Intel-HEX artifact, three runner failure paths, two
  scenario-shape/coverage guards — and 4 in `test_wiring_schemdraw` —
  outputs present in both directories, generator labels vs firmware pins,
  PDF title/source-of-truth) → **303 passed / 0 failed**;
  `ruff check software tests` **All checks passed**.
- **MEASURED:** `wokwi-cli lint diagrams/wokwi` → `✓ No issues found`
  (wokwi-cli v0.27.1), i.e. every part type, pin name and wire endpoint in
  `diagram.json` resolves against the Wokwi registry.
- **MEASURED — live simulation (wokwi-cli v0.27.1, token supplied by the
  operator):** three runs, all exit 0 with
  *Scenario completed successfully* / *TEST PASSED*, serial logs in
  `logs/wokwi_serial*.log`:
  - **plain run** — `DIST:100.3`, `STATUS:OK`, `TICKS:0,0` (HC-SR04 echo at
    the diagram's 100 cm, telemetry cadence 200 ms);
  - **`scenarios/safety.yaml`** — drivers released at boot (IN1/IN3 low),
    `X` → `STATUS:ERROR` with the bridge still released, `F` → IN1/IN3 high
    at 100 cm, **3.6 s of silence → watchdog `STATUS:STOP` and both bridges
    released**, then recovery on the next `F` and a clean `S`;
  - **`scenarios/obstacle_gate.yaml`** — `set-control` moved the simulated
    sonar to **10 cm** (< `EMERGENCY_STOP_CM` 15), `F` → **`STATUS:STOP` with
    IN1 low**: the emergency gate blocks translation in simulation, the same
    path the host harness checks (`sensor_dead`/`blocked`).
  Scenario assertion semantics were verified, not assumed: a deliberately
  wrong `expect-pin` exits **1**, so a green run is real. One alpha-API trap
  found and fixed: `expect-pin` reads `value:`, while `expected:` compares
  against `undefined` and fails for the wrong reason — now guarded by
  `test_scenarios_are_well_formed_and_reference_real_parts`.
- **Label: SIMULATED (host-verified firmware behaviour in the Wokwi
  simulator).** Still **HARDWARE REQUIRED** for anything physical — a
  simulated H-bridge and sonar are models, not the rover.
- **Docs synced:** README §16/§20 (commands, deliverables, 303),
  `docs/testing.md` (303 + the new test files), `docs/21_CIRCUIT_CONNECTIONS.md`
  (companion figure, PDF, Wokwi project), `.gitignore` (`diagrams/wokwi/build/`).

---

## 11. Session log — 2026-09-27 (data-link consistency + team walkthrough PDF)

**Defect found (documentation, pre-existing):** eight documents and five figure
generators claimed a **wired ESP32↔Arduino UART through a logic level
shifter**. The code says otherwise: `esp32/camera_stream/camera_stream.ino`
serves Wi-Fi MJPEG (`/stream`) and uses `Serial` only for debug prints, while
`software/hardware/arduino_serial.py` is the sole command link (laptop USB →
Arduino, 9600 baud). The ESP32-CAM is wired **5V + GND only**; D0/D1 stay free.

- **Fixed at the source** (`tools/generate_tables.py`,
  `tools/generate_docs.py`, `tools/create_bom.py`, `tools/generate_diagrams.py`,
  `tools/generate_figures.py`) **and mirrored into every generated output**:
  `docs/01, 05, 08, 10, 21, 22, 28, 31`, `BILL_OF_MATERIALS.md`, `BOM.csv`.
  - `docs/21`: the four UART rows are gone; the wiring table now ends with a
    **DATA LINKS** note (Wi-Fi MJPEG out, laptop USB serial in, D0/D1 free).
  - `docs/22`: D0/D1 documented as *Laptop (USB Serial)*; ESP32 GPIO 1/3 as
    *Debug/flash UART — NOT WIRED*.
  - FMEA `FM-02` root cause corrected (host USB link, not an MCU↔ESP32 jumper);
    `FM-09` occurrence lowered 4→1 with RPN 120→30 because the hazard wire
    does not exist.
  - **BOM:** level-shifter line item removed — total **$64.40 → $62.90**,
    acquisition **$23.00 → $21.50** — and §3 now explains why none is needed.
- **Figures regenerated (17 files, hash-diff verified, nothing else touched):**
  `01_system_architecture`, `03_hardware_architecture` (title now *… and
  Data-Link Topology*), `05_esp32_pipeline`, `15_full_robot_block_diagram`,
  `circuit_diagram` (PNG ×3 dirs + SVG ×2) — the shifter box became a
  **LAPTOP (HOST)** box with dashed *Wi-Fi MJPEG* and solid *USB serial* legs.
- **New guard:** `tests/test_docs_data_links.py` (6 tests) fails if any design
  doc, generator or BOM reintroduces the UART claim, if `docs/21` wires a
  non-power ESP32 pin, or if D0/D1 stop being documented as the host link.
- **MEASURED:** `pytest tests -q` → **309 passed**; `ruff check software tests`
  → **All checks passed**; `tools/validate_docs.py` → **PASS (0/0)**.
- **Deliverable added:** `docs/PROCESS_WALKTHROUGH.md` + `tools/generate_process_pdf.py`
  → `reports/AI_Rover_Process_Walkthrough.pdf` (end-to-end process guide for
  the team, with the corrected connection tables and figures).

---

## 12. Session log — 2026-09-27 (hardware toolchain + dev-loop speedups)

**Toolchain installed on the dev PC:** `arduino-cli` 1.5.1 (winget, machine
PATH) with `arduino:avr` 1.8.8 and `esp32:esp32` 3.3.12 (new index URL);
ESP32-CAM compiles (`1013913 B / 32%`), UNO compiles (`5526 B / 17%`, gate-identical).

- **`tools/hw_check.py` (new):** one CLI for real-circuit testing —
  `ports` / `flash` / `serial` / `mon` / `esp32` / `all`, exit codes 0/1/2
  (pass/fail/skip). Serial battery: telemetry heartbeat, `DIST:-1` wiring hint,
  `STATUS`/`TICKS` format, junk → `STATUS:ERROR`, speed suffix, 3 s watchdog
  STOP+recovery; optional `--obstacle` (15 cm gate) and `--motion --space`.
  Smoke-tested: both compiles PASS, missing hardware SKIPs, unreachable camera
  FAILs fast. Known trap guarded: `COM3` on this PC is Intel AMT SOL, not a board.
- **Port auto-detect (dev-loop speedup):** `arduino_serial.py` gained
  `detect_board_port()` (CH340/CP210/Arduino/ESP32 descriptions, system ports
  denied) and `connect()` now falls back to it once when `serial.port` fails to
  open — no config edit needed when the board appears on a new COM port.
  Guards: `test_detect_board_port_skips_system_ports`,
  `test_detect_board_port_returns_none_without_board` (+2 tests).
- **`tools/dev.py` (new):** single-command gates — `py -3.12 tools\dev.py`
  (ruff + pytest), `--quick` (`pytest -x`), `--watch` (re-run on file change),
  `--fix`, `--hw` (adds `hw_check all`).
- **MEASURED:** `pytest tests -q` → **311 passed / 0 failed** (309 + 2 port
  auto-detect guards); `ruff check software tests` → **All checks passed**;
  `tools/validate_docs.py` → **PASS (0/0)**. Counts synced in README, docs/testing.md,
  docs/PROCESS_WALKTHROUGH.md and §4 of this report.
