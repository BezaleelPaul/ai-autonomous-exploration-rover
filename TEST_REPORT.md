# TEST_REPORT - AI Visual Intelligence Rover (360 Vision Self-Balancing Rover)

Independent QA / red-team report generated from `MASTER_TEST_PROMPT.md`.
Report-only engagement: no source, config, or existing test file was modified.
New evidence tests were added under `tests/` only.

| Field | Value |
|---|---|
| Date | 2026-09-25 |
| Spec | `MASTER_TEST_PROMPT.md` (sections 1-30) |
| Environment | Windows 11, Python 3.12.10, pytest 9.1.1, ruff, arduino-cli 1.5.2-rc.1, g++ (host harness) |
| Hardware available | NONE (no rover, no battery, no buck converter, no ESP32-CAM, no COM port) |
| Label convention | PASS / FAIL / NOT TESTED / SIMULATED / HARDWARE REQUIRED / NOT SIMULATABLE |

---

## 1. Executive summary

**Verdict: NOT READY for physical autonomous testing.**

What is solid:

- Build: UNO firmware, ESP32-CAM firmware, 31 Python modules, CLI entry points, lint - all **PASS**.
- Pre-existing test suite: **58/58 PASS** (unchanged, re-verified after adding 104 red-team tests).
- Safety units (priority chain, latch hysteresis, comm timeout, manual watchdog, config validation): **PASS**.
- Firmware watchdog timing, obstacle gate, startup STOP: **PASS (SIMULATED)** - host-compiled copy of the real `.ino`.
- Pin map: `docs/PINOUT.md` <-> firmware constants: **PASS**.
- Documentation validator tool: 0 errors, 0 warnings - **PASS** (but see finding M9).

What blocks release: **1 CRITICAL** finding - an ultrasonic sensor failure (or an out-of-range/stale reading) bypasses *both* safety layers and the rover keeps driving forward. Four separate tests fail on it.

New evidence suite added: 104 tests in 6 files; **79 pass / 25 fail**. Every one of the 25 failures is a defect report (assertion text is the evidence), not a flaky test - the whole suite is deterministic and leaves the repository unmodified (`logs/events.csv` delta = 0 on a full run).

**Section 27 score (see also section 27 below):**

```
BUILD:                PASS
UNIT TESTS:           97/110
INTEGRATION TESTS:    40/52
SAFETY TESTS:         68/80
SIMULATION TESTS:     40/52
WOKWI TESTS:          NOT SIMULATABLE (0/0)   [superseded 2026-09-27 - see section 6]
HARDWARE TESTS:       0/13  (all NOT TESTED / HARDWARE REQUIRED)
CRITICAL FAILURES:    1
HIGH FAILURES:        4
MEDIUM FAILURES:      10
LOW FAILURES:         11
```

**Release gate: NOT READY** (motor safety broken + obstacle stop bypassable + motor voltage/driver capability unverified).

---

## 2. Architecture review

Actual data flow (verified by reading + tracing code, not documentation):

```
laptop Python (RoverApp)
  camera: ESP32Stream (HTTP MJPEG) | mock
  AI:     create_detector() -> HFDetector(DETR) / ColorDetector / Mock
  nav:    ObjectTracker -> SceneAnalyzer -> DecisionEngine -> ObstacleAvoidance
  safety: SafetyManager (priority chain) -> ArduinoSerial.send()
     |  USB-serial, single ASCII byte + '\n', 9600 baud
     v
Arduino UNO (rover_controller.ino)
  single-byte actuation (NO framing) + HC-SR04 gate + 3000 ms comm watchdog
     -> L298N -> 2x gear motors
ESP32-CAM: camera only, no control role, no CLAHE/FSM, no link to the Arduino
```

Notes:

- There are exactly **two** command gates: `ObstacleAvoidance.override()` (rewrites F/B to S) and `SafetyManager.check()` (priority chain). Firmware adds a third (`blocked`) plus a watchdog.
- `DecisionEngine.emergency()` / `to_search()` / `STATES` are never reached (finding L6).
- The ESP32 has **no** safety or control responsibility in code, contradicting docs/02 and docs/18 (finding M9).

## 3. Build results

