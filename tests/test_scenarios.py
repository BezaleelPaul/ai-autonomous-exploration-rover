"""Scenario framework: 20+ software-level cases. Expandable JSON-like list."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from software.control.steering import command_for_position
from software.navigation.gap_assessment import GapAssessor
from software.navigation.obstacle_avoidance import ObstacleAvoidance
from software.safety.safety_manager import SafetyManager


def pipeline(
    ai_position,
    target_present,
    very_close,
    distance_cm,
    serial_ok=True,
    camera_ok=True,
    confidence=0.9,
):
    """Full chain: Decision -> Avoidance -> Safety. Returns final command."""
    desired = command_for_position(ai_position, very_close, target_present)[0]
    desired = ObstacleAvoidance(15.0, 30.0).override(desired, distance_cm)
    v = SafetyManager(15.0, 30.0).check(
        desired, distance_cm, serial_ok, camera_ok, confidence, 0.5
    )
    return v.command, v.reason


SCENARIOS = [
    # perception
    {
        "name": "no object -> stop",
        "pos": "NONE",
        "present": False,
        "close": False,
        "dist": 100.0,
        "expected": "S",
        "cat": "perception",
    },
    {
        "name": "low confidence -> stop",
        "pos": "CENTER",
        "present": True,
        "close": False,
        "dist": 100.0,
        "conf": 0.2,
        "expected": "S",
        "cat": "perception",
    },
    {
        "name": "target left open -> L",
        "pos": "LEFT",
        "present": True,
        "close": False,
        "dist": 100.0,
        "expected": "L",
        "cat": "perception",
    },
    {
        "name": "target center open -> F",
        "pos": "CENTER",
        "present": True,
        "close": False,
        "dist": 100.0,
        "expected": "F",
        "cat": "perception",
    },
    {
        "name": "target right open -> R",
        "pos": "RIGHT",
        "present": True,
        "close": False,
        "dist": 100.0,
        "expected": "R",
        "cat": "perception",
    },
    {
        "name": "very close -> stop",
        "pos": "CENTER",
        "present": True,
        "close": True,
        "dist": 100.0,
        "expected": "S",
        "cat": "perception",
    },
    # obstacle avoidance
    {
        "name": "obstacle directly ahead",
        "pos": "CENTER",
        "present": True,
        "close": False,
        "dist": 10.0,
        "expected": "S",
        "cat": "obstacle",
    },
    {
        "name": "slow zone still forward",
        "pos": "CENTER",
        "present": True,
        "close": False,
        "dist": 25.0,
        "expected": "F",
        "cat": "obstacle",
    },
    {
        "name": "emergency allows turn to escape",
        "pos": "LEFT",
        "present": True,
        "close": False,
        "dist": 10.0,
        "expected": "L",
        "cat": "obstacle",
    },
    {
        "name": "invalid sensor blocks forward",
        "pos": "CENTER",
        "present": True,
        "close": False,
        "dist": None,
        "expected": "S",
        "cat": "obstacle",
    },
    # target search / nav
    {
        "name": "target behind rover (no fix) -> search stop",
        "pos": "NONE",
        "present": False,
        "close": False,
        "dist": 100.0,
        "expected": "S",
        "cat": "search",
    },
    {
        "name": "target disappears -> stop",
        "pos": "NONE",
        "present": False,
        "close": False,
        "dist": 50.0,
        "expected": "S",
        "cat": "search",
    },
    # safety / comms
    {
        "name": "serial lost -> stop",
        "pos": "CENTER",
        "present": True,
        "close": False,
        "dist": 100.0,
        "serial": False,
        "expected": "S",
        "cat": "safety",
    },
    {
        "name": "camera lost -> stop",
        "pos": "CENTER",
        "present": True,
        "close": False,
        "dist": 100.0,
        "camera": False,
        "expected": "S",
        "cat": "safety",
    },
    {
        "name": "ai says go sensor says no -> stop",
        "pos": "CENTER",
        "present": True,
        "close": False,
        "dist": 8.0,
        "expected": "S",
        "cat": "safety",
    },
    {
        "name": "dead end (close obstacle, target center) -> stop",
        "pos": "CENTER",
        "present": True,
        "close": False,
        "dist": 12.0,
        "expected": "S",
        "cat": "edge",
    },
    {
        "name": "oscillation guard covered in unit tests",
        "pos": "CENTER",
        "present": True,
        "close": False,
        "dist": 100.0,
        "expected": "F",
        "cat": "edge",
    },
    {
        "name": "both sides blocked but turning allowed",
        "pos": "LEFT",
        "present": True,
        "close": False,
        "dist": 10.0,
        "expected": "L",
        "cat": "edge",
    },
    {
        "name": "safe distance normal op",
        "pos": "RIGHT",
        "present": True,
        "close": False,
        "dist": 200.0,
        "expected": "R",
        "cat": "edge",
    },
    {
        "name": "backward blocked by invalid sensor",
        "pos": "NONE",
        "present": False,
        "close": False,
        "dist": -1.0,
        "expected": "S",
        "cat": "comm",
    },
    {
        "name": "target at edge still classified",
        "pos": "LEFT",
        "present": True,
        "close": False,
        "dist": 60.0,
        "expected": "L",
        "cat": "perception",
    },
    {
        "name": "target reached holds stop",
        "pos": "CENTER",
        "present": True,
        "close": True,
        "dist": 40.0,
        "expected": "S",
        "cat": "search",
    },
]


def test_scenarios():
    failed = []
    for sc in SCENARIOS:
        cmd, reason = pipeline(
            sc["pos"],
            sc["present"],
            sc["close"],
            sc.get("dist"),
            sc.get("serial", True),
            sc.get("camera", True),
            sc.get("conf", 0.9),
        )
        if cmd != sc["expected"]:
            failed.append(f"{sc['name']}: got {cmd} ({reason}), want {sc['expected']}")
    assert not failed, "\n".join(failed)


def test_gap_scenarios():
    g = GapAssessor(18.0, 8.0, 0.65)
    assert g.assess(60, 0.9).feasible  # wide gap
    assert not g.assess(30, 0.9).feasible  # narrow gap
    assert g.assess(None, 0.9).level == "UNKNOWN"
    assert g.assess(60, 0.2).level == "UNKNOWN"  # moving obstacle / uncertain
