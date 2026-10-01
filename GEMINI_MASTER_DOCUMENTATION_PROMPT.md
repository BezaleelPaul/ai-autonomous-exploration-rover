# GEMINI CLI — MASTER PROJECT DOCUMENTATION GENERATOR

You are the lead technical documentation engineer, robotics engineer,
embedded systems engineer, control-systems engineer, AI/edge-computing
engineer, scientific illustrator, and Python automation engineer.

Your task is to create a COMPLETE, PROFESSIONAL, BUILD-READY documentation
and report-generation system for this project.

============================================================
PROJECT
============================================================

Title:

AI-Based Vision-Guided Differential Drive Rover with
Distributed Edge Intelligence and Safety Control

Core architecture:

ESP32
  ├── Camera
  ├── AI inference
  ├── Visual perception
  ├── Target detection
  ├── Target position estimation
  └── Decision making
          |
          | high-level movement command
          v
Arduino UNO
  ├── Command validation
  ├── Motor PWM
  ├── Motor direction
  ├── HC-SR04
  ├── Safety override
  ├── Communication watchdog
  └── Emergency stop
          |
          v
L298N
  ├── Left motor
  └── Right motor

Laptop:
Development / debugging / data analysis / documentation only.

The final autonomous robot must NOT secretly depend on the laptop for
AI inference or decision making.

============================================================
CRITICAL RULE
============================================================

DO NOT FABRICATE:

- hardware specifications
- ESP32 GPIO mappings
- AI capabilities
- model performance
- inference latency
- accuracy
- experimental results
- circuit connections
- battery specifications
- motor specifications

If information is unavailable, explicitly mark:

[TO VERIFY]

If something is an engineering assumption:

[ASSUMPTION]

If experimentally measured:

[MEASURED]

If a design choice:

[DESIGN DECISION]

Never turn an assumption into a fact.

============================================================
PHASE 0 — INSPECT THE PROJECT
============================================================

Before generating anything:

1. Inspect the current directory.
2. Inspect all existing files.
3. Identify existing source code.
4. Identify existing documentation.
5. Identify hardware information.
6. Identify exact ESP32 board if documented.
7. Identify exact camera.
8. Identify existing Arduino code.
9. Identify existing diagrams.
10. Identify existing test data.

DO NOT overwrite useful existing work.

Create:

docs/project_inventory.md

containing:

- existing files
- purpose
- status
- reusable components
- missing information
- risks

============================================================
PHASE 1 — VERIFY HARDWARE
============================================================

Create:

docs/hardware/HARDWARE_VERIFICATION.md

Required information:

Arduino:
- exact board
- operating voltage
- available PWM pins

ESP32:
- exact board
- exact chip
- RAM
- PSRAM
- flash
- camera
- camera interface
- supported AI framework

Camera:
- model
- resolution
- interface

Motor:
- voltage
- current
- gear ratio
- wheel diameter

Motor driver:
- model
- voltage
- current
- logic interface

Sensor:
- HC-SR04
- operating voltage
- trigger/echo pins

Battery:
- chemistry
- voltage
- capacity
- maximum current

If exact information is unavailable, DO NOT guess.

Create a clearly visible:

HARDWARE INFORMATION REQUIRED

checklist.

============================================================
PHASE 2 — CREATE PYTHON DOCUMENTATION SYSTEM
============================================================

Create:

tools/
  generate_docs.py
  generate_diagrams.py
  generate_figures.py
  generate_tables.py
  generate_report.py
  generate_pdf.py
  validate_docs.py
  simulate_control.py
  create_test_templates.py
  create_bom.py

Create:

requirements.txt

Use Python libraries where appropriate:

python-docx
reportlab
matplotlib
numpy
pandas
Pillow
networkx
svgwrite
jinja2
openpyxl
qrcode

Use Graphviz only when available.

The Python system must generate all reproducible diagrams and documents.

============================================================
PHASE 3 — DIRECTORY STRUCTURE
============================================================

Create:

project/
│
├── docs/
│   ├── architecture/
│   ├── hardware/
│   ├── ai/
│   ├── control/
│   ├── testing/
│   ├── research/
│   ├── troubleshooting/
│   ├── figures/
│   └── generated/
│
├── diagrams/
├── figures/
├── data/
├── experiments/
├── reports/
├── tools/
├── esp32/
├── arduino/
└── README.md

