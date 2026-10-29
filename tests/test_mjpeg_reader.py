"""Zero-buffer MJPEG client: parser edge cases + a live loopback stream."""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest

from software.perception_node.stream import MjpegParser, MjpegReader, open_ip_webcam


@pytest.fixture(scope="module")
def jpeg_bytes() -> bytes:
    import cv2

    frame = np.full((16, 16, 3), 40, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", frame)
    assert ok
    return bytes(buf)


# ---- parser ---------------------------------------------------------------


def test_parser_extracts_one_jpeg(jpeg_bytes):
    p = MjpegParser()
    p.feed(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n")
    assert p.frame == jpeg_bytes
    assert p.frames == 1


def test_parser_handles_a_jpeg_split_across_chunks(jpeg_bytes):
    p = MjpegParser()
    cut = len(jpeg_bytes) // 2
    p.feed(b"\xff\xd8" + jpeg_bytes[2:cut])
    assert p.frame is None
    p.feed(jpeg_bytes[cut:])
    assert p.frame == jpeg_bytes
    assert p.frames == 1


def test_parser_keeps_only_the_newest_frame(jpeg_bytes):
    p = MjpegParser()
    p.feed(b"\xff\xd8first\xff\xd9")
    p.feed(jpeg_bytes)  # already a complete JPEG: SOI..EOI
    assert p.frame == jpeg_bytes
    assert p.frames == 2


def test_parser_stays_bounded_on_pure_garbage():
    p = MjpegParser()
    for _ in range(20):
        p.feed(b"x" * 100_000)
    assert p.frame is None
    assert len(p._buf) < 200_000


def test_open_ip_webcam_routes_http_to_the_mjpeg_reader():
    client = open_ip_webcam("http://192.168.1.77:8080/video")
    assert isinstance(client, MjpegReader)
    client.close()


def test_open_ip_webcam_keeps_esp32stream_for_rtsp():
    from software.camera.esp32_stream import ESP32Stream

    client = open_ip_webcam("rtsp://192.168.1.77:554/stream")
    assert isinstance(client, ESP32Stream)
    client.close()


# ---- loopback end-to-end --------------------------------------------------


def test_reader_pulls_frames_from_a_live_loopback_stream(jpeg_bytes):
    sent = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=x")
            self.end_headers()
            for _ in range(5):
                try:
                    self.wfile.write(b"--x\r\nContent-Type: image/jpeg\r\n\r\n")
                    self.wfile.write(jpeg_bytes)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                except BrokenPipeError:
                    return
                time.sleep(0.02)
            sent.set()

        def log_message(self, *args):
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    reader = MjpegReader(
        f"http://127.0.0.1:{port}/video", open_timeout_s=3.0, frozen_timeout_s=5.0
    )
    try:
        assert reader.open() is True
        frame = None
        deadline = time.time() + 3.0
        while time.time() < deadline:
            frame = reader.read()
            if frame is not None:
                break
            time.sleep(0.05)
        assert frame is not None
        assert frame.shape == (16, 16, 3)
        assert sent.wait(5.0)
        assert reader.parser.frames >= 1
    finally:
        reader.close()
        server.shutdown()
