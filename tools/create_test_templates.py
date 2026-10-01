"""Test Templates & Experimental Framework Generator.

Generates:
1. data/test_results.csv
2. data/test_results.xlsx (formatted openpyxl workbook with formulas)
3. 32 comprehensive, rigorous test cases in docs/testing/TEST_CASES.md
4. Experimental protocols E01 through E11 in experiments/ and docs/testing/

CRITICAL RULE:
- DO NOT insert fake results.
- 'Actual' and 'Pass/Fail' fields remain blank or marked [TO PERFORM].
"""

import os
import csv
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


TEST_CASES_DATA = [
    # Motor & Drivetrain Tests
    (
        "TC-MOT-01",
        "Motor Direction Integrity (Forward/Reverse)",
        "Wheels elevated off ground, 7.4V battery connected",
        "Issue 'F' command via Serial; observe left and right wheel rotation directions. Issue 'B' command.",
        "Both wheels rotate forward on 'F', reverse on 'B' without stalling or opposite rotation.",
        "Motors and L298N H-Bridge wiring",
    ),
    (
        "TC-MOT-02",
        "Differential Steering Rotation (Left/Right)",
        "Wheels elevated off ground, Arduino powered",
        "Issue 'L' command; observe wheel rotations. Issue 'R' command.",
        "Left turns: Left wheel reverse, right wheel forward. Right turns: Left forward, right reverse.",
        "Steering logic in rover_controller.ino",
    ),
    (
        "TC-MOT-03",
        "PWM Symmetrical Speed Response",
        "Bench power supply at 6.0V, tachometer",
        "Apply 200 PWM to ENA and ENB. Measure RPM of left and right output shafts over 10 seconds.",
        "RPM difference between left and right motors is within ±5% tolerance.",
        "Open-loop motor mismatch characterization",
    ),
    (
        "TC-MOT-04",
        "Motor Cutoff Command Latency ('S')",
        "Wheels rotating at 200 PWM",
        "Send ASCII 'S' command via serial. Measure time until PWM drops to 0 using oscilloscope.",
        "PWM duty cycle drops to 0% in < 10 ms upon character arrival.",
        "Actuator responsiveness",
    ),
    # Ultrasonic & Safety Tests
    (
        "TC-US-01",
        "HC-SR04 Ranging Linearity (Flat Wall)",
        "Tape measure fixed along floor, cardboard target",
        "Place obstacle at 15cm, 30cm, 50cm, 100cm, 200cm. Record DIST telemetry readings.",
        "Sensor error <= ±1.0 cm at distances < 100cm; <= ±3.0 cm at 200cm.",
        "Ultrasonic acoustic accuracy",
    ),
    (
        "TC-US-02",
        "Ultrasonic Emergency Stop Override (<15cm)",
        "Rover driving forward on ground toward wall at 200 PWM",
        "Rover approaches barrier at 15cm threshold. Observe motor cutoff independently of PC commands.",
        "Arduino immediately cuts PWM to 0 at distance < 15.0 cm; status reports STATUS:STOP.",
        "Autonomous safety hardware override",
    ),
    (
        "TC-US-03",
        "Acoustic Glancing Angle & Specular Reflection",
        "Flat acrylic sheet angled at 15°, 30°, 45°, 60° to sensor beam",
        "Measure distance reported at 50 cm distance across different incidence angles.",
        "Valid echo returned up to 30°; beyond 45° specular reflection may report -1 (out of range).",
        "HC-SR04 beam boundary limitations",
    ),
    (
        "TC-US-04",
        "Echo Timeout & Missing Target Recovery",
        "No obstacle in range (> 4.5m)",
        "Trigger HC-SR04 pulse; record timeout duration in pulseIn().",
        "Firmware completes in 30ms timeout without locking CPU; reports DIST:-1.",
        "Non-blocking safety loop verification",
    ),
    # Communication & Watchdog Tests
    (
        "TC-COM-01",
        "Communication Timeout Watchdog",
        "Rover driving forward ('F')",
        "Disconnect UART TX wire or pause transmission for > 3000 ms.",
        "Arduino watchdog timer expires at exactly 3000 ms; motors halt immediately; STATUS:STOP.",
        "Failsafe loss of signal (LOS) interlock",
    ),
    (
        "TC-COM-02",
        "Invalid Command Packet Rejection",
        "Arduino listening at 9600 baud",
        "Transmit corrupted or invalid characters ('X', '1', '\\x00', 'FAST').",
        "Arduino ignores invalid commands, remains stopped/previous state, returns STATUS:ERROR.",
        "Serial buffer validation",
    ),
    (
        "TC-COM-03",
        "Baud Rate & Frame Synchronization",
        "PySerial connected at 9600-8-N-1",
        "Stream 1000 consecutive movement commands at 20 Hz rate.",
        "Zero frame errors, 0 dropped characters, 100% command execution rate.",
        "UART throughput and signal integrity",
    ),
    (
        "TC-COM-04",
        "Telemetry Streaming Rate Verification",
        "Oscilloscope / serial timestamp logger",
        "Record arrival timestamps of DIST telemetry packets from Arduino.",
        "Telemetry packets arrive at strictly 200 ms ± 10 ms interval.",
        "Microcontroller loop timing stability",
    ),
    # Camera & Vision Sensor Tests
    (
        "TC-CAM-01",
        "OV2640 Frame Acquisition & Resolution",
        "ESP32-CAM powered, camera initialized",
        "Capture frame buffer via esp_camera_fb_get(). Inspect dimensions and pixel format.",
        "Resolution is exactly 640x480 (VGA), PIXFORMAT_JPEG, length > 10 KB.",
        "Camera sensor driver verification",
    ),
    (
        "TC-CAM-02",
        "Camera Frame Rate (FPS) Stability",
        "Static indoor scene, 5V / 2A bench supply",
        "Count captured frames over 60 seconds at VGA resolution.",
        "Sustained frame rate >= 12.0 FPS without camera FIFO overflow.",
        "Video capture pipeline throughput",
    ),
    (
        "TC-CAM-03",
        "Camera Frozen Frame Watchdog",
        "Frame manager thread active",
        "Simulate camera disconnect or halt frame arrival for > 3.0 seconds.",
        "SafetyManager detects frozen buffer timeout (>3.0s); autonomous movement inhibited.",
        "Visual sensor failure interlock",
    ),
    (
        "TC-CAM-04",
        "CLAHE & Preprocessing Image Normalization",
        "Low-contrast indoor lighting (100 lux)",
        "Process frame through enhance_clahe and sharpen filters. Compute histogram spread.",
        "Dynamic range of histogram expands; edges sharpened in < 15 ms execution time.",
        "Preprocessing pipeline efficiency",
    ),
    # AI & Perception Tests
    (
        "TC-AI-01",
        "Target Object Detection Confidence (Center)",
        "Target object placed in optical center at 1.0m",
        "Run detector on 20 consecutive frames. Record confidence scores.",
        "Mean confidence >= 0.70; bounding box centered within normalized [0.45, 0.55].",
        "Perception accuracy under nominal conditions",
    ),
    (
        "TC-AI-02",
        "False Positive Immunity (Empty Scene)",
        "Neutral white/beige wall with no target objects",
        "Run detector on 50 consecutive frames. Record false detections.",
        "Zero target detections above 0.50 confidence threshold (False Positive Rate < 2%).",
        "Classifier specificity",
    ),
    (
        "TC-AI-03",
        "Low Confidence Filtering & Suppression",
        "Target placed at 3.5m distance in dim light",
        "Record detection score. Verify behavior when confidence < 0.50.",
        "Detector rejects bounding box when confidence < 0.50; rover remains in SEARCHING state.",
        "Confidence threshold validation",
    ),
    (
        "TC-AI-04",
        "Multiple Object Disambiguation",
        "Two target objects placed at different distances (1m and 2m)",
        "Feed frame to ObjectTracker. Observe which bounding box is prioritized.",
        "Tracker locks onto primary/largest target bounding box consistently.",
        "Object tracking arbitration",
    ),
    (
        "TC-AI-05",
        "Target Disappearance & Search Fallback",
        "Target centered, rover approaching",
        "Abruptly remove target from camera field of view.",
        "Rover retains target lock for 1.0s, then transitions safely to SEARCHING mode.",
        "Target occlusion / loss handling",
    ),
    # Environmental & Lighting Robustness Tests
    (
        "TC-ENV-01",
        "Low Illumination Robustness (<50 lux)",
        "Dimmable laboratory test room, light meter at 30 lux",
        "Present target at 1.0m distance. Record detection rate and confidence.",
        "Target successfully identified or graceful fallback to SEARCHING without crash.",
        "Low-light perception limits",
    ),
    (
        "TC-ENV-02",
        "High Illumination & Direct Glare (>1500 lux)",
        "High-intensity spotlight directed toward camera lens",
        "Assess frame overexposure and auto-gain recovery.",
        "OV2640 AGC/AEC recovers in < 1.0 second; no firmware lockup.",
        "Sensor glare tolerance",
    ),
    (
        "TC-ENV-03",
        "Motion Blur During Rapid Pivot Turns",
        "Rover executing 'L' spin turn at 200 PWM",
        "Capture frames during angular rotation. Evaluate detector bounding box jitter.",
        "Frame skipping ignores blurred intermediate frames; locks when paused or stabilized.",
        "Rotational blur mitigation",
    ),
    # Navigation & State Machine Tests
    (
        "TC-NAV-01",
        "Vision Zone Steering Mapping (Left Sector)",
        "Target placed in left sector (x_center = 0.20)",
        "Evaluate DecisionEngine output.",
        "DecisionEngine outputs state ALIGNING, command 'L' (turn left).",
        "Steering logic verification",
    ),
    (
        "TC-NAV-02",
        "Vision Zone Steering Mapping (Center Sector)",
        "Target placed in center sector (x_center = 0.50)",
        "Evaluate DecisionEngine output.",
        "DecisionEngine outputs state APPROACHING, command 'F' (drive straight).",
        "Straight tracking verification",
    ),
    (
        "TC-NAV-03",
        "Vision Zone Steering Mapping (Right Sector)",
        "Target placed in right sector (x_center = 0.80)",
        "Evaluate DecisionEngine output.",
        "DecisionEngine outputs state ALIGNING, command 'R' (turn right).",
        "Steering logic verification",
    ),
    (
        "TC-NAV-04",
        "Anti-Oscillation Deadband Stability",
        "Target positioned at border (x_center = 0.52 to 0.48)",
        "Observe command sequence over 30 cycles.",
        "No rapid chattering between 'L' and 'R'; center tolerance (±0.06) holds 'F'.",
        "Control oscillation prevention",
    ),
    (
        "TC-NAV-05",
        "Target Proximity Termination (Stop Ratio)",
        "Rover approaches target until bbox width ratio > 0.45",
        "Record commanded movement.",
        "DecisionEngine detects width_ratio > 0.45; transitions to STOPPED; issues 'S'.",
        "Goal completion boundary",
    ),
    (
        "TC-NAV-06",
        "Search Mode Timeout & Rotation Limit",
        "Target completely absent from room",
        "Initiate search mode. Monitor search duration and rotations.",
        "Rover halts after 30.0s timeout or 2 complete rotations; transitions to STOPPED.",
        "Search space bounding",
    ),
    # Electrical, Power & Fault Injection Tests
    (
        "TC-PWR-01",
        "Battery Voltage Sag Under Motor Stall",
        "Fresh 2S Li-ion battery (8.2V), dual motor stall induced for 1.0s",
        "Log 5.0V buck converter output voltage using digital storage oscilloscope.",
        "Buck converter 5.0V logic rail remains >= 4.85V; NO micro resets occur on ESP32 or UNO.",
        "Power decoupling and brownout resilience",
    ),
    (
        "TC-PWR-02",
        "Arduino Hardware Reset Fault Injection",
        "Rover in autonomous tracking mode",
        "Momentarily press Arduino onboard RESET button.",
        "Motors immediately disengage; system re-initializes cleanly in < 1.5s into STOPPED state.",
        "Hardware reset fault tolerance",
    ),
    (
        "TC-PWR-03",
        "Long-Duration Autonomous Endurance (30 Minutes)",
        "Continuous tracking loop in obstacle-free arena",
        "Monitor temperature of L298N heatsink and ESP32-CAM SoC every 5 minutes.",
        "L298N temp < 65°C; ESP32-CAM temp < 60°C; zero memory leaks or task freeze.",
        "Thermal and system stability",
    ),
]


