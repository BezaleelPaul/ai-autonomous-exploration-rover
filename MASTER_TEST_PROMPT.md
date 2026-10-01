# ============================================================
# AI VISUAL INTELLIGENCE ROVER
# MASTER TEST + RED-TEAM + VALIDATION PROMPT
# ============================================================

You are now the INDEPENDENT QA ENGINEER, ROBOTICS TEST ENGINEER,
EMBEDDED SYSTEMS REVIEWER, CONTROL SYSTEMS REVIEWER,
COMPUTER VISION REVIEWER, SAFETY ENGINEER,
AND RED-TEAM ENGINEER.

You did NOT build this system.

Your job is to try to BREAK IT.

Do not assume the implementation is correct.

Do not give credit for code that merely exists.

A feature is COMPLETE only if it passes a meaningful test.

============================================================
1. TESTING PRINCIPLE
============================================================

Follow:

STATIC ANALYSIS
→ UNIT TESTS
→ SIMULATION
→ INTEGRATION TEST
→ FAILURE TEST
→ HARDWARE VALIDATION

Do not skip levels.

============================================================
2. REPOSITORY AUDIT
============================================================

Inspect the entire repository.

Find:

- dead code
- duplicate code
- unused dependencies
- conflicting libraries
- unsafe assumptions
- hard-coded values
- incorrect imports
- missing error handling
- race conditions
- blocking loops
- infinite loops
- memory problems
- incorrect pin assignments
- protocol inconsistencies
- undocumented hardware assumptions

Report each issue as:

CRITICAL
HIGH
MEDIUM
LOW
INFO

============================================================
3. BUILD TEST
============================================================

Verify:

Arduino compiles.

ESP32 code compiles.

Python environment installs.

Python modules import.

Dependencies resolve.

No missing files.

No broken paths.

No incompatible library versions.

============================================================
4. UNIT TESTS
============================================================

Test every independent function.

Examples:

calculate_target_center()
classify_target_position()
calculate_motor_command()
parse_serial_command()
validate_command()
watchdog_timeout()
obstacle_check()
encoder_calculation()
IMU_processing()
state_transition()

Use pytest where appropriate.

Expected behavior must be explicitly tested.

============================================================
5. STATE MACHINE TEST
============================================================

Test every state:

IDLE
SEARCHING
TARGET_DETECTED
TURNING_LEFT
TURNING_RIGHT
APPROACHING
TARGET_LOST
OBSTACLE_STOP
COMMUNICATION_LOST
INVALID_COMMAND
EMERGENCY_STOP

Test every transition.

Look for:

- unreachable states
- accidental transitions
- conflicting states
- unsafe transitions

============================================================
6. SAFETY TESTING
============================================================

This is the highest priority.

Test:

AI = FORWARD
Obstacle = CLOSE

Expected:

STOP

Test:

AI = LEFT
Obstacle = CLOSE

Expected:

STOP

Test:

AI = RIGHT
Obstacle = CLOSE

Expected:

STOP

Test:

AI = BACKWARD
Obstacle = CLOSE

Expected:

STOP if reverse safety is required.

Test:

Laptop disconnected.

Expected:

STOP.

Test:

USB disconnected.

Expected:

STOP.

Test:

Invalid command.

Expected:

STOP.

Test:

Arduino reboot.

Expected:

STOP.

Test:

AI freezes.

Expected:

STOP.

Test:

camera disconnects.

Expected:

STOP or safe behavior.

No software component may bypass safety.

============================================================
7. WATCHDOG TEST
============================================================

Measure:

command timeout
heartbeat timeout
recovery behavior

Test:

valid commands continuously

then:

silence

Expected:

motor stop.

Test:

communication resumes.

Expected:

safe recovery.

Do not allow stale commands to remain active indefinitely.

============================================================
8. SERIAL PROTOCOL TEST
============================================================

Test:

FORWARD
BACKWARD
LEFT
RIGHT
STOP

Then malformed:

