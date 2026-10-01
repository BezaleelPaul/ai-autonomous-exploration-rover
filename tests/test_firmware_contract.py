"""Firmware↔software contract tests (Phase 1).

These parse the Arduino source and config YAML to guarantee:
  R2: invalid serial command forces STOP in firmware
  R3: safety constants stay in sync between YAML and firmware
  Safe startup: motors stopped in setup()
  Protocol: command set + telemetry prefixes match on both sides
  R1: documented run command `python software/main.py --help` works
"""

import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

INO = (ROOT / "arduino" / "rover_controller" / "rover_controller.ino").read_text(
    encoding="utf-8"
)
CONFIG = yaml.safe_load((ROOT / "config" / "config.yaml").read_text(encoding="utf-8"))
THRESH = yaml.safe_load(
    (ROOT / "config" / "thresholds.yaml").read_text(encoding="utf-8")
)


def _const(name: str) -> str:
    m = re.search(rf"const\s+[\w\s]+?\b{name}\s*=\s*([^;]+);", INO)
    assert m, f"{name} not found in firmware"
    return m.group(1).strip()


def test_emergency_distance_firmware_matches_yaml():
    assert float(_const("EMERGENCY_STOP_CM")) == float(
        CONFIG["rover"]["emergency_stop_distance_cm"]
    )
    assert float(_const("EMERGENCY_STOP_CM")) == float(
        THRESH["ultrasonic"]["emergency_stop_cm"]
    )


def test_comm_timeout_firmware_matches_yaml():
    assert int(_const("COMM_TIMEOUT_MS")) == int(
        CONFIG["safety"]["comm_timeout_s"] * 1000
    )


def test_speed_firmware_matches_yaml():
    assert int(_const("DEFAULT_SPEED")) == int(CONFIG["rover"]["max_speed_pwm"])


def test_invalid_command_forces_stop_in_firmware():
    # R2 (MASTER PROMPT §2): invalid chunk must clear command + stop motors
    # immediately before the actual reply statement (not comment mentions).
    marker = 'Serial.println("STATUS:ERROR")'
    idx = INO.find(marker)
    assert idx != -1, "no STATUS:ERROR reply statement in firmware"
    branch = INO[max(0, idx - 300) : idx]
    assert "stopMotors()" in branch, "invalid command branch does not stop motors"
    assert "currentCmd = 'S'" in branch, "invalid command does not clear currentCmd"


def test_setup_stops_motors_first():
    m = re.search(r"void\s+setup\s*\(\s*\)\s*\{(.*?)\n\}", INO, re.DOTALL)
    assert m, "setup() not found"
    body = m.group(1)
    assert "stopMotors()" in body, "setup() must stop motors (safe startup)"
    assert "drive(" not in body, "setup() must never drive"


def test_watchdog_and_obstacle_guard_present():
    assert "COMM_TIMEOUT_MS" in INO and "commLost" in INO
    assert "EMERGENCY_STOP_CM" in INO and "blocked" in INO


def test_command_set_matches_between_sides():
    from software.hardware.arduino_serial import VALID_COMMANDS

    m = re.search(r"c=='(\w)'\|\|c=='(\w)'\|\|c=='(\w)'\|\|c=='(\w)'\|\|c=='(\w)'", INO)
    assert m, "firmware command whitelist not found"
    fw = set(m.groups())
    assert fw == VALID_COMMANDS, f"mismatch: firmware={fw} python={VALID_COMMANDS}"


def test_telemetry_prefixes_match():
    from software.hardware.arduino_serial import TELEMETRY_PREFIXES

    for prefix in ("DIST:", "STATUS:", "TICKS:"):
        assert prefix in INO, f"firmware does not emit {prefix}"
        assert any(p.startswith(prefix) for p in TELEMETRY_PREFIXES)


def test_encoder_pins_match_pinout_doc():
    # Phase 9+: D2/D3 wheel encoders must be documented where they are wired.
    pinout = (ROOT / "docs" / "PINOUT.md").read_text(encoding="utf-8")
    assert int(_const("ENC_L_PIN")) == 2
    assert int(_const("ENC_R_PIN")) == 3
    assert "encISR_L" in INO and "encISR_R" in INO
    assert "D2" in pinout and "D3" in pinout
    assert re.search(r"D2\b.*encoder", pinout, re.IGNORECASE)
    assert re.search(r"D3\b.*encoder", pinout, re.IGNORECASE)


def test_documented_run_command_works():
    # R1 regression: README command must not crash on software/logging shadowing
    r = subprocess.run(
        [sys.executable, str(ROOT / "software" / "main.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(ROOT),
        check=False,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert "manual" in r.stdout


def test_velocity_loop_constants_match_yaml():
    # Phase 9+: firmware velocity-loop consts are driven by config `control:`.
    ctl = CONFIG["control"]
    assert float(_const("VEL_KP")) == float(ctl["velocity_kp"])
    assert int(_const("VEL_TARGET_TPS")) == int(ctl["velocity_target_tps"])
    assert int(_const("VEL_PWM_FF")) == int(ctl["velocity_pwm_ff"])
    assert int(_const("VEL_PERIOD_MS")) == int(ctl["velocity_period_ms"])


def test_encoders_enabled_flag_matches_yaml():
    # Firmware ships the flag false; flipping config control.encoders_enabled
    # to true without real encoders must fail this sync contract.
    assert re.search(r"bool\s+encodersEnabled\s*=\s*false\b", INO), (
        "firmware encodersEnabled must default to false (no encoder hardware)"
    )
    assert bool(CONFIG["control"]["encoders_enabled"]) is False


def test_protocol_v2_speed_suffix_documented_both_sides():
    # RX parser accepts a PWM suffix; the Python sender can emit one.
    assert "speedAccum" in INO and "activeSpeed" in INO
    py = (ROOT / "software" / "hardware" / "arduino_serial.py").read_text(
        encoding="utf-8"
    )
    assert "def send(self, cmd: str, speed: int | None = None)" in py
