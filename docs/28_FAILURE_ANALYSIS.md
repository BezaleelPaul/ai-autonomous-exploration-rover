# 28. Failure Mode and Effects Analysis (FMEA)

**Document ID:** DOC-SAF-002  
**Project:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Status:** Complete Risk & FMEA Assessment  
**Standard Compliance:** Automotive/Robotics Risk Priority Numbering ($RPN = S \times O \times D$)  
*(Scale: 1 = lowest risk / easily detected, 10 = catastrophic / undetectable)*

---

## 1. Master FMEA Risk Assessment Matrix

| Failure ID | Subsystem | Failure Mode | Root Cause | Potential Severity ($S$) | Potential Occurrence ($O$) | Detection Rating ($D$) | Initial RPN | Engineering Mitigation Strategy & Failsafe Response | Revised Severity ($S$) | Revised Occurrence ($O$) | Revised Detection ($D$) | Final RPN |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| **FM-01** | Power | Microcontroller Brownout Reset | Motor inrush current sags battery rail below 4.5V | 9 | 7 | 4 | **252** | Dedicated LM2596 buck converter for logic; 470µF bulk capacitor on 5V rail; star ground topology | 3 | 2 | 2 | **12** |
| **FM-02** | Comms | Host Serial Link Loss / Disconnect | USB cable vibration or host process stops sending | 8 | 5 | 2 | **80** | Arduino hardware watchdog triggers after 3000 ms; automatically defaults to emergency STOP | 2 | 3 | 1 | **6** |
| **FM-03** | Perception | Camera Frame Freeze / Video Stall | OV2640 FIFO crash or Wi-Fi streaming socket lockup | 7 | 6 | 3 | **126** | FrameManager watchdog monitors inter-frame delay; halts autonomous commands if delay > 3.0s | 2 | 2 | 1 | **4** |
| **FM-04** | Safety | Ultrasonic Specular Reflection Blindness | Obstacle angled at >45° reflects acoustic wave away from sensor | 8 | 6 | 7 | **336** | Conservative slow-down zone (30cm); wide target search radius; fallback stop on proximity limit | 4 | 4 | 3 | **48** |
| **FM-05** | Actuation | Motor Driver Overheating / Thermal Cutoff | Prolonged stall on carpet or obstacle contact | 6 | 4 | 5 | **120** | Current-limiting fuse (3A); passive aluminum heatsink on L298N; 1.0s movement timeout in software | 2 | 2 | 2 | **8** |
| **FM-06** | AI / Perception | False Positive Target Misidentification | Background clutter resembles target color/shape | 5 | 6 | 4 | **120** | Confidence filter (>= 0.50); minimum box size constraint (>= 20px); largest-box tracking priority | 2 | 3 | 2 | **12** |
| **FM-07** | Control | Limit Cycle Steering Oscillation | High proportional gain ($K_p$) causes overshooting across center | 4 | 7 | 2 | **56** | Deadband tolerance (±0.06); minimum command duration (0.4s); decision cooldown (0.2s) | 2 | 2 | 1 | **4** |
| **FM-08** | Mechanical | Wheel Slip / Trajectory Drift | Surface friction disparity between left and right tires | 5 | 8 | 6 | **240** | Differential drive kinematics calibrated via median turning duration; closed-loop visual servoing | 3 | 4 | 2 | **24** |
| **FM-09** | Electrical | ESP32 GPIO Overvoltage Breakdown | Mis-wiring Arduino 5V TX straight to a 3.3V ESP32 GPIO | 10 | 1 | 3 | **30** | No wired UART link exists (ESP32 is power-only: 5V/GND) - enforced by doc-consistency test; if a wired link is ever added, install a level shifter first | 2 | 1 | 1 | **2** |
| **FM-10** | Software | Corrupt Serial Character Ingestion | Electromagnetic interference (EMI) on serial lines | 5 | 5 | 2 | **50** | Single-character ASCII validation filter; rejects unrecognized characters; sends STATUS:ERROR | 2 | 2 | 1 | **4** |

---

## 2. Summary of Critical Mitigation Safeguards

1. **Watchdog Redundancy:** Two independent software watchdogs exist:
   - High-level perception watchdog in `software/safety/safety_manager.py` (halts commands if camera frame frozen $> 3.0$ s).
   - Low-level microcontroller watchdog in `arduino/rover_controller/rover_controller.ino` (cuts motor PWM if no valid packet received for $> 3000$ ms).
2. **Deterministic Default State:** In any error, timeout, sensor disconnection, or emergency condition, the state machine and microcontroller default immediately to `STOP`.
