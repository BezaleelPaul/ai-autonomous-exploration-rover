"""Scientific mission data logging for autonomous exploration rover.

Records 13 synchronized modalities per observation:
  timestamp, frame_id, track_id, class, confidence, bbox, distance,
  speed, heading, tilt, battery, temperature, decision
"""

from __future__ import annotations

import csv
import datetime
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from software.ai.detection import Detection
    from software.fusion.sensor_fusion import RobotState


MISSION_HEADER = [
    "timestamp",
    "frame_id",
    "track_id",
    "class",
    "confidence",
    "bbox",
    "distance",
    "speed",
    "heading",
    "tilt",
    "battery",
    "temperature",
    "decision",
]


class MissionLogger:
    """Scientific data recorder for autonomous exploration trials."""

    def __init__(self, log_dir: str = "logs", filename: str = "mission_log.csv"):
        self.dir = Path(log_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.dir / filename
        self._frame_counter = 0
        self._init_csv()

    def _init_csv(self) -> None:
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(MISSION_HEADER)

    def log_mission_step(
        self,
        state: RobotState,
        detection: Detection | None = None,
        decision_cmd: str = "S",
        frame_id: int | None = None,
    ) -> None:
        """Record one synchronized observation row."""
        if frame_id is not None:
            fid = frame_id
        else:
            self._frame_counter += 1
            fid = self._frame_counter

        ts = datetime.datetime.fromtimestamp(
            state.timestamp if state.timestamp > 0 else datetime.datetime.now().timestamp()
        ).isoformat(timespec="milliseconds")

        track_id = state.target_track_id if state.target_track_id is not None else "-"
        cls_name = state.target_class
        conf = round(state.target_confidence, 3)

        if detection is not None:
            bbox_str = f"[{int(detection.x1)},{int(detection.y1)},{int(detection.x2)},{int(detection.y2)}]"
        else:
            bbox_str = "-"

        dist = round(state.obstacle_distance_m, 3) if state.obstacle_distance_m is not None else "-"
        speed = round(state.velocity_m_s, 3)
        heading = round(state.heading_deg, 1)
        tilt = round(state.tilt_deg, 1)
        batt = round(state.battery_pct, 1) if state.battery_pct is not None else "-"
        temp = round(state.temperature_c, 1) if state.temperature_c is not None else "-"

        row = [
            ts,
            fid,
            track_id,
            cls_name,
            conf,
            bbox_str,
            dist,
            speed,
            heading,
            tilt,
            batt,
            temp,
            decision_cmd,
        ]

        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
