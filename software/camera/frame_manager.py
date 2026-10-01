"""Frame manager: throttles inference and holds the latest frame with age stats."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class FrameInfo:
    frame_id: int = 0
    capture_time: float = 0.0
    inference_ms: float = 0.0
    frame: Any = None


class FrameManager:
    """Single-slot latest-wins frame buffer plus inference throttling.

    ``observe``/``consume`` are the write/read halves of the buffer. A stored
    frame that is replaced before it is consumed counts as **dropped**, which
    is how a producer outrunning the consumer is detected. **Frame age** is
    ``now - capture_time`` of the newest frame, i.e. how stale the picture the
    rover is acting on is; ``max_frame_age_s`` is the freeze threshold from
    FM-03 (camera frame freeze > 3.0 s).
    """

    def __init__(self, inference_interval: int = 2, max_frame_age_s: float = 3.0):
        self.inference_interval = max(1, inference_interval)
        self.max_frame_age_s = float(max_frame_age_s)
        self._count = 0
        self._received = 0
        self._consumed = 0
        self._dropped = 0
        self._latest: FrameInfo | None = None
        self._pending = False

    def should_infer(self) -> bool:
        self._count += 1
        return (self._count % self.inference_interval) == 0

    def observe(self, frame: Any, capture_time: float = 0.0) -> FrameInfo:
        """Store the newest frame; count any still-unconsumed one as dropped."""
        if frame is None:
            raise ValueError("frame must not be None")
        if self._pending:
            self._dropped += 1
        self._received += 1
        self._latest = FrameInfo(
            frame_id=self._received,
            capture_time=float(capture_time),
            frame=frame,
        )
        self._pending = True
        return self._latest

    def consume(self) -> Any | None:
        """Take the stored frame and mark the slot empty; None if already taken."""
        if self._latest is None or not self._pending:
            return None
        self._pending = False
        self._consumed += 1
        return self._latest.frame

    def frame_age(self, now: float | None = None) -> float | None:
        """Seconds between ``now`` and the stored frame's capture time.

        Returns None when there is no frame, or when capture_time was never
        supplied (0.0) — an unknown age must not be reported as 0.
        """
        if self._latest is None or self._latest.capture_time <= 0.0:
            return None
        return (time.time() if now is None else now) - self._latest.capture_time

    def is_stale(self, now: float | None = None) -> bool:
        age = self.frame_age(now)
        return age is not None and age > self.max_frame_age_s

    def stats(self) -> dict:
        age = self.frame_age()
        return {
            "received": self._received,
            "consumed": self._consumed,
            "dropped": self._dropped,
            "age_s": None if age is None else round(age, 3),
            "stale": self.is_stale(),
            "inference_interval": self.inference_interval,
            "max_frame_age_s": self.max_frame_age_s,
        }

    def reset(self) -> None:
        self._count = 0
        self._received = 0
        self._consumed = 0
        self._dropped = 0
        self._latest = None
        self._pending = False
