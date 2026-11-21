# API and protocol reference

Three interfaces: **HTTP** (phone/laptop → ESP32), **UART** (ESP32 ⇄ Uno) and
**OTA** (laptop → ESP32). Everything is validated twice — in
`firmware/libraries/AIRoverCore/src/protocol.h` and in
`software/ai_rover/protocol.py` — and the test suite keeps the two in sync.

---

## 1. Command grammar

```
<CMD>[<SPEED>][*<CRC>]\n
```

| Field | Values | Notes |
|---|---|---|
| `CMD` | `F` `B` `L` `R` `S` | lowercase accepted, normalised to uppercase |
| `SPEED` | optional `0`–`255` | clamped to **60–255**; `S` ignores it |
| `*CRC` | optional 2 hex digits | CRC-8/SMBUS over everything before `*` |
| terminator | `\n`, `\r`, or 15 ms of silence | the Uno's gap framer ends the packet |

```
F200*B1        ESP32 -> Uno, CRC on (required on the link)
S*BE           stop with checksum
F200           legacy / human form (USB bench + HTTP, no CRC)
```

CRC-8/SMBUS: poly `0x07`, init `0x00`, no reflection, no final XOR.
Check value: `crc8("123456789") == 0xF4`.

**Where the CRC is mandatory:** only the ESP32→Uno UART. HTTP runs over TCP and
a human typing on the serial monitor cannot compute a checksum. The ESP32
accepts `?c=F200` and emits `F200*B1` on the wire.

Rejected (HTTP 400 / `STATUS: ERROR`): empty payload, unknown command, > 3
digits, value > 255, extra spaces, trailing garbage, non-ASCII digits, body
longer than 8 characters, malformed/wrong CRC, and a missing CRC on the link.

`L`/`R` are **pivot turns** (one wheel forward, one reverse).

**With encoders** the speed field is a speed request, not a duty cycle:
`F180` ≈ 55 % of `kMaxSpeedMmS` (default 350 mm/s → ~215 mm/s), held by a PI
loop as the battery drains. Without encoders it is plain PWM.

---

## 2. HTTP API (ESP32, `http://192.168.4.1`)

| Endpoint | Method | Auth | Behaviour |
|---|---|---|---|
| `/` | GET | — | mobile drive pad (token injected from flash) |
| `/cmd?c=<CMD><SPEED>` | GET | token | whitelist → rate limit → CRC → UART |
| `/status` | GET | — | gateway + Uno health JSON |
| `/cam?u=<URL>` | GET | token | persist camera URL in NVS |
| `/cam` | GET | token | current camera URL |
| `/health` | GET | — | `ok` (scripts/CI) |
| `/favicon.ico` | GET | — | 204 |

`/cmd` responses:

```json
{ "ok": true, "cmd": "F", "speed": 200, "frame": "F200*B1" }
{ "ok": false, "error": "invalid command" }     // 400
{ "ok": false, "error": "rate limited" }        // 429
{ "ok": false, "error": "token required" }      // 401
{ "ok": false, "error": "frame build failed" }  // 500
```

**Rate limit:** non-stop commands are capped at one per **60 ms** (the AVR
software-serial link is half-duplex). `S` is never delayed. The drive pad sends
every 150 ms, the pilot every 200 ms.

**Auth:** set `API_TOKEN` in `config.h` to require a token on `/cmd` and `/cam`
(query `?k=…` or header `X-Rover-Token`). `/status` and `/health` stay open so
dashboards work. The laptop scripts read `ROVER_TOKEN` from the environment:

```bash
export ROVER_TOKEN='your-token'
python scripts/ai_video_server.py
```

**CORS:** `CORS_ORIGIN` in `config.h` (default `*`; set it to
`http://localhost:8080` for the local dashboard in production).

`/status`:

```json
{
  "fw": "1.3.0",
  "uptime_ms": 91234,
  "ssid": "AI_Rover_Control",
  "ip": "192.168.4.1",
  "clients": 2,
  "forwarded": 1841,
  "rejected": 3,
  "last_cmd": "F140",
  "last_cmd_age_ms": 42,
  "camera": "http://192.168.4.2:8080/video",
  "free_heap": 214336,
  "uno": {
    "alive": true,
    "wired": true,
    "hz": 1000.0,
    "fault_pin": false,
    "has_telemetry": true,
    "telemetry_age_ms": 45,
    "state": "GO",
    "fault": "NONE",
    "cmd": "F",
    "pwm": 180,
    "dist_cm": 42,
    "battery_mv": 7580,
    "speed_l_mm_s": 318,
    "speed_r_mm_s": 316,
    "odo_x_mm": 1200,
    "odo_y_mm": 300,
    "odo_theta_deg": 45,
    "odometer_mm": 1250,
    "crc_failures": 0,
    "overflows": 0
  }
}
```

