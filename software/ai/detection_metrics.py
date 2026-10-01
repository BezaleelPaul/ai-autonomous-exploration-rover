"""Offline detection-quality metrics for multi-object evaluation.

Pure functions over plain boxes: no model, no I/O, no numpy. Used by
``scripts/eval_detection.py`` to score a detector against a labelled dataset
(COCO128) so accuracy claims can be measured instead of asserted.

Metric conventions:
- Matching is greedy by descending confidence, one prediction to one ground
  truth, same class only, at a single IoU threshold (default 0.5).
- A prediction that overlaps an *already claimed* ground truth counts as a
  ``duplicate`` (and as a false positive) — that is the specific failure mode
  behind "sees N objects but reports N-1 / double-counts one".
- ``multi_object_*`` metrics are restricted to images holding >= 2 ground-truth
  objects, i.e. the case the operator actually asked about.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_IOU = 0.5
AP_INTERPOLATION_POINTS = 101


@dataclass(frozen=True)
class Box:
    """Axis-aligned box in pixel coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


@dataclass(frozen=True)
class Prediction:
    box: Box
    confidence: float
    class_name: str


@dataclass(frozen=True)
class GroundTruth:
    box: Box
    class_name: str


def iou(a: Box, b: Box) -> float:
    """Intersection-over-union of two boxes (0.0 when disjoint)."""
    ix = max(0.0, min(a.x2, b.x2) - max(a.x1, b.x1))
    iy = max(0.0, min(a.y2, b.y2) - max(a.y1, b.y1))
    inter = ix * iy
    if inter <= 0.0:
        return 0.0
    union = a.area + b.area - inter
    return inter / union if union > 0.0 else 0.0


@dataclass(frozen=True)
class FrameResult:
    """Matching outcome for a single image."""

    true_positives: int
    false_positives: int
    false_negatives: int
    duplicates: int
    predictions: int
    ground_truths: int
    matched_confidences: tuple[float, ...]


def match_frame(
    predictions: list[Prediction],
    ground_truths: list[GroundTruth],
    iou_threshold: float = DEFAULT_IOU,
) -> FrameResult:
    """Greedily match one image's predictions against its ground truth."""
    if not 0.0 < iou_threshold <= 1.0:
        raise ValueError(f"iou_threshold must be in (0, 1], got {iou_threshold!r}")

    unmatched = set(range(len(ground_truths)))
    matched: set[int] = set()
    claimed: set[int] = set()
    tp = fp = duplicates = 0
    matched_confidences: list[float] = []

    ranked = sorted(predictions, key=lambda p: p.confidence, reverse=True)
    for pred in ranked:
        best_index: int | None = None
        best_iou = iou_threshold
        for index in sorted(unmatched):
            if ground_truths[index].class_name != pred.class_name:
                continue
            score = iou(pred.box, ground_truths[index].box)
            if score >= best_iou:
                best_iou = score
                best_index = index
        if best_index is not None:
            unmatched.discard(best_index)
            matched.add(best_index)
            claimed.add(best_index)
            tp += 1
            matched_confidences.append(pred.confidence)
            continue
        # Overlaps a ground truth already taken by an earlier (higher
        # confidence) prediction of the same class -> double count.
        if any(
            ground_truths[index].class_name == pred.class_name
            and iou(pred.box, ground_truths[index].box) >= iou_threshold
            for index in claimed
        ):
            duplicates += 1
            fp += 1
        else:
            fp += 1

    return FrameResult(
        true_positives=tp,
        false_positives=fp,
        false_negatives=len(unmatched),
        duplicates=duplicates,
        predictions=len(predictions),
        ground_truths=len(ground_truths),
        matched_confidences=tuple(matched_confidences),
    )


def _ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def aggregate(results: list[FrameResult], iou_threshold: float = DEFAULT_IOU) -> dict:
    """Pool per-frame matches into dataset-level precision / recall / F1."""
    tp = sum(r.true_positives for r in results)
    fp = sum(r.false_positives for r in results)
    fn = sum(r.false_negatives for r in results)
    multi = [r for r in results if r.ground_truths >= 2]

    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = (
        round(2 * precision * recall / (precision + recall), 4)
        if (precision + recall)
        else 0.0
    )

    multi_tp = sum(r.true_positives for r in multi)
    multi_fn = sum(r.false_negatives for r in multi)

    return {
        "iou_threshold": iou_threshold,
        "images": len(results),
        "images_with_multiple_objects": len(multi),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "duplicate_detections": sum(r.duplicates for r in results),
        "multi_object_recall": _ratio(multi_tp, multi_tp + multi_fn),
        "mean_predictions_per_image": round(
            sum(r.predictions for r in results) / len(results), 3
        )
        if results
        else 0.0,
        "mean_ground_truths_per_image": round(
            sum(r.ground_truths for r in results) / len(results), 3
        )
        if results
        else 0.0,
    }


