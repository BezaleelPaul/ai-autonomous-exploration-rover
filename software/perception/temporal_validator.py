"""Temporal perception validation: confidence checks, track persistence, and bounding-box sanity.

Prevents single-frame detection flickers (e.g. pillow momentarily misidentified as person)
from triggering rover actions. Enforces multi-frame track persistence and geometric sanity.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from software.ai.detection import Detection


@dataclass
class TrackHistory:
    """Historical tracking information for a single object track ID."""

    track_id: int
    class_name: str
    hits: int = 1
    misses: int = 0
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    confidence_sum: float = 0.0
    last_bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    appearance_signature: np.ndarray | None = None

    @property
    def average_confidence(self) -> float:
        return self.confidence_sum / max(1, self.hits)

    @property
    def age(self) -> int:
        return self.hits


@dataclass
class ValidationResult:
    """Result of temporal and geometric validation of a detection."""

    is_valid: bool
    reason: str
    track_age: int = 1
    smoothed_confidence: float = 0.0
    uncertainty: float = 0.0
    appearance_distance: float = 0.0


def extract_appearance_signature(
    frame: np.ndarray | None,
    bbox: tuple[float, float, float, float],
) -> np.ndarray | None:
    """Extract normalized visual appearance signature (color + gradient descriptor).

    Used for metric verification (ReID): distinguishes real target from defective lookalike
    appearing at the same spatial coordinates.
    """
    if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
        return None
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = [int(round(v)) for v in bbox]
    x1 = max(0, min(w - 1, x1))
    x2 = max(0, min(w, x2))
    y1 = max(0, min(h - 1, y1))
    y2 = max(0, min(h, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    try:
        import cv2
        if len(crop.shape) == 3 and crop.shape[2] == 3:
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            hist_h = cv2.calcHist([hsv], [0], None, [8], [0, 180]).flatten()
            hist_s = cv2.calcHist([hsv], [1], None, [8], [0, 256]).flatten()
            hist_v = cv2.calcHist([hsv], [2], None, [8], [0, 256]).flatten()
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            hist_h = np.zeros(8, dtype=np.float32)
            hist_s = np.zeros(8, dtype=np.float32)
            hist_v = np.histogram(crop, bins=8, range=(0, 256))[0].astype(np.float32)
            gray = crop if len(crop.shape) == 2 else crop[:, :, 0]

        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(gx, gy)
        hist_mag = cv2.calcHist([mag], [0], None, [8], [0, 256]).flatten()
        vec = np.concatenate([hist_h, hist_s, hist_v, hist_mag]).astype(np.float32)
        norm = float(np.linalg.norm(vec))
        if norm > 1e-6:
            vec /= norm
        return vec
    except Exception:
        channels = [crop[:, :, c] for c in range(crop.shape[2])] if len(crop.shape) == 3 else [crop]
        hists = [np.histogram(c, bins=8, range=(0, 256))[0].astype(np.float32) for c in channels]
        vec = np.concatenate(hists).astype(np.float32)
        norm = float(np.linalg.norm(vec))
        if norm > 1e-6:
            vec /= norm
        return vec


def compute_appearance_distance(
    sig1: np.ndarray | None,
    sig2: np.ndarray | None,
) -> float:
    """Cosine distance in metric appearance space d = 1 - (u . v) in [0, 2]."""
    if sig1 is None or sig2 is None:
        return 0.0
    dot = float(np.dot(sig1, sig2))
    return max(0.0, 1.0 - min(1.0, dot))


def estimate_evidential_uncertainty(
    frame: np.ndarray | None,
    bbox: tuple[float, float, float, float],
    raw_confidence: float,
) -> tuple[float, float]:
    """Estimate epistemic uncertainty u in [0, 1] and calibrated confidence.

    Theoretical basis: Evidential Deep Learning (Dirichlet prior strength) and spatial entropy.
    Degraded, saturated, or low-contrast regions carry low Dirichlet evidence -> high vacuity.
    """
    if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
        return 0.0, raw_confidence

    h, w = frame.shape[:2]
    x1, y1, x2, y2 = [int(round(v)) for v in bbox]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return 0.0, raw_confidence

    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return 0.0, raw_confidence

    std_val = float(np.std(crop))
    mean_val = float(np.mean(crop))

    sat_penalty = max(0.0, (mean_val - 235.0) / 20.0) if mean_val > 235.0 else (
        max(0.0, (20.0 - mean_val) / 20.0) if mean_val < 20.0 else 0.0
    )
    var_factor = min(1.0, std_val / 30.0)

    evidence = max(0.01, var_factor * (1.0 - sat_penalty))
    K = 2.0
    u = float(np.clip(K / (K + evidence * 10.0), 0.0, 1.0))
    calibrated = float(np.clip(raw_confidence * (1.0 - 0.5 * u), 0.0, 1.0))
    return u, calibrated


class TemporalValidator:
    """Validates detections across time and geometric constraints.

    Workflow:
      YOLO detection -> BoT-SORT track -> Confidence check -> Track persistence
      -> Bounding-box sanity -> Frame quality -> Target accepted?
    """

    def __init__(
        self,
        min_confidence: float = 0.5,
        min_persistence_frames: int = 3,
        max_miss_frames: int = 5,
        min_box_ratio: float = 0.01,
        max_box_ratio: float = 0.95,
        min_aspect_ratio: float = 0.1,
        max_aspect_ratio: float = 10.0,
        min_frame_brightness: float = 5.0,
        max_frame_brightness: float = 250.0,
        min_blur_score: float = 0.0,
        max_appearance_distance: float = 0.70,
        max_uncertainty: float = 0.85,
    ):
        self.min_confidence = min_confidence
        self.min_persistence_frames = min_persistence_frames
        self.max_miss_frames = max_miss_frames
        self.min_box_ratio = min_box_ratio
        self.max_box_ratio = max_box_ratio
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio
        self.min_frame_brightness = min_frame_brightness
        self.max_frame_brightness = max_frame_brightness
        self.min_blur_score = min_blur_score
        self.max_appearance_distance = max_appearance_distance
        self.max_uncertainty = max_uncertainty

        # track_id -> TrackHistory
        self.tracks: dict[int, TrackHistory] = {}
        # spatial fallback for detections lacking track_id
        self._untracked_count = 0

    def check_frame_quality(self, frame: np.ndarray | None) -> tuple[bool, str]:
        """Validate input frame quality (not blank, uniform, or corrupted)."""
        if frame is None:
            return False, "FRAME_NONE"
        if not isinstance(frame, np.ndarray) or frame.size == 0:
            return False, "FRAME_EMPTY"
        if len(frame.shape) < 2:
            return False, "FRAME_INVALID_SHAPE"

        mean_val = float(np.mean(frame))
        if mean_val < self.min_frame_brightness:
            return False, f"FRAME_TOO_DARK ({mean_val:.1f} < {self.min_frame_brightness})"
        if mean_val > self.max_frame_brightness:
            return False, f"FRAME_OVEREXPOSED ({mean_val:.1f} > {self.max_frame_brightness})"

        # Check for zero-variance / corrupted uniform image
        std_val = float(np.std(frame))
        if std_val < 0.5:
            return False, "FRAME_ZERO_VARIANCE"

        # Check motion blur if threshold enabled
        if self.min_blur_score > 0.0:
            try:
                import cv2
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
                blur_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                if blur_var < self.min_blur_score:
                    return False, f"FRAME_MOTION_BLUR ({blur_var:.1f} < {self.min_blur_score:.1f})"
            except Exception:
                pass

        return True, "FRAME_OK"

    def check_bbox_sanity(
        self,
        det: Detection,
        frame_width: float = 640.0,
        frame_height: float = 480.0,
    ) -> tuple[bool, str]:
        """Check bounding box geometry: bounds, aspect ratio, and relative size."""
        x1, y1, x2, y2 = det.x1, det.y1, det.x2, det.y2
        w = x2 - x1
        h = y2 - y1

        if w <= 0 or h <= 0:
            return False, "BBOX_NON_POSITIVE_DIMENSIONS"

        # Coordinates sanity
        if x2 < 0 or y2 < 0 or x1 > frame_width or y1 > frame_height:
            return False, "BBOX_OUT_OF_BOUNDS"

        # Size ratio
        w_ratio = w / max(1.0, frame_width)
        h_ratio = h / max(1.0, frame_height)
        if w_ratio < self.min_box_ratio or h_ratio < self.min_box_ratio:
            return False, f"BBOX_TOO_SMALL (w={w_ratio:.3f}, h={h_ratio:.3f})"
        if w_ratio > self.max_box_ratio and h_ratio > self.max_box_ratio:
            return False, f"BBOX_TOO_LARGE (w={w_ratio:.3f}, h={h_ratio:.3f})"

        # Aspect ratio (width / height)
        aspect = w / h
        if aspect < self.min_aspect_ratio or aspect > self.max_aspect_ratio:
            return False, f"BBOX_UNREALISTIC_ASPECT ({aspect:.2f})"

        return True, "BBOX_OK"

    def update_and_validate(
        self,
        det: Detection,
        frame_width: float = 640.0,
        frame_height: float = 480.0,
        now: float | None = None,
        frame: np.ndarray | None = None,
    ) -> ValidationResult:
        """Update track history and validate confidence, persistence, geometry, and appearance."""
        now = now if now is not None else time.time()

        # 1. Raw Confidence Check
        if det.confidence < self.min_confidence:
            return ValidationResult(
                is_valid=False,
                reason=f"LOW_CONFIDENCE ({det.confidence:.2f} < {self.min_confidence:.2f})",
                track_age=1,
                smoothed_confidence=det.confidence,
            )

        # 2. Geometric BBox Sanity
        bbox_ok, bbox_reason = self.check_bbox_sanity(det, frame_width, frame_height)
        if not bbox_ok:
            return ValidationResult(
                is_valid=False,
                reason=bbox_reason,
                track_age=1,
                smoothed_confidence=det.confidence,
            )

        # 3. Evidential Uncertainty Estimation (Epistemic / Defect filter)
        unc, calib_conf = estimate_evidential_uncertainty(
            frame, (det.x1, det.y1, det.x2, det.y2), det.confidence
        )
        if unc > self.max_uncertainty:
            return ValidationResult(
                is_valid=False,
                reason=f"HIGH_UNCERTAINTY_DEFECTIVE ({unc:.2f} > {self.max_uncertainty:.2f})",
                track_age=1,
                smoothed_confidence=calib_conf,
                uncertainty=unc,
            )

        # 4. Track Persistence & Appearance Metric Association
        track_id = det.track_id
        if track_id is None:
            # For backends without track IDs (or mock), use a synthetic ID
            track_id = hash((det.class_name, round(det.x1 / 40), round(det.y1 / 40)))

        history = self.tracks.get(track_id)
        new_sig = extract_appearance_signature(frame, (det.x1, det.y1, det.x2, det.y2))
        app_dist = 0.0

        if history is not None and history.appearance_signature is not None and new_sig is not None:
            app_dist = compute_appearance_distance(history.appearance_signature, new_sig)
            if app_dist >= self.max_appearance_distance:
                return ValidationResult(
                    is_valid=False,
                    reason=f"APPEARANCE_MISMATCH_DEFECTIVE ({app_dist:.2f} >= {self.max_appearance_distance:.2f})",
                    track_age=history.age,
                    smoothed_confidence=history.average_confidence,
                    uncertainty=unc,
                    appearance_distance=app_dist,
                )

        if history is None:
            history = TrackHistory(
                track_id=track_id,
                class_name=det.class_name,
                hits=1,
                misses=0,
                first_seen=now,
                last_seen=now,
                confidence_sum=calib_conf,
                last_bbox=(det.x1, det.y1, det.x2, det.y2),
                appearance_signature=new_sig,
            )
            self.tracks[track_id] = history
        else:
            history.hits += 1
            history.misses = 0
            history.last_seen = now
            history.confidence_sum += calib_conf
            history.last_bbox = (det.x1, det.y1, det.x2, det.y2)
            if new_sig is not None:
                if history.appearance_signature is None:
                    history.appearance_signature = new_sig
                else:
                    # Momentum update of visual embedding
                    history.appearance_signature = 0.8 * history.appearance_signature + 0.2 * new_sig
                    norm = float(np.linalg.norm(history.appearance_signature))
                    if norm > 1e-6:
                        history.appearance_signature /= norm

        avg_conf = history.average_confidence
        age = history.age

        if age < self.min_persistence_frames:
            return ValidationResult(
                is_valid=False,
                reason=f"TRACK_UNSTABLE (age={age} < {self.min_persistence_frames})",
                track_age=age,
                smoothed_confidence=avg_conf,
                uncertainty=unc,
                appearance_distance=app_dist,
            )

        return ValidationResult(
            is_valid=True,
            reason="ACCEPTED",
            track_age=age,
            smoothed_confidence=avg_conf,
            uncertainty=unc,
            appearance_distance=app_dist,
        )

    def prune_stale_tracks(self, active_track_ids: set[int] | None = None) -> None:
        """Age out tracks that have not been observed in consecutive frames."""
        active = active_track_ids or set()
        stale_ids = []
        for tid, history in self.tracks.items():
            if tid not in active:
                history.misses += 1
                if history.misses > self.max_miss_frames:
                    stale_ids.append(tid)

        for tid in stale_ids:
            del self.tracks[tid]

    def validate_detections(
        self,
        detections: list[Detection],
        frame: np.ndarray | None = None,
        frame_width: float = 640.0,
        frame_height: float = 480.0,
        now: float | None = None,
    ) -> list[tuple[Detection, ValidationResult]]:
        """Run temporal validation across all detections in the current frame."""
        now = now if now is not None else time.time()

        # Frame level quality check
        if frame is not None:
            frame_ok, frame_reason = self.check_frame_quality(frame)
            if not frame_ok:
                return [
                    (
                        d,
                        ValidationResult(
                            is_valid=False,
                            reason=frame_reason,
                            track_age=1,
                            smoothed_confidence=d.confidence,
                        ),
                    )
                    for d in detections
                ]

        active_tids = {d.track_id for d in detections if d.track_id is not None}
        self.prune_stale_tracks(active_tids)

        results = []
        for det in detections:
            v_res = self.update_and_validate(
                det,
                frame_width=frame_width,
                frame_height=frame_height,
                now=now,
                frame=frame,
            )
            results.append((det, v_res))
        return results

