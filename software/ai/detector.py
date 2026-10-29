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


def resolve_model_path(model: str, export: str = "torch") -> tuple[str, str]:
    """Pick the artifact ``ai.export`` asks for, falling back to the .pt weights.

    Returns ``(path, engine)``. ``export`` is ``torch`` (default), ``onnx`` or
    ``openvino``; a missing export artifact is never an error - we load the
    original ``.pt`` and report ``torch`` so tests and offline machines behave
    exactly as before.
    """
    from pathlib import Path

    engine = (export or "torch").strip().lower()
    if engine not in ("torch", "onnx", "openvino"):
        engine = "torch"
    if engine != "torch":
        stem = Path(model).with_suffix("")
        if engine == "onnx":
            onnx_path = Path(f"{stem}.onnx")
            if onnx_path.is_file():
                return str(onnx_path), "onnx"
        else:
            ov_dir = Path(f"{stem}_openvino_model")
            if ov_dir.is_dir() and any(ov_dir.glob("*.xml")):
                return str(ov_dir), "openvino"
        warnings.warn(
            f"ai.export={engine} but no export artifact for {model}; using .pt",
            RuntimeWarning,
            stacklevel=2,
        )
    return model, "torch"


def box_iou(b1: tuple[float, float, float, float], b2: tuple[float, float, float, float]) -> float:
    """Intersection over Union for (x1, y1, x2, y2)."""
    xx1 = max(b1[0], b2[0])
    yy1 = max(b1[1], b2[1])
    xx2 = min(b1[2], b2[2])
    yy2 = min(b1[3], b2[3])
    w = max(0.0, xx2 - xx1)
    h = max(0.0, yy2 - yy1)
    inter = w * h
    area1 = max(0.0, b1[2] - b1[0]) * max(0.0, b1[3] - b1[1])
    area2 = max(0.0, b2[2] - b2[0]) * max(0.0, b2[3] - b2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


def nms_detections(dets: list[Detection], iou_thresh: float = 0.5) -> list[Detection]:
    """Class-aware Non-Maximum Suppression over a list of Detection objects."""
    if not dets:
        return []
    sorted_dets = sorted(dets, key=lambda d: d.confidence, reverse=True)
    kept: list[Detection] = []
    for d in sorted_dets:
        box_d = (d.x1, d.y1, d.x2, d.y2)
        suppress = False
        for k in kept:
            if d.class_name.lower() == k.class_name.lower():
                box_k = (k.x1, k.y1, k.x2, k.y2)
                if box_iou(box_d, box_k) > iou_thresh:
                    suppress = True
                    break
        if not suppress:
            kept.append(d)
    return kept


class YoloDetector(BaseDetector):
    """Ultralytics YOLO backend: multi-object detection and tracking.
    
    Supports TrackTrack, BoT-SORT, ByteTrack, OC-SORT, Deep OC-SORT, FastTracker,
    plus SAHI (Slicing Aided Hyper Inference) for small/far distant object detection.
    """

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
        export: str = "torch",
        openvino_device: str = "",
        sahi_enabled: bool = False,
        sahi_slice_size: int = 320,
        sahi_overlap: float = 0.20,
    ):
        self.model_name = model
        self.confidence_threshold = confidence_threshold
        self.allowed = {a.lower() for a in (allowed_classes or [])}
        self.min_box_px = min_box_px
        self.imgsz = imgsz
        self.use_track = track
        self.iou_threshold = iou_threshold
        self.tracker = self._normalize_tracker(tracker)
        self.export = export
        self.openvino_device = (openvino_device or "").strip().lower()
        self.sahi_enabled = sahi_enabled
        self.sahi_slice_size = max(128, int(sahi_slice_size))
        self.sahi_overlap = max(0.0, min(0.5, float(sahi_overlap)))
        self.engine = "torch"
        # Open-vocabulary words (only used by *-world.pt models, e.g. "pen").
        self.custom_classes = [c for c in (custom_classes or []) if c]
        self._model = None
        self._load_error: str | None = None
        self._track_unavailable = False

    @staticmethod
    def _normalize_tracker(tracker: str | None) -> str:
        if not tracker:
            return "botsort.yaml"
        t = tracker.strip().lower()
        if t in ("default", "bytetrack"):
            return "bytetrack.yaml"
        if not t.endswith(".yaml") and not t.endswith(".yml"):
            return f"{t}.yaml"
        return t

    def load(self) -> bool:
        try:
            # On a 2-core laptop ONNX Runtime otherwise saturates every logical
            # CPU during each pass and the video decoder starves (visible lag).
            # Respect an explicit user choice; override with OMP_NUM_THREADS.
            import os

            os.environ.setdefault("OMP_NUM_THREADS", "2")
            from ultralytics import YOLO

            path, engine = resolve_model_path(self.model_name, self.export)
            self._model = YOLO(path)
            self.engine = engine
            if engine == "openvino":
                self.openvino_device = self._resolve_ov_device()
            if "world" in self.model_name.lower() and self.custom_classes:
                self._model.set_classes(self.custom_classes)
            return True
        except Exception as e:
            self._load_error = str(e)
            return False

    def _resolve_ov_device(self) -> str:
        """Validate the requested OpenVINO device; fall back to CPU when absent.

        Accepts ``intel:gpu``/``gpu``/``GPU`` etc. Returns the normalized
        ultralytics device string (``intel:gpu`` or ``intel:cpu``). A missing
        iGPU is never fatal - we degrade to CPU rather than refuse to load.
        """
        wanted = (self.openvino_device or "intel:cpu").lower()
        if wanted in ("gpu", "intel:gpu"):
            wanted = "intel:gpu"
        elif wanted in ("cpu", "intel:cpu"):
            wanted = "intel:cpu"
        if wanted == "intel:gpu":
            try:
                import openvino as ov

                # GPU shows up as "GPU" (or "GPU.0") in available_devices.
                if not any(
                    d.upper().startswith("GPU") for d in ov.Core().available_devices
                ):
                    return "intel:cpu"
            except Exception:
                return "intel:cpu"
        return wanted

    def _device_kwargs(self) -> dict:
        """predict/track kwargs pinning the OpenVINO device (empty for torch/onnx)."""
        if self.engine == "openvino" and self.openvino_device:
            return {"device": self.openvino_device}
        return {}

    def is_ready(self) -> bool:
        return self._model is not None

    def _predict(self, frame: np.ndarray, imgsz: int | None = None):
        """Plain inference pass (no tracker), shared by both branches."""
        sz = imgsz or self.imgsz
        return self._model.predict(
            frame,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            imgsz=sz,
            verbose=False,
            **self._device_kwargs(),
        )[0]

    def _parse_boxes(
        self,
        res,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> list[Detection]:
        """Convert ultralytics result to list[Detection] with optional coordinate offset."""
        out: list[Detection] = []
        names = getattr(res, "names", {})
        boxes = getattr(res, "boxes", None)
        ids = (
            boxes.id.cpu().tolist()
            if boxes is not None and boxes.id is not None
            else []
        )
        now = time.time()
        for i, b in enumerate(boxes or []):
            name = str(names[int(b.cls[0])]).lower()
            if self.allowed and name not in self.allowed:
                continue
            x1, y1, x2, y2 = [float(v) for v in b.xyxy[0].tolist()]
            if (x2 - x1) < self.min_box_px or (y2 - y1) < self.min_box_px:
                continue  # tiny-box false positives
            tid = int(ids[i]) if i < len(ids) else None
            out.append(
                Detection(
                    name,
                    float(b.conf[0]),
                    x1 + offset_x,
                    y1 + offset_y,
                    x2 + offset_x,
                    y2 + offset_y,
                    now,
                    tid,
                )
            )
        return out

    def _detect_sliced(self, frame: np.ndarray) -> list[Detection]:
        """SAHI Sliced Inference: combines global scene pass with local tiles for far/small objects."""
        h, w = frame.shape[:2]
        # 1. Global pass (carries main tracker state if active)
        global_dets = self._detect_standard(frame)

        # If image is smaller or equal to slice size, slicing is redundant
        if w <= self.sahi_slice_size and h <= self.sahi_slice_size:
            return global_dets

        # 2. Sliced passes: tile across image with overlap
        slice_w = min(w, self.sahi_slice_size)
        slice_h = min(h, self.sahi_slice_size)
        step_x = max(1, int(slice_w * (1.0 - self.sahi_overlap)))
        step_y = max(1, int(slice_h * (1.0 - self.sahi_overlap)))

        tile_dets: list[Detection] = []
        for y in range(0, h, step_y):
            for x in range(0, w, step_x):
                y_end = min(h, y + slice_h)
                x_end = min(w, x + slice_w)
                y_start = max(0, y_end - slice_h)
                x_start = max(0, x_end - slice_w)

                crop = frame[y_start:y_end, x_start:x_end]
                # Slices use plain prediction to avoid disrupting global tracker GMC/optical flow
                crop_res = self._predict(crop, imgsz=self.sahi_slice_size)
                crop_boxes = self._parse_boxes(
                    crop_res, offset_x=float(x_start), offset_y=float(y_start)
                )
                tile_dets.extend(crop_boxes)

        # 3. Fuse global and tile detections using Non-Maximum Suppression
        all_dets = list(global_dets) + tile_dets
        fused = nms_detections(all_dets, iou_thresh=self.iou_threshold)

        # Transfer track IDs from global detections to fused detections when boxes overlap
        for fd in fused:
            if fd.track_id is None:
                for gd in global_dets:
                    if gd.track_id is not None and gd.class_name == fd.class_name:
                        if box_iou((fd.x1, fd.y1, fd.x2, fd.y2), (gd.x1, gd.y1, gd.x2, gd.y2)) > 0.4:
                            fd.track_id = gd.track_id
                            break

        return sorted(fused, key=lambda d: d.confidence, reverse=True)

    def _detect_standard(self, frame: np.ndarray) -> list[Detection]:
        """Standard full-frame detection / tracking pass."""
        if self.use_track and not self._track_unavailable:
            track_kwargs = {
                "conf": self.confidence_threshold,
                "iou": self.iou_threshold,
                "imgsz": self.imgsz,
                "verbose": False,
                "persist": True,
                **self._device_kwargs(),
            }
            if self.tracker:
                track_kwargs["tracker"] = self.tracker
            try:
                res = self._model.track(frame, **track_kwargs)[0]
            except Exception:
                # Track failure fallback: degrade to plain predict for this frame
                res = self._predict(frame)
        else:
            res = self._predict(frame)

        boxes = self._parse_boxes(res)
        return sorted(boxes, key=lambda d: d.confidence, reverse=True)

    def detect(self, frame: np.ndarray | None) -> list[Detection]:
        if frame is None:
            return []
        if self._model is None and not self.load():
            return []
        try:
            if self.sahi_enabled:
                return self._detect_sliced(frame)
            return self._detect_standard(frame)
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
            export=ai.get("export", "torch"),
            openvino_device=ai.get("openvino_device", ""),
            sahi_enabled=bool(ai.get("sahi_enabled", False)),
            sahi_slice_size=int(ai.get("sahi_slice_size", 320)),
            sahi_overlap=float(ai.get("sahi_overlap", 0.20)),
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
