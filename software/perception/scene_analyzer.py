"""Scene summary: target + position + size ratio + approach flag."""

from __future__ import annotations

from dataclasses import dataclass

from software.ai.detection import Detection
from software.perception.position_estimator import classify_position


@dataclass
class SceneResult:
    target: Detection | None = None
    position: str = "NONE"  # LEFT|CENTER|RIGHT|NONE
    width_ratio: float = 0.0
    very_close: bool = False
    count: int = 0
    center_error: float = 0.0  # cx - 0.5 in [-0.5, 0.5]; legacy P-steering input
    normalized_error: float = 0.0  # e_x = (x_c - W/2)/(W/2) in [-1.0, 1.0]


class SceneAnalyzer:
    def __init__(
        self,
        left_max: float = 0.33,
        center_max: float = 0.66,
        stop_width_ratio: float = 0.45,
    ):
        self.left_max = left_max
        self.center_max = center_max
        self.stop_width_ratio = stop_width_ratio

    def analyze(
        self,
        target: Detection | None,
        all_dets: list[Detection],
        frame_width: float = 640.0,
    ) -> SceneResult:
        if target is None:
            return SceneResult(count=len(all_dets))
        cx = target.center_x_norm(frame_width)
        pos = classify_position(cx, self.left_max, self.center_max)
        wr = target.width_ratio(frame_width)
        c_err = cx - 0.5
        norm_err = 2.0 * c_err
        return SceneResult(
            target=target,
            position=pos,
            width_ratio=wr,
            very_close=wr >= self.stop_width_ratio,
            count=len(all_dets),
            center_error=c_err,
            normalized_error=norm_err,
        )
