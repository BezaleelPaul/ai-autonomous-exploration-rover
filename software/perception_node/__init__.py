"""Two-tier perception node: IP Webcam -> YOLOv8n -> F/L/R/S over serial.

Tier 1 (this package) runs on the laptop. Tier 2 is the ESP32 Bluetooth bridge
(``esp32/bt_bridge``) plus the Arduino motion & safety executive
(``arduino/motion_safety``).
"""

from software.perception_node.cli import build_arg_parser, main
from software.perception_node.hud import draw_hud
from software.perception_node.node import NodeState, PerceptionNode, policy_from_config
from software.perception_node.serial_link import (
    SerialLink,
    detect_bluetooth_port,
    resolve_serial_port,
)
from software.perception_node.stream import open_ip_webcam, validate_stream_url
from software.perception_node.zones import (
    PERCEPTION_COMMANDS,
    SteeringDecision,
    SteeringPolicy,
    Zone,
    classify_zone,
)

__all__ = [
    "PERCEPTION_COMMANDS",
    "NodeState",
    "PerceptionNode",
    "SerialLink",
    "SteeringDecision",
    "SteeringPolicy",
    "Zone",
    "build_arg_parser",
    "classify_zone",
    "detect_bluetooth_port",
    "draw_hud",
    "main",
    "open_ip_webcam",
    "policy_from_config",
    "resolve_serial_port",
    "validate_stream_url",
]
