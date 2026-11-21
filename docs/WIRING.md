# Wiring map and power topology

Everything below matches the firmware exactly. If you change a pin, change it in
`firmware/libraries/AIRoverCore/src/pins.h` and the contract tests will tell you
what else must follow.

Builds supported from the same source:

| | **Bench build** (default) | **Production build** | **Encoder build** |
|---|---|---|---|
| Drive enable | TB6612 `STBY` on 5 V | 555 missing-pulse interlock | 555 + encoders |
| E-stop | none | 2-pole NC switch on `A1` | same |
| Battery sense | none | 100k/47k on `A0` | same |
| Closed-loop speed | off | off | on (`D2`/`D3`) |
| Rear sensor | optional (`D2`/`D3`) | optional | not possible (pins shared) |
| Compile | default | `make flash-prod-uno` | `make flash-encoders` |

---

## 1. Arduino Uno R3 pin map

| Function | Pin | Notes |
|---|---|---|
| Left PWM | **D5** | `PWMA`, ~976 Hz |
| Left direction | **D6 / D7** | `AIN1` / `AIN2` (AIN2 is left of AIN1) |
| Right direction | **D8 / D10** | `BIN1` / `BIN2` |
| Right PWM | **D9** | `PWMB`, far right of the module row |
| Front sonar | **D11 / D12** | `TRIG` / `ECHO` |
| ESP32 link RX | **D4** | ← ESP32 `GPIO17`, 9600 8N1 |
| ESP32 link TX | **A2** | → ESP32 `GPIO16` through a divider (telemetry) |
| Heartbeat | **A5** | 1 kHz square wave → 555 → `STBY` + ESP32 `GPIO13` |
| Wheel encoder L | **D2** | INT0, optional (mutually exclusive with the rear sonar) |
| Wheel encoder R | **D3** | INT1, optional |
| Rear sonar | **D2 / D3** | `TRIG` / `ECHO`, optional (same pins as the encoders) |
| Status LED | **D13** | onboard |
| Battery sense | **A0** | 100k / 47k divider (production) |
| E-stop sense | **A1** | NC contact to GND, `INPUT_PULLUP` (production) |
| Fault out | **A4** | active LOW → ESP32 `GPIO14` |
| Spare | **A3** | free |

> ⚠️ `D2`/`D3` are the Uno's only external-interrupt pins, and SoftwareSerial
> already owns the pin-change vectors. That is why the encoders and the rear
> sonar share those pins and the firmware refuses to build with both enabled.

> ⚠️ `A5` must **never** be wired straight to `STBY`. It is a 1 kHz square
> wave: connected directly it chops the H-bridge and the motors buzz without
> torque. It goes through the 555 interlock.

---

## 2. Arduino Uno R3 → TB6612FNG

The production module's silkscreen is unusual — **AIN2 sits left of AIN1** and
**PWMB is at the far right of the bottom row**. Trust the physical header.

### Top row (left → right)

| Pin | Silkscreen | Connect to | Notes |
|---|---|---|---|
| 1 | `VM` | E-stop → battery + through switch + 3 A fuse | 7.4 V nominal |
| 2 | `VCC` | Uno `5V` | logic supply |
| 3 | `GND` | **star ground** | battery −, Uno, ESP32 |
| 4 | `AO1` | left motor tab | polarity decides forward |
| 5 | `AO2` | left motor tab | |
| 6 | `BO1` | right motor tab | |
| 7 | `BO2` | right motor tab | |

### Bottom row (left → right)

| Pin | Silkscreen | Connect to | Constant |
|---|---|---|---|
| 1 | `PWMA` | **D5** | `kPwma` |
| 2 | `AIN2` ⚠ | **D7** | `kAin2` |
| 3 | `AIN1` ⚠ | **D6** | `kAin1` |
| 4 | `STBY` | 555 output / 5 V (bench) | — |
| 5 | `BIN1` | **D8** | `kBin1` |
| 6 | `BIN2` | **D10** | `kBin2` |
| 7 | `PWMB` ⚠ | **D9** | `kPwmb` |

| Motion | AIN1 | AIN2 | BIN1 | BIN2 | PWM |
|---|---|---|---|---|---|
| Forward `F` | H | L | H | L | 60–255 |
| Reverse `B` | L | H | L | H | 60–255 |
| Pivot left `L` | L | H | H | L | 60–255 |
| Pivot right `R` | H | L | L | H | 60–255 |
| Stop `S` | L | L | L | L | 0 (coast) |

Wrong wheel direction? Swap that motor's two tabs, never the logic pins.

