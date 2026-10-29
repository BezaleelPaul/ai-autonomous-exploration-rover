"""AI video annotation server: live YOLO boxes for the rover's Wi-Fi pad.

Sits between the phone's IP Webcam stream and the rover control pad:

    phone IP Webcam (http://<PHONE_IP>:8080/video)
        -> this server: YOLO detection + box overlay
        -> rover pad CAMERA panel (http://<LAPTOP_IP>:8000/video)

Run it on the laptop while the laptop's Wi-Fi is joined to the rover's
soft-AP ("AI_Rover_Control"), then paste the printed URL into the pad's
CAMERA panel (or GET /cam?u=<url> once). The pad at http://192.168.4.1/
then shows the live video WITH AI recognition boxes, next to the drive
buttons.

    py -3.12 scripts/ai_video_server.py --url http://<PHONE_IP>:8080/video
    py -3.12 scripts/ai_video_server.py --mock        # no camera, self-test

Endpoints: / (status + the URL for the pad), /video (annotated MJPEG),
/state (JSON health). Probe a running server with --check.
"""

from __future__ import annotations

import argparse
import contextlib
import socket
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from software.ai.detector import BaseDetector, create_detector
from software.perception_node.stream import open_ip_webcam

MJPEG_FPS = 12.0
STATUS_JSON = "application/json"


@dataclass
class Shared:
    """Latest-frame slot shared between the grabber/detector and HTTP."""

    lock: threading.Lock
    annotated: np.ndarray | None = None
    source_ok: bool = False
    detections: int = 0
    infer_fps: float = 0.0
    model_name: str = ""

    def publish(self, frame: np.ndarray, count: int, fps: float, ok: bool) -> None:
        with self.lock:
            self.annotated = frame
            self.detections = count
            self.infer_fps = fps
            self.source_ok = ok

    def snapshot(self) -> tuple[np.ndarray | None, bool, int, float]:
        with self.lock:
            frame = None if self.annotated is None else self.annotated.copy()
            return frame, self.source_ok, self.detections, self.infer_fps


def placeholder_frame(text: str) -> np.ndarray:
    img = np.full((480, 640, 3), 24, dtype=np.uint8)
    cv2.putText(
        img,
        text,
        (30, 230),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (80, 200, 255),
        2,
        cv2.LINE_AA,
    )
    return img


def draw_detections(frame: np.ndarray, detections, target: str) -> np.ndarray:
    out = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = (int(det.x1), int(det.y1), int(det.x2), int(det.y2))
        is_target = det.class_name.lower() == target.lower()
        color = (60, 220, 60) if is_target else (60, 160, 240)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f"{det.class_name} {det.confidence:.2f}"
        if is_target:
            label = f"TARGET {label}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        ty = y1 - 8 if y1 - 8 > th else y2 + th + 8
        cv2.rectangle(out, (x1, ty - th - 6), (x1 + tw + 6, ty + 4), color, -1)
        cv2.putText(
            out,
            label,
            (x1 + 3, ty),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )
    hud = f"AI LIVE  objects={len(detections)}"
    cv2.rectangle(out, (0, 0), (out.shape[1], 30), (0, 0, 0), -1)
    cv2.putText(
        out,
        hud,
        (10, 21),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (120, 255, 120),
        2,
        cv2.LINE_AA,
    )
    return out


def detect_loop(
    url: str,
    detector: BaseDetector,
    shared: Shared,
    target: str,
    mock: bool,
    cam: int = -1,
) -> None:
    """Owns the frame source (webcam or IP Webcam client): grab -> YOLO -> slot."""
    cap = None
    stream = None
    if cam >= 0:
        cap = cv2.VideoCapture(cam)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    else:
        stream = open_ip_webcam(url, mock=mock)
        stream.open()
    ema = 0.0
    while True:
        started = time.time()
        ok = True
        if cam >= 0:
            good, frame = cap.read()
            if not good:
                ok = False
                cap.release()
                time.sleep(0.5)
                cap = cv2.VideoCapture(cam)
                frame = None
        else:
            try:
                frame = stream.read()
            except Exception:
                frame = None
        if frame is None:
            text = "NO WEBCAM" if cam >= 0 else f"NO STREAM  {url}"
            frame = placeholder_frame(text)
            count = 0
        else:
            detections = detector.detect(frame)
            count = len(detections)
            frame = draw_detections(frame, detections, target)
        took = time.time() - started
        ema = 0.9 * ema + 0.1 * (1.0 / took if took > 0 else 0.0)
        shared.publish(frame, count, ema, ok)
        time.sleep(max(0.0, 1.0 / MJPEG_FPS - took))


def build_detector(args: argparse.Namespace) -> BaseDetector:
    if args.mock:
        from software.ai.detector import MockDetector

        return MockDetector(target=args.target or "bottle")
    cfg = {
        "ai": {
            "backend": "yolo",
            "yolo_model": args.model,
            "confidence_threshold": args.conf,
            "yolo_imgsz": args.imgsz,
            "allowed_classes": args.classes or [],
            "yolo_track": False,
            "export": "torch",
        }
    }
    return create_detector(cfg)


