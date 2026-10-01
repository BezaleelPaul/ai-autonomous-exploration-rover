"""Unit tests for software/ai/detection_metrics.py (pure, no model)."""

from __future__ import annotations

import pytest

from software.ai.detection_metrics import (
    AP_INTERPOLATION_POINTS,
    Box,
    GroundTruth,
    Prediction,
    aggregate,
    average_precision,
    evaluate,
    iou,
    match_frame,
)


def _box(x1: float, y1: float, x2: float, y2: float) -> Box:
    return Box(x1, y1, x2, y2)


def _pred(box: Box, conf: float, name: str = "person") -> Prediction:
    return Prediction(box=box, confidence=conf, class_name=name)


def _gt(box: Box, name: str = "person") -> GroundTruth:
    return GroundTruth(box=box, class_name=name)


# --- iou -------------------------------------------------------------------


def test_iou_identical_boxes_is_one() -> None:
    assert iou(_box(0, 0, 10, 10), _box(0, 0, 10, 10)) == 1.0


def test_iou_disjoint_boxes_is_zero() -> None:
    assert iou(_box(0, 0, 10, 10), _box(20, 20, 30, 30)) == 0.0


def test_iou_partial_overlap() -> None:
    a, b = _box(0, 0, 10, 10), _box(5, 0, 15, 10)
    assert iou(a, b) == pytest.approx(50 / 150, abs=1e-6)


def test_iou_zero_area_box_returns_zero() -> None:
    assert iou(_box(0, 0, 0, 0), _box(0, 0, 10, 10)) == 0.0


# --- match_frame -----------------------------------------------------------


def test_perfect_match_is_all_true_positives() -> None:
    preds = [_pred(_box(0, 0, 10, 10), 0.9), _pred(_box(20, 0, 30, 10), 0.8)]
    gts = [_gt(_box(0, 0, 10, 10)), _gt(_box(20, 0, 30, 10))]
    result = match_frame(preds, gts)
    assert (result.true_positives, result.false_positives) == (2, 0)
    assert result.false_negatives == 0
    assert result.duplicates == 0


def test_class_mismatch_is_false_positive_and_false_negative() -> None:
    preds = [_pred(_box(0, 0, 10, 10), 0.9, name="dog")]
    gts = [_gt(_box(0, 0, 10, 10), name="person")]
    result = match_frame(preds, gts)
    assert result.true_positives == 0
    assert result.false_positives == 1
    assert result.false_negatives == 1


def test_duplicate_detection_is_counted_separately() -> None:
    """Two overlapping preds on one GT: one TP + one duplicate, GT still 1."""
    gt = _gt(_box(0, 0, 10, 10))
    preds = [_pred(_box(0, 0, 10, 10), 0.9), _pred(_box(0, 0, 10, 10), 0.8)]
    result = match_frame(preds, [gt])
    assert result.true_positives == 1
    assert result.duplicates == 1
    assert result.false_positives == 1
    assert result.false_negatives == 0


def test_highest_confidence_wins_the_ground_truth() -> None:
    """Confidence order decides which pred claims the single GT."""
    gt = _gt(_box(0, 0, 10, 10))
    preds = [_pred(_box(0, 0, 10, 10), 0.4), _pred(_box(0, 0, 10, 10), 0.95)]
    result = match_frame(preds, [gt])
    assert result.matched_confidences == (0.95,)


def test_low_iou_prediction_is_a_miss_not_a_duplicate() -> None:
    preds = [_pred(_box(0, 0, 10, 10), 0.9), _pred(_box(50, 50, 60, 60), 0.8)]
    gts = [_gt(_box(0, 0, 10, 10))]
    result = match_frame(preds, gts)
    assert result.duplicates == 0
    assert result.false_positives == 1


def test_empty_prediction_list_counts_all_ground_truths_as_misses() -> None:
    gts = [_gt(_box(0, 0, 10, 10)), _gt(_box(20, 0, 30, 10))]
    result = match_frame([], gts)
    assert result.true_positives == 0
    assert result.false_negatives == 2
    assert result.predictions == 0


def test_empty_image_with_no_predictions_is_clean() -> None:
    result = match_frame([], [])
    assert (result.true_positives, result.false_positives) == (0, 0)
    assert result.false_negatives == 0


def test_match_frame_rejects_invalid_iou_threshold() -> None:
    with pytest.raises(ValueError, match="iou_threshold"):
        match_frame([], [], iou_threshold=0.0)
    with pytest.raises(ValueError, match="iou_threshold"):
        match_frame([], [], iou_threshold=1.5)


# --- aggregate -------------------------------------------------------------


def test_aggregate_precision_recall_f1() -> None:
    good = match_frame(
        [_pred(_box(0, 0, 10, 10), 0.9), _pred(_box(20, 0, 30, 10), 0.8)],
        [_gt(_box(0, 0, 10, 10)), _gt(_box(20, 0, 30, 10))],
    )
    missed = match_frame(
        [_pred(_box(0, 0, 10, 10), 0.9)],
        [_gt(_box(0, 0, 10, 10)), _gt(_box(20, 0, 30, 10))],
    )
    stats = aggregate([good, missed])
    assert (stats["true_positives"], stats["false_negatives"]) == (3, 1)
    assert stats["precision"] == 1.0
    assert stats["recall"] == pytest.approx(0.75, abs=1e-4)
    assert stats["f1"] == pytest.approx(0.8571, abs=1e-4)


