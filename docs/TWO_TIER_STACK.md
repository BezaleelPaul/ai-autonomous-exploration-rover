# Two-Tier Rover Stack â€” IP Webcam + YOLOv8n + Bluetooth Bridge

A second, **self-contained** pipeline for the same chassis. It shares code
primitives (detector interface, stream client, config loader) with the main
ESP32-CAM stack but **no runtime state, no firmware and no pinout** â€” the two
stacks can coexist in one repository without either one changing.

```
 TIER 1 â€” LAPTOP (software/perception_node)          TIER 2 â€” EMBEDDED
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ IP Webcam app (phone)                     â”‚   â”‚ esp32/bt_bridge/bt_bridge.ino    â”‚
â”‚   http://<PHONE_IP>:8080/video            â”‚   â”‚  Bluetooth SPP "AI_Rover_Control"â”‚
â”‚        â”‚ OpenCV (ESP32Stream)             â”‚   â”‚        â”‚ validates F/B/L/R/S     â”‚
â”‚        â–¼                                  â”‚   â”‚        â–¼                        â”‚
â”‚ YOLOv8n (ultralytics) â”€â”€> Detection       â”‚   â”‚ UART2  GPIO17 (TX2)  9600 8N1   â”‚
â”‚        â–¼                                  â”‚   â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
â”‚ 3-zone steering + area proximity          â”‚            â”‚ GPIO17 -> D4, GND -> GND
â”‚  (F / L / R / S)                          â”‚            â–¼
â”‚        â–¼                                  â”‚   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ SerialLink: USB COM  -or-  BT virtual COM â”‚   â”‚ arduino/motion_safety.ino        â”‚
â”‚  (selectable, reconnecting)               â”‚   â”‚  SoftwareSerial D4 (RX) / D12(TX)â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜   â”‚  HC-SR04 D2/D3, TB6612FNG motors   â”‚
                                                â”‚  15 cm forward gate + watchdog   â”‚
                                                â”‚  telemetry -> USB Serial 9600    â”‚
                                                â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

## 1. Files

| Tier | File | Role |
|------|------|------|
| 1 | `software/perception_node/stream.py` | IP Webcam URL validation + stream client (reconnect, frozen-frame detection) |
| 1 | `software/perception_node/zones.py` | LEFT/CENTER/RIGHT geometry + the F/L/R/S policy (pure, fully typed) |
| 1 | `software/perception_node/hud.py` | 640x480 HUD: zone columns, target box, proximity bar, command badge |
| 1 | `software/perception_node/serial_link.py` | USB vs Bluetooth COM selection, validation, reconnect with backoff |
| 1 | `software/perception_node/node.py` | lifecycle: startup â†’ step â†’ render â†’ run â†’ shutdown (always stops) |
| 1 | `software/perception_node/cli.py` | argparse entry point (`python -m software.perception_node`) |
| 1 | `software/perception_node/bench.py` | bench sender: drive `F/L/R/S` over any COM port, print telemetry |
| 2a | `esp32/bt_bridge/bt_bridge.ino` | Bluetooth Classic SPP â†’ UART2 relay (noise-filtered, latest-wins) |
| 2b | `arduino/motion_safety/motion_safety.ino` | non-blocking ultrasonic safety layer + motor executive + telemetry |

## 2. Wiring

| From | To | Notes |
|------|----|-------|
| ESP32 DevKit V1 GPIO17 (TX2) | Arduino UNO D4 (SoftwareSerial RX) | 9600 baud, 8N1, one-way |
| ESP32 GND | Arduino UNO GND | **common ground is mandatory** |
| HC-SR04 VCC / GND | 5V / GND | power |
| HC-SR04 TRIG / ECHO | Arduino D2 / D3 | trigger / echo |
| TB6612FNG PWMA / AIN1 / AIN2 | Arduino D5 / D6 / D7 | left motor (PWM on D5) |
| TB6612FNG PWMB / BIN1 / BIN2 | Arduino D9 / D8 / D10 | right motor (PWM on D9), STBY -> 5V |
| Laptop â†” rover | USB cable (direct mode) **or** Bluetooth SPP (bridge mode) | chosen by `perception.serial_mode` |

Arduino D0/D1 stay free for the USB Serial Monitor (telemetry only).

## 3. Command protocol

Single ASCII characters, 9600 8N1, case-insensitive:

| Char | Meaning |
|------|---------|
| `F` | forward |
| `B` | back (accepted by firmware; the perception node never emits it) |
| `L` / `R` | turn left / right |
| `S` | stop |

* Perception node decisions: no target â†’ `S`; area â‰¥ `perception.stop_area_ratio`
  â†’ `S` (close range beats steering); left third â†’ `L`; right third â†’ `R`;
  centre third â†’ `F`.
* The ESP32 forwards **only** valid motion characters and counts dropped
  noise/framing bytes (`DROP:` on its debug port).
* Bench fallback: while the bridge is unwired, the Arduino also accepts the
  same characters on USB Serial (`python -m software.perception_node.bench
  COM8 F --listen 5`), through the identical whitelist and noise rules.
* The Arduino judges each received chunk: anything malformed â†’ motors off +
  `STATUS:ERROR` (rate-limited), never a partial actuation.
* A communication gap > `safety.comm_timeout_s` (3 s) stops the motors, so a
  dead Bluetooth link cannot leave the rover driving.

## 4. Hardware safety layer (Arduino, authoritative)

* Ultrasonic readings run as a `micros()`/`millis()` state machine
  (`PING_IDLE â†’ PING_WAIT_RISE â†’ PING_WAIT_FALL`) â€” the loop never blocks on
  `pulseIn()`.
* `distance < 15 cm` **and** command `F` â†’ override: motors cut,
  `STATE:BLOCKED`, `ALERT:OBSTACLE dist=.. cmd=F` (â‰¤ every 500 ms).
* An invalid/missing echo also blocks `F` (`BLOCK_ON_INVALID_ECHO`) â€” the
  rover never drives on a dead sensor.
* `B`, `L`, `R`, `S` are executed exactly as received.
* Telemetry (USB Serial Monitor, 9600): `DIST:<cm>`, `CMD:<c> STATE:<...>`,
  `STATUS:OK|STOP` every 200 ms; `BOOT:STOP` at reset.

## 5. Configuration (`config/config.yaml` â†’ `perception:`)

| Key | Default | Meaning |
|-----|---------|---------|
| `stream_url` | `http://192.168.1.50:8080/video` | IP Webcam URL |
| `model` | `yolov8n.pt` | YOLOv8 Nano weights (swap to shipped `yolo11n.pt` offline) |
| `target_class` | `person` | single target class the detector is locked to |
| `confidence_threshold` | `0.4` | report threshold |
| `imgsz` / `inference_interval` | `320` / `2` | realtime budget on CPU |
| `left_boundary` / `center_boundary` | `0.33` / `0.66` | the three zones |
| `stop_area_ratio` | `0.35` | bbox area / frame area at or above this â†’ `S` |
| `serial_mode` | `auto` | `auto` \| `usb` \| `bluetooth` |
| `serial_port` | `""` | explicit port (e.g. `COM5` for a BT adapter) |
| `baud_rate` | `9600` | must match both firmwares |
| `heartbeat_interval_s` | `1.0` | resend active command (< `safety.comm_timeout_s`) |
| `command_cooldown_s` | `0.2` | spacing between distinct motion commands |
| `hud_enabled` / `window_name` | `true` / `AI Rover - Perception Node` | OpenCV window |

