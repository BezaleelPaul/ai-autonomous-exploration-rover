# Bring-up protocol

Follow this order. It is the same layer-by-layer method that resurrected the
rover after incident #2: verify one physical layer at a time, never guess.

Two builds exist. Start with the **bench build** (what the current hardware
supports), then move the safety inputs to the **production build** once the
E-stop, divider and 555 interlock are fitted (`docs/WIRING.md`).

---

## Prerequisites

```bash
./setup.sh                 # venv + deps + tests
make compile               # proves both firmwares build
arduino-cli board list     # find your ports
```

Expect `/dev/ttyACM0` (Uno) and `/dev/ttyUSB0` (ESP32); on Windows `COM5`,
`COM6`; on macOS `/dev/cu.usbmodem*`.

---

## Step 0 — power off, wheels up

Battery disconnected. Rover on a stand so both wheels are free.

**Bench:** power the Uno from USB only and finish steps 1–3 without the pack.

Before applying power to a **production** build, measure:

| Test | Expected |
|---|---|
| VM ↔ GND with the switch open | open circuit |
| Buck output, no load | 5.0 V ± 0.1 V |
| `A0` (pack connected) | 2.0–2.7 V (100k/47k divider) |
| `A1` with the E-stop released | 0 V (NC contact closed to GND) |
| `A1` with the E-stop pressed | 5 V (contact open, pull-up) |
| All three Uno→ESP32 dividers | ≤ 3.3 V |

---

## Step 1 — drive tier in isolation (`wheel_test_hold.ino`)

This sketch ignores the sonar, the E-stop and the watchdog. It **does** emit the
1 kHz heartbeat, so a fitted 555 interlock stays enabled.

```bash
make flash-test PORT_UNO=/dev/ttyACM0
make monitor-uno PORT_UNO=/dev/ttyACM0     # 115200
```

| Key | Expected |
|---|---|
| `1` | left wheel forward for 3 s |
| `2` | left wheel reverse |
| `3` | right wheel forward |
| `4` | right wheel reverse |
| `5` | both forward |
| `0` | immediate stop |

Pass: both wheels spin smoothly both ways, no buzzing, no Uno reset, no heat
after 30 s.

Dead wheel? Measure VM at the driver, then the motor tab against the pack. That
separates driver from wiring in 30 seconds.

---

## Step 2 — reflex core (`motion_safety.ino`), USB only

```bash
make flash-uno PORT_UNO=/dev/ttyACM0
make monitor-uno PORT_UNO=/dev/ttyACM0
```

Expected banner:

```
[UNO] BOOT:STOP
[UNO] LINK: 9600 8N1 RX=D4 (CRC required) | USB commands: on
[UNO] SAFETY BUILD: estop=off battery=off rear=off encoders=open-loop wdt=250ms | boot state: motors coasting
[UNO] GATE: 15..35 cm (speed-scaled)
[UNO] SAFETY: estop=ARMED | batt=-- | fault=NONE | gate<=27cm
[UNO] CMD: S | Speed: 180/255 | STATE: STOP | STATUS: OK
[UNO] DIST: 42 cm | Gate Check: PASSED (>= 27 cm)
```

Checks:

1. **Silent boot.** No twitch on reset (PWM 0 before `setup()`).
2. **Distance tracks** your hand.
3. **Gate blocks.** Put a book at ~10 cm → `REFUSED (< 27 cm)`.
4. **Speed scaling.** At `F60` the gate is 15 cm; at `F255` it is 35 cm. Verify
   with a tape measure: 25 cm + `F255` must refuse, 25 cm + `F60` must pass.
5. **Forward refused, escape allowed.** `F200` with something close →
   `STATE: BLOCKED`; `B120` and `L120` still work.
6. **Watchdog.** `F200` with a clear path, then stop typing. After 500 ms:
   `STATE: TIMEOUT`, outputs zero.
7. **CRC on the link.** Typed USB commands work without a checksum (bench port).
   The link itself requires one — verified in step 4.
8. **Malformed rejected.** `F999` → `STATUS: ERROR`, motion continues until the
   watchdog. (A bad packet is discarded, not executed.)

> `DIST: -1` on the bench means no echo: aim at a wall 1–2 m away.

---

## Step 3 — production safety checks

Flash the production build **after** fitting the hardware:

```bash
make flash-prod-uno PORT_UNO=/dev/ttyACM0
# with the rear sensor fitted:
make flash-prod-uno PORT_UNO=/dev/ttyACM0 \
     PROD_FLAGS="-DREQUIRE_ESTOP=1 -DBATTERY_SENSE=1 -DREAR_SONAR=1"
```

The banner must say `estop=enforced battery=enforced`.

