"""Layer 6 & Layer 7: Sensor Fusion and Safety Arbitration.

Fuses:
  - Computer Vision (YOLO11n + BoT-SORT track + Temporal validation)
  - Distance Sensors (HC-SR04 / ToF)
  - Odometry (Wheel encoders)
  - IMU (Heading yaw + Tilt pitch/roll)
  - Environmental Telemetry (Battery + Temperature)

Produces a unified ROBOT STATE and executes safety arbitration.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from software.ai.detection import Detection
    from software.control.odometry import Odometry
    from software.hardware.arduino_serial import Telemetry
    from software.perception.scene_analyzer import SceneResult


@dataclass
class RobotState:
    """Consolidated state representation of the autonomous rover."""

    timestamp: float = 0.0
    target_class: str = "NONE"
    target_track_id: int | None = None
    target_confidence: float = 0.0
    target_direction: float = 0.0  # normalized horizontal error e_x in [-1.0, 1.0]
    obstacle_distance_m: float | None = None
    velocity_m_s: float = 0.0
    heading_deg: float = 0.0
    tilt_deg: float = 0.0
    battery_pct: float | None = None
    temperature_c: float | None = None
    safety_status: str = "INITIALIZING"
    is_safe_to_move: bool = False

    def formatted_summary(self) -> str:
        """Publication/Console format for real-time telemetry."""
        tgt_str = self.target_class
        if self.target_track_id is not None:
            tgt_str += f" #{self.target_track_id}"
        conf_str = f"{int(round(self.target_confidence * 100))}%"
        dir_sign = "+" if self.target_direction >= 0 else ""
        dir_str = f"{dir_sign}{self.target_direction:.2f}"
        dist_str = f"{self.obstacle_distance_m:.2f} m" if self.obstacle_distance_m is not None else "N/A"
        batt_str = f"{int(round(self.battery_pct))}%" if self.battery_pct is not None else "N/A"

        lines = [
            "ROBOT STATE",
            f"Target: {tgt_str}",
            f"Target confidence: {conf_str}",
            f"Target direction: {dir_str}",
            f"Obstacle distance: {dist_str}",
            f"Velocity: {self.velocity_m_s:.2f} m/s",
            f"Heading: {self.heading_deg:.1f}°",
            f"Tilt: {self.tilt_deg:.1f}°",
            f"Battery: {batt_str}",
        ]
        return "\n".join(lines)


class SensorFusion:
    """Fuses multi-modal sensors into a coherent physical and perceptual state."""

    def __init__(
        self,
        emergency_obstacle_dist_m: float = 0.25,
        min_target_confidence: float = 0.50,
        wheel_odometry: WheelOdometry | None = None,
    ):
        self.emergency_dist_m = emergency_obstacle_dist_m
        self.min_target_conf = min_target_confidence
        self.odometry = wheel_odometry

        self._last_ticks: tuple[int, int] | None = None
        self._last_tick_time: float = 0.0
        self._last_dist_m: float = 0.0
        self._current_state = RobotState()

    def update(
        self,
        scene: SceneResult | None,
        telemetry: Telemetry | None,
        now: float | None = None,
    ) -> RobotState:
        now = now if now is not None else time.time()

        # 1. Vision State
        target_name = "NONE"
        track_id = None
        conf = 0.0
        direction = 0.0

        if scene is not None and scene.target is not None:
            t = scene.target
            target_name = t.class_name.capitalize()
            track_id = t.track_id
            conf = float(t.confidence)
            # normalized horizontal error e_x in [-1.0, 1.0]
            direction = float(getattr(scene, "normalized_error", 2.0 * scene.center_error))

        # 2. Obstacle Distance
        dist_m = None
        if telemetry is not None and getattr(telemetry, "distance_cm", None) is not None:
            if not getattr(telemetry, "sensor_fault", False):
                raw_d = telemetry.distance_cm
                if not isinstance(raw_d, bool):
                    try:
                        d_val = float(raw_d)
                        if math.isfinite(d_val) and d_val >= 0:
                            dist_m = round(d_val / 100.0, 3)
                    except (TypeError, ValueError):
                        dist_m = None

        # 3. Odometry & Velocity
        velocity = 0.0
        if telemetry is not None and telemetry.encoder_ticks is not None and self.odometry is not None:
            left_t, right_t = telemetry.encoder_ticks
            avg_ticks = int((left_t + right_t) / 2)
            curr_dist = self.odometry.ticks_to_cm(avg_ticks) / 100.0
            dt = now - self._last_tick_time
            if dt > 0.02 and self._last_tick_time > 0:
                velocity = max(0.0, (curr_dist - self._last_dist_m) / dt)
            self._last_dist_m = curr_dist
            self._last_tick_time = now

        # 4. IMU & Environmental Telemetry
        heading = 0.0
        tilt = 0.0
        battery = None
        temperature = None

        if telemetry is not None:
            try:
                h_val = float(getattr(telemetry, "heading_deg", 0.0))
                if math.isfinite(h_val):
                    heading = h_val
            except (TypeError, ValueError):
                heading = 0.0

            try:
                t_val = float(getattr(telemetry, "tilt_deg", 0.0))
                if math.isfinite(t_val):
                    tilt = t_val
            except (TypeError, ValueError):
                tilt = 0.0

            raw_temp = getattr(telemetry, "temperature_c", None)
            if raw_temp is not None:
                try:
                    temp_f = float(raw_temp)
                    if math.isfinite(temp_f):
                        temperature = temp_f
                except (TypeError, ValueError):
                    temperature = None

            raw_batt = getattr(telemetry, "battery", None)
            if raw_batt is not None and not isinstance(raw_batt, bool):
                try:
                    b_str = str(raw_batt).rstrip("%").rstrip("V").strip()
                    val = float(b_str)
                    if math.isfinite(val):
                        battery = val if "%" in str(raw_batt) or val > 12.0 else min(100.0, max(0.0, (val - 6.0) / 2.4 * 100))
                except (TypeError, ValueError):
                    battery = None

        # 5. Safety Arbitration
        # AI proposes movement, physical safety layer arbitrates.
        is_safe = True
        safety_status = "SAFE"

        if dist_m is not None and dist_m < self.emergency_dist_m:
            is_safe = False
            safety_status = f"SAFETY_OVERRIDE_OBSTACLE ({dist_m:.2f}m < {self.emergency_dist_m:.2f}m)"
        elif telemetry is not None and telemetry.sensor_fault:
            is_safe = False
            safety_status = "SENSOR_FAULT_OVERRIDE"
        elif target_name != "NONE" and conf < self.min_target_conf:
            is_safe = False
            safety_status = f"LOW_CONFIDENCE ({conf:.2f} < {self.min_target_conf:.2f})"

        self._current_state = RobotState(
            timestamp=now,
            target_class=target_name,
            target_track_id=track_id,
            target_confidence=conf,
            target_direction=direction,
            obstacle_distance_m=dist_m,
            velocity_m_s=round(velocity, 3),
            heading_deg=heading,
            tilt_deg=tilt,
            battery_pct=battery,
            temperature_c=temperature,
            safety_status=safety_status,
            is_safe_to_move=is_safe,
        )
        return self._current_state

    @property
    def current_state(self) -> RobotState:
        return self._current_state