============================================================
PHASE 4 — DOCUMENTS TO GENERATE
============================================================

Generate all of these:

01_PROJECT_OVERVIEW.md
02_ABSTRACT.md
03_PROBLEM_STATEMENT.md
04_MOTIVATION.md
05_OBJECTIVES.md
06_SCOPE.md
07_SYSTEM_ARCHITECTURE.md
08_HARDWARE_ARCHITECTURE.md
09_SOFTWARE_ARCHITECTURE.md
10_ESP32_AI_PIPELINE.md
11_AI_MODEL_SELECTION.md
12_TARGET_DETECTION.md
13_DECISION_ENGINE.md
14_DIFFERENTIAL_DRIVE_PHYSICS.md
15_CONTROL_SYSTEM.md
16_ARDUINO_MOTOR_CONTROL.md
17_ULTRASONIC_SAFETY.md
18_COMMUNICATION_PROTOCOL.md
19_STATE_MACHINE.md
20_POWER_ARCHITECTURE.md
21_CIRCUIT_CONNECTIONS.md
22_PIN_CONFIGURATION.md
23_BUILD_GUIDE.md
24_CALIBRATION_GUIDE.md
25_TEST_PLAN.md
26_EXPERIMENTAL_METHODOLOGY.md
27_RESULTS_TEMPLATE.md
28_FAILURE_ANALYSIS.md
29_LIMITATIONS.md
30_FUTURE_WORK.md
31_BILL_OF_MATERIALS.md
32_TROUBLESHOOTING.md
33_FINAL_DEMO.md
34_RESEARCH_NOTES.md
35_FINAL_REPORT_OUTLINE.md

============================================================
PHASE 5 — PROFESSIONAL DIAGRAMS
============================================================

Use Python to generate actual diagrams.

Do NOT use fake AI-generated circuit images.

Generate:

01_system_architecture.png
02_data_flow.png
03_hardware_architecture.png
04_power_architecture.png
05_esp32_pipeline.png
06_decision_pipeline.png
07_arduino_pipeline.png
08_safety_hierarchy.png
09_state_machine.png
10_control_loop.png
11_differential_drive_geometry.png
12_target_position.png
13_left_center_right_zones.png
14_communication_protocol.png
15_full_robot_block_diagram.png

All diagrams must have:

- title
- labels
- arrows
- readable text
- legend where necessary
- consistent typography
- high resolution
- white background
- suitable dimensions for A4 reports

============================================================
PHASE 6 — CIRCUIT DIAGRAM
============================================================

Generate a technical circuit diagram.

IMPORTANT:

Never generate a circuit diagram until actual pin assignments have been
verified.

Use SVG/vector generation with Python where practical.

The diagram must distinguish:

POWER
GROUND
SIGNAL

Use labels:

Arduino UNO
ESP32
L298N
HC-SR04
LEFT MOTOR
RIGHT MOTOR
BATTERY
BUCK CONVERTER

Show:

- motor power
- logic power
- common ground
- signal connections

Do not connect motors directly to Arduino GPIO.

Do not power motors from Arduino 5V.

============================================================
PHASE 7 — DIFFERENTIAL DRIVE FIGURE
============================================================

Generate a scientific diagram showing:

        FRONT
          ↑

LEFT WHEEL       RIGHT WHEEL

      <--- L --->

        ROBOT

Show:

wheel radius r
wheel separation L
left velocity
right velocity
linear velocity v
angular velocity omega

Include equations:

v = r/2 (ωR + ωL)

ω = r/L (ωR - ωL)

============================================================
PHASE 8 — AI PIPELINE FIGURE
============================================================

Generate:

CAMERA
 ↓
IMAGE
 ↓
PREPROCESSING
 ↓
AI INFERENCE
 ↓
DETECTION
 ↓
CONFIDENCE FILTER
 ↓
TARGET POSITION
 ↓
DECISION ENGINE
 ↓
COMMAND
 ↓
ARDUINO

Clearly identify ESP32 boundary.

============================================================
PHASE 9 — CONTROL THEORY
============================================================

Explain:

target_center_x
image_center_x

error:

e = target_center_x - image_center_x

Simple proportional steering:

ω = Kp e

Generate Python simulation plots.

Simulate multiple Kp values.

Generate:

control_response_kp_comparison.png

Plot:

- target error
- response
- overshoot
- settling behaviour

