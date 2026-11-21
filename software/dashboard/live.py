"""Live browser GUI backend: smooth webcam video + AI boxes overlaid.

Three threads, so a slow plugin can never freeze video or detection:

* capture  — grabs raw frames at camera FPS;
* inference — enhance + detect on the newest frame whenever free (~0.1 s on
  the iGPU), publishing boxes and handing the frame to the plugin worker;
* plugins  — runs the detection hooks (YOLO-World, monocular depth + world
  model) off the critical path. These take seconds on this CPU-only host, so
  they refresh the advisory world model on their own cadence while video and
  the control loop stay realtime.

The MJPEG stream always shows fresh video with the latest boxes; world-model
labels a plugin adds are merged in at read time.
"""

from __future__ import annotations

import contextlib
import threading
import time
from typing import Any

import numpy as np

from software.autotune.factory import build_realtime, build_tuner

# Sources LiveFeed can pull frames from. Anything that looks like a network URL
# is handed straight to the IP Webcam client (phone MJPEG) instead of OpenCV.
NETWORK_SCHEMES = ("http://", "https://", "rtsp://")


def resolve_source(
    cfg: dict,
    *,
    mock: bool = False,
    esp32: bool = False,
    ip_webcam: str | None = None,
) -> str:
    """Pick the feed source for the dashboard.

    ``ip_webcam`` may be an explicit stream URL or ``""``/``None``-with-flag to
    fall back to ``perception.stream_url``; an unparseable URL raises
    ``ValueError`` so the CLI can report it before opening a camera.
    """
    if mock:
        return "mock"
    if esp32:
        return "esp32"
    if ip_webcam is None:
        return "cam"
    from software.perception_node.stream import validate_stream_url

    url = (ip_webcam or str(cfg["perception"]["stream_url"])).strip()
    return validate_stream_url(url)


