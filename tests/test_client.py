"""RoverClient tests against a local fake ESP32 gateway (no hardware)."""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from support import read  # noqa: F401  (ensures sys.path is set up)

from ai_rover import RoverClient
from ai_rover.protocol import ProtocolError


class FakeGateway:
    def __init__(self) -> None:
        self.state = {
            "cmds": [],
            "tokens": [],
            "fail_next": 0,
            "fail_status": False,
            "bad_json": False,
            "camera": "",
        }
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence
                pass

            def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query, keep_blank_values=True)
                state = outer.state

                if parsed.path == "/health":
                    if state["fail_status"]:
                        self._send(500, b"nope")
                    else:
                        self._send(200, b"ok", "text/plain")
                    return

                if parsed.path == "/cmd":
                    if state["fail_status"]:
                        self._send(500, b"{}")
                        return
                    if "c" not in query:
                        self._send(400, b'{"ok":false}')
                        return
                    state["cmds"].append(query["c"][0])
                    state["tokens"].append(query.get("k", [None])[0])
                    if state["fail_next"] > 0:
                        state["fail_next"] -= 1
                        self._send(503, b'{"ok":false}')
                        return
                    self._send(200, b'{"ok":true}')
                    return

                if parsed.path == "/status":
                    if state["fail_status"]:
                        self._send(500, b"{}")
                        return
                    if state["bad_json"]:
                        self._send(200, b"<html>not json</html>", "text/html")
                        return
                    payload = {
                        "fw": "1.1.0",
                        "uptime_ms": 12345,
                        "forwarded": len(state["cmds"]),
                        "rejected": 2,
                        "clients": 1,
                        "last_cmd": "F200\n",
                        "last_cmd_age_ms": 42,
                        "camera": state["camera"],
                        "free_heap": 200000,
                        "uno": {
                            "alive": True,
                            "wired": True,
                            "hz": 1000.0,
                            "fault_pin": False,
                            "has_telemetry": True,
                            "telemetry_age_ms": 45,
                            "state": "GO",
                            "fault": "NONE",
                            "cmd": "F",
                            "pwm": 180,
                            "dist_cm": 42,
                            "battery_mv": 7580,
                            "crc_failures": 0,
                        },
                    }
                    self._send(200, json.dumps(payload).encode())
                    return

                if parsed.path == "/cam":
                    if "u" in query:
                        state["camera"] = query["u"][0]
                        self._send(200, b'{"ok":true}')
                    else:
                        self._send(200, json.dumps({"ok": True, "camera": state["camera"]}).encode())
                    return

                self._send(404, b"{}")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def gateway():
    fake = FakeGateway()
    yield fake
    fake.close()


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------
def test_send_encodes_the_exact_payload(gateway):
    client = RoverClient(gateway.url)
    assert client.send("F", 200) is True
    assert gateway.state["cmds"] == ["F200"]
    assert client.stats.ok == 1
    assert client.stats.last_cmd == "F"


def test_stop_sends_bare_s(gateway):
    client = RoverClient(gateway.url)
    client.send("F", 180)
    assert client.stop() is True
    assert gateway.state["cmds"][-1] == "S"


def test_invalid_command_never_reaches_the_network(gateway):
    client = RoverClient(gateway.url)
    assert client.send("Z", 180) is False
    assert gateway.state["cmds"] == []
    assert client.stats.failed == 1
    assert "invalid command" in client.stats.last_error


def test_strict_mode_raises(gateway):
    client = RoverClient(gateway.url)
    with pytest.raises(ProtocolError):
        client.send("F", 900, strict=True)


def test_http_failure_is_reported(gateway):
    gateway.state["fail_status"] = True
    client = RoverClient(gateway.url)
    assert client.send("F", 180) is False
    assert client.stats.failed == 1
    assert "HTTP 500" in client.stats.last_error


def test_unreachable_gateway_fails_soft():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    client = RoverClient(f"http://127.0.0.1:{port}", timeout=0.2)
    assert client.send("S") is False
    assert client.status() is None
    assert client.health() is False
    assert client.stats.last_error


def test_rate_limit_waits_between_motion_commands(gateway):
    clock = FakeClock()
    slept: list[float] = []
    client = RoverClient(gateway.url, min_interval=0.2, clock=clock, sleep=slept.append)

    assert client.send("F", 180) is True
    assert slept == []  # first command is never delayed

    clock.now = 0.05
    assert client.send("F", 180) is True
    assert slept and slept[-1] == pytest.approx(0.15)

    slept.clear()
    clock.now = 1.0
    assert client.send("L", 180) is True
    assert slept == []