| Field | Meaning |
|---|---|
| `uno.alive` | 1 kHz heartbeat seen in the last second |
| `uno.wired` | heartbeat has **ever** been seen (dead vs not wired) |
| `uno.hz` | measured heartbeat frequency |
| `uno.fault_pin` | Uno `A4` fault line is LOW |
| `uno.telemetry_age_ms` | age of the last valid `T,…` frame, `-1` if none |
| `uno.state` / `fault` | the Uno's real state, not a guess |
| `uno.speed_l/r_mm_s` | closed-loop wheel speeds (0 without encoders) |
| `uno.odo_*` / `odometer_mm` | pose and path length (0 without encoders) |
| `uno.crc_failures` | telemetry frames dropped by the checksum |

`last_cmd_age_ms` is the quickest gateway-only debug number: if it grows past
500 while you hold a button, the Uno has already stopped.

### curl

```bash
curl http://192.168.4.1/status
curl "http://192.168.4.1/cmd?c=F180"
curl "http://192.168.4.1/cmd?c=S"
curl "http://192.168.4.1/cmd?c=Z"           # -> 400
curl "http://192.168.4.1/cmd?c=F180&k=..."  # token mode
```

---

## 3. UART links

| Property | Command link | Telemetry link |
|---|---|---|
| ESP32 pin | `GPIO17` TX2 | `GPIO16` RX2 |
| Uno pin | `D4` (RX) | `A2` (TX) |
| Baud | 9600 8N1 | 9600 8N1 |
| Framing | 15 ms gap / CRLF | `\n` |
| Integrity | CRC-8 required | CRC-8 required |
| Watchdog | 500 ms → `STATE: TIMEOUT` | advisory |

The ESP32 never forwards the raw HTTP value: it parses, clamps, rebuilds and
checksums the frame, so `?c=F999` cannot reach the motor core.

---

## 4. Uno → ESP32 telemetry

```
T,<state>,<cmd>,<pwm>,<dist>,<mv>,<fault>,<vL>,<vR>,<x>,<y>,<theta>,<odo>*<CRC>\n
T,1,F,180,42,7580,0,320,-320,1200,300,45,1250*6C
```

| Field | Values |
|---|---|
| `state` | 0 STOP, 1 GO, 2 BLOCKED, 3 TIMEOUT, 4 FAULT |
| `cmd` | last/most relevant command character |
| `pwm` | commanded PWM |
| `dist` | front distance cm, `-1` = invalid |
| `mv` | pack millivolts, `0` = not sensed |
| `fault` | 0 NONE, 1 ESTOP, 2 BATTLOW, 3 STALL |
| `vL`,`vR` | wheel speeds mm/s (negative = reverse) |
| `x`,`y` | pose mm |
| `theta` | heading degrees, −180…180 |
| `odo` | path length mm |

Sent at 5 Hz **only inside a safe window**: just after a command (the gateway
will not transmit for ≥ 60 ms) or after 1 s of link silence. The AVR software
serial disables interrupts while transmitting, so this timing rule prevents it
from eating a command byte. Lost frames are dropped by the checksum and
`telemetry_age_ms` grows — telemetry is advisory, never used for control.

Python mirror:

```python
from ai_rover import parse_telemetry

tlm = parse_telemetry("T,1,F,180,42,7580,0,320,-320,1200,300,45,1250*6C")
tlm.state_name, tlm.battery_v, tlm.odometer_mm   # ('GO', 7.58, 1250)
```

---

## 5. Uno USB telemetry dictionary (115200 8N1)

| Line | Meaning |
|---|---|
| `[UNO] BOOT:STOP` | booted stopped, PWM 0 |
| `[UNO] BOOT:STOP (recovered from watchdog reset)` | the 250 ms WDT fired |
| `[UNO] LINK: 9600 8N1 RX=D4 (CRC required) \| USB commands: on` | link config |
| `[UNO] SAFETY BUILD: estop=enforced battery=enforced rear=off encoders=closed-loop wdt=250ms` | compiled options |
| `[UNO] GATE: 15..35 cm (speed-scaled)` | forward gate envelope |
| `[UNO] ODO: cpr=960 wheel=204.0mm track=150mm (PI speed control)` | encoder calibration |
| `[UNO] SAFETY: estop=ARMED \| batt=7.58V \| fault=NONE \| gate<=27cm` | live snapshot |
| `[UNO] DIST: 42 cm \| Gate Check: PASSED (>= 27 cm)` | forward allowed |
| `[UNO] DIST: 11 cm \| Gate Check: REFUSED (< 15 cm)` | inside the gate |
| `[UNO] DIST: -1 cm \| Gate Check: FAILED (sensor lost, DIST:-1)` | echo loss |
| `[UNO] REAR: 120 cm` | optional rear sensor |
| `[UNO] DRIVE: vL=318 vR=316 mm/s \| odo=412mm x=398 y=12 th=3deg` | encoder build, 2 Hz |
| `[UNO] CMD: F \| Speed: 180/255 \| STATE: GO \| STATUS: OK` | accepted |
| `[UNO] CMD: S \| Speed: 180/255 \| STATE: TIMEOUT \| STATUS: OK` | watchdog |
| `[UNO] CMD: S \| Speed: 180/255 \| STATE: FAULT \| STATUS: OK` | E-stop / battery / stall |
| `[UNO] STATUS: ERROR \| rejected="F200" src=LINK \| CRC:MISSING \| total=4` | checksum missing |
| `[UNO] STATUS: ERROR \| rejected="F200*00" src=LINK \| CRC:FAIL \| total=5` | corrupt frame |
| `[UNO] ALERT:OBSTACLE dist=11cm cmd=F --> Immediate Motor STOP (PWM=0)` | hazard |
| `[UNO] ACT: PWMA=200 PWMB=200 AIN1=H AIN2=L BIN1=H BIN2=L` | pin levels |

