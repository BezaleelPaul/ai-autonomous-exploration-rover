"""Regression tests for the ESP32-CAM stream connection path.

Found while exercising ``scripts/collect_camera_dataset.py`` with no camera on
the network: ``cv2.VideoCapture(url)`` blocked for **93.5 s** before the tool
reported "could not open ... (is the ESP32-CAM on?)", because the FFmpeg
backend retries the TCP connect with no open timeout. The second defect is
that ``reconnect_timeout_s`` (read from ``config.yaml`` and passed in by
``RoverApp``) was stored but never honoured, so every failed read paid the
full connect timeout again.

``cv2`` is stubbed here — these are contract tests, not network tests.
"""

from __future__ import annotations

import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from software.camera.esp32_stream import ESP32Stream  # noqa: E402

URL = "http://10.255.255.1/stream"


def fake_cv2(monkeypatch, *, opened: bool = False, params_unsupported: bool = False):
    """Install a stub ``cv2`` and return the list of VideoCapture builds."""
    builds: list[tuple] = []

    class Cap:
        def __init__(self, *args, **kwargs):
            if params_unsupported and len(args) > 1:
                raise TypeError("VideoCapture() takes no keyword arguments")
            builds.append(args)
            self._opened = bool(opened)

        def isOpened(self) -> bool:
            return self._opened

        def set(self, *_args) -> bool:
            return True

        def read(self):
            return False, None

        def release(self) -> None:
            pass

    stub = types.ModuleType("cv2")
    setattr(stub, "CAP_FFMPEG", 1900)
    setattr(stub, "CAP_PROP_OPEN_TIMEOUT_MSEC", 53)
    setattr(stub, "CAP_PROP_READ_TIMEOUT_MSEC", 54)
    setattr(stub, "VideoCapture", Cap)
    monkeypatch.setitem(sys.modules, "cv2", stub)
    return builds


def test_open_passes_connect_timeout_to_the_ffmpeg_backend(monkeypatch):
    builds = fake_cv2(monkeypatch, opened=True)
    stream = ESP32Stream(URL, open_timeout_s=2.5)

    assert stream.open() is True
    assert len(builds) == 1
    url, backend, params = builds[0]
    assert url == URL
    assert backend == 1900, "must select the FFmpeg backend explicitly"
    assert 53 in params and 2500 in params, "CAP_PROP_OPEN_TIMEOUT_MSEC not applied"


def test_falls_back_when_the_capture_overload_is_unsupported(monkeypatch):
    builds = fake_cv2(monkeypatch, opened=True, params_unsupported=True)
    stream = ESP32Stream(URL)

    assert stream.open() is True
    assert len(builds) == 1, "fallback must not leave a second capture open"
    assert len(builds[0]) == 1 and builds[0][0] == URL


def test_failed_open_is_not_retried_inside_the_backoff_window(monkeypatch):
    builds = fake_cv2(monkeypatch, opened=False)
    stream = ESP32Stream(URL, reconnect_timeout_s=60.0)

    assert stream.open() is False
    assert stream.open() is False
    assert stream.open() is False
    assert len(builds) == 1, "camera was re-contacted inside the backoff window"
    assert stream.is_healthy() is False


def test_backoff_expires_and_the_camera_is_recontacted(monkeypatch):
    builds = fake_cv2(monkeypatch, opened=False)
    stream = ESP32Stream(URL, reconnect_timeout_s=0.05)

    assert stream.open() is False
    time.sleep(0.06)
    assert stream.open() is False
    assert len(builds) == 2, "camera was never retried after the backoff expired"


def test_mock_stream_is_unaffected_by_the_connection_path(monkeypatch):
    builds = fake_cv2(monkeypatch, opened=False)  # a mock stream must never touch cv2
    stream = ESP32Stream("mock", mock=True)

    assert stream.open() is True
    frame = stream.read()
    assert frame is not None
    assert frame.shape == (480, 640, 3)
    assert stream.is_healthy() is True
    assert builds == [], "mock stream constructed a real capture"


def test_unreachable_camera_reports_failure_quickly(monkeypatch):
    """End-to-end timing guard for the 93.5 s hang (stubbed, so no network)."""
    builds = fake_cv2(monkeypatch, opened=False)
    stream = ESP32Stream(URL, reconnect_timeout_s=30.0, open_timeout_s=0.5)

    started = time.perf_counter()
    for _ in range(20):  # the collector's default --max-failures
        if not stream.open():
            break
    elapsed = time.perf_counter() - started

    assert len(builds) == 1
    assert elapsed < 5.0, f"failure path took {elapsed:.1f}s; backoff is not working"