def generate_test_templates():
    os.makedirs("data", exist_ok=True)
    os.makedirs("docs/testing", exist_ok=True)

    # 1. Generate data/test_results.csv
    csv_path = "data/test_results.csv"
    headers = [
        "test_id",
        "date",
        "scenario",
        "lighting",
        "target_distance",
        "target_position",
        "confidence",
        "command",
        "obstacle_distance",
        "response_time_ms",
        "result",
        "notes",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        # Write template rows with IDs from test cases
        for tc in TEST_CASES_DATA:
            writer.writerow(
                [
                    tc[0],
                    "",
                    tc[1],
                    "[LIGHTING]",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "[TO PERFORM]",
                    tc[5],
                ]
            )
    print(f"[OK] Generated {csv_path}")

    # 2. Generate data/test_results.xlsx
    xlsx_path = "data/test_results.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Test Results"

    ws.merge_cells("A1:L1")
    title_cell = ws["A1"]
    title_cell.value = "AI ROVER PHYSICAL EXPERIMENTAL TEST RESULTS LOG"
    title_cell.font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    title_cell.fill = PatternFill(
        start_color="1565C0", end_color="1565C0", fill_type="solid"
    )
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 35

    ws.merge_cells("A2:L2")
    sub_cell = ws["A2"]
    sub_cell.value = "Standard Verification Template (Fields marked [TO PERFORM] must be filled during lab execution - NO FAKE DATA)"
    sub_cell.font = Font(name="Calibri", size=10, italic=True, color="333333")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

    header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    header_fill = PatternFill(
        start_color="283593", end_color="283593", fill_type="solid"
    )
    border_thin = Border(
        left=Side(style="thin", color="DDDDDD"),
        right=Side(style="thin", color="DDDDDD"),
        top=Side(style="thin", color="DDDDDD"),
        bottom=Side(style="thin", color="DDDDDD"),
    )

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for idx, tc in enumerate(TEST_CASES_DATA, 1):
        r = 4 + idx
        ws.row_dimensions[r].height = 20
        ws.cell(row=r, column=1, value=tc[0]).alignment = Alignment(horizontal="center")
        ws.cell(row=r, column=2, value="").alignment = Alignment(horizontal="center")
        ws.cell(row=r, column=3, value=tc[1])
        ws.cell(row=r, column=4, value="Standard (300 lux)").alignment = Alignment(
            horizontal="center"
        )
        ws.cell(row=r, column=5, value="").alignment = Alignment(horizontal="right")
        ws.cell(row=r, column=6, value="").alignment = Alignment(horizontal="center")
        ws.cell(row=r, column=7, value="").alignment = Alignment(horizontal="right")
        ws.cell(row=r, column=8, value="").alignment = Alignment(horizontal="center")
        ws.cell(row=r, column=9, value="").alignment = Alignment(horizontal="right")
        ws.cell(row=r, column=10, value="").alignment = Alignment(horizontal="right")
        res_cell = ws.cell(row=r, column=11, value="[TO PERFORM]")
        res_cell.alignment = Alignment(horizontal="center")
        res_cell.font = Font(color="777777", italic=True)
        ws.cell(row=r, column=12, value=tc[5])

        for c in range(1, 13):
            ws.cell(row=r, column=c).border = border_thin

    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = 18
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["C"].width = 38
    ws.column_dimensions["L"].width = 30

    wb.save(xlsx_path)
    print(f"[OK] Generated {xlsx_path}")

    # 3. Generate docs/testing/TEST_CASES.md (and docs/25_TEST_PLAN.md)
    generate_markdown_test_cases()
    generate_experiment_templates()


def generate_markdown_test_cases():
    md = """# 25. System Test Plan & Verification Matrix

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

"""
    for tc in TEST_CASES_DATA:
        md += f"""### Test Case {tc[0]}: {tc[1]}

| Parameter | Specification / Field Record |
| :--- | :--- |
| **Test ID** | `{tc[0]}` |
| **Objective** | {tc[1]} |
| **Setup & Preconditions** | {tc[2]} |
| **Procedure** | {tc[3]} |
| **Expected Outcome** | {tc[4]} |
| **Actual Measured Result** | `[TO PERFORM EXPERIMENTALLY — FIELD MEASUREMENT REQUIRED]` |
| **Status (Pass / Fail)** | `[PENDING PHYSICAL VERIFICATION]` |
| **Subsystem Tested** | {tc[5]} |
| **Engineering Notes** | Do not populate actual results without physical test bench execution. |

---

"""
    with open("docs/25_TEST_PLAN.md", "w", encoding="utf-8") as f:
        f.write(md)
    print("[OK] Generated docs/25_TEST_PLAN.md")


def generate_experiment_templates():
    experiments = [
        (
            "E01",
            "Motor Characterization & Speed Calibration",
            "Measure rotational speed (RPM) and linear rover velocity (m/s) as a function of PWM duty cycle (60 to 255 in steps of 20).",
            [
                "PWM Duty Cycle (0-255)",
                "Left Wheel RPM",
                "Right Wheel RPM",
                "Measured Linear Speed (m/s)",
                "Current Draw (mA)",
            ],
        ),
        (
            "E02",
            "Ultrasonic Ranging Accuracy & Cone Angle",
            "Evaluate HC-SR04 distance measurement error across distances from 5 cm to 250 cm and incidence angles from 0° to 45°.",
            [
                "True Distance (cm)",
                "Sensor Reading (cm)",
                "Absolute Error (cm)",
                "Percentage Error (%)",
                "Incidence Angle (deg)",
            ],
        ),
        (
            "E03",
            "AI Inference Latency & Resource Footprint",
            "Benchmark inference time, frames per second (FPS), heap memory consumption, and CPU core utilization across different models.",
            [
                "Model Architecture",
                "Input Resolution",
                "Inference Latency (ms)",
                "Effective FPS",
                "RAM / PSRAM Used (KB)",
            ],
        ),
        (
            "E04",
            "Target Detection Recall & Precision vs Distance",
            "Record true positives, false positives, and missed detections as the target object distance varies from 0.5m to 4.0m.",
            [
                "Distance (m)",
                "Lighting (lux)",
                "True Positives",
                "False Positives",
                "Confidence Score",
            ],
        ),
        (
            "E05",
            "Proportional Steering Gain (Kp) Comparison",
            "Compare heading settling time, overshoot, and lateral trajectory stability for Kp = 0.2, 0.4, 0.6, 0.8, 1.2 in simulation and hardware.",
            [
                "Kp Value",
                "Rise Time (s)",
                "Overshoot (%)",
                "Settling Time (s)",
                "Steady-State Error (deg)",
            ],
        ),
        (
            "E06",
            "Target Visual Alignment & Deadband Tolerance",
            "Measure robot heading alignment accuracy when stopping in front of the target, and observe the effect of center tolerance band (±0.06).",
            [
                "Initial Heading Offset (deg)",
                "Final Heading Offset (deg)",
                "Cycles to Align",
                "Oscillation Count",
                "Status",
            ],
        ),
        (
            "E07",
            "Autonomous Navigation & Goal Approach",
            "Record total mission completion time, path efficiency, and terminal stopping distance from starting positions at 1m, 2m, and 3m.",
            [
                "Trial #",
                "Initial Distance (m)",
                "Time to Target (s)",
                "Final Stop Bounding Box Width",
                "Final Stoppage Distance (cm)",
            ],
        ),
        (
            "E08",
            "Obstacle Detection & Safety Override Integrity",
            "Evaluate obstacle braking distance and hardware override response when an obstacle is suddenly introduced into the rover's path.",
            [
                "Approach Velocity (m/s)",
                "Obstacle Insertion Distance (cm)",
                "Braking Distance (cm)",
                "Stopping Margin to Impact (cm)",
                "Watchdog Tripped",
            ],
        ),
        (
            "E09",
            "Communication Link Reliability & Timeout Response",
            "Evaluate packet delivery ratio, UART bit error rate, and exact watchdog trigger timing under varying transmission frequencies.",
            [
                "Packet Rate (Hz)",
                "Packets Sent",
                "Packets Received",
                "Drop Rate (%)",
                "Watchdog Cutoff Latency (ms)",
            ],
        ),
        (
            "E10",
            "Environmental Illumination Robustness Sweep",
            "Measure target detection confidence and tracking success across ambient lighting levels: 10 lux (dark), 100 lux (dim), 500 lux (office), 2000 lux (bright).",
            [
                "Illumination (lux)",
                "Frame Contrast",
                "Mean Target Confidence",
                "Tracking Lost Events",
                "Classification Accuracy",
            ],
        ),
        (
            "E11",
            "Long-Duration Operational Thermal & Power Profiling",
            "Profile battery discharge curve, voltage sag, component temperatures (L298N, ESP32, Arduino), and heap stability over a 45-minute continuous run.",
            [
                "Time (minutes)",
                "Battery Voltage (V)",
                "Logic Rail (V)",
                "L298N Temp (°C)",
                "ESP32 Temp (°C)",
                "Operational Status",
            ],
        ),
    ]

    os.makedirs("experiments", exist_ok=True)
    exp_md = """# 26. Experimental Methodology & Evaluation Protocols

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

"""
    for exp_id, title, objective, cols in experiments:
        exp_md += f"""## Protocol {exp_id}: {title}

### 1. Objective
{objective}

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

| {" | ".join(cols)} |
| {" | ".join([":---:"] * len(cols))} |
| {" | ".join(["[TO RECORD]"] * len(cols))} |
| {" | ".join(["[TO RECORD]"] * len(cols))} |
| {" | ".join(["[TO RECORD]"] * len(cols))} |
| {" | ".join(["[TO RECORD]"] * len(cols))} |
| {" | ".join(["[TO RECORD]"] * len(cols))} |

*Note: All numerical entries must be populated from calibrated physical test bench measurements.*

---

"""
    with open("docs/26_EXPERIMENTAL_METHODOLOGY.md", "w", encoding="utf-8") as f:
        f.write(exp_md)
    print("[OK] Generated experimental protocol templates E01-E11 in docs/26.")


if __name__ == "__main__":
    generate_test_templates()
