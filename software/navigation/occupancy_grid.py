"""Local Bayesian Log-Odds Occupancy Grid and Costmap for Autonomous Rover Navigation.

Implements:
1. Log-Odds Bayesian mapping: transforms ultrasonic sonar readings and vision obstacles into
   cell probabilities with inverse sensor models.
2. Costmap inflation: expands obstacles by rover radius + safety margin to prevent collisions.
3. Candidate heading evaluation: finds the clearance valley that minimizes heading error
   toward a goal while avoiding high-cost cells.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass
class CostmapConfig:
    width_m: float = 4.0        # grid physical width (meters)
    height_m: float = 4.0       # grid physical height (meters)
    resolution_m: float = 0.05  # cell size (5 cm per cell = 80x80 grid)
    rover_radius_m: float = 0.15 # robot physical radius
    safety_margin_m: float = 0.10 # buffer distance around obstacles
    l_occ: float = 0.85         # log-odds increment for occupied cells
    l_free: float = -0.40       # log-odds decrement for free ray cells
    l_min: float = -4.0         # log-odds lower clamp
    l_max: float = 4.0          # log-odds upper clamp
    occupied_threshold: float = 0.65  # probability threshold for occupied cell


class LocalOccupancyGrid:
    """Robot-centric 2D Occupancy Grid maintaining log-odds of obstacle presence."""

    def __init__(self, config: CostmapConfig | None = None) -> None:
        self.cfg = config or CostmapConfig()
        self.grid_w = int(round(self.cfg.width_m / self.cfg.resolution_m))
        self.grid_h = int(round(self.cfg.height_m / self.cfg.resolution_m))
        # Origin is at robot center (grid_w // 2, grid_h // 2)
        self.origin_x = self.grid_w // 2
        self.origin_y = self.grid_h // 2

        # Log-odds array (0.0 = prior P=0.5 unknown)
        self.log_odds = np.zeros((self.grid_h, self.grid_w), dtype=np.float32)

    def reset(self) -> None:
        """Clear the occupancy grid to unknown state."""
        self.log_odds.fill(0.0)

    def world_to_grid(self, x_m: float, y_m: float) -> tuple[int, int] | None:
        """Convert robot-relative coordinates (x=forward, y=left) to grid indices."""
        gx = int(self.origin_x + round(y_m / self.cfg.resolution_m))
        gy = int(self.origin_y + round(x_m / self.cfg.resolution_m))
        if 0 <= gx < self.grid_w and 0 <= gy < self.grid_h:
            return gx, gy
        return None

    def grid_to_world(self, gx: int, gy: int) -> tuple[float, float]:
        """Convert grid indices (gx, gy) to robot-relative coordinates (x_m, y_m)."""
        x_m = (gy - self.origin_y) * self.cfg.resolution_m
        y_m = (gx - self.origin_x) * self.cfg.resolution_m
        return x_m, y_m

    def probabilities(self) -> np.ndarray:
        """Convert log-odds to occupancy probabilities [0.0, 1.0]."""
        # p = 1 - 1 / (1 + exp(l))
        return 1.0 - 1.0 / (1.0 + np.exp(self.log_odds))

    def update_sonar_reading(self, distance_m: float | None, cone_angle_deg: float = 15.0) -> None:
        """Update occupancy grid using an ultrasonic sensor reading along the forward axis."""
        if distance_m is None or distance_m <= 0.0 or not math.isfinite(distance_m):
            return

        # Maximum sonar range considered reliable
        max_range_m = min(distance_m, self.cfg.width_m / 2.0)
        hit_range_m = distance_m if distance_m <= (self.cfg.width_m / 2.0) else None

        # Raycast across acoustic cone angles
        half_cone = math.radians(cone_angle_deg / 2.0)
        num_rays = 7
        angles = np.linspace(-half_cone, half_cone, num_rays)

        for ang in angles:
            cos_a = math.cos(ang)
            sin_a = math.sin(ang)

            # Raycast free cells up to distance_m - resolution
            ray_steps = max(1, int(round(max_range_m / self.cfg.resolution_m)))
            for step in range(1, ray_steps):
                dist = step * self.cfg.resolution_m
                rx = dist * cos_a
                ry = dist * sin_a
                cell = self.world_to_grid(rx, ry)
                if cell is not None:
                    gx, gy = cell
                    self.log_odds[gy, gx] = max(
                        self.cfg.l_min, self.log_odds[gy, gx] + self.cfg.l_free
                    )

            # Mark obstacle cell if within grid bounds
            if hit_range_m is not None:
                ox = hit_range_m * cos_a
                oy = hit_range_m * sin_a
                cell = self.world_to_grid(ox, oy)
                if cell is not None:
                    gx, gy = cell
                    self.log_odds[gy, gx] = min(
                        self.cfg.l_max, self.log_odds[gy, gx] + self.cfg.l_occ
                    )

    def add_vision_obstacle(self, x_m: float, y_m: float, radius_m: float = 0.10) -> None:
        """Incorporate a detected obstacle position from computer vision."""
        cell = self.world_to_grid(x_m, y_m)
        if cell is None:
            return
        gx_c, gy_c = cell
        r_cells = max(1, int(round(radius_m / self.cfg.resolution_m)))

        for dy in range(-r_cells, r_cells + 1):
            for dx in range(-r_cells, r_cells + 1):
                if dx * dx + dy * dy <= r_cells * r_cells:
                    gx = gx_c + dx
                    gy = gy_c + dy
                    if 0 <= gx < self.grid_w and 0 <= gy < self.grid_h:
                        self.log_odds[gy, gx] = min(
                            self.cfg.l_max, self.log_odds[gy, gx] + self.cfg.l_occ * 1.5
                        )

    def build_inflated_costmap(self) -> np.ndarray:
        """Compute an obstacle-inflated costmap where cost in [0, 255]."""
        probs = self.probabilities()
        occupied_mask = probs >= self.cfg.occupied_threshold

        costmap = np.zeros_like(probs, dtype=np.uint8)
        if not np.any(occupied_mask):
            return costmap

        # Inflate obstacles by inflation radius
        inflation_m = self.cfg.rover_radius_m + self.cfg.safety_margin_m
        r_cells = max(1, int(round(inflation_m / self.cfg.resolution_m)))

        # Direct kernel convolution / morphological dilation
        occ_y, occ_x = np.nonzero(occupied_mask)
        for y, x in zip(occ_y, occ_x):
            y_min = max(0, y - r_cells)
            y_max = min(self.grid_h, y + r_cells + 1)
            x_min = max(0, x - r_cells)
            x_max = min(self.grid_w, x + r_cells + 1)

            for iy in range(y_min, y_max):
                for ix in range(x_min, x_max):
                    dist_cells = math.hypot(ix - x, iy - y)
                    if dist_cells <= r_cells:
                        # Cost decays linearly from 255 (obstacle core) to 1 (outer safety boundary)
                        cost = int(255 * (1.0 - (dist_cells / (r_cells + 1))))
                        if cost > costmap[iy, ix]:
                            costmap[iy, ix] = cost
        return costmap

    def find_safe_heading(
        self,
        target_heading_rad: float = 0.0,
        lookahead_m: float = 1.0,
        num_candidates: int = 17,
    ) -> tuple[float, bool]:
        """Find the safest heading angle that avoids high-cost cells.

        Returns (chosen_heading_rad, is_safe).
        """
        costmap = self.build_inflated_costmap()
        angles = np.linspace(-math.pi / 2.0, math.pi / 2.0, num_candidates)

        best_heading = target_heading_rad
        best_score = float("inf")
        is_safe = False

        steps = max(2, int(round(lookahead_m / self.cfg.resolution_m)))

        for ang in angles:
            cos_a = math.cos(ang)
            sin_a = math.sin(ang)

            path_cost = 0.0
            blocked = False

            for step in range(1, steps + 1):
                dist = step * self.cfg.resolution_m
                rx = dist * cos_a
                ry = dist * sin_a
                cell = self.world_to_grid(rx, ry)
                if cell is None:
                    continue
                gx, gy = cell
                cell_cost = costmap[gy, gx]
                if cell_cost >= 200:  # Hard collision or near-core
                    blocked = True
                    break
                path_cost += cell_cost

            if not blocked:
                # Score combines heading error toward goal + path cost penalty
                heading_err = abs(ang - target_heading_rad)
                score = heading_err * 2.0 + (path_cost / (steps * 255.0))
                if score < best_score:
                    best_score = score
                    best_heading = ang
                    is_safe = True

        return best_heading, is_safe
