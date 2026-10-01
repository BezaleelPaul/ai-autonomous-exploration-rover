"""Target search with timeout + max rotations. Never infinite."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class SearchState:
    active: bool = False
    start_time: float = 0.0
    rotations: int = 0
    found: bool = False


class TargetSearch:
    def __init__(
        self,
        timeout_s: float = 30.0,
        max_rotations: int = 2,
        rotation_duration_s: float = 20.0,
    ):
        self.timeout_s = timeout_s
        self.max_rotations = max_rotations
        self.rotation_duration_s = rotation_duration_s
        self.s = SearchState()

    def start(self, now: float | None = None) -> None:
        self.s = SearchState(
            active=True, start_time=now if now is not None else time.time()
        )

    def stop(self) -> None:
        self.s.active = False

    def update(self, target_present: bool, now: float | None = None):
        """Returns (command, done, message)."""
        now = now if now is not None else time.time()
        if not self.s.active:
            return "S", True, "not active"
        if target_present:
            self.s.found = True
            self.s.active = False
            return "S", True, "target found"
        elapsed = now - self.s.start_time
        if elapsed > self.timeout_s:
            self.s.active = False
            return "S", True, "search timeout"
        # count full rotations
        self.s.rotations = int(elapsed / self.rotation_duration_s)
        if self.s.rotations >= self.max_rotations:
            self.s.active = False
            return "S", True, "max rotations reached"
        return "R", False, f"scanning {elapsed:.1f}s"
