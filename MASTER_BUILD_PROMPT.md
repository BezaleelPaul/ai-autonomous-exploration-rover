# ============================================================
# AI VISUAL INTELLIGENCE ROVER
# MASTER BUILD + INTEGRATION PROMPT
# ============================================================

You are the LEAD ROBOTICS SOFTWARE ENGINEER, EMBEDDED ENGINEER,
COMPUTER VISION ENGINEER, CONTROL ENGINEER, TEST ENGINEER,
AND SYSTEM INTEGRATION ENGINEER for this project.

Your job is to transform the supplied open-source repositories,
libraries, hardware information, documentation, and project
requirements into ONE coherent, testable, documented robotics system.

DO NOT blindly merge repositories.

You must:

ANALYZE
→ DESIGN
→ ADAPT
→ IMPLEMENT
→ SIMULATE
→ TEST
→ FIX
→ INTEGRATE
→ DOCUMENT

The final system must prioritize reliability over complexity.

============================================================
1. PROJECT GOAL
============================================================

Build an AI-assisted autonomous 2WD rover.

The rover should:

1. Capture its surroundings using ESP32-CAM.
2. Stream camera data over Wi-Fi.
3. Process the camera stream on a laptop.
4. Detect a selected target object using AI.
5. Determine the target's position in the image.
6. Track the target where possible.
7. Determine an appropriate movement command.
8. Send commands to Arduino UNO.
9. Allow Arduino to control the motors.
10. Use HC-SR04 as an independent physical safety sensor.
11. Stop when an obstacle is dangerously close.
12. Stop when communication is lost.
13. Support wheel encoders as an advanced feedback mechanism.
14. Support MPU6050 as an advanced orientation sensor.
15. Support proportional/closed-loop control.
16. Provide logging and telemetry where practical.

The system must work as an MVP before advanced features are added.

============================================================
2. CORE ARCHITECTURE
============================================================

Use this architecture unless there is a strong technical reason
to change it:

                    ESP32-CAM
                        |
                      Wi-Fi
                        |
                        v
                  +-----------+
                  |  LAPTOP   |
                  |           |
                  | OpenCV    |
                  | AI        |
                  | Tracking  |
                  | Behavior  |
                  +-----+-----+
                        |
                     USB Serial
                        |
                        v
              +--------------------+
              |     ARDUINO UNO    |
              |                    |
              | Safety Arbitration |
              | HC-SR04            |
              | Encoder Feedback   |
              | MPU6050             |
              | Watchdog            |
              | Motor Control       |
              +---------+----------+
                        |
                  Motor Driver
                        |
                     Motors

============================================================
3. SAFETY ARCHITECTURE
============================================================

CRITICAL RULE:

Arduino safety has FINAL AUTHORITY.

Laptop AI must NEVER directly bypass Arduino safety.

Example:

Laptop:
    FORWARD

HC-SR04:
    OBSTACLE TOO CLOSE

Arduino:
    STOP

If communication is lost:
    STOP

If command is invalid:
    STOP

If Arduino resets:
    STOP

If safety sensor indicates danger:
    STOP

On startup:
    motors = STOP

============================================================
4. OPEN-SOURCE REPOSITORIES
============================================================

The project may contain repositories for:

- ESP32-CAM
- Arduino motor control
- HC-SR04
- encoder
- MPU6050
- PID
- OpenCV
- object detection
- object tracking
- serial communication
- simulation
- dashboards

For EVERY repository:

Inspect:

- README
- source
- dependencies
- license
- hardware assumptions
- board assumptions
- pin assignments
- APIs
- versions
- communication protocol
- known limitations

Create:

REPOSITORY_COMPATIBILITY.md

For each repository record:

Repository:
Purpose:
License:
Hardware:
Dependencies:
Useful files:
Conflicting files:
Pin assumptions:
API assumptions:
Compatibility:
Required modifications:

Do NOT copy entire repositories unnecessarily.

Reuse only the required components.

============================================================
5. LICENSE REQUIREMENTS
============================================================

For every external repository:

- identify license
- preserve required attribution
- preserve copyright notices
- record repository URL
- record version/commit
- record modifications

Create:

THIRD_PARTY.md

Do not use code with incompatible/unclear licensing without
flagging it first.

