# As-built configuration (no extra parts)

This is the configuration to use with the hardware you already own. It needs
**nothing else to buy** and it is the build the report and demo should describe.

---

## Hardware assumed present

| Part | Use |
|---|---|
| Arduino Uno R3 | reflex core |
| ESP32 DevKit V1 | Soft-AP, drive pad, OTA, UART bridge |
| TB6612FNG | motor driver (`STBY` tied to 5 V) |
| 2 × TT 1:48 gearmotors + wheels + caster | drive |
| HC-SR04 | forward gate |
| 2S 18650 pack + LM2596 buck + switch + fuse | power |
| Smartphone | IP Webcam stream |
| Laptop | YOLO tier |
| Acrylic chassis, wiring, USB cables | build |

---

## Flash exactly this (bench build)

```bash
make flash-uno   PORT_UNO=/dev/ttyACM0
make flash-esp32 PORT_ESP=/dev/ttyUSB0
```

**Do not** flash `flash-prod-uno` or `flash-encoders`: those builds enforce the
E-stop (`A1`) and battery divider (`A0`) and expect encoders. Without the parts
they will report a fault and refuse to drive — correct behaviour, wrong build.

`make install-libs` is only needed if you open the sketches in the Arduino IDE.

---

## What is active on this configuration

| Layer | Status | Evidence |
|---|---|---|
| Boot stopped (PWM 0 before `setup()`) | **active** | serial `BOOT:STOP`, native test |
| 250 ms AVR watchdog | **active** | source contract; `wdt_reset()` in loop |
| 15 → 35 cm speed-scaled forward gate | **active** | `DIST`/`Gate Check` lines |
| 500 ms link watchdog | **active** | `STATE: TIMEOUT` |
| CRC-8 on the ESP32→Uno link | **active** | `CRC:FAIL` / `CRC:MISSING` |
| 15 ms gap framing + whitelist | **active** | rejected-frame log |
| Median-of-3 sonar filtering | **active** | code + native test |
| Vision: 3-zone steering, 28 % area brake | **active** | annotated stream |
| Vision: bbox-growth **TTC brake** (0.8 s) | **active** | `closing fast (TTC …)` |
| Vision: stale-camera stop + 200 ms heartbeat | **active** | pilot log |
| HTTP rate limit + `/status` | **active** | 429 / JSON |
| OTA (ESP32) | **active** | `make ota-esp32` |
| Optional API token / CORS | **available** | `config.h` |

Run the proof before the demo:

```bash
make test                                  # 375 Python tests + 225 native
python scripts/bench_smoke_test.py         # gateway + protocol armour
python scripts/soak_test.py --seconds 60   # link/latency
```

---

## Code-ready, **not fitted** (do not claim these as hardware-verified)

| Feature | Missing part | Effect today | Evidence it is implemented |
|---|---|---|---|
| E-stop latch (`A1`) | 2-pole NC switch | no E-stop; master switch is the physical stop | native `test_estop_latches_a_fault` |
| Battery cutoff (`A0`) | 100k/47k divider | no `VBAT`, no low-battery fault | native `test_battery_cutoff_and_recovery` |
| 555 STBY interlock | NE555 + R/C | `STBY` stays on 5 V; AVR WDT + link watchdog still protect | `test_loop_never_blocks` |
| Closed-loop speed + odometry | encoder motors | open-loop PWM; `vL/vR/odo = 0` | native speed-loop/odometry tests |
| Stall latch | encoders | cannot detect a jam | native stall tests |
| Rear gate | second HC-SR04 | reverse is unguarded | native rear-gate tests |
| Uno health in `/status` | 3 × divider resistors | `uno.wired:false`, pad shows `UNO --` | ESP32 contract tests |

The *logic* is tested on the host; the *wiring* is what is missing. Say exactly
that in the report.

---

## What the operator can see

* **Drive pad:** connection, uptime, packets, rejects, command age. The `UNO`
  chip shows `--` because the health harness is not wired.
* **USB serial monitor (115200):** the authoritative rover state — `BOOT:STOP`,
  `DIST`/`Gate Check`, `CMD/STATE/STATUS`, `ACT` pin levels, `ALERT:OBSTACLE`,
  `CRC:FAIL`.
* **Vision server** (`http://localhost:8080`): boxes, zones, chosen command,
  TTC/area-brake reason.

Use the USB monitor in the demo in place of `/status.uno`; it needs no parts.

---

## Demo procedure for this build

1. **Cold boot:** switch on, no motion, LED 1 Hz, USB shows `BOOT:STOP`.
2. **Teleop:** hold ▲, move the PWM slider, release → stop.
3. **Gate:** hand/clipboard at ~12 cm → `REFUSED`, motors stop; reverse out.
4. **Watchdog:** hold ▲, airplane mode → `STATE: TIMEOUT` within 500 ms.
5. **Physical stop:** master switch (there is no E-stop fitted). Say the E-stop
   layer is implemented and tested but not installed.
6. **Vision:** `--dry-run` first, then live; show the TTC/area brake by walking
   quickly toward the rover.
7. **Evidence:** USB log + `make test` output + model card.

Updated runbook: [`FINAL_DEMO.md`](FINAL_DEMO.md).

---

## Honest wording for the report

Use **“implemented and unit-tested; not fitted on the as-built platform”** for
E-stop, battery cutoff, 555 interlock, encoders/odometry, stall and rear gate.
Use **“verified on hardware”** for boot-stop, the speed-scaled gate, the 500 ms
watchdog, CRC rejection, sonar fail-safe and the USB telemetry.

Suggested sentence:

> The safety layers for E-stop, battery cutoff, a hardware STBY interlock and
> closed-loop odometry are implemented and covered by host tests, but the
> current as-built platform is limited to the bench configuration: boot-stop,
> the 15–35 cm speed-scaled ultrasonic gate, the 500 ms link watchdog, CRC-8
> link integrity and vision-side stale-frame/TTC braking. The remaining layers
> require additional hardware that is specified in the wiring annex.

---

## If parts arrive later

`docs/WIRING.md` and `docs/BRINGUP.md` §3 contain the exact modification and
acceptance procedure; `make flash-prod-uno` / `make flash-encoders` are already
built and tested.
