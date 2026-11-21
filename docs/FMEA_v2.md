# Failure Modes and Effects Analysis (v2)

Revision 2 covers the hardened platform (firmware 1.3.0): CRC link, hardware
watchdog + STBY interlock, E-stop/battery/stall latches, speed-scaled and rear
gates, closed-loop speed, and truthful Uno telemetry.

**Severity:** 1 = cosmetic, 5 = injury/fire. **Detection** = how the operator or
software finds out. **Residual** = what is still not covered.

| ID | Subsystem | Failure mode | Root cause | Sev | Detection | Mitigation (implemented) | Verification | Residual risk |
|---|---|---|---|---|---|---|---|---|
| P1 | Power | Battery dead short | Lug rotating into chassis / chafed harness | 5 | Smoke, heat, pack voltage collapse | 3 A fuse, heat-shrink, direct 20 AWG, cells removed during work | `WIRING` checklist, incident #1 post-mortem | Fuse protects the wire, not the driver; no current limiter |
| P2 | Power | Logic brownout under motor surge | Shared breadboard rail | 4 | `BOOT:STOP (watchdog reset)`, `/status` `UNO LOST` | Separate buck rail, star ground, no motor current in breadboard | `WIRING` §10, `BRINGUP` §0 | Buck has no under-voltage lockout |
| P3 | Power | Deep discharge / cell damage | No BMS | 4 | `FAULT: BATTLOW`, `/status` `battery_mv` | 6.4 V cutoff + 6.8 V recovery, BMS recommended | `test_battery_cutoff_and_recovery` | BMS is optional; cells still drain when switched off |
| D1 | Drive | Motor runaway, MCU hung | Firmware hang / reset | 5 | Heartbeat stops (`UNO LOST`), 555 timeout | 250 ms AVR WDT + 1 kHz heartbeat → 555 → `STBY` low in ~110 ms | `test_loop_never_blocks`, `BRINGUP` §3c | 555 circuit must be fitted; bench build relies on software only |
| D2 | Drive | Runaway after link loss | Wi-Fi drop, laptop crash | 5 | `STATE: TIMEOUT`, `/status` age | 500 ms watchdog zeroes PWM | `test_watchdog`, `test_heartbeat_stays_under_the_firmware_watchdog` | None identified |
| D3 | Drive | Corrupted command becomes motion | EMI on the UART | 4 | `CRC:FAIL`, `/status` `crc_failures` | CRC-8 on the link + strict whitelist; USB bench accepts legacy frames | `test_crc_required_on_the_link` | A corrupted frame that re-computes a valid CRC is impossible in practice |
| D4 | Drive | Wheel jam / gearbox damage | Obstacle under the chassis | 4 | `FAULT: STALL` | PI loop detects < 15 % of target for 1 s → fault, motors cut | `test_speed_loop_stall_window`, `test_stall_fault_requires_acknowledgement` | Encoder build only; open-loop build cannot detect it |
| D5 | Drive | Speed drift as the pack drains | Open-loop PWM | 2 | None without encoders | Closed-loop PI holds the requested mm/s | `test_speed_loop_tracks_the_requested_speed` | Encoder build only; wheel slip still biases odometry |
| S1 | Sensor | Sonar dead / unplugged | Harness, 5 V loss | 4 | `DIST: -1`, `Gate Check: FAILED` | Fail-safe: forward refused, escapes allowed | `test_dead_sensor_blocks_forward` | Reverse remains unguarded if the rear sensor is absent |
| S2 | Sensor | Sonar false negative (soft/angled surface) | Acoustic absorption | 3 | `DIST: -1` | Same fail-safe (stops rather than guesses) | `test_dead_sensor_blocks_before_moving` | Rover may refuse to move in open soft spaces |
| S3 | Sensor | Rear blind spot | No rear sensor in the default build | 4 | None | Optional rear HC-SR04, 15 cm reverse gate, fail-safe on loss | `test_rear_gate_only_when_a_rear_sensor_is_present` | Not fitted by default; mutually exclusive with encoders |
| S4 | Sensor | False positive from a single spike | Ultrasonic noise | 2 | Distance jumps | Median-of-3 filter | `test_median_filter` | Not a substitute for a second sensor |
| V1 | Vision | Camera stream freezes | Phone app crash, Wi-Fi stall | 4 | `stale` log, `/status` telemetry age | Pilot sends STOP once and goes silent | `test_stale_camera_sends_one_stop` | The Uno cannot see the camera; it relies on the pilot |
| V2 | Vision | Wrong class / false positive | Domain gap, small model | 3 | Overlay review | Confidence threshold, area brake, speed-scaled gate | `test_large_object_brakes_even_in_center` | No depth sensor; 2D area is a proxy for distance |
| V3 | Vision | Laptop dies while driving | OS crash, battery | 4 | Commands stop | 500 ms Uno watchdog | `test_watchdog` | Mission ends (safe stop) |
| C1 | Comms | Wi-Fi packet loss | Interference, range | 3 | `/status`, timeout state | Heartbeat resend (200 ms) + 500 ms watchdog | `test_command_is_resent_on_the_heartbeat` | 2.4 GHz congestion at the expo |
| C2 | Comms | HTTP flood / DoS | Malicious or buggy client | 3 | `429`, rejected counter | 60 ms non-stop rate limit, 4 client cap | `test_command_rate_is_limited_but_stop_is_never_delayed` | No per-IP quota |
| C3 | Security | Unauthorized driving | Password shared at the demo | 4 | `/status` forwarded without you | WPA2 + optional `API_TOKEN` + configurable CORS | `test_token_protects_state_changing_endpoints_only` | No TLS, no per-user auth, AP password is printed in the report |
| C4 | Security | OTA abuse | Default OTA password | 3 | OTA log line | Password-protected ArduinoOTA, park-before-update rule | `test_ota_is_wired_and_password_protected` | Password is in the repo; change it |
| F1 | Firmware | Telemetry collides with a command | Half-duplex AVR software serial | 2 | `telemetry_age_ms` grows | Send only in a post-command window; CRC | `test_uart_telemetry_can_be_disabled` | A client faster than 60 ms could still overlap (rate-limited) |
| F2 | Firmware | OTA interrupted | Power loss mid-flash | 3 | ESP32 reboots to the old image | OTA updates only the ESP32; the Uno watchdog stops the motors | `BRINGUP` §4 | No rollback slot on the ESP32 partition scheme |
| E1 | Environment | Rover falls down stairs | No cliff sensor | 5 | None | **Not mitigated** | — | Hard gap: add a downward ToF/IR pair before stairs |
| M1 | Mechanical | Chassis crack / wheel detach | Acrylic fatigue | 3 | Visual inspection | M3 hardware, zip-tied strain relief | `WIRING` checklist | No scheduled inspection interval |
| R1 | Compliance | Li-ion transport / EMC | No UN38.3/CE testing | 5 | — | **Not addressed** | — | Required for a shipped product, not for a university demo |

