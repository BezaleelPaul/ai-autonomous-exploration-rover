"""Vision plumbing: resilient MJPEG frame source + Ultralytics YOLO adapter.

Heavy dependencies (OpenCV, ultralytics) are imported lazily so the rest of
the package (and the test suite) works on a machine without them.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .steering import Detection


@dataclass
class CapturedFrame:
    image: object  # numpy.ndarray (BGR)
    ts: float


class LatestFrameSource:
    """Background MJPEG reader that always exposes the newest frame.

    A dedicated thread keeps draining the camera, so slow YOLO inference never
    builds a latency backlog: the pilot always sees the *current* scene.  If
    the phone stops streaming, :meth:`read` returns ``None`` once frames go
    stale and the pilot commands a stop.
    """

    def __init__(
        self,
        url: str,
        reconnect_delay: float = 1.5,
        read_fail_limit: int = 15,
        capture_factory: Callable[[str], object] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not url:
            raise ValueError("camera URL is empty")
        self.url = url
        self.reconnect_delay = reconnect_delay
        self.read_fail_limit = read_fail_limit
        self._capture_factory = capture_factory
        self._clock = clock
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._frame: CapturedFrame | None = None
        self.frames_read = 0
        self.reconnects = 0
        self.last_error = ""
        self.started_at = 0.0

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> "LatestFrameSource":
        if self._thread and self._thread.is_alive():
            return self
        self._stop.clear()
        self.started_at = self._clock()
        self._thread = threading.Thread(target=self._run, name="frame-source", daemon=True)
        self._thread.start()
        return self

    def stop(self, join: bool = True) -> None:
        self._stop.set()
        if join and self._thread:
            self._thread.join(timeout=3.0)
        self._thread = None

    def __enter__(self) -> "LatestFrameSource":
        return self.start()

    def __exit__(self, *exc_info) -> None:
        self.stop()

    # -- capture -----------------------------------------------------------
    def _make_capture(self) -> object:
        if self._capture_factory is not None:
            return self._capture_factory(self.url)
        import cv2  # local import: keeps tests dependency-free

        cap = cv2.VideoCapture(self.url)
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        return cap

    def _run(self) -> None:
        failures = 0
        while not self._stop.is_set():
            cap = self._make_capture()
            if not getattr(cap, "isOpened", lambda: True)():
                failures += 1
                self.reconnects += 1
                self.last_error = f"cannot open {self.url}"
                self._sleep_reconnect(failures)
                continue
            failures = 0
            while not self._stop.is_set():
                ok, image = cap.read()
                if not ok or image is None:
                    failures += 1
                    if failures >= self.read_fail_limit:
                        self.last_error = "stream read failures"
                        break
                    time.sleep(0.01)
                    continue
                failures = 0
                with self._lock:
                    self._frame = CapturedFrame(image=image, ts=self._clock())
                self.frames_read += 1
            try:
                cap.release()
            except Exception:
                pass
            if not self._stop.is_set():
                self.reconnects += 1
                self._sleep_reconnect(1)

    def _sleep_reconnect(self, attempt: int) -> None:
        self._stop.wait(min(self.reconnect_delay * max(1, attempt), 5.0))

    # -- consumer ----------------------------------------------------------
    def read(self, max_age: float = 1.5) -> CapturedFrame | None:
        with self._lock:
            frame = self._frame
        if frame is None:
            return None
        if (self._clock() - frame.ts) > max_age:
            return None
        return frame

    def read_latest(self) -> CapturedFrame | None:
        with self._lock:
            return self._frame

    @property
    def fps(self) -> float:
        elapsed = self._clock() - self.started_at
        return (self.frames_read / elapsed) if elapsed > 0 else 0.0

    def age(self) -> float | None:
        frame = self.read_latest()
        return None if frame is None else self._clock() - frame.ts


class YoloDetector:
    """Ultralytics YOLO wrapper returning plain :class:`Detection` objects."""

    def __init__(
        self,
        weights: str = "yolo11n.pt",
        imgsz: int = 320,
        conf: float = 0.35,
        device: str = "cpu",
        class_names: Sequence[str] | None = None,
        verbose: bool = False,
    ) -> None:
        self.weights = weights
        self.imgsz = int(imgsz)
        self.conf = float(conf)
        self.device = device
        self.verbose = verbose
        self._model = None
        self._wanted_names = list(class_names or [])
        self.class_ids: list[int] | None = None

    # -- loading -----------------------------------------------------------
    @property
    def model(self):
        if self._model is None:
            from ultralytics import YOLO

            self._model = YOLO(self.weights)
            self._resolve_classes()
        return self._model

    def _resolve_classes(self) -> None:
        names = getattr(self._model, "names", {}) or {}
        if isinstance(names, dict):
            by_name = {str(v).lower(): int(k) for k, v in names.items()}
        else:
            by_name = {str(v).lower(): i for i, v in enumerate(names)}
        missing = [n for n in self._wanted_names if n.lower() not in by_name]
        if missing:
            raise ValueError(f"classes not in model {self.weights}: {missing}; available: {sorted(by_name)}")
        self.class_ids = [by_name[n.lower()] for n in self._wanted_names] or None

    @property
    def class_names(self) -> dict[int, str]:
        names = getattr(self.model, "names", {}) or {}
        return {int(k): str(v) for k, v in names.items()} if isinstance(names, dict) else dict(enumerate(names))

    def warmup(self) -> None:
        try:
            import numpy as np

            blank = np.zeros((self.imgsz, self.imgsz, 3), dtype=np.uint8)
            self.detect(blank)
        except Exception:
            pass

    # -- inference ---------------------------------------------------------
    def detect(self, frame) -> list[Detection]:
        results = self.model.predict(
            source=frame,
            imgsz=self.imgsz,
            conf=self.conf,
            device=self.device,
            classes=self.class_ids,
            verbose=False,
        )
        return _results_to_detections(results)

    def __call__(self, frame) -> list[Detection]:
        return self.detect(frame)


class WorldDetector:
    """Open-vocabulary detector (YOLO-World): prompt arbitrary object names.

    This is the "any type of object" path: instead of a fixed 80/24-class
    head, the vocabulary is a list of text prompts. It is slower on CPU than
    YOLO11n and less precise on classes the base vocabulary knows poorly, but
    it can look for things no COCO model contains (door, cable, cone, ...).

    >>> WorldDetector(class_names=["door", "cable"])   # doctest: +SKIP
    """

    def __init__(
        self,
        weights: str = "yolov8s-worldv2.pt",
        imgsz: int = 320,
        conf: float = 0.30,
        device: str = "cpu",
        class_names: Sequence[str] | None = None,
        verbose: bool = False,
    ) -> None:
        self.weights = weights
        self.imgsz = int(imgsz)
        self.conf = float(conf)
        self.device = device
        self.verbose = verbose
        self._model = None
        self._prompts = [str(name).strip() for name in (class_names or []) if str(name).strip()]
        self._prompts_applied = False

    @property
    def model(self):
        if self._model is None:
            from ultralytics import YOLOWorld

            self._model = YOLOWorld(self.weights)
        if not self._prompts_applied:
            if self._prompts:
                self._model.set_classes(self._prompts)
            self._prompts_applied = True
        return self._model

    @property
    def prompts(self) -> list[str]:
        return list(self._prompts)

    def warmup(self) -> None:
        try:
            import numpy as np

            self.detect(np.zeros((self.imgsz, self.imgsz, 3), dtype=np.uint8))
        except Exception:
            pass

    def detect(self, frame) -> list[Detection]:
        results = self.model.predict(
            source=frame,
            imgsz=self.imgsz,
            conf=self.conf,
            device=self.device,
            verbose=False,
        )
        return _results_to_detections(results)

    def __call__(self, frame) -> list[Detection]:
        return self.detect(frame)


def _results_to_detections(results) -> list[Detection]:
    detections: list[Detection] = []
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None or len(boxes) == 0:
            continue
        names = getattr(result, "names", {}) or {}
        xyxy = boxes.xyxy.tolist()
        confs = boxes.conf.tolist()
        classes = boxes.cls.tolist()
        for coords, score, cls_id in zip(xyxy, confs, classes):
            cls_id = int(cls_id)
            label = str(names.get(cls_id, cls_id)) if isinstance(names, dict) else str(cls_id)
            detections.append(
                Detection(
                    cls=label,
                    conf=float(score),
                    x1=float(coords[0]),
                    y1=float(coords[1]),
                    x2=float(coords[2]),
                    y2=float(coords[3]),
                )
            )
    return detections


def make_detector(
    weights: str = "yolo11n.pt",
    imgsz: int = 320,
    conf: float = 0.35,
    device: str = "cpu",
    class_names: Sequence[str] | None = None,
):
    """Pick the right backend from the weights name.

    Any weights file whose stem contains ``world`` (e.g.
    ``yolov8s-worldv2.pt``) selects the open-vocabulary backend; everything
    else uses the fixed-class YOLO detector.
    """
    stem = Path(str(weights)).stem.lower()
    if "world" in stem:
        return WorldDetector(weights, imgsz, conf, device, class_names)
    return YoloDetector(weights, imgsz, conf, device, class_names)
