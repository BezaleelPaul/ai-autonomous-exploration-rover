"""Multi-object scene tracking and state estimation.

Maintains identity, trajectory history, velocity vectors, and deformation
recovery across multiple simultaneous objects in the camera view.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from software.ai.detection import Detection
from software.perception.point_tracker import PointTracker


@dataclass
class TrackedObject:
    track_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    center_x: float
    center_y: float
    width: float
    height: float
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    track_age: int = 1
    is_coasting: bool = False
    last_seen: float = field(default_factory=time.time)
    history: list[tuple[float, float]] = field(default_factory=list)

    @property
    def box(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    def center_x_norm(self, frame_width: float = 640.0) -> float:
        return self.center_x / max(1.0, frame_width)

    def to_detection(self) -> Detection:
        return Detection(
            class_name=self.class_name,
            confidence=self.confidence,
            x1=self.x1,
            y1=self.y1,
            x2=self.x2,
            y2=self.y2,
            timestamp=self.last_seen,
            track_id=self.track_id,
        )


class MultiObjectTracker:
    """Manages simultaneous multi-object tracks with trajectory and deformation recovery."""

    def __init__(
        self,
        max_history_len: int = 30,
        enable_point_tracking: bool = True,
        track_ttl_s: float = 1.5,
    ):
        self.max_history_len = max_history_len
        self.enable_point_tracking = enable_point_tracking
        self.track_ttl_s = track_ttl_s
        self.point_tracker = PointTracker() if enable_point_tracking else None
        self._tracks: dict[int, TrackedObject] = {}

    def reset(self) -> None:
        self._tracks.clear()
        if self.point_tracker is not None:
            self.point_tracker.reset()

    def update(
        self,
        detections: list[Detection],
        frame: np.ndarray | None = None,
        now: float | None = None,
    ) -> list[TrackedObject]:
        """Update active tracks with current detections and optional frame for optical flow."""
        now = now if now is not None else time.time()

        # Step 1: Run PointTracker if frame is available and point tracking enabled
        point_tracks: dict[int, tuple[tuple[float, float, float, float], float, str, bool]] = {}
        if self.enable_point_tracking and self.point_tracker is not None and frame is not None:
            pt_out = self.point_tracker.update(frame, detections)
            for tid, box, conf, cls_name, coasting in pt_out:
                point_tracks[tid] = (box, conf, cls_name, coasting)

        # Step 2: Combine neural detections and point-tracked objects
        active_ids = set()

        for d in detections:
            tid = d.track_id
            if tid is None:
                continue

            cx = (d.x1 + d.x2) / 2.0
            cy = (d.y1 + d.y2) / 2.0
            w = d.x2 - d.x1
            h = d.y2 - d.y1

            if tid in self._tracks:
                tr = self._tracks[tid]
                dt = max(1e-3, now - tr.last_seen)
                vx = (cx - tr.center_x) / dt
                vy = (cy - tr.center_y) / dt

                tr.confidence = d.confidence
                tr.x1, tr.y1, tr.x2, tr.y2 = d.x1, d.y1, d.x2, d.y2
                tr.center_x, tr.center_y = cx, cy
                tr.width, tr.height = w, h
                tr.velocity_x = 0.7 * tr.velocity_x + 0.3 * vx
                tr.velocity_y = 0.7 * tr.velocity_y + 0.3 * vy
                tr.track_age += 1
                tr.is_coasting = False
                tr.last_seen = now
                tr.history.append((cx, cy))
                if len(tr.history) > self.max_history_len:
                    tr.history.pop(0)
            else:
                self._tracks[tid] = TrackedObject(
                    track_id=tid,
                    class_name=d.class_name,
                    confidence=d.confidence,
                    x1=d.x1,
                    y1=d.y1,
                    x2=d.x2,
                    y2=d.y2,
                    center_x=cx,
                    center_y=cy,
                    width=w,
                    height=h,
                    track_age=1,
                    is_coasting=False,
                    last_seen=now,
                    history=[(cx, cy)],
                )
            active_ids.add(tid)

        # Step 3: Handle coasting objects from point tracker that detector missed
        for tid, (box, conf, cls_name, coasting) in point_tracks.items():
            if tid not in active_ids and coasting and tid in self._tracks:
                tr = self._tracks[tid]
                cx = (box[0] + box[2]) / 2.0
                cy = (box[1] + box[3]) / 2.0
                w = box[2] - box[0]
                h = box[3] - box[1]

                dt = max(1e-3, now - tr.last_seen)
                vx = (cx - tr.center_x) / dt
                vy = (cy - tr.center_y) / dt

                tr.x1, tr.y1, tr.x2, tr.y2 = box
                tr.center_x, tr.center_y = cx, cy
                tr.width, tr.height = w, h
                tr.velocity_x = 0.7 * tr.velocity_x + 0.3 * vx
                tr.velocity_y = 0.7 * tr.velocity_y + 0.3 * vy
                tr.track_age += 1
                tr.is_coasting = True
                tr.last_seen = now
                tr.history.append((cx, cy))
                if len(tr.history) > self.max_history_len:
                    tr.history.pop(0)
                active_ids.add(tid)

        # Step 4: Prune stale tracks that exceeded TTL
        dead = [
            tid
            for tid, tr in self._tracks.items()
            if (now - tr.last_seen) > self.track_ttl_s
        ]
        for tid in dead:
            self._tracks.pop(tid, None)

        return sorted(
            list(self._tracks.values()),
            key=lambda t: t.confidence,
            reverse=True,
        )

    def get_active_tracks(self) -> list[TrackedObject]:
        return list(self._tracks.values())

    def get_target_track(self, target_class: str) -> TrackedObject | None:
        """Find the most prominent active track for a given target class."""
        cands = [
            t
            for t in self._tracks.values()
            if t.class_name.lower() == target_class.lower()
        ]
        if not cands:
            return None
        return max(cands, key=lambda t: t.width * t.height)
