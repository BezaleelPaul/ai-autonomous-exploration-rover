# 26. Experimental Methodology & Evaluation Protocols

**Document ID:** DOC-EXP-001  
**Project:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Status:** Experimental Framework Specification (Protocols E01 to E11)

---

## 1. Scientific Experimental Framework

To substantiate the engineering claims of this distributed robotic architecture without manufacturing or fabricating empirical data, eleven systematic laboratory experiments (E01 to E11) are established.

Each protocol contains:
- Formal objective and scientific rationale
- Required apparatus and test bench instrumentation
- Controlled variables and independent parameters
- Structured data recording tables (with placeholders for real laboratory measurements)

---

## Protocol E01: Motor Characterization & Speed Calibration

### 1. Objective
Measure rotational speed (RPM) and linear rover velocity (m/s) as a function of PWM duty cycle (60 to 255 in steps of 20).

### 2. Apparatus & Instrumentation
- Rover chassis with verified dual-microcontroller setup
- Digital Storage Oscilloscope (DSO), Digital Multimeter (DMM)
- Laser distance meter / tape measure, Lux meter
- Bench power supply (0-12V, 5A) with current monitoring

### 3. Procedure & Data Collection Protocol
1. Configure rover environment to designated baseline conditions.
2. Execute 5 independent trials per data point to compute sample mean and standard deviation.
3. Record raw observations in the structured matrix below.

### 4. Empirical Data Recording Table

| PWM Duty Cycle (0-255) | Left Wheel RPM | Right Wheel RPM | Measured Linear Speed (m/s) | Current Draw (mA) |
| :---: | :---: | :---: | :---: | :---: |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |

*Note: All numerical entries must be populated from calibrated physical test bench measurements.*

---

## Protocol E02: Ultrasonic Ranging Accuracy & Cone Angle

### 1. Objective
Evaluate HC-SR04 distance measurement error across distances from 5 cm to 250 cm and incidence angles from 0° to 45°.

### 2. Apparatus & Instrumentation
- Rover chassis with verified dual-microcontroller setup
- Digital Storage Oscilloscope (DSO), Digital Multimeter (DMM)
- Laser distance meter / tape measure, Lux meter
- Bench power supply (0-12V, 5A) with current monitoring

### 3. Procedure & Data Collection Protocol
1. Configure rover environment to designated baseline conditions.
2. Execute 5 independent trials per data point to compute sample mean and standard deviation.
3. Record raw observations in the structured matrix below.

### 4. Empirical Data Recording Table

| True Distance (cm) | Sensor Reading (cm) | Absolute Error (cm) | Percentage Error (%) | Incidence Angle (deg) |
| :---: | :---: | :---: | :---: | :---: |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |

*Note: All numerical entries must be populated from calibrated physical test bench measurements.*

---

## Protocol E03: AI Inference Latency & Resource Footprint

### 1. Objective
Benchmark inference time, frames per second (FPS), heap memory consumption, and CPU core utilization across different models.

### 2. Apparatus & Instrumentation
- Rover chassis with verified dual-microcontroller setup
- Digital Storage Oscilloscope (DSO), Digital Multimeter (DMM)
- Laser distance meter / tape measure, Lux meter
- Bench power supply (0-12V, 5A) with current monitoring

### 3. Procedure & Data Collection Protocol
1. Configure rover environment to designated baseline conditions.
2. Execute 5 independent trials per data point to compute sample mean and standard deviation.
3. Record raw observations in the structured matrix below.

### 4. Empirical Data Recording Table

| Model Architecture | Input Resolution | Inference Latency (ms) | Effective FPS | RAM / PSRAM Used (KB) |
| :---: | :---: | :---: | :---: | :---: |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |

*Note: All numerical entries must be populated from calibrated physical test bench measurements.*

---

## Protocol E04: Target Detection Recall & Precision vs Distance

### 1. Objective
Record true positives, false positives, and missed detections as the target object distance varies from 0.5m to 4.0m.