| Check | Result | Evidence |
|---|---|---|
| `arduino-cli compile --fqbn arduino:avr:uno arduino/rover_controller` | **PASS** | 4448 B flash (13% of 32256), 258 B RAM (12% of 2048) |
| `arduino-cli compile --fqbn esp32:esp32:esp32cam esp32/camera_stream` | **PASS** | 1026129 B flash (32% of 3145728), 57224 B RAM (17% of 327680) |
| Import all `software.*` modules (31) | **PASS** | 0 failures |
| `python -m software.main --help` and `python software/main.py --help` | **PASS** | exit 0, `scan360` listed (test R1) |
| `ruff check software tests` | **PASS** | All checks passed |
| `pytest tests -q` | **FAIL (25)** | 137 passed, 25 failed - all 25 are red-team defect reports |
| `pip check` (shared interpreter) | **PASS for repo deps** | conflicts reported only for unrelated global packages (aider-chat, pdfplumber) - see INFO I1 |
| Missing/broken paths in README command list | **PASS** | every referenced script/tool file exists |
| Requirements resolvable / unused | **FAIL (LOW)** | `timm`, `networkx`, `qrcode` never imported (finding L4) |

## 4. Unit test results

Full suite: **137/162**. Categories use the mapping below (110 unit + 52 integration = 162).

| File | Tests | Pass | Fail | Category |
|---|---:|---:|---:|---|
| test_decision_engine.py | 4 | 4 | 0 | unit |
| test_detector.py | 5 | 5 | 0 | unit |
| test_enhance.py | 4 | 4 | 0 | unit |
| test_firmware_contract.py | 9 | 9 | 0 | unit (static contract) |
| test_hf_detector.py | 3 | 3 | 0 | unit |
| test_manual_guard.py | 6 | 6 | 0 | unit |
| test_navigation.py | 5 | 5 | 0 | unit |
| test_regression_fixes.py | 3 | 3 | 0 | unit |
| test_safety.py | 13 | 13 | 0 | unit |
| test_scenarios.py | 2 | 2 | 0 | unit |
| test_serial_protocol.py | 4 | 4 | 0 | unit |
| **baseline subtotal** | **58** | **58** | **0** | |
| test_redteam_docs_config.py (new) | 21 | 11 | 10 | unit |
| test_redteam_serial_fuzz.py (new) | 18 | 17 | 1 | unit |
| test_redteam_property.py (new) | 13 | 11 | 2 | unit |
| test_redteam_safety_chain.py (new) | 21 | 14 | 7 | integration |
| test_redteam_watchdog.py (new) | 13 | 12 | 1 | integration |
| test_redteam_firmware_host.py (new) | 18 | 14 | 4 | integration |
| **new subtotal** | **104** | **79** | **25** | |
| **TOTAL** | **162** | **137** | **25** | |

- UNIT TESTS: **97/110** (58 baseline + serial fuzz + property + docs/config audit).
- INTEGRATION TESTS: **40/52** (RoverApp loop with mock camera/serial, CLI subprocess, host-compiled firmware binary).

The 25 failing tests, grouped by finding: C1 (4), H1/H2 (3), H3 (2), H4 (0 - see section 11), M1 (1), M2 (1), M3 (1), M4 (1), M5 (1), M6 (2), M9 (3), L1 (1), L2 (1), L4 (1), L5 (1), docs/config audit remainder (2).

## 5. Simulation results

| Simulation | Result | Label |
|---|---|---|
| `--mock --mode observe` run | runs, emits STOP/target-less log stream, clean shutdown | **SIMULATED** |
| `--mock --mode search` run | runs, **0 rotation commands issued** (finding H1) | **SIMULATED / FAIL** |
| `--mock --mode scan360` run | runs, **0 rotation commands issued** (finding H2) | **SIMULATED / FAIL** |
| `--mock --mode manual` run | keyboard loop + auto-stop path exercised by unit tests | **SIMULATED** |
| RoverApp loop (200 steps, mock HW): step latency median 1.3 ms, p95 3.7 ms, max 23.9 ms | **PASS** | **SIMULATED** |
| Largest gap between consecutive motion commands: max 23.6 ms vs 3000 ms firmware timeout | **PASS** | **SIMULATED** |
| Firmware host harness: 18 scenarios compiled from the real `.ino` with stubbed Arduino core | 14 PASS / 4 FAIL | **SIMULATED** |
| `tools/simulate_control.py` (Kp sweep figure written to `figures/`) | **PASS** | **SIMULATED** |
| PyBullet physics simulation | not present in repo | **NOT TESTED** |
| Sensor noise / motor mismatch / battery sag scenarios | no physics or electrical model exists | **NOT TESTED** |

## 6. Wokwi results

**NOT SIMULATABLE** - there is no Wokwi project anywhere in the repository (no `wokwi.toml`, no `diagram.json`, no `.wokwi/`). Nothing was pretended: firmware behaviour was instead verified with a host-compiled harness (section 5) and static contract tests.

