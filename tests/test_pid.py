"""Unit tests for Phase 9+ control foundations (PID + wheel odometry).

Covers software/control/pid.py and software/control/odometry.py:
math correctness, anti-windup, edge cases (dt<=0, ppr<=0, negative gains)
and the config factories. Physical validation is HARDWARE REQUIRED — these
tests only prove the software math.
"""

import math
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from software.control.odometry import Odometry, odometry_from_config
from software.control.pid import PID, pid_from_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = yaml.safe_load((ROOT / "config" / "config.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- PID math --
def test_p_only_output():
    pid = PID(kp=2.0, ki=0.0, kd=0.0)
    assert pid.update(10.0, 0.1) == pytest.approx(20.0)


def test_output_clamped_to_range():
    pid = PID(kp=1000.0, out_min=-255.0, out_max=255.0)
    assert pid.update(10.0, 0.1) == 255.0
    assert pid.update(-10.0, 0.1) == -255.0


def test_integral_anti_windup_limits_future_response():
    # kp=0, ki=1, output range +-10: a huge error must NOT bank 100 units of
    # integral (windup); it clamps to the output range and recovers fast.
    pid = PID(kp=0.0, ki=1.0, kd=0.0, out_min=-10.0, out_max=10.0)
    assert pid.update(100.0, 1.0) == pytest.approx(10.0)  # clamped
    assert pid.update(0.0, 1.0) == pytest.approx(10.0)  # still held at max
    # With anti-windup the banked integral is 10, so a -10 error unwinds it
    # to ~0 in one step (without the clamp it would stay pinned at +10).
    assert pid.update(-10.0, 1.0) == pytest.approx(0.0)


def test_nonpositive_dt_returns_zero_and_keeps_state():
    pid = PID(kp=5.0, ki=1.0, kd=2.0)
    assert pid.update(10.0, 0.0) == 0.0
    assert pid.update(10.0, -1.0) == 0.0
    # real update afterwards still works: P=50 + I=10 + D=0 (no prior error
    # was stored by the discarded dt<=0 calls) = 60
    out = pid.update(10.0, 1.0)
    assert out == pytest.approx(60.0)


def test_derivative_on_error_only_after_first_sample():
    pid = PID(kp=0.0, ki=0.0, kd=1.0)
    assert pid.update(10.0, 1.0) == 0.0  # no previous error -> no D
    assert pid.update(20.0, 1.0) == pytest.approx(10.0)  # (20-10)/1
    assert pid.update(15.0, 1.0) == pytest.approx(-5.0)  # (15-20)/1


def test_reset_clears_integral_and_derivative_history():
    pid = PID(kp=1.0, ki=1.0, kd=1.0)
    pid.update(10.0, 1.0)
    pid.reset()
    # after reset: no previous error (D=0), integral cleared
    assert pid.update(0.0, 1.0) == 0.0


def test_negative_gains_rejected():
    with pytest.raises(ValueError):
        PID(kp=-1.0)
    with pytest.raises(ValueError):
        PID(kp=1.0, ki=-0.1)
    with pytest.raises(ValueError):
        PID(kp=1.0, kd=-0.1)


def test_invalid_output_range_rejected():
    with pytest.raises(ValueError):
        PID(kp=1.0, out_min=10.0, out_max=10.0)
    with pytest.raises(ValueError):
        PID(kp=1.0, out_min=5.0, out_max=-5.0)


def test_p_only_controller_converges_on_integrator_plant():
    # First-order plant: velocity k*u; goal = reduce error to 0. P control
    # must converge without oscillation for a reasonable gain (SIMULATED math).
    k = 0.5
    pid = PID(kp=1.0, ki=0.0, kd=0.0, out_min=-255.0, out_max=255.0)
    x, goal, dt = 0.0, 100.0, 0.1
    for _ in range(200):
        u = pid.update(goal - x, dt)
        x += k * u * dt
    assert abs(goal - x) < 1.0


# ------------------------------------------------------- config factories --
def test_pid_from_config_reads_real_yaml_gains():
    pid = pid_from_config(CONFIG)
    assert pid.kp == pytest.approx(float(CONFIG["control"]["pid_kp"]))
    assert pid.ki == pytest.approx(float(CONFIG["control"]["pid_ki"]))
    assert pid.kd == pytest.approx(float(CONFIG["control"]["pid_kd"]))


def test_pid_from_config_defaults_when_section_missing():
    pid = pid_from_config({})
    assert (pid.kp, pid.ki, pid.kd) == (0.0, 0.0, 0.0)


# --------------------------------------------------------------- odometry --
def test_odometry_from_config_reads_real_yaml_geometry():
    od = odometry_from_config(CONFIG)
    ctl = CONFIG["control"]
    assert od.encoder_ppr == int(ctl["encoder_ppr"])
    assert od.wheel_diameter_cm == pytest.approx(float(ctl["wheel_diameter_cm"]))
    assert od.encoders_enabled is bool(ctl["encoders_enabled"])
    assert od.encoders_enabled is False  # no hardware yet: HARDWARE REQUIRED


def test_odometry_defaults_when_section_missing():
    od = odometry_from_config({})
    assert od.encoder_ppr == 20
    assert od.wheel_diameter_cm == pytest.approx(6.5)
    assert od.encoders_enabled is False


def test_ticks_to_cm_uses_ppr_and_circumference():
    od = Odometry(encoder_ppr=20, wheel_diameter_cm=6.5)
    assert od.wheel_circumference_cm == pytest.approx(math.pi * 6.5)
    assert od.ticks_to_cm(20) == pytest.approx(math.pi * 6.5)
    assert od.ticks_to_cm(0) == 0.0
    assert od.ticks_to_cm(10) == pytest.approx(math.pi * 6.5 / 2)


def test_ticks_to_cm_clamps_negative_ticks():
    od = Odometry(encoder_ppr=20, wheel_diameter_cm=6.5)
    assert od.ticks_to_cm(-5) == 0.0


def test_ticks_to_cm_rejects_nonpositive_ppr():
    od = Odometry(encoder_ppr=0, wheel_diameter_cm=6.5)
    with pytest.raises(ValueError):
        od.ticks_to_cm(10)


def test_odometry_is_immutable():
    od = Odometry(encoder_ppr=20, wheel_diameter_cm=6.5)
    with pytest.raises(Exception):
        od.encoder_ppr = 100