### 2. Apparatus & Instrumentation
- Rover chassis with verified dual-microcontroller setup
- Digital Storage Oscilloscope (DSO), Digital Multimeter (DMM)
- Laser distance meter / tape measure, Lux meter
- Bench power supply (0-12V, 5A) with current monitoring

### 3. Procedure & Data Collection Protocol
1. Configure rover environment to designated baseline conditions.
2. Execute 5 independent trials per data point to compute sample mean and standard deviation.
3. Record raw observations in the structured matrix below.

### 4. Empirical Data Recording Table

| Distance (m) | Lighting (lux) | True Positives | False Positives | Confidence Score |
| :---: | :---: | :---: | :---: | :---: |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |

*Note: All numerical entries must be populated from calibrated physical test bench measurements.*

---

## Protocol E05: Proportional Steering Gain (Kp) Comparison

### 1. Objective
Compare heading settling time, overshoot, and lateral trajectory stability for Kp = 0.2, 0.4, 0.6, 0.8, 1.2 in simulation and hardware.

### 2. Apparatus & Instrumentation
- Rover chassis with verified dual-microcontroller setup
- Digital Storage Oscilloscope (DSO), Digital Multimeter (DMM)
- Laser distance meter / tape measure, Lux meter
- Bench power supply (0-12V, 5A) with current monitoring

### 3. Procedure & Data Collection Protocol
1. Configure rover environment to designated baseline conditions.
2. Execute 5 independent trials per data point to compute sample mean and standard deviation.
3. Record raw observations in the structured matrix below.

### 4. Empirical Data Recording Table

| Kp Value | Rise Time (s) | Overshoot (%) | Settling Time (s) | Steady-State Error (deg) |
| :---: | :---: | :---: | :---: | :---: |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |

*Note: All numerical entries must be populated from calibrated physical test bench measurements.*

---

## Protocol E06: Target Visual Alignment & Deadband Tolerance

### 1. Objective
Measure robot heading alignment accuracy when stopping in front of the target, and observe the effect of center tolerance band (±0.06).

### 2. Apparatus & Instrumentation
- Rover chassis with verified dual-microcontroller setup
- Digital Storage Oscilloscope (DSO), Digital Multimeter (DMM)
- Laser distance meter / tape measure, Lux meter
- Bench power supply (0-12V, 5A) with current monitoring

### 3. Procedure & Data Collection Protocol
1. Configure rover environment to designated baseline conditions.
2. Execute 5 independent trials per data point to compute sample mean and standard deviation.
3. Record raw observations in the structured matrix below.

### 4. Empirical Data Recording Table

| Initial Heading Offset (deg) | Final Heading Offset (deg) | Cycles to Align | Oscillation Count | Status |
| :---: | :---: | :---: | :---: | :---: |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |

*Note: All numerical entries must be populated from calibrated physical test bench measurements.*

---

## Protocol E07: Autonomous Navigation & Goal Approach

### 1. Objective
Record total mission completion time, path efficiency, and terminal stopping distance from starting positions at 1m, 2m, and 3m.

### 2. Apparatus & Instrumentation
- Rover chassis with verified dual-microcontroller setup
- Digital Storage Oscilloscope (DSO), Digital Multimeter (DMM)
- Laser distance meter / tape measure, Lux meter
- Bench power supply (0-12V, 5A) with current monitoring

### 3. Procedure & Data Collection Protocol
1. Configure rover environment to designated baseline conditions.
2. Execute 5 independent trials per data point to compute sample mean and standard deviation.
3. Record raw observations in the structured matrix below.

### 4. Empirical Data Recording Table

| Trial # | Initial Distance (m) | Time to Target (s) | Final Stop Bounding Box Width | Final Stoppage Distance (cm) |
| :---: | :---: | :---: | :---: | :---: |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |

*Note: All numerical entries must be populated from calibrated physical test bench measurements.*

---

## Protocol E08: Obstacle Detection & Safety Override Integrity

### 1. Objective
Evaluate obstacle braking distance and hardware override response when an obstacle is suddenly introduced into the rover's path.

