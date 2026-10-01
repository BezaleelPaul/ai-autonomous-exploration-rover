# 29. Known Technical Limitations & Constraints

**Document ID:** DOC-LIM-001  

## 1. Physical & Algorithmic Limitations

1. **Monocular Depth Ambiguity:** The single OV2640 camera does not provide direct stereoscopic depth. Range to target is inferred heuristically from 2D bounding box width ratio (`stop_width_ratio = 0.45`). Variations in target object physical dimensions introduce distance estimation errors.
2. **Ultrasonic Beam Specular Reflection:** The HC-SR04 has a conical beam pattern ($~15^\circ$). Smooth obstacles approached at angles greater than $45^\circ$ reflect acoustic pulses away from the receiver, causing false negative distance reports (`DIST: -1`).
3. **Open-Loop Wheel Synchronization:** In the absence of optical wheel encoders or IMU feedback, the rover operates in open-loop PWM mode. Surface friction variations cause lateral path deviation over distance.
4. **Illumination Sensitivity:** Severe underexposure (< 20 lux) or direct sunlight glare (> 2000 lux) degrades camera dynamic range, reducing target detection recall.