CLI flags override the file without mutating it: `--url`, `--target`,
`--model`, `--serial-mode`, `--port`, `--no-hud`, `--mock`, `--once`,
`--loop-period`, `-v`.

## 6. Run

```bash
# 1. Phone: install "IP Webcam", start the server, note the IPv4 address.
# 2. Laptop:
python -m software.perception_node --mock --once                # smoke, no hardware
python -m software.perception_node --url http://192.168.1.50:8080/video
python -m software.perception_node --serial-mode bluetooth --port COM5
python -m software.perception_node --mock-camera --serial-mode bluetooth --port COM5 --once
python -m software.perception_node.bench COM5 F --listen 5      # drive rover, print telemetry
python -m software.perception_node.bench COM8 --listen 5        # listen-only (phone drives)
# 3. Flash firmware (Arduino IDE / arduino-cli):
#    esp32/bt_bridge/bt_bridge.ino      -> ESP32 DevKit V1
#    arduino/motion_safety/motion_safety.ino -> Arduino UNO R3
```

Keys: `q` / `ESC` quit (always sends `S`), `p` pause (holds `S`), `h` toggle HUD.
CTRL+C in headless mode is equivalent to `q`.

## 7. Failure behaviour (fail-safe matrix)

| Failure | Behaviour |
|---------|-----------|
| stream lost / frozen | `S` immediately, HUD shows `stream LOST` |
| target leaves frame | `S` |
| target too close (area) | `S` regardless of zone |
| serial port down at start | node keeps running, retries with backoff, HUD shows `serial RETRY` |
| serial write fails | link marked down, port closed, reconnect attempted |
| detector fails to load | `startup()` returns False â€” the loop never runs |
| BT client disconnects | ESP32 relays nothing; Arduino watchdog stops within 3 s |
| ultrasonic < 15 cm + `F` | Arduino overrides to stop + `ALERT:OBSTACLE` |
| malformed serial chunk | Arduino stops + `STATUS:ERROR` |

## 8. Tests

```bash
python -m pytest tests/test_perception_node.py tests/test_two_tier_firmware.py -q
python -m pytest tests -q
```

* `tests/test_perception_node.py` â€” zone geometry, area policy, URL/port
  validation, `SerialLink` (mock, open failure, write failure), HUD, node loop
  (heartbeat, stream loss, target filtering, shutdown stop), CLI smoke.
* `tests/test_two_tier_firmware.py` â€” source contracts that pin the spec:
  device name `AI_Rover_Control`, GPIO17, D4 link / D2-D3 HC-SR04 / D5-D10
  TB6612FNG pin map, 9600 baud on
  both sides, 15 cm threshold synced to YAML, forward-only override, invalid
  echo blocks forward, non-blocking loop/ultrasonic, boot STOP.

## 9. Limits

One-way link (no telemetry back to the laptop â€” read the Arduino Serial
Monitor instead), monocular sizeâ‰ˆproximity heuristic, HC-SR04 narrow FOV, no
localisation. Proof-of-concept, not collision-free.
