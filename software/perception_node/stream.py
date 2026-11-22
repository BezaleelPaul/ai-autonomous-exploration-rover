"""IP Webcam (smartphone) stream ingestion with URL validation.

HTTP(S) MJPEG sources go through :class:`MjpegReader` — a pure-Python client
that keeps only the newest frame. OpenCV's FFmpeg backend buffers several
frames before handing them over, which shows up as seconds of lag on the
dashboard; this reader has no queue at all (latest-wins). RTSP and other
non-HTTP sources still use :class:`software.camera.esp32_stream.ESP32Stream`.
URL validation stays phone-specific: ``http://<PHONE_IP>:8080/video``.
"""

from __future__ import annotations

import threading
import time
import urllib.request
from urllib.parse import urlparse, urlunparse

from software.camera.esp32_stream import ESP32Stream

DEFAULT_PORT = 8080
IP_WEBCAM_STREAM_PATH = "/video"
MAX_JPEG_BYTES = 8_000_000  # refuse to buffer more than 8 MB of one frame


def validate_stream_url(url: str) -> str:
    """Accept an http(s) IP Webcam / RTSP-style URL, reject obvious garbage.

    A bare origin (``http://192.168.1.50:8080``) is what the Android IP Webcam
    app prints on its start screen, so it is completed to the MJPEG path
    ``/video`` instead of being refused; ``/videofeed`` (the app's other alias)
    and any other explicit path pass through untouched. Bare hostnames or IPs
    without scheme (``192.168.1.50:8080`` or ``192.168.1.50``) are completed
    with ``http://`` and the default ``:8080/video`` path.
    """
    raw = (url or "").strip()
    if not raw:
        raise ValueError("stream_url is empty (expected http://<PHONE_IP>:8080/video)")
    if "://" not in raw:
        if ":" in raw:
            raw = f"http://{raw}"
        else:
            raw = f"http://{raw}:{DEFAULT_PORT}/video"
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https", "rtsp"):
        raise ValueError(
            f"stream_url scheme must be http, https or rtsp, got {parsed.scheme!r}"
        )
    if not parsed.hostname:
        raise ValueError(
            "stream_url has no host (expected http://<PHONE_IP>:8080/video)"
        )
    if parsed.port is not None and not (0 < parsed.port < 65536):
        raise ValueError(f"stream_url port {parsed.port} is out of range")
    if parsed.scheme in ("http", "https") and parsed.path in ("", "/"):
        return urlunparse(parsed._replace(path=IP_WEBCAM_STREAM_PATH))
    return raw


