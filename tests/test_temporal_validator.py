"""Unit tests for TemporalValidator (Layer 3 perception validation)."""

import time
import numpy as np
import pytest

from software.ai.detection import Detection
from software.perception.temporal_validator import TemporalValidator, ValidationResult


def test_frame_quality_checks():
    validator = TemporalValidator(min_frame_brightness=10.0, max_frame_brightness=240.0)

    # None or empty
    assert validator.check_frame_quality(None)[0] is False
    assert validator.check_frame_quality(np.zeros((0, 0, 3)))[0] is False

    # Pitch black frame
    black_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    ok, reason = validator.check_frame_quality(black_frame)
    assert not ok
    assert "DARK" in reason or "ZERO_VARIANCE" in reason

    # Overexposed frame
    bright_frame = np.full((100, 100, 3), 255, dtype=np.uint8)
    ok, reason = validator.check_frame_quality(bright_frame)
    assert not ok
    assert "OVEREXPOSED" in reason or "ZERO_VARIANCE" in reason

    # Normal frame with texture
    normal_frame = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
    ok, reason = validator.check_frame_quality(normal_frame)
    assert ok
    assert reason == "FRAME_OK"


def test_bbox_sanity_checks():
    validator = TemporalValidator(min_box_ratio=0.02, max_box_ratio=0.9)

    # Valid box
    det_good = Detection("person", 0.9, 100, 100, 200, 300)
    ok, reason = validator.check_bbox_sanity(det_good, 640, 480)
    assert ok
    assert reason == "BBOX_OK"

    # Microscopic box
    det_tiny = Detection("person", 0.9, 100, 100, 102, 102)
    ok, reason = validator.check_bbox_sanity(det_tiny, 640, 480)
    assert not ok
    assert "BBOX_TOO_SMALL" in reason

    # Impossible aspect ratio (e.g. 350px wide, 20px high -> aspect 17.5 > 10.0)
    det_aspect = Detection("person", 0.9, 50, 50, 400, 70)
    ok, reason = validator.check_bbox_sanity(det_aspect, 640, 480)
    assert not ok
    assert "UNREALISTIC_ASPECT" in reason


def test_track_persistence_rejection_and_acceptance():
    # Requires 3 consecutive hits before accepting
    validator = TemporalValidator(min_confidence=0.6, min_persistence_frames=3)

    det = Detection("person", 0.85, 100, 100, 200, 300, track_id=42)

    # Frame 1: age=1 < 3 -> rejected as UNSTABLE
    res1 = validator.update_and_validate(det, 640, 480)
    assert not res1.is_valid
    assert "TRACK_UNSTABLE" in res1.reason
    assert res1.track_age == 1

    # Frame 2: age=2 < 3 -> rejected
    res2 = validator.update_and_validate(det, 640, 480)
    assert not res2.is_valid
    assert res2.track_age == 2

    # Frame 3: age=3 >= 3 -> ACCEPTED!
    res3 = validator.update_and_validate(det, 640, 480)
    assert res3.is_valid
    assert res3.reason == "ACCEPTED"
    assert res3.track_age == 3


def test_low_confidence_rejected_immediately():
    validator = TemporalValidator(min_confidence=0.7)
    det_low = Detection("person", 0.52, 100, 100, 200, 300, track_id=7)
    res = validator.update_and_validate(det_low, 640, 480)
    assert not res.is_valid
    assert "LOW_CONFIDENCE" in res.reason


def test_appearance_mismatch_defective_lookalike_rejected():
    validator = TemporalValidator(
        min_confidence=0.5,
        min_persistence_frames=2,
        max_appearance_distance=0.50,
    )
    # Real target: bright green texture
    real_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    real_frame[100:300, 100:200, 1] = 200

    det_real = Detection("bottle", 0.90, 100, 100, 200, 300, track_id=10)

    # Frame 1: initial observation
    res1 = validator.update_and_validate(det_real, 640, 480, frame=real_frame)
    assert not res1.is_valid  # age=1 < 2

    # Frame 2: confirmed real target
    res2 = validator.update_and_validate(det_real, 640, 480, frame=real_frame)
    assert res2.is_valid
    assert res2.reason == "ACCEPTED"

    # Frame 3: Defective lookalike / impostor at the same position claiming track_id=10
    # But it has completely different red texture
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    fake_frame[100:300, 100:200, 2] = 250  # red channel instead of green

    det_fake = Detection("bottle", 0.88, 100, 100, 200, 300, track_id=10)
    res_fake = validator.update_and_validate(det_fake, 640, 480, frame=fake_frame)

    assert not res_fake.is_valid
    assert "APPEARANCE_MISMATCH_DEFECTIVE" in res_fake.reason
    assert res_fake.appearance_distance >= 0.50


def test_high_uncertainty_defective_rejected():
    validator = TemporalValidator(min_confidence=0.5, max_uncertainty=0.80)

    # Defective, flat, blown out uniform white patch
    blown_frame = np.full((480, 640, 3), 254, dtype=np.uint8)
    det = Detection("person", 0.95, 100, 100, 200, 300, track_id=20)

    res = validator.update_and_validate(det, 640, 480, frame=blown_frame)
    assert not res.is_valid
    assert "HIGH_UNCERTAINTY_DEFECTIVE" in res.reason
    assert res.uncertainty > 0.80


def test_frame_motion_blur_filter():
    validator = TemporalValidator(min_blur_score=30.0)

    # Create a blurred uniform gradient frame
    blurred_frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
    ok, reason = validator.check_frame_quality(blurred_frame)
    assert not ok
    assert "FRAME_MOTION_BLUR" in reason or "ZERO_VARIANCE" in reason

