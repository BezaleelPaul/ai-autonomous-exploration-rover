# Phase 0 — Repository Compatibility Report

**Date:** 2026-09-25 | **Status:** AWAITING VALIDATION | **Author:** Lead Integration Engineer (CLI agent)

## 1. What was actually supplied

There are **no separate third-party repositories** in this workspace (no clones, no
submodules, no `.git` at all). The workspace is a **single monorepo** ("MWE PROJECT").
Third-party code enters through three other channels:

1. **pip packages** (opencv, torch, transformers, ultralytics, flask, ...)
2. **Model weights** (DETR, YOLO/YOLO-World, CLIP)
3. **Possibly-derived firmware sketches** (ESP32-CAM streamer resembles public
   Espressif/tutorial examples — attribution not recorded, see LICENSE_REPORT)

Compatibility analysis therefore applies to the **in-repo components** and the
**specification documents**, not to merged external repos.

## 2. Component inventory

| Component | Path | Language | Target | Status | Reuse decision |
|---|---|---|---|---|---|
| Arduino rover firmware | `arduino/rover_controller/rover_controller.ino` | C++ | UNO | Works (mock-verified; hardware untested) | **KEEP as-is** (Phase 1 base) |
| ESP32-CAM streamer | `esp32/camera_stream/camera_stream.ino` | C++ | AI-Thinker ESP32-CAM | Works (VGA MJPEG :81/stream) | **KEEP**, add Wi-Fi reconnect later |
| Laptop orchestrator | `software/` (14 modules) | Python 3.12 | Laptop | Tests pass (39/39) | **KEEP**, fix P0 bugs below |
| Detector backends | `software/ai/detector.py` | Python | Laptop | mock/hf/yolo/color all load | **KEEP** interface; pick backend by benchmark |
| Safety manager | `software/safety/safety_manager.py` | Python | Laptop | 6-priority gate, latching | **KEEP** (Tier 2 of safety) |
| Doc/report generator | `tools/` (10 scripts) | Python | Laptop | Generates docs/reports | **KEEP**, out of runtime path |
| Tests | `tests/` (9 files) | Python | Laptop | **39 passed** (measured today) | **KEEP**, extend per TEST_PLAN |

## 3. Specification conflict (must be resolved before code changes)

Two master documents describe **different architectures**:

| Source | Architecture | Verdict |
|---|---|---|
| **MASTER PROMPT (this engagement)** | ESP32-CAM → Wi-Fi → **Laptop (AI)** → USB Serial → Arduino (safety) | **AUTHORITATIVE** — matches the existing code 1:1 |
| `GEMINI_MASTER_DOCUMENTATION_PROMPT.md` | **ESP32 does all AI**; laptop is dev/telemetry only | **INCOMPATIBLE** with current code and with hardware reality (DETR = ~1 GB RAM, measured 0.2 FPS on laptop CPU — impossible on ESP32) |

**Decision:** architecture = laptop-in-the-loop (per MASTER PROMPT §2). The Gemini
document is retained **only** as a documentation-generation input. Its requirement
"AI must run on ESP32" is deferred to P3/future work (would need FOMO/TFLM, see
`docs/FINAL_AUDIT.md`).

Related doc/code mismatches to reconcile during Phase 1-3 (docs claim what code does not do):

- `docs/hardware/PIN_CONFIGURATION.md` + `CIRCUIT_CONNECTIONS.md` describe an
  **ESP32↔Arduino UART link with level shifter** — no firmware code and no MVP
  wiring uses it. Mark `[NOT IMPLEMENTED]`.
- `docs/22_PIN_CONFIGURATION.md` claims D13 = heartbeat LED — firmware never drives D13.
- `docs/` has **exact duplicates** (`docs/21_...` == `docs/hardware/CIRCUIT_...`,
  `docs/22_...` == `docs/hardware/PIN_...`, etc.) — dedupe later, not blocking.

## 4. Interface compatibility (verified by reading code + running it)

| Interface | Producer | Consumer | Match? | Evidence |
|---|---|---|---|---|
| Serial chars `F/B/L/R/S` + `\n` | `arduino_serial.py:107` | `rover_controller.ino:78` | **YES** | both validate same set |
| Telemetry `DIST:` / `STATUS:` | `rover_controller.ino:107-111` | `arduino_serial.py:124-135` | **YES** | parser tolerant of garbage |
| Baud 9600 | `config.yaml:69`, `.env.example` | `rover_controller.ino:35` | **YES** | 3 sources agree |
| Emergency distance 15 cm | `config.yaml:60` | `rover_controller.ino:25` | **YES** (manual sync — see risk R3) |
| Comm timeout 3 s | `config.yaml:85` | `rover_controller.ino:26` | **YES** (manual sync) |
| MJPEG URL `:81/stream` | `camera_stream.ino:52` | `config.yaml:3` | **YES** (IP must match site) |
| Frame size 640×480 | `camera_stream.ino:66` | `config.yaml:4-5` | **YES** | |

## 5. Risks

| ID | Risk | Severity | Phase |
|---|---|---|---|
| R1 | `python software/main.py ...` (the **documented** run command) crashes: `software/logging/` shadows stdlib `logging` → circular import. `python -m software.main` works. | **P0** | 1 |
| R2 | Invalid serial char → Arduino replies `STATUS:ERROR` but **keeps executing the last motion command**. MASTER PROMPT §2 requires invalid → STOP. | **P0** | 2 |
| R3 | Safety constants (15 cm, 3 s) duplicated between YAML and firmware with no automated sync check. | P1 | 2 |
| R4 | `SafetyManager.emergency_latch` is never reset by `main.py` — one <10.5 cm event permanently blocks motion until process restart; no operator reset path. | P1 | 2 |
| R5 | Manual mode sends a command only on keypress → Arduino keeps driving up to 3 s after the last keypress (watchdog gap in UX). | P1 | 1 |
| R6 | ESP32 firmware connects Wi-Fi once at boot; no reconnect. Laptop side has reconnect + frozen-frame detection (good). | P1 | 3 |
| R7 | README claims "35 tests passed"; actual = **39 passed** (measured 2026-09-25). Stale docs. | P2 | 1 |
| R8 | `logs/dashboard.err.log` is 7.9 MB junk; `logs/` not committed anyway (`.gitignore`) — delete locally. | P3 | 1 |

## 6. Verdict

**COMPATIBLE — single coherent codebase, no repository merging required.**
No external repo needs to be integrated. Work = fix 2 P0 bugs, validate on
hardware, benchmark the detector, and document reality.

**Next:** DEPENDENCY_REPORT, PIN_CONFLICT_REPORT, LICENSE_REPORT, HARDWARE_COMPATIBILITY,
INTEGRATION_PLAN → then **WAIT for validation** before Phase 1.