> **UPDATE (2026-09-27, after this report):** the finding above is now fixed —
> `diagrams/wokwi/` holds `diagram.json`, `wokwi.toml`, `sketch.ino` and two
> automation scenarios, built from the shipping firmware by
> `tools/build_wokwi_firmware.py`, guarded by `tests/test_wokwi_sim.py`, and
> linted clean by `wokwi-cli v0.27.1` ("No issues found"). The live run has
> since been executed (`tools/run_wokwi_sim.py --scenario ...`): three runs,
> exit 0 each — boot = STOP, `X` → `STATUS:ERROR`, `F` actuates, 3 s watchdog
> → `STATUS:STOP` + bridge released, and at 10 cm the firmware refuses `F`.
> Label is now **SIMULATED (PASS)**, still **HARDWARE REQUIRED** for physical
> behaviour. See `REGRESSION_REPORT.md` §10.

## 7. Integration results

| Flow | Result |
|---|---|
| CLI: both documented invocation styles start and print usage | **PASS** |
| `startup()` -> `send('S')` before loop, `shutdown()` -> STOP + disconnect (host harness `startup`/`reboot` scenarios) | **PASS (SIMULATED)** |
| Full perceive->decide->safety->send chain over 200 mock steps, no exception, clean shutdown | **PASS (SIMULATED)** |
| Serial death mid-run -> all subsequent commands `S` | **PASS (SIMULATED)** |
| Target lost -> `S` | **PASS** (main.py bypasses the engine, see M4) |
| Search mode end-to-end (rotate until target) | **FAIL** - 0/120 motion commands, last reason `LOW_CONFIDENCE` |
| scan360 mode end-to-end (scan, then approach visible target) | **FAIL** - 0/120 motion commands; visible centred target ignored |
| Malformed / corrupt serial input end-to-end to the firmware | **FAIL** - firmware actuates (finding H3) |
| Dead ultrasonic end-to-end to the firmware + Python chain | **FAIL** - both layers return GO (finding C1) |
| ESP32 live stream, real COM-port serial, dashboard over network | **NOT TESTED** (no hardware) |

## 8. Safety results

SAFETY TESTS: **68/80** (12 failures, all defect reports).

| Safety mechanism | Test result | Label |
|---|---|---|
| Priority chain (emergency > sensor > comm > camera > confidence > nav) | **PASS** at unit level | PASS |
| Emergency latch engage/release hysteresis (R4) | **PASS** in isolation (`test_safety.py`) | PASS |
| Emergency latch through the **autonomous** path | **FAIL** - `assert False is True: emergency latch never engaged in the autonomous path (R4 ineffective)` | FAIL |
| Comm-loss -> STOP (3.0 s laptop, 3000 ms firmware) | **PASS** | **SIMULATED** |
| Firmware watchdog fires strictly after 3000 ms; newline does not refresh it; `currentCmd='S'` | **PASS** | **SIMULATED** |
| Flood of invalid bytes -> STOP, flood then silence -> STOP | **PASS** | **SIMULATED** |
| Manual motion auto-stop (R5), measured with a real clock | **PASS** - stop observed within [0.9 x timeout, timeout + 1.0 s]; cancel path emits exactly one STOP | PASS |
| Obstacle gate blocks F/B, allows pivot (firmware + Python) | **PASS** | **SIMULATED** |
| Startup state = STOP, drivers released before first command | **PASS** | **SIMULATED** |
| **Ultrasonic failure -> fail safe** | **FAIL (CRITICAL)** - `dead sensor allowed motion: SafetyVerdict(allowed=True, command='F', reason='SAFE')`; firmware final state `motors=F` | FAIL |
| **Stale/out-of-range telemetry -> fail safe** | **FAIL (CRITICAL)** - `stale/garbage distance -> SafetyVerdict(allowed=True, command='F', reason='SAFE')` | FAIL |
| `SafetyManager` rejects non-protocol commands | **FAIL (MEDIUM)** - `SafetyManager passed through 'FORWARD' -> 'FORWARD'` | FAIL |
| Link heartbeat only from recognised telemetry | **FAIL (MEDIUM)** - `unrecognised STATUS payload counted as a live heartbeat` | FAIL |
| AI confidence gate honoured in every distance zone | **FAIL (MEDIUM)** - `low-confidence forward allowed at 20.0 cm: CAUTION_SLOW_ZONE` | FAIL |
| Live obstacle demo, loss-of-signal demo, physical cutoff timing (<50 ms claim) | not executable | **HARDWARE REQUIRED / NOT TESTED** |

## 9. Computer vision results