### 2. Apparatus & Instrumentation
- Rover chassis with verified dual-microcontroller setup
- Digital Storage Oscilloscope (DSO), Digital Multimeter (DMM)
- Laser distance meter / tape measure, Lux meter
- Bench power supply (0-12V, 5A) with current monitoring

### 3. Procedure & Data Collection Protocol
1. Configure rover environment to designated baseline conditions.
2. Execute 5 independent trials per data point to compute sample mean and standard deviation.
3. Record raw observations in the structured matrix below.

### 4. Empirical Data Recording Table

| Approach Velocity (m/s) | Obstacle Insertion Distance (cm) | Braking Distance (cm) | Stopping Margin to Impact (cm) | Watchdog Tripped |
| :---: | :---: | :---: | :---: | :---: |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |

*Note: All numerical entries must be populated from calibrated physical test bench measurements.*

---

## Protocol E09: Communication Link Reliability & Timeout Response

### 1. Objective
Evaluate packet delivery ratio, UART bit error rate, and exact watchdog trigger timing under varying transmission frequencies.

### 2. Apparatus & Instrumentation
- Rover chassis with verified dual-microcontroller setup
- Digital Storage Oscilloscope (DSO), Digital Multimeter (DMM)
- Laser distance meter / tape measure, Lux meter
- Bench power supply (0-12V, 5A) with current monitoring

### 3. Procedure & Data Collection Protocol
1. Configure rover environment to designated baseline conditions.
2. Execute 5 independent trials per data point to compute sample mean and standard deviation.
3. Record raw observations in the structured matrix below.

### 4. Empirical Data Recording Table

| Packet Rate (Hz) | Packets Sent | Packets Received | Drop Rate (%) | Watchdog Cutoff Latency (ms) |
| :---: | :---: | :---: | :---: | :---: |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |

*Note: All numerical entries must be populated from calibrated physical test bench measurements.*

---

## Protocol E10: Environmental Illumination Robustness Sweep

### 1. Objective
Measure target detection confidence and tracking success across ambient lighting levels: 10 lux (dark), 100 lux (dim), 500 lux (office), 2000 lux (bright).

### 2. Apparatus & Instrumentation
- Rover chassis with verified dual-microcontroller setup
- Digital Storage Oscilloscope (DSO), Digital Multimeter (DMM)
- Laser distance meter / tape measure, Lux meter
- Bench power supply (0-12V, 5A) with current monitoring

### 3. Procedure & Data Collection Protocol
1. Configure rover environment to designated baseline conditions.
2. Execute 5 independent trials per data point to compute sample mean and standard deviation.
3. Record raw observations in the structured matrix below.

### 4. Empirical Data Recording Table

| Illumination (lux) | Frame Contrast | Mean Target Confidence | Tracking Lost Events | Classification Accuracy |
| :---: | :---: | :---: | :---: | :---: |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |

*Note: All numerical entries must be populated from calibrated physical test bench measurements.*

---

## Protocol E11: Long-Duration Operational Thermal & Power Profiling

### 1. Objective
Profile battery discharge curve, voltage sag, component temperatures (L298N, ESP32, Arduino), and heap stability over a 45-minute continuous run.

### 2. Apparatus & Instrumentation
- Rover chassis with verified dual-microcontroller setup
- Digital Storage Oscilloscope (DSO), Digital Multimeter (DMM)
- Laser distance meter / tape measure, Lux meter
- Bench power supply (0-12V, 5A) with current monitoring

### 3. Procedure & Data Collection Protocol
1. Configure rover environment to designated baseline conditions.
2. Execute 5 independent trials per data point to compute sample mean and standard deviation.
3. Record raw observations in the structured matrix below.

### 4. Empirical Data Recording Table

| Time (minutes) | Battery Voltage (V) | Logic Rail (V) | L298N Temp (°C) | ESP32 Temp (°C) | Operational Status |
| :---: | :---: | :---: | :---: | :---: | :---: |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |
| [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] | [TO RECORD] |

*Note: All numerical entries must be populated from calibrated physical test bench measurements.*

---

