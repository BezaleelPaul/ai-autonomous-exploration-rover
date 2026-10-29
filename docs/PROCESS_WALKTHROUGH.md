# 1. What This Project Is

An **AI visual smart rover**: a small differential-drive robot that sees a target
with a camera, decides where to drive, and moves — while two independent safety
layers can stop it at any moment. Three computers share the work:

| Unit | Job | Talks to the others via |
|---|---|---|
| **ESP32-CAM** (AI-Thinker) | Streams live video over Wi-Fi | Wi-Fi MJPEG only (`http://<ip>:81/stream`) |
| **Laptop (host software)** | Runs the AI detector, decision engine, safety manager | Video over Wi-Fi; commands over USB serial |
| **Arduino UNO R3** | Validates commands, drives motors, reads the ultrasonic sensor, enforces watchdogs | USB serial from the laptop (9600 baud) |

> [!NOTE]
> There is **no wire between the ESP32 and the Arduino**. The ESP32 is connected
> to 5V and GND only; video travels over Wi-Fi and commands travel
> laptop → USB → Arduino. This is enforced by `tests/test_docs_data_links.py`.

![Figure: 01_system_architecture.png]

---

# 2. The Whole Process, Start to Finish

Every frame of video follows the same five-step loop, 5–10 times per second:

1. **SEE** — the ESP32-CAM captures a frame (OV2640) and serves it as MJPEG.
   The laptop pulls the stream from `software/camera/`.
2. **UNDERSTAND** — `software/ai/detector.py` runs the object detector and
   returns a bounding box; the box centre is compared with the frame centre to
   produce a heading error `e = x_target - x_center`.
3. **DECIDE** — `software/control/steering.py` turns the error into a
   zone (left / centre / right), and `software/safety/safety_manager.py` gets
   the **final veto**: camera stale, serial unhealthy, obstacle too close, or an
   invalid command all collapse to `S` (stop).
4. **ACT** — the approved one-letter command (`F`, `B`, `L`, `R`, `S`) is sent
   over USB serial (`software/hardware/arduino_serial.py`).
5. **PROTECT** — the Arduino re-checks everything in hardware: 3 s without a
   valid packet → stop; HC-SR04 under 15 cm → stop; only then are the L298N
   bridge inputs raised.

![Figure: 02_data_flow.png]

---

# 3. What You Need on the Bench

| # | Part | Qty | Why |
|---|---|---|---|
| 1 | Arduino UNO R3 | 1 | Real-time motor control + safety watchdog |
| 2 | ESP32-CAM (AI-Thinker, OV2640) | 1 | Camera + Wi-Fi video |
| 3 | L298N dual H-bridge driver | 1 | Drives the two motors |
| 4 | TT gear motors, 1:48, with wheels | 2 | Differential drive |
| 5 | HC-SR04 ultrasonic sensor | 1 | Independent 15 cm obstacle cutoff |
| 6 | 2S 18650 battery pack (7.4 V) + holder, switch, 3 A fuse | 1 | Energy for everything |
| 7 | LM2596 buck converter | 1 | Clean 5 V logic rail, separate from motors |
| 8 | Jumper wires, standoffs | 1 set | Wiring |

Prototype BOM total: **$62.90** ($21.50 still to buy). Full list:
`docs/31_BILL_OF_MATERIALS.md`. No logic level shifter is needed — see §4.

---

# 4. How Everything Is Connected

## 4.1 Power chain (follow it in this order)

1. **Battery (+)** → switch/fuse → splits to two branches:
   - **Motor branch:** straight into the **L298N 12 V terminal** (up to 1.2 A
     per motor — never through the Arduino).
   - **Logic branch:** **LM2596 buck IN+** → regulated **5 V OUT+** →
     Arduino `5V`, ESP32-CAM `5V`, HC-SR04 `VCC`.
