"""Detection recall and driving caution must stay decoupled.

`ai.confidence_threshold` decides *which objects are reported*; `ai.target_confidence`
decides *which detections we steer toward and drive forward on*. They used to be
the same key, so lowering the detection bar to improve multi-object recall
silently relaxed the forward-motion safety gate. These tests pin the split
(REGRESSION_REPORT.md section 9).

The detection bar is one of the dials ``scripts/autotune_detection.py`` may
move, and ``load_config`` merges the learned overlay in, so the *shipped*
value is asserted by reading ``config/config.yaml`` directly. The act-on bar
is never auto-tuned, so ``load_config`` is fine for it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from software.ai.detection import Detection
from software.main import RoverApp
from software.perception.object_tracker import ObjectTracker
from software.safety.safety_manager import SafetyManager
from software.utils.config_loader import load_config, validate_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg() -> dict:
    return load_config(str(ROOT / "config" / "config.yaml"))


def _bottle(confidence: float) -> Detection:
    return Detection("bottle", confidence, 10.0, 10.0, 60.0, 80.0)


def test_shipped_config_reports_more_objects_than_it_acts_on() -> None:
    shipped = yaml.safe_load(
        (ROOT / "config" / "config.yaml").read_text(encoding="utf-8")
    )["ai"]
    assert shipped["confidence_threshold"] == 0.25, "detection bar was lowered"
    assert shipped["target_confidence"] == 0.5, "act-on bar must stay put"
    assert shipped["target_confidence"] > shipped["confidence_threshold"]


def test_target_confidence_is_accepted_by_config_validation(cfg: dict) -> None:
    cfg["ai"]["target_confidence"] = 1.5  # out of [0,1] must be rejected
    with pytest.raises(ValueError, match="target_confidence"):
        validate_config(cfg)


def test_tracker_ignores_detections_below_the_act_on_bar() -> None:
    tracker = ObjectTracker("bottle", 0.5, lock_duration_s=1.0)
    low = _bottle(0.3)
    assert tracker.select([low]) is None
    assert tracker.select([low, _bottle(0.9)]) is not None


def test_safety_blocks_forward_on_a_low_confidence_target() -> None:
    safety = SafetyManager(emergency_cm=15.0, slow_cm=30.0)
    verdict = safety.check("F", 100.0, True, True, 0.3, 0.5)
    assert not verdict.allowed
    assert verdict.command == "S"
    assert verdict.reason == "LOW_CONFIDENCE"


def test_safety_still_allows_escape_turns_on_low_confidence() -> None:
    safety = SafetyManager(emergency_cm=15.0, slow_cm=30.0)
    verdict = safety.check("L", 100.0, True, True, 0.3, 0.5)
    assert verdict.allowed


def test_safety_allows_forward_at_the_act_on_bar() -> None:
    safety = SafetyManager(emergency_cm=15.0, slow_cm=30.0)
    verdict = safety.check("F", 100.0, True, True, 0.5, 0.5)
    assert verdict.allowed


def test_rover_app_wires_the_two_bars_separately(cfg: dict) -> None:
    app = RoverApp(cfg, mode="observe", target="bottle", mock_hw=True)
    assert app.target_confidence == cfg["ai"]["target_confidence"]
    assert app.tracker.confidence_threshold == cfg["ai"]["target_confidence"]
    # --mock simulates one clearly visible target: actionable, not merely
    # "at the detection bar" (that would make mock mode undrivable)
    assert getattr(app.detector, "confidence", None) == cfg["ai"]["target_confidence"]
