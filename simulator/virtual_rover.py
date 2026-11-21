#!/usr/bin/env python3
"""Virtual AI Rover: an ESP32+Uno twin that speaks the real protocol.

Purpose
  * exercise the laptop tier, teleop CLI, smoke test and soak rig with **no
    hardware**;
  * demonstrate the safety state machine (15 cm speed-scaled gate, 500 ms
    watchdog, E-stop, low battery) deterministically;
  * give CI an HTTP endpoint that behaves like the rover.

It is a behaviour/protocol simulator, not a physics engine: wheel response is a
first-order lag, the "obstacle" is a single distance ahead, and there is no
camera.  Use it for control-path testing; use the real rover for vision.

    python simulator/virtual_rover.py --port 8090
    python scripts/teleop_cli.py --gateway http://127.0.0.1:8090
    python scripts/bench_smoke_test.py --gateway http://127.0.0.1:8090

Endpoints: /cmd /status /health /cam /sim/obstacle /sim/estop /sim/reset /
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "software") not in sys.path:
    sys.path.insert(0, str(ROOT / "software"))

from ai_rover.protocol import (  # noqa: E402
    DEFAULT_SPEED,
    ProtocolError,
    clamp_speed,
    parse_command,
    required_gate_cm,
)

MAX_SPEED_MM_S = 350.0
TRACK_MM = 150.0
WATCHDOG_MS = 500
BATTERY_LOW_MV = 6400
BATTERY_START_MV = 7800
DRAIN_MV_PER_S = 3.0


class VirtualRover:
    """Thread-safe simulated rover with the firmware's command semantics."""

    def __init__(self, obstacle_cm: float = 200.0) -> None:
        self.lock = threading.RLock()
        self.started = time.monotonic()
        self.obstacle_cm = float(obstacle_cm)
        self.battery_mv = float(BATTERY_START_MV)
        self.camera = ""
        self.reset()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- lifecycle ---------------------------------------------------------
    def reset(self) -> None:
        with self.lock:
            self.cmd = "S"
            self.speed = DEFAULT_SPEED
            self.state = "STOP"
            self.fault = "NONE"
            self.last_cmd_at = time.monotonic()
            self.last_cmd_text = "--"
            self.forwarded = 0
            self.rejected = 0
            self.estop = False
            self.vl = 0.0
            self.vr = 0.0
            self.x = 0.0
            self.y = 0.0
            self.theta = 0.0
            self.odometer = 0.0
            self.dist_cm = self.obstacle_cm
            self.gate_trips = 0
            self.timeouts = 0

    def start(self) -> "VirtualRover":
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="virtual-rover", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def __enter__(self) -> "VirtualRover":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    # -- physics -----------------------------------------------------------
    def _run(self) -> None:
        last = time.monotonic()
        while not self._stop.wait(0.02):
            now = time.monotonic()
            dt = min(0.1, now - last)
            last = now
            with self.lock:
                self._tick(dt)

    def _target_wheel_speeds(self) -> tuple[float, float]:
        if self.state != "GO":
            return 0.0, 0.0
        mag = MAX_SPEED_MM_S * (clamp_speed(self.speed) - 60) / (255 - 60)
        return {
            "F": (mag, mag),
            "B": (-mag, -mag),
            "L": (-mag, mag),
            "R": (mag, -mag),
        }.get(self.cmd, (0.0, 0.0))

    def _tick(self, dt: float) -> None:
        age_ms = (time.monotonic() - self.last_cmd_at) * 1000.0
        if self.state in ("GO", "BLOCKED") and age_ms > WATCHDOG_MS:
            self.state = "TIMEOUT"
            self.cmd = "S"
            self.timeouts += 1

        self.battery_mv -= DRAIN_MV_PER_S * dt
        if self.battery_mv < BATTERY_LOW_MV and not self.estop:
            self.fault = "BATTLOW"
            if self.state != "FAULT":
                self.state = "FAULT"
                self.cmd = "S"

        if self.state == "GO" and self.cmd == "F" and self.dist_cm < required_gate_cm(self.speed):
            self.state = "BLOCKED"
            self.cmd = "S"
            self.gate_trips += 1

        tl, tr = self._target_wheel_speeds()
        lag = min(1.0, dt * 8.0)
        self.vl += (tl - self.vl) * lag
        self.vr += (tr - self.vr) * lag
        if self.state != "GO" and abs(self.vl) < 3 and abs(self.vr) < 3:
            self.vl = self.vr = 0.0

        dcenter = (self.vl + self.vr) * 0.5 * dt
        self.x += dcenter * math.cos(self.theta)
        self.y += dcenter * math.sin(self.theta)
        self.theta += (self.vr - self.vl) / TRACK_MM * dt
        self.odometer += (abs(self.vl) + abs(self.vr)) * 0.5 * dt
        self.dist_cm = max(2.0, min(400.0, self.dist_cm - dcenter / 10.0))

    # -- commands ----------------------------------------------------------
    def command(self, raw: str) -> tuple[int, dict]:
        try:
            packet = parse_command(raw)
        except ProtocolError as exc:
            with self.lock:
                self.rejected += 1
            return 400, {"ok": False, "error": str(exc)}

        with self.lock:
            self.forwarded += 1
            self.last_cmd_at = time.monotonic()
            self.last_cmd_text = raw
            if packet.cmd == "S":
                self.state = "STOP"
                self.cmd = "S"
                self.vl = self.vr = 0.0
                if self.fault == "STALL":
                    self.fault = "NONE"
            elif self.estop:
                self.fault = "ESTOP"
                self.state = "FAULT"
                self.cmd = "S"
            elif self.battery_mv < BATTERY_LOW_MV:
                self.fault = "BATTLOW"
                self.state = "FAULT"
                self.cmd = "S"
            else:
                if packet.speed is not None:
                    self.speed = clamp_speed(packet.speed)
                self.cmd = packet.cmd
                self.state = "GO"
                if packet.cmd == "F" and self.dist_cm < required_gate_cm(self.speed):
                    self.state = "BLOCKED"
                    self.cmd = "S"
                    self.gate_trips += 1
            return 200, {"ok": True, "cmd": packet.cmd, "speed": 0 if packet.is_stop else self.speed}

    def set_estop(self, engaged: bool) -> None:
        with self.lock:
            self.estop = engaged
            if engaged:
                self.fault = "ESTOP"
                self.state = "FAULT"
                self.cmd = "S"
                self.vl = self.vr = 0.0
            elif self.fault == "ESTOP":
                self.fault = "NONE"
                self.state = "STOP"

    # -- reporting ---------------------------------------------------------
    def status(self) -> dict:
        with self.lock:
            age_ms = int((time.monotonic() - self.last_cmd_at) * 1000.0)
            return {
                "fw": "sim-1.3.0",
                "uptime_ms": int((time.monotonic() - self.started) * 1000),
                "ssid": "AI_Rover_Sim",
                "ip": "127.0.0.1",
                "clients": 1,
                "forwarded": self.forwarded,
                "rejected": self.rejected,
                "last_cmd": self.last_cmd_text,
                "last_cmd_age_ms": age_ms,
                "camera": self.camera,
                "free_heap": 200000,
                "uno": {
                    "alive": True,
                    "wired": True,
                    "hz": 1000.0,
                    "fault_pin": self.fault != "NONE",
                    "has_telemetry": True,
                    "telemetry_age_ms": age_ms,
                    "state": self.state,
                    "fault": self.fault,
                    "cmd": self.cmd,
                    "pwm": 0 if self.state != "GO" else self.speed,
                    "dist_cm": int(self.dist_cm),
                    "battery_mv": int(self.battery_mv),
                    "crc_failures": 0,
                    "overflows": 0,
                    "speed_l_mm_s": int(self.vl),
                    "speed_r_mm_s": int(self.vr),
                    "odo_x_mm": int(self.x),
                    "odo_y_mm": int(self.y),
                    "odo_theta_deg": int(math.degrees(self.theta)),
                    "odometer_mm": int(self.odometer),
                },
            }


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def make_server(rover: VirtualRover, port: int = 0) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        server_version = "AIRoverSim/1.3"

        def log_message(self, *args) -> None:  # keep pytest output clean
            pass

        def _json(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query, keep_blank_values=True)
            route = parsed.path

            if route == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"ok")
                return
            if route == "/status":
                self._json(200, rover.status())
                return
            if route == "/cmd":
                if "c" not in query:
                    with rover.lock:
                        rover.rejected += 1
                    self._json(400, {"ok": False, "error": "missing c"})
                    return
                code, payload = rover.command(query["c"][0])
                self._json(code, payload)
                return
            if route == "/cam":
                if "u" in query:
                    rover.camera = query["u"][0]
                    self._json(200, {"ok": True, "camera": rover.camera})
                else:
                    self._json(200, {"ok": True, "camera": rover.camera})
                return

            # --- simulation-only controls --------------------------------
            if route == "/sim/obstacle":
                try:
                    cm = float(query.get("cm", ["200"])[0])
                except ValueError:
                    self._json(400, {"ok": False, "error": "cm must be numeric"})
                    return
                with rover.lock:
                    rover.dist_cm = max(2.0, min(400.0, cm))
                self._json(200, {"ok": True, "obstacle_cm": rover.dist_cm})
                return
            if route == "/sim/estop":
                on = query.get("on", ["1"])[0].lower() in ("1", "true", "on", "yes")
                rover.set_estop(on)
                self._json(200, {"ok": True, "estop": on})
                return
            if route == "/sim/reset":
                rover.reset()
                self._json(200, {"ok": True})
                return
            if route == "/":
                page = (
                    "<!doctype html><meta charset=utf-8><title>AI Rover Sim</title>"
                    "<body style='background:#070b12;color:#22d3ee;font-family:monospace;padding:2rem'>"
                    "<h1>AI Rover simulator</h1><pre id=s>loading...</pre>"
                    "<script>setInterval(async()=>{const r=await fetch('/status');"
                    "document.getElementById('s').textContent=JSON.stringify(await r.json(),null,2)},500)</script>"
                )
                body = page.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self._json(404, {"ok": False, "error": "not found"})

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    return httpd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Virtual AI Rover")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--obstacle", type=float, default=200.0, help="initial distance ahead (cm)")
    args = parser.parse_args(argv)

    rover = VirtualRover(args.obstacle).start()
    httpd = make_server(rover, args.port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(f"[SIM] virtual rover on http://127.0.0.1:{httpd.server_port}")
    print("[SIM] /sim/obstacle?cm=30  /sim/estop?on=1  /sim/reset")
    print("[SIM] Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        rover.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