DO NOT claim this simulation represents the real rover.

Clearly label:

SIMULATION — NOT MEASURED HARDWARE DATA

============================================================
PHASE 10 — PHYSICS
============================================================

Generate documentation for:

- differential drive
- wheel velocity
- angular velocity
- turning radius
- linear velocity
- angular velocity
- wheel slip
- motor mismatch
- acceleration
- stopping distance

Where formulas require assumptions, state assumptions.

============================================================
PHASE 11 — AI MODEL SELECTION
============================================================

Do NOT blindly select YOLO/DETR.

Determine:

ESP32 variant
RAM
PSRAM
flash
camera
framework

Then create:

AI_MODEL_COMPARISON.md

Compare feasible approaches.

Columns:

Model
Framework
Memory
Input Resolution
Expected Speed
Accuracy Tradeoff
ESP32 Compatibility
Implementation Complexity

If exact benchmark data is unavailable:

write:

NOT BENCHMARKED ON TARGET HARDWARE

Do not invent performance.

============================================================
PHASE 12 — TARGET POSITION
============================================================

Generate an image showing:

+--------------------------------+
| LEFT | CENTER | RIGHT          |
|      |        |                |
|      | TARGET |                |
+--------------------------------+

Calculate:

target_center_x = x + width/2

error = target_center_x - image_center_x

Generate documentation explaining how this produces steering direction.

============================================================
PHASE 13 — ARDUINO SAFETY
============================================================

Generate:

safety architecture

Priority:

1. Emergency stop
2. Obstacle safety
3. Communication watchdog
4. Invalid command
5. AI confidence
6. Navigation command

Every movement command must pass safety validation.

Default failure state:

STOP

Generate safety flowchart.

============================================================
PHASE 14 — COMMUNICATION
============================================================

Document the ESP32 → Arduino protocol.

Possible baseline:

F
B
L
R
S
E

Or structured packets.

The final protocol must include:

- command
- validation
- timeout
- invalid command handling
- emergency stop

Do not create unnecessary protocol complexity.

Generate:

communication_protocol.png

============================================================
PHASE 15 — TESTING
============================================================

Create:

data/test_results.csv

with columns:

test_id
date
scenario
lighting
target_distance
target_position
confidence
command
obstacle_distance
response_time_ms
result
notes

Generate:

data/test_results.xlsx

using openpyxl.

Create formulas where useful.

Do not insert fake results.

============================================================
PHASE 16 — TEST CASES
============================================================

Generate at least 30 test cases.

Include:

motor tests
camera tests
AI tests
target detection
false positives
false negatives
low confidence
obstacle
communication loss
Arduino reset
ESP32 reset
camera failure
low light
bright light
motion blur
multiple objects
target disappearance
emergency stop
battery issue
long duration operation

Each test:

ID
Objective
Setup
Procedure
Expected
Actual
Pass/Fail
Evidence
Notes

Actual must remain blank until experimentally performed.

============================================================
PHASE 17 — EXPERIMENTS
============================================================

Create experimental templates for:

E01 Motor characterization
E02 Ultrasonic accuracy
E03 AI inference
E04 Target detection
E05 Kp comparison
E06 Target alignment
E07 Navigation
E08 Obstacle safety
E09 Communication reliability
E10 Lighting robustness
E11 Long-duration operation

Generate tables automatically.

============================================================
PHASE 18 — BILL OF MATERIALS
============================================================

Generate:

BOM.csv
BOM.xlsx
BILL_OF_MATERIALS.md

Columns:

Component
Quantity
Specification
Purpose
Required
Optional
Existing
Need to Buy
Price
Source
Notes

Do not invent current prices.

Use:

PRICE TO VERIFY

when unknown.

============================================================
PHASE 19 — 360-DEGREE EXTENSION
============================================================

Document as OPTIONAL.

Potential method:

ESP32-CAM
+
servo

Scan:

0
45
90
135
180
225
270
315 degrees

Generate:

360_degree_scan_diagram.png

Call it:

DISCRETE PANORAMIC SCANNING

Do not claim continuous 360-degree vision.

============================================================
PHASE 20 — SELF-BALANCING
============================================================

DO NOT include self-balancing in the baseline system.

Document it only under:

Future Work / Possible Extension

Explain:

- inverted pendulum
- IMU
- PID
- high-torque motors
- additional control complexity

