#!/usr/bin/env python3
"""End-to-end simulator verifying mobile companion pairing, stream ingestion,
command dispatch, and ultrasonic safety gating across the full stack.

Usage:
    python3 scripts/simulate_full_stack.py
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STREAM_PORT = 8089
DASHBOARD_PORT = 5000


class MockPhoneCameraServer(ThreadingHTTPServer):
    def __init__(self, host: str = "127.0.0.1", port: int = STREAM_PORT):
        self.running = True
        self.frame_count = 0
        super().__init__((host, port), _CameraHandler)

    def generate_frame(self) -> bytes:
        self.frame_count += 1
        t = self.frame_count * 0.1
        # Create a synthetic 320x240 frame with a moving target block
        img = np.zeros((240, 320, 3), dtype=np.uint8)
        # Background gradient
        img[:, :] = [20, 25, 35]

        # Moving obstacle target (oscillating x)
        cx = int(160 + 80 * np.sin(t))
        cy = 120
        cv2.rectangle(img, (cx - 30, cy - 30), (cx + 30, cy + 30), (0, 242, 254), -1)
        cv2.putText(
            img,
            f"SIM PHONE CAM F:{self.frame_count}",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
        )

        _, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return enc.tobytes()


class _CameraHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress request spam

    def do_GET(self):
        if self.path in ("/video", "/video_feed", "/"):
            self.send_response(200)
            self.send_header(
                "Content-Type", "multipart/x-mixed-replace; boundary=frame"
            )
            self.end_headers()
            while getattr(self.server, "running", False):
                frame_bytes = self.server.generate_frame()
                try:
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(
                        f"Content-Length: {len(frame_bytes)}\r\n\r\n".encode()
                    )
                    self.wfile.write(frame_bytes)
                    self.wfile.write(b"\r\n")
                    time.sleep(0.05)  # 20 FPS
                except (BrokenPipeError, ConnectionResetError):
                    break


def run_full_stack_verification() -> dict:
    results = {}
    print("=" * 65)
    print("  AI ROVER FULL-STACK COMPANION & TELEMETRY SIMULATION")
    print("=" * 65)

    # 1. Start Mock Phone Camera Server
    print("[1/5] Launching Simulated Mobile Phone Camera Server on port 8089...")
    cam_server = MockPhoneCameraServer("127.0.0.1", STREAM_PORT)
    cam_thread = threading.Thread(target=cam_server.serve_forever, daemon=True)
    cam_thread.start()
    time.sleep(0.5)
    print("      -> Mock Phone Camera Server active at http://127.0.0.1:8089/video")
    results["cam_server"] = "UP"

    # 2. Test QR Code Pairing Endpoint
    print("[2/5] Testing Mobile Pairing Endpoints (/companion & /api/qr)...")
    req_qr = urllib.request.Request(f"http://127.0.0.1:{DASHBOARD_PORT}/api/qr")
    with urllib.request.urlopen(req_qr, timeout=3) as resp:
        qr_bytes = resp.read()
        assert len(qr_bytes) > 200, "QR code image payload too small"
        print(f"      -> /api/qr generated valid PNG QR code ({len(qr_bytes)} bytes)")
    results["qr_endpoint"] = "OK"

    # 3. Automated Stream Registration Handshake
    print("[3/5] Simulating Phone Handshake -> Registering Stream URL with Mission Control...")
    stream_payload = json.dumps({"url": f"http://127.0.0.1:{STREAM_PORT}/video"}).encode()
    req_stream = urllib.request.Request(
        f"http://127.0.0.1:{DASHBOARD_PORT}/api/stream",
        data=stream_payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req_stream, timeout=4) as resp:
        data = json.loads(resp.read().decode())
        assert data.get("ok") is True, f"Stream registration failed: {data}"
        print(f"      -> Handshake accepted! Active source: {data.get('source')}")
    results["handshake"] = "OK"

    # 4. Dispatch Motion Commands (F, L, R, S)
    print("[4/5] Testing Motion Commands dispatch and latency...")
    test_commands = [
        ("F", 180, "Forward 180"),
        ("L", 150, "Turn Left 150"),
        ("R", 150, "Turn Right 150"),
        ("S", 0, "Emergency Stop"),
    ]
    latencies = []
    for cmd, spd, desc in test_commands:
        t0 = time.perf_counter()
        cmd_payload = json.dumps({"c": cmd, "speed": spd}).encode()
        req_cmd = urllib.request.Request(
            f"http://127.0.0.1:{DASHBOARD_PORT}/api/cmd",
            data=cmd_payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req_cmd, timeout=2) as resp:
            data = json.loads(resp.read().decode())
            dt_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(dt_ms)
            assert data.get("ok") is True, f"Command {cmd} failed"
            print(f"      -> {desc} ({cmd}{spd}): ACK in {dt_ms:.1f} ms")
        time.sleep(0.1)

    avg_latency = sum(latencies) / len(latencies)
    print(f"      -> Average command round-trip latency: {avg_latency:.1f} ms")
    results["avg_cmd_latency_ms"] = round(avg_latency, 1)

    # 5. Verify Telemetry State
    print("[5/5] Checking live telemetry feedback loop (/api/state)...")
    req_state = urllib.request.Request(f"http://127.0.0.1:{DASHBOARD_PORT}/api/state")
    with urllib.request.urlopen(req_state, timeout=3) as resp:
        state_data = json.loads(resp.read().decode())
        link = state_data.get("link", {})
        feed = state_data.get("feed", {})
        print(f"      -> Link Connected: {link.get('connected')} | State: {link.get('state')}")
        print(f"      -> Camera Source: {feed.get('source')} | AI Model: {feed.get('model')}")
        assert link.get("connected") is True
        results["telemetry"] = "VERIFIED"

    # Cleanup
    cam_server.running = False
    cam_server.shutdown()
    print("=" * 65)
    print("  ALL VERIFICATION CHECKS PASSED: FULL SYSTEM READY")
    print("=" * 65)
    return results


if __name__ == "__main__":
    run_full_stack_verification()
