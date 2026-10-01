# 31. Bill of Materials (BOM) & Component Sourcing

**Document ID:** DOC-BOM-001  
**Project:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Status:** Baseline Educational Estimate — `[PRICE TO VERIFY]`  
**Companion Files:** [`BOM.csv`](../BOM.csv) | [`BOM.xlsx`](../BOM.xlsx)

---

## 1. Executive Cost Summary

- **Total Prototype Estimated Cost:** **$62.90 USD**
- **Existing Lab Assets Value:** **$41.40 USD**
- **Incremental Acquisition Cost (Need to Buy):** **$21.50 USD**
- **Target Category:** Low-cost undergraduate robotics proof-of-concept (< $60 USD).

> [!NOTE]
> All unit prices represent educational procurement benchmarks from common distributors (e.g., Adafruit, SparkFun, AliExpress, Digikey). Exact current retail pricing must be verified locally at the time of purchase (`[PRICE TO VERIFY]`).

---

## 2. Complete Component Sourcing Matrix

| # | Component | Qty | Specification | Purpose | Req. | Opt. | Status | Unit Price | Total Cost | Sourcing Notes |
| :-: | :--- | :-: | :--- | :--- | :-: | :-: | :-: | -: | -: | :--- |
| 1 | **Arduino UNO R3** | 1 | ATmega328P DIP, 16MHz, 5V, 32KB Flash, 2KB SRAM | Safety supervisor, motor PWM generation, ultrasonic watchdog | Yes | No | Existing | $8.50 | $8.50 | Verified in rover_controller.ino [VERIFIED IN CODE] |
| 2 | **ESP32-CAM AI-Thinker Module** | 1 | ESP32-D0WDQ6 (240MHz Dual-Core), 4MB PSRAM, Wi-Fi/BT | Edge camera capture, vision preprocessing, AI inference | Yes | No | Existing | $7.00 | $7.00 | Includes OV2640 camera sensor ribbon [VERIFIED IN CODE] |
| 3 | **OmniVision OV2640 Camera** | 1 | 2 Megapixel CMOS, DVP 8-bit interface, 66° FOV lens | Primary visual sensor for target detection & tracking | Yes | No | Existing | $3.50 | $3.50 | VGA/QVGA resolution configured [VERIFIED IN CODE] |
| 4 | **L298N Dual H-Bridge Driver** | 1 | Dual BJT Full-Bridge, 2A/channel, with 5V logic regulator | Drive left and right DC motors from battery rail | Yes | No | Existing | $3.20 | $3.20 | Internal ~2V drop; heatsink required [VERIFIED IN CODE] |
| 5 | **HC-SR04 Ultrasonic Sensor** | 1 | 40 kHz Acoustic Transducer, 2cm-400cm range, 5V | Forward safety barrier & emergency distance cutoff | Yes | No | Existing | $2.00 | $2.00 | 15cm emergency stop threshold [VERIFIED IN CODE] |
| 6 | **TT Gearbox DC Motors** | 2 | Yellow TT Dual-Shaft, 3V-6V DC, 1:48 Gear Ratio | Differential propulsion for left and right wheels | Yes | No | Existing | $2.50 | $5.00 | 0.1uF suppression capacitors required [ASSUMPTION] |
| 7 | **Robot Drive Wheels** | 2 | 65mm diameter, rubber tread tire on plastic rim | Ground traction and differential propulsion | Yes | No | Existing | $1.50 | $3.00 | Radius r = 32.5mm used in kinematics [ASSUMPTION] |
| 8 | **Front Ball Caster Wheel** | 1 | Omni-directional metal/nylon ball caster, height matched | Passive third point of ground support | Yes | No | Existing | $1.20 | $1.20 | Prevents chassis pitch dragging [ASSUMPTION] |
| 9 | **Robot Chassis Base Plate** | 1 | Laser-cut acrylic / aluminum 2WD plate (180mm x 220mm) | Mechanical structure holding all electronics and motors | Yes | No | Existing | $5.00 | $5.00 | Track width L = 180mm [VERIFIED IN CODE] |
| 10 | **Step-Down Buck Converter** | 1 | LM2596 / MP1584, DC 7V-24V to 5.0V Regulated, 3A max | Clean 5.0V logic rail isolating ESP32 and Arduino from motors | Yes | No | **Need to Buy** | $2.20 | $2.20 | Prevents motor voltage dips and micro reboots [DESIGN DECISION] |
| 11 | **2S 18650 Li-ion Battery Pack** | 1 | 7.4V nominal (8.4V max), 2600mAh, with internal BMS | Main portable DC energy storage | Yes | No | **Need to Buy** | $14.00 | $14.00 | Exact pack chemistry to confirm physically [PRICE TO VERIFY] |
| 12 | **18650 Battery Holder & Switch** | 1 | 2-Slot 18650 series tray with rocker switch and inline 3A fuse | Safe battery retention, master power switch, overcurrent fuse | Yes | No | **Need to Buy** | $2.50 | $2.50 | Essential laboratory safety feature [DESIGN DECISION] |
| 13 | **TowerPro SG90 Micro Servo** | 1 | 9g analog servo, 180° rotation, 4.8V-6V operating | Discrete panoramic scanning mechanism (0° to 315° sweep) | No | Yes | **Need to Buy** | $2.80 | $2.80 | Optional extension (Phase 19) [DESIGN DECISION] |
| 14 | **Prototyping Standoffs & Jumper Wires** | 1 | M3 nylon standoffs (20mm), 40-pin Dupont wires (M-M, M-F) | Component mounting and electrical interconnection | Yes | No | Existing | $3.00 | $3.00 | Standard hardware consumables |
| | **TOTAL** | | | | | | | | **$62.90** | *Formula: $\sum (Qty \times UnitPrice)$* |

---

## 3. Critical Sourcing Decisions

1. **No Level Shifter Required (Design Decision):**
   - The Arduino UNO runs at 5.0V TTL and the ESP32-CAM GPIO at 3.3V CMOS - but **there is no wired data link between them**.
   - The ESP32-CAM is connected to 5V and GND only; video leaves as Wi-Fi MJPEG (`http://<ip>:81/stream`) and commands reach the Arduino over USB serial from the laptop (9600 baud on D0/D1).
   - A level shifter would only be needed if a direct ESP32-to-Arduino UART wire were added; if that ever happens, fit a BSS138 shifter (or 1k/2k divider) first and never jumper 5V TX straight into a 3.3V GPIO.

2. **Power Decoupling & Brownout Prevention [CRITICAL]:**
   - DC motors create substantial inductive transients and current draw spikes (up to 1.2A per motor during stall).
   - Directly powering the Arduino 5V or ESP32 from the L298N on-board linear regulator during motor transients will cause severe voltage dips, triggering ESP32 brownout detector resets.
   - An independent high-efficiency buck converter (LM2596 / MP1584) stepped down to 5.0V is dedicated exclusively to the logic controllers, while the 7.4V battery rail feeds the L298N power terminal directly.

3. **Drive Motors & Chassis Geometry:**
   - 1:48 gear ratio TT yellow gear motors provide adequate torque for smooth indoor surface navigation (~0.35 m/s at 6.0V).
   - Wheel radius $r = 32.5$ mm and track width $L = 180$ mm match the kinematic parameters in `config.yaml`.
