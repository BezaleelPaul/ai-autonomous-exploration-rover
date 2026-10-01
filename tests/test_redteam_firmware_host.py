"""SIMULATED host-execution tests against the REAL rover_controller.ino.

The unmodified firmware source is compiled with g++ together with Arduino API
stubs (tests/firmware_host/arduino_stubs.h) so that loop()/setup() can be
driven with adversarial serial input and observed.

  * This is NOT hardware validation: no MCU, no real UART, no real timing.
  * Label for every result produced here: SIMULATED.
  * Tests that assert the REQUIRED safe behaviour and fail document a bug.

Environment: requires g++; the suite is skipped if no compiler is found.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOST_SRC = ROOT / "tests" / "firmware_host" / "firmware_host.cpp"


def _find_gpp() -> str | None:
    found = shutil.which("g++")
    if found:
        return found
    for cand in (
        Path(r"C:\Program Files (x86)\cpeditor\mingw64\bin\g++.exe"),
        Path(r"C:\msys64\mingw64\bin\g++.exe"),
    ):
        if cand.exists():
            return str(cand)
    return None


GPP = _find_gpp()

pytestmark = pytest.mark.skipif(
    GPP is None, reason="g++ not available: firmware host execution NOT TESTED"
)


@pytest.fixture(scope="module")
def host_exe():
    assert GPP is not None  # guarded by pytestmark above
    tmp = tempfile.mkdtemp(prefix="fw_host_")
    exe = Path(tmp) / "firmware_host.exe"
    r = subprocess.run(
        [GPP, "-std=c++17", "-O0", "-o", str(exe), str(HOST_SRC)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=300,
        check=False,
    )
    assert r.returncode == 0, r.stderr[-4000:]
    yield exe
    shutil.rmtree(tmp, ignore_errors=True)


def run(host_exe, scenario: str) -> str:
    r = subprocess.run(
        [str(host_exe), scenario],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def motion_lines(out: str) -> list[str]:
    return [ln for ln in out.splitlines() if ln.startswith("iter=") and "motors=" in ln]


# ---------------------------------------------------------------- startup --
def test_setup_stops_motors(host_exe):
    out = run(host_exe, "startup")
    assert "after setup motors=STOP" in out


def test_reboot_leaves_motors_stopped(host_exe):
    out = run(host_exe, "reboot")
    assert "motors before reboot=F" in out
    assert "before setup(): motors=HIGH-Z" in out  # GPIO high-Z until setup()
    assert "iter=1 cmd=S motors=STOP" in out  # setup() re-establishes STOP
    assert "FINAL cmd=S motors=STOP" in out


# ------------------------------------------------------------ valid input --
def test_valid_commands_produce_each_direction(host_exe):
    out = run(host_exe, "valid")
    for d in ("cmd=F motors=F", "cmd=B motors=B", "cmd=L motors=L", "cmd=R motors=R"):
        assert d in out, out
    assert "FINAL cmd=S motors=STOP" in out


def test_lower_case_command_accepted(host_exe):
    out = run(host_exe, "case_insensitive")
    assert "lowercase f -> cmd=F motors=F" in out


# ------------------------------------------------------- invalid input R2 --
def test_single_invalid_char_stops_motors_and_replies_error(host_exe):
    out = run(host_exe, "invalid_char")
    assert "iter=0 cmd=F motors=F" in out
    assert "STATUS:ERROR" in out
    assert "FINAL cmd=S motors=STOP" in out


def test_binary_bytes_stop_motors(host_exe):
    out = run(host_exe, "binary")
    assert out.count("STATUS:ERROR") >= 3
    assert "FINAL cmd=S motors=STOP" in out


def test_flood_of_invalid_bytes_stops_motors(host_exe):
    out = run(host_exe, "flood_invalid")
    assert "after 500xZ: cmd=S motors=STOP" in out


# -------------------------------------------------- malformed input (§8) ---
def test_malformed_command_is_rejected_without_actuating_motors(host_exe):
    """§8: malformed input must be rejected safely (no motion).

    NOTE (fixed assertion mechanics, not intent): trace lines end with
    ``tx=<telemetry>``, so ``endswith("motors=STOP")`` could never be true
    even for perfectly safe behaviour. We parse the motors field instead.
    """
    import re

    out = run(host_exe, "malformed_word")

    def motor_of(ln: str) -> str | None:
        m = re.search(r" motors=(\S+)", ln)
        return m.group(1) if m else None

    actuated = [ln for ln in motion_lines(out) if motor_of(ln) not in (None, "STOP")]
    assert not actuated, (
        "firmware actuated on a malformed multi-char command:\n" + "\n".join(actuated)
    )


def test_corrupt_command_ending_in_motion_byte_does_not_keep_driving(host_exe):
    """Noise ending in a valid motion byte must not leave motors running."""
    out = run(host_exe, "corrupt_ends_F")
    assert "FINAL cmd=S motors=STOP" in out, out


# ------------------------------------------------------------ watchdog §7 --
def test_comm_watchdog_stops_after_3s_of_silence(host_exe):
    out = run(host_exe, "watchdog")
    assert "iter=0 cmd=F motors=F" in out
    assert "iter=1 cmd=S motors=STOP" in out
    assert "STATUS:STOP" in out


def test_newline_bytes_do_not_refresh_watchdog(host_exe):
    out = run(host_exe, "watchdog_newline_only")
    assert "iter=1 cmd=S motors=STOP" in out
    assert "FINAL cmd=S motors=STOP" in out


def test_watchdog_boundary_is_strictly_greater_than_3000ms(host_exe):
    out = run(host_exe, "watchdog_exact")
    assert "at +3000 motors=F" in out
    assert "at +3001 motors=STOP" in out


def test_flood_then_silence_still_stops(host_exe):
    out = run(host_exe, "flood_then_silence")
    assert "during flood motors=F" in out
    assert "FINAL cmd=S motors=STOP" in out


# ----------------------------------------------------- obstacle guard (§6) --
def test_obstacle_blocks_forward_and_backward_but_allows_turn(host_exe):
    out = run(host_exe, "obstacle")
    assert "cmd=F motors=STOP" in out  # forward blocked at 10 cm
    assert "cmd=L motors=L" in out  # pivot allowed
    assert "cmd=B motors=STOP" in out  # reverse blocked
    assert "FINAL cmd=B motors=STOP" in out


# ------------------------------------------------- sensor failure (§9/§17) --
def test_sensor_failure_must_fail_safe_mid_run(host_exe):
    """HC-SR04 dying while driving forward must stop the rover (§17)."""
    out = run(host_exe, "sensor_dead")
    final = next(ln for ln in out.splitlines() if ln.startswith("FINAL"))
    assert "motors=STOP" in final, out


def test_sensor_dead_from_boot_must_fail_safe_in_firmware(host_exe):
    """§9: a disconnected ultrasonic must not let firmware drive (§9)."""
    out = run(host_exe, "sensor_dead_from_boot")
    assert "DIST:-1" in out  # firmware does detect the fault...
    final = next(ln for ln in out.splitlines() if ln.startswith("FINAL"))
    assert "motors=STOP" in final, out


# ------------------------------------------------------------ telemetry ----
def test_telemetry_emitted_and_distance_matches_pulse(host_exe):
    out = run(host_exe, "telemetry")
    assert "DIST:10.0" in out
    assert "STATUS:OK" in out


def test_partial_garbage_then_valid_recovers(host_exe):
    out = run(host_exe, "partial_then_valid")
    assert "STATUS:ERROR" in out
    assert "FINAL cmd=F motors=F" in out


# ------------------------------------------------------------ encoders P9 --
def test_encoder_ticks_counted_and_reported(host_exe):
    """Phase 9+ (SIMULATED): D2/D3 ISRs count and TICKS telemetry reports them."""
    out = run(host_exe, "encoders")
    assert "ticks L=5 R=2" in out, out
    assert "TICKS:5,2" in out, out
    assert "STATUS:OK" in out, out  # heartbeat unaffected by extra telemetry
    assert "FINAL cmd=F motors=STOP" not in out  # no watchdog trip at +250ms


# ------------------------------------------------- Protocol v2 speed suffix --
def test_speed_suffix_applied_and_overspeed_fails_safe(host_exe):
    """SIMULATED: F180/L77 set PWM; bare B keeps sticky speed; >255 stops."""
    out = run(host_exe, "speed_suffix")
    assert "after F180 pwm L=180 R=180" in out, out
    assert "after L77 pwm L=77 R=77 cmd=L" in out, out
    assert "after bare B pwm L=77 R=77 cmd=B" in out, out  # sticky, no reset
    assert "after overspeed: cmd=S motors=STOP" in out, out
    assert "STATUS:ERROR" in out, out


def test_velocity_loop_boosts_trims_and_falls_back(host_exe):
    """SIMULATED: P velocity loop on wheel encoders, dead-sensor fallback."""
    out = run(host_exe, "velocity")
    assert "pwm L=210 R=210" in out, out  # 0 tps: 150 + 1.2*(50-0)
    assert "pwm L=138 R=138" in out, out  # 60 tps: 150 + 1.2*(50-60)
    assert "fallback pwm L=200 R=200" in out, out  # dead encoders -> open loop
    assert "cmd=F motors=F" in out, out  # loop never commandeers the command
    assert "FINAL cmd=F motors=STOP" not in out  # no watchdog trip at +500ms
