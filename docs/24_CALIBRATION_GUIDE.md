# 24. Sensor & Drivetrain Calibration Guide

**Document ID:** DOC-CAL-001  
**Source Code:** [`scripts/calibration.py`](../scripts/calibration.py)

## 1. Calibration Procedures

1. **Rover Width Calibration:** Measure exact track width $L$ with calipers; record in `config/thresholds.yaml` (default: 18.0 cm).
2. **Ultrasonic Range Calibration:** Position flat obstacle at 15.0 cm, 30.0 cm, and 50.0 cm; verify `DIST:` telemetry; adjust `emergency_stop_cm` if necessary.
3. **Vision Zone Tuning:** Present visual target in left, center, and right quadrants of camera view; adjust `left_boundary: 0.33`, `center_boundary: 0.66`, and deadband `center_tolerance: 0.06`.
4. **Approach Stop Ratio Tuning:** Advance rover toward target until desired stopping distance ($~20$ cm) is achieved; note bounding box width ratio; set `approach_stop_width_ratio: 0.45`.
5. **Motor Turn Calibration:** Time the vehicle during a 90-degree pivot turn on test flooring; set `turning_duration_s: 0.5`.