def test_stop_bypasses_rate_limit(gateway):
    clock = FakeClock()
    slept: list[float] = []
    client = RoverClient(gateway.url, min_interval=1.0, clock=clock, sleep=slept.append)
    client.send("F", 180)
    client.stop()
    assert slept == []


def test_stop_retries_until_success(gateway):
    gateway.state["fail_next"] = 2
    slept: list[float] = []
    client = RoverClient(gateway.url, sleep=slept.append)
    assert client.stop(attempts=3) is True
    assert gateway.state["cmds"] == ["S", "S", "S"]
    assert len(slept) == 2


def test_stop_gives_up_after_attempts(gateway):
    gateway.state["fail_status"] = True
    client = RoverClient(gateway.url)
    assert client.stop(attempts=2) is False
    assert client.stats.failed == 2


def test_latency_is_recorded(gateway):
    clock = FakeClock()
    client = RoverClient(gateway.url, clock=clock)
    clock.now = 0.5
    client.send("F", 180)
    assert client.stats.last_latency_ms >= 0.0


# ---------------------------------------------------------------------------
# Gateway API
# ---------------------------------------------------------------------------
def test_status_parsing(gateway):
    client = RoverClient(gateway.url)
    client.send("F", 200)
    status = client.status()
    assert status is not None
    assert status.fw == "1.1.0"
    assert status.uptime_ms == 12345
    assert status.forwarded == 1
    assert status.rejected == 2
    assert status.clients == 1
    assert status.last_cmd == "F200\n"
    assert status.free_heap == 200000
    assert status.uno_alive is True
    assert status.uno_fault is False
    assert status.rover_state == "GO"
    assert status.battery_v == 7.58
    assert status.telemetry_age_ms == 45


def test_status_returns_none_on_server_error(gateway):
    gateway.state["fail_status"] = True
    assert RoverClient(gateway.url).status() is None


def test_status_returns_none_on_bad_json(gateway):
    gateway.state["bad_json"] = True
    assert RoverClient(gateway.url).status() is None


def test_health(gateway):
    assert RoverClient(gateway.url).health() is True


def test_camera_roundtrip(gateway):
    client = RoverClient(gateway.url)
    url = "http://192.168.4.2:8080/video?x=1"
    assert client.set_camera_url(url) is True
    assert gateway.state["camera"] == url
    assert client.camera_url() == url


def test_camera_url_is_validated(gateway):
    client = RoverClient(gateway.url)
    with pytest.raises(ProtocolError):
        client.set_camera_url("ftp://nope")


def test_context_manager_stops(gateway):
    with RoverClient(gateway.url) as client:
        client.send("F", 180)
    assert gateway.state["cmds"][-1] == "S"


def test_stats_dict_shape(gateway):
    client = RoverClient(gateway.url)
    client.send("F", 180)
    payload = client.stats.as_dict()
    for key in ("sent", "ok", "failed", "skipped", "last_error", "last_latency_ms", "last_cmd"):
        assert key in payload
    assert payload["ok"] == 1


def test_status_without_uno_block_is_safe(gateway):
    gateway.state["bad_json"] = False
    # Simulate an older gateway that does not publish "uno".
    original = gateway.server.RequestHandlerClass.do_GET

    def legacy(handler):
        handler._send(200, b'{"fw":"1.0.0","forwarded":1}')

    gateway.server.RequestHandlerClass.do_GET = legacy
    try:
        status = RoverClient(gateway.url).status()
        assert status is not None
        assert status.uno == {}
        assert status.uno_alive is False
        assert status.battery_v == 0.0
        assert status.telemetry_age_ms == -1
    finally:
        gateway.server.RequestHandlerClass.do_GET = original


def test_api_token_is_sent_on_requests(gateway):
    client = RoverClient(gateway.url, token="s3cret")
    assert client.send("F", 180) is True
    client.status()
    assert gateway.state["tokens"][0] == "s3cret"


def test_api_token_from_environment(gateway, monkeypatch):
    monkeypatch.setenv("ROVER_TOKEN", "env-token")
    client = RoverClient(gateway.url)
    client.send("S")
    assert gateway.state["tokens"][-1] == "env-token"


def test_no_token_means_no_query_parameter(gateway):
    client = RoverClient(gateway.url, token="")
    client.send("S")
    assert gateway.state["tokens"][-1] is None