def test_aggregate_multi_object_recall_only_uses_dense_images() -> None:
    """Images with a single GT must not dilute the multi-object recall."""
    dense_hit = match_frame(
        [
            _pred(_box(0, 0, 10, 10), 0.9),
            _pred(_box(20, 0, 30, 10), 0.8),
            _pred(_box(40, 0, 50, 10), 0.7),
        ],
        [
            _gt(_box(0, 0, 10, 10)),
            _gt(_box(20, 0, 30, 10)),
            _gt(_box(40, 0, 50, 10)),
        ],
    )
    single_missed = match_frame([], [_gt(_box(0, 0, 10, 10))])
    stats = aggregate([dense_hit, single_missed])
    assert stats["images_with_multiple_objects"] == 1
    assert stats["multi_object_recall"] == 1.0
    assert stats["recall"] == pytest.approx(0.75, abs=1e-4)


def test_aggregate_counts_duplicates_and_image_tallies() -> None:
    dup = match_frame(
        [_pred(_box(0, 0, 10, 10), 0.9), _pred(_box(0, 0, 10, 10), 0.8)],
        [_gt(_box(0, 0, 10, 10))],
    )
    stats = aggregate([dup])
    assert stats["duplicate_detections"] == 1
    assert stats["images"] == 1
    assert stats["mean_predictions_per_image"] == 2.0
    assert stats["mean_ground_truths_per_image"] == 1.0


def test_aggregate_of_no_frames_is_all_zero() -> None:
    stats = aggregate([])
    assert stats["images"] == 0
    assert stats["precision"] == 0.0
    assert stats["recall"] == 0.0
    assert stats["f1"] == 0.0
    assert stats["multi_object_recall"] == 0.0


# --- average_precision -----------------------------------------------------


def test_average_precision_perfect_ranking_is_one() -> None:
    preds = {"a": [_pred(_box(0, 0, 10, 10), 0.99)]}
    gts = {"a": [_gt(_box(0, 0, 10, 10))]}
    ap = average_precision(preds, gts)
    assert ap["mAP"] == 1.0
    assert ap["classes_evaluated"] == 1
    assert ap["per_class_ap"]["person"] == 1.0


def test_average_precision_ignores_classes_without_ground_truth() -> None:
    preds = {"a": [_pred(_box(0, 0, 10, 10), 0.9, name="dog")]}
    gts = {"a": [_gt(_box(0, 0, 10, 10), name="person")]}
    ap = average_precision(preds, gts)
    assert ap["classes_evaluated"] == 1
    assert "dog" not in ap["per_class_ap"]


def test_average_precision_is_zero_without_predictions() -> None:
    ap = average_precision({}, {"a": [_gt(_box(0, 0, 10, 10))]})
    assert ap["mAP"] == 0.0


def test_average_precision_penalises_false_positives_ranked_first() -> None:
    """A high-confidence miss drags precision down across the curve."""
    preds = {
        "a": [
            _pred(_box(90, 90, 100, 100), 0.99),
            _pred(_box(0, 0, 10, 10), 0.5),
        ]
    }
    gts = {"a": [_gt(_box(0, 0, 10, 10))]}
    ap = average_precision(preds, gts)
    assert 0.0 < ap["mAP"] < 1.0


def test_interpolation_uses_configured_sample_count() -> None:
    assert AP_INTERPOLATION_POINTS == 101


# --- evaluate --------------------------------------------------------------


def test_evaluate_prunes_by_operating_confidence() -> None:
    """Low-confidence boxes count for AP but not for the operating point."""
    preds = {
        "a": [
            _pred(_box(0, 0, 10, 10), 0.9),
            _pred(_box(20, 0, 30, 10), 0.1),
        ]
    }
    gts = {"a": [_gt(_box(0, 0, 10, 10)), _gt(_box(20, 0, 30, 10))]}
    report = evaluate(preds, gts, operating_confidence=0.5)
    operating = report["operating_point"]
    assert operating["true_positives"] == 1
    assert operating["false_negatives"] == 1
    assert operating["recall"] == 0.5
    assert report["ap"]["mAP"] == 1.0


def test_evaluate_without_confidence_keeps_everything() -> None:
    preds = {"a": [_pred(_box(0, 0, 10, 10), 0.01)]}
    gts = {"a": [_gt(_box(0, 0, 10, 10))]}
    report = evaluate(preds, gts, operating_confidence=None)
    assert report["operating_point"]["true_positives"] == 1
    assert report["operating_confidence"] is None


def test_evaluate_rejects_empty_ground_truth() -> None:
    with pytest.raises(ValueError, match="ground-truth"):
        evaluate({}, {})


def test_evaluate_rejects_predictions_for_unknown_images() -> None:
    with pytest.raises(ValueError, match="without ground truth"):
        evaluate({"bogus": [_pred(_box(0, 0, 1, 1), 0.9)]}, {"a": []})
