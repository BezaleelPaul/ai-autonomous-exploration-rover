"""Firmware source contracts: pinout, safety constants and non-blocking rules.

These are the checks the project report calls "the pinout contract" and the
"15 cm / 500 ms" contracts.  They run in milliseconds on a laptop and catch
the classic regressions: a swapped AIN1/AIN2, a reintroduced pulseIn(), a
delay() in loop(), or a threshold edited in only one place.
"""

from __future__ import annotations

import re

from support import c_constants, read, section

PINS = read("firmware/libraries/AIRoverCore/src/pins.h")
CORE = read("firmware/libraries/AIRoverCore/src/safety_core.h")
SKETCH = read("firmware/arduino/motion_safety/motion_safety.ino")
WHEEL_TEST = read("firmware/arduino/wheel_test_hold/wheel_test_hold.ino")
PROTOCOL = read("firmware/libraries/AIRoverCore/src/protocol.h")


def pin(name: str) -> int:
    match = re.search(rf"constexpr\s+uint8_t\s+{name}\s*=\s*(\d+)", PINS)
    assert match, f"{name} missing from pins.h"
    return int(match.group(1))


# ---------------------------------------------------------------------------
# Pinout
# ---------------------------------------------------------------------------
def test_tb6612_pinout_matches_production_silkscreen():
    assert pin("kPwma") == 5
    assert pin("kAin1") == 7
    assert pin("kAin2") == 6
    assert pin("kBin1") == 8
    assert pin("kBin2") == 10
    assert pin("kPwmb") == 9


def test_sensor_and_link_pins():
    assert pin("kTrig") == 2
    assert pin("kEcho") == 3
    assert pin("kLinkRx") == 4
    assert pin("kLinkTx") == 16   # A2: SoftwareSerial TX -> ESP32 GPIO16
    assert pin("kPinHeartbeat") == 19
    assert pin("kEncoderLeft") == 11
    assert pin("kEncoderRight") == 12
    assert pin("kRearTrig") == 11
    assert pin("kPinFaultOut") == 18
    assert pin("kPinEstop") == 15
    assert pin("kPinBattery") == 14
    assert pin("kStatusLed") == 13


def test_no_pin_collisions():
    # kRearTrig/kRearEcho intentionally alias the encoder pins: the build has
    # a compile-time #error if both features are enabled.
    used = {name: pin(name) for name in (
        "kPwma", "kAin1", "kAin2", "kBin1", "kBin2", "kPwmb",
        "kTrig", "kEcho", "kLinkRx", "kLinkTx", "kStatusLed",
        "kPinHeartbeat", "kEncoderLeft", "kEncoderRight",
        "kPinFaultOut", "kPinEstop", "kPinBattery",
    )}
    assert len(set(used.values())) == len(used), f"pin reused: {used}"


def test_esp32_link_is_unidirectional_and_uses_uart2():
    esp = read("firmware/esp32/wifi_bridge/config.h")
    assert "#define LINK_TX_PIN 17" in esp
    assert "#define LINK_RX_PIN 16" in esp
    assert "#define LINK_BAUD 9600" in esp
    # The Uno only listens on D4; it must never drive the ESP32's 3.3 V RX.
    assert pin("kLinkRx") == 4


# ---------------------------------------------------------------------------
# Safety constants live in exactly one place
# ---------------------------------------------------------------------------
def test_safety_constants():
    constants = c_constants(PROTOCOL)
    assert constants["kForwardGateCm"] == 15
    assert constants["kLinkWatchdogMs"] == 500
    assert constants["kSonarPeriodMs"] == 60
    assert constants["kCommandGapUs"] == 15000
    assert constants["kSpeedMin"] == 60
    assert constants["kSpeedMax"] == 255
    assert constants["kDefaultSpeed"] == 180


def test_core_includes_the_shared_protocol():
    assert '#include "protocol.h"' in CORE
    # The Uno must not redefine the gate/threshold locally.
    assert "kForwardGateCm =" not in CORE
    assert "kLinkWatchdogMs =" not in CORE


def test_sketch_uses_shared_constants_not_magic_numbers():
    assert "rover::kForwardGateCm" in SKETCH
    assert "rover::kGateSpeedCm" in SKETCH
    assert "rover::kSonarPeriodMs" in SKETCH
    assert "kLinkWatchdogMs" in CORE  # watchdog is owned by the core


# ---------------------------------------------------------------------------
# Boot safety
# ---------------------------------------------------------------------------
def test_boot_prints_stopped_and_zeroes_pwm():
    setup = section(SKETCH, "void setup()", "void loop()")
    assert "analogWrite(rover::pins::kPwma, 0)" in setup
    assert "analogWrite(rover::pins::kPwmb, 0)" in setup
    assert '"[UNO] BOOT:STOP"' in setup
    assert "core.begin(millis())" in setup
    # Direction pins are driven low before they become outputs.
    assert setup.index("digitalWrite(rover::pins::kAin1, LOW)") < setup.index("pinMode(rover::pins::kAin1, OUTPUT)")