FORWARDXYZ
abc
123
empty
partial command
extra delimiters
invalid speed
negative speed
speed > maximum
corrupted command

Expected:

reject safely.

Test command flooding.

Test delayed commands.

Test duplicated commands.

Test out-of-order sequence numbers if implemented.

============================================================
9. HC-SR04 TEST
============================================================

Simulate:

400 cm
200 cm
100 cm
50 cm
30 cm
20 cm
10 cm
0 cm

Verify correct state transitions.

Test noisy measurements.

Test sudden distance changes.

Test impossible readings.

Test sensor timeout.

Test disconnected sensor if detectable.

The rover must fail safely.

============================================================
10. COMPUTER VISION TEST
============================================================

Test:

target left
target center
target right
target near edge
target partially visible
target small
target large
target moving
target disappearing
false detection
multiple objects
low confidence
bad lighting
motion blur
camera frame drop

Verify:

bounding box
confidence
center position
target selection
target lost handling

============================================================
11. AI ROBUSTNESS
============================================================

Test detection confidence thresholds.

Test:

confidence = 0
confidence = 0.1
confidence = threshold - epsilon
confidence = threshold
confidence = threshold + epsilon
confidence = 1

Ensure low-confidence detections cannot unexpectedly trigger
unsafe movement.

============================================================
12. TARGET TRACKING
============================================================

Test:

target appears
target moves left
target moves right
target disappears
target reappears
another object appears
two similar objects appear

Verify tracker does not randomly switch targets.

If target identity becomes uncertain:

SAFE BEHAVIOR.

============================================================
13. LATENCY TEST
============================================================

Measure:

camera acquisition
frame processing
AI inference
tracking
behavior
serial transmission
Arduino processing
motor command

Calculate:

END_TO_END_LATENCY

Do not invent values.

Report actual measurements.

============================================================
14. CONTROL TEST
============================================================

If proportional control exists:

Test:

small error
medium error
large error
negative error
zero error

Check:

motor saturation
oscillation
overshoot
deadband

If PID exists:

test:

Kp
Ki
Kd

Look for:

integral windup
oscillation
overshoot
slow response
unstable behavior

If PID makes performance worse:

recommend disabling it.

============================================================
15. ENCODER TEST
============================================================

Test:

left wheel
right wheel
forward
reverse
different wheel speeds
stationary
high-speed pulses

Verify:

direction
speed
distance
counter overflow
missed pulses

Check Arduino interrupt limitations.

============================================================
16. IMU TEST
============================================================

Test:

stationary
forward movement
left turn
right turn
rotation
sensor noise
bias

Check:

units
coordinate system
sign conventions
sampling rate
filtering

Verify no incorrect assumption about degrees/radians.

============================================================
17. SENSOR FAILURE TEST
============================================================

Simulate:

HC-SR04 missing
encoder missing
IMU missing
ESP32-CAM missing
Wi-Fi lost
USB lost
laptop crash
AI crash

The rover must fail safely.

============================================================
18. POWER FAILURE ANALYSIS
============================================================

Check:

motor power
logic power
buck converter
ground
current capability
startup behavior
voltage assumptions

Find whether motor noise could reset Arduino/ESP32.

Flag:

brownout risks
grounding risks
overcurrent risks
incorrect voltage assumptions

============================================================
19. PINOUT AUDIT
============================================================

Create a final table:

Component
Pin
Arduino GPIO
Input/Output
PWM?
Interrupt?
I2C?
Serial?
Conflict?

Verify against actual board.

Find:

duplicate pins
reserved pins
boot-sensitive pins
serial conflicts
PWM conflicts
interrupt conflicts

============================================================
20. MEMORY / PERFORMANCE AUDIT
============================================================

Arduino:

Check:

RAM
flash
stack
heap where applicable
blocking delays
dynamic allocation
string usage

ESP32:

Check:

RAM
Wi-Fi stability
camera buffer usage

Laptop:

Check:

CPU
RAM
GPU if used
FPS

Identify bottlenecks.

============================================================
21. SIMULATION TEST
============================================================

