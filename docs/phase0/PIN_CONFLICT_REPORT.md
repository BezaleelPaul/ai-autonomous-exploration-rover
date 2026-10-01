# Phase 0 — Pin Conflict Report

**Date:** 2026-09-25 | **Status:** VALIDATED (Phase 1) | **Authoritative source going forward:**
`docs/PINOUT.md` (created in Phase 1 from §1 below). The two firmware
files remain the raw source: `rover_controller.ino:13-22`, `camera_stream.ino:12-27`.

## 1. Current allocation (extracted from firmware — not from docs)

### Arduino UNO

| Pin | Use | Source | Conflicts |
|---|---|---|---|
| D0 (RX) | USB serial from laptop | `rover_controller.ino:35` | none — **do not reuse** |
| D1 (TX) | USB serial to laptop | `rover_controller.ino:35` | none — **do not reuse** |
| D2 | **encoder L** (ext-interrupt, `encISR_L`) | `rover_controller.ino` (Phase 9+) | assigned — do not reuse |
| D3 | **encoder R** (ext-interrupt, `encISR_R`) | `rover_controller.ino` (Phase 9+) | assigned — do not reuse |
| D4 | **FREE** | — | free for status LED / servo signal |
| D5 | L298N ENA (PWM, Timer0) | `:13` | — |
| D6 | L298N IN1 | `:14` | — |
| D7 | L298N IN2 | `:15` | — |
| D8 | L298N IN3 | `:16` | — |
| D9 | L298N IN4 | `:17` | **collides with `Servo` library (Timer1)** — see §3 |
| D10 | L298N ENB (PWM, Timer1) | `:18` | **collides with `Servo` library (Timer1)** — see §3 |
| D11 | HC-SR04 TRIG | `:21` | — |
| D12 | HC-SR04 ECHO | `:22` | — |
| D13 | free (docs claim LED heartbeat — code does **not**) | — | doc/code mismatch |
| A4/A5 | **FREE** (I2C) | — | reserved for MPU6050 |
| A0-A3 | **FREE** | — | spare analog |

### ESP32-CAM (AI-Thinker)

Camera DVP consumes GPIO 0,5,18,19,21,22,23,25,26,27,32,34,35,36,39 (`camera_stream.ino:12-27`).
Free/claimed elsewhere:

| GPIO | Status |
|---|---|
| GPIO 1 (TX0) / 3 (RX0) | **USED by USB flashing/serial** — docs propose UART-to-Arduino here; **do not wire until flashing workflow is solved**. MVP does not use them. |
| GPIO 4 | onboard flash LED — free for use |
| GPIO 12 | **strapping pin (MTDI)** — boot-strap sensitivity; avoid for peripherals |
| GPIO 13, 14, 15, 16 | free-ish (16 tied to PSRAM on some boards) — usable for servo/extra UART |
| GPIO 33 | docs claim red status LED — code does not drive it |

**ESP32 verdict: no pin conflicts in current firmware.** The only conflict is a
*documentation* conflict (docs claim GPIO1/3 UART link that no code implements).

## 2. Forward reservations (authoritative — do not reassign)

- **D2, D3** → wheel encoders (only two true external-interrupt pins on UNO; MUST stay free).
- **A4, A5** → MPU6050 I2C.
- **D4** → first choice for status LED or future servo signal.
- **D0, D1** → laptop USB serial only (MVP).

## 3. Identified conflicts and resolutions

| ID | Conflict | Severity | Resolution |
|---|---|---|---|
| PC-1 | `Servo` library (SG90) uses **Timer1**, killing `analogWrite` on **D9/D10** → ENB (D10) loses PWM → right motor runs full/zero speed | **HIGH if servo added** | If SG90 becomes required: move servo signal to **D4** does NOT help (conflict is timer-based, not pin-based). Options: (a) drop `Servo` for `ESP32-driven servo` on GPIO 13/14, (b) use Timer1-free `ServoTimer2`-style lib on D3? not UNO-friendly, (c) accept losing D9/D10 PWM and drive ENB via software PWM. **Recommended: (a) — keep UNO timers untouched; servo belongs to the ESP32 side.** Defer: servo is P3. |
| PC-2 | Docs assign D2/D3 "optional encoder" but also D3 as PWM — encoders need interrupt, not PWM; no real conflict, just ambiguity | LOW | §2 reservation is authoritative. |
| PC-3 | Docs assign D0/D1 to a level-shifter UART link **and** they are the laptop USB serial path | **HIGH (docs)** | MVP: D0/D1 = laptop only. If edge-UART is ever adopted, laptop serial must move (e.g., SoftwareSerial on D2/D3 — which would then steal encoder pins → that is why MVP keeps laptop-in-the-loop). |
| PC-4 | Docs claim D13 LED, GPIO33 LED — code drives neither | LOW | Either implement heartbeat LED (nice, cheap) or correct docs. |
| PC-5 | ESP32 GPIO12 strapping: if a peripheral pulls it wrong at boot, flash-voltage strapping misconfigures | MEDIUM | Do not attach peripherals to GPIO12. |
| PC-6 | L298N ENA/ENB onboard jumpers left on → PWM ignored (motors uncontrolled at full speed) | **HIGH (safety)** | Build checklist item: jumpers removed, ENA/ENB wired to D5/D10. Test 04 covers it. |

## 4. Verdict

**No active pin conflict in the code as it exists today.** The real hazards are
(PC-6) a physical jumper that can defeat speed control, and (PC-1/PC-3) future
additions. One authoritative pin map (`docs/PINOUT.md`) will be created in Phase 1
from §1/§2 and referenced by all other docs.
