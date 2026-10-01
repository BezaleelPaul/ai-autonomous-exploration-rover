# Phase 0 — Integration Plan

**Date:** 2026-09-25 | **Status:** Phase 1 **software-side COMPLETE** (2026-09-25);
hardware gate still pending (battery + buck not bought). Phase 0 plan was approved
verbally by the operator ("continue which feels best").

## Phase 1 progress log (software side — all verified)

| Item | Result |
|---|---|
| R1 run-command crash | **FIXED** — `software/logging/` → `software/telemetry/`; `python software/main.py --help` returns 0 (regression-tested) |
| R2 invalid char no STOP | **FIXED** — invalid branch now clears `currentCmd='S'` + `stopMotors()` before `STATUS:ERROR`; compiles (`arduino:avr:uno`, 4448 B) |
| R3 constant drift | **GUARDED** — `tests/test_firmware_contract.py` asserts YAML ↔ `.ino` equality for 15 cm / 3 s / PWM 200 |
| R4 emergency latch lockout | **FIXED** — latch auto-releases at ≥ slow_cm (hysteresis), `reset_latch()` kept; 4 new tests |
| R5 manual 3 s post-key motion | **FIXED** — `ManualMotionGuard` (new) auto-sends STOP after `rover.movement_timeout_s`; 6 new tests |
| R6 ESP32 no Wi-Fi reconnect | **FIXED** — 5 s reconnect loop in `camera_stream.ino`; compiles (`esp32:esp32:esp32cam`, 1.03 MB) |
| R7 README "35 tests" | **FIXED** → 58 passed |
| R8 7.6 MB junk log | **DELETED** |
| Toolchain | arduino-cli 1.5.2 + `arduino:avr` + `esp32:esp32` both compile the repo sketches |
| pyserial | installed (3.5) in Python 3.12 |
| Lint | `ruff` installed; `ruff.toml` added (deliberate fail-safe catch-alls excluded); **All checks passed** |
| `docs/PINOUT.md` | created (authoritative, extracted from firmware) |
| Tests | **58 passed** (was 39) |

**Remaining Phase 1 gate (hardware):** TEST 01-04 on real motors — blocked on
battery + buck purchase and L298N jumper/ground checklist. Commits deliberately
**not** made (no git repo yet; awaiting operator instruction).

## Red-team round (MASTER_TEST_PROMPT) — 2026-09-25

| Item | Result |
|---|---|
| Independent red-team report | [`TEST_REPORT.md`](../../TEST_REPORT.md) — baseline 137/162 pass, findings 1 CRITICAL · 4 HIGH · 10 MEDIUM · 11 LOW |
| Fix round | **All 25 failing tests fixed** (C1 fail-safe, H1/H2/H3 mode+framing, M1–M9, docs/config audit) — see [`REGRESSION_REPORT.md`](../../REGRESSION_REPORT.md) |
| Regression | **288 passed / 0 failed** (after model benchmark + frame-buffer + collector + ESP32 stream work); `ruff` All checks passed; UNO 5526 B + ESP32 1.03 MB compile; 21/21 firmware-host scenarios; 4 mock modes run clean |
| Doc/config hygiene | README + docs/testing.md counts → 288; docs/18 host corrected; 8 byte-identical doc pairs deduplicated; unused requirements removed (`timm`, `networkx`, `qrcode`) |
| Detection accuracy | Labelled benchmark added (`scripts/eval_detection.py` on COCO128, `software/ai/detection_metrics.py`); shipped `confidence_threshold` 0.5→0.25, `min_box_px` 20→8 with `yolo_imgsz` **held at 320** (480 measured +20.7 pts recall but broke the realtime gate at 100 % host load) → **recall 0.352→0.477, multi-object recall 0.347→0.471, F1 0.509→0.601, mAP50 0.618→0.640** at p50 184 ms @50 % CPU load (0.37 s refresh, H4 green; 534–685 ms @100 % load → H4 red). Safety split added: new `ai.target_confidence: 0.5` keeps `ObjectTracker` + `SafetyManager` forward-motion gate at the old value so the lower detection bar cannot relax driving caution — see `REGRESSION_REPORT.md` §9 |
| H4 fix round | `ai.backend` → **yolo** (yolo11s, measured p50 119–211 ms @320 vs DETR 4135 ms), `inference_interval` 4→2 → refresh ~0.42 s < 1.0 s lock; `--mock` forces `MockDetector`; `logs/benchmark.json` regenerated (DETR evidence kept in `logs/benchmark_detr.json`); enforced by `tests/test_redteam_h4_realtime.py` |
| H4 status | **CLOSED on host** (MEASURED); on-robot AI confirmation remains part of the hardware gate |
| Phase 9+ session | Future work moved to [`../future-work/30_FUTURE_WORK.md`](../future-work/30_FUTURE_WORK.md); PID/odometry modules + D2/D3 encoder ISRs + `TICKS` telemetry + `control:` config landed (+22 tests → 186) |
| Protocol v2 session | Firmware P velocity loop + laptop P-steering via optional speed suffix (`F180`); `control.velocity_*`/`steering_*` keys contract-synced (+13 tests → 199, host 21/21) |
| Dataset eval harness | software/telemetry/event_eval.py + scripts/evaluate.py (+33 tests → 232): 10 safety/protocol invariants over logs/events.csv, distance-state data quality, logs/eval.json |
| Detection accuracy | `software/ai/detection_metrics.py` + `scripts/eval_detection.py` (+25 tests → 257, +7 confidence split → 264, +3 eval-harness class names → 267, +8 frame buffer + 2 `model_dir` shadow → 277, +5 camera collector → 283, +6 ESP32 stream → **288**): COCO128 labelled benchmark, precision/recall/F1, multi-object recall, mAP@0.5, duplicate counting, latency + H4 check → `logs/detection_eval.json`; `ai.target_confidence` decouples "reported" from "acted on" |
| Hardware gate | **unchanged — HARDWARE REQUIRED / NOT TESTED** (battery + buck not bought) |