class LiveFeed:
    def __init__(self, cfg: dict, source: str = "cam", cam_index: int = 0):
        self.cfg = cfg
        self.source = source
        self.cam_index = cam_index
        self._lock = threading.Lock()
        self._raw: np.ndarray | None = None
        self._pushed: np.ndarray | None = None
        self._pushed_at: float = 0.0
        self._dets: list = []
        self._infer_ms = 0.0
        self._last_infer = 0.0
        self._frames = 0
        self._t0 = time.time()
        self._fps = 0.0
        self._running = False
        self._cap = None
        self._net = None
        self._detector = None
        self._backend = cfg["ai"].get("backend", "mock")
        self._plugins: list = []
        self._plugin_ms: dict[str, float] = {}
        self._plugin_stats: dict = {}
        # Split-timeline plugin state: the inference thread owns the frame
        # pass, the worker thread owns the (slow) detection pass. Read-only
        # consumers see the union of raw detections and plugin-added extras.
        self._frame_ms: dict[str, float] = {}
        self._det_ms: dict[str, float] = {}
        self._extra_dets: list = []
        self._plugin_job: tuple | None = None
        self._plugin_wake = threading.Event()
        self._plugin_thread: threading.Thread | None = None
        plugins_cfg = cfg.get("plugins", {}) or {}
        self._slow_interval_s = float(plugins_cfg.get("slow_interval_s", 2.0))
        # Adaptive inference pacing (software/autotune). The governor owns the
        # interval; this loop only gates on it and hands over its latency.
        self._tuner, autotune_settings = build_tuner(cfg)
        self._rt = build_realtime(
            self._tuner,
            autotune_settings,
            interval=int(cfg["ai"].get("inference_interval", 1) or 1),
        )
        self._infer_interval = self._rt.interval
        self._infer_seq = max(0, self._infer_interval - 1)

    def start(self) -> None:
        from software.ai.detector import create_detector
        from software.plugins import load_plugins

        self._detector = create_detector(self.cfg)
        load = getattr(self._detector, "load", None)
        if callable(load):
            load()
        self._plugins = load_plugins(self.cfg)
        if self.source == "esp32":
            from software.camera.esp32_stream import ESP32Stream

            cam = self.cfg["camera"]
            self._net = ESP32Stream(cam["esp32_url"], mock=False)
            self._net.open()
        elif self.source.startswith(NETWORK_SCHEMES):
            from software.perception_node.stream import open_ip_webcam

            self._net = open_ip_webcam(self.source, mock=False)
            self._net.open()
        elif self.source == "mock":
            pass
        else:
            import cv2

            self._cap = cv2.VideoCapture(self.cam_index)
        self._running = True
        threading.Thread(target=self._capture_loop, daemon=True).start()
        threading.Thread(target=self._infer_loop, daemon=True).start()
        if self._plugins:
            self._plugin_thread = threading.Thread(
                target=self._plugin_loop, daemon=True
            )
            self._plugin_thread.start()

    def stop(self) -> None:
        self._running = False
        self._plugin_wake.set()
        for plugin in self._plugins:
            with contextlib.suppress(Exception):
                plugin.stop()

    def set_source(self, url: str) -> str:
        """Switch to a new network stream at runtime (the phone IP changes).

        Validates first (ValueError on garbage), opens the new client with its
        bounded connect timeout, then swaps it in — the capture thread keeps
        running and picks the new client up on its next grab. The last frame
        is dropped so the dashboard shows NO VIDEO until the new source talks.
        """
        from software.perception_node.stream import open_ip_webcam, validate_stream_url

        validated = validate_stream_url(url)
        new_net = open_ip_webcam(validated, mock=False)
        new_net.open()
        old_net, old_cap = self._net, self._cap
        self._net = new_net
        self._cap = None
        self.source = validated
        with self._lock:
            self._raw = None
            self._pushed = None
            self._dets = []
            self._last_infer = 0.0
        try:
            if old_net is not None:
                old_net.close()
        except Exception:
            pass
        try:
            if old_cap is not None:
                old_cap.release()
        except Exception:
            pass
        return validated

    def note_distance(self, distance_cm: float) -> None:
        """Push the newest ultrasonic reading (cm) into plugins that care
        (scenesense uses it to calibrate monocular depth to metres)."""
        for plugin in self._plugins:
            note = getattr(plugin, "note_distance", None)
            if callable(note):
                with contextlib.suppress(Exception):
                    note(distance_cm)

    def push_frame(self, frame: np.ndarray) -> None:
        """Accept an incoming camera frame pushed over HTTP/WebSocket from a phone companion."""
        if frame is None or getattr(frame, "size", 0) == 0:
            return
        now = time.time()
        with self._lock:
            self._pushed = frame
            self._pushed_at = now
            self._raw = frame
            self._frames += 1
            dt = now - self._t0
            if dt >= 2.0:
                self._fps = self._frames / dt
                self._frames = 0
                self._t0 = now

    # ---- threads ----
    def _grab(self) -> np.ndarray | None:
        if getattr(self, "_pushed", None) is not None:
            # Plan A (Phone Push) is active. Watchdog check: must have arrived within last 3.5 seconds
            if time.time() - getattr(self, "_pushed_at", 0.0) < 3.5:
                return self._pushed
            # Plan A stalled! Clear pushed frame and fail over to underlying stream or mock
            self._pushed = None
        if self.source == "mock":
            f = np.zeros((480, 640, 3), dtype=np.uint8)
            f[:] = (25, 25, 30)
            t = time.time()
            cx = int(320 + 160 * np.sin(t * 1.2))
            cy = int(240 + 70 * np.cos(t * 1.2))
            try:
                import cv2

                cv2.rectangle(
                    f, (cx - 35, cy - 60), (cx + 35, cy + 60), (0, 200, 255), -1
                )
                cv2.putText(
                    f,
                    "SIMULATED TARGET (bottle)",
                    (cx - 90, cy - 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 255, 255),
                    1,
                )
                cv2.putText(
                    f,
                    f"TIME: {time.strftime('%H:%M:%S')}",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                )
            except Exception:
                pass
            return f
        if self._net is not None:
            return self._net.read()
        if self._cap is not None:
            ok, f = self._cap.read()
            return f if ok else None
        return None

    def _capture_loop(self) -> None:
        while self._running:
            try:
                f = self._grab()
            except Exception:
                f = None  # a source swap can close the client mid-read
            if f is None:
                time.sleep(0.1)
                continue
            with self._lock:
                self._raw = f
                self._frames += 1
                dt = time.time() - self._t0
                if dt >= 2.0:
                    self._fps = self._frames / dt
                    self._frames = 0
                    self._t0 = time.time()
            time.sleep(0.01)

    def _infer_loop(self) -> None:
        from software.plugins import merge_timings, run_frame_plugins

        while self._running:
            with self._lock:
                f = None if self._raw is None else self._raw.copy()
            if f is None or f.ndim != 3 or f.shape[2] != 3:
                time.sleep(0.2)
                continue
            self._sync_interval()
            if not self._should_infer():
                # Pace the detector instead of pegging the CPU: the governor
                # picks the interval, the gate just honours it.
                time.sleep(0.02)
                continue
            t0 = time.time()
            probe = None
            try:
                from software.camera.enhance import enhance_for_inference

                cam_cfg = self.cfg.get("camera", {})
                probe = enhance_for_inference(
                    f,
                    clahe=cam_cfg.get("enhance_clahe", True),
                    sharpen=cam_cfg.get("enhance_sharpen", True),
                    denoise=cam_cfg.get("enhance_denoise", False),
                    fourier=cam_cfg.get("enhance_fourier", False),
                )
                probe, frame_ms = run_frame_plugins(self._plugins, probe)
                dets = self._detector.detect(probe) or []
            except Exception:
                dets = []
                frame_ms = {}
            infer_ms = (time.time() - t0) * 1000.0
            with self._lock:
                self._dets = dets
                self._infer_ms = infer_ms
                self._last_infer = time.time()
                self._frame_ms = frame_ms
                self._plugin_ms = merge_timings(self._frame_ms, self._det_ms)
                if self._plugins and probe is not None:
                    self._plugin_job = (probe, list(dets))
            self._plugin_wake.set()
            self._rt.observe(time.time(), infer_ms)
            time.sleep(0.05)

    def _sync_interval(self) -> None:
        """Adopt whatever interval the governor committed (it owns the dial)."""
        wanted = self._rt.interval
        if wanted == self._infer_interval:
            return
        self._infer_interval = wanted
        self._infer_seq = max(0, wanted - 1)

    def _should_infer(self) -> bool:
        """True on every ``inference_interval``-th pass (first pass included)."""
        interval = max(1, int(self._infer_interval))
        self._infer_seq = (self._infer_seq + 1) % interval
        return self._infer_seq == 0

    def _plugin_loop(self) -> None:
        """Run the slow detection hooks off the inference path.

        Takes the newest (frame, dets), runs every detection plugin, and
        publishes plugin-added detections + timings. Sleeps ``slow_interval_s``
        between passes so the worker can never peg the CPU and starve the
        realtime detector on a 2-core laptop.
        """
        from software.plugins import merge_timings, run_detection_plugins

        while self._running:
            with self._lock:
                job = self._plugin_job
                self._plugin_job = None
            if job is None:
                self._plugin_wake.wait(timeout=0.3)
                self._plugin_wake.clear()
                continue
            probe, dets = job
            t0 = time.time()
            try:
                merged, det_ms = run_detection_plugins(self._plugins, probe, dets)
            except Exception:
                merged, det_ms = dets, {}
            extra = [d for d in merged if all(d is not o for o in dets)]
            with self._lock:
                self._extra_dets = extra
                self._det_ms = det_ms
                self._plugin_ms = merge_timings(self._frame_ms, self._det_ms)
            elapsed = time.time() - t0
            if self._slow_interval_s > elapsed:
                time.sleep(self._slow_interval_s - elapsed)

    # ---- reads ----
    def snapshot(self) -> tuple[np.ndarray | None, list[dict]]:
        """Latest raw frame + latest detections (no drawing)."""
        with self._lock:
            f = None if self._raw is None else self._raw.copy()
            dets = list(self._dets) + list(self._extra_dets)
        return f, [d.to_dict() for d in dets]

    def jpeg(self) -> bytes | None:
        import cv2

        f, dets = self.snapshot()
        if f is None:
            return None
        for d in dets:
            tid = f" #{d['track_id']}" if d.get("track_id") is not None else ""
            cv2.rectangle(
                f,
                (int(d["x1"]), int(d["y1"])),
                (int(d["x2"]), int(d["y2"])),
                (0, 255, 0),
                2,
            )
            cv2.putText(
                f,
                f"{d['class_name']}{tid} {d['confidence']:.2f}",
                (int(d["x1"]), max(0, int(d["y1"]) - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
        # q70: ~3x smaller than the cv2 default q95 — the deck redraws boxes on
        # every browser pull, so smaller chunks keep the MJPEG loop snappy.
        ok, buf = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return bytes(buf) if ok else None

    def autotune_status(self) -> dict[str, Any]:
        """What the tuner is doing (surfaced as ``feed.autotune`` on the deck).

        Cheap enough to call per request: it rebuilds small dicts from the
        tuner's own bookkeeping and touches no frame, lock or detector.
        """
        status = self._tuner.status()
        status["realtime"] = self._rt.status()
        return status

    def state(self) -> dict[str, Any]:
        with self._lock:
            dets = list(self._dets) + list(self._extra_dets)
            fps, ms = self._fps, self._infer_ms
            plugin_ms = dict(self._plugin_ms)
            age = (
                round(time.time() - self._last_infer, 1) if self._last_infer > 0 else -1
            )
        det_cfg = self._detector
        model = getattr(det_cfg, "model_name", self.cfg["ai"].get("model_name", "-"))
        engine = getattr(det_cfg, "engine", "-")
        plugin_stats = {}
        world: dict[str, Any] = {}
        for plugin in self._plugins:
            with contextlib.suppress(Exception):
                plugin_stats[plugin.name] = plugin.stats()
            world_state = getattr(plugin, "world_state", None)
            if callable(world_state):
                with contextlib.suppress(Exception):
                    world = world_state() or world
        return {
            "source": self.source,
            "cam_index": self.cam_index,
            "backend": type(self._detector).__name__ if self._detector else "-",
            "engine": engine,
            "model": model,
            "camera_fps": round(fps, 1),
            "infer_ms": round(ms, 0),
            "ai_age_s": age,
            "inference_interval": self._infer_interval,
            "autotune": self.autotune_status(),
            "objects": len(dets),
            "plugins": plugin_ms,
            "plugins_stats": plugin_stats,
            "world": world,
            "detections": [
                {
                    "label": d.class_name,
                    "conf": round(d.confidence, 2),
                    "id": d.track_id,
                    "pos": "L"
                    if (d.center_x_norm(640) < 0.33)
                    else ("C" if d.center_x_norm(640) < 0.66 else "R"),
                    "cx": int(d.center_x),
                    "w": int(d.width),
                }
                for d in dets
            ],
        }