| Check | Result |
|---|---|
| Position estimator (LEFT/CENTER/RIGHT, boundaries, symmetry) | **PASS** - 4 randomized properties x 2000-4000 samples, fixed seeds |
| Frame enhancement (CLAHE/sharpen/denoise) unit behaviour | **PASS** |
| `enhance_for_inference` latency, 640x480 | median 34.4 ms, p95 56.6 ms (**measured**) |
| HF detector loads offline from `models/detr-resnet-50` | **PASS** - load 19.12 s, `ready=True`, `err=None` |
| HF inference on a synthetic frame | runs, 0 detections (expected for noise) |
| Detection accuracy / precision / recall on real images | **NOT TESTED** - the repository contains no test images or recorded video, and no camera exists |
| Frozen-frame and stream-loss handling on a real ESP32 | **HARDWARE REQUIRED / NOT TESTED** |
| Wrong-object selection (green bottle vs background) | **NOT TESTED** - needs real imagery |

## 10. Control results

| Check | Result |
|---|---|
| Decision engine unit tests (left/right/center, cooldown, deadband) | **PASS** |
| Randomized engine inputs -> command always in {F,B,L,R,S} (3000 cases) | **PASS** |
| Lost target never leaves the engine translating | **PASS in observe mode** only because `main.py` bypasses the engine (`if target is None: cmd = "S"`) |
| Stop decision issued immediately (docs/19: APPROACHING -> STOPPED with `'S'`) | **FAIL (MEDIUM)** - `engine re-asserted a motion command immediately after deciding to stop in 400 of 400 cases` (anti-oscillation cooldown of 0.2 s holds the previous `F`) |
| Search rotation (state SEARCHING) | **FAIL (HIGH)** - never rotates; `LOW_CONFIDENCE` gate blocks self-initiated rotation, 0/120 motion commands |
| scan360 rotation + approach | **FAIL (HIGH)** - 0/120 motion commands; scan branch never starts, `engine.decide` never called |
| `max_search_rotations` reachable within `search_timeout_s` | **FAIL (LOW)** - 30 s / 20 s = 1 rotation, cap is 2 |
| Proportional/Kp response simulation | **PASS - SIMULATED** (figure produced by `tools/simulate_control.py`) |
| Real closed-loop visual servoing on the ground | **HARDWARE REQUIRED / NOT TESTED** |
| PID / encoder / IMU control | **NOT APPLICABLE** - no encoder or IMU code exists in `software/`, `arduino/`, `esp32/` (1 comment-only match) |

## 11. Performance measurements

Measured on this host (no hardware in the loop):

| Metric | Measured | Documented claim | Verdict |
|---|---|---|---|
| DETR-ResNet-50 CPU inference | median **4135 ms**, min 3832, max 4752 (n=12) | 5.14 s / 0.2 FPS (docs/11, `logs/benchmark.json`, README) | consistent - **PASS as a measurement**, see H4 |
| HF model load (local weights) | **19.12 s** | ~27 s (README) | consistent - PASS |
| Vision preprocessing | median 34.4 ms/frame | not stated | INFO |
| Control step (mock) | median **1.3 ms**, p95 3.7 ms, max 23.9 ms (n=200) | not stated | PASS |
| Inter-command gap | median 1.3 ms, max **23.6 ms** | watchdog 3000 ms | PASS (margin >100x) |
| Firmware watchdog trip | stops at **+3001 ms**, not +3000 | ">3000 ms" | PASS **SIMULATED** |
| Manual guard auto-stop | within timeout (+0/-10%) | `movement_timeout_s` 1.0 s | PASS |
| UNO flash / RAM | 4448 B (13%) / 258 B (12%) | - | PASS with headroom |
| ESP32 flash / RAM | 1026129 B (32%) / 57224 B (17%) | - | PASS with headroom |
| Docs validator | 0 errors, 0 warnings, 59 markdown files, 19 figures, 36 required docs | "DOCUMENTATION INTEGRITY VERIFIED" | PASS (tool self-check only) |

**H4 (HIGH, derived from the two measurements above):** with `inference_interval = 2` the loop produces a fresh detection roughly every 4.1 s, while `target_lock_duration_s` is 1.0 s. Consequence: the target is reported lost for ~3.1 s of every ~4.1 s cycle, so observe mode emits `S` most of the time - the visual servoing loop cannot close with the shipped primary backend. The repository does document the 0.2 FPS bottleneck, but no compensation (prediction, held input, reduced-resolution path) exists in the control loop. Label: **MEASURED (host) / HARDWARE REQUIRED for on-robot confirmation**.

## 12. Hardware risks

