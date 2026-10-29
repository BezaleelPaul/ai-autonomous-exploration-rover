"""Control-layer steering helpers: mapping, anti-oscillation, P-steering,
and the finite search rotation (supersedes the removed decision engine)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from software.control.steering import (
    AntiOscillation,
    SearchRotation,
    command_for_position,
    p_steer_speed,
)


def osc(min_dur=10.0, cooldown=0.0):
    return AntiOscillation(min_command_duration_s=min_dur, cooldown_s=cooldown)


def test_position_mapping_left_right_center():
    assert command_for_position("LEFT", False, True)[0] == "L"
    assert command_for_position("RIGHT", False, True)[0] == "R"
    assert command_for_position("CENTER", False, True)[0] == "F"


def test_target_lost_and_close_stop():
    assert command_for_position("CENTER", False, False)[0] == "S"
    assert command_for_position("CENTER", True, True)[0] == "S"


def test_states_match_the_mapping():
    assert command_for_position("CENTER", False, True)[1] == "APPROACHING"
    assert command_for_position("LEFT", False, True)[1] == "ALIGNING"
    assert command_for_position("JUNK", False, False)[1] == "SEARCHING"
    assert command_for_position("JUNK", False, True)[1] == "OBSERVE"


def test_anti_oscillation_blocks_rapid_flip():
    o = osc(min_dur=10.0)
    assert o.apply("L", 0.0) == "L"
    # 1s later R requested but min duration 10s blocks it -> holds L
    assert o.apply("R", 1.0) == "L"
    # after 11s the flip is allowed
    assert o.apply("R", 11.0) == "R"


def test_anti_oscillation_never_delays_stop():
    o = osc(min_dur=10.0)
    assert o.apply("L", 0.0) == "L"
    assert o.apply("S", 0.01) == "S"


def test_anti_oscillation_allows_resuming_from_stop():
    # Resuming right after a stop must not wait out the anti-chatter window:
    # at startup (and on an emergency release) the first motion command would
    # otherwise be suppressed for decision_cooldown_s.
    o = osc(min_dur=10.0, cooldown=10.0)
    assert o.apply("S", 0.0) == "S"
    assert o.apply("F", 0.01) == "F"


def test_psteering_disabled_by_default():
    assert p_steer_speed("L", -0.3, kp=0.0, min_pwm=120) is None


def test_psteering_speed_is_proportional_and_clamped():
    assert p_steer_speed("L", -0.2, kp=600.0, min_pwm=120) == 120
    assert p_steer_speed("R", 0.25, kp=600.0, min_pwm=120) == 150
    assert p_steer_speed("L", -0.01, kp=600.0, min_pwm=120) == 120  # floor
    assert p_steer_speed("R", 0.9, kp=600.0, min_pwm=120) == 255  # ceiling


def test_psteering_speed_only_on_turns():
    assert p_steer_speed("F", 0.0, kp=600.0, min_pwm=120) is None
    assert p_steer_speed("S", 0.5, kp=600.0, min_pwm=120) is None


def test_search_finds_target():
    s = SearchRotation(timeout_s=30.0, max_rotations=2, rotation_duration_s=20.0)
    s.start(now=0.0)
    cmd, done, _ = s.update(False, now=5.0)
    assert cmd == "R" and not done
    cmd, done, _ = s.update(True, now=6.0)
    assert done and cmd == "S"


def test_search_timeout_and_max_rotations():
    s = SearchRotation(timeout_s=10.0, max_rotations=5, rotation_duration_s=20.0)
    s.start(now=0.0)
    cmd, done, msg = s.update(False, now=11.0)
    assert done and cmd == "S" and "timeout" in msg

    s2 = SearchRotation(timeout_s=100.0, max_rotations=1, rotation_duration_s=10.0)
    s2.start(now=0.0)
    cmd, done, _ = s2.update(False, now=11.0)
    assert done and cmd == "S"
