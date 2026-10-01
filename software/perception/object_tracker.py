"""Nearest-target tracker with confidence filter, temporal validation, and lock hysteresis."""

from __future__ import annotations

import time

from software.ai.detection import Detection
from software.perception.target_scorer import TargetScorer
from software.perception.temporal_validator import TemporalValidator


class ObjectTracker:
    def __init__(
        self,
        target_class: str = "bottle",
        confidence_threshold: float = 0.5,
        lock_duration_s: float = 1.0,
        min_persistence_frames: int = 1,
        enable_temporal_validation: bool = False,
    ):
        self.target_class = target_class.lower()
        self.confidence_threshold = confidence_threshold
        self.lock_duration_s = lock_duration_s
        self.min_persistence_frames = min_persistence_frames
        self.enable_temporal_validation = enable_temporal_validation
        self.validator = TemporalValidator(
            min_confidence=confidence_threshold,
            min_persistence_frames=min_persistence_frames,
        )
        self.scorer = TargetScorer()
        self._locked_since: float | None = None
        self._last_seen: float | None = None
        self._last_detection: Detection | None = None
        self._last_track_age: int = 1

    @property
    def track_age(self) -> int:
        return self._last_track_age

    def select(
        self,
        detections: list[Detection],
        frame_width: float = 640.0,
        frame_height: float = 480.0,
        frame: np.ndarray | None = None,
    ) -> Detection | None:
        cands = [
            d
            for d in detections
            if d.class_name.lower() == self.target_class
            and d.confidence >= self.confidence_threshold
        ]
        if not cands:
            return None

        if self.enable_temporal_validation and self.min_persistence_frames > 1:
            validated_cands: list[tuple[Detection, int, float]] = []
            for d in cands:
                res = self.validator.update_and_validate(
                    d,
                    frame_width=frame_width,
                    frame_height=frame_height,
                    frame=frame,
                )
                if res.is_valid:
                    validated_cands.append((d, res.track_age, res.uncertainty))
            if not validated_cands:
                return None
            best_scored = self.scorer.select_best(
                validated_cands,
                self.target_class,
                frame_width=frame_width,
                frame_height=frame_height,
            )
            if best_scored is not None:
                self._last_track_age = best_scored.track_age
                return best_scored.detection

        # Default / fallback: largest = closest approximation
        return max(cands, key=lambda d: d.width * d.height)

    def update(
        self,
        detections: list[Detection],
        now: float | None = None,
        frame_width: float = 640.0,
        frame_height: float = 480.0,
        frame: np.ndarray | None = None,
    ) -> Detection | None:
        now = now if now is not None else time.time()
        best = self.select(
            detections,
            frame_width=frame_width,
            frame_height=frame_height,
            frame=frame,
        )
        if best is None:
            if (
                self._last_seen is not None
                and (now - self._last_seen) > self.lock_duration_s
            ):
                self._locked_since = None
                self._last_detection = None
                self._last_track_age = 1
            # lock hysteresis: hold the last detection briefly so a throttled
            # inference loop (inference_interval > 1) does not flicker the
            # target in and out between detections
            return self._last_detection
        self._last_seen = now
        self._last_detection = best
        if self._locked_since is None:
            self._locked_since = now
        return best

    def is_locked(self, now: float | None = None) -> bool:
        if self._locked_since is None:
            return False
        now = now if now is not None else time.time()
        return (now - self._locked_since) >= self.lock_duration_s
