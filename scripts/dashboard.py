"""Launch live browser GUI.
Usage:
  python scripts/dashboard.py                    # webcam + real model
  python scripts/dashboard.py --backend mock     # instant, no weights
  python scripts/dashboard.py --esp32            # ESP32-CAM stream instead
  python scripts/dashboard.py --port 5000
  python scripts/dashboard.py --controls                 # + drive pad on COM port
  python scripts/dashboard.py --controls --arduino COM8  # explicit serial port
  python scripts/dashboard.py --controls --mock-serial   # no hardware
  python scripts/dashboard.py --ip-webcam                # phone stream from config
  python scripts/dashboard.py --ip-webcam http://<PHONE_IP>:8080/video
  python scripts/dashboard.py --auto --arduino COM8       # strict-gated autopilot
  python scripts/dashboard.py --observe --controls        # dry-run why-chain
  python scripts/dashboard.py --auto --record             # capture a run to data/runs
  python scripts/dashboard.py --controls                  # CLIP auto-loads for /api/explain
  python scripts/dashboard.py --controls --no-clip        # skip the CLIP explainer
  python scripts/dashboard.py --no-plugins                # drop scenesense depth (low-RAM host)
Then open: http://127.0.0.1:5000
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from software.dashboard.app import run_control_dashboard, run_live_dashboard
from software.dashboard.controls import ArduinoLink
from software.dashboard.live import LiveFeed
from software.utils.config_loader import load_config


def _open_arduino(cfg: dict, port: str, mock: bool, esp32_bridge: str | None = None) -> object:
    if esp32_bridge or (port and (port.startswith("http://") or port.startswith("https://"))):
        from software.dashboard.controls import Esp32Link

        bridge_url = esp32_bridge or port
        link = Esp32Link(bridge_url)
        link.connect()
        print(f"Rover wireless link via ESP32 @ {bridge_url}")
        return link

    from software.perception_node.serial_link import resolve_serial_port

    perception = cfg["perception"]
    board = port or resolve_serial_port("usb", (perception.get("serial_port") or None))
    if board is None and not mock:
        from software.dashboard.controls import Esp32Link

        print(
            "No Arduino found on USB. Falling back to wireless ESP32 gateway at http://192.168.4.1"
        )
        link = Esp32Link("http://192.168.4.1")
        link.connect()
        return link
    baud = int(perception.get("baud_rate", 115200)) if port else 115200
    link = ArduinoLink(board or "", baud, mock=mock)
    if not link.connect():
        print(f"Could not open {board}. Close the Arduino Serial Monitor first.")
        raise SystemExit(1)
    print(f"Arduino link on {board or 'mock'} @ {baud} baud")
    return link


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cam", type=int, default=0)
    p.add_argument("--esp32", action="store_true")
    p.add_argument(
        "--mock", action="store_true", help="run with animated simulation frame"
    )
    p.add_argument(
        "--ip-webcam",
        nargs="?",
        const="",
        default=None,
        metavar="URL",
        help="analyse a phone IP Webcam stream; omit the URL to use "
        "perception.stream_url from config/config.yaml",
    )
    p.add_argument("--backend", default=None)
    p.add_argument("--conf", type=float, default=None)
    p.add_argument("--controls", action="store_true", help="serve the drive pad too")
    p.add_argument(
        "--esp32-bridge",
        default=None,
        metavar="URL",
        help="wireless HTTP bridge to ESP32 (e.g. http://192.168.4.1) for untethered rover control",
    )
    p.add_argument(
        "--mock-serial", action="store_true", help="no hardware; record sends in memory"
    )
    p.add_argument("--arduino", default="", help="serial port, e.g. COM8")
    p.add_argument(
        "--auto",
        action="store_true",
        help="start MissionPilot in AUTO (strict arming; needs --controls)",
    )
    p.add_argument(
        "--observe",
        action="store_true",
        help="run the why-chain dry (nothing is sent) — needs --controls",
    )
    p.add_argument(
        "--explore",
        action="store_true",
        help="start MissionPilot in EXPLORE (roam loop; needs --controls)",
    )
    p.add_argument(
        "--record",
        action="store_true",
        help="capture decisions + frames to dashboard.record_dir (needs link)",
    )
    p.add_argument(
        "--explain",
        action="store_true",
        help="start the control deck; CLIP loads automatically (see --no-clip)",
    )
    p.add_argument(
        "--no-clip",
        action="store_true",
        help="skip the CLIP explainer (it auto-loads on the control deck)",
    )
    p.add_argument(
        "--no-plugins",
        action="store_true",
        help="clear plugins.enabled for this run (drops scenesense depth: ~9 s "
        "per pass on a memory-starved host, which is what makes the world "
        "model go degraded/stale). Shipped config keeps its default.",
    )
    p.add_argument(
        "--journal",
        action="store_true",
        help="force explorer.enabled on (needs GEMINI_API_KEY; advisory, "
        "off the control loop; reads config explorer: otherwise)",
    )
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    args = p.parse_args()

    cfg = load_config("config/config.yaml")
    if args.backend:
        cfg["ai"]["backend"] = args.backend
    if args.conf is not None:
        cfg["ai"]["confidence_threshold"] = args.conf
    if args.no_plugins:
        cfg.setdefault("plugins", {})["enabled"] = []
        print("plugins.enabled cleared for this run (--no-plugins)")

    dashboard_cfg = cfg.get("dashboard", {})
    host = args.host or str(dashboard_cfg.get("host", "127.0.0.1"))
    http_port = args.port or int(dashboard_cfg.get("port", 5000))

    from software.dashboard.live import resolve_source

    try:
        source = resolve_source(
            cfg,
            mock=args.mock,
            esp32=args.esp32,
            ip_webcam=args.ip_webcam,
        )
    except ValueError as exc:
        print(f"bad stream URL: {exc}")
        raise SystemExit(2) from exc
    feed = LiveFeed(cfg, source=source, cam_index=args.cam)
    feed.start()
    link: ArduinoLink | None = None
    pilot = None
    recorder = None
    explainer = None
    journal = None
    wants_journal = args.journal or bool((cfg.get("explorer") or {}).get("enabled"))
    wants_pilot = (
        args.controls
        or args.auto
        or args.observe
        or args.explore
        or args.record
        or args.explain
    )
    if wants_journal:
        from software.ai.journal import create_journal

        if args.journal:
            cfg.setdefault("explorer", {})["enabled"] = True
        journal = create_journal(cfg, feed, None)
        opened = journal.start()
        if journal.available:
            print(f"Explorer journal -> {opened}")
        else:
            print(f"Explorer journal off: {journal.reason}")
    if wants_pilot:
        link = _open_arduino(cfg, args.arduino, args.mock_serial, getattr(args, "esp32_bridge", None))
        from software.dashboard.pilot import MissionPilot

        from software.dashboard.recorder import RunRecorder

        recorder = RunRecorder(cfg, feed, None, link)
        if args.record:
            print(f"Recording -> {recorder.start()}")

        def _on_tick(decision) -> None:
            """Recorder and journal both ride the pilot tick; neither may block it."""
            if recorder is not None:
                recorder.record(decision)
            if journal is not None:
                journal.tick(decision)

        pilot = MissionPilot(
            cfg, feed, link, on_tick=_on_tick if (recorder or journal) else None
        )
        if args.auto:
            pilot.set_mode("auto")
        elif args.observe:
            pilot.set_mode("observe")
        elif args.explore:
            pilot.set_mode("explore")
        pilot.start(rate_hz=4.0)
        print(f"MissionPilot mode={pilot.mode} (4 Hz)")
    if link is not None and not args.no_clip:
        from software.ai.explainer import create_explainer

        explainer = create_explainer(cfg)
        if explainer.available:
            print(f"CLIP explainer ready via {explainer.backend}")
        else:
            print(f"CLIP unavailable: {explainer.reason}")
    try:
        if link is None:
            print(
                f"Live GUI on http://{host}:{http_port}  (CTRL+C stops, motors unaffected)"
            )
            run_live_dashboard(feed, host, http_port)
        else:
            print(
                f"Control deck on http://{host}:{http_port}  "
                "(hold W/arrow or a pad button to drive, release to stop)"
            )
            run_control_dashboard(
                feed,
                link,
                host,
                http_port,
                pilot=pilot,
                recorder=recorder,
                explainer=explainer,
                journal=journal,
            )
    finally:
        if pilot is not None:
            pilot.stop()
        if recorder is not None:
            recorder.stop()
        if journal is not None:
            journal.stop()
        feed.stop()
        if link is not None:
            try:
                link.release()
            finally:
                link.close()


if __name__ == "__main__":
    main()