2. **Battery (−)**, buck `IN−`/`OUT−`, L298N `GND`, Arduino `GND`, ESP32 `GND`,
   HC-SR04 `GND` all meet at **one star-ground lug**.

![Figure: 04_power_architecture.png]

## 4.2 Signal chain (the complete wiring schedule)

| From | Pin | To | Pin | Wire | Carries |
|---|---|---|---|---|---|
| Arduino | D5 (PWM) | L298N | ENA (jumper off) | Purple | Left motor speed |
| Arduino | D6 | L298N | IN1 | Orange | Left forward |
| Arduino | D7 | L298N | IN2 | Orange | Left reverse |
| Arduino | D8 | L298N | IN3 | Orange | Right forward |
| Arduino | D9 | L298N | IN4 | Orange | Right reverse |
| Arduino | D10 (PWM) | L298N | ENB (jumper off) | Purple | Right motor speed |
| Arduino | D11 | HC-SR04 | TRIG | White | 10 µs trigger |
| HC-SR04 | ECHO | Arduino | D12 | White | Echo pulse width |
| L298N | OUT1/OUT2 | Left motor | + / − | Grey | Motor drive |
| L298N | OUT3/OUT4 | Right motor | + / − | Grey | Motor drive |
| Laptop | USB | Arduino | D0 (RX) / D1 (TX) | USB cable | Commands + telemetry, 9600 baud |
| ESP32-CAM | 5V, GND | Buck 5 V rail | OUT+, star ground | Blue / Black | Power **only** |

> [!WARNING]
> **Never wire these:** Arduino **D0/D1** to anything except the USB cable
> (they are the bootloader serial pins), and **no wire at all** between the
> ESP32's GPIO 1/3 and the Arduino. If you ever add a wired UART between the
> boards, fit a 3.3 V ↔ 5 V level shifter first — 5 V on an ESP32 GPIO
> destroys it.

![Figure: wiring_schemdraw.png]

![Figure: circuit_diagram.png]

---

# 5. The Three Pieces of Software

| Piece | Location | Runs on | What it does |
|---|---|---|---|
| Host application | `software/` (entry: `main.py`) | Laptop | Camera, AI, decisions, safety, serial, dashboard |
| Camera firmware | `esp32/camera_stream/camera_stream.ino` | ESP32-CAM | Wi-Fi + MJPEG `/stream`, auto-reconnect |
| Motion firmware | `arduino/rover_controller/rover_controller.ino` | Arduino UNO | Command validation, PWM, watchdogs, ultrasonic, telemetry |

Configuration lives in `config/config.yaml` (ports, thresholds, model) and
`config/thresholds.yaml` (safety numbers). Both are validated at startup by
`software/utils/config_loader.py`.

---

# 6. The Serial Protocol (laptop ↔ Arduino)

One ASCII character per command, optional speed suffix; telemetry comes back
every 200 ms regardless of commands.

| Direction | Example | Meaning |
|---|---|---|
| → Arduino | `F` / `B` / `L` / `R` / `S` | Forward, back, left, right, stop |
| → Arduino | `F180` | Forward at PWM 180 (speed suffix form) |
| ← Arduino | `DIST:12.4` | Ultrasonic distance in cm |
| ← Arduino | `STATUS:OK` / `STOP` / `ERROR` | Current state machine status |
| ← Arduino | `TICKS:14,17` | Wheel-encoder ticks (left, right) |

Rules the firmware enforces on every packet: unknown character → `STATUS:ERROR`
and no actuation; no valid packet for **3000 ms** → motors released; distance
under **15 cm** → translation refused. The host mirrors the same rules in
`software/safety/safety_manager.py` before anything is sent.

![Figure: 14_communication_protocol.png]

---

# 7. Safety: Two Independent Layers