States: `STOP`, `GO`, `BLOCKED`, `TIMEOUT`, `FAULT`.
Statuses: `OK`, `ERROR`, `BLOCKED`.
Faults: `NONE`, `ESTOP`, `BATTLOW`, `STALL`.

### Status LED

| State | Pattern |
|---|---|
| STOP | 1 Hz |
| GO | solid |
| BLOCKED / TIMEOUT | 5 Hz |
| FAULT | 2.5 Hz |

---

## 6. OTA updates (ESP32)

`ENABLE_OTA` in `config.h` is on by default; the hostname is `rover.local` and
the password is `OTA_PASSWORD` (`roverota`).

```bash
# arduino-cli: build the .bin, then espota (supports the password)
make ota-esp32 OTA_HOST=192.168.4.1 OTA_PASS=roverota

# or from the Arduino IDE: Tools -> Port -> "rover at 192.168.4.1"
```

Safety: an OTA reboot stops the command stream, so the Uno's 500 ms watchdog
stops the motors. Park the rover before updating. The OTA password is the only
protection besides WPA2 — change it before the expo.

---

## 7. Compile-time options

### Uno (`motion_safety.ino`)

| Macro | Default | Effect |
|---|---|---|
| `ACCEPT_USB_COMMANDS` | `1` | accept commands on USB (bench) |
| `REQUIRE_ESTOP` | `0` | enforce the `A1` NC contact |
| `BATTERY_SENSE` | `0` | read the `A0` divider, 3.2 V/cell cutoff |
| `ENCODERS` | `0` | closed-loop speed + odometry on `D2`/`D3` |
| `REAR_SONAR` | `0` | rear HC-SR04 on `D2`/`D3` (not with `ENCODERS`) |
| `ENABLE_UART_TELEMETRY` | `1` | `T,…` frames on `A2` |
| `SONAR_MEDIAN_FILTER` | `1` | median-of-3 spike rejection |
| `STATUS_LED_ENABLED` | `1` | state LED patterns |

```bash
make compile-prod-uno                                   # E-stop + battery
make flash-encoders PORT_UNO=/dev/ttyACM0               # production + encoders
make compile-uno                                        # all switches to default
```

### ESP32 (`config.h`)

| Macro | Default | Effect |
|---|---|---|
| `AP_SSID` / `AP_PASSWORD` | `AI_Rover_Control` / `rover1234` | Soft-AP |
| `AP_CHANNEL` | `6` | 2.4 GHz channel |
| `ENABLE_CAPTIVE_PORTAL` | `0` | auto-open the pad on join |
| `ENABLE_MDNS` | `1` | `http://rover.local` |
| `ENABLE_OTA` / `OTA_PASSWORD` | `1` / `roverota` | wireless updates |
| `API_TOKEN` | `""` | token required on `/cmd`, `/cam` |
| `CORS_ORIGIN` | `"*"` | allow-list for dashboard fetches |
| `ENABLE_UNO_HEALTH` | `1` | heartbeat + fault monitoring |
| `UNO_ALIVE_PIN` / `UNO_FAULT_PIN` | `13` / `14` | health inputs |
| `CMD_MIN_INTERVAL_MS` | `60` | non-stop command rate limit |
| `MAX_CAMERA_URL` | `192` | NVS string limit |

---

## 8. Python client

```python
from ai_rover import RoverClient

with RoverClient("http://192.168.4.1") as rover:   # sends STOP on exit
    rover.send("F", 180)
    status = rover.status()
    print(status.rover_state, status.battery_v, status.uno_alive, status.uno_fault)
    print(status.uno.get("speed_l_mm_s"), status.uno.get("odometer_mm"))
```

```python
from ai_rover import ZoneSteering, Detection

steering = ZoneSteering()
decision = steering.decide([Detection("person", 0.9, 280, 100, 360, 300)], 640, 480)
print(decision.cmd, decision.zone, decision.reason)   # F CENTER person at cx=0.50
```

```python
from ai_rover import crc8, encode_command, parse_command, required_gate_cm

encode_command("F", 200)                      # 'F200*B1\n'
parse_command("F200*B1", require_crc=True)    # Packet(cmd='F', speed=200, has_crc=True)
crc8("123456789")                             # 0xF4
required_gate_cm(180)                         # 27 (cm)
```
