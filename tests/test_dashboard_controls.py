"""Control deck: USB link semantics + localhost game-style control page."""

from __future__ import annotations

from pathlib import Path

import pytest

from software.dashboard.app import create_control_app
from software.dashboard.controls import (
    MOTION_COMMANDS,
    VALID_COMMANDS,
    ArduinoLink,
    parse_telemetry_line,
    validate_command,
)

ROOT = Path(__file__).resolve().parents[1]
MOTION_INO = ROOT / "arduino" / "motion_safety" / "motion_safety.ino"


class FakeSerial:
    """Scripted stand-in for pyserial: serves queued lines, then EOFs."""

    def __init__(self, lines: tuple[str, ...] = ()) -> None:
        self.written = bytearray()
        self.closed = False
        self._lines = list(lines)

    def readline(self) -> bytes:
        if self._lines:
            return self._lines.pop(0).encode("ascii")
        raise RuntimeError("eof")

    def write(self, data: bytes) -> int:
        self.written.extend(data)
        return len(data)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class FakeFeed:
    """Minimal LiveFeed stand-in for the MJPEG/state routes."""

    def __init__(self) -> None:
        self.state_calls = 0

    def state(self) -> dict:
        self.state_calls += 1
        return {"backend": "MockDetector", "model": "yolov8n.pt", "objects": 1}

    def jpeg(self) -> bytes:
        return b"\xff\xd8fakeframe\xff\xd9"


# ---- validate_command ----


@pytest.mark.parametrize("cmd", ["F", "B", "L", "R", "S"])
def test_validate_command_accepts_every_firmware_command(cmd: str):
    assert validate_command(cmd) == cmd


@pytest.mark.parametrize("cmd", [" f ", "l", "B", "S"])
def test_validate_command_normalises_case_and_padding(cmd: str):
    assert validate_command(cmd) == cmd.strip().upper()


@pytest.mark.parametrize("cmd", ["", "   ", "X", "FF", "F;", "hello", "F\nB", "STOP"])
def test_validate_command_rejects_malformed_input(cmd: str):
    with pytest.raises(ValueError):
        validate_command(cmd)


def test_dashboard_whitelist_matches_the_arduino_source_of_truth():
    ino = MOTION_INO.read_text(encoding="utf-8")
    assert "validCmd" in ino
    for cmd in VALID_COMMANDS:
        assert f"c == '{cmd}'" in ino, f"{cmd} not accepted by motion_safety"


# ---- parse_telemetry_line ----


def test_parses_a_distance_reading():
    state: dict = {}
    parse_telemetry_line("DIST:57.6", state)
    assert state["distance_cm"] == pytest.approx(57.6)
    assert state["echo_ok"] is True


def test_invalid_echo_yields_no_distance_but_stays_flagged():
    state: dict = {}
    parse_telemetry_line("DIST:-1", state)
    assert state["distance_cm"] is None
    assert state["echo_ok"] is False


def test_non_numeric_distance_is_ignored():
    state: dict = {"distance_cm": 42.0}
    parse_telemetry_line("DIST:abc", state)
    assert state["distance_cm"] == 42.0


def test_parses_combined_command_state_status_line():
    state: dict = {}
    parse_telemetry_line("CMD:S STATE:STOP STATUS:STOP", state)
    assert state["command"] == "S"
    assert state["state"] == "STOP"
    assert state["status"] == "STOP"


def test_parses_go_state_and_ok_status():
    state: dict = {}
    parse_telemetry_line("CMD:F STATE:GO STATUS:OK", state)
    assert state == {"command": "F", "state": "GO", "status": "OK"}


def test_parses_standalone_status_error():
    state: dict = {"status": "OK"}
    parse_telemetry_line("STATUS:ERROR", state)
    assert state["status"] == "ERROR"


def test_obstacle_alert_is_recorded_with_a_timestamp():
    state: dict = {}
    parse_telemetry_line("ALERT:OBSTACLE dist=10.0cm cmd=F", state)
    assert state["alert"].startswith("ALERT:OBSTACLE")
    assert state["alert_at"] > 0


def test_boot_line_parks_status_on_stop():
    state: dict = {"status": "OK"}
    parse_telemetry_line("BOOT:STOP", state)
    assert state["status"] == "STOP"


@pytest.mark.parametrize("line", ["", "   ", "\n"])
def test_blank_lines_are_ignored(line: str):
    state: dict = {"status": "OK"}
    parse_telemetry_line(line, state)
    assert state == {"status": "OK"}


def test_unknown_text_does_not_clobber_known_fields():
    state: dict = {"state": "GO", "command": "F", "status": "OK"}
    parse_telemetry_line("noise from the bootloader", state)
    assert state["state"] == "GO"
    assert state["status"] == "OK"


# ---- ArduinoLink ----


