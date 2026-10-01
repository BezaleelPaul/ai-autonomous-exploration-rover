"""Launch live browser GUI.
Usage:
  python scripts/dashboard.py                    # webcam + real model
  python scripts/dashboard.py --backend mock     # instant, no weights
  python scripts/dashboard.py --esp32            # ESP32-CAM stream instead
  python scripts/dashboard.py --port 5000
Then open: http://127.0.0.1:5000
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from software.utils.config_loader import load_config
from software.dashboard.live import LiveFeed
from software.dashboard.app import run_live_dashboard


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cam", type=int, default=0)
    p.add_argument("--esp32", action="store_true")
    p.add_argument("--mock", action="store_true", help="run with animated simulation frame")
    p.add_argument("--backend", default=None)
    p.add_argument("--conf", type=float, default=None)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    args = p.parse_args()

    cfg = load_config("config/config.yaml")
    if args.backend:
        cfg["ai"]["backend"] = args.backend
    if args.conf is not None:
        cfg["ai"]["confidence_threshold"] = args.conf

    source = "mock" if args.mock else ("esp32" if args.esp32 else "cam")
    feed = LiveFeed(cfg, source=source, cam_index=args.cam)
    feed.start()
    print(
        f"Live GUI on http://{args.host}:{args.port}  (CTRL+C stops, motors unaffected)"
    )
    try:
        run_live_dashboard(feed, args.host, args.port)
    finally:
        feed.stop()


if __name__ == "__main__":
    main()