---

## 3. Front HC-SR04

| Sensor pin | Connect to |
|---|---|
| `VCC` | Uno `5V` (header pin) |
| `TRIG` | **D11** |
| `ECHO` | **D12** |
| `GND` | star ground |

Echo timeout or disconnection reports `DIST: -1`, which blocks forward motion.

---

## 4. ESP32 DevKit V1 ⇄ Uno

### Commands (ESP32 → Uno)

| ESP32 | Uno | Direction |
|---|---|---|
| `GPIO17` (TX2) | **D4** (SoftwareSerial RX) | ESP32 → Uno |
| `GND` | star ground | reference |

Frames are CRC-8 protected.

### Telemetry + health (Uno → ESP32)

All three are 5 V outputs and need a divider into the ESP32:

| Uno | Divider | ESP32 | Purpose |
|---|---|---|---|
| `A2` (link TX) | 10k / 20k | `GPIO16` (RX2) | `T,…*HH` telemetry @ 5 Hz |
| `A5` (heartbeat) | 10k / 20k | `GPIO13` | 1 kHz “MCU alive” |
| `A4` (fault) | 10k / 20k | `GPIO14` | active LOW fault latch |

```
A2 ──10k──┬── GPIO16
          │
         20k
          │
         GND
```
(same for A5→GPIO13 and A4→GPIO14)

Advisory only: with those wires missing, `/status` reports `"wired": false` and
the pad shows `UNO --`. Commands still work.

The ESP32 also accepts **OTA** updates (see `docs/API.md`), so the USB cable is
only needed for the very first flash.

---

## 5. E-stop (production)

Use a **2-pole normally-closed** mushroom switch:

* **Pole 1**: pack → switch → fuse → **E-stop pole 1** → TB6612 `VM`.
* **Pole 2**: between `A1` and `GND`.

Pressed: VM is physically cut **and** `A1` opens → `INPUT_PULLUP` reads HIGH →
`STATE: FAULT / FAULT: ESTOP`. Released: VM returns, but the rover stays
stopped until a new command. A broken E-stop wire also reads HIGH (fail-safe).

The logic rail (buck) must be tapped **before** the E-stop so the rover can
still report the fault.

Bench without a switch: jumper `A1`→`GND` **only if** built with
`-DREQUIRE_ESTOP=0` (the default build ignores A1).

---

## 6. Heartbeat → STBY interlock (production)

The Uno outputs a 1 kHz square wave on `A5`. A 555 missing-pulse detector turns
it into a DC enable for `STBY`; when the pulses stop (hang, reset, dead MCU),
`STBY` falls within ~110 ms.

```
        +5V
         │
        100k
         │
 A5 ─10nF─┤TRIG            NE555 (or TLC555)
         │                  THR ──100k── +5V
        GND                  │
                           1µF
                             │
                            GND        OUT ──► TB6612 STBY
```

* `R = 100k`, `C = 1µF` → 1.1 × R × C ≈ **110 ms**.
* Power the 555 from the 5 V logic rail; `RESET` → 5 V, `CONT` → 10 nF to GND.
* Tap `A5` **before** the 10 nF coupling capacitor for the ESP32 divider.

The AVR watchdog alone is not enough: a reset leaves the TB6612 inputs floating
while `STBY` is high. The interlock removes drive enable independently of
software.

Bench without the 555: keep `STBY` on 5 V. You still get the 250 ms AVR
watchdog and the 500 ms link watchdog, but not the hardware output disable.

---

## 7. Battery sense (production)

2S pack (8.4 V full) → **100k** → `A0` → **47k** → GND.

* 8.4 V → 2.686 V at the pin; 6.4 V → 2.046 V.
* Motion is cut below **6.400 V** and only recovers above **6.800 V**
  (`STATE: FAULT / FAULT: BATTLOW`).

Calibrate against a multimeter by adjusting `kBatteryDividerRatio` in `pins.h`
if it is off by more than ~3 %.

A **2S BMS with over-discharge protection** is strongly recommended — the
firmware cutoff protects the rover, not the cells from a deep discharge while
switched off.

---

## 8. Rear HC-SR04 (optional, not with encoders)

| Sensor pin | Connect to |
|---|---|
| `VCC` | Uno `5V` |
| `TRIG` | **D2** |
| `ECHO` | **D3** |
| `GND` | star ground |

Enable with `-DREAR_SONAR=1`. Reverse is refused below 15 cm; once a rear sensor
has been seen, losing it also blocks reverse. `ENCODERS=1` and `REAR_SONAR=1`
together fail the build on purpose.

