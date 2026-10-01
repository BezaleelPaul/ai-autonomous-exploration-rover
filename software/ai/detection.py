"""Structured detection type."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class Detection:
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    timestamp: float = 0.0
    track_id: int | None = None  # persistent ID when tracker backend is on

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    def center_x_norm(self, frame_width: float) -> float:
        return self.center_x / frame_width if frame_width else 0.5

    def width_ratio(self, frame_width: float) -> float:
        return self.width / frame_width if frame_width else 0.0

    def to_dict(self) -> dict:
        return {
            "class_name": self.class_name,
            "confidence": self.confidence,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "width": self.width,
            "height": self.height,
            "timestamp": self.timestamp,
            "track_id": self.track_id,
        }
