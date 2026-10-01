"""Gap assessment: approximate only. UNKNOWN never means SAFE."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GapVerdict:
    feasible: bool
    level: str  # SAFE | CAUTION | UNKNOWN
    required_cm: float
    estimated_cm: float | None
    reason: str


class GapAssessor:
    def __init__(
        self,
        rover_width_cm: float = 18.0,
        safety_margin_cm: float = 8.0,
        min_confidence: float = 0.65,
    ):
        self.rover_width = rover_width_cm
        self.margin = safety_margin_cm
        self.min_conf = min_confidence

    @property
    def required_width(self) -> float:
        return self.rover_width + 2 * self.margin

    def assess(
        self, estimated_clearance_cm: float | None, confidence: float = 1.0
    ) -> GapVerdict:
        req = self.required_width
        if estimated_clearance_cm is None:
            return GapVerdict(False, "UNKNOWN", req, None, "no clearance estimate")
        if confidence < self.min_conf:
            return GapVerdict(
                False, "UNKNOWN", req, estimated_clearance_cm, "low confidence"
            )
        if estimated_clearance_cm >= req:
            return GapVerdict(
                True, "SAFE", req, estimated_clearance_cm, "clearance sufficient"
            )
        if estimated_clearance_cm >= req * 0.8:
            return GapVerdict(
                False, "CAUTION", req, estimated_clearance_cm, "marginal clearance"
            )
        return GapVerdict(False, "UNKNOWN", req, estimated_clearance_cm, "too narrow")
