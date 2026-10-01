"""Unit tests for SensorFusion and RobotState (Layer 6 & Layer 7)."""

import pytest
from software.ai.detection import Detection
from software.control.odometry import Odometry
from software.fusion.sensor_fusion import RobotState, SensorFusion
from software.hardware.arduino_serial import Telemetry
from software.perception.scene_analyzer import SceneResult


def test_sensor_fusion_state_and_summary():
    fusion = SensorFusion(emergency_obstacle_dist_m=0.25, min_target_confidence=0.5)

    det = Detection("person", 0.91, 350, 100, 450, 300, track_id=7)
    scene = SceneResult(target=det, position="CENTER", center_error=0.115, normalized_error=0.23)

    telemetry = Telemetry(
        distance_cm=142.0,
        status="OK",
        battery="78%",
        encoder_ticks=(100, 100),
        heading_deg=38.0,
        tilt_deg=3.1,
        temperature_c=26.5,
        sensor_fault=False,
    )

    state = fusion.update(scene, telemetry, now=100.0)

    assert state.target_class == "Person"
    assert state.target_track_id == 7
    assert state.target_confidence == 0.91
    assert round(state.target_direction, 2) == 0.23
    assert state.obstacle_distance_m == 1.42
    assert state.heading_deg == 38.0
    assert state.tilt_deg == 3.1
    assert state.battery_pct == 78.0
    assert state.is_safe_to_move is True

    summary = state.formatted_summary()
    assert "ROBOT STATE" in summary
    assert "Target: Person #7" in summary
    assert "Target confidence: 91%" in summary
    assert "Target direction: +0.23" in summary
    assert "Obstacle distance: 1.42 m" in summary
    assert "Heading: 38.0°" in summary
    assert "Tilt: 3.1°" in summary
    assert "Battery: 78%" in summary


def test_safety_arbitration_obstacle_override():
    fusion = SensorFusion(emergency_obstacle_dist_m=0.25)
    det = Detection("person", 0.95, 300, 100, 400, 300, track_id=3)
    scene = SceneResult(target=det, position="CENTER")

    # Obstacle is 0.15 m away (< 0.25 m emergency threshold)
    telemetry = Telemetry(distance_cm=15.0, status="OK", sensor_fault=False)

    state = fusion.update(scene, telemetry)
    assert not state.is_safe_to_move
    assert "SAFETY_OVERRIDE_OBSTACLE" in state.safety_status