| Risk | Status |
|---|---|
| Motor rail voltage (claimed 2S 18650 = 7.4 V) | **HARDWARE REQUIRED / NOT TESTED** - gate trigger |
| LM2596 5.0 V logic rail, decoupling, brownout | **HARDWARE REQUIRED / NOT TESTED** - gate trigger |
| L298N current capability vs stall current of two gear motors | **HARDWARE REQUIRED / NOT TESTED** - gate trigger (docs mandate per-motor 0.1 uF suppression; unverifiable) |
| "Electrically isolated, level-shifted UART link" (docs/02, docs 2.4) | **FAIL as a claim** - no isolation/level-shifting component exists in code or wiring docs for the actual laptop<->Arduino USB link (finding M9) |
| Pin map consistency (docs vs firmware vs ESP32) | **PASS** for `docs/PINOUT.md` <-> UNO constants (D5/D6/D7/D8/D9/D10/Trig D11/Echo D12, all unique, all 0-13) - **NOT TESTED** physically |
| Motor noise resetting the Arduino | **NOT TESTED** (needs hardware; no reset-suppression analysis exists in repo) |
| Battery voltage causing unexpected behaviour | **FAIL (MEDIUM)** - `BATTERY:` telemetry is parsed and then never used; no low-battery guard exists (finding M10) |
| Encoder overflow / IMU drift | **NOT APPLICABLE** - not in the build |
| Degrees/radians, cm/m, left/right unit mixing | **PASS** - units are centimetres and normalized [0,1] x everywhere; no radian/degree API exists; no mixed-unit test failure found |
| Wires/connector uncertainty, HC-SR04 mounting height | **HARDWARE REQUIRED / NOT TESTED** |

## 13. Critical failures

**C1 - CRITICAL: an ultrasonic failure or a stale/out-of-range reading lets the rover drive blind.**

Evidence chain (all reproduced by tests in this report):

1. Firmware: `bool blocked = (dist > 0 && dist < EMERGENCY_STOP_CM && ...)`. A dead sensor yields `DIST:-1`, so `dist > 0` is false -> `blocked` stays false -> `F` is applied. Host harness: `sensor_dead_from_boot` final state `cmd=F motors=F tx=DIST:-1`; `sensor_dead` final state `motors=F` (both tests FAIL as expected).
2. Python parser: `if 0 <= v <= 500` silently discards `DIST:-1`, so `telemetry.distance_cm` keeps the **last good** value (e.g. 150.0/200.0).
3. Link health: `STATUS:OK` keeps arriving -> `is_healthy()` stays true.
4. `SafetyManager.check('F', <stale 150.0>, healthy=True, ...)` -> `SafetyVerdict(allowed=True, command='F', reason='SAFE')`.
5. Result: **both** independent safety layers pass while the physical sensor is dead.
   - `test_stale_distance_from_dead_sensor_does_not_allow_forward` FAIL: `dead sensor allowed motion: SafetyVerdict(allowed=True, command='F', reason='SAFE')`
   - `test_out_of_range_telemetry_does_not_allow_forward` FAIL: same verdict for out-of-range telemetry
   - `test_sensor_failure_must_fail_safe_mid_run` / `test_sensor_dead_from_boot_must_fail_safe_in_firmware` FAIL

Impact: uncommanded forward motion into an obstacle with no stop. This alone triggers the release gate.

**HIGH failures**

- **H1** `search` mode never rotates: `assert []: search mode never issued a rotation; last reasons=['LOW_CONFIDENCE']` (0/120 motion commands in a 120-step run with the target absent). The LOW_CONFIDENCE gate blocks self-initiated `R`.
- **H2** `scan360` mode never scans and never approaches: `scan360 mode never issued a rotation command` and `scan360 ignored a centred visible target` (0/120 motion commands).
- **H3** Firmware actuates on any single byte - no newline framing, contradicting "newline-terminated" (docs/18) and "malformed input must be rejected safely" (section 8). `malformed_word` produced `iter=2 cmd=R motors=R` and `iter=5 cmd=R motors=R`; corrupt input ending in `F` leaves the motors driving until the 3000 ms watchdog (`FINAL cmd=S` assertion FAIL).
- **H4** AI-in-the-loop control cannot close: measured 4135 ms inference vs 1.0 s target lock and 0.2 s decision cooldown (see section 11).

## 14. Recommended fixes (priority order)

