"""Command-line entry point for the two-tier perception node.

Examples::

    python -m software.perception_node --url http://192.168.1.50:8080/video
    python -m software.perception_node --serial-mode bluetooth --port COM5
    python -m software.perception_node --mock --once        # no hardware
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from software.perception_node.node import PerceptionNode
from software.perception_node.serial_link import SERIAL_MODES
from software.utils.config_loader import load_config


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Two-tier rover perception node: IP Webcam -> YOLOv8n -> F/L/R/S"
    )
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument(
        "--url",
        default=None,
        help="video URL, e.g. http://<PHONE_IP>:8080/video (default: perception.stream_url)",
    )
    parser.add_argument(
        "--target",
        default=None,
        help="target class (default: perception.target_class, e.g. person)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="ultralytics weights (default: perception.model, e.g. yolov8n.pt)",
    )
    parser.add_argument(
        "--serial-mode",
        choices=[*SERIAL_MODES, "http"],
        default=None,
        help="output transport (default: perception.serial_mode; http = ESP32 WiFi bridge)",
    )
    parser.add_argument(
        "--rover-url",
        default=None,
        help="WiFi bridge base URL for --serial-mode http, e.g. http://192.168.4.1",
    )
    parser.add_argument(
        "--port",
        default=None,
        help="explicit COM port, e.g. COM5 for a Bluetooth virtual serial",
    )
    parser.add_argument(
        "--no-hud", action="store_true", help="headless: no OpenCV window"
    )
    parser.add_argument(
        "--mock", action="store_true", help="no hardware: simulated camera + serial"
    )
    parser.add_argument(
        "--mock-camera",
        action="store_true",
        help="simulated camera + detector, real serial (bench-test the BT link)",
    )
    parser.add_argument(
        "--mock-serial",
        action="store_true",
        help="simulated serial, real camera/detector",
    )
    parser.add_argument(
        "--loop-period",
        type=float,
        default=0.03,
        help="headless loop period in seconds",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="run a single cycle, print the command, exit",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return parser


def _config_with_overrides(args: argparse.Namespace) -> dict:
    """Overlay CLI flags on top of the loaded config without mutating it."""
    cfg = load_config(args.config)
    perception = dict(cfg.get("perception", {}))
    if args.url is not None:
        perception["stream_url"] = args.url
    if args.target is not None:
        perception["target_class"] = args.target
    if args.model is not None:
        perception["model"] = args.model
    if args.serial_mode is not None:
        perception["serial_mode"] = args.serial_mode
    if args.rover_url is not None:
        perception["rover_url"] = args.rover_url
    if args.port is not None:
        perception["serial_port"] = args.port
    if args.no_hud:
        perception["hud_enabled"] = False
    return {**cfg, "perception": perception}


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    cfg = _config_with_overrides(args)
    node = PerceptionNode(
        cfg,
        mock=args.mock,
        mock_camera=args.mock_camera or None,
        mock_serial=args.mock_serial or None,
    )

    if args.once:
        if not node.startup():
            return 1
        try:
            state = node.step()
        finally:
            node.shutdown()
        decision = state.decision
        print(
            f"{decision.command} | zone={decision.zone} | "
            f"area={decision.area_ratio:.3f} | {decision.reason}"
        )
        return 0

    node.run(loop_period_s=max(0.0, args.loop_period))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
