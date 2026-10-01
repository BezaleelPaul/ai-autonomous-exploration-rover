"""Central safety layer. Every autonomous movement must pass through here."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class SafetyVerdict:
    allowed: bool
    command: str  # final command (may be S)
    reason: str


class SafetyManager:
    """Priority: 1 emergency stop, 2 sensor safety, 3 comm health,
    4 sensor validity, 5 AI confidence, 6 navigation objective."""

    def __init__(
        self,
        emergency_cm: float = 15.0,
        slow_cm: float = 30.0,
        comm_timeout_s: float = 3.0,
        max_valid_cm: float = 400.0,
        min_valid_cm: float = 2.0,
        sensor_invalid_limit: int = 5,
    ):
        self.emergency_cm = emergency_cm
        self.slow_cm = slow_cm
        self.comm_timeout_s = comm_timeout_s
        self.max_valid = max_valid_cm
        self.min_valid = min_valid_cm
        self.sensor_invalid_limit = sensor_invalid_limit
        self.emergency_latch = False
        self._invalid_count = 0

    def reset_latch(self) -> None:
        self.emergency_latch = False
        self._invalid_count = 0

    def check(
        self,
        proposed: str,
        distance_cm,
        serial_healthy: bool,
        camera_healthy: bool,
        ai_confidence: float = 1.0,
        min_confidence: float = 0.0,
        allow_without_camera: bool = False,
    ) -> SafetyVerdict:
        # 0. command alphabet (M2): anything outside the protocol is STOP.
        proposed = str((proposed or "S")).upper()
        if proposed not in ("F", "B", "L", "R", "S"):
            return SafetyVerdict(False, "S", "INVALID_COMMAND")
        # 1. latched emergency — R4: recover only when obstacle clearly cleared
        #    (hysteresis: latch at <0.7*emergency, release at >=slow_cm) or via
        #    explicit reset_latch(). Without this the rover locks out forever.
        if (
            self.emergency_latch
            and isinstance(distance_cm, (int, float))
            and math.isfinite(distance_cm)
            and distance_cm >= self.slow_cm
        ):
            self.emergency_latch = False
        if self.emergency_latch and proposed != "S":
            return SafetyVerdict(False, "S", "EMERGENCY_LATCH")
        # 2/3. comm health
        if not serial_healthy:
            return SafetyVerdict(False, "S", "COMM_LOST")
        # 4. camera required for autonomous forward motion
        if (
            not camera_healthy
            and not allow_without_camera
            and proposed in ("F", "B", "L", "R")
        ):
            return SafetyVerdict(False, "S", "CAMERA_UNHEALTHY")
        # 5. sensor validity (reject None/str/NaN/inf/negative: never crash, never GO blind)
        if (
            not isinstance(distance_cm, (int, float))
            or not math.isfinite(distance_cm)
            or distance_cm < 0
        ):
            self._invalid_count += 1
            if self._invalid_count >= self.sensor_invalid_limit and proposed in (
                "F",
                "B",
            ):
                return SafetyVerdict(False, "S", "SENSOR_INVALID")
            # unknown distance: allow turns in place, block translation
            if proposed in ("F", "B"):
                return SafetyVerdict(False, "S", "SENSOR_UNKNOWN")
            return SafetyVerdict(True, proposed, "CAUTION_UNKNOWN_DISTANCE")
        if not (self.min_valid <= distance_cm <= self.max_valid):
            return SafetyVerdict(False, "S", "SENSOR_OUT_OF_RANGE")
        self._invalid_count = 0
        # 6. emergency obstacle
        if distance_cm < self.emergency_cm:
            if proposed in ("F", "B"):
                self.emergency_latch = distance_cm < self.emergency_cm * 0.7
                return SafetyVerdict(False, "S", "EMERGENCY_OBSTACLE")
            return SafetyVerdict(True, proposed, "CAUTION_CLOSE_OBSTACLE")
        # AI confidence gate (5 before 6 per docs/06): forward motion only, so
        # escape turns stay possible when the detector is unsure (H1/M5).
        if ai_confidence < min_confidence and proposed in ("F", "B"):
            return SafetyVerdict(False, "S", "LOW_CONFIDENCE")
        # slow zone: still allow but flagged
        if distance_cm < self.slow_cm and proposed == "F":
            return SafetyVerdict(True, "F", "CAUTION_SLOW_ZONE")
        return SafetyVerdict(True, proposed, "SAFE")

    # helper used by tests/scenarios
    def classify_distance(self, d: float) -> str:
        if d < self.emergency_cm:
            return "EMERGENCY"
        if d < self.slow_cm:
            return "CAUTION"
        return "SAFE"