class MjpegParser:
    """Incremental SOI/EOI scanner: newest complete JPEG wins, no queue.

    Boundary-agnostic on purpose — IP Webcam's multipart framing varies by
    firmware, but every frame is still a ``FF D8 ... FF D9`` pair.
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self.frame: bytes | None = None
        self.frames = 0

    def feed(self, chunk: bytes) -> None:
        self._buf.extend(chunk)
        while True:
            soi = self._buf.find(b"\xff\xd8")
            if soi < 0:
                if len(self._buf) > 2:
                    del self._buf[:-2]  # keep 2 bytes: SOI may straddle chunks
                return
            eoi = self._buf.find(b"\xff\xd9", soi + 2)
            if eoi < 0:
                if soi:
                    del self._buf[:soi]
                if len(self._buf) > MAX_JPEG_BYTES:
                    del self._buf[:-2]
                return
            self.frame = bytes(self._buf[soi : eoi + 2])
            self.frames += 1
            del self._buf[: eoi + 2]


class MjpegReader:
    """HTTP MJPEG client with zero frame buffering (latest-wins).

    Duck-types the parts of ESP32Stream LiveFeed uses: ``open``/``read``/
    ``close``/``healthy``. ``read`` decodes only the newest JPEG — the phone
    can stream at 30 fps while the laptop analysis runs slower; we never fall
    behind by more than one frame.
    """

    def __init__(
        self,
        url: str,
        *,
        open_timeout_s: float = 5.0,
        reconnect_timeout_s: float = 2.0,
        frozen_timeout_s: float = 3.0,
        read_chunk: int = 65536,
    ) -> None:
        self.url = url
        self.open_timeout_s = float(open_timeout_s)
        self.reconnect_timeout_s = float(reconnect_timeout_s)
        self.frozen_timeout_s = float(frozen_timeout_s)
        self.read_chunk = int(read_chunk)
        self.parser = MjpegParser()
        self.healthy = False
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_frame_time = 0.0
        self._decoded_id = -1
        self._decoded = None
        self._last_open_attempt = 0.0
        self._open_failed = False
        self.failures = 0

    def open(self) -> bool:
        now = time.time()
        if self._open_failed and (now - self._last_open_attempt) < max(
            0.0, self.reconnect_timeout_s
        ):
            self.healthy = False
            return False
        self._last_open_attempt = now
        if self._thread is None or not self._thread.is_alive():
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        # first bytes decide health; give the reader a moment
        deadline = time.time() + min(self.open_timeout_s, 2.0)
        while time.time() < deadline:
            if self.parser.frames:
                self.healthy = True
                return True
            if not self._running:
                break
            time.sleep(0.05)
        self._open_failed = self.parser.frames == 0
        self.healthy = bool(self.parser.frames)
        return self.healthy

    def _loop(self) -> None:
        while self._running:
            try:
                req = urllib.request.Request(
                    self.url, headers={"User-Agent": "mwe-rover/1.0"}
                )
                with urllib.request.urlopen(req, timeout=self.open_timeout_s) as resp:
                    self._open_failed = False
                    while self._running:
                        chunk = resp.read(self.read_chunk)
                        if not chunk:
                            break
                        self.parser.feed(chunk)
                        self._last_frame_time = time.time()
                        self.healthy = True
            except Exception:
                self.failures += 1
                self.healthy = False
            if not self._running:
                break
            time.sleep(self.reconnect_timeout_s)

    def read(self):
        """Decode the newest frame once; None when stale or absent."""
        if not self.parser.frames:
            return None
        if (time.time() - self._last_frame_time) > self.frozen_timeout_s:
            self.healthy = False
            return None
        if self._decoded_id == self.parser.frames:
            return self._decoded
        try:
            import cv2
            import numpy as np

            buf = np.frombuffer(self.parser.frame, dtype=np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        except Exception:
            self.failures += 1
            return None
        if img is None:
            self.failures += 1
            return None
        self._decoded_id = self.parser.frames
        self._decoded = img
        return img

    def close(self) -> None:
        self._running = False
        self.healthy = False

    def is_healthy(self) -> bool:
        return self.healthy


def open_ip_webcam(
    url: str,
    *,
    mock: bool = False,
    reconnect_timeout_s: float = 5.0,
    frozen_timeout_s: float = 3.0,
    jpeg_timeout_s: float | None = 2.0,
    open_timeout_s: float = 5.0,
    fps_target: float | None = None,
):
    """Validate the URL and build a ready-to-``open()`` stream client.

    HTTP(S) MJPEG (the phone) gets the zero-buffer MjpegReader; RTSP and mock
    keep the ESP32Stream client. ``fps_target``/``jpeg_timeout_s`` only apply
    to the ESP32Stream path.
    """
    checked = url if mock else validate_stream_url(url)
    if not mock and checked.startswith(("http://", "https://")):
        return MjpegReader(
            checked,
            open_timeout_s=open_timeout_s,
            reconnect_timeout_s=min(reconnect_timeout_s, 2.0),
            frozen_timeout_s=frozen_timeout_s,
        )
    return ESP32Stream(
        checked,
        reconnect_timeout_s=reconnect_timeout_s,
        frozen_timeout_s=frozen_timeout_s,
        mock=mock,
        fps_target=fps_target,
        jpeg_timeout_s=jpeg_timeout_s,
        open_timeout_s=open_timeout_s,
    )


def suggested_url(phone_ip: str, port: int = DEFAULT_PORT) -> str:
    """Build the canonical IP Webcam URL for a phone IP."""
    host = (phone_ip or "").strip()
    if not host:
        raise ValueError("phone_ip is empty")
    if "://" in host:
        return validate_stream_url(host)
    return validate_stream_url(f"http://{host}:{int(port)}/video")
