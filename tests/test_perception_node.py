"""Perception node: zone geometry, area policy, serial transport, HUD, loop."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from software.ai.detection import Detection
from software.ai.detector import BaseDetector, MockDetector
from software.perception_node import bench as perception_bench
from software.perception_node import cli as perception_cli
from software.perception_node import http_link as http_link_module
from software.perception_node.http_link import HttpLink
from software.perception_node.hud import draw_hud
from software.perception_node.node import (
    NodeState,
    PerceptionNode,
    build_detector,
    policy_from_config,
)
from software.perception_node.serial_link import (
    SerialLink,
    detect_bluetooth_port,
    resolve_serial_port,
)
from software.perception_node.stream import suggested_url, validate_stream_url
from software.perception_node.zones import (
    FORWARD,
    STOP,
    TURN_LEFT,
    TURN_RIGHT,
    SteeringPolicy,
    Zone,
    best_target,
    classify_zone,
)
from software.utils.config_loader import load_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_config(str(ROOT / "config" / "config.yaml"))
FRAME_W, FRAME_H = 640, 480


def _det(x1: float, y1: float, x2: float, y2: float, name: str = "person") -> Detection:
    return Detection(name, 0.9, x1, y1, x2, y2, 0.0)


class FakeDetector(BaseDetector):
    def __init__(self, detections: list[Detection]) -> None:
        self.detections = detections
        self.loaded = False

    def load(self) -> bool:
        self.loaded = True
        return True

    def detect(self, frame: np.ndarray | None = None) -> list[Detection]:
        return list(self.detections)


class FakeStream:
    """Minimal stream double: togglable frame source, no network."""

    def __init__(self, frame: np.ndarray | None = None) -> None:
        self.frame = frame
        self.mock = False
        self.url = "http://192.168.1.50:8080/video"
        self.closed = False

    def open(self) -> bool:
        return self.frame is not None

    def read(self) -> np.ndarray | None:
        return self.frame

    def close(self) -> None:
        self.closed = True

    def is_healthy(self) -> bool:
        return self.frame is not None


def _node(
    detections: list[Detection] | None = None,
    *,
    interval: int = 1,
    stream: object | None = None,
) -> PerceptionNode:
    cfg = {
        **CONFIG,
        "perception": {
            **CONFIG["perception"],
            "inference_interval": interval,
            "hud_enabled": False,
        },
    }
    return PerceptionNode(
        cfg,
        detector=FakeDetector(detections or []),
        stream=stream or FakeStream(np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)),
        serial=SerialLink(mock=True),
    )


# ------------------------------------------------------------- zone geometry
def test_classify_zone_splits_into_three_columns():
    assert classify_zone(0.0) is Zone.LEFT
    assert classify_zone(0.32) is Zone.LEFT
    assert classify_zone(0.33) is Zone.CENTER
    assert classify_zone(0.5) is Zone.CENTER
    assert classify_zone(0.6599) is Zone.CENTER
    assert classify_zone(0.66) is Zone.RIGHT
    assert classify_zone(1.0) is Zone.RIGHT


def test_classify_zone_rejects_invalid_input():
    with pytest.raises(ValueError):
        classify_zone(-0.01)
    with pytest.raises(ValueError):
        classify_zone(1.01)
    with pytest.raises(ValueError):
        classify_zone(0.5, left_boundary=0.9, center_boundary=0.2)


def test_zone_stringifies_to_its_value():
    assert f"{Zone.LEFT}" == "LEFT"
    assert str(Zone.RIGHT) == "RIGHT"


# ----------------------------------------------------------- steering policy
def test_policy_without_target_is_stop():
    decision = SteeringPolicy().decide(None, FRAME_W, FRAME_H)
    assert decision.command == STOP
    assert decision.target_present is False
    assert decision.area_ratio == 0.0
    assert "no target" in decision.reason


def test_policy_steers_by_zone():
    policy = SteeringPolicy()
    left = policy.decide(_det(30, 180, 130, 300), FRAME_W, FRAME_H)
    center = policy.decide(_det(270, 180, 370, 300), FRAME_W, FRAME_H)
    right = policy.decide(_det(510, 180, 610, 300), FRAME_W, FRAME_H)
    assert (left.command, center.command, right.command) == (
        TURN_LEFT,
        FORWARD,
        TURN_RIGHT,
    )
    assert (left.zone, center.zone, right.zone) == (Zone.LEFT, Zone.CENTER, Zone.RIGHT)
    assert left.area_ratio < SteeringPolicy().stop_area_ratio


def test_policy_stops_on_close_target_even_in_a_side_zone():
    decision = SteeringPolicy().decide(_det(0, 0, 500, 300), FRAME_W, FRAME_H)
    assert decision.command == STOP
    assert decision.target_present is True
    assert decision.area_ratio >= SteeringPolicy().stop_area_ratio
    assert "too close" in decision.reason


def test_area_ratio_is_bbox_over_frame():
    ratio = SteeringPolicy.area_ratio(_det(0, 0, 320, 160), FRAME_W, FRAME_H)
    assert ratio == pytest.approx((320 * 160) / (FRAME_W * FRAME_H))


def test_area_ratio_rejects_zero_frame():
    with pytest.raises(ValueError):
        SteeringPolicy.area_ratio(_det(0, 0, 10, 10), 0, 480)


def test_policy_constructor_validates_thresholds():
    with pytest.raises(ValueError):
        SteeringPolicy(stop_area_ratio=0.0)
    with pytest.raises(ValueError):
        SteeringPolicy(stop_area_ratio=1.5)


def test_policy_from_config_reads_perception_section():
    policy = policy_from_config(
        {
            "perception": {
                "left_boundary": 0.4,
                "center_boundary": 0.6,
                "stop_area_ratio": 0.5,
            }
        }
    )
    assert policy.left_boundary == 0.4
    assert policy.center_boundary == 0.6
    assert policy.stop_area_ratio == 0.5


def test_policy_from_config_falls_back_to_navigation():
    policy = policy_from_config(
        {"navigation": {"left_boundary": 0.25, "center_boundary": 0.75}}
    )
    assert policy.left_boundary == 0.25
    assert policy.center_boundary == 0.75
    assert policy.stop_area_ratio == 0.35


def test_best_target_returns_highest_confidence():
    low = Detection("person", 0.4, 0, 0, 10, 10)
    high = Detection("person", 0.95, 0, 0, 10, 10)
    assert best_target([low, high]) is high
    assert best_target([]) is None


# -------------------------------------------------------------------- stream
def test_validate_stream_url_accepts_ip_webcam():
    url = "http://192.168.1.50:8080/video"
    assert validate_stream_url(url) == url
    assert (
        validate_stream_url("  http://10.0.0.4:8080/video ")
        == "http://10.0.0.4:8080/video"
    )


def test_validate_stream_url_completes_the_bare_origin_the_app_prints():
    """IP Webcam's start screen shows only http://<ip>:8080 - complete it."""
    assert (
        validate_stream_url("http://192.168.1.50:8080")
        == "http://192.168.1.50:8080/video"
    )
    assert (
        validate_stream_url("http://192.168.1.50:8080/")
        == "http://192.168.1.50:8080/video"
    )
    assert (
        validate_stream_url("  http://10.0.0.4:9000 ") == "http://10.0.0.4:9000/video"
    )