### 3a. E-stop

1. `SAFETY: estop=ARMED`.
2. Press the mushroom switch → `estop=ENGAGED | fault=ESTOP` and
   `STATE: FAULT`; any motion command is refused (VM is physically cut too).
3. Release → `STATE: STOP`. The rover stays still until a **new** command.
4. Pull the `A1` wire while armed → it must report `ENGAGED` (fail-safe).

### 3b. Battery

1. With a charged pack: `SAFETY: ... batt=8.xxV` and no fault.
2. Use a bench supply (not the pack) to sweep the voltage down:
   * **6.5 V** → no fault (above the cutoff, below the recovery point).
   * **6.3 V** → `fault=BATTLOW`, `STATE: FAULT`, no motion.
   * back to **6.9 V** → fault clears, `STATE: STOP`, new command required.
3. Compare `VBAT` with a multimeter; if it is off by more than ~3 %, adjust
   `kBatteryDividerRatio` in `pins.h`.

### 3c. Heartbeat / STBY interlock

With the 555 fitted:

1. Motors enabled only while the heartbeat runs.
2. Reset the Uno (or hold it in reset): `STBY` must fall within ~110 ms. You can
   measure this at the driver with a meter on `STBY`.
3. `STBY` must be high again after the MCU reboots and stays stopped.
4. If you see the banner `BOOT:STOP (recovered from watchdog reset)`, the 250 ms
   AVR watchdog fired — note what the rover was doing.

### 3d. Rear gate (if fitted)

1. `REAR: xx cm` lines appear.
2. Hold `B120` with a hand 10 cm behind the rover → `STATE: BLOCKED`.
3. Unplug the rear sensor while reversing → reverse is refused (fail-safe).

### 3e. Encoders + closed loop (optional)

Flash the encoder build (it includes the production safety inputs):

```bash
make flash-encoders PORT_UNO=/dev/ttyACM0
```

The banner must say `encoders=closed-loop`, followed by the `ODO:` line.

1. **Wheels off the ground**, command `F150` over USB. `DRIVE: vL=… vR=…` should
   show both wheels turning at a similar speed, and `odo` should climb.
2. Stop, then **calibrate** (`docs/WIRING.md` §9): roll one wheel revolution by
   hand and compare `odo` with `kWheelCircumferenceMm`; then roll 1.00 m.
3. Command `L120`: `th` must change while `x`/`y` stay near zero.
4. Command `F150` for ~2 s on the floor: `x` should advance roughly
   `speed × time`, and the speed should hold as you squeeze the pack voltage.
5. **Stall test:** hold a wheel still while commanding `F200`. After ~1 s the
   rover must report `STATE: FAULT | fault=STALL` and cut the motors. Send `S`
   to acknowledge, then drive again.
6. Compare the commanded `F180` speed with a stopwatch over 2 m:
   `v ≈ 215 mm/s` with the default calibration.

---

## Step 4 — ESP32 gateway

```bash
make flash-esp32 PORT_ESP=/dev/ttyUSB0
arduino-cli monitor -p /dev/ttyUSB0 --config baudrate=115200
```

Expected:

```
[ESP32] BOOT fw=1.2.0
[ESP32] SoftAP AI_Rover_Control -> 192.168.4.1 (up)
[ESP32] HTTP :80 ready | UART2 9600 8N1 TX=GPIO17 -> Uno D4 (CRC on)
[ESP32] uno health pins: alive=GPIO13 fault=GPIO14
```

Then:

0. **OTA:** `make ota-esp32 OTA_HOST=192.168.4.1 OTA_PASS=roverota` should
   complete with `OTA done, rebooting`. Park the rover first.
1. Join `AI_Rover_Control` / `rover1234`, open `http://192.168.4.1/`.
2. Hold ▲ → drives; release → stops immediately.
3. Airplane mode while holding → stops within 500 ms.
4. Check the health chip:
   * `UNO GO` (or `STOP`) + battery in the header → heartbeat and telemetry OK.
   * `UNO --` → health wires not fitted (bench).
   * `UNO LOST` → the heartbeat wire is connected but no edges: MCU hung/reset.
   * `UNO FAULT` + red banner → E-stop or battery latch.
5. `curl http://192.168.4.1/status` and confirm `uno.alive`, `uno.state`,
   `uno.dist_cm`, `uno.battery_mv` change while you drive.

If `uno.alive` is true but `has_telemetry` is false, the `A2` wire or its divider
is missing — health works, real state does not.

**Token mode:** set `API_TOKEN` in `config.h`, re-flash, and export the same
value before starting any laptop script:

```bash
export ROVER_TOKEN='your-token'
python scripts/rover_status.py        # /status stays open
python scripts/bench_smoke_test.py    # /cmd now needs the token
```

