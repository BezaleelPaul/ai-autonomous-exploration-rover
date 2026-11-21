"""Vision adapter tests with fake captures/models (no OpenCV, no weights)."""

from __future__ import annotations

import time

import pytest

from support import read  # noqa: F401

from ai_rover.vision import LatestFrameSource, YoloDetector


# ---------------------------------------------------------------------------
# LatestFrameSource
# ---------------------------------------------------------------------------
class HealthyCapture:
    def __init__(self) -> None:
        self.released = False
        self.count = 0

    def isOpened(self):
        return True

    def read(self):
        self.count += 1
        return True, f"frame-{self.count}"

    def release(self):
        self.released = True


class DeadCapture:
    def isOpened(self):
        return False

    def read(self):  # pragma: no cover - never reached
        return False, None

    def release(self):
        return None


def wait_until(predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_source_delivers_latest_frame():
    capture = HealthyCapture()
    source = LatestFrameSource("http://cam/video", capture_factory=lambda _url: capture)
    try:
        source.start()
        assert wait_until(lambda: source.frames_read >= 3)
        frame = source.read(max_age=5.0)
        assert frame is not None
        assert str(frame.image).startswith("frame-")
    finally:
        source.stop()
    assert capture.released is True
    assert source.fps > 0


def test_source_reports_stale_frames():
    now = [100.0]
    capture = HealthyCapture()
    source = LatestFrameSource("http://cam", capture_factory=lambda _u: capture, clock=lambda: now[0])
    try:
        source.start()
        assert wait_until(lambda: source.read(max_age=1.0) is not None)
        now[0] += 10.0
        assert source.read(max_age=1.5) is None
        assert source.read_latest() is not None
        assert source.age() >= 9.0
    finally:
        source.stop()


def test_source_counts_reconnects():
    source = LatestFrameSource(
        "http://dead",
        reconnect_delay=0.01,
        capture_factory=lambda _u: DeadCapture(),
    )
    try:
        source.start()
        assert wait_until(lambda: source.reconnects >= 2)
    finally:
        source.stop()
    assert "cannot open" in source.last_error


def test_source_requires_a_url():
    with pytest.raises(ValueError):
        LatestFrameSource("")


# ---------------------------------------------------------------------------
# YoloDetector without ultralytics
# ---------------------------------------------------------------------------
class Tensor:
    def __init__(self, value):
        self.value = value

    def tolist(self):
        return self.value


class FakeBoxes:
    def __init__(self, rows):
        self.xyxy = Tensor([r[:4] for r in rows])
        self.conf = Tensor([r[4] for r in rows])
        self.cls = Tensor([r[5] for r in rows])

    def __len__(self):
        return len(self.conf.value)


class FakeResult:
    def __init__(self, rows, names):
        self.boxes = FakeBoxes(rows)
        self.names = names


class FakeModel:
    def __init__(self, rows, names=None):
        self.rows = rows
        self.names = names or {0: "person", 1: "chair"}
        self.calls = []

    def predict(self, **kwargs):
        self.calls.append(kwargs)
        return [FakeResult(self.rows, self.names)]


def test_detect_maps_boxes_to_detections():
    model = FakeModel([[10, 20, 110, 220, 0.91, 0], [5, 5, 50, 50, 0.42, 1]])
    detector = YoloDetector(weights="fake.pt", imgsz=320, conf=0.3)
    detector._model = model

    detections = detector.detect("frame")
    assert len(detections) == 2
    first = detections[0]
    assert first.cls == "person"
    assert first.conf == pytest.approx(0.91)
    assert (first.x1, first.y1, first.x2, first.y2) == (10, 20, 110, 220)
    assert detections[1].cls == "chair"
    assert model.calls[0]["imgsz"] == 320
    assert model.calls[0]["conf"] == 0.3


def test_detect_handles_empty_results():
    model = FakeModel([])
    detector = YoloDetector()
    detector._model = model
    assert detector.detect("frame") == []


def test_class_filter_resolution():
    detector = YoloDetector(class_names=["chair"])
    detector._model = FakeModel([], names={0: "person", 1: "chair"})
    detector._resolve_classes()
    assert detector.class_ids == [1]


def test_unknown_class_filter_raises():
    detector = YoloDetector(class_names=["unicorn"])
    detector._model = FakeModel([], names={0: "person"})
    with pytest.raises(ValueError):
        detector._resolve_classes()


def test_class_names_property():
    detector = YoloDetector()
    detector._model = FakeModel([], names={0: "person", 1: "chair"})
    assert detector.class_names == {0: "person", 1: "chair"}


def test_detector_callable():
    detector = YoloDetector()
    detector._model = FakeModel([[0, 0, 10, 10, 0.5, 0]])
    assert len(detector("frame")) == 1


# ---------------------------------------------------------------------------
# Open vocabulary (YOLO-World) backend
# ---------------------------------------------------------------------------
class FakeWorld:
    def __init__(self, prompts, names=None):
        self.prompts = prompts
        self.names = names or {i: name for i, name in enumerate(prompts)}
        self.set_calls = []

    def set_classes(self, classes):
        self.set_calls.append(list(classes))
        self.names = {i: name for i, name in enumerate(classes)}

    def predict(self, **kwargs):
        rows = [[5, 5, 50, 50, 0.8, i] for i in range(len(self.names))]
        return [FakeResult(rows, self.names)]


def test_world_detector_applies_prompts():
    from ai_rover.vision import WorldDetector

    detector = WorldDetector(class_names=["door", "cone"])
    fake = FakeWorld(["door", "cone"])
    detector._model = fake

    detections = detector.detect("frame")
    assert fake.set_calls == [["door", "cone"]]
    assert [d.cls for d in detections] == ["door", "cone"]
    assert detector.prompts == ["door", "cone"]


def test_world_detector_without_prompts_keeps_the_default_vocabulary():
    from ai_rover.vision import WorldDetector

    detector = WorldDetector()
    fake = FakeWorld([], names={0: "person"})
    detector._model = fake
    assert detector.detect("frame")[0].cls == "person"
    assert fake.set_calls == []


def test_world_detector_ignores_blank_prompts():
    from ai_rover.vision import WorldDetector

    detector = WorldDetector(class_names=[" door ", "", "  "])
    assert detector.prompts == ["door"]


def test_make_detector_selects_the_backend():
    from ai_rover.vision import WorldDetector, YoloDetector, make_detector

    assert isinstance(make_detector("yolov8s-worldv2.pt"), WorldDetector)
    assert isinstance(make_detector("models/rover6_best.pt"), YoloDetector)
    assert isinstance(make_detector("models/rover24_best.pt"), YoloDetector)