def test_validate_stream_url_keeps_the_videofeed_alias_untouched():
    url = "http://192.168.1.50:8080/videofeed"
    assert validate_stream_url(url) == url


@pytest.mark.parametrize(
    "bad",
    ["", "192.168.1.5:8080/video", "ftp://host/video", "http://"],
)
def test_validate_stream_url_rejects_bad_input(bad: str):
    with pytest.raises(ValueError):
        validate_stream_url(bad)


def test_suggested_url_builds_canonical_form():
    assert suggested_url("192.168.1.9") == "http://192.168.1.9:8080/video"
    assert suggested_url("192.168.1.9", 9000) == "http://192.168.1.9:9000/video"


# -------------------------------------------------------------- serial link
def test_resolve_serial_port_prefers_explicit_port(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "software.perception_node.serial_link.detect_board_port", lambda: "COM3"
    )
    monkeypatch.setattr(
        "software.perception_node.serial_link.detect_bluetooth_port", lambda: "COM9"
    )
    assert resolve_serial_port("auto", "COM5") == "COM5"
    assert resolve_serial_port("usb") == "COM3"
    assert resolve_serial_port("bluetooth") == "COM9"
    assert resolve_serial_port("auto") == "COM3"


def test_resolve_serial_port_falls_back_to_bluetooth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "software.perception_node.serial_link.detect_board_port", lambda: None
    )
    monkeypatch.setattr(
        "software.perception_node.serial_link.detect_bluetooth_port", lambda: "COM9"
    )
    assert resolve_serial_port("auto") == "COM9"