def test_mock_link_records_commands_without_hardware():
    link = ArduinoLink("", mock=True)
    assert link.connect() is True
    assert link.send("F") is True
    snap = link.telemetry()
    assert snap["sent_count"] == 1
    assert snap["active"] == "F"
    assert snap["history"][-1]["cmd"] == "F"
    assert snap["connected"] is True


def test_mock_link_release_sends_stop():
    link = ArduinoLink("", mock=True)
    link.connect()
    link.send("L")
    link.release()
    snap = link.telemetry()
    assert snap["active"] == "S"
    assert [h["cmd"] for h in snap["history"]][-2:] == ["L", "S"]


def test_send_rejects_bad_command_and_records_nothing():
    link = ArduinoLink("", mock=True)
    link.connect()
    with pytest.raises(ValueError):
        link.send("F; drop table")
    assert link.telemetry()["sent_count"] == 0


def test_send_without_a_port_reports_failure():
    link = ArduinoLink("COM99", boot_s=0.0)
    assert link.connected is False
    assert link.send("F") is False


def test_heartbeat_only_resends_motion_commands():
    link = ArduinoLink("", mock=True, heartbeat_s=0.0)
    link.connect()
    link.send("S")
    assert link.pump() is False
    link.send("F")
    assert link.pump() is True


def test_heartbeat_respects_the_interval():
    link = ArduinoLink("", mock=True, heartbeat_s=60.0)
    link.connect()
    link.send("F")
    assert link.pump() is False


def test_read_loop_folds_firmware_telemetry():
    fake = FakeSerial(
        ("DIST:12.5", "CMD:F STATE:GO STATUS:OK", "ALERT:OBSTACLE dist=9.9cm cmd=F")
    )
    link = ArduinoLink("COMX", boot_s=0.0, open_port=lambda p, b: fake)
    assert link.connect() is True
    if link._thread is not None:
        link._thread.join(timeout=2.0)
    snap = link.telemetry()
    assert snap["distance_cm"] == pytest.approx(12.5)
    assert snap["state"] == "GO"
    assert snap["alert"].startswith("ALERT:OBSTACLE")
    link.close()
    assert snap["connected"] is True
    assert link.connected is False


def test_close_releases_the_port():
    fake = FakeSerial()
    link = ArduinoLink("COMX", boot_s=0.0, open_port=lambda p, b: fake)
    link.connect()
    link.close()
    assert fake.closed is True
    assert link.connected is False


def test_open_failure_returns_false_not_an_exception():
    def boom(port: str, baud: int) -> object:
        raise OSError("access denied")

    link = ArduinoLink("COMX", boot_s=0.0, open_port=boom)
    assert link.connect() is False
    assert link.connected is False


def test_telemetry_age_is_unknown_before_any_reading():
    link = ArduinoLink("", mock=True)
    assert link.telemetry()["telemetry_age_s"] == -1.0


def test_telemetry_snapshot_is_a_copy():
    link = ArduinoLink("", mock=True)
    link.connect()
    snap = link.telemetry()
    snap["state"] = "TAMPERED"
    assert link.telemetry()["state"] == "STOP"


# ---- control page ----


def test_page_exposes_every_drive_key():
    from software.dashboard.control_page import CONTROL_PAGE

    for key in ('data-key="w"', 'data-key="a"', 'data-key="s"', 'data-key="d"'):
        assert key in CONTROL_PAGE
    assert "arrowup" in CONTROL_PAGE
    assert "SPACE" in CONTROL_PAGE


def test_page_posts_commands_to_the_api():
    from software.dashboard.control_page import CONTROL_PAGE

    assert 'fetch("/api/cmd"' in CONTROL_PAGE
    assert "keydown" in CONTROL_PAGE
    assert "keyup" in CONTROL_PAGE


def test_page_stops_on_release():
    from software.dashboard.control_page import CONTROL_PAGE

    assert "held.size===0" in CONTROL_PAGE
    assert 'send("S")' in CONTROL_PAGE


def test_motion_commands_are_exposed_for_the_pad():
    assert set(MOTION_COMMANDS) == {"F", "B", "L", "R"}
    assert set(MOTION_COMMANDS) <= set(VALID_COMMANDS)


# ---- flask app ----


@pytest.fixture()
def app_pair():
    link = ArduinoLink("", mock=True)
    link.connect()
    return create_control_app(FakeFeed(), link), link


def test_root_serves_the_control_deck(app_pair):
    app, _link = app_pair
    res = app.test_client().get("/")
    assert res.status_code == 200
    assert b"CONTROL DECK" in res.data
    assert b"/video_feed" in res.data
    assert b"/api/state" in res.data


def test_state_combines_ai_and_firmware(app_pair):
    app, _link = app_pair
    res = app.test_client().get("/api/state")
    body = res.get_json()
    assert res.status_code == 200
    assert body["feed"]["backend"] == "MockDetector"
    assert body["link"]["connected"] is True


def test_post_command_is_sent(app_pair):
    app, link = app_pair
    res = app.test_client().post("/api/cmd", json={"c": "F"})
    assert res.status_code == 200
    assert res.get_json() == {"ok": True, "command": "F"}
    assert link.telemetry()["active"] == "F"


