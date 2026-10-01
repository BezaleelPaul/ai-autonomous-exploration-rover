# 05. System Objectives

### Primary Objectives:
1. **Distributed System Partitioning:** Implement a dual-microcontroller architecture separating visual edge perception (ESP32) from real-time motor control and safety (Arduino UNO).
2. **Visual Target Guidance:** Track a designated visual target within a horizontal field of view ($66^\circ$), estimating lateral displacement error $e = x_{target} - x_{center}$ and steering the rover to maintain target alignment within $\pm 0.06$ deadband tolerance.
3. **Multi-Tiered Safety Supervision:** Implement a dual-layer hardware and software safety architecture guaranteeing motor cutoff in $< 50$ ms upon detecting an obstacle $< 15.0$ cm or upon loss of serial communication $> 3000$ ms.
4. **Proportional Control Stability:** Validate proportional heading steering control ($\omega = K_p \cdot e$) preventing limit-cycle oscillation through configurable command hold times and zone deadbands.

### Secondary Objectives:
1. **Deterministic Documentation Pipeline:** Build a fully automated Python documentation generation toolchain producing 300 DPI vector schematics, kinematic simulations, test templates, and final reports.
2. **Electrical Isolation & Data-Link Separation:** Design a validated wiring topology with dedicated logic power regulation (LM2596 buck), a single star ground, and data links kept off the motor rail (Wi-Fi MJPEG video; laptop USB serial control; ESP32 wired to 5V/GND only).