1. **C1:** treat "no fresh in-range reading within N ms" as link-unsafe. Add a `last_valid_distance_time`; if `now - last_valid > ~0.5 s`, force `S` and stop refreshing health. In firmware, make `dist <= 0` a fail-safe condition (`blocked = true` / `currentCmd = 'S'` for `dist <= 0`), not a pass-through.
2. **H3:** require `Serial.readBytesUntil('\n', ...)` framing in the firmware; reject anything that is not exactly one of `F B L R S`; clear `currentCmd` on any framing error.
3. **H1/H2:** permit engine-initiated rotation when `target_present` is false and confidence is irrelevant (confidence gate applies to forward motion only); fix `scan360` so it calls `engine.decide` once the scan completes.
4. **M1:** run the autonomous commands through `SafetyManager` *before* `ObstacleAvoidance` rewrites them, or have `ObstacleAvoidance` set the latch, so R4 hysteresis is actually exercised.
5. **M2/M3:** validate `proposed` against `{'F','B','L','R','S'}` at the top of `SafetyManager.check` (reject -> `S`); accept `STATUS:` only for the exact values `OK|STOP|ERROR`.
6. **M4:** bypass `_can_switch` when the new command is `S` (STOP must never be delayed by the anti-oscillation cooldown).
7. **M5:** move the AI-confidence gate above the slow-zone return.
8. **M6/M7/M8:** wire `config/thresholds.yaml` and the 14 unread keys into the runtime (or delete them); pass `rover.width_cm` / `safety_margin_cm` into `GapAssessment`; apply `camera.enhance_*` in the control loop.
9. **M9:** correct docs/18 (host is the laptop), docs/02 (ESP32 has no CLAHE/FSM role; no isolation/level shifting), docs/05 (<50 ms vs >3000 ms), docs/19 (AVOIDING/EMERGENCY_STOP unreachable), and the stale test counts.
10. **M10:** act on `BATTERY:` (warn/stop below a threshold) or remove the claim.
11. **H4:** use a cheaper/faster path for control (color-blob or nano model), lower `inference_interval`, or add target prediction between inferences.

## 15. Regression status

The engagement rules allow writing only `TEST_REPORT.md`, so the regression record required by section 24 (`REGRESSION_REPORT.md`) is folded in here.

| ID | Regression | Status | Evidence |
|---|---|---|---|
| R1 | Both run modes work (`python -m software.main` and `python software/main.py`) | **PASS** | `test_python_m_software_main_help_works`, `test_python_software_main_help_works` |
| R2 | Invalid serial command forces STOP in firmware | **PASS (static)** / **FAIL (dynamic, new)** | contract test asserts `stopMotors()` + `currentCmd='S'` in the invalid branch; host harness shows single invalid char stops, but multi-char malformed input actuates (H3) |
| R3 | `config/thresholds.yaml` <-> firmware contract | **PASS** | `test_emergency_distance_firmware_matches_yaml`, watchdog/obstacle constants, new pin-map property |
| R4 | Emergency latch auto-release at >= `slow_cm` | **PASS in unit** / **FAIL in the autonomous path** | `test_safety.py` passes; `test_emergency_latch_engages_through_the_auto_chain` FAIL |
| R5 | Manual motion guard stops after timeout | **PASS** | 6 manual-guard tests + 3 real-timing red-team tests |
| R6 | ESP32 Wi-Fi reconnect | **NOT TESTED** | reconnect logic exists in `camera_stream.ino`; no unit/integration test covers it (no ESP32 available) |
| baseline suite | 58 pre-existing tests | **PASS 58/58** | re-run after all additions; no pre-existing test regressed |

## 16. Hardware readiness (section 25 checklist)

| Item | Status |
|---|---|
| Firmware compiles | **PASS** |
| Startup = STOP | **PASS (SIMULATED)** |
| Watchdog tested | **PASS (SIMULATED)** - 3001 ms trip, flood/silence, newline non-refresh |
| Safety tested | **PARTIAL** - units PASS, sensor-failure path **FAIL (C1)** |
| Pinout verified | **PASS vs docs (code), HARDWARE REQUIRED (physical)** |
| Voltage verified | **HARDWARE REQUIRED / NOT TESTED** |
| Motor driver verified | **HARDWARE REQUIRED / NOT TESTED** |
| Serial tested | **PASS (SIMULATED)** - parser/fuzz/health; **HARDWARE REQUIRED** for a real COM port |
| Wheels-off-ground bench test | **HARDWARE REQUIRED / NOT TESTED** |
| Low-speed test | **HARDWARE REQUIRED / NOT TESTED** |
| Full physical test | **HARDWARE REQUIRED / NOT TESTED** |

## 17. Final MVP status

> **SUPERSEDED (baseline snapshot).** The figures below are the red-team
> baseline: **137/162**. The suite now stands at **288 passed / 0 failed**
> (`README.md`, `docs/testing.md`). `realtime AI servoing (H4)` now **passes**
> at ≤~60 % host CPU load and is load-sensitive by construction — see
> `docs/testing.md` and `REGRESSION_REPORT.md` §9.

- **Works offline today:** build, lint, 137/162 tests, mock runs of all four modes, static firmware contracts, safety units, docs tooling.
- **Works only in simulation:** watchdog, obstacle gate, startup/shutdown fail-safe, manual auto-stop (host-compiled firmware + mocks).
- **Does not work:** sensor-failure fail-safe (C1), `search` mode (H1), `scan360` mode (H2), framed/malformed input rejection (H3), autonomous-path emergency latch (R4/M1), realtime AI servoing (H4).
- **Unknown until powered:** everything in section 12.

## 18. Advanced-feature status