---

## 9. Wheel encoders (optional, closed loop)

Single-channel is enough: the firmware measures speed from the pulse rate and
takes the direction from the motor command. If your motors have A/B outputs,
use channel **A** only.

| Encoder | Uno | Notes |
|---|---|---|
| Left `A` | **D2** | INT0, `INPUT_PULLUP` |
| Right `A` | **D3** | INT1, `INPUT_PULLUP` |
| `VCC` | Uno `5V` | most TT encoders are 3.3–5 V |
| `GND` | star ground | |

Build and flash:

```bash
make flash-encoders PORT_UNO=/dev/ttyACM0     # production + ENCODERS
```

The boot banner shows `encoders=closed-loop` and an `ODO:` calibration line.
Every 500 ms the USB log prints:

```
[UNO] DRIVE: vL=318 vR=316 mm/s | odo=412mm x=398 y=12 th=3deg
```

### Calibration (do this once)

1. Mark a wheel and a fixed point on the chassis.
2. Push/roll the rover **exactly one wheel revolution** by hand.
3. Read `odo`. It should equal `kWheelCircumferenceMm` (default 204 mm for a
   65 mm wheel). If it reads 190, set
   `kWheelCircumferenceMm = 204 × 204/190`.
4. Roll **1.00 m** on the floor and check `odo` again; adjust the same constant
   by the ratio (this also absorbs tyre slip).
5. Measure the track (centre-to-centre between wheels) and set `kTrackMm`
   (default 150 mm).
6. If your encoder has a different slot count, set `kEncoderCpr` —
   20 slots × 1:48 gearbox = 960 counts per output revolution.

Verify a spin: command `L120` and check `th` changes while `x`/`y` stay put.
Then drive forward 1 m and check `x ≈ 1000`, `th ≈ 0`.

### Stall protection

If a wheel is commanded above ~60 mm/s and does not move for **1 s**, the
firmware latches `FAULT: STALL` and cuts the motors. Send `S` to acknowledge,
then drive again. This is what protects the gearboxes and the driver when the
rover wedges itself under furniture.

### What changes with encoders

* `F180` now means “~215 mm/s”, not “55 % duty cycle”, so speed stays constant
  as the pack drains.
* `/status` publishes wheel speeds, x/y/heading and odometer.
* Pivots and straight lines become repeatable enough to script a demo path.

---

## 10. Power distribution (star ground)

```
 2S 18650 pack (7.4 V nom / 8.4 V full)
        │
   SPST master switch
        │
   3 A fast fuse
        │
        ├──────────────► E-stop pole 1 ──► TB6612 VM   (≥20 AWG, direct)
        │
        └──► LM2596 buck (set 5.0 V) ──┬──► Uno 5V
                                       ├──► ESP32 5V
                                       ├──► HC-SR04 VCC
                                       └──► 555 VCC
     (buck tapped BEFORE the E-stop so logic survives an E-stop)

 Battery − ──► STAR GROUND (single bolt/terminal)
                 ├── TB6612 GND
                 ├── LM2596 GND
                 ├── Uno GND
                 ├── ESP32 GND
                 ├── HC-SR04 GND / encoder GND
                 └── 555 GND
```

Rules from the two short-circuit incidents:

1. No motor current through a solderless breadboard.
2. No taped inline splices on power conductors.
3. Remove the cells before soldering or adjusting anything.
4. Measure the buck output at **5.0 V before** connecting the boards.
5. One star ground; motor return current must not share the logic return.
6. 3 A fuse close to the pack positive terminal.

> **USB + battery:** avoid feeding both from different sources at once.

---

## 11. Harness checklist before the first power-on

- [ ] Continuity from battery − to every GND pad, and **nowhere else**.
- [ ] No continuity between VM and GND with the switch open (incident #1).
- [ ] LM2596 output 5.0 V ± 0.1 V with no load.
- [ ] `STBY` high with the MCU running, low ~110 ms after the heartbeat stops.
- [ ] E-stop pole 1 opens VM; pole 2 reads HIGH on `A1` when pressed.
- [ ] `A0` reads 2.0–2.7 V with the pack connected.
- [ ] All three Uno→ESP32 dividers read ≤ 3.3 V (A2, A5, A4).
- [ ] Encoders: `D2`/`D3` pull high, and `odo` moves when you turn a wheel.
- [ ] Motor tabs soldered, heat-shrunk, tug-tested.
- [ ] Battery cells **removed** while doing all of the above.
- [ ] Wheels off the ground for the first flash (`docs/BRINGUP.md`).
