# Phase 0 — Hardware Compatibility Report

**Date:** 2026-09-25 | **Status:** AWAITING VALIDATION | **Rule:** never invent specs — see §3

## 1. Target hardware vs what the code assumes

| Component | Required by code | BOM says | Compatible? |
|---|---|---|---|
| Arduino UNO (ATmega328P) | 6 PWM/digital outs + 2 ultrasonic pins + HW serial (D0/D1) | Present, "Existing" | **YES** |
| ESP32-CAM AI-Thinker | OV2640 DVP pin map, Wi-Fi MJPEG server | Present, "Existing" | **YES** |
| L298N driver | ENA=D5, IN1-4=D6-D9, ENB=D10, ENA/ENB jumpers must be **removed** | Present, "Existing" | **YES** — physical jumper state is `[TO VERIFY]` |
| 2× TT DC motors + 65 mm wheels | open-loop PWM only, no encoders yet | Present (gear ratio `[TO VERIFY]`) | **YES** for Phase 1-2 |
| HC-SR04 | TRIG=D11, ECHO=D12, 5V | Present | **YES** |
| Battery + buck | **not read by code** | 2S 18650 pack + LM2596 = **Need to Buy** | **BLOCKED** — no rover motion without them |
| Level shifter (3.3↔5V) | only needed for ESP32↔Arduino UART, which **no code implements** | Need to Buy, "CRITICAL" | **NOT REQUIRED for MVP architecture** (laptop USB serial does the job). Buy only if edge-UART link is later adopted. |
| Wheel encoders | none exist in firmware | not in BOM | P2 — see §4 |
| MPU6050 | none exist in firmware | not in BOM | P2 — see §4 |
| SG90 servo | none exist in firmware | Optional | P3 — pin conflict if added (see PIN_CONFLICT_REPORT) |

**MVP hardware verdict:** everything needed for Phases 1-8 is either present or a
low-cost purchase (battery + buck). Nothing in the MVP path is INCOMPATIBLE.

## 2. Power system compatibility (HARDWARE RULE: do not invent numbers)

| Parameter | Value | Status |
|---|---|---|
| Motor voltage / stall current | **UNKNOWN** | TO VERIFY — required before claiming driver margin |
| L298N continuous rating | 2 A/channel (datasheet), ~2 V BJT drop | VERIFIED DATASHEET (docs/hardware/HARDWARE_VERIFICATION.md) |
| Battery chemistry / capacity / max current | **UNKNOWN** (BOM: 2S 18650 7.4 V 2600 mAh, "PRICE TO VERIFY", "confirm physically") | TO VERIFY |
| Buck converter output current | **UNKNOWN** (BOM: 3 A max, to buy) | TO VERIFY |
| Motor vs logic rail separation | design requires it; not yet built | DESIGN DECISION — must be physically confirmed |
| Common ground | required, not yet built | DESIGN DECISION |

**RISK:** until stall current is measured, we cannot prove the battery/buck/L298N
chain survives a dual-motor stall. Mitigation for MVP: keep `max_speed_pwm: 200`
(78 %), never reverse instantly at full PWM (firmware currently reverses directly —
acceptable at 200/255 with L298N, flagged for Phase 10 acceleration limiting).

## 3. UNKNOWN list (must stay UNKNOWN until physically measured)

1. Motor rated voltage, no-load RPM, stall current, gear ratio (1:48 vs 1:120)
2. Wheel diameter actually fitted (65 mm assumed), track width actually fitted (180 mm assumed)
3. Battery chemistry, capacity, internal resistance, max discharge
4. Buck converter real output under load
5. ESP32-CAM PSRAM size (2/4/8 MB) and flash size
6. HC-SR04 mounting height/tilt (affects ground-reflection false readings)
7. Encoder PPR/CPR — N/A until encoders purchased
8. Any measured stopping distance, FPS, latency — all `[MEASURED]` slots remain empty

## 4. Advanced hardware (P2 — only after MVP drives, sees, communicates, stops safely)

- **Encoders:** firmware counts ticks on D2/D3 and reports `TICKS:<l>,<r>`
  (Phase 9+, docs/future-work/30); D2/D3 are the UNO's interrupt-capable pins
  (PIN_CONFLICT_REPORT §2). Encoder specs/PPR still UNKNOWN until purchased →
  do not assume PPR; closed-loop claims are HARDWARE REQUIRED.
- **MPU6050:** I2C pins A4/A5 free. No code, no BOM line.
- **Servo:** optional; creates a Timer1/PWM conflict with ENB (see PIN_CONFLICT_REPORT §3).

## 5. Electrical hazards carried into Phase 1 (must be physically checked)

1. **5V→3.3V overvoltage** on any direct Arduino-TX→ESP32-RX wire — only relevant
   if someone wires the UART link docs describe; MVP does not use it.
2. **Brownout** from motors on shared rail → separate rails + common ground.
3. **L298N ENA/ENB jumpers** must be removed or PWM is ignored (motors run full speed —
   a safety issue, not just a performance one).
4. **Safe startup:** firmware `setup()` calls `stopMotors()` first — verified in code;
   physical confirmation on first power-up required (TEST 04).