## 0. Guiding rule (from MASTER PROMPT)

> MVP first. Advanced components (encoders, MPU6050, PID, servo) may be purchased
> now, but their **software integration happens only after the rover can drive,
> see, communicate, and stop safely.**

Sequencing principle: **Repositories → compatibility analysis → architecture →
Phase N → test → Phase N+1 → test.** Every phase ends with a passing test gate;
a failure is traceable to exactly one phase.

## 1. Current state (measured 2026-09-25)

| Item | State |
|---|---|
| Architecture | Laptop-in-the-loop: ESP32-CAM → Wi-Fi → laptop (OpenCV/AI) → USB serial → Arduino (safety) → L298N → motors — **matches MASTER PROMPT §2 exactly** |
| Code | Complete for Phases 1-8 *in software*, mock-verified |
| Tests | **39 passed** (mock only, no hardware) |
| Hardware | Present per BOM except battery + buck (Need to Buy); **never powered as a system yet** |
| Known P0 bugs | R1 (documented run command crashes), R2 (invalid serial char doesn't STOP) |
| Measurements | Only DETR CPU benchmark (0.2 FPS) exists. No camera, serial, latency, or stopping-distance measurements. |

**Honest summary: this is a well-built prototype awaiting hardware bring-up and two
bug fixes — not a from-scratch integration.** The plan below maps MASTER PROMPT
phases onto the existing code so we fix/verify instead of rewrite.

## 2. Phase map

### Phase 1 — MOTOR CONTROL (P0)
- Install pyserial; create `.venv` (Py 3.12); verify Arduino toolchain compiles `rover_controller.ino`.
- Fix **R1**: rename `software/logging/` → `software/telemetry/` (or restructure imports) so `python software/main.py` works; update README.
- Fix **R5**: manual mode — resend command / send heartbeat while key held, or document 3 s decay behavior.
- Build checklist: L298N ENA/ENB jumpers removed, rails separated, common ground.
- **Gate:** TEST 01-04 (F/B/L/R/STOP) pass on real motors; `docs/PINOUT.md` + `THIRD_PARTY.md` created; commit `01-working-motor-control`.

### Phase 2 — SAFETY (P0)
- Fix **R2**: invalid char → `stopMotors()` + `STATUS:ERROR`.
- Fix **R4**: define emergency-latch reset policy (manual mode key / explicit reset command / boot only — decide and test).
- Sync check **R3**: single source for 15 cm / 3 s (document in `PROTOCOL.md`, add a unit test asserting YAML↔firmware constants table stays equal, or generate the `const` block from YAML).
- **Gate:** TEST 05 (obstacle < 15 cm overrides AI FORWARD), TEST 06 (comms loss → STOP ≤ 3 s), TEST 12 (invalid command → STOP). Commits `02-ultrasonic-safety`, `03-watchdog`.

### Phase 3 — ESP32-CAM (P0)
- Flash `camera_stream.ino`, record real IP in `config.yaml`.
- Add Wi-Fi reconnect loop (R6) — small, safe firmware change.
- **Measure** (record in `docs/measurements/`): connection time, FPS, latency, frame-drop rate, reconnect behavior, image quality at 2 lighting levels. **No claims without numbers.**
- **Gate:** TEST 07 + TEST 08 pass. Commit `04-esp32-camera`.

### Phase 4 — OPENCV PIPELINE (P0)
- Laptop receives real frames via `ESP32Stream` (code already exists).
- **Measure** frame acquisition rate + end-to-end camera→laptop latency.
- **Gate:** 30 min stream without unrecovered failure. Commit `05-opencv-pipeline`.

### Phase 5 — OBJECT DETECTION (P0)
- Benchmark on **this** laptop: `color` (baseline), `yolo11n`, `yolo11s@320`, (DETR already measured at 0.2 FPS — excluded unless surprising results).
- Record: inference ms, effective FPS with `inference_interval`, CPU/RAM, confidence stability, detection distance, false pos/neg in 3 lighting conditions.
- Select **one** target class + one backend by measurement; default config switches to the winner; **keep mock/color fallbacks**.
- **Gate:** TEST 09 passes at ≥2 effective FPS (steering needs it). Commit `06-object-detection`.

### Phase 6 — TARGET TRACKING (P1)
- Verify `ObjectTracker` (confidence gate + lock hysteresis) on real detections; add target-lost state exposure to telemetry if missing.
- Center/zone math already exists (`scene_analyzer`) — validate against recorded frames.
- **Gate:** TEST 10 (target lost → stop/search, no oscillation). Commit `07-target-tracking`.

### Phase 7 — BEHAVIOR CONTROLLER (P1)
- `DecisionEngine` FSM exists (IDLE/SEARCHING/ALIGNING/APPROACHING/…); reconcile its state names with MASTER PROMPT §8 list, add `COMMUNICATION_LOST`/`OBSTACLE_STOP` explicit states if not represented (safety reasons exist — surface them as states).
- Keep perception ⊥ behavior (already separated).
- **Gate:** mock scenario suite extended for new states still passes. Commit `08-autonomous-steering` (includes Phase 8).

### Phase 8 — SERIAL PROTOCOL (P0, interleaved with 1-2)
- Current single-char protocol **works**; do NOT add CMD,<move>,<speed>,<seq> yet (§17: no unneeded complexity). Document actual protocol in `PROTOCOL.md`.
- Revisit framing/ACK only if Phase 1-7 testing shows real corruption.
- **Gate:** TEST 11 + TEST 12 pass. (Commit folded into `02`/`08`.)

### Phase 9+ — ENCODERS, PROPORTIONAL, PID, IMU, FUSION (P2)
- **STARTED 2026-09-25** (operator request): PID module, D2/D3 encoder tick
  counting + `TICKS` telemetry, `control:` config landed; full detail + backlog
  moved to [`../future-work/30_FUTURE_WORK.md`](../future-work/30_FUTURE_WORK.md).
- Still holds: PID only with measured evidence it beats P-control (MASTER PROMPT
  §11); MPU6050 last, explicitly **not** a self-balancing claim; encoders need
  hardware purchase + PPR specs before any physical closed-loop claim.

## 3. Final integration criteria — MVP (P0/P1)

- [ ] Arduino motor control works (real hardware)
- [ ] HC-SR04 safety overrides AI
- [ ] Comms watchdog works
- [ ] ESP32-CAM streams reliably
- [ ] Laptop receives frames
- [ ] AI detects selected target (measured backend)
- [ ] Target position calculated + loss handled
- [ ] Laptop ↔ Arduino validated commands
- [ ] Rover turns toward + approaches target
- [ ] Obstacle forces STOP; comms loss forces STOP
- [ ] Safe startup / safe shutdown
- [ ] Complete demo works
- Advanced (encoders, P/PID, IMU, telemetry, fusion, servo): tracked separately, P2/P3.

## 4. Test plan

Existing: 39 mock unit/scenario tests + `docs/25_TEST_PLAN.md` (32 TCs with blank
Actual fields — correct: fill only what is physically run).
Add per phase: hardware test rows in `data/test_results.csv` with Expected/Actual/
Pass-Fail/Notes (MASTER PROMPT §15, TEST 01-15). Failure-mode tests (§16) run
after Phase 8: unplug USB, kill laptop process, block camera, remove target,
disconnect ultrasonic, reset Arduino mid-drive.

## 5. Risk register (top 5)

| Risk | Impact | Mitigation |
|---|---|---|
| Battery/buck not yet purchased | Blocks Phase 1 | Buy immediately (in parallel with software prep) |
| YOLO ~1 FPS on CPU | Steering lag/oscillation | frame-skip + hysteresis (exists); consider yolo11n; fallback color detector |
| Unknown motor stall current | Driver/battery damage | measure in Phase 1 (clamp current on bench supply), keep PWM ≤ 200 |
| Brownout resets | Random unsafe behavior | separate rails + common ground; verify in Phase 1 |
| Doc claims drifting from reality | Misleading report/audit | docs updated per phase; `tools/validate_docs.py` run each commit |

## 6. Deliverables on completion (MASTER PROMPT §25)

Final architecture, folder structure, pin map, hardware list, dependencies,
install/build/run instructions, test results, known limitations, third-party
licenses, **measured** performance, troubleshooting, future work, `FINAL_STATUS.md`.

---

**⏸ END OF PHASE 0. Awaiting your validation of this plan before Phase 1 begins.**
Decisions needed from you:
1. Project license choice (LICENSE_REPORT L-5).
2. Approve/adjust phase ordering above.
3. Confirm battery + buck purchase timing (only hardware blocker).
