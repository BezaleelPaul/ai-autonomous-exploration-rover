"""Obstacle avoidance: safety always overrides AI."""

from __future__ import annotations

import math


class ObstacleAvoidance:
    def __init__(self, emergency_cm: float = 15.0, slow_cm: float = 30.0):
        self.emergency_cm = emergency_cm
        self.slow_cm = slow_cm

    def override(self, ai_cmd: str, distance_cm: float | None) -> str:
        ai_cmd = (ai_cmd or "S").upper()
        if (
            not isinstance(distance_cm, (int, float))
            or not math.isfinite(distance_cm)
            or distance_cm < 0
        ):
            return "S" if ai_cmd in ("F", "B") else ai_cmd
        if distance_cm < self.emergency_cm:
            # allow turning in place to escape, block forward/back
            return "S" if ai_cmd in ("F", "B") else ai_cmd
        return ai_cmd
