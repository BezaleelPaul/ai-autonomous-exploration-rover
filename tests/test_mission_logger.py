"""Unit tests for MissionLogger and analyze_mission (Layer 8)."""

from pathlib import Path
import pytest

from scripts.analyze_mission import analyze, parse_mission_log
from software.ai.detection import Detection
from software.fusion.sensor_fusion import RobotState
from software.telemetry.mission_logger import MissionLogger


def test_mission_logger_and_analysis(tmp_path):
    log_dir = str(tmp_path / "logs")
    logger = MissionLogger(log_dir=log_dir, filename="test_mission.csv")

    state1 = RobotState(
        timestamp=1000.0,
        target_class="Person",
        target_track_id=7,
        target_confidence=0.91,
        target_direction=0.23,
        obstacle_distance_m=1.42,
        velocity_m_s=0.28,
        heading_deg=38.0,
        tilt_deg=3.1,
        battery_pct=78.0,
        temperature_c=25.0,
    )
    det = Detection("person", 0.91, 100, 100, 200, 300, track_id=7)

    logger.log_mission_step(state1, det, decision_cmd="F", frame_id=1)

    state2 = RobotState(
        timestamp=1000.1,
        target_class="Person",
        target_track_id=7,
        target_confidence=0.93,
        target_direction=0.05,
        obstacle_distance_m=0.20,
        velocity_m_s=0.0,
        heading_deg=38.5,
        tilt_deg=3.2,
        battery_pct=77.9,
        temperature_c=25.2,
    )
    logger.log_mission_step(state2, det, decision_cmd="S", frame_id=2)

    csv_file = Path(log_dir) / "test_mission.csv"
    assert csv_file.exists()

    rows = parse_mission_log(csv_file)
    assert len(rows) == 2

    report = analyze(rows)
    assert report["mission_summary"]["total_frames_logged"] == 2
    assert report["detection_statistics"]["detections_by_class"]["Person"] == 2
    assert report["tracking_statistics"]["unique_tracks_count"] == 1
    assert "7" in report["tracking_statistics"]["track_identities"]
    assert report["safety_and_decisions"]["safety_stop_events"] == 1
