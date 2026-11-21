"""High-Fidelity Differential Drive Kinematics and Ultrasonic Raycast Simulator.

Models:
1. Differential drive non-holonomic kinematic equations (v, omega -> x, y, theta).
2. Motor stiction deadband (PWM < 60 produces zero torque).
3. Battery voltage scaling (7.4V nominal 2S Li-ion).
4. Wheel slip dynamics on low-traction surfaces.
5. Acoustic HC-SR04 ultrasonic cone raycaster with specular reflection misses.
6. Optical wheel encoder pulse generation (960 counts/revolution).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class ObstacleSegment:
    """A 2D line segment obstacle in global coordinates (x1, y1) to (x2, y2)."""
    x1: float
    y1: float
    x2: float
    y2: float
    is_specular: bool = True  # whether high incidence angles cause reflection misses


@dataclass
class PhysicsConfig:
    wheel_radius_m: float = 0.0325      # 65 mm wheel diameter -> r = 32.5 mm
    track_width_m: float = 0.150        # center-to-center distance between wheels
    stiction_pwm: int = 60              # minimum PWM to break static friction
    max_pwm: int = 255
    max_wheel_rad_s: float = 12.0       # top wheel angular velocity at 8.4V full PWM
    nominal_battery_v: float = 7.4
    min_battery_v: float = 6.4
    max_battery_v: float = 8.4
    encoder_cpr: float = 960.0          # ticks per wheel output revolution
    sonar_max_range_m: float = 3.5      # max ultrasonic range
    sonar_cone_deg: float = 15.0        # HC-SR04 acoustic emission cone
    specular_cutoff_deg: float = 45.0   # incidence angle cutoff for specular bounce


@dataclass
class RoverState2D:
    x: float = 0.0          # global X (meters)
    y: float = 0.0          # global Y (meters)
    theta: float = 0.0      # global heading angle (radians)
    v_linear: float = 0.0   # forward velocity (m/s)
    w_angular: float = 0.0  # rotational velocity (rad/s)
    ticks_left: int = 0     # optical encoder tick counter left
    ticks_right: int = 0    # optical encoder tick counter right
    battery_v: float = 7.4  # current battery pack voltage


class DifferentialDriveSimulator:
    """Physics simulation engine for the differential drive chassis."""

    def __init__(self, config: PhysicsConfig | None = None) -> None:
        self.cfg = config or PhysicsConfig()
        self.state = RoverState2D()
        self.obstacles: list[ObstacleSegment] = []

    def add_box_obstacle(self, cx: float, cy: float, width: float, height: float) -> None:
        """Add an axis-aligned bounding box obstacle into the global simulation world."""
        hw = width / 2.0
        hh = height / 2.0
        # 4 segments
        self.obstacles.extend([
            ObstacleSegment(cx - hw, cy - hh, cx + hw, cy - hh),
            ObstacleSegment(cx + hw, cy - hh, cx + hw, cy + hh),
            ObstacleSegment(cx + hw, cy + hh, cx - hw, cy + hh),
            ObstacleSegment(cx - hw, cy + hh, cx - hw, cy - hh),
        ])

    def pwm_to_wheel_speed(self, pwm: int) -> float:
        """Convert a commanded PWM value (-255 to 255) to wheel angular velocity (rad/s)."""
        if abs(pwm) < self.cfg.stiction_pwm:
            return 0.0

        sign = 1.0 if pwm > 0 else -1.0
        effective_pwm = min(self.cfg.max_pwm, abs(pwm)) - self.cfg.stiction_pwm
        usable_span = self.cfg.max_pwm - self.cfg.stiction_pwm

        # Battery voltage scaling factor
        v_factor = max(0.5, min(1.2, self.state.battery_v / self.cfg.nominal_battery_v))
        w = sign * (effective_pwm / usable_span) * self.cfg.max_wheel_rad_s * v_factor
        return w

    def step(
        self,
        pwm_left: int,
        pwm_right: int,
        dt_s: float = 0.05,
        slip_ratio: float = 0.0,
    ) -> RoverState2D:
        """Advance the physics simulation by time dt_s with commanded wheel PWMs."""
        w_l = self.pwm_to_wheel_speed(pwm_left)
        w_r = self.pwm_to_wheel_speed(pwm_right)

        # Apply wheel slip reduction to linear motion
        traction = max(0.0, min(1.0, 1.0 - slip_ratio))
        v_l = w_l * self.cfg.wheel_radius_m * traction
        v_r = w_r * self.cfg.wheel_radius_m * traction

        # Differential drive forward kinematics
        v = (v_r + v_l) / 2.0
        omega = (v_r - v_l) / self.cfg.track_width_m

        # Integrate pose (Runge-Kutta / exact arc integration)
        if abs(omega) < 1e-6:
            # Straight-line translation
            self.state.x += v * math.cos(self.state.theta) * dt_s
            self.state.y += v * math.sin(self.state.theta) * dt_s
        else:
            # Arc motion
            theta_next = self.state.theta + omega * dt_s
            self.state.x += (v / omega) * (math.sin(theta_next) - math.sin(self.state.theta))
            self.state.y -= (v / omega) * (math.cos(theta_next) - math.cos(self.state.theta))
            self.state.theta = (theta_next + math.pi) % (2.0 * math.pi) - math.pi

        self.state.v_linear = v
        self.state.w_angular = omega

        # Increment optical encoder tick counters
        rad_to_ticks = self.cfg.encoder_cpr / (2.0 * math.pi)
        self.state.ticks_left += int(round(abs(w_l) * dt_s * rad_to_ticks))
        self.state.ticks_right += int(round(abs(w_r) * dt_s * rad_to_ticks))

        return self.state

    def raycast_sonar(self) -> float | None:
        """Simulate the front HC-SR04 acoustic sensor pinging against obstacles."""
        if not self.obstacles:
            return None

        # Ultrasonic beam casts 5 rays within acoustic cone
        half_cone = math.radians(self.cfg.sonar_cone_deg / 2.0)
        rays = [-half_cone, -half_cone / 2.0, 0.0, half_cone / 2.0, half_cone]

        min_hit_dist = float("inf")

        for ray_offset in rays:
            ray_theta = self.state.theta + ray_offset
            cos_r = math.cos(ray_theta)
            sin_r = math.sin(ray_theta)

            p_start = (self.state.x, self.state.y)
            p_end = (
                self.state.x + self.cfg.sonar_max_range_m * cos_r,
                self.state.y + self.cfg.sonar_max_range_m * sin_r,
            )

            for seg in self.obstacles:
                hit = _intersect_segments(p_start, p_end, (seg.x1, seg.y1), (seg.x2, seg.y2))
                if hit is not None:
                    hx, hy = hit
                    dist = math.hypot(hx - self.state.x, hy - self.state.y)

                    # Check incidence angle for specular reflection
                    if seg.is_specular:
                        # Segment normal
                        dx = seg.x2 - seg.x1
                        dy = seg.y2 - seg.y1
                        seg_norm = (-dy, dx)
                        norm_len = math.hypot(seg_norm[0], seg_norm[1])
                        if norm_len > 1e-6:
                            nx = seg_norm[0] / norm_len
                            ny = seg_norm[1] / norm_len
                            # Dot product with ray
                            cos_inc = abs(cos_r * nx + sin_r * ny)
                            incidence_deg = math.degrees(math.acos(min(1.0, cos_inc)))
                            if incidence_deg > self.cfg.specular_cutoff_deg:
                                # Sound bounces away, no echo returned!
                                continue

                    if dist < min_hit_dist:
                        min_hit_dist = dist

        if min_hit_dist <= self.cfg.sonar_max_range_m:
            return min_hit_dist
        return None


def _intersect_segments(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> tuple[float, float] | None:
    """Compute the 2D intersection point between segment p1->p2 and segment p3->p4."""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
    if abs(denom) < 1e-9:
        return None

    ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
    ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denom

    if 0.0 <= ua <= 1.0 and 0.0 <= ub <= 1.0:
        ix = x1 + ua * (x2 - x1)
        iy = y1 + ua * (y2 - y1)
        return ix, iy
    return None