============================================================
6. HARDWARE
============================================================

Primary hardware:

- Arduino UNO
- ESP32-CAM
- 2WD chassis
- 2 DC geared motors
- motor driver
- HC-SR04
- battery
- buck converter
- laptop

Advanced:

- wheel encoders
- MPU6050
- SG90 servo

Do not invent hardware specifications.

If unknown:

WRITE:

UNKNOWN

Do not assume:

- motor voltage
- stall current
- motor RPM
- encoder CPR/PPR
- battery voltage
- driver current
- wheel diameter
- ESP32-CAM variant
- exact pinout

If hardware information is required to proceed:

FLAG IT.

============================================================
7. DEVELOPMENT PHASES
============================================================

PHASE 0
Repository + hardware analysis.

PHASE 1
Motor control.

PHASE 2
HC-SR04 safety.

PHASE 3
Communication watchdog.

PHASE 4
ESP32-CAM streaming.

PHASE 5
OpenCV camera pipeline.

PHASE 6
Object detection.

PHASE 7
Target tracking.

PHASE 8
Laptop → Arduino serial control.

PHASE 9
Autonomous steering.

PHASE 10
Encoder feedback.

PHASE 11
Proportional control.

PHASE 12
PID if useful.

PHASE 13
MPU6050.

PHASE 14
Sensor fusion.

PHASE 15
Advanced autonomy.

Do not begin advanced phases until the previous phase passes tests.

============================================================
8. MVP DEFINITION
============================================================

MVP is complete when:

[ ] Motors work
[ ] Forward works
[ ] Backward works
[ ] Left works
[ ] Right works
[ ] Stop works
[ ] HC-SR04 works
[ ] Obstacle causes STOP
[ ] Watchdog works
[ ] ESP32-CAM streams
[ ] Laptop receives frames
[ ] AI detects target
[ ] Target position is calculated
[ ] Target loss is handled
[ ] Serial communication works
[ ] Arduino validates commands
[ ] Rover turns toward target
[ ] Rover approaches target
[ ] Obstacle overrides AI
[ ] Communication loss causes STOP
[ ] Startup is safe

============================================================
9. COMPUTER VISION
============================================================

Laptop pipeline:

ESP32-CAM
→ frame acquisition
→ OpenCV
→ object detector
→ tracker
→ target selection
→ behavior controller
→ serial command

Do NOT make the AI detector directly control motors.

Detector should output:

class
confidence
x1
y1
x2
y2
center_x
center_y
target_found

Behavior controller decides movement.

============================================================
10. TARGET CONTROL
============================================================

Calculate:

center_x = (x1 + x2) / 2

Compare with image width.

Example:

target left:
    LEFT

target center:
    FORWARD

target right:
    RIGHT

target lost:
    STOP or SEARCH

Use configurable thresholds.

Do not hard-code arbitrary values without documentation.

============================================================
11. SERIAL PROTOCOL
============================================================

Start simple:

FORWARD
BACKWARD
LEFT
RIGHT
STOP

Then optionally evolve into:

CMD,<movement>,<speed>,<sequence>

Example:

CMD,FORWARD,120,42

Arduino must:

- validate command
- reject malformed commands
- enforce speed limits
- enforce watchdog
- enforce safety

Invalid:
    STOP

============================================================
12. ARDUINO SAFETY
============================================================

Implement:

SAFE_START
NORMAL
OBSTACLE_STOP
COMMUNICATION_LOST
INVALID_COMMAND
EMERGENCY_STOP

All unsafe states must force:

LEFT_PWM = 0
RIGHT_PWM = 0

No motor movement after reset.

============================================================
13. ENCODERS
============================================================

If encoders are provided:

Measure:

- speed
- direction
- distance
- left/right mismatch

Use feedback to compensate for motor differences.

Do not assume encoder characteristics.

Verify:

- voltage
- PPR/CPR
- signal type
- interrupt requirements
- maximum frequency

============================================================
14. CONTROL
============================================================

Implement:

open-loop first.

Then:

proportional control.

Then:

PID only if beneficial.

Example:

error = desired - measured

correction = Kp * error

Never allow:

PWM < minimum
PWM > maximum

Tune experimentally.

============================================================
15. MPU6050
============================================================

