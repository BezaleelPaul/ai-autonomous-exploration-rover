"""Unit tests for TargetScorer (Layer 4 target selection & scoring)."""

import pytest
from software.ai.detection import Detection
from software.perception.target_scorer import TargetScorer


def test_target_scorer_multi_criteria():
    scorer = TargetScorer()

    # Two persons:
    # Person 1: centered, mature track, medium confidence (0.85)
    det1 = Detection("person", 0.85, 270, 150, 370, 350, track_id=1)
    # Person 2: extreme corner, young track, high confidence (0.92)
    det2 = Detection("person", 0.92, 10, 10, 60, 100, track_id=2)

    score1 = scorer.score_candidate(det1, "person", track_age=20, frame_width=640, frame_height=480)
    score2 = scorer.score_candidate(det2, "person", track_age=2, frame_width=640, frame_height=480)

    # Even though det2 has higher confidence, det1 is centered, larger, and stable
    assert score1.centering_score > score2.centering_score
    assert score1.stability_score > score2.stability_score
    assert score1.total_score > score2.total_score


def test_select_best_picks_optimal_target():
    scorer = TargetScorer()
    candidates = [
        (Detection("chair", 0.97, 100, 100, 300, 300, track_id=4), 10),
        (Detection("person", 0.88, 280, 100, 360, 350, track_id=7), 15),
        (Detection("bottle", 0.81, 200, 200, 250, 300, track_id=9), 5),
    ]

    # Mission objective is "person"
    best = scorer.select_best(candidates, "person", frame_width=640, frame_height=480)
    assert best is not None
    assert best.detection.class_name == "person"
    assert best.detection.track_id == 7


def test_foreground_first_then_distant_high_precision():
    scorer = TargetScorer(close_area_ratio=0.03, min_distant_confidence=0.70, min_distant_track_age=4)

    # Candidate 1: Immediate foreground (in front of camera, large area)
    # Area: 160 x 200 = 32000 / 307200 = 0.104 > 0.03 (Foreground)
    det_fg = Detection("bottle", 0.75, 200, 200, 360, 400, track_id=1)

    # Candidate 2: Far away in background (small, area: 25 x 30 = 750 / 307200 = 0.0024)
    # Even if it has higher confidence (0.95) and mature age (10)
    det_bg = Detection("bottle", 0.95, 450, 100, 475, 130, track_id=2)

    candidates = [(det_fg, 3), (det_bg, 10)]
    best = scorer.select_best(candidates, "bottle", frame_width=640, frame_height=480)

    # RULE 1: Foreground object immediately in front of camera is selected FIRST!
    assert best is not None
    assert best.detection.track_id == 1
    assert best.is_foreground is True

    # RULE 2: When foreground is gone, distant target is considered ONLY WITH HIGH PRECISION
    # Far candidate with low confidence or young track is rejected
    det_bg_low_conf = Detection("bottle", 0.50, 450, 100, 475, 130, track_id=3)
    best_distant_reject = scorer.select_best([(det_bg_low_conf, 1)], "bottle", frame_width=640, frame_height=480)
    assert best_distant_reject is None  # Dropped because distant requires high precision

    # Far candidate with high confidence & mature track is accepted
    best_distant_accept = scorer.select_best([(det_bg, 10)], "bottle", frame_width=640, frame_height=480)
    assert best_distant_accept is not None
    assert best_distant_accept.detection.track_id == 2