| Feature | Status |
|---|---|
| DETR HF backend (offline load + inference) | **PASS (measured)**, not real-time (H4) |
| YOLO backends (`yolo11n.pt`, `yolo11s.pt`, `yolov8s.pt`, `yolov8m-worldv2.pt` present) | **NOT TESTED** - ultralytics not exercised by the suite |
| CLIP weights (`weights/clip/ViT-B-32.pt`, 354 MB) | **FAIL (LOW)** - never referenced by any code (finding L4) |
| ESP32 on-board preprocessing (CLAHE/FSM, docs/02) | **FAIL (claim)** - not implemented; enhancement runs on the laptop and is not applied in the control loop (M8/M9) |
| Dashboard (`--dashboard`) | **NOT TESTED** (network); code path exists |
| Calibration script, benchmark script, BOM/report generators | files exist; generators were **NOT RUN** because they would rewrite repository artifacts (report-only engagement) |
| `search` / `scan360` autonomous behaviours | **FAIL (H1/H2)** |
| Self-balancing / encoders / IMU / TinyML on ESP32 | **NOT IMPLEMENTED** (documented as future work) |

---

## 27. FINAL SCORE

```
BUILD:
PASS

UNIT TESTS:
97/110

INTEGRATION TESTS:
40/52

SAFETY TESTS:
68/80

SIMULATION TESTS:
40/52

WOKWI TESTS:
NOT SIMULATABLE (0/0)   [superseded 2026-09-27 -> PASS (SIMULATED): lint
 clean, 3 headless runs exit 0 - plain run, scenarios/safety.yaml and
 scenarios/obstacle_gate.yaml all completed (boot STOP, protocol rejection,
 3 s watchdog, 10 cm obstacle gate). Physical rover still HARDWARE REQUIRED
 - see section 6 and REGRESSION_REPORT.md section 10]

HARDWARE TESTS:
0/13   (all NOT TESTED / HARDWARE REQUIRED)

CRITICAL FAILURES:
1      C1 ultrasonic failure or stale/out-of-range reading bypasses both safety layers

HIGH FAILURES:
4      H1 search never rotates; H2 scan360 never scans/approaches;
       H3 firmware actuates on unframed/corrupt input; H4 AI loop cannot close (4.1 s/frame)

MEDIUM FAILURES:
10     M1 autonomous latch never engages; M2 non-protocol command passes SafetyManager;
       M3 any STATUS refreshes link health; M4 STOP delayed up to 0.2 s by cooldown;
       M5 confidence gate bypassed in the slow zone; M6 thresholds.yaml + geometry keys unused;
       M7 sensor_invalid_limit config ignored; M8 camera.enhance_* unused by control loop;
       M9 documentation contradicts implementation; M10 battery telemetry parsed but unused

LOW FAILURES:
11     L1 stale test counts (README 58 vs docs/testing.md 35); L2 8 byte-identical doc pairs;
       L3 .env.example unread; L4 unused deps (timm/networkx/qrcode) + 354 MB unused CLIP weights;
       L5 max_search_rotations unreachable; L6 dead engine API (emergency/to_search/STATES);
       L7 12 unused config keys; L8 unbounded logs/events.csv growth (append per step);
       L9 guard bookkeeping may emit an extra STOP (fails safe); L10 prompt/meta files at repo root;
       L11 config path is CWD-relative (only runs from the repo root)
```

## 28. RELEASE GATE

| Gate condition | Triggered? |
|---|---|
| Motor safety is broken | **YES** - C1 (and M2) |
| Watchdog is broken | No - passes in simulation (3001 ms trip, flood/silence) |
| Obstacle stop is broken | **YES** - the firmware gate is defeated by `dist <= 0` (C1) |
| Startup is unsafe | No - startup STOP verified in simulation |
| Pinout is uncertain | Code/docs agree; physical wiring unverified -> uncertain |
| Motor voltage is uncertain | **YES** - never measured |
| Motor driver current capability is uncertain | **YES** - never measured |

### **Mark: NOT READY**

Do not connect motors for autonomous testing until C1 is fixed and re-tested, and until voltage/current are measured on the bench. H1/H2/H3 should be fixed before any demo that relies on `search`/`scan360`.

---

## Appendix A - Findings register (section 2)

