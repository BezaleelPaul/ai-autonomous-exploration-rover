"""Detector abstraction: mock | color | hf. Decision engine never touches a model directly."""

from __future__ import annotations

import time
import warnings

import numpy as np

from software.ai.detection import Detection


class BaseDetector:
    def detect(self, frame: np.ndarray | None) -> list[Detection]:
        raise NotImplementedError

    def is_ready(self) -> bool:
        return True


def detector_class_names(detector: BaseDetector) -> dict[int, str]:
    """Map class index -> label for any backend.

    Ultralytics models expose ``.names``; Hugging Face transformers models keep
    the model in a ``_pipe`` tuple and expose ``config.id2label``. Without both
    conventions the ``hf`` backend reports no class names, which made every HF
    model unbenchmarkable (REGRESSION_REPORT.md section 9).
    """
    model = getattr(detector, "_model", None)
    if model is None:
        pipe = getattr(detector, "_pipe", None)
        if isinstance(pipe, tuple) and len(pipe) > 1:
            model = pipe[1]
    names = dict(getattr(model, "names", None) or {})
    if names:
        return {int(key): str(value) for key, value in names.items()}
    id2label = dict(getattr(getattr(model, "config", None), "id2label", None) or {})
    return {int(key): str(value) for key, value in id2label.items()}


class MockDetector(BaseDetector):
    """Deterministic detector for tests/demo without weights."""

    def __init__(
        self,
        target: str = "bottle",
        position: str = "CENTER",
        confidence: float = 0.9,
        emit: bool = True,
        frame_width: int = 640,
        frame_height: int = 480,
    ):
        self.target = target
        self.position = position
        self.confidence = confidence
        self.emit = emit
        self.frame_width = frame_width
        self.frame_height = frame_height

    def detect(self, frame=None) -> list[Detection]:
        if not self.emit:
            return []
        w, h = self.frame_width, self.frame_height
        cx_frac = {"LEFT": 0.16, "CENTER": 0.5, "RIGHT": 0.84}.get(self.position, 0.5)
        cx = cx_frac * w
        bw, bh = w * 0.15, h * 0.25
        return [
            Detection(
                self.target,
                self.confidence,
                cx - bw / 2,
                h * 0.35,
                cx + bw / 2,
                h * 0.35 + bh,
            )
        ]


class ColorDetector(BaseDetector):
    """Lightweight offline fallback: detects large green blobs as 'bottle'.
    Useful when no HF weights are available. No ML claims."""

    def __init__(self, confidence: float = 0.6, min_area: int = 4000):
        self.confidence = confidence
        self.min_area = min_area

    def detect(self, frame: np.ndarray | None) -> list[Detection]:
        if frame is None:
            return []
        try:
            import cv2

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, np.array([35, 60, 60]), np.array([85, 255, 255]))
            contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            out: list[Detection] = []
            for c in contours:
                if cv2.contourArea(c) < self.min_area:
                    continue
                x, y, w, h = cv2.boundingRect(c)
                out.append(
                    Detection(
                        "bottle",
                        self.confidence,
                        float(x),
                        float(y),
                        float(x + w),
                        float(y + h),
                    )
                )
            return sorted(out, key=lambda d: d.confidence, reverse=True)
        except Exception:
            return []