---

## Step 5 — laptop tier

```bash
python scripts/rover_status.py          # gateway + uno block
python scripts/bench_smoke_test.py      # HTTP + protocol armour, motors idle
python scripts/bench_smoke_test.py --drive   # wheels, 1.2 s each
```

**No hardware?** Run the virtual rover and point every script at it:

```bash
python simulator/virtual_rover.py --port 8090
python scripts/bench_smoke_test.py --gateway http://127.0.0.1:8090
python scripts/soak_test.py --gateway http://127.0.0.1:8090 --seconds 10
```

Then the camera:

1. Phone joins the rover AP, IP Webcam → *Start server*.
2. `python scripts/rover_status.py --set-camera http://192.168.4.2:8080/video`
3. `python scripts/ai_video_server.py --dry-run` → boxes and zones, no motion.
4. `python scripts/ai_video_server.py` → autonomous.

---

## Step 6 — calibrate for the demo

| Knob | Start | Tune when |
|---|---|---|
| `zones.speed` | 140 | stalls on carpet → 160–180; twitchy → 110 |
| `zones.stop_area` | 0.28 | brakes late → 0.20; early → 0.35 |
| `zones.min_conf` | 0.35 | false positives → 0.45; misses → 0.25 |
| `zones.switch_frames` | 2 | wobble → 3; sluggish → 1 |
| `imgsz` | 320 | 10+ FPS → 416 is better but slower |

The **forward gate is now speed-scaled**, so a faster demo run stops earlier.
Measure the stopping distance at your demo speed and keep the gate above it.

---

## Troubleshooting matrix

| Symptom | Likely cause | Check |
|---|---|---|
| Nothing on serial | wrong port / monitor open twice | `arduino-cli board list` |
| `DIST: -1` always | TRIG/ECHO swapped, no 5 V, missing GND | continuity, manual echo test |
| `DIST` jumps 10 ↔ 300 | single-sample noise | median filter is on; 100 µF across VCC/GND |
| Forward refused in open space | no echo (soft/angled surface, > 4 m) | aim at a wall |
| Forward refused at the demo speed | speed-scaled gate | lower `--speed` or measure the distance |
| `SAFETY: estop=ENGAGED` but nothing pressed | `A1` floating / wire off | jumper `A1`–`GND` **and** `-DREQUIRE_ESTOP=0`, or fix the switch |
| `fault=BATTLOW` on a charged pack | divider missing / wrong ratio | measure `A0` (2.0–2.7 V), recalibrate |
| Motors buzz, no motion | voltage collapse or STBY low | measure VM and STBY while commanding |
| `STBY` low only after a reset | 555 interlock working as designed | heartbeat resumes after boot |
| Uno resets on motor start | brownout | pack for motors, USB/buck for logic |
| ESP32 AP missing | weak 5 V / cable | direct USB port, check `SoftAP … FAILED` |
| `/cmd` 400 | payload not whitelisted / bad CRC | `F|B|L|R|S` + 0–255; the URL must not include the CRC |
| `/cmd` 429 | client faster than 60 ms | normal clients send every 150–200 ms |
| `UNO LOST` in the pad | heartbeat missing | `D2` → divider → `GPIO13` |
| `uno.state` stale | telemetry wire missing | `D3` → divider → `GPIO16` |
| `crc_failures` climbing | noisy UART / poor ground | shortest possible wire, star ground, 9600 baud |
| `FAULT: STALL` while driving | wheel jammed or encoder unplugged | free the wheel, check `D2`/`D3`, send `S` |
| `odo` does not move | encoder VCC/GND or wrong pin | `odo` must change when you turn the wheel by hand |
| Speed drifts from the request | calibration or battery sag | repeat the 1 m calibration; check `vL/vR` |
| OTA fails | wrong IP/password, or not on the AP | `ping 192.168.4.1`, `OTA_PASSWORD`, park the rover |
| `/cmd` 401 | token mode enabled | `export ROVER_TOKEN=...` or clear `API_TOKEN` |
| Rover creeps after release | client still sending | `last_cmd_age_ms` should grow past 500 |

---

## After a crash or a short

1. **Disconnect the pack.** Remove the cells if anything is warm or discoloured.
2. Inspect power conductors at the chassis pass-throughs.
3. Continuity check VM ↔ GND with the switch **off** (must be open).
4. Re-run step 1 before trusting the full stack.
5. If the Uno resets randomly, check the 5 V rail under load — a damaged buck
   converter looks fine unloaded and collapses under motor current.
6. Check `/status` → `uno.crc_failures` and the USB log for `CRC:FAIL` after an
   incident; they are early warning signs of a damaged harness.
