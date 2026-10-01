# 23. Robot Assembly & Mechanical Build Guide

**Document ID:** DOC-MEC-001  
**Companion Diagram:** [`figures/15_full_robot_block_diagram.png`](../figures/15_full_robot_block_diagram.png)

## 1. Step-by-Step Mechanical & Electrical Assembly

1. **Chassis Preparation:** Secure the dual yellow TT gear motors to the lower acrylic chassis plate using M3 screws and brackets. Mount the passive ball caster at the front-center.
2. **Drive Wheel Installation:** Press-fit the rubber wheels onto the dual-flat motor shafts.
3. **Power Subsystem Mounting:** Mount the 2S 18650 battery holder at the center-of-gravity. Install the master switch and 3A fuse in series on the positive lead.
4. **Driver Installation:** Fasten the L298N module toward the rear. Connect motor wires with 0.1 µF ceramic suppression capacitors across the motor terminals.
5. **Microcontroller Stacking:** Mount the Arduino UNO and ESP32-CAM using 20 mm nylon standoffs.
6. **Ultrasonic Sensor Alignment:** Mount the HC-SR04 horizontally at front center, exactly 5.0 cm above ground level.
7. **Camera Orientation:** Mount the ESP32-CAM pointing forward with a slight downward pitch ($~5^\circ$) to encompass both ground target bottles and approaching obstacles.
