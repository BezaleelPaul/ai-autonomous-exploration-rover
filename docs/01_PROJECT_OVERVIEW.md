# 01. Project Overview

**Document ID:** DOC-SYS-001  
**Project Title:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Academic Level:** Bachelor of Technology (B.Tech) Capstone Engineering Project  
**Author/Engineering Team:** Autonomous Robotics & Embedded Systems Research Group

---

## 1. Project Synopsis

This project presents the design, mathematical modeling, embedded implementation, and experimental evaluation of an autonomous, vision-guided differential drive mobile robotic platform. The system operates via a **hierarchical distributed edge architecture**:
1. **Perception & Decision Coprocessor:** An ESP32 microcontroller with an OmniVision OV2640 camera executes image acquisition, visual preprocessing, target identification, spatial tracking error estimation, and finite state machine (FSM) navigation logic.
2. **Safety & Motion Supervisor:** An Arduino UNO R3 microcontroller handles hard real-time command validation, motor PWM generation, directional H-bridge gating, acoustic obstacle sensing via an HC-SR04 ultrasonic sensor, and an independent failsafe communication watchdog.
3. **Actuation Subsystem:** An L298N dual full-bridge driver modulating high-current DC power to dual 1:48 gearbox DC drive wheels.

```
+---------------------------------------------------------------------------------+
|                                 CORE ARCHITECTURE                               |
|                                                                                 |
|   [ OV2640 Camera ]                                                             |
|           |                                                                     |
|           v                                                                     |
|   [ ESP32-CAM ]                                                                 |
|     • Visual Perception & Contrast Normalization (CLAHE)                        |
|     • Target Identification (int8 TinyML / Color Centroid Tracking)             |
|     • Horizontal Heading Error Calculation: e = x_target - x_center             |
|     • Decision Engine (Finite State Machine: IDLE -> SEARCH -> TRACK -> STOP)   |
|           |                                                                     |
|           | Wi-Fi MJPEG video -> [ LAPTOP: detection + safety ]                 |
|           | Laptop -> USB serial: commands (F/B/L/R/S) @ 9600 baud              |
|           v                                                                     |
|   [ ARDUINO UNO R3 ] <========================= [ HC-SR04 Ultrasonic (Front) ]  |
|     • Command Syntax & Range Validation                   (Acoustic Barrier)    |
|     • 3000 ms Communication Watchdog (Auto-STOP on LOS)                         |
|     • Emergency Hardware Obstacle Cutoff (< 15 cm)                              |
|     • Dual-Channel PWM Modulation (Pins 5 & 10)                                 |
|           |                                                                     |
|           v                                                                     |
|   [ L298N Dual H-Bridge Driver ] ===> [ Left Motor (1:48) & Right Motor (1:48) ]|
+---------------------------------------------------------------------------------+
```

---

## 2. Key Engineering Principles

- **True Edge Autonomy:** The mobile robot does not rely on an external workstation or cloud server during autonomous navigation `[DESIGN DECISION]`. Workstation computers are restricted exclusively to development, offline model training, telemetry recording, and calibration.
- **Fail-Safe Determinism:** Safety is prioritized over mission completion. If the visual coprocessor crashes, communication drops, or an obstacle approaches within 15 cm, the physical hardware defaults to `STOP` independently of high-level software state.
- **Academic Rigor:** All hardware parameters, sensor tolerances, and latency budgets are tagged (`[MEASURED]`, `[VERIFIED IN CODE]`, `[ASSUMPTION]`, or `[TO VERIFY]`).
