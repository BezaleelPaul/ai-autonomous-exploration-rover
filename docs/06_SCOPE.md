# 06. Scope of Work & Project Boundaries

## 1. In-Scope Engineering Deliverables

- 2WD differential drive chassis assembly with front omnidirectional ball caster.
- Electrical schematic with clean separation between high-current motor power (7.4V) and regulated logic power (5.0V).
- Arduino UNO firmware (`rover_controller.ino`) executing 9600 baud command ingestion, 200 ms telemetry streaming, HC-SR04 pulse measurement, and motor PWM.
- ESP32 edge perception firmware capturing frames, computing centroid error, and executing the 10-state decision FSM.
- Python simulation of proportional steering response ($K_p$ sweep).
- 32 standardized experimental test cases and 11 experimental protocols.

## 2. Explicitly Out-of-Scope (Boundaries)

- **Simultaneous Localization and Mapping (SLAM):** No 2D/3D LiDAR or visual SLAM mapping is implemented.
- **Inverted Pendulum / Self-Balancing:** The baseline rover is a 3-point statically stable 2WD platform. Two-wheeled dynamic self-balancing is documented strictly as Future Work.
- **Workstation-Tethered Autonomous Operation:** The laptop is strictly excluded from live closed-loop control during autonomous runs.
