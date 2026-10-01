import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from software.navigation.decision_engine import DecisionEngine


def eng():
    return DecisionEngine(
        center_tolerance=0.06, min_command_duration_s=10.0, cooldown_s=0.0
    )


def test_left_right_center():
    e = DecisionEngine(min_command_duration_s=0.0, cooldown_s=0.0)
    assert e.decide("LEFT", False, True, now=0.0).command == "L"
    assert e.decide("RIGHT", False, True, now=1.0).command == "R"
    assert e.decide("CENTER", False, True, now=2.0).command == "F"


def test_target_lost_and_close():
    e = DecisionEngine(min_command_duration_s=0.0, cooldown_s=0.0)
    assert e.decide("CENTER", False, False, now=0.0).command == "S"
    assert e.decide("CENTER", True, True, now=1.0).command == "S"


def test_anti_oscillation_blocks_rapid_flip():
    e = eng()
    assert e.decide("LEFT", False, True, now=0.0).command == "L"
    # 1s later R requested but min duration 10s blocks it -> holds L
    d = e.decide("RIGHT", False, True, now=1.0)
    assert d.command == "L"
    # after 11s flip allowed
    assert e.decide("RIGHT", False, True, now=11.0).command == "R"


def test_state_transitions():
    e = DecisionEngine(min_command_duration_s=0.0, cooldown_s=0.0)
    assert e.decide("CENTER", False, True, now=0.0).state == "APPROACHING"
    assert e.decide("LEFT", False, True, now=1.0).state == "ALIGNING"
    assert e.decide("X", False, False, now=2.0).state == "SEARCHING"


# ------------------------------------------------- P-steering (Protocol v2) --
def test_psteering_disabled_by_default():
    e = DecisionEngine(min_command_duration_s=0.0, cooldown_s=0.0)
    d = e.decide("LEFT", False, True, now=0.0, center_error=-0.3)
    assert d.command == "L" and d.speed is None  # bare L: fw open-loop speed


def test_psteering_speed_is_proportional_to_center_error():
    e = DecisionEngine(
        min_command_duration_s=0.0,
        cooldown_s=0.0,
        steering_kp=600.0,
        steering_min_pwm=120,
    )
    d = e.decide("LEFT", False, True, now=0.0, center_error=-0.2)
    assert d.command == "L" and d.speed == 120  # 600 * 0.2 = 120
    d2 = e.decide("RIGHT", False, True, now=1.0, center_error=0.25)
    assert d2.command == "R" and d2.speed == 150  # 600 * 0.25 = 150


def test_psteering_clamped_to_120_255():
    e = DecisionEngine(
        min_command_duration_s=0.0,
        cooldown_s=0.0,
        steering_kp=600.0,
        steering_min_pwm=120,
    )
    d = e.decide("LEFT", False, True, now=0.0, center_error=-0.01)
    assert d.speed == 120  # floor: a turn never gets less than min_pwm
    d2 = e.decide("RIGHT", False, True, now=1.0, center_error=0.9)
    assert d2.speed == 255  # ceiling


def test_psteering_speed_only_on_turn_commands():
    e = DecisionEngine(
        min_command_duration_s=0.0,
        cooldown_s=0.0,
        steering_kp=600.0,
        steering_min_pwm=120,
    )
    f = e.decide("CENTER", False, True, now=0.0, center_error=0.0)
    assert f.command == "F" and f.speed is None
    s = e.decide("CENTER", False, False, now=1.0, center_error=0.0)
    assert s.command == "S" and s.speed is None
