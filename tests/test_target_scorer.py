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
