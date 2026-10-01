"""Regression tests for reviewer-found fixes: non-finite telemetry, lock expiry at t=0."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from software.navigation.obstacle_avoidance import ObstacleAvoidance
from software.perception.object_tracker import ObjectTracker
from software.safety.safety_manager import SafetyManager


def test_nan_distance_never_crashes_and_blocks_forward():
    v = SafetyManager(15.0, 30.0).check("F", float("nan"), True, True, 0.9, 0.5)
    assert v.command == "S"
    assert ObstacleAvoidance(15.0, 30.0).override("F", float("nan")) == "S"
    assert ObstacleAvoidance(15.0, 30.0).override("L", float("nan")) == "L"


def test_inf_and_str_distance_blocked():
    for bad in (float("inf"), "25", None, -1.0):
        v = SafetyManager(15.0, 30.0).check("F", bad, True, True, 0.9, 0.5)
        assert v.command == "S", f"failed for {bad!r}"


def test_tracker_lock_expires_from_zero_time():
    t = ObjectTracker("bottle", 0.1, lock_duration_s=1.0)
    t.update([], now=0.0)
    t._last_seen = 0.0  # simulate a sighting exactly at t=0
    assert t.update([], now=2.0) is None
    assert t._locked_since is None