| Priority | Check | Where it runs | Action |
|---|---|---|---|
| 1 | Emergency obstacle < 15 cm | Arduino firmware | Refuse forward motion |
| 2 | Comm watchdog > 3000 ms | Arduino firmware | Release the H-bridge |
| 3 | Invalid / unknown command | Arduino firmware | `STATUS:ERROR`, no actuation |
| 4 | Camera frame stale > 3 s | Host `safety_manager` | Send `S` |
| 5 | Serial link unhealthy | Host `safety_manager` | Send `S` |
| 6 | Manual-mode exit / crash | Host | `safe_stop()` sends `S` |

Both layers default to **stop** — there is no state in which silence means "keep
driving".

![Figure: 08_safety_hierarchy.png]

---

# 8. How to Run It

```bash
# 1. Python env (3.12)
pip install -r requirements.txt

# 2. Firmware (COM port from Device Manager)
arduino-cli compile --fqbn arduino:avr:uno arduino/rover_controller
arduino-cli upload  --fqbn arduino:avr:uno -p COM3 arduino/rover_controller
# ESP32: select "AI Thinker ESP32-CAM" as the board, same idea

# 3. Host application
python -m software.main                # real camera + real Arduino
python -m software.main --mock         # no hardware at all (safe to demo)

# 4. Verification (no hardware needed)
python -m pytest tests -q              # 311 passed
python -m ruff check software tests
python tools/validate_docs.py
```

Simulation without hardware (Wokwi):

```bash
python tools/build_wokwi_firmware.py    # arduino-cli -> build/*.hex,elf
python tools/run_wokwi_sim.py           # lint + simulate, exit 0
python tools/run_wokwi_sim.py --scenario scenarios/safety.yaml
```

---

# 9. How It Was Verified

| Gate | Result |
|---|---|
| Unit + integration tests | **311 passed / 0 failed** (`pytest tests -q`) |
| Static analysis | **All checks passed** (`ruff check software tests`) |
| Documentation integrity | **PASS**, 0 broken links (`tools/validate_docs.py`) |
| Arduino UNO build | 5526 B flash (17%) |
| ESP32 build | 1026129 B (32%) |
| Wokwi simulator lint | `✓ No issues found` |
| Wokwi live runs (3) | **PASS** — boot-STOP, protocol rejection, 3.6 s watchdog, 10 cm obstacle gate |
| Detector speed | yolo11s p50 119–211 ms @ 320 px, model load 0.4 s |
| Realtime budget | Green at ≤ 60% CPU load (`test_redteam_h4_realtime`) |
| Streaming regression harness | 8550 rows, 10 invariants PASS |

Detailed evidence: `TEST_REPORT.md` (per-test case results) and
`REGRESSION_REPORT.md` (before/after gates, §10–§11 session logs).

---

# 10. Status: What Is Done and What Is Not

**Done (evidence-backed):** design, firmware, host software, safety chain,
documentation set, unit/integration tests, simulation.

**Still open — hardware gate:** the rover has never been powered. Battery
voltage, buck rail under load, motor stall current vs the L298N, a real COM
port, a live ESP32 stream, and detection on the real camera all remain
**HARDWARE REQUIRED / NOT TESTED**. Until those measurements exist, do not
claim 100% (README §18).

---

# 11. Where Everything Lives

| Path | Contents |
|---|---|
| `software/` | Host application (camera, AI, navigation, safety, serial, dashboard) |
| `arduino/rover_controller/` | Motion + safety firmware |
| `esp32/camera_stream/` | Camera + Wi-Fi streaming firmware |
| `config/` | `config.yaml`, `thresholds.yaml` |
| `docs/` | 35 design documents (01–35) + guides |
| `tests/` | 311 tests, runnable without hardware |
| `tools/` | Doc/figure/PDF generators, Wokwi build & simulation, validators |
| `diagrams/wokwi/` | Wokwi project, scenarios |
| `figures/` | 300 DPI diagrams used in the PDFs |
| `reports/` | Final report, wiring PDF, this walkthrough |
| `BILL_OF_MATERIALS.md`, `BOM.csv` | Parts list and costs |
