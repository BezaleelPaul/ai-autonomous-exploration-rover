"""Plugin framework: loading, isolation, hooks, and the YOLO-World labeler."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from software.ai.detection import Detection
from software.dashboard.deck_page import DECK_PAGE
from software.plugins import (
    VisionPlugin,
    load_plugins,
    merge_timings,
    run_detection_plugins,
    run_frame_plugins,
)
from software.plugins.world import WorldLabeler, box_iou
from software.plugins.world import create as create_world
from software.utils.config_loader import load_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def cfg() -> dict:
    return load_config(str(ROOT / "config" / "config.yaml"))


class Recorder(VisionPlugin):
    name = "rec"

    def __init__(self, fail_frame=False, fail_det=False):
        self.frames = []
        self.dets_seen = []
        self.fail_frame = fail_frame
        self.fail_det = fail_det

    def process_frame(self, frame):
        self.frames.append(frame)
        if self.fail_frame:
            raise RuntimeError("boom")
        return frame * 2

    def process_detections(self, frame, dets):
        self.dets_seen.append(list(dets))
        if self.fail_det:
            raise RuntimeError("boom")
        return [*dets, Detection("extra", 0.4, 1, 1, 2, 2)]


# ---- loading --------------------------------------------------------------


def test_no_plugins_enabled_by_default_shape(cfg):
    cfg["plugins"] = {"enabled": []}
    assert load_plugins(cfg) == []


def test_missing_plugins_section_is_fine():
    assert load_plugins({}) == []


def test_unknown_plugin_is_skipped_without_raising():
    assert load_plugins({"plugins": {"enabled": ["does_not_exist"]}}) == []


def test_plugin_names_are_sanitized():
    assert load_plugins({"plugins": {"enabled": ["../evil"]}}) == []
    assert load_plugins({"plugins": {"enabled": ["a;b"]}}) == []


def test_plugin_create_failure_is_isolated(monkeypatch):
    def boom(name):
        raise ImportError("nope")

    monkeypatch.setattr("software.plugins.importlib.import_module", boom)
    assert load_plugins({"plugins": {"enabled": ["world"]}}) == []


# ---- hooks ----------------------------------------------------------------


def test_frame_plugins_transform_and_record_timings():
    rec = Recorder()
    frame = np.ones((4, 4, 3), dtype=np.uint8)
    out, timings = run_frame_plugins([rec], frame)
    assert out[0, 0, 0] == 2
    assert "rec" in timings


def test_frame_plugin_exceptions_never_break_the_pipeline():
    rec = Recorder(fail_frame=True)
    frame = np.ones((4, 4, 3), dtype=np.uint8)
    out, timings = run_frame_plugins([rec], frame)
    assert out is frame  # original kept
    assert timings["rec"] >= 0.0


def test_detection_plugins_merge_and_isolate():
    rec = Recorder(fail_det=True)
    dets = [Detection("bottle", 0.9, 0, 0, 10, 10)]
    out, _timings = run_detection_plugins([rec], None, dets)
    assert out == dets  # failure keeps input
    rec2 = Recorder()
    out2, _ = run_detection_plugins([rec2], None, dets)
    assert [d.class_name for d in out2] == ["bottle", "extra"]


def test_merge_timings_sums_per_plugin():
    assert merge_timings({"world": 10.0}, {"world": 5.5, "x": 1.0}) == {
        "world": 15.5,
        "x": 1.0,
    }


# ---- world labeler --------------------------------------------------------


class FakeBox:
    def __init__(self, xyxy, conf=0.9, cls=0):
        self.cls = [cls]
        self.conf = [conf]
        self.xyxy = [list(xyxy)]


class FakeRes:
    def __init__(self, boxes):
        self.boxes = boxes
        self.names = {0: "pen"}


class FakeWorldModel:
    def __init__(self, boxes):
        self.boxes = boxes
        self.predicts = 0

    def predict(self, frame, **kwargs):
        self.predicts += 1
        return [FakeRes(self.boxes)]


def test_box_iou_extremes():
    a = Detection("x", 1, 0, 0, 10, 10)
    assert box_iou(a, Detection("y", 1, 0, 0, 10, 10)) == pytest.approx(1.0)
    assert box_iou(a, Detection("y", 1, 50, 50, 60, 60)) == 0.0


def test_world_drops_duplicates_and_adds_novel_objects():
    plugin = WorldLabeler(conf=0.25, every_n=1)
    model = FakeWorldModel(
        [
            FakeBox([10, 10, 20, 20]),  # overlaps existing -> dropped
            FakeBox([200, 200, 260, 260]),  # novel -> added
        ]
    )
    plugin._model = model
    coco = [Detection("bottle", 0.9, 10, 10, 22, 22)]
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    out = plugin.process_detections(frame, coco)
    assert [d.class_name for d in out] == ["bottle", "pen"]
    assert plugin.stats()["added"] == 1
    assert plugin.stats()["passes"] == 1


def test_world_every_n_gates_the_extra_pass():
    plugin = WorldLabeler(conf=0.25, every_n=2)
    plugin._model = FakeWorldModel([FakeBox([200, 200, 260, 260])])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    for _ in range(4):
        plugin.process_detections(frame, [])
    assert plugin._model.predicts == 2  # every 2nd of 4 calls
    assert plugin.stats()["calls"] == 4


def test_world_create_reads_plugin_config(cfg):
    cfg["plugins"]["world_conf"] = 0.4
    cfg["plugins"]["world_every_n"] = 3
    plugin = create_world(cfg)
    assert plugin.conf == pytest.approx(0.4)
    assert plugin.every_n == 3


def test_shipped_config_uses_a_single_detector_pass(cfg):
    # Only the COCO control model runs per frame. The YOLO-World `world`
    # second pass is opt-in so it cannot duplicate per-frame analysis.
    assert cfg["plugins"]["enabled"] == ["scenesense"]
    assert "world" not in cfg["plugins"]["enabled"]
    assert cfg["plugins"]["world_every_n"] == 2  # dial kept for opt-in use


def test_shipped_plugin_stack_loads_a_single_detector(cfg):
    assert [p.name for p in load_plugins(cfg)] == ["scenesense"]


# ---- pipeline + deck ------------------------------------------------------


def test_live_feed_state_reports_plugin_timings(cfg):
    from software.dashboard.live import LiveFeed

    feed = LiveFeed(cfg, source="mock")
    feed._plugin_ms = {"world": 123.4}
    state = feed.state()
    assert state["plugins"] == {"world": 123.4}
    assert state["plugins_stats"] == {}


def test_deck_page_shows_plugin_timings():
    assert "f.plugins" in DECK_PAGE


def test_live_feed_merges_plugin_added_detections(cfg):
    from software.dashboard.live import LiveFeed

    feed = LiveFeed(cfg, source="mock")
    feed._dets = [Detection("bottle", 0.9, 10, 10, 40, 40)]
    feed._extra_dets = [Detection("pen", 0.5, 50, 50, 90, 90)]
    state = feed.state()
    assert state["objects"] == 2
    assert {d["label"] for d in state["detections"]} == {"bottle", "pen"}
    _frame, snap = feed.snapshot()
    assert {d["class_name"] for d in snap} == {"bottle", "pen"}


def test_live_feed_reads_slow_interval_from_config(cfg):
    from software.dashboard.live import LiveFeed

    cfg["plugins"]["slow_interval_s"] = 1.25
    assert LiveFeed(cfg, source="mock")._slow_interval_s == pytest.approx(1.25)


def test_shipped_config_gives_the_plugin_worker_headroom(cfg):
    assert cfg["plugins"]["world_deadline_s"] >= 8.0
    assert cfg["plugins"]["slow_interval_s"] > 0


def test_plugin_worker_runs_detection_hooks_and_publishes_extras(cfg):
    import threading
    import time

    from software.dashboard.live import LiveFeed

    cfg["plugins"]["slow_interval_s"] = 0.0
    feed = LiveFeed(cfg, source="mock")
    feed._plugins = [Recorder()]
    feed._frame_ms = {"rec": 1.0}
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    base = Detection("bottle", 0.9, 1, 1, 4, 4)
    feed._plugin_job = (frame, [base])
    feed._running = True
    worker = threading.Thread(target=feed._plugin_loop, daemon=True)
    worker.start()
    deadline = time.time() + 2.0
    while time.time() < deadline and not feed._extra_dets:
        time.sleep(0.01)
    feed._running = False
    worker.join(timeout=1.0)
    assert [d.class_name for d in feed._extra_dets] == ["extra"]
    assert "rec" in feed._plugin_ms
    assert feed._plugin_job is None