class HFDetector(BaseDetector):
    """Hugging Face object-detection model behind a stable interface.

    Primary: facebook/detr-resnet-50. Replaceable with hustvl/yolos-tiny or
    RT-DETR variants via config ai.model_name only — navigation/safety/serial
    code never imports transformers/torch directly (see create_detector).
    Output is always List[Detection]: label, score, x1/y1/x2/y2 + derived
    center_x/center_y/width/height (see detection.py).
    """

    def __init__(
        self,
        model_name: str = "facebook/detr-resnet-50",
        confidence_threshold: float = 0.5,
        allowed_classes: list[str] | None = None,
        device: str = "cpu",
        model_dir: str | None = None,
    ):
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.allowed = {a.lower() for a in (allowed_classes or [])}
        self.device = device
        self.model_dir = model_dir  # local offline cache; None => HF cache
        self._pipe = None
        self._load_error: str | None = None
        self._ready = False

    def _dir_matches_name(self) -> bool:
        """True when the local model_dir looks like the requested checkpoint."""
        from pathlib import Path as _P

        leaf = _P(self.model_dir or "").name.lower()
        if not leaf:
            return True
        return leaf in (self.model_name or "").lower()

    def _source(self) -> str:
        from pathlib import Path as _P

        if (
            self.model_dir
            and _P(self.model_dir).exists()
            and any(_P(self.model_dir).iterdir())
        ):
            if not self._dir_matches_name():
                # Silently loading the wrong checkpoint made an HF benchmark
                # unattributable once already (REGRESSION_REPORT.md section 9).
                warnings.warn(
                    f"ai.model_dir={self.model_dir!r} exists and therefore shadows "
                    f"ai.model_name={self.model_name!r}; loading from model_dir. "
                    "Clear ai.model_dir to use model_name.",
                    UserWarning,
                    stacklevel=2,
                )
            return self.model_dir
        return self.model_name

    def load(self) -> bool:
        try:
            import torch

            src = self._source()
            # Generic path first => YOLOS-Tiny / RT-DETR swappable without code change.
            try:
                from transformers import (
                    AutoImageProcessor,
                    AutoModelForObjectDetection,
                )

                proc = AutoImageProcessor.from_pretrained(src, local_files_only=False)
                model = AutoModelForObjectDetection.from_pretrained(src)
            except Exception:
                from transformers import DetrForObjectDetection, DetrImageProcessor

                proc = DetrImageProcessor.from_pretrained(src)
                model = DetrForObjectDetection.from_pretrained(src)
            model.to(self.device)
            model.eval()
            self._pipe = (proc, model, torch)
            self._ready = True
            return True
        except Exception as e:
            self._load_error = str(e)
            self._ready = False
            return False

    def is_ready(self) -> bool:
        return self._ready

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def detect(self, frame: np.ndarray | None) -> list[Detection]:
        if frame is None:
            return []
        if not self._ready and not self.load():
            return []
        try:
            import torch
            from PIL import Image

            proc, model, _ = self._pipe
            img = Image.fromarray(frame[:, :, ::-1])  # BGR->RGB
            inputs = proc(images=img, return_tensors="pt").to(self.device)
            with torch.no_grad():
                out = model(**inputs)
            tw, th = img.size
            results = proc.post_process_object_detection(
                out, target_sizes=[(th, tw)], threshold=self.confidence_threshold
            )[0]
            dets: list[Detection] = []
            for score, label, box in zip(
                results["scores"], results["labels"], results["boxes"]
            ):
                name = model.config.id2label[int(label)].lower()
                if self.allowed and name not in self.allowed:
                    continue
                x1, y1, x2, y2 = [float(v) for v in box.tolist()]
                dets.append(Detection(name, float(score), x1, y1, x2, y2, time.time()))
            return dets
        except Exception:
            return []