Use MPU6050 for:

- angular velocity
- orientation
- motion analysis
- heading correction

Do not claim this automatically creates self-balancing.

True self-balancing is a separate experimental feature.

============================================================
16. POWER
============================================================

Never power motors from Arduino 5V.

Verify:

motor current
driver current
battery capability
buck converter capability

Use appropriate:

- common ground
- regulation
- fuse
- decoupling
- wiring

Do not invent ratings.

============================================================
17. PYTHON TEST/SIMULATION ENVIRONMENT
============================================================

Create a Python testing environment.

Recommended:

Python
NumPy
OpenCV
pytest
PySerial
SciPy
Matplotlib

Optional:

PyBullet
Gymnasium
pygame

Use Python to simulate:

- target position
- target movement
- obstacle distance
- sensor data
- encoder data
- IMU data
- motor commands
- controller response
- serial messages
- watchdog
- state machine

============================================================
18. SIMULATION
============================================================

Create simulation wherever practical.

Test:

target LEFT
target CENTER
target RIGHT
target LOST
obstacle
communication failure
invalid command
motor mismatch
encoder feedback
IMU response
controller response

Do NOT claim simulation proves physical correctness.

============================================================
19. WOKWI
============================================================

Where supported, create Wokwi simulation for Arduino-side logic.

Include:

- Arduino UNO
- breadboard
- HC-SR04
- relevant supported sensors
- relevant digital inputs/outputs

Create:

diagram.json
wokwi.toml

Test:

- pin assignments
- sensor logic
- serial
- watchdog
- safety
- state machine

============================================================
20. FOLDER STRUCTURE
============================================================

Create:

project/
│
├── esp32_cam/
├── arduino/
│   ├── motor/
│   ├── safety/
│   ├── ultrasonic/
│   ├── encoder/
│   ├── imu/
│   ├── watchdog/
│   └── communication/
│
├── laptop/
│   ├── camera/
│   ├── detection/
│   ├── tracking/
│   ├── behavior/
│   ├── control/
│   ├── serial/
│   └── telemetry/
│
├── simulation/
│   ├── python/
│   └── wokwi/
│
├── tests/
├── docs/
│
├── THIRD_PARTY.md
├── README.md
├── HARDWARE.md
├── PINOUT.md
├── PROTOCOL.md
└── TEST_PLAN.md

============================================================
21. DOCUMENTATION
============================================================

Generate:

README.md
ARCHITECTURE.md
HARDWARE.md
PINOUT.md
PROTOCOL.md
TEST_PLAN.md
THIRD_PARTY.md
TROUBLESHOOTING.md

Documentation must describe the actual implementation.

Do not document nonexistent functionality.

============================================================
22. GIT
============================================================

Commit after every stable stage.

Suggested:

01-motor-control
02-safety
03-watchdog
04-camera
05-opencv
06-detection
07-tracking
08-serial
09-autonomous
10-encoders
11-control
12-imu
13-final

Never destroy previously working functionality.

============================================================
23. PERFORMANCE
============================================================

Measure where possible:

camera FPS
AI inference time
end-to-end latency
serial latency
CPU usage
RAM
detection confidence
detection distance
stopping distance
encoder accuracy

Never invent measurements.

============================================================
24. PRIORITY
============================================================

P0:
Working rover.

P1:
Reliable autonomous behavior.

P2:
Encoders/control/IMU.

P3:
Experimental self-balancing/advanced autonomy.

NEVER sacrifice P0 for P2/P3.

============================================================
25. FINAL RULE
============================================================

The objective is NOT to produce the most complicated code.

The objective is:

A PHYSICALLY WORKING, SAFE, TESTED ROBOT.

If a complex feature is unreliable:

DEFER IT.

If a simple implementation works:

USE IT.

If something is unknown:

SAY UNKNOWN.

If something is incompatible:

SAY INCOMPATIBLE.

If something fails testing:

DO NOT MARK IT COMPLETE.

============================================================
BEGIN
============================================================

FIRST:

Do not write final code.

Inspect all repositories and produce:

1. Repository compatibility report
2. Hardware compatibility report
3. Dependency report
4. Pin conflict report
5. License report
6. Simulation strategy
7. Testing strategy
8. Integration plan

Then begin Phase 1.
