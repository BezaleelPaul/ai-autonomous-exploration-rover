"""Wheel-odometry math: encoder ticks -> distance (Phase 9+ foundation).

Consumes config.yaml `control:` (encoders_enabled, encoder_ppr,
wheel_diameter_cm). Firmware counts ticks on D2/D3 and reports `TICKS:<l>,<r>`;
this module converts them once feedback is used on the laptop side. Physical
validation is HARDWARE REQUIRED until real wheels turn the encoders.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Odometry:
    """Converts encoder ticks to physical distance (IMU-free dead reckoning)."""

    encoder_ppr: int
    wheel_diameter_cm: float
    encoders_enabled: bool = False

    @property
    def wheel_circumference_cm(self) -> float:
        return math.pi * self.wheel_diameter_cm

    def ticks_to_cm(self, ticks: int) -> float:
        if self.encoder_ppr <= 0:
            raise ValueError("encoder_ppr must be > 0")
        return (max(0, int(ticks)) / self.encoder_ppr) * self.wheel_circumference_cm


def odometry_from_config(cfg: dict) -> Odometry:
    """Build odometry geometry from config.yaml `control:` keys."""
    ctl = cfg.get("control", {})
    return Odometry(
        encoder_ppr=int(ctl.get("encoder_ppr", 20)),
        wheel_diameter_cm=float(ctl.get("wheel_diameter_cm", 6.5)),
        encoders_enabled=bool(ctl.get("encoders_enabled", False)),
    )