def test_loop_never_blocks():
    loop = section(SKETCH, "void loop()", "\n}")
    assert "delay(" not in loop
    assert "pulseIn(" not in SKETCH
    assert "core.tick(nowMs)" in loop
    assert "wdt_reset()" in loop


def test_watchdog_and_gate_are_enforced_by_the_core():
    tick = section(CORE, "void tick(uint32_t nowMs)", "bool sonarDue")
    assert "kLinkWatchdogMs" in tick
    assert "stop(State::Timeout" in tick
    assert "requiredGateCm" in CORE
    assert "kRearGateCm" in CORE


def test_dead_sensor_is_fail_safe():
    update = section(CORE, "void updateSonar", "void tick(")
    assert "distCm_ = -1" in update
    assert "State::Blocked" in update


# ---------------------------------------------------------------------------
# Telemetry dictionary (Appendix B of the report)
# ---------------------------------------------------------------------------
def test_telemetry_dictionary_is_emitted():
    for token in ("BOOT:STOP", "[UNO] DIST: ", "[UNO] CMD: ", "STATE: ", "STATUS: ", "ALERT:OBSTACLE", "ACT: PWMA="):
        assert token in SKETCH, f"missing telemetry token {token}"


def test_telemetry_state_names():
    for name in ('"GO"', '"STOP"', '"TIMEOUT"', '"BLOCKED"', '"OK"', '"ERROR"'):
        assert name in CORE


def test_sonar_values_are_converted_with_58us_per_cm():
    assert "width / 58UL" in SKETCH
    assert "25000" in SKETCH  # ~4.3 m echo timeout
    assert "5000" in SKETCH   # 5 ms wait-for-rise timeout (dead sensor)


def test_usb_command_input_can_be_disabled_for_production():
    assert "#define ACCEPT_USB_COMMANDS 1" in SKETCH
    assert "#if ACCEPT_USB_COMMANDS" in SKETCH


# ---------------------------------------------------------------------------
# Diagnostic firmware
# ---------------------------------------------------------------------------
def test_wheel_test_is_isolated_and_auto_stopping():
    assert "kAutoStopMs = 3000" in WHEEL_TEST
    assert "stopAll()" in WHEEL_TEST
    assert "ISOLATED DRIVE TEST" in WHEEL_TEST
    setup = section(WHEEL_TEST, "void setup()", "void loop()")
    assert "stopAll();" in setup  # never boots driving


def test_no_motor_write_outside_the_output_stage():
    """All PWM writes in the main sketch must go through applyOutputs()."""
    writes = re.findall(r"analogWrite\([^;]+\);", SKETCH)
    assert writes, "sketch does not drive PWM at all"
    assert all(("pwmL" in w) or ("pwmR" in w) or (", 0)" in w) for w in writes), writes


def test_uart_telemetry_can_be_disabled():
    assert "#if ENABLE_UART_TELEMETRY" in SKETCH
    assert "#define ENABLE_UART_TELEMETRY 1" in SKETCH


def test_heartbeat_and_watchdog_are_serviced_every_loop():
    loop = section(SKETCH, "void loop()", "\n}")
    assert "serviceHeartbeat()" in loop
    assert "wdt_reset()" in loop
    assert "serviceEstop()" in loop
    assert "serviceBattery()" in loop


# ---------------------------------------------------------------------------
# Encoders / closed loop
# ---------------------------------------------------------------------------
def test_encoder_build_is_optional_and_conflict_guarded():
    assert "#define ENCODERS 0" in SKETCH
    assert "#if ENCODERS && REAR_SONAR" in SKETCH
    assert '#error "ENCODERS and REAR_SONAR both need A2/A3: enable only one"' in SKETCH


def test_encoder_interrupts_use_the_hardware_ext_interrupts():
    # SoftwareSerial owns the pin-change vectors, so INT0/INT1 are mandatory.
    assert "attachInterrupt(digitalPinToInterrupt(rover::pins::kEncoderLeft), encoderLeftIsr, RISING)" in SKETCH
    assert "attachInterrupt(digitalPinToInterrupt(rover::pins::kEncoderRight), encoderRightIsr, RISING)" in SKETCH
    assert "PCICR" not in SKETCH


def test_closed_loop_control_runs_on_a_fixed_period():
    assert "serviceControl(nowMs)" in SKETCH
    assert "kControlPeriodMs" in SKETCH
    assert "speedL.update(cL, dt, thrL)" in SKETCH
    assert "core.setStall(true)" in SKETCH


def test_motor_output_falls_to_zero_when_not_driving():
    apply = section(SKETCH, "static void applyOutputs()", "static void printActuation")
    assert "if (core.moving())" in apply
    assert "pwmL = 0;" in apply
    assert "pwmR = 0;" in apply


def test_telemetry_frame_has_the_full_odometry_payload():
    tlm = section(SKETCH, "static void sendTelemetryIfDue()", "static void reportSonar")
    for token in ("speedL.speedMmS()", "speedR.speedMmS()", "odom.xMm()", "odom.yMm()",
                  "odom.thetaDeg()"):
        assert token in tlm, token
    assert "char buf[80]" in SKETCH
    assert "n < 76" in SKETCH  # appendInt guard must not truncate the frame
    assert "static void sendTelemetryIfDue" in SKETCH
