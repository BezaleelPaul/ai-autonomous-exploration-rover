"""ESP32-CAM MJPEG client with reconnect + frozen-frame detection."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np


@dataclass
class FrameStats:
    fps: float = 0.0
    target_fps: float = 0.0
    last_frame_time: float = 0.0
    frames: int = 0
    failures: int = 0


class ESP32Stream:
    def __init__(
        self,
        url: str,
        reconnect_timeout_s: float = 5.0,
        frozen_timeout_s: float = 3.0,
        mock: bool = False,
        fps_target: float | None = None,
        jpeg_timeout_s: float | None = None,
        open_timeout_s: float = 5.0,
    ):
        self.url = url
        self.reconnect_timeout_s = reconnect_timeout_s
        self.frozen_timeout_s = frozen_timeout_s
        self.mock = mock
        self.jpeg_timeout_s = jpeg_timeout_s
        self.open_timeout_s = open_timeout_s
        self.cap = None
        self.stats = FrameStats(target_fps=float(fps_target or 0.0))
        self._last_good: np.ndarray | None = None
        self._last_good_time = 0.0
        self._t0 = time.time()
        self.healthy = bool(mock)
        self._open_failed = False
        self._last_open_attempt = 0.0

    def _connect(self, cv2):
        """Open the capture, bounded so a dead camera fails in seconds.

        Without CAP_PROP_OPEN_TIMEOUT_MSEC the FFmpeg backend retries the TCP
        connect for ~90 s (measured: 93.5 s to report "is the ESP32-CAM on?").
        """
        timeout_ms = max(1, int(float(self.open_timeout_s) * 1000))
        backend = getattr(cv2, "CAP_FFMPEG", None)
        prop = getattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC", None)
        if backend is not None and prop is not None:
            try:
                return cv2.VideoCapture(self.url, backend, [prop, timeout_ms])
            except TypeError:
                pass  # build predates the (url, backend, params) overload
        return cv2.VideoCapture(self.url)

    def open(self) -> bool:
        if self.mock:
            self.healthy = True
            return True
        now = time.time()
        # Honour reconnect_timeout_s as a backoff: a dead camera must not be
        # re-contacted on every read (previously each read paid the full
        # connect timeout, so 20 failed reads cost minutes).
        if self._open_failed and (now - self._last_open_attempt) < max(
            0.0, float(self.reconnect_timeout_s)
        ):
            self.healthy = False
            return False
        self._last_open_attempt = now
        try:
            import cv2

            self.cap = self._connect(cv2)
            if self.jpeg_timeout_s:
                timeout_ms = int(self.jpeg_timeout_s * 1000)
                prop = getattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC", None)
                if prop is not None:
                    self.cap.set(prop, timeout_ms)
            ok = self.cap.isOpened()
            self._open_failed = not ok
            self.healthy = bool(ok)
            return bool(ok)
        except Exception:
            self._open_failed = True
            self.healthy = False
            return False

    def close(self) -> None:
        try:
            if self.cap is not None:
                self.cap.release()
        except Exception:
            pass
        self.healthy = False

    def _mock_frame(self) -> np.ndarray:
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # moving bar so frozen detection can be tested
        x = int((time.time() * 60) % 600)
        img[200:280, max(0, x - 40) : min(640, x + 40)] = (0, 255, 0)
        return img

    def read(self) -> np.ndarray | None:
        now = time.time()
        if self.mock:
            f = self._mock_frame()
            self._update_stats(now)
            self._last_good = f
            self._last_good_time = now
            self.healthy = True
            return f
        try:
            import cv2  # noqa

            if self.cap is None or not self.cap.isOpened():
                self.open()
            if self.cap is None or not self.cap.isOpened():
                self.stats.failures += 1
                self.healthy = False
                return self._last_good if not self._is_frozen(now) else None
            ok, frame = self.cap.read()
            if not ok or frame is None:
                self.stats.failures += 1
                self.healthy = False
                self.open()
                return self._last_good if not self._is_frozen(now) else None
            self._update_stats(now)
            self._last_good = frame
            self._last_good_time = now
            self.healthy = True
            return frame
        except Exception:
            self.stats.failures += 1
            self.healthy = False
            return None

    def _update_stats(self, now: float) -> None:
        self.stats.frames += 1
        dt = now - self._t0
        if dt >= 2.0:
            self.stats.fps = self.stats.frames / dt
            self.stats.frames = 0
            self._t0 = now
        self.stats.last_frame_time = now

    def _is_frozen(self, now: float) -> bool:
        return (now - self._last_good_time) > self.frozen_timeout_s

    def is_healthy(self) -> bool:
        if self.mock:
            return True
        if self._last_good is None:
            return False
        return not self._is_frozen(time.time()) and self.healthy
