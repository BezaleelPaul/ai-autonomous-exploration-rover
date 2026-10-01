"""LEFT/CENTER/RIGHT classification from bbox center. No depth claims."""

from __future__ import annotations


def classify_position(
    center_x_norm: float, left_max: float = 0.33, center_max: float = 0.66
) -> str:
    if center_x_norm < left_max:
        return "LEFT"
    if center_x_norm < center_max:
        return "CENTER"
    return "RIGHT"


def is_centered(center_x_norm: float, tolerance: float = 0.06) -> bool:
    return abs(center_x_norm - 0.5) <= tolerance