---

## Safety response budget (measured targets)

| Event | Target | Implemented by | Verified |
|---|---|---|---|
| Command loss → stop | ≤ 500 ms | link watchdog | native `test_watchdog` |
| Release button → stop | ≤ 150 ms | UI sends S on release, 60 ms rate limit | UI contract tests |
| MCU hang → drive disabled | ≤ 250 ms (WDT resets; 555 drops STBY in parallel) | WDT + heartbeat | `BRINGUP` §3c (measure with a meter) |
| E-stop → VM cut | immediate (hardware) | 2-pole switch | `BRINGUP` §3a |
| Camera freeze → stop | ≤ 1.5 s + one stop packet | pilot stale check | `test_stale_camera_sends_one_stop` |
| Stall → motors cut | ≤ 1 s + 50 ms | PI loop | native stall tests |
| Low battery → no motion | ≤ 250 ms (ADC period) | battery service | native battery tests |

---

## Before / after (v1.1 → v1.3)

| Risk | v1.1 (report) | v1.3 (this build) |
|---|---|---|
| MCU hang | software link watchdog only | AVR WDT + hardware STBY interlock |
| Lost/corrupt command | whitelist only | CRC-8 + whitelist |
| E-stop | none | 2-pole NC, hardware VM cut + fault latch |
| Battery protection | none | 6.4 V cutoff + recovered hysteresis |
| Forward gate | fixed 15 cm | 15 cm floor, 35 cm at full speed |
| Reverse | unguarded | optional rear gate, fail-safe |
| Stall | undetected | 1 s latch (encoder build) |
| Speed | open loop | PI closed loop (encoder build) |
| Rover state | inferred | real telemetry + heartbeat + fault line |
| Field updates | USB only | password-protected OTA |
| Unauthorized control | WPA2 only | optional token + CORS allow-list |

## Residual risks to state honestly

1. **No cliff/edge detection** — do not drive near stairs or table edges.
2. **No current sensing** — a stall is inferred from encoders, not measured.
3. **Monocular vision** — no depth; proximity is a 2D-area heuristic.
4. **No TLS** — the AP is trusted-LAN security, not internet security.
5. **No BMS by default** — the firmware cutoff is the last line of defence.
6. **Encoders are single-channel** — odometry assumes the commanded direction;
   coasting in the opposite direction is not observed.
