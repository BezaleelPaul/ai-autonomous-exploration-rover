"""AI Rover laptop tier: teleoperation, perception and autonomous steering.

Quick start::

    from ai_rover import RoverClient, ZoneSteering, YoloDetector, VisionPilot

The package is import-safe without OpenCV/Ultralytics installed; the heavy
libraries are only imported when a camera or a model is actually opened.
"""

from __future__ import annotations

__version__ = "1.3.0"

from .client import ClientStats, RoverClient, RoverStatus
from .config import AppConfig
from .pilot import PilotConfig, PilotStats, VisionPilot
from .protocol import (
    BATTERY_LOW_MV,
    BATTERY_RECOVER_MV,
    COMMANDS,
    FAULT_NAMES,
    STATE_NAMES,
    DEFAULT_SPEED,
    FORWARD_GATE_CM,
    GATE_SPEED_CM,
    LINK_WATCHDOG_MS,
    MOTION_COMMANDS,
    REAR_GATE_CM,
    SPEED_MAX,
    SPEED_MIN,
    Packet,
    ProtocolError,
    Telemetry,
    clamp_speed,
    crc8,
    encode_command,
    encode_telemetry,
    parse_command,
    parse_frame,
    parse_telemetry,
    required_gate_cm,
)
from .steering import Decision, Detection, ZoneConfig, ZoneSteering
from .vision import LatestFrameSource, WorldDetector, YoloDetector, make_detector

__all__ = [
    "AppConfig",
    "ClientStats",
    "BATTERY_LOW_MV",
    "BATTERY_RECOVER_MV",
    "COMMANDS",
    "DEFAULT_SPEED",
    "Decision",
    "Detection",
    "FAULT_NAMES",
    "FORWARD_GATE_CM",
    "GATE_SPEED_CM",
    "LINK_WATCHDOG_MS",
    "LatestFrameSource",
    "MOTION_COMMANDS",
    "Packet",
    "PilotConfig",
    "PilotStats",
    "ProtocolError",
    "REAR_GATE_CM",
    "RoverClient",
    "RoverStatus",
    "SPEED_MAX",
    "SPEED_MIN",
    "STATE_NAMES",
    "Telemetry",
    "VisionPilot",
    "WorldDetector",
    "YoloDetector",
    "make_detector",
    "ZoneConfig",
    "ZoneSteering",
    "clamp_speed",
    "crc8",
    "encode_command",
    "encode_telemetry",
    "parse_command",
    "parse_frame",
    "parse_telemetry",
    "required_gate_cm",
    "__version__",
]