def test_resolve_serial_port_rejects_unknown_mode():
    with pytest.raises(ValueError):
        resolve_serial_port("wifi")


class _FakePort:
    def __init__(self, device: str, description: str, hwid: str = "0") -> None:
        self.device = device
        self.description = description
        self.hwid = hwid


def test_detect_bluetooth_port_matches_spp_description(monkeypatch: pytest.MonkeyPatch):
    ports = [
        _FakePort("COM3", "USB-SERIAL CH340 (COM3)"),
        _FakePort("COM7", "Standard Serial over Bluetooth link (COM7)"),
    ]
    monkeypatch.setattr("software.perception_node.serial_link._comports", lambda: ports)
    assert detect_bluetooth_port() == "COM7"


def test_detect_bluetooth_port_none_when_absent(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "software.perception_node.serial_link._comports",
        lambda: [_FakePort("COM3", "USB-SERIAL CH340 (COM3)")],
    )
    assert detect_bluetooth_port() is None


def test_serial_link_mock_send_validates_and_stops_on_close():
    link = SerialLink(mock=True)
    assert link.connect() is True
    assert link.send(FORWARD) is True
    assert link.send("  r  ") is True  # whitespace + case are normalised
    with pytest.raises(ValueError):
        link.send("Z")
    link.close()
    assert link.sent == ["F", "R", "S"]
    assert link.last_sent == "S"


def test_serial_link_rejects_bad_construction():
    with pytest.raises(ValueError):
        SerialLink(mode="wifi")
    with pytest.raises(ValueError):
        SerialLink(baud_rate=0)
    with pytest.raises(ValueError):
        SerialLink(reconnect_attempts=0)


def test_serial_link_reports_failure_when_port_cannot_open(
    monkeypatch: pytest.MonkeyPatch,
):
    def boom(port: str, baud_rate: int, timeout_s: float) -> object:
        raise OSError("no such port")

    monkeypatch.setattr("software.perception_node.serial_link._open_serial", boom)
    monkeypatch.setattr(
        "software.perception_node.serial_link.resolve_serial_port",
        lambda mode="auto", preferred=None: "COM9",
    )
    monkeypatch.setattr(
        "software.perception_node.serial_link.time.sleep", lambda _s: None
    )
    link = SerialLink(port="COM9", reconnect_attempts=1, retry_backoff_s=0.0)
    assert link.connect() is False
    assert link.connected is False
    assert link.send(FORWARD) is False


