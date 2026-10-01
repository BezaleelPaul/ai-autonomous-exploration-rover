"""Rover-specific intelligence: Multi-criteria Target Selection and Scoring.

Combines detection confidence, track stability, estimated distance/proximity,
angular centering position, and mission objective match into a composite target score:
  Score = w_obj * match + w_conf * conf + w_stab * stability + w_dist * proximity + w_pos * centering
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from software.ai.detection import Detection


@dataclass
class ScoredCandidate:
    detection: Detection
    total_score: float
    confidence_score: float
    stability_score: float
    proximity_score: float
    centering_score: float
    objective_score: float
    track_age: int = 1
    uncertainty: float = 0.0
    is_foreground: bool = True


class TargetScorer:
    """Scores candidate detections across multiple mission and spatial dimensions."""

    def __init__(
        self,
        weight_objective: float = 0.35,
        weight_confidence: float = 0.25,
        weight_stability: float = 0.15,
        weight_proximity: float = 0.15,
        weight_centering: float = 0.10,
        target_stability_age: int = 15,
        close_area_ratio: float = 0.03,
        min_distant_confidence: float = 0.60,
        min_distant_track_age: int = 3,
        prioritize_foreground: bool = True,
    ):
        self.w_obj = weight_objective
        self.w_conf = weight_confidence
        self.w_stab = weight_stability
        self.w_dist = weight_proximity
        self.w_pos = weight_centering
        self.target_stability_age = max(1, target_stability_age)
        self.close_area_ratio = close_area_ratio
        self.min_distant_confidence = min_distant_confidence
        self.min_distant_track_age = min_distant_track_age
        self.prioritize_foreground = prioritize_foreground

    def score_candidate(
        self,
        det: Detection,
        target_class: str,
        track_age: int = 1,
        frame_width: float = 640.0,
        frame_height: float = 480.0,
        uncertainty: float = 0.0,
    ) -> ScoredCandidate:
        """Calculate multi-criteria score for a single candidate detection."""
        # 1. Objective match: 1.0 if matching primary mission objective, 0.0 otherwise
        target_norm = target_class.strip().lower()
        det_norm = det.class_name.strip().lower()
        obj_score = 1.0 if det_norm == target_norm else 0.0

        # 2. Confidence: penalized by evidential uncertainty (Dirichlet vacuity)
        calibrated_conf = float(det.confidence) * (1.0 - 0.5 * min(1.0, max(0.0, uncertainty)))
        conf_score = max(0.0, min(1.0, calibrated_conf))

        # 3. Track stability: asymptotic approach to 1.0 as track persists
        stab_score = min(1.0, float(track_age) / self.target_stability_age)

        # 4. Proximity / scale: bounding box area fraction of frame (capped at 40% frame area)
        frame_area = max(1.0, frame_width * frame_height)
        box_area = det.width * det.height
        area_ratio = box_area / frame_area
        prox_score = min(1.0, area_ratio / 0.40)

        # 5. Centering: normalized horizontal error e_x in [-1, 1], centering = 1 - |e_x|
        # center_x_norm is in [0, 1], normalized error e_x = 2 * (cx - 0.5)
        cx_norm = det.center_x_norm(frame_width)
        e_x = 2.0 * (cx_norm - 0.5)
        pos_score = max(0.0, 1.0 - abs(e_x))

        # Check if immediately present in front of camera (Foreground vs Distant)
        is_fg = bool((area_ratio >= self.close_area_ratio) or (det.y2 >= 0.65 * frame_height))

        total = (
            self.w_obj * obj_score
            + self.w_conf * conf_score
            + self.w_stab * stab_score
            + self.w_dist * prox_score
            + self.w_pos * pos_score
        )

        return ScoredCandidate(
            detection=det,
            total_score=round(total, 4),
            confidence_score=round(conf_score, 3),
            stability_score=round(stab_score, 3),
            proximity_score=round(prox_score, 3),
            centering_score=round(pos_score, 3),
            objective_score=round(obj_score, 3),
            track_age=track_age,
            uncertainty=round(uncertainty, 3),
            is_foreground=is_fg,
        )

    def select_best(
        self,
        candidates: list[tuple[Detection, int] | tuple[Detection, int, float]],
        target_class: str,
        frame_width: float = 640.0,
        frame_height: float = 480.0,
        require_objective_match: bool = True,
    ) -> ScoredCandidate | None:
        """Select the highest-scoring candidate among all valid detections."""
        if not candidates:
            return None

        scored: list[ScoredCandidate] = []
        for item in candidates:
            if len(item) == 3:
                det, age, unc = item  # type: ignore
            else:
                det, age = item  # type: ignore
                unc = 0.0
            if require_objective_match and det.class_name.strip().lower() != target_class.strip().lower():
                continue
            scored.append(
                self.score_candidate(
                    det,
                    target_class,
                    track_age=age,
                    frame_width=frame_width,
                    frame_height=frame_height,
                    uncertainty=unc,
                )
            )

        if not scored:
            return None

        # Depth-stratified Priority:
        # 1. First, prioritize what is present in front of the camera (Foreground)
        if self.prioritize_foreground:
            fg = [s for s in scored if s.is_foreground]
            if fg:
                fg.sort(key=lambda s: s.total_score, reverse=True)
                return fg[0]

            # 2. Later, what is far away from the camera with HIGH PRECISION
            distant = [
                s for s in scored
                if not s.is_foreground
                and s.confidence_score >= self.min_distant_confidence
                and s.track_age >= self.min_distant_track_age
                and s.uncertainty <= 0.65
            ]
            if distant:
                distant.sort(key=lambda s: s.total_score, reverse=True)
                return distant[0]
            return None

        # Fallback / standard
        scored.sort(key=lambda s: s.total_score, reverse=True)
        return scored[0]