def _interpolated_ap(
    precisions: list[float], recalls: list[float], points: int
) -> float:
    """COCO-style fixed-sample (default 101-point) interpolated AP."""
    if not precisions:
        return 0.0
    grid = [
        max(
            (p for p, r in zip(precisions, recalls) if r >= target / (points - 1)),
            default=0.0,
        )
        for target in range(points)
    ]
    return round(sum(grid) / points, 4)


def average_precision(
    predictions_by_image: dict[str, list[Prediction]],
    ground_truths_by_image: dict[str, list[GroundTruth]],
    iou_threshold: float = DEFAULT_IOU,
) -> dict:
    """Per-class AP@IoU and mean AP over classes that have ground truth."""
    class_names = sorted(
        {gt.class_name for gts in ground_truths_by_image.values() for gt in gts}
    )
    per_class: dict[str, float] = {}
    for class_name in class_names:
        total_gt = sum(
            1
            for gts in ground_truths_by_image.values()
            for gt in gts
            if gt.class_name == class_name
        )
        if total_gt == 0:
            continue
        ranked: list[Prediction] = [
            pred
            for preds in predictions_by_image.values()
            for pred in preds
            if pred.class_name == class_name
        ]
        ranked.sort(key=lambda p: p.confidence, reverse=True)

        # Re-score the ranked list against the same images, in confidence
        # order, so the precision/recall curve is built on cumulative TP/FP.
        claimed: dict[str, set[int]] = {key: set() for key in ground_truths_by_image}
        cumulative_tp = 0
        cumulative_fp = 0
        precisions: list[float] = []
        recalls: list[float] = []
        for pred in ranked:
            frame_keys = [
                key
                for key, gts in ground_truths_by_image.items()
                if any(gt.class_name == class_name for gt in gts)
            ]
            hit = False
            for key in frame_keys:
                candidates = [
                    index
                    for index, gt in enumerate(ground_truths_by_image[key])
                    if gt.class_name == class_name
                    and index not in claimed[key]
                    and iou(pred.box, gt.box) >= iou_threshold
                ]
                if candidates:
                    best = max(
                        candidates,
                        key=lambda index: iou(
                            pred.box, ground_truths_by_image[key][index].box
                        ),
                    )
                    claimed[key].add(best)
                    cumulative_tp += 1
                    hit = True
                    break
            if not hit:
                cumulative_fp += 1
            precisions.append(
                cumulative_tp / (cumulative_tp + cumulative_fp)
                if (cumulative_tp + cumulative_fp)
                else 0.0
            )
            recalls.append(cumulative_tp / total_gt)

        per_class[class_name] = _interpolated_ap(
            precisions, recalls, AP_INTERPOLATION_POINTS
        )

    return {
        "iou_threshold": iou_threshold,
        "classes_evaluated": len(per_class),
        "mAP": round(sum(per_class.values()) / len(per_class), 4) if per_class else 0.0,
        "per_class_ap": dict(sorted(per_class.items(), key=lambda kv: -kv[1])),
    }


def evaluate(
    predictions_by_image: dict[str, list[Prediction]],
    ground_truths_by_image: dict[str, list[GroundTruth]],
    iou_threshold: float = DEFAULT_IOU,
    operating_confidence: float | None = None,
) -> dict:
    """Full report: operating-point metrics plus AP for one dataset split.

    ``operating_confidence`` prunes the stored predictions first, so the
    precision/recall numbers describe what the shipped config would actually
    report, while AP still uses every stored box.
    """
    keys = sorted(ground_truths_by_image)
    if not keys:
        raise ValueError("no ground-truth images supplied")
    if set(predictions_by_image) - set(ground_truths_by_image):
        raise ValueError("predictions supplied for images without ground truth")

    pruned = {
        key: [
            pred
            for pred in predictions_by_image.get(key, [])
            if operating_confidence is None or pred.confidence >= operating_confidence
        ]
        for key in keys
    }
    results = [
        match_frame(pruned[key], ground_truths_by_image[key], iou_threshold)
        for key in keys
    ]
    return {
        "operating_confidence": operating_confidence,
        "operating_point": aggregate(results, iou_threshold),
        "ap": average_precision(
            predictions_by_image, ground_truths_by_image, iou_threshold
        ),
    }