class YoloDetector(BaseDetector):
    """Ultralytics YOLO backend (default yolo11s.pt): accurate + ByteTrack IDs
    so labels stick to objects between inferences. Same Detection output
    (+track_id); swap via config ai.backend=yolo / ai.yolo_model.
    Auto-downloads weights once."""

    def __init__(
        self,
        model: str = "yolo11n.pt",
        confidence_threshold: float = 0.5,
        allowed_classes: list[str] | None = None,
        min_box_px: int = 8,
        imgsz: int = 320,
        track: bool = True,
        custom_classes: list[str] | None = None,
        iou_threshold: float = 0.7,
        tracker: str = "botsort.yaml",
    ):
        self.model_name = model
        self.confidence_threshold = confidence_threshold
        self.allowed = {a.lower() for a in (allowed_classes or [])}
        self.min_box_px = min_box_px
        self.imgsz = imgsz
        self.use_track = track
        self.iou_threshold = iou_threshold
        self.tracker = tracker
        # Open-vocabulary words (only used by *-world.pt models, e.g. "pen").
        self.custom_classes = [c for c in (custom_classes or []) if c]
        self._model = None
        self._load_error: str | None = None

    def load(self) -> bool:
        try:
            from ultralytics import YOLO

            self._model = YOLO(self.model_name)
            if "world" in self.model_name.lower() and self.custom_classes:
                self._model.set_classes(self.custom_classes)
            return True
        except Exception as e:
            self._load_error = str(e)
            return False

    def is_ready(self) -> bool:
        return self._model is not None

    def detect(self, frame: np.ndarray | None) -> list[Detection]:
        if frame is None:
            return []
        if self._model is None and not self.load():
            return []
        try:
            if self.use_track:
                track_kwargs = {
                    "conf": self.confidence_threshold,
                    "iou": self.iou_threshold,
                    "imgsz": self.imgsz,
                    "verbose": False,
                    "persist": True,
                }
                if self.tracker and self.tracker not in ("default", "bytetrack"):
                    track_kwargs["tracker"] = self.tracker
                res = self._model.track(frame, **track_kwargs)[0]
            else:
                res = self._model.predict(
                    frame,
                    conf=self.confidence_threshold,
                    iou=self.iou_threshold,
                    imgsz=self.imgsz,
                    verbose=False,
                )[0]
            out: list[Detection] = []
            names = res.names
            boxes = res.boxes
            ids = (
                boxes.id.cpu().tolist()
                if boxes is not None and boxes.id is not None
                else []
            )
            for i, b in enumerate(boxes or []):
                name = str(names[int(b.cls[0])]).lower()
                if self.allowed and name not in self.allowed:
                    continue
                x1, y1, x2, y2 = [float(v) for v in b.xyxy[0].tolist()]
                if (x2 - x1) < self.min_box_px or (y2 - y1) < self.min_box_px:
                    continue  # tiny-box false positives
                tid = int(ids[i]) if i < len(ids) else None
                out.append(
                    Detection(name, float(b.conf[0]), x1, y1, x2, y2, time.time(), tid)
                )
            return sorted(out, key=lambda d: d.confidence, reverse=True)
        except Exception:
            return []


def create_detector(cfg: dict) -> BaseDetector:
    ai = cfg.get("ai", {})
    backend = str(ai.get("backend", "mock")).lower()
    if backend == "hf":
        return HFDetector(
            ai.get("model_name", "facebook/detr-resnet-50"),
            ai.get("confidence_threshold", 0.5),
            ai.get("allowed_classes", []),
            ai.get("device", "cpu"),
            ai.get("model_dir"),
        )
    if backend == "yolo":
        return YoloDetector(
            ai.get("yolo_model", "yolo11n.pt"),
            ai.get("confidence_threshold", 0.5),
            ai.get("allowed_classes", []),
            ai.get("min_box_px", 8),
            ai.get("yolo_imgsz", 320),
            ai.get("yolo_track", True),
            ai.get("custom_classes", []),
            ai.get("iou_threshold", 0.7),
            tracker=ai.get("tracker", "botsort.yaml"),
        )
    if backend == "color":
        return ColorDetector()
    allowed = ai.get("allowed_classes", ["bottle"])
    tgt = allowed[0] if allowed else "bottle"
    # The mock simulates "one clearly visible target", so it reports exactly the
    # bar ObjectTracker/SafetyManager act on. Anchoring it to
    # confidence_threshold instead would make mock mode undrivable whenever the
    # detection threshold (a recall dial) is lowered below target_confidence.
    return MockDetector(
        target=tgt,
        confidence=ai.get("target_confidence", ai.get("confidence_threshold", 0.5)),
    )