def lan_ip() -> str:
    for probe in ("192.168.4.1", "8.8.8.8"):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.2)
            sock.connect((probe, 80))
            ip = sock.getsockname()[0]
            sock.close()
            if not ip.startswith("127."):
                return ip
        except OSError:
            continue
    return "127.0.0.1"


STATUS_PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="5"><title>AI Video Server</title></head>
<body style="background:#111;color:#eee;font-family:monospace">
<h2 style="color:#7c7">AI VIDEO SERVER</h2>
<p>Paste this URL into the rover pad CAMERA panel:<br>
<b style="color:#fc6;font-size:1.2em">{base}/video</b></p>
<p>source ok: <b>{ok}</b> | objects: <b>{objects}</b> | infer: <b>{fps} fps</b><br>
model: {model}</p>
<p><img src="/video" style="max-width:640px;border:1px solid #333"></p>
</body></html>"""


def make_handler(shared: Shared, model_name: str):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/state":
                _, ok, count, fps = shared.snapshot()
                body = (
                    '{"ok":'
                    + ("true" if ok else "false")
                    + ',"objects":'
                    + str(count)
                    + ',"infer_fps":'
                    + f"{fps:.1f}"
                    + ',"model":"'
                    + model_name
                    + '"}'
                )
                self._send(200, STATUS_JSON, body.encode())
            elif self.path == "/video":
                self._stream()
            elif self.path.startswith("/"):
                _, ok, count, fps = shared.snapshot()
                html = STATUS_PAGE.format(
                    base=f"http://{self.server.server_address[0]}:{self.server.server_port}",
                    ok=ok,
                    objects=count,
                    fps=f"{fps:.1f}",
                    model=model_name,
                )
                self._send(200, "text/html", html.encode())
            else:
                self._send(404, "text/plain", b"not found")

        def _send(self, code: int, ctype: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            with contextlib.suppress(ConnectionResetError, BrokenPipeError):
                self.wfile.write(body)

        def _stream(self) -> None:
            self.send_response(200)
            self.send_header(
                "Content-Type", "multipart/x-mixed-replace; boundary=frame"
            )
            self.end_headers()
            while True:
                frame, _ok, _n, _f = shared.snapshot()
                if frame is None:
                    frame = placeholder_frame("AI SERVER STARTING...")
                ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if not ok:
                    continue
                try:
                    self.wfile.write(
                        b"--frame\r\nContent-Type: image/jpeg\r\n"
                        + f"Content-Length: {len(buf)}\r\n\r\n".encode()
                        + buf.tobytes()
                        + b"\r\n"
                    )
                    self.wfile.flush()
                except (ConnectionResetError, BrokenPipeError):
                    return
                time.sleep(1.0 / MJPEG_FPS)

        def log_message(self, *args) -> None:
            return  # keep the console quiet; /state is the healthcheck

    return Handler


def self_check(port: int) -> int:
    """--check: fetch /state and one JPEG from a running server."""
    import urllib.request

    base = f"http://127.0.0.1:{port}"
    with urllib.request.urlopen(f"{base}/state", timeout=5) as res:
        print("state:", res.read().decode())
    with urllib.request.urlopen(f"{base}/video", timeout=5) as res:
        chunk = res.read(60000)
    ok = b"\xff\xd8" in chunk and b"\xff\xd9" in chunk
    print("video: JPEG SOI/EOI found =", ok)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI annotated video server")
    parser.add_argument(
        "--url", default=None, help="phone stream URL (default: config.yaml)"
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument(
        "--target", default="person", help="class to highlight green (default: person)"
    )
    parser.add_argument(
        "--classes", default="", help="comma list to limit detection classes"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="synthetic frames + mock detector (self-test)",
    )
    parser.add_argument(
        "--cam",
        type=int,
        default=-1,
        help="use the laptop webcam (cv2 index, 0 = default) instead of --url",
    )
    parser.add_argument(
        "--check", action="store_true", help="probe a running server and exit"
    )
    args = parser.parse_args(argv)

    if args.check:
        return self_check(args.port)

    if args.url is None:
        try:
            import yaml

            with open("config/config.yaml", encoding="utf-8") as handle:
                cfg = yaml.safe_load(handle) or {}
            args.url = cfg.get("perception", {}).get("stream_url", "")
        except OSError:
            args.url = ""
    if not args.url and not args.mock and args.cam < 0:
        parser.error("--url is required (or use --mock or --cam)")
    if args.classes:
        args.classes = [c.strip() for c in args.classes.split(",") if c.strip()]

    print(f"loading model {args.model} (mock={args.mock})...")
    detector = build_detector(args)
    shared = Shared(lock=threading.Lock(), model_name=args.model)
    threading.Thread(
        target=detect_loop,
        args=(args.url, detector, shared, args.target, args.mock, args.cam),
        daemon=True,
    ).start()

    server = ThreadingHTTPServer(
        ("0.0.0.0", args.port), make_handler(shared, args.model)
    )
    print("=" * 60)
    print(f"AI VIDEO SERVER  ->  http://{lan_ip()}:{args.port}/video")
    print("Paste that URL into the rover pad CAMERA panel (192.168.4.1).")
    print("Ctrl+C to stop.")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
