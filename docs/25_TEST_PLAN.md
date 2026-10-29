# 25. System Test Plan & Verification Matrix

**Document ID:** DOC-TEST-001  
**Project:** AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence and Safety Control  
**Status:** Build-Ready Engineering Test Suite (32 Rigorous Cases)  
**Standard Compliance:** Strict Engineering Classification (`Expected` defined; `Actual` reserved for hardware execution)

---

## 1. Test Suite Architecture

The system test plan spans four foundational verification domains:
1. **Actuation & Low-Level Control:** Motor direction, PWM linearity, speed symmetry, emergency stop response.
2. **Sensory Safety & Interlocks:** HC-SR04 ultrasonic ranging accuracy, acoustic reflections, 15 cm hard stop, echo timeout.
3. **Communication & Watchdogs:** UART packet parsing, 3000 ms communication loss watchdog, invalid command filtering, telemetry rates.
4. **Perception & Edge Intelligence:** Target confidence scoring, false-positive rejection, visual zone mapping, anti-oscillation deadband, and power brownout resilience.

---

## 2. Master Test Cases (32 Standard Engineering Cases)

### Test Case TC-MOT-01: Motor Direction Integrity (Forward/Reverse)

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-MOT-01` |
| **Objective** | Motor Direction Integrity (Forward/Reverse) |
| **Setup & Preconditions** | Wheels elevated off ground, 7.4V battery connected |
| **Procedure** | Issue 'F' command via Serial; observe left and right wheel rotation directions. Issue 'B' command. |
| **Expected Outcome** | Both wheels rotate forward on 'F', reverse on 'B' without stalling or opposite rotation. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Motors and L298N H-Bridge wiring |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-MOT-02: Differential Steering Rotation (Left/Right)

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-MOT-02` |
| **Objective** | Differential Steering Rotation (Left/Right) |
| **Setup & Preconditions** | Wheels elevated off ground, Arduino powered |
| **Procedure** | Issue 'L' command; observe wheel rotations. Issue 'R' command. |
| **Expected Outcome** | Left turns: Left wheel reverse, right wheel forward. Right turns: Left forward, right reverse. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Steering logic in rover_controller.ino |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-MOT-03: PWM Symmetrical Speed Response

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-MOT-03` |
| **Objective** | PWM Symmetrical Speed Response |
| **Setup & Preconditions** | Bench power supply at 6.0V, tachometer |
| **Procedure** | Apply 200 PWM to ENA and ENB. Measure RPM of left and right output shafts over 10 seconds. |
| **Expected Outcome** | RPM difference between left and right motors is within ±5% tolerance. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Open-loop motor mismatch characterization |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-MOT-04: Motor Cutoff Command Latency ('S')

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-MOT-04` |
| **Objective** | Motor Cutoff Command Latency ('S') |
| **Setup & Preconditions** | Wheels rotating at 200 PWM |
| **Procedure** | Send ASCII 'S' command via serial. Measure time until PWM drops to 0 using oscilloscope. |
| **Expected Outcome** | PWM duty cycle drops to 0% in < 10 ms upon character arrival. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Actuator responsiveness |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-US-01: HC-SR04 Ranging Linearity (Flat Wall)

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-US-01` |
| **Objective** | HC-SR04 Ranging Linearity (Flat Wall) |
| **Setup & Preconditions** | Tape measure fixed along floor, cardboard target |
| **Procedure** | Place obstacle at 15cm, 30cm, 50cm, 100cm, 200cm. Record DIST telemetry readings. |
| **Expected Outcome** | Sensor error <= ±1.0 cm at distances < 100cm; <= ±3.0 cm at 200cm. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Ultrasonic acoustic accuracy |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-US-02: Ultrasonic Emergency Stop Override (<15cm)

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-US-02` |
| **Objective** | Ultrasonic Emergency Stop Override (<15cm) |
| **Setup & Preconditions** | Rover driving forward on ground toward wall at 200 PWM |
| **Procedure** | Rover approaches barrier at 15cm threshold. Observe motor cutoff independently of PC commands. |
| **Expected Outcome** | Arduino immediately cuts PWM to 0 at distance < 15.0 cm; status reports STATUS:STOP. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Autonomous safety hardware override |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-US-03: Acoustic Glancing Angle & Specular Reflection

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-US-03` |
| **Objective** | Acoustic Glancing Angle & Specular Reflection |
| **Setup & Preconditions** | Flat acrylic sheet angled at 15°, 30°, 45°, 60° to sensor beam |
| **Procedure** | Measure distance reported at 50 cm distance across different incidence angles. |
| **Expected Outcome** | Valid echo returned up to 30°; beyond 45° specular reflection may report -1 (out of range). |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | HC-SR04 beam boundary limitations |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-US-04: Echo Timeout & Missing Target Recovery

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-US-04` |
| **Objective** | Echo Timeout & Missing Target Recovery |
| **Setup & Preconditions** | No obstacle in range (> 4.5m) |
| **Procedure** | Trigger HC-SR04 pulse; record timeout duration in pulseIn(). |
| **Expected Outcome** | Firmware completes in 30ms timeout without locking CPU; reports DIST:-1. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Non-blocking safety loop verification |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-COM-01: Communication Timeout Watchdog

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-COM-01` |
| **Objective** | Communication Timeout Watchdog |
| **Setup & Preconditions** | Rover driving forward ('F') |
| **Procedure** | Disconnect UART TX wire or pause transmission for > 3000 ms. |
| **Expected Outcome** | Arduino watchdog timer expires at exactly 3000 ms; motors halt immediately; STATUS:STOP. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Failsafe loss of signal (LOS) interlock |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-COM-02: Invalid Command Packet Rejection

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-COM-02` |
| **Objective** | Invalid Command Packet Rejection |
| **Setup & Preconditions** | Arduino listening at 9600 baud |
| **Procedure** | Transmit corrupted or invalid characters ('X', '1', '\x00', 'FAST'). |
| **Expected Outcome** | Arduino ignores invalid commands, remains stopped/previous state, returns STATUS:ERROR. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Serial buffer validation |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-COM-03: Baud Rate & Frame Synchronization

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-COM-03` |
| **Objective** | Baud Rate & Frame Synchronization |
| **Setup & Preconditions** | PySerial connected at 9600-8-N-1 |
| **Procedure** | Stream 1000 consecutive movement commands at 20 Hz rate. |
| **Expected Outcome** | Zero frame errors, 0 dropped characters, 100% command execution rate. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | UART throughput and signal integrity |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-COM-04: Telemetry Streaming Rate Verification

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-COM-04` |
| **Objective** | Telemetry Streaming Rate Verification |
| **Setup & Preconditions** | Oscilloscope / serial timestamp logger |
| **Procedure** | Record arrival timestamps of DIST telemetry packets from Arduino. |
| **Expected Outcome** | Telemetry packets arrive at strictly 200 ms ± 10 ms interval. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Microcontroller loop timing stability |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-CAM-01: OV2640 Frame Acquisition & Resolution

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-CAM-01` |
| **Objective** | OV2640 Frame Acquisition & Resolution |
| **Setup & Preconditions** | ESP32-CAM powered, camera initialized |
| **Procedure** | Capture frame buffer via esp_camera_fb_get(). Inspect dimensions and pixel format. |
| **Expected Outcome** | Resolution is exactly 640x480 (VGA), PIXFORMAT_JPEG, length > 10 KB. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Camera sensor driver verification |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-CAM-02: Camera Frame Rate (FPS) Stability

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-CAM-02` |
| **Objective** | Camera Frame Rate (FPS) Stability |
| **Setup & Preconditions** | Static indoor scene, 5V / 2A bench supply |
| **Procedure** | Count captured frames over 60 seconds at VGA resolution. |
| **Expected Outcome** | Sustained frame rate >= 12.0 FPS without camera FIFO overflow. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Video capture pipeline throughput |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-CAM-03: Camera Frozen Frame Watchdog

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-CAM-03` |
| **Objective** | Camera Frozen Frame Watchdog |
| **Setup & Preconditions** | Frame manager thread active |
| **Procedure** | Simulate camera disconnect or halt frame arrival for > 3.0 seconds. |
| **Expected Outcome** | SafetyManager detects frozen buffer timeout (>3.0s); autonomous movement inhibited. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Visual sensor failure interlock |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-CAM-04: CLAHE & Preprocessing Image Normalization

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-CAM-04` |
| **Objective** | CLAHE & Preprocessing Image Normalization |
| **Setup & Preconditions** | Low-contrast indoor lighting (100 lux) |
| **Procedure** | Process frame through enhance_clahe and sharpen filters. Compute histogram spread. |
| **Expected Outcome** | Dynamic range of histogram expands; edges sharpened in < 15 ms execution time. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Preprocessing pipeline efficiency |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-AI-01: Target Object Detection Confidence (Center)

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-AI-01` |
| **Objective** | Target Object Detection Confidence (Center) |
| **Setup & Preconditions** | Target object placed in optical center at 1.0m |
| **Procedure** | Run detector on 20 consecutive frames. Record confidence scores. |
| **Expected Outcome** | Mean confidence >= 0.70; bounding box centered within normalized [0.45, 0.55]. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Perception accuracy under nominal conditions |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-AI-02: False Positive Immunity (Empty Scene)

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-AI-02` |
| **Objective** | False Positive Immunity (Empty Scene) |
| **Setup & Preconditions** | Neutral white/beige wall with no target objects |
| **Procedure** | Run detector on 50 consecutive frames. Record false detections. |
| **Expected Outcome** | Zero target detections above 0.50 confidence threshold (False Positive Rate < 2%). |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Classifier specificity |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-AI-03: Low Confidence Filtering & Suppression

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-AI-03` |
| **Objective** | Low Confidence Filtering & Suppression |
| **Setup & Preconditions** | Target placed at 3.5m distance in dim light |
| **Procedure** | Record detection score. Verify behavior when confidence < 0.50. |
| **Expected Outcome** | Detector rejects bounding box when confidence < 0.50; rover remains in SEARCHING state. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Confidence threshold validation |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-AI-04: Multiple Object Disambiguation

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-AI-04` |
| **Objective** | Multiple Object Disambiguation |
| **Setup & Preconditions** | Two target objects placed at different distances (1m and 2m) |
| **Procedure** | Feed frame to ObjectTracker. Observe which bounding box is prioritized. |
| **Expected Outcome** | Tracker locks onto primary/largest target bounding box consistently. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Object tracking arbitration |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-AI-05: Target Disappearance & Search Fallback

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-AI-05` |
| **Objective** | Target Disappearance & Search Fallback |
| **Setup & Preconditions** | Target centered, rover approaching |
| **Procedure** | Abruptly remove target from camera field of view. |
| **Expected Outcome** | Rover retains target lock for 1.0s, then transitions safely to SEARCHING mode. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Target occlusion / loss handling |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-ENV-01: Low Illumination Robustness (<50 lux)

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-ENV-01` |
| **Objective** | Low Illumination Robustness (<50 lux) |
| **Setup & Preconditions** | Dimmable laboratory test room, light meter at 30 lux |
| **Procedure** | Present target at 1.0m distance. Record detection rate and confidence. |
| **Expected Outcome** | Target successfully identified or graceful fallback to SEARCHING without crash. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Low-light perception limits |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-ENV-02: High Illumination & Direct Glare (>1500 lux)

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-ENV-02` |
| **Objective** | High Illumination & Direct Glare (>1500 lux) |
| **Setup & Preconditions** | High-intensity spotlight directed toward camera lens |
| **Procedure** | Assess frame overexposure and auto-gain recovery. |
| **Expected Outcome** | OV2640 AGC/AEC recovers in < 1.0 second; no firmware lockup. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Sensor glare tolerance |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-ENV-03: Motion Blur During Rapid Pivot Turns

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-ENV-03` |
| **Objective** | Motion Blur During Rapid Pivot Turns |
| **Setup & Preconditions** | Rover executing 'L' spin turn at 200 PWM |
| **Procedure** | Capture frames during angular rotation. Evaluate detector bounding box jitter. |
| **Expected Outcome** | Frame skipping ignores blurred intermediate frames; locks when paused or stabilized. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Rotational blur mitigation |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-NAV-01: Vision Zone Steering Mapping (Left Sector)

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-NAV-01` |
| **Objective** | Vision Zone Steering Mapping (Left Sector) |
| **Setup & Preconditions** | Target placed in left sector (x_center = 0.20) |
| **Procedure** | Evaluate steering layer output. |
| **Expected Outcome** | steering layer outputs state ALIGNING, command 'L' (turn left). |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Steering logic verification |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-NAV-02: Vision Zone Steering Mapping (Center Sector)

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-NAV-02` |
| **Objective** | Vision Zone Steering Mapping (Center Sector) |
| **Setup & Preconditions** | Target placed in center sector (x_center = 0.50) |
| **Procedure** | Evaluate steering layer output. |
| **Expected Outcome** | steering layer outputs state APPROACHING, command 'F' (drive straight). |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Straight tracking verification |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-NAV-03: Vision Zone Steering Mapping (Right Sector)

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-NAV-03` |
| **Objective** | Vision Zone Steering Mapping (Right Sector) |
| **Setup & Preconditions** | Target placed in right sector (x_center = 0.80) |
| **Procedure** | Evaluate steering layer output. |
| **Expected Outcome** | steering layer outputs state ALIGNING, command 'R' (turn right). |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Steering logic verification |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-NAV-04: Anti-Oscillation Deadband Stability

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-NAV-04` |
| **Objective** | Anti-Oscillation Deadband Stability |
| **Setup & Preconditions** | Target positioned at border (x_center = 0.52 to 0.48) |
| **Procedure** | Observe command sequence over 30 cycles. |
| **Expected Outcome** | No rapid chattering between 'L' and 'R'; center tolerance (±0.06) holds 'F'. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Control oscillation prevention |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-NAV-05: Target Proximity Termination (Stop Ratio)

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-NAV-05` |
| **Objective** | Target Proximity Termination (Stop Ratio) |
| **Setup & Preconditions** | Rover approaches target until bbox width ratio > 0.45 |
| **Procedure** | Record commanded movement. |
| **Expected Outcome** | steering layer detects width_ratio > 0.45; transitions to STOPPED; issues 'S'. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Goal completion boundary |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-NAV-06: Search Mode Timeout & Rotation Limit

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-NAV-06` |
| **Objective** | Search Mode Timeout & Rotation Limit |
| **Setup & Preconditions** | Target completely absent from room |
| **Procedure** | Initiate search mode. Monitor search duration and rotations. |
| **Expected Outcome** | Rover halts after 30.0s timeout or 2 complete rotations; transitions to STOPPED. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Search space bounding |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-PWR-01: Battery Voltage Sag Under Motor Stall

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-PWR-01` |
| **Objective** | Battery Voltage Sag Under Motor Stall |
| **Setup & Preconditions** | Fresh 2S Li-ion battery (8.2V), dual motor stall induced for 1.0s |
| **Procedure** | Log 5.0V buck converter output voltage using digital storage oscilloscope. |
| **Expected Outcome** | Buck converter 5.0V logic rail remains >= 4.85V; NO micro resets occur on ESP32 or UNO. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Power decoupling and brownout resilience |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-PWR-02: Arduino Hardware Reset Fault Injection

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-PWR-02` |
| **Objective** | Arduino Hardware Reset Fault Injection |
| **Setup & Preconditions** | Rover in autonomous tracking mode |
| **Procedure** | Momentarily press Arduino onboard RESET button. |
| **Expected Outcome** | Motors immediately disengage; system re-initializes cleanly in < 1.5s into STOPPED state. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Hardware reset fault tolerance |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

### Test Case TC-PWR-03: Long-Duration Autonomous Endurance (30 Minutes)

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `TC-PWR-03` |
| **Objective** | Long-Duration Autonomous Endurance (30 Minutes) |
| **Setup & Preconditions** | Continuous tracking loop in obstacle-free arena |
| **Procedure** | Monitor temperature of L298N heatsink and ESP32-CAM SoC every 5 minutes. |
| **Expected Outcome** | L298N temp < 65°C; ESP32-CAM temp < 60°C; zero memory leaks or task freeze. |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | Thermal and system stability |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

