# PINOUT — AI Visual Intelligence Rover (authoritative)

**Source of truth for all wiring docs.** Extracted from firmware, not from prose docs:
`arduino/rover_controller/rover_controller.ino` and `esp32/camera_stream/camera_stream.ino`.
Conflicts/reservations rationale: `docs/phase0/PIN_CONFLICT_REPORT.md`.

## Arduino UNO

| Pin | Function | Notes |
|---|---|---|
| D0 (RX) | USB serial from laptop | **Do not reuse** |
| D1 (TX) | USB serial to laptop | **Do not reuse** |
| D2 | **Left wheel encoder (INT0)** | Firmware `encISR_L`; ticks reported as `TICKS:<l>,<r>` (inert until encoder fitted) |
| D3 | **Right wheel encoder (INT1)** | Firmware `encISR_R`; ticks reported as `TICKS:<l>,<r>` (inert until encoder fitted) |
| D4 | **Reserved: status LED / future servo signal** | First free choice |
| D5 | L298N ENA (PWM) | Speed control left |
| D6 | L298N IN1 | |
| D7 | L298N IN2 | |
| D8 | L298N IN3 | |
| D9 | L298N IN4 | Timer1 collision if `Servo` lib added |
| D10 | L298N ENB (PWM) | Timer1 collision if `Servo` lib added |
| D11 | HC-SR04 TRIG | |
| D12 | HC-SR04 ECHO | |
| D13 | free | (old docs claimed LED heartbeat — firmware does not) |
| A4/A5 | **Reserved: MPU6050 I2C** | |
| A0-A3 | free (spare analog) | |

## ESP32-CAM (AI-Thinker)

Camera DVP consumes GPIO 0, 5, 18, 19, 21, 22, 23, 25, 26, 27, 32, 34, 35, 36, 39.

| GPIO | Status |
|---|---|
| 1 (TX0) / 3 (RX0) | USB flashing/serial only — **do not wire** until flashing workflow is solved |
| 4 | Onboard flash LED — usable |
| 12 | **Strapping pin (MTDI) — never attach peripherals** |
| 13, 14, 15 | Free — preferred for future servo / extra UART |
| 16 | Free-ish (PSRAM on some boards) |
| 33 | Free (old docs claimed red status LED — firmware does not drive it) |

## Hard rules

1. **SG90 servo never on the UNO** — `Servo` lib uses Timer1 and kills ENB (D10) PWM.
   Servo, if ever added, goes to ESP32 GPIO 13/14. Servo is P3.
2. **L298N ENA/ENB onboard jumpers must be removed** — otherwise PWM is bypassed and
   motors run uncontrolled at full speed (safety hazard, checked in Test 04).
3. Encoders (D2/D3) are wired to firmware tick counters (`TICKS:` telemetry);
   MPU6050 (A4/A5) stays reserved. Do not reassign either.
4. Wiring change → update this file first, then reconcile other docs against it.
