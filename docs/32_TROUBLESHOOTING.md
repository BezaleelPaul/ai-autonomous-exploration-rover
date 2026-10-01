# 32. System Troubleshooting & Diagnostic Guide

**Document ID:** DOC-TRB-001  

## 1. Common Diagnostic Scenarios & Resolutions

| Symptom / Fault | Potential Root Cause | Diagnostic Check | Corrective Action |
| :--- | :--- | :--- | :--- |
| **ESP32 Camera Fails to Init** | Insufficient current or corrupt ribbon | Inspect serial log for `CAM FAIL` | Reseat 24-pin ribbon cable; verify 5V supply delivers >= 1.5A |
| **Arduino Not Responding** | Port contention or baud rate mismatch | Check `serial.port` in `config.yaml` | Close Arduino IDE Serial Monitor; verify 9600 baud setting |
| **Motors Spin During Boot** | Floating Arduino digital inputs | Observe L298N LED indicators | Ensure `setup()` pulls IN1-IN4 LOW; add 10k pull-downs |
| **Rover Spins Continuously** | Target lost or search timeout too long | Check FSM state in logs | Verify target lighting; calibrate `search_timeout_s` |
| **Steering Limit-Cycle Chatter**| Proportional gain or deadband too tight | Observe rapid 'L'/'R' switching | Increase `center_tolerance` to 0.08; increase `min_command_duration_s` |