| ID | Sev | Finding | Location | Evidence test |
|---|---|---|---|---|
| C1 | CRITICAL | Dead/out-of-range/stale ultrasonic -> both safety layers return GO | `rover_controller.ino` (`blocked`), `arduino_serial.py` (`0<=v<=500`), `safety_manager.py` | `test_stale_distance_from_dead_sensor_does_not_allow_forward`, `test_out_of_range_telemetry_does_not_allow_forward`, `test_sensor_failure_must_fail_safe_mid_run`, `test_sensor_dead_from_boot_must_fail_safe_in_firmware` |
| H1 | HIGH | `search` mode never rotates (LOW_CONFIDENCE blocks self-initiated rotation) | `main.py:166-172`, `safety_manager.py:99` | `test_search_mode_must_rotate_until_target_found` |
| H2 | HIGH | `scan360` never scans, never approaches | `main.py:173-177` | `test_scan360_mode_must_rotate`, `test_scan360_mode_approaches_when_target_visible` |
| H3 | HIGH | No input framing: single byte actuates; corrupt tail keeps driving up to 3000 ms | `rover_controller.ino` `Serial.read()` | `test_malformed_command_is_rejected_without_actuating_motors`, `test_corrupt_command_ending_in_motion_byte_does_not_keep_driving` |
| H4 | HIGH | AI inference 4135 ms/frame vs 1.0 s lock -> loop cannot close | `main.py:153-159`, `config.yaml` | measured (section 11) |
| M1 | MEDIUM | Emergency latch unreachable in the autonomous path | `main.py:187` (`avoid.override` first) | `test_emergency_latch_engages_through_the_auto_chain` |
| M2 | MEDIUM | Non-protocol string passes SafetyManager, then `send()` raises | `safety_manager.py:50` | `test_safety_manager_must_reject_unknown_command_alphabet` |
| M3 | MEDIUM | Any `STATUS:<garbage>` refreshes link health | `arduino_serial.py:129-132` | `test_only_recognised_status_values_may_refresh_link_health` |
| M4 | MEDIUM | STOP delayed up to `decision_cooldown_s` (0.2 s) by anti-oscillation hold | `decision_engine.py:47-53,76` | `test_engine_stop_decision_is_not_delayed_by_the_oscillation_hold` |
| M5 | MEDIUM | Confidence gate evaluated after the slow-zone return | `safety_manager.py:96-100` | `test_ai_confidence_gate_is_applied_in_every_distance_zone` |
| M6 | MEDIUM | `config/thresholds.yaml` unread; `rover.width_cm`/`safety_margin_cm`/`length_cm` never passed to `GapAssessment` (hardcoded 18.0/8.0) | `config_loader.py`, `main.py`, `gap_assessment.py:20-25` | `test_thresholds_yaml_is_consumed_at_runtime`, `test_every_config_key_is_referenced_by_the_software` |
| M7 | MEDIUM | `safety.sensor_invalid_limit` ignored (hardcoded 5); `_invalid_count` trip unreachable | `config_loader`/`safety_manager.py:80` | `test_every_config_key_is_referenced_by_the_software` |
| M8 | MEDIUM | `camera.enhance_*` not applied by the control loop | `main.py` (no enhance call) | `test_camera_enhance_settings_are_used_by_the_control_loop` |
| M9 | MEDIUM | Docs contradict implementation (18: ESP32<->Arduino; 02: ESP32 CLAHE/FSM + isolation; 05: <50 ms vs >3000 ms; 19: unreachable states) | `docs/18`, `docs/02`, `docs/05`, `docs/19` | `test_docs_communication_protocol_names_the_correct_host`, `test_docs_state_machine_states_are_reachable_in_code`, `test_decision_engine_emergency_path_is_wired_up` |
| M10 | MEDIUM | `BATTERY:` telemetry parsed, never used; no low-battery guard | `arduino_serial.py:133-134` | code inspection |
| L1-L11 | LOW | see section 27 | various | see section 4 failure list |
| I1-I5 | INFO | shared-interpreter pip conflicts; no test imagery; no encoder/IMU in build; Wi-Fi credentials are placeholders (good); early test runs appended to gitignored `logs/events.csv` before the redirect was added (later runs verified delta 0) | - | - |

## Appendix B - How to reproduce

```powershell
$py = "C:\Users\bezal\AppData\Local\Programs\Python\Python312\python.exe"
& $py -m pytest tests -q          # 137 passed, 25 failed (25 = defect reports)
& $py -m ruff check software tests  # All checks passed
& "C:\Users\bezal\tools\bin\arduino-cli.exe" compile --fqbn arduino:avr:uno arduino\rover_controller
& "C:\Users\bezal\tools\bin\arduino-cli.exe" compile --fqbn esp32:esp32:esp32cam esp32\camera_stream
& $py tools\simulate_control.py   # SIMULATED control figures
& $py tools\validate_docs.py      # documentation validator
& $py software\main.py --mock --mode observe   # also search | scan360 | manual
```

Deliberately not executed (report-only rule: only `TEST_REPORT.md` may be written):
`tools/generate_*.py`, `scripts/benchmark.py`, `scripts/download_model.py` (would rewrite repository artifacts).