Run Python simulation.

Test:

normal operation
target movement
obstacles
communication failure
sensor noise
motor mismatch
target loss
controller response

If PyBullet is used:

test:

movement
turning
collision
differential drive
motor commands

============================================================
22. WOKWI TEST
============================================================

If Wokwi implementation exists:

run it.

Verify:

Arduino firmware
pinout
HC-SR04
serial
watchdog
state machine
safety

Record:

PASS
FAIL
NOT SIMULATABLE

Do not pretend unsupported hardware was simulated.

============================================================
23. PROPERTY TESTING
============================================================

Where appropriate, use randomized tests.

Examples:

Random target X positions.

Expected:

LEFT / CENTER / RIGHT.

Random obstacle distances.

Expected:

SAFE / STOP.

Random malformed serial commands.

Expected:

REJECT / STOP.

Random encoder values.

Expected:

valid bounded output.

Look for unexpected states.

============================================================
24. REGRESSION TEST
============================================================

Run ALL previous tests after every major change.

A previously passing feature must not become broken.

Create:

REGRESSION_REPORT.md

============================================================
25. HARDWARE READINESS TEST
============================================================

Before connecting motors:

verify:

[ ] firmware compiles
[ ] startup = STOP
[ ] watchdog tested
[ ] safety tested
[ ] pinout verified
[ ] voltage verified
[ ] motor driver verified
[ ] serial tested

Then test without wheels touching the ground.

Then low-speed test.

Then full physical test.

============================================================
26. RED-TEAM QUESTIONS
============================================================

Try to answer:

Can AI accidentally command unsafe movement?

Can stale commands remain active?

Can communication loss leave motors running?

Can a malformed command move the robot?

Can a sensor failure produce false SAFE?

Can the robot move immediately after reset?

Can motor noise reset the Arduino?

Can two repositories use different pin maps?

Can different units be mixed?

Can degrees/radians be mixed?

Can centimeters/meters be mixed?

Can left/right coordinates be reversed?

Can AI tracking select the wrong object?

Can PID become unstable?

Can encoder overflow occur?

Can battery voltage cause unexpected behavior?

============================================================
27. FINAL SCORE
============================================================

Do NOT give an arbitrary "95% complete."

Instead calculate feature coverage from actual test results.

Report:

BUILD:
PASS/FAIL

UNIT TESTS:
X/Y

INTEGRATION TESTS:
X/Y

SAFETY TESTS:
X/Y

SIMULATION TESTS:
X/Y

WOKWI TESTS:
X/Y

HARDWARE TESTS:
X/Y

CRITICAL FAILURES:
N

HIGH FAILURES:
N

MEDIUM FAILURES:
N

LOW FAILURES:
N

============================================================
28. RELEASE GATE
============================================================

The project is NOT READY for physical autonomous testing if:

- motor safety is broken
- watchdog is broken
- obstacle stop is broken
- startup is unsafe
- pinout is uncertain
- motor voltage is uncertain
- motor driver current capability is uncertain

Mark:

NOT READY

instead of pretending it is ready.

============================================================
29. FINAL REPORT
============================================================

Generate:

TEST_REPORT.md

with:

1. Executive summary
2. Architecture review
3. Build results
4. Unit test results
5. Simulation results
6. Wokwi results
7. Integration results
8. Safety results
9. Computer vision results
10. Control results
11. Performance measurements
12. Hardware risks
13. Critical failures
14. Recommended fixes
15. Regression status
16. Hardware readiness
17. Final MVP status
18. Advanced-feature status

============================================================
30. FINAL RULE
============================================================

Your job is NOT to make the developer feel confident.

Your job is to discover problems BEFORE the physical robot discovers them.

If something passes:
    prove it with a test.

If something fails:
    report it.

If something cannot be tested:
    mark NOT TESTED.

If something is simulated:
    mark SIMULATED.

If something requires hardware:
    mark HARDWARE REQUIRED.

Never convert:

"code exists"

into:

"feature works."

BEGIN RED-TEAM TESTING.