def test_serial_link_write_failure_marks_link_down(monkeypatch: pytest.MonkeyPatch):
    class Handle:
        def write(self, _payload: bytes) -> None:
            raise OSError("device disconnected")

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        "software.perception_node.serial_link._open_serial",
        lambda *_a, **_k: Handle(),
    )
    monkeypatch.setattr(
        "software.perception_node.serial_link.resolve_serial_port",
        lambda mode="auto", preferred=None: "COM9",
    )
    monkeypatch.setattr(
        "software.perception_node.serial_link.time.sleep", lambda _s: None
    )
    link = SerialLink(port="COM9", retry_backoff_s=999.0)
    assert link.connect() is True
    assert link.send(FORWARD) is False
    assert link.connected is False


# ----------------------------------------------------------------------- HUD
def test_hud_returns_annotated_copy():
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    policy = SteeringPolicy()
    decision = policy.decide(_det(270, 180, 370, 300), FRAME_W, FRAME_H)
    out = draw_hud(frame, decision, [_det(270, 180, 370, 300)], fps=5.0)
    assert out.shape == frame.shape
    assert out.dtype == np.uint8
    assert not np.array_equal(out, frame)
    assert np.array_equal(frame, np.zeros_like(frame))


def test_hud_handles_grayscale_frames():
    frame = np.zeros((FRAME_H, FRAME_W), dtype=np.uint8)
    out = draw_hud(frame, SteeringPolicy().decide(None, FRAME_W, FRAME_H))
    assert out.ndim == 3
    assert out.shape[2] == 3


# ---------------------------------------------------------------------- node
def test_node_startup_loads_detector_and_connects_link():
    node = _node([_det(270, 180, 370, 300)])
    assert node.startup() is True
    assert isinstance(node.detector, FakeDetector)
    assert node.detector.loaded is True
    assert node.serial_ok is True
    node.shutdown()
    assert node.serial.last_sent == STOP


def test_node_forwards_target_position_as_commands():
    node = _node([_det(270, 180, 370, 300)])
    node.startup()
    state = node.step(now=100.0)
    assert isinstance(state, NodeState)
    assert state.decision.command == FORWARD
    assert state.sent is True
    assert state.stream_ok is True
    assert state.target_count == 1
    assert node.serial.sent[-1] == FORWARD
    node.shutdown()


def test_node_steers_left_and_right():
    left_node = _node([_det(30, 180, 130, 300)])
    left_node.startup()
    assert left_node.step(now=100.0).decision.command == TURN_LEFT
    left_node.shutdown()

    right_node = _node([_det(510, 180, 610, 300)])
    right_node.startup()
    assert right_node.step(now=100.0).decision.command == TURN_RIGHT
    right_node.shutdown()


def test_node_stops_when_stream_is_lost():
    stream = FakeStream(np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8))
    node = _node([_det(270, 180, 370, 300)], stream=stream)
    node.startup()
    node.step(now=100.0)
    stream.frame = None
    state = node.step(now=200.0)
    assert state.decision.command == STOP
    assert state.stream_ok is False
    assert node.serial.sent[-1] == STOP
    node.shutdown()


def test_node_ignores_detections_that_are_not_the_target():
    node = _node([_det(30, 180, 130, 300, name="bottle")])
    node.startup()
    state = node.step(now=100.0)
    assert state.target_count == 0
    assert state.decision.command == STOP
    node.shutdown()


def test_node_heartbeat_resends_the_active_command():
    node = _node([_det(270, 180, 370, 300)])
    node.startup()
    node.step(now=1000.0)
    sent_before = list(node.serial.sent)
    quiet = node.step(now=1000.5)
    assert quiet.sent is False
    assert node.serial.sent == sent_before
    beat = node.step(now=1001.5)
    assert beat.sent is True
    assert node.serial.sent[-1] == FORWARD
    node.shutdown()


def test_node_emits_stop_immediately_on_first_cycle():
    node = _node([])
    node.startup()
    state = node.step(now=50.0)
    assert state.decision.command == STOP
    assert state.sent is True
    node.shutdown()


def test_node_shutdown_always_sends_stop():
    node = _node([_det(270, 180, 370, 300)])
    node.startup()
    node.step(now=10.0)
    node.shutdown()
    assert node.serial.sent[-1] == STOP
    assert node.serial.connected is False


