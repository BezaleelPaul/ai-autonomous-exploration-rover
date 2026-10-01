import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from software.navigation.gap_assessment import GapAssessor
from software.navigation.obstacle_avoidance import ObstacleAvoidance
from software.safety.safety_manager import SafetyManager


def sm():
    return SafetyManager(emergency_cm=15.0, slow_cm=30.0)


def test_emergency_blocks_forward():
    v = sm().check("F", 10.0, True, True, 0.9, 0.5)
    assert not v.allowed and v.command == "S"


def test_safe_allows_forward():
    v = sm().check("F", 100.0, True, True, 0.9, 0.5)
    assert v.allowed and v.command == "F" and v.reason == "SAFE"


def test_safety_overrides_ai():
    # AI says GO but sensor unsafe -> STOP
    v = sm().check("F", 5.0, True, True)
    assert v.command == "S"


def test_comm_lost_stops():
    v = sm().check("F", 100.0, False, True)
    assert v.command == "S" and v.reason == "COMM_LOST"


def test_camera_fail_safe_state():
    v = sm().check("F", 100.0, True, False)
    assert v.command == "S"


def test_invalid_sensor_blocks_translation_but_allows_turn():
    s = sm()
    v = s.check("F", None, True, True)
    assert v.command == "S"
    v2 = s.check("L", None, True, True)
    assert v2.command == "L"


def test_low_confidence_blocks():
    v = sm().check("F", 100.0, True, True, ai_confidence=0.2, min_confidence=0.5)
    assert v.command == "S" and v.reason == "LOW_CONFIDENCE"


def test_obstacle_avoidance_module():
    o = ObstacleAvoidance(15.0, 30.0)
    assert o.override("F", 10.0) == "S"
    assert o.override("F", 100.0) == "F"
    assert o.override("L", 10.0) == "L"  # turn in place allowed


def test_gap_assessment():
    g = GapAssessor(18.0, 8.0, 0.65)
    assert g.required_width == 34.0
    assert g.assess(50.0, 0.9).level == "SAFE"
    assert g.assess(None, 0.9).level == "UNKNOWN"
    assert g.assess(50.0, 0.1).level == "UNKNOWN"  # low conf never SAFE
    assert not g.assess(20.0, 0.9).feasible
    # UNKNOWN must never be feasible
    assert g.assess(None).feasible is False


def test_emergency_latch_engages_when_very_close():
    s = sm()
    v = s.check("F", 8.0, True, True)  # < 0.7 * 15 = 10.5 -> latch
    assert v.command == "S" and s.emergency_latch


def test_emergency_latch_blocks_all_motion_until_clear():
    s = sm()
    s.check("F", 8.0, True, True)
    assert s.emergency_latch
    # still latched while obstacle remains (10cm < slow 30cm)
    v = s.check("L", 10.0, True, True)
    assert v.command == "S" and v.reason == "EMERGENCY_LATCH"


def test_emergency_latch_recovers_when_obstacle_cleared():
    # R4: latch must auto-release once distance >= slow_cm (no permanent lockout)
    s = sm()
    s.check("F", 8.0, True, True)
    assert s.emergency_latch
    v = s.check("F", 50.0, True, True, 0.9, 0.5)
    assert v.command == "F" and not s.emergency_latch


def test_emergency_latch_manual_reset():
    s = sm()
    s.check("F", 8.0, True, True)
    s.reset_latch()
    assert not s.emergency_latch