def test_get_command_is_sent(app_pair):
    app, link = app_pair
    res = app.test_client().get("/api/cmd?c=R")
    assert res.status_code == 200
    assert res.get_json()["command"] == "R"
    assert link.telemetry()["active"] == "R"


def test_form_command_is_sent(app_pair):
    app, link = app_pair
    res = app.test_client().post("/api/cmd", data={"c": "B"})
    assert res.status_code == 200
    assert link.telemetry()["active"] == "B"


@pytest.mark.parametrize("bad", ["", "Z", "F; drop", "forward"])
def test_malformed_command_is_rejected_with_400(app_pair, bad: str):
    app, link = app_pair
    res = app.test_client().post("/api/cmd", json={"c": bad})
    assert res.status_code == 400
    assert res.get_json()["ok"] is False
    assert link.telemetry()["sent_count"] == 0


def test_video_feed_route_is_mounted(app_pair):
    app, _link = app_pair
    rules = {str(rule) for rule in app.url_map.iter_rules()}
    assert "/video_feed" in rules
    assert "/api/cmd" in rules


def test_mjpeg_generator_emits_a_frame_part():
    from software.dashboard.app import _mjpeg

    stream = _mjpeg(FakeFeed()).response
    chunk = next(iter(stream))
    assert b"--frame" in chunk
    assert b"Content-Type: image/jpeg" in chunk
    assert b"fakeframe" in chunk
    stream.close()


def test_state_survives_a_broken_feed():
    class BrokenFeed:
        def state(self) -> dict:
            raise RuntimeError("camera unplugged")

        def jpeg(self) -> bytes:
            return None

    link = ArduinoLink("", mock=True)
    link.connect()
    app = create_control_app(BrokenFeed(), link)
    body = app.test_client().get("/api/state").get_json()
    assert "camera unplugged" in body["feed"]["error"]
    assert body["link"]["connected"] is True


def test_video_feed_is_optional_when_there_is_no_camera():
    link = ArduinoLink("", mock=True)
    link.connect()
    app = create_control_app(None, link)
    assert app.test_client().get("/video_feed").status_code == 503
    assert app.test_client().get("/").status_code == 200


# ---- feed source selection (IP Webcam) ----


@pytest.fixture()
def cfg() -> dict:
    from software.utils.config_loader import load_config

    return load_config(str(ROOT / "config" / "config.yaml"))


def test_source_defaults_to_the_local_webcam(cfg: dict):
    from software.dashboard.live import resolve_source

    assert resolve_source(cfg) == "cam"


def test_mock_and_esp32_flags_beat_the_stream_url(cfg: dict):
    from software.dashboard.live import resolve_source

    assert (
        resolve_source(cfg, mock=True, ip_webcam="http://1.2.3.4:8080/video") == "mock"
    )
    assert resolve_source(cfg, esp32=True) == "esp32"


def test_ip_webcam_flag_without_a_url_falls_back_to_config(cfg: dict):
    from software.dashboard.live import resolve_source

    expected = cfg["perception"]["stream_url"]
    assert resolve_source(cfg, ip_webcam="") == expected


def test_ip_webcam_flag_accepts_an_explicit_url(cfg: dict):
    from software.dashboard.live import resolve_source

    url = "http://10.0.0.7:8080/video"
    assert resolve_source(cfg, ip_webcam=url) == url


@pytest.mark.parametrize("bad", ["not a url", "ftp://x/video", "192.168.1.50:8080"])
def test_ip_webcam_flag_rejects_an_unusable_url(cfg: dict, bad: str):
    from software.dashboard.live import resolve_source

    with pytest.raises(ValueError):
        resolve_source(cfg, ip_webcam=bad)


def test_network_source_builds_the_ip_webcam_client(monkeypatch):
    import numpy as np

    from software.ai import detector as detector_mod
    from software.dashboard import live as live_mod
    from software.perception_node import stream as stream_mod
    from software.utils.config_loader import load_config

    seen: dict = {}

    class DummyDetector:
        model_name = "yolov8n.pt"

        def detect(self, frame):
            return []

    class FakeStream:
        def open(self) -> None:
            seen["opened"] = True

        def read(self):
            return np.zeros((48, 64, 3), dtype=np.uint8)

    def fake_open(url, mock=False):
        seen["url"] = url
        return FakeStream()

    monkeypatch.setattr(detector_mod, "create_detector", lambda c: DummyDetector())
    monkeypatch.setattr(stream_mod, "open_ip_webcam", fake_open)

    cfg = load_config(str(ROOT / "config" / "config.yaml"))
    feed = live_mod.LiveFeed(cfg, source="http://192.168.1.50:8080/video")
    feed.start()
    try:
        assert seen.get("opened") is True
        assert seen["url"].startswith("http://")
        assert feed._net is not None
        assert feed._grab() is not None
    finally:
        feed.stop()
