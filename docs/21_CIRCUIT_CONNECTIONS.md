# 21. Hardware Circuit Connections & Wiring Specification

**Document ID:** DOC-HW-003  
**Project:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Status:** Build-Ready Electrical Specification  
**Companion Diagrams:** [`figures/circuit_diagram.svg`](../figures/circuit_diagram.svg) | [`figures/circuit_diagram.png`](../figures/circuit_diagram.png) | [`figures/wiring_schemdraw.png`](../figures/wiring_schemdraw.png) (regenerate: `python tools/generate_wiring_schemdraw.py`)  
**Wiring & Breadboard Guide:** [`reports/AI_Rover_Wiring_and_Breadboard.pdf`](../reports/AI_Rover_Wiring_and_Breadboard.pdf)  
**Wokwi simulation:** [`diagrams/wokwi/`](../diagrams/wokwi/) — build with `python tools/build_wokwi_firmware.py`, run with `python tools/run_wokwi_sim.py`

---

## 1. Power Distribution Circuitry

```
+---------------------------------------------------------------------------------+
|                                 POWER ARCHITECTURE                              |
|                                                                                 |
|  [ 2S Li-ion Battery (7.4V) ] --+--> [ L298N 12V Terminal ]                     |
|                                 |          |                                    |
|                                 |          +--> [ Left & Right DC Motors ]      |
|                                 |                                               |
|                                 +--> [ LM2596 Buck (5V) ] --+--> [ Arduino 5V ] |
|                                                             +--> [ ESP32 5V ]   |
|                                                             +--> [ HC-SR04 VCC ]|
+---------------------------------------------------------------------------------+
```

> [!WARNING]
> **ELECTRICAL DESIGN DECISION & SAFETY ISOLATION:**  
> 1. NEVER power the DC drive motors from the Arduino 5V pin or ESP32 VCC pin. The inductive back-EMF and stall current (up to 1.2A per motor) will destroy the onboard linear regulators or trigger immediate brownout resets.
> 2. The ESP32-CAM is **power-only (5V + GND)**: there is NO wired data link to the Arduino. Video leaves it as Wi-Fi MJPEG (`http://<ip>:81/stream`) and commands reach the Arduino over USB serial from the laptop, so D0/D1 must stay unwired. NEVER jumper Arduino TX (5V) to a 3.3V ESP32 GPIO; if a wired UART is ever added, level-shift first.
> 3. ALL grounds (Battery Negative, Buck Converter Ground, Arduino Ground, ESP32 Ground, and L298N Ground) MUST converge at a single common star ground point.

---

## 2. Inter-Module Point-to-Point Wiring Schedule

| From Device / Module | Pin / Terminal | To Device / Module | Pin / Terminal | Wire Color Standard | Signal Type | Electrical Specification |
| :--- | :--- | :--- | :--- | :---: | :--- | :--- |
| **Battery Pack (2S)** | Positive (+) | **Power Switch / Fuse** | Input Terminal | Red | Power Rail | 7.4V - 8.4V DC, max 3A fuse |
| **Power Switch** | Output Terminal | **Buck Converter** | IN+ | Red | Power Rail | 7.4V Unregulated |
| **Power Switch** | Output Terminal | **L298N Driver** | 12V Terminal Block | Red | Motor Power | 7.4V High Current |
| **Battery Pack (2S)** | Negative (-) | **Common Star Junction** | Terminal Lug | Black | Ground Rail | 0V Reference |
| **Buck Converter** | IN- | **Common Star Junction** | Terminal Lug | Black | Ground Rail | 0V Reference |
| **Buck Converter** | OUT+ | **Arduino UNO** | 5V Pin | Blue | Logic Power | 5.0V Regulated (±2%) |
| **Buck Converter** | OUT+ | **ESP32-CAM** | 5V Pin | Blue | Logic Power | 5.0V Regulated (±2%) |
| **Buck Converter** | OUT+ | **HC-SR04** | VCC Pin | Blue | Logic Power | 5.0V Regulated |
| **Buck Converter** | OUT- | **Common Star Junction** | Terminal Lug | Black | Ground Rail | 0V Reference |
| **Arduino UNO** | Pin 5 (PWM) | **L298N Driver** | ENA (Jumper Off) | Purple | Speed PWM | 0 - 255 Duty Cycle (~976 Hz) |
| **Arduino UNO** | Pin 6 (Digital) | **L298N Driver** | IN1 Terminal | Orange | Direction DO | 5V HIGH = Left Forward |
| **Arduino UNO** | Pin 7 (Digital) | **L298N Driver** | IN2 Terminal | Orange | Direction DO | 5V HIGH = Left Reverse |
| **Arduino UNO** | Pin 8 (Digital) | **L298N Driver** | IN3 Terminal | Orange | Direction DO | 5V HIGH = Right Forward |
| **Arduino UNO** | Pin 9 (Digital) | **L298N Driver** | IN4 Terminal | Orange | Direction DO | 5V HIGH = Right Reverse |
| **Arduino UNO** | Pin 10 (PWM) | **L298N Driver** | ENB (Jumper Off) | Purple | Speed PWM | 0 - 255 Duty Cycle (~490 Hz) |
| **L298N Driver** | OUT1 / OUT2 | **Left TT Motor** | Motor Terminals | Grey | Actuator Drive | Dual BJT H-Bridge Switched DC |
| **L298N Driver** | OUT3 / OUT4 | **Right TT Motor** | Motor Terminals | Grey | Actuator Drive | Dual BJT H-Bridge Switched DC |
| **Arduino UNO** | Pin 11 (Digital) | **HC-SR04** | TRIG Pin | White | Acoustic Pulse | 10 µs High Trigger |
| **HC-SR04** | ECHO Pin | **Arduino UNO** | Pin 12 (Digital) | White | Echo Return | 5V TTL Pulse Width |
| **HC-SR04** | GND Pin | **Common Star Junction** | Terminal Lug | Black | Ground Rail | 0V Reference |
| **L298N Driver** | GND Terminal | **Common Star Junction** | Terminal Lug | Black | Ground Rail | 0V Reference |
| **Arduino UNO** | GND Pin | **Common Star Junction** | Terminal Lug | Black | Ground Rail | 0V Reference |
| **ESP32-CAM** | GND Pin | **Common Star Junction** | Terminal Lug | Black | Ground Rail | 0V Reference |

> [!NOTE]
> **DATA LINKS (what is NOT wired):** The ESP32-CAM connects only to 5V and GND — it has no data wires to the Arduino.
> Video travels **Wi-Fi MJPEG** to the laptop (`http://<esp32-ip>:81/stream`), and commands/telemetry travel
> **laptop USB serial -> Arduino D0/D1** at 9600 baud. Keep D0/D1 free: they are the USB bootloader serial pins.