def test_build_detector_locks_on_to_the_target_class():
    perception = dict(CONFIG["perception"])
    detector = build_detector(perception, "person")
    assert detector.allowed == {"person"}
    assert detector.model_name == "yolov8n.pt"
    mock = build_detector(perception, "bottle", mock=True)
    assert mock.target == "bottle"


def test_node_run_single_cycle_then_stops():
    node = _node([_det(270, 180, 370, 300)])
    node.run(max_cycles=2, loop_period_s=0.0)
    assert node.serial.sent[-1] == STOP


# ----------------------------------------------------------------------- CLI
def test_cli_parser_defaults():
    args = perception_cli.build_arg_parser().parse_args([])
    assert args.config == "config/config.yaml"
    assert args.no_hud is False
    assert args.mock is False
    assert args.mock_camera is False
    assert args.mock_serial is False
    assert args.serial_mode is None


def test_cli_mock_once_smoke():
    code = perception_cli.main(
        [
            "--mock",
            "--once",
            "--no-hud",
            "--config",
            str(ROOT / "config" / "config.yaml"),
            "--target",
            "person",
        ]
    )
    assert code == 0


# -------------------------------------------------- mock split + bench sender
def test_node_splits_mock_camera_and_serial():
    node = PerceptionNode(CONFIG, mock_camera=True, mock_serial=False)
    assert isinstance(node.detector, MockDetector)
    assert node.stream.mock is True
    assert node.serial.mock is False


def test_node_mock_serial_keeps_camera_real():
    node = PerceptionNode(
        CONFIG,
        detector=FakeDetector([]),
        stream=FakeStream(np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)),
        mock_serial=True,
    )
    assert node.serial.mock is True
    assert node.stream.mock is False


class _FakeSerialPort:
    def __init__(self, incoming: list[bytes] | None = None) -> None:
        self.writes: list[bytes] = []
        self.incoming = list(incoming or [])
        self.closed = False

    def write(self, data: bytes) -> int:
        self.writes.append(bytes(data))
        return len(data)

    def flush(self) -> None:
        pass

    def readline(self) -> bytes:
        return self.incoming.pop(0) if self.incoming else b""

    def close(self) -> None:
        self.closed = True


def test_bench_sends_command_then_stop(monkeypatch):
    port = _FakeSerialPort()
    monkeypatch.setattr(perception_bench, "_open_serial", lambda *_: port)
    lines: list[str] = []
    ok = perception_bench.send_command("COM5", "f", on_line=lines.append)
    assert ok is True
    assert port.writes == [b"F", b"S"]
    assert port.closed is True
    assert any("sent F -> COM5" in line for line in lines)


def test_bench_rejects_invalid_command_without_opening(monkeypatch):
    def _boom(*_):
        raise AssertionError("must not open the port")

    monkeypatch.setattr(perception_bench, "_open_serial", _boom)
    assert perception_bench.send_command("COM5", "X") is False


def test_bench_reports_open_failure(monkeypatch):
    def _fail(*_):
        raise OSError("no such port")

    monkeypatch.setattr(perception_bench, "_open_serial", _fail)
    assert perception_bench.send_command("COM7", "S") is False


def test_bench_listen_prints_telemetry(monkeypatch):
    port = _FakeSerialPort([b"DIST:12.5\r\n", b"CMD:F STATE:BLOCKED\r\n"])
    monkeypatch.setattr(perception_bench, "_open_serial", lambda *_: port)
    lines: list[str] = []
    ok = perception_bench.send_command(
        "COM5", "F", listen_s=0.05, interval_s=10.0, on_line=lines.append
    )
    assert ok is True
    assert any("rover: DIST:12.5" in line for line in lines)
    assert any("STATE:BLOCKED" in line for line in lines)
    assert port.writes[-1] == b"S"


