"""Point and feature motion tracking inspired by DeepMind TAPNet / CoTracker.

Tracks keypoints inside object bounding boxes across consecutive frames using
Pyramidal Lucas-Kanade Sparse Optical Flow (calcOpticalFlowPyrLK). Provides:
- Keypoint motion consensus (median dx, dy) to compensate for camera motion and turns
- Scale change tracking (expansion / contraction from distance changes)
- Track coasting / recovery across brief occlusions and low-confidence detector misses
- Deformation measurement (relative feature strain)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from software.ai.detection import Detection


@dataclass
class PointTrackState:
    track_id: int
    class_name: str
    box: tuple[float, float, float, float]  # (x1, y1, x2, y2)
    confidence: float
    points: np.ndarray  # shape (N, 1, 2), float32
    initial_distances: float = 1.0
    age: int = 1
    coasted_frames: int = 0
    last_update: float = field(default_factory=time.time)
    deformation_score: float = 0.0


class PointTracker:
    """CPU-friendly feature-point tracker for bounding-box deformation & recovery."""

    def __init__(
        self,
        max_points_per_box: int = 30,
        quality_level: float = 0.03,
        min_distance: float = 7.0,
        max_coast_frames: int = 5,
        min_tracked_points: int = 4,
    ):
        self.max_points_per_box = max_points_per_box
        self.quality_level = quality_level
        self.min_distance = min_distance
        self.max_coast_frames = max_coast_frames
        self.min_tracked_points = min_tracked_points
        self._prev_gray: np.ndarray | None = None
        self._tracks: dict[int, PointTrackState] = {}
        self._next_internal_id: int = 1000

    def reset(self) -> None:
        self._prev_gray = None
        self._tracks.clear()

    def _to_gray(self, frame: np.ndarray) -> np.ndarray | None:
        try:
            import cv2

            if frame.ndim == 2:
                return frame
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        except Exception:
            return None

    def _extract_points_in_box(
        self, gray: np.ndarray, box: tuple[float, float, float, float]
    ) -> np.ndarray:
        try:
            import cv2

            x1, y1, x2, y2 = [int(v) for v in box]
            h, w = gray.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if (x2 - x1) < 10 or (y2 - y1) < 10:
                return np.empty((0, 1, 2), dtype=np.float32)

            mask = np.zeros(gray.shape, dtype=np.uint8)
            mask[y1:y2, x1:x2] = 255
            pts = cv2.goodFeaturesToTrack(
                gray,
                maxCorners=self.max_points_per_box,
                qualityLevel=self.quality_level,
                minDistance=self.min_distance,
                mask=mask,
            )
            return pts if pts is not None else np.empty((0, 1, 2), dtype=np.float32)
        except Exception:
            return np.empty((0, 1, 2), dtype=np.float32)

    def _mean_pairwise_distance(self, pts: np.ndarray) -> float:
        if len(pts) < 2:
            return 1.0
        coords = pts.reshape(-1, 2)
        # Sample subset to keep CPU cost minimal
        n = min(len(coords), 10)
        sub = coords[:n]
        diffs = sub[:, np.newaxis, :] - sub[np.newaxis, :, :]
        dists = np.sqrt(np.sum(diffs**2, axis=-1))
        non_zero = dists[dists > 0]
        return float(np.mean(non_zero)) if len(non_zero) > 0 else 1.0

    def update(
        self,
        frame: np.ndarray | None,
        detections: list[Detection],
    ) -> list[tuple[int, tuple[float, float, float, float], float, str, bool]]:
        """Update point tracks given current frame and detector detections.

        Returns list of (track_id, box, confidence, class_name, is_coasting).
        """
        if frame is None:
            return []

        gray = self._to_gray(frame)
        if gray is None:
            return []

        import cv2

        updated_results: list[tuple[int, tuple[float, float, float, float], float, str, bool]] = []
        now = time.time()

        # Step 1: Propagate existing point tracks with Optical Flow if previous frame exists
        active_track_ids = set()
        if self._prev_gray is not None and self._tracks:
            lk_params = dict(
                winSize=(15, 15),
                maxLevel=2,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
            )

            dead_tracks = []
            for tid, state in self._tracks.items():
                if len(state.points) < self.min_tracked_points:
                    dead_tracks.append(tid)
                    continue

                try:
                    p1, st, err = cv2.calcOpticalFlowPyrLK(
                        self._prev_gray, gray, state.points, None, **lk_params
                    )
                    good_new = p1[st == 1]
                    good_old = state.points[st == 1]

                    if len(good_new) < self.min_tracked_points:
                        state.coasted_frames += 1
                        if state.coasted_frames > self.max_coast_frames:
                            dead_tracks.append(tid)
                        continue

                    # Calculate consensus translation vector (dx, dy)
                    displacements = good_new - good_old
                    dx = float(np.median(displacements[:, 0]))
                    dy = float(np.median(displacements[:, 1]))

                    # Calculate scale change
                    current_dist = self._mean_pairwise_distance(good_new.reshape(-1, 1, 2))
                    scale = current_dist / max(1e-3, state.initial_distances)
                    scale_clamped = max(0.8, min(1.2, scale))

                    # Update bounding box with translation and scale
                    x1, y1, x2, y2 = state.box
                    cx, cy = (x1 + x2) / 2.0 + dx, (y1 + y2) / 2.0 + dy
                    bw = (x2 - x1) * scale_clamped
                    bh = (y2 - y1) * scale_clamped

                    new_box = (
                        max(0.0, cx - bw / 2.0),
                        max(0.0, cy - bh / 2.0),
                        min(float(frame.shape[1]), cx + bw / 2.0),
                        min(float(frame.shape[0]), cy + bh / 2.0),
                    )

                    # Compute deformation metric (dispersion of point motions relative to median)
                    residuals = np.linalg.norm(displacements - [dx, dy], axis=-1)
                    deformation = float(np.mean(residuals))

                    state.box = new_box
                    state.points = good_new.reshape(-1, 1, 2).astype(np.float32)
                    state.age += 1
                    state.coasted_frames += 1  # Will be reset to 0 if matched with a detection
                    state.last_update = now
                    state.deformation_score = deformation
                except Exception:
                    dead_tracks.append(tid)

            for tid in dead_tracks:
                self._tracks.pop(tid, None)

        # Step 2: Match incoming detections to existing tracks
        matched_tracks = set()
        for d in detections:
            matched_id: int | None = None
            d_box = (d.x1, d.y1, d.x2, d.y2)

            # Check track_id match first
            if d.track_id is not None and d.track_id in self._tracks:
                matched_id = d.track_id
            else:
                # Spatial IoU matching
                best_iou = 0.3
                for tid, state in self._tracks.items():
                    if tid in matched_tracks:
                        continue
                    if state.class_name == d.class_name:
                        iou = self._box_iou(d_box, state.box)
                        if iou > best_iou:
                            best_iou = iou
                            matched_id = tid

            if matched_id is not None:
                # Refresh matched track with new ground-truth detector box
                state = self._tracks[matched_id]
                state.box = d_box
                state.confidence = d.confidence
                state.class_name = d.class_name
                state.coasted_frames = 0
                state.last_update = now
                matched_tracks.add(matched_id)
                # Re-seed feature points if count dropped
                if len(state.points) < (self.max_points_per_box // 2):
                    pts = self._extract_points_in_box(gray, d_box)
                    if len(pts) >= self.min_tracked_points:
                        state.points = pts
                        state.initial_distances = self._mean_pairwise_distance(pts)
            else:
                # Create brand new track
                tid = d.track_id if d.track_id is not None else self._next_internal_id
                if d.track_id is None:
                    self._next_internal_id += 1
                pts = self._extract_points_in_box(gray, d_box)
                self._tracks[tid] = PointTrackState(
                    track_id=tid,
                    class_name=d.class_name,
                    box=d_box,
                    confidence=d.confidence,
                    points=pts,
                    initial_distances=self._mean_pairwise_distance(pts),
                    age=1,
                    coasted_frames=0,
                    last_update=now,
                )
                matched_tracks.add(tid)

        # Step 3: Emit all valid tracks (both detected and coasting through occlusion)
        for tid, state in list(self._tracks.items()):
            is_coasting = state.coasted_frames > 0
            if is_coasting and state.coasted_frames > self.max_coast_frames:
                self._tracks.pop(tid, None)
                continue
            updated_results.append(
                (tid, state.box, state.confidence, state.class_name, is_coasting)
            )

        self._prev_gray = gray.copy()
        return updated_results

    @staticmethod
    def _box_iou(
        b1: tuple[float, float, float, float], b2: tuple[float, float, float, float]
    ) -> float:
        xx1 = max(b1[0], b2[0])
        yy1 = max(b1[1], b2[1])
        xx2 = min(b1[2], b2[2])
        yy2 = min(b1[3], b2[3])
        w = max(0.0, xx2 - xx1)
        h = max(0.0, yy2 - yy1)
        inter = w * h
        area1 = max(0.0, b1[2] - b1[0]) * max(0.0, b1[3] - b1[1])
        area2 = max(0.0, b2[2] - b2[0]) * max(0.0, b2[3] - b2[1])
        union = area1 + area2 - inter
        return inter / union if union > 0 else 0.0
