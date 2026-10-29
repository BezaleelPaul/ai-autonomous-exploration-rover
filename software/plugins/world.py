"""Open-vocabulary second pass (YOLO-World) for classes COCO misses.

The control model (yolo26n, COCO-80) never says "pen" or "keys". This plugin
runs yolov8s-worldv2 on the same frame with the repo's ``custom_classes``
vocabulary and merges any *new* object — duplicates of what COCO already found
(IoU >= 0.5) are dropped so the why-chain keeps a single target per object.

Cost control via config::

    plugins:
      world_every_n: 2   # run every 2nd AI pass (1 = every pass)
      world_conf: 0.25
"""

from __future__ import annotations

import time

from software.ai.detection import Detection
from software.plugins import VisionPlugin

WORLD_MODEL = "yolov8s-worldv2.pt"
WORLD_IMGSZ = 320
DEDUP_IOU = 0.5


def box_iou(a, b) -> float:
    """IoU of two xyxy boxes (Detection or anything with x1..y2)."""
    ix1, iy1 = max(a.x1, b.x1), max(a.y1, b.y1)
    ix2, iy2 = min(a.x2, b.x2), min(a.y2, b.y2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, a.x2 - a.x1) * max(0.0, a.y2 - a.y1)
    area_b = max(0.0, b.x2 - b.x1) * max(0.0, b.y2 - b.y1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


class WorldLabeler(VisionPlugin):
    name = "world"

    def __init__(self, conf: float = 0.25, every_n: int = 2) -> None:
        self.conf = float(conf)
        self.every_n = max(1, int(every_n))
        self._model = None
        self._calls = 0
        self._passes = 0
        self._added = 0
        self.last_ms = 0.0

    def start(self, cfg: dict) -> None:
        from ultralytics import YOLO

        self._model = YOLO(WORLD_MODEL)
        words = [
            str(c) for c in (cfg.get("ai", {}) or {}).get("custom_classes", []) or []
        ]
        if words:
            self._model.set_classes(words)

    def process_detections(self, frame, dets: list) -> list:
        self._calls += 1
        if self._model is None or frame is None:
            return dets
        if (self._calls % self.every_n) != 0:
            return dets  # every_n > 1: amortize the extra inference pass
        self._passes += 1
        t0 = time.time()
        try:
            res = self._model.predict(
                frame, conf=self.conf, imgsz=WORLD_IMGSZ, verbose=False
            )[0]
            names = res.names
            merged = list(dets)
            for b in res.boxes or []:
                name = str(names[int(b.cls[0])]).lower()
                score = float(b.conf[0])
                raw = b.xyxy[0]
                vals = raw.tolist() if hasattr(raw, "tolist") else list(raw)
                x1, y1, x2, y2 = [float(v) for v in vals]
                candidate = Detection(name, score, x1, y1, x2, y2, time.time())
                if any(box_iou(candidate, seen) >= DEDUP_IOU for seen in merged):
                    continue  # COCO already saw this object
                merged.append(candidate)
                self._added += 1
            return merged
        finally:
            self.last_ms = round((time.time() - t0) * 1000.0, 1)

    def stats(self) -> dict:
        return {
            "calls": self._calls,
            "passes": self._passes,
            "added": self._added,
            "last_ms": self.last_ms,
        }


def create(cfg: dict) -> WorldLabeler:
    plugins_cfg = cfg.get("plugins", {}) or {}
    return WorldLabeler(
        conf=float(plugins_cfg.get("world_conf", 0.25)),
        every_n=int(plugins_cfg.get("world_every_n", 2)),
    )
