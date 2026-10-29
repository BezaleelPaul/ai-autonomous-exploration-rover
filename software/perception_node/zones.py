"""Three-zone steering geometry and the bounding-box-area proximity policy.

The frame is split into vertical columns (the *left* / *center* / *right*
steering zones). The target's normalised centre-x selects the zone; the target
bounding-box area relative to the whole frame estimates proximity, because a
single camera has no depth.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from software.ai.detection import Detection

FORWARD = "F"
TURN_LEFT = "L"
TURN_RIGHT = "R"
STOP = "S"

PERCEPTION_COMMANDS: tuple[str, ...] = (FORWARD, TURN_LEFT, TURN_RIGHT, STOP)


class Zone(str, Enum):
    """Which third of the frame the target's centre falls into."""

    LEFT = "LEFT"
    CENTER = "CENTER"
    RIGHT = "RIGHT"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class SteeringDecision:
    """Immutable outcome of one perception cycle."""

    command: str
    zone: Zone | None
    area_ratio: float
    target_present: bool
    reason: str


def classify_zone(
    center_x_norm: float, left_boundary: float = 0.33, center_boundary: float = 0.66
) -> Zone:
    """Map a normalised horizontal centre (0..1) onto LEFT / CENTER / RIGHT."""
    if not 0.0 <= center_x_norm <= 1.0:
        raise ValueError(f"center_x_norm must be in [0,1], got {center_x_norm}")
    if not 0.0 < left_boundary < center_boundary < 1.0:
        raise ValueError(
            "boundaries must satisfy 0 < left_boundary < center_boundary < 1"
        )
    if center_x_norm < left_boundary:
        return Zone.LEFT
    if center_x_norm < center_boundary:
        return Zone.CENTER
    return Zone.RIGHT


def command_for_zone(zone: Zone) -> str:
    """Single source of truth for the zone -> steering command mapping."""
    if zone is Zone.LEFT:
        return TURN_LEFT
    if zone is Zone.RIGHT:
        return TURN_RIGHT
    return FORWARD


class SteeringPolicy:
    """Pure decision function: target -> single-character command.

    Rules (spec):
      * no target detected            -> 'S'
      * area >= stop_area_ratio       -> 'S'  (close range wins over steering)
      * target in the left third      -> 'L'
      * target in the right third     -> 'R'
      * target in the centre third    -> 'F'
    """

    def __init__(
        self,
        left_boundary: float = 0.33,
        center_boundary: float = 0.66,
        stop_area_ratio: float = 0.35,
    ) -> None:
        classify_zone(0.5, left_boundary, center_boundary)
        if not 0.0 < stop_area_ratio <= 1.0:
            raise ValueError(f"stop_area_ratio must be in (0,1], got {stop_area_ratio}")
        self.left_boundary = float(left_boundary)
        self.center_boundary = float(center_boundary)
        self.stop_area_ratio = float(stop_area_ratio)

    @staticmethod
    def area_ratio(
        detection: Detection, frame_width: float, frame_height: float
    ) -> float:
        """Bounding-box area as a fraction of the frame area, clipped to [0,1]."""
        if frame_width <= 0 or frame_height <= 0:
            raise ValueError("frame dimensions must be > 0")
        frame_area = float(frame_width) * float(frame_height)
        box_area = max(0.0, float(detection.width)) * max(0.0, float(detection.height))
        return min(1.0, box_area / frame_area)

    def decide(
        self,
        detection: Detection | None,
        frame_width: float,
        frame_height: float,
    ) -> SteeringDecision:
        """Choose the next command for one (possibly absent) target detection."""
        if detection is None:
            return SteeringDecision(STOP, None, 0.0, False, "no target detected")

        area = self.area_ratio(detection, frame_width, frame_height)
        if area >= self.stop_area_ratio:
            return SteeringDecision(
                STOP,
                None,
                area,
                True,
                f"target too close: area {area:.2f} >= {self.stop_area_ratio:.2f}",
            )

        zone = classify_zone(
            detection.center_x_norm(frame_width),
            self.left_boundary,
            self.center_boundary,
        )
        command = command_for_zone(zone)
        if command == TURN_LEFT:
            reason = "target in left zone"
        elif command == TURN_RIGHT:
            reason = "target in right zone"
        else:
            reason = "target centred and far enough"
        return SteeringDecision(command, zone, area, True, reason)


def best_target(detections: list[Detection]) -> Detection | None:
    """Highest-confidence detection, or None when the list is empty."""
    if not detections:
        return None
    return max(detections, key=lambda d: d.confidence)
