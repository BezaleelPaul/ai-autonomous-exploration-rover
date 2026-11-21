"""Integration test for full-stack mobile companion, stream pairing, and command loop."""

from __future__ import annotations

import json
import threading
import time
import urllib.request
import pytest

from scripts.simulate_full_stack import (
    DASHBOARD_PORT,
    STREAM_PORT,
    MockPhoneCameraServer,
)


def test_full_stack_mobile_handshake_and_commands():
    # 1. Start mock phone stream
    server = MockPhoneCameraServer("127.0.0.1", STREAM_PORT + 1)
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()
    time.sleep(0.3)

    try:
        # 2. Verify QR endpoint produces valid PNG
        req_qr = urllib.request.Request(f"http://127.0.0.1:{DASHBOARD_PORT}/api/qr")
        with urllib.request.urlopen(req_qr, timeout=3) as resp:
            png_bytes = resp.read()
            assert png_bytes.startswith(b"\x89PNG")
            assert len(png_bytes) > 200

        # 3. Register phone stream URL
        stream_url = f"http://127.0.0.1:{STREAM_PORT + 1}/video"
        req_stream = urllib.request.Request(
            f"http://127.0.0.1:{DASHBOARD_PORT}/api/stream",
            data=json.dumps({"url": stream_url}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req_stream, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            assert data["ok"] is True
            assert data["source"] == stream_url

        # 4. Dispatch drive commands
        for cmd in ("F", "L", "R", "S"):
            req_cmd = urllib.request.Request(
                f"http://127.0.0.1:{DASHBOARD_PORT}/api/cmd",
                data=json.dumps({"c": cmd, "speed": 180}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req_cmd, timeout=2) as resp:
                res = json.loads(resp.read().decode())
                assert res["ok"] is True

        # 5. Verify state
        req_state = urllib.request.Request(f"http://127.0.0.1:{DASHBOARD_PORT}/api/state")
        with urllib.request.urlopen(req_state, timeout=3) as resp:
            st = json.loads(resp.read().decode())
            assert st["link"]["connected"] is True
            assert st["feed"]["source"] == stream_url

    finally:
        server.running = False
        server.shutdown()
