# 17. Ultrasonic Safety Subsystem & Collision Override

**Document ID:** DOC-SAF-001  
**Companion Diagram:** [`figures/08_safety_hierarchy.png`](../figures/08_safety_hierarchy.png)

## 1. Acoustic Ranging & Failsafe Interlock

The HC-SR04 ultrasonic sensor operates via 40 kHz acoustic burst ranging:
$$d_{cm} = \frac{t_{echo} \times 0.0343 \text{ cm/\mu s}}{2}$$

```
+---------------------------------------------------------------------------------+
|                               DISTANCE THRESHOLDS                               |
|                                                                                 |
| 0 cm          15.0 cm                       30.0 cm                     50.0 cm |
| |---------------|-----------------------------|---------------------------|---> |
|   EMERGENCY     |        CAUTION ZONE         |        NOMINAL ZONE       |     |
|   STOP ZONE     |        Slow Velocity        |        Full Speed         |     |
| (Hardware Latch)|       (Seek clearance)      |     (Normal tracking)     |     |
+---------------------------------------------------------------------------------+
```

- **Emergency Cutoff (< 15.0 cm):** If a valid distance reading is detected below 15 cm and the current command is `'F'` or `'B'`, the Arduino immediately cuts motor PWM to 0. High-level forward commands from the ESP32 are suppressed.
