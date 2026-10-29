"""Unit and integration tests for multi-object tracking, SAHI sliced inference, and point deformation tracking."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from software.ai.detection import Detection
from software.ai.detector import YoloDetector, box_iou, nms_detections
from software.perception.multi_object_tracker import MultiObjectTracker, TrackedObject
from software.perception.point_tracker import PointTracker


def test_box_iou():
    b1 = (0.0, 0.0, 10.0, 10.0)
    b2 = (0.0, 0.0, 10.0, 10.0)
    assert pytest.approx(box_iou(b1, b2)) == 1.0

    b3 = (5.0, 0.0, 15.0, 10.0)
    # intersection: 5 x 10 = 50, union = 100 + 100 - 50 = 150 -> 50 / 150 = 1/3
    assert pytest.approx(box_iou(b1, b3), rel=1e-3) == 1.0 / 3.0

    b4 = (20.0, 20.0, 30.0, 30.0)
    assert box_iou(b1, b4) == 0.0


def test_nms_detections():
    d1 = Detection("bottle", 0.9, 10, 10, 50, 50)
    d2 = Detection("bottle", 0.8, 12, 12, 52, 52)  # High overlap with d1 -> should suppress
    d3 = Detection("chair", 0.85, 11, 11, 51, 51)  # Different class -> should keep
    d4 = Detection("bottle", 0.7, 200, 200, 250, 250)  # No overlap -> should keep

    kept = nms_detections([d1, d2, d3, d4], iou_thresh=0.5)
    assert len(kept) == 3
    assert d1 in kept
    assert d2 not in kept
    assert d3 in kept
    assert d4 in kept


def test_tracker_normalization():
    assert YoloDetector._normalize_tracker("botsort") == "botsort.yaml"
    assert YoloDetector._normalize_tracker("bytetrack") == "bytetrack.yaml"
    assert YoloDetector._normalize_tracker("tracktrack") == "tracktrack.yaml"
    assert YoloDetector._normalize_tracker("fasttrack") == "fasttrack.yaml"
    assert YoloDetector._normalize_tracker("ocsort") == "ocsort.yaml"
    assert YoloDetector._normalize_tracker("default") == "bytetrack.yaml"
    assert YoloDetector._normalize_tracker("custom.yaml") == "custom.yaml"


def test_point_tracker_optical_flow_and_coasting():
    pt = PointTracker(min_tracked_points=2, max_coast_frames=3)

    # Frame 1: Create a frame with a textured target box
    f1 = np.zeros((200, 200, 3), dtype=np.uint8)
    f1[30:70, 30:70] = np.random.randint(50, 255, (40, 40, 3), dtype=np.uint8)

    det = Detection("bottle", 0.88, 30.0, 30.0, 70.0, 70.0, track_id=42)
    res1 = pt.update(f1, [det])
    assert len(res1) == 1
    tid, box, conf, cls_name, is_coasting = res1[0]
    assert tid == 42
    assert not is_coasting

    # Frame 2: Shift the frame by (+10, +5) pixels simulating camera or object motion
    f2 = np.zeros((200, 200, 3), dtype=np.uint8)
    f2[35:75, 40:80] = f1[30:70, 30:70]

    # Detector drops the object (empty detections) -> PointTracker must coast!
    res2 = pt.update(f2, [])
    assert len(res2) == 1
    tid2, box2, conf2, cls_name2, is_coasting2 = res2[0]
    assert tid2 == 42
    assert is_coasting2
    # The box should have shifted toward the new location
    assert box2[0] > 30.0 or box2[1] > 30.0


def test_multi_object_tracker_tracks_multiple_targets():
    mot = MultiObjectTracker(enable_point_tracking=False)

    d1 = Detection("bottle", 0.9, 10.0, 10.0, 50.0, 50.0, track_id=1)
    d2 = Detection("person", 0.85, 100.0, 50.0, 180.0, 200.0, track_id=2)
    d3 = Detection("chair", 0.75, 300.0, 100.0, 400.0, 300.0, track_id=3)

    tracks = mot.update([d1, d2, d3], now=100.0)
    assert len(tracks) == 3
    track_ids = {t.track_id for t in tracks}
    assert track_ids == {1, 2, 3}

    # Step 2: Object 1 moves to the right
    d1_moved = Detection("bottle", 0.92, 30.0, 10.0, 70.0, 50.0, track_id=1)
    tracks2 = mot.update([d1_moved, d2, d3], now=101.0)
    t1 = next(t for t in tracks2 if t.track_id == 1)
    assert t1.track_age == 2
    assert t1.velocity_x > 0  # Moved to the right

    # Verify target query
    target = mot.get_target_track("bottle")
    assert target is not None and target.track_id == 1


@pytest.mark.parametrize("tracker_cfg", ["bytetrack.yaml", "botsort.yaml", "tracktrack.yaml"])
def test_ultralytics_trackers_execution(tracker_cfg):
    """Test that all tracker algorithms run successfully on synthetic frames."""
    pytest.importorskip("ultralytics")
    det = YoloDetector(
        model="yolo26n.pt",
        tracker=tracker_cfg,
        imgsz=320,
        track=True,
    )
    assert det.load(), f"Failed to load detector with {tracker_cfg}"

    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    dets = det.detect(frame)
    assert isinstance(dets, list)


def test_sahi_sliced_inference_execution():
    """Verify SAHI sliced inference executes and returns valid bounded detections."""
    pytest.importorskip("ultralytics")
    det = YoloDetector(
        model="yolo26n.pt",
        imgsz=320,
        sahi_enabled=True,
        sahi_slice_size=320,
        sahi_overlap=0.20,
    )
    assert det.load()

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    dets = det.detect(frame)
    assert isinstance(dets, list)
    for d in dets:
        assert 0 <= d.x1 <= 640
        assert 0 <= d.y1 <= 480
        assert 0 <= d.x2 <= 640
        assert 0 <= d.y2 <= 480
