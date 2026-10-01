# 20. Power Architecture & Electrical Decoupling

**Document ID:** DOC-HW-004  
**Project:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Status:** Verified Electrical Power Budget & Distribution Design  
**Companion Diagram:** [`figures/04_power_architecture.png`](../figures/04_power_architecture.png)

---

## 1. Power Supply Overview & Decoupling Strategy

The rover employs a **split-rail decoupled power architecture** to isolate sensitive digital processing logic from inductive motor switching noise.

```
+---------------------------------------------------------------------------------+
|                                 POWER RAIL TOPOLOGY                             |
|                                                                                 |
|  [ 2S Li-ion Battery (7.4V - 8.4V) ]                                            |
|       |                                                                         |
|       +--> [ Main Switch & 3A Fuse ]                                            |
|                 |                                                               |
|                 +--> [ High-Current Motor Rail: 7.4V Unregulated ]              |
|                 |         |                                                     |
|                 |         +--> L298N 12V Terminal                               |
|                 |                   |                                           |
|                 |                   +--> Left & Right DC TT Motors              |
|                 |                                                               |
|                 +--> [ High-Efficiency Step-Down Buck Converter (5.0V / 3A) ]   |
|                           |                                                     |
|                           +--> ESP32-CAM 5V Input (Onboard LDO -> 3.3V Core)    |
|                           +--> Arduino UNO 5V Pin (Bypasses Onboard Regulator)  |
|                           +--> HC-SR04 Ultrasonic Sensor VCC                    |
|                                                                                 |
|  COMMON STAR GROUND (0V): Battery (-) == Buck (-) == Arduino GND == ESP32 GND   |
+---------------------------------------------------------------------------------+
```

---

## 2. Power Consumption & Energy Budget

| Subsystem / Component | Operating Voltage | Quiescent / Idle Current | Typical Operating Current | Peak / Stall Current | Power Consumption (Typical) | Power Consumption (Peak) | Sourcing Rail |
| :--- | :---: | :-: | :-: | :-: | :-: | :-: | :--- |
| **Arduino UNO R3** | 5.0 V | 35 mA | 45 mA | 50 mA | 0.225 W | 0.250 W | Regulated 5.0V Logic |
| **ESP32-CAM (Wi-Fi + Capture)**| 5.0 V | 110 mA | 180 mA | 310 mA (Wi-Fi burst)| 0.900 W | 1.550 W | Regulated 5.0V Logic |
| **HC-SR04 Ultrasonic** | 5.0 V | 2 mA | 15 mA | 20 mA (Acoustic burst)| 0.075 W | 0.100 W | Regulated 5.0V Logic |
| **L298N Logic Stage** | 5.0 V | 15 mA | 25 mA | 35 mA | 0.125 W | 0.175 W | Regulated 5.0V Logic |
| **Dual TT DC Motors** | 7.4 V | 0 mA | 300 mA (Both wheels)| 2200 mA (Dual Stall) | 2.220 W | 16.280 W | Unregulated 7.4V Motor Rail |
| **Buck Converter Quiescent** | 7.4 V | 8 mA | 12 mA | 15 mA | 0.089 W | 0.111 W | Unregulated 7.4V Motor Rail |
| **SYSTEM TOTAL** | — | **170 mA** | **577 mA** | **2940 mA (Peak Stall)**| **3.634 W** | **18.466 W** | Battery Pack |

---

## 3. Battery Endurance & Runtime Calculations

Assuming a standard **2S 18650 Li-ion Battery Pack** with **2600 mAh capacity (19.24 Wh energy)**:

- **Continuous Nominal Driving Runtime:**
  $$\text{Runtime}_{nominal} = \frac{2600 \text{ mAh}}{577 \text{ mA}} \approx 4.50 \text{ hours} \quad (\text{Derated to 70\% safety margin } \approx 3.15 \text{ hours})$$

- **Aggressive Continuous Steering / High-PWM Runtime:**
  $$\text{Runtime}_{heavy} = \frac{2600 \text{ mAh}}{1200 \text{ mA}} \approx 2.16 \text{ hours} \quad (\text{Derated to 70\% } \approx 1.51 \text{ hours})$$

- **Worst-Case Stall Cutoff Protection:**
  The inline **3.0A fast-acting fuse** protects the Li-ion cell protection circuit from over-discharge or thermal runaway in the event of mechanical motor jamming.
