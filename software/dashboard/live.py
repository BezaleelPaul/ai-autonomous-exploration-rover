"""Live browser GUI backend: smooth webcam video + AI boxes overlaid.

Two threads: capture grabs raw frames at camera FPS; inference re-runs the
detector on the newest frame whenever free (~0.3 s on CPU with yolo11s). The
MJPEG stream always shows fresh video with the latest boxes — video stays live
even while the AI runs.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import numpy as np


class LiveFeed:
    def __init__(self, cfg: dict, source: str = "cam", cam_index: int = 0):
        self.cfg = cfg
        self.source = source
        self.cam_index = cam_index
        self._lock = threading.Lock()
        self._raw: np.ndarray | None = None
        self._dets: list = []
        self._infer_ms = 0.0
        self._last_infer = 0.0
        self._frames = 0
        self._t0 = time.time()
        self._fps = 0.0
        self._running = False
        self._cap = None
        self._esp32 = None
        self._detector = None
        self._backend = cfg["ai"].get("backend", "mock")

    def start(self) -> None:
        from software.ai.detector import create_detector

        self._detector = create_detector(self.cfg)
        load = getattr(self._detector, "load", None)
        if callable(load):
            load()
        if self.source == "esp32":
            from software.camera.esp32_stream import ESP32Stream

            cam = self.cfg["camera"]
            self._esp32 = ESP32Stream(cam["esp32_url"], mock=False)
            self._esp32.open()
        else:
            import cv2

            self._cap = cv2.VideoCapture(self.cam_index)
        self._running = True
        threading.Thread(target=self._capture_loop, daemon=True).start()
        threading.Thread(target=self._infer_loop, daemon=True).start()

    def stop(self) -> None:
        self._running = False

    # ---- threads ----
    def _grab(self) -> np.ndarray | None:
        if self._esp32 is not None:
            return self._esp32.read()
        if self._cap is not None:
            ok, f = self._cap.read()
            return f if ok else None
        return None

    def _capture_loop(self) -> None:
        while self._running:
            f = self._grab()
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
            time.sleep(0.03)

    def _infer_loop(self) -> None:
        while self._running:
            with self._lock:
                f = None if self._raw is None else self._raw.copy()
            if f is None or f.ndim != 3 or f.shape[2] != 3:
                time.sleep(0.2)
                continue
            t0 = time.time()
            try:
                from software.camera.enhance import enhance_for_inference

                cam_cfg = self.cfg.get("camera", {})
                probe = enhance_for_inference(
                    f,
                    clahe=cam_cfg.get("enhance_clahe", True),
                    sharpen=cam_cfg.get("enhance_sharpen", True),
                    denoise=cam_cfg.get("enhance_denoise", False),
                )
                dets = self._detector.detect(probe) or []
            except Exception:
                dets = []
            with self._lock:
                self._dets = dets
                self._infer_ms = (time.time() - t0) * 1000.0
                self._last_infer = time.time()
            time.sleep(0.05)

    # ---- reads ----
    def snapshot(self) -> tuple[np.ndarray | None, list[dict]]:
        """Latest raw frame + latest detections (no drawing)."""
        with self._lock:
            f = None if self._raw is None else self._raw.copy()
            dets = list(self._dets)
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
        ok, buf = cv2.imencode(".jpg", f)
        return bytes(buf) if ok else None

    def state(self) -> dict[str, Any]:
        with self._lock:
            dets = list(self._dets)
            fps, ms = self._fps, self._infer_ms
            age = (
                round(time.time() - self._last_infer, 1) if self._last_infer > 0 else -1
            )
        det_cfg = self._detector
        model = getattr(det_cfg, "model_name", self.cfg["ai"].get("model_name", "-"))
        return {
            "source": self.source,
            "cam_index": self.cam_index,
            "backend": type(self._detector).__name__ if self._detector else "-",
            "model": model,
            "camera_fps": round(fps, 1),
            "infer_ms": round(ms, 0),
            "ai_age_s": age,
            "objects": len(dets),
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