Do not allow it to distract from the baseline rover.

============================================================
PHASE 21 — DOCUMENT QUALITY
============================================================

Every Markdown file must:

- have a title
- have purpose
- explain concepts
- contain diagrams where useful
- reference figures
- include assumptions
- include limitations
- avoid unexplained jargon

Use engineering language appropriate for a B.Tech project.

Do not write like marketing material.

Avoid phrases such as:

"revolutionary"
"groundbreaking"
"state-of-the-art"

unless backed by evidence.

============================================================
PHASE 22 — REFERENCES
============================================================

Create:

docs/references.md

Prioritize:

official Espressif documentation
Arduino documentation
STMicroelectronics/L298 documentation
HC-SR04 documentation
official framework documentation
peer-reviewed papers
reputable technical references

Do not cite random blogs when an official source exists.

For every technical claim that depends on external information,
record the source.

============================================================
PHASE 23 — FINAL REPORT
============================================================

Generate:

reports/
  AI_Rover_Final_Report.docx
  AI_Rover_Final_Report.pdf

The report must include:

Cover Page
Certificate Placeholder
Declaration Placeholder
Acknowledgement
Abstract
Table of Contents
List of Figures
List of Tables

Chapter 1:
Introduction

Chapter 2:
Problem Definition

Chapter 3:
Objectives

Chapter 4:
Literature/Technical Background

Chapter 5:
System Architecture

Chapter 6:
Hardware Design

Chapter 7:
Software Design

Chapter 8:
AI Design

Chapter 9:
Control and Physics

Chapter 10:
Safety

Chapter 11:
Implementation

Chapter 12:
Testing

Chapter 13:
Experimental Methodology

Chapter 14:
Results

Chapter 15:
Limitations

Chapter 16:
Future Work

Chapter 17:
Conclusion

References

Appendices

IMPORTANT:

Results chapter must contain placeholders if experiments have not yet
been performed.

Never manufacture results.

============================================================
PHASE 24 — FIGURE QUALITY
============================================================

Use Python-generated figures.

Use:

matplotlib
Pillow
networkx
svgwrite

Figures should be:

- 300 DPI
- readable
- consistent typography
- A4 compatible
- vector where possible

Generate captions automatically.

Example:

Figure 5.1:
High-level architecture of the proposed distributed edge-intelligence
robotic system.

============================================================
PHASE 25 — FINAL VALIDATION SCRIPT
============================================================

Create:

tools/validate_docs.py

It must check:

- broken internal links
- missing figures
- missing referenced files
- duplicate headings
- empty sections
- missing required documents
- unresolved [TO VERIFY]
- unresolved [ASSUMPTION]
- missing references
- missing figure captions

Print:

DOCUMENTATION VALIDATION REPORT

============================================================
PHASE 26 — FINAL PROJECT AUDIT
============================================================

Create:

docs/FINAL_AUDIT.md

Sections:

TECHNICAL FEASIBILITY
HARDWARE FEASIBILITY
AI FEASIBILITY
SOFTWARE FEASIBILITY
SAFETY
RESEARCH QUALITY
DOCUMENTATION QUALITY
TIME RISK
COST RISK

Then produce:

CRITICAL BLOCKERS
HIGH PRIORITY
MEDIUM PRIORITY
OPTIONAL

Do NOT rank the project itself.

This is an engineering risk classification, not a project quality rating.

============================================================
PHASE 27 — GENERATION ORDER
============================================================

Execute in this order:

1. Inspect repository
2. Identify hardware
3. Create project inventory
4. Create documentation structure
5. Create Python tools
6. Generate verified diagrams
7. Generate technical Markdown
8. Generate test templates
9. Generate Excel data templates
10. Generate DOCX
11. Generate PDF
12. Validate all documents
13. Generate final audit
14. Generate README
15. Print final status

============================================================
FINAL OUTPUT
============================================================

At the end print:

PROJECT DOCUMENTATION GENERATION COMPLETE

Then show:

Files generated:
<number>

Figures generated:
<number>

Tables generated:
<number>

Test cases:
<number>

Experiments:
<number>

Unresolved hardware questions:
<number>

Unresolved assumptions:
<number>

Validation errors:
<number>

Validation warnings:
<number>

Most critical next actions:
1.
2.
3.
4.
5.

DO NOT claim the project is hardware-ready until the physical hardware
has actually been verified.
