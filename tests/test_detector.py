import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from software.ai.detection import Detection
from software.ai.detector import MockDetector
from software.perception.object_tracker import ObjectTracker
from software.perception.position_estimator import classify_position, is_centered


def test_detection_fields():
    d = Detection("bottle", 0.86, 100, 100, 200, 260)
    assert d.center_x == 150
    assert d.width == 100
    assert d.center_x_norm(640) == 150 / 640
    assert d.width_ratio(640) == 100 / 640


def test_confidence_threshold_filter():
    t = ObjectTracker("bottle", 0.5)
    dets = [
        Detection("bottle", 0.3, 0, 0, 10, 10),
        Detection("bottle", 0.9, 0, 0, 50, 50),
    ]
    assert t.select(dets) is not None and t.select(dets).confidence == 0.9  # type: ignore
    assert ObjectTracker("bottle", 0.95).select(dets) is None


def test_position_classification():
    assert classify_position(0.10) == "LEFT"
    assert classify_position(0.50) == "CENTER"
    assert classify_position(0.90) == "RIGHT"
    assert classify_position(0.33, 0.33, 0.66) == "CENTER"  # boundary -> center
    assert is_centered(0.5) and not is_centered(0.8)


def test_mock_detector_positions():
    for pos, frac in [("LEFT", 0.16), ("CENTER", 0.5), ("RIGHT", 0.84)]:
        m = MockDetector(position=pos)
        d = m.detect()[0]
        assert classify_position(d.center_x_norm(640)) == pos
    assert MockDetector(emit=False).detect() == []


def test_tracker_picks_largest():
    t = ObjectTracker("bottle", 0.1)
    small = Detection("bottle", 0.9, 0, 0, 10, 10)
    big = Detection("bottle", 0.8, 0, 0, 100, 100)
    assert t.select([small, big]) is big