def test_bench_sanitizes_bootloader_garbage(monkeypatch):
    port = _FakeSerialPort([b"\xff\x00\x80DIST:9.9\r\n"])
    monkeypatch.setattr(perception_bench, "_open_serial", lambda *_: port)
    lines: list[str] = []
    ok = perception_bench.send_command(
        "COM8", "S", listen_s=0.05, interval_s=10.0, on_line=lines.append
    )
    assert ok is True
    assert any("DIST:9.9" in line for line in lines)


def test_bench_main_exit_codes(monkeypatch):
    port = _FakeSerialPort()
    monkeypatch.setattr(perception_bench, "_open_serial", lambda *_: port)
    assert perception_bench.main(["COM5", "L"]) == 0
    assert perception_bench.main(["COM5", "X"]) == 1


def test_bench_listen_only_transmits_nothing(monkeypatch):
    port = _FakeSerialPort([b"CMD:F STATE:GO\r\n"])
    monkeypatch.setattr(perception_bench, "_open_serial", lambda *_: port)
    lines: list[str] = []
    ok = perception_bench.send_command(
        "COM8", None, listen_s=0.05, on_line=lines.append
    )
    assert ok is True
    assert port.writes == []
    assert any("CMD:F STATE:GO" in line for line in lines)


# ------------------------------------------------------------- HTTP transport
class _FakeResponse:
    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def read(self, _n: int = -1) -> bytes:
        return b"OK"


def test_httplink_mock_send_validates_and_stops_on_close():
    link = HttpLink("http://192.168.4.1", mock=True)
    assert link.connect() is True
    assert link.send("f") is True
    with pytest.raises(ValueError):
        link.send("X")
    link.close()
    assert link.sent == ["F", "S"]
    assert link.connected is False


def test_httplink_rejects_bad_base_url():
    with pytest.raises(ValueError):
        HttpLink("192.168.4.1")
    with pytest.raises(ValueError):
        HttpLink("")


def test_httplink_real_send_hits_cmd_endpoint(monkeypatch):
    calls: list[str] = []

    def fake_urlopen(url: str, timeout: float | None = None):
        calls.append(url)
        return _FakeResponse()

    monkeypatch.setattr(http_link_module.urllib.request, "urlopen", fake_urlopen)
    link = HttpLink("http://192.168.4.1/")
    assert link.connect() is True
    assert link.send("F") is True
    assert calls == ["http://192.168.4.1/status", "http://192.168.4.1/cmd?c=F"]


def test_httplink_send_failure_marks_link_down(monkeypatch):
    def boom(*_args, **_kwargs):
        raise OSError("bridge down")

    monkeypatch.setattr(http_link_module.urllib.request, "urlopen", boom)
    link = HttpLink("http://192.168.4.1")
    assert link.connect() is False
    assert link.send("F") is False
    link.close()
    assert link.connected is False


def test_node_uses_httplink_for_http_mode():
    cfg = {
        **CONFIG,
        "perception": {
            **CONFIG["perception"],
            "serial_mode": "http",
            "rover_url": "http://192.168.4.1",
        },
    }
    node = PerceptionNode(
        cfg,
        detector=FakeDetector([]),
        stream=FakeStream(np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)),
        mock_serial=True,
    )
    assert isinstance(node.serial, HttpLink)
    assert node.serial.mock is True
    assert node.serial.base_url == "http://192.168.4.1"


def test_cli_rover_url_override():
    args = perception_cli.build_arg_parser().parse_args(
        [
            "--config",
            str(ROOT / "config" / "config.yaml"),
            "--serial-mode",
            "http",
            "--rover-url",
            "http://10.0.0.5",
        ]
    )
    assert args.serial_mode == "http"
    cfg = perception_cli._config_with_overrides(args)
    assert cfg["perception"]["serial_mode"] == "http"
    assert cfg["perception"]["rover_url"] == "http://10.0.0.5"
