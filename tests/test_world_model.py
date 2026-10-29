"""World model logic (space/motion/relations) + the scenesense plugin."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from software.ai.detection import Detection
from software.ai.world_model import (
    InverseDepthCalibrator,
    WorldModel,
    band_of,
    band_of_metric,
    ground_distance_m,
    side_of,
)
from software.dashboard.deck_page import DECK_PAGE
from software.plugins.scenesense import (
    METRIC_DEPTH_MODEL,
    SceneSense,
    create,
    depth_to_metric_map,
    depth_to_score_map,
)
from software.utils.config_loader import load_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def cfg() -> dict:
    return load_config(str(ROOT / "config" / "config.yaml"))


def det(name, x1, y1, x2, y2, conf=0.9, tid=None):
    return Detection(name, conf, x1, y1, x2, y2, track_id=tid)


# ---- helpers --------------------------------------------------------------


def test_side_of_and_band_of():
    assert side_of(50, 640) == "left"
    assert side_of(320, 640) == "center"
    assert side_of(600, 640) == "right"
    assert band_of(0.9) == "near"
    assert band_of(0.5) == "mid"
    assert band_of(0.1) == "far"


# ---- spatial facts --------------------------------------------------------


def test_update_produces_scene_facts_and_objects():
    m = WorldModel()
    world = m.update(
        [
            det("bottle", 20, 200, 80, 380, tid=1),
            det("person", 400, 50, 620, 450, tid=2),
        ]
    )
    assert "bottle" in world["scene"] and "person" in world["scene"]
    assert any(f.startswith("bottle left") for f in world["facts"])
    assert any(f.startswith("person right") for f in world["facts"])
    assert world["blocked"] is False
    json.dumps(world)  # JSON-safe for /api/state


def test_on_relation_when_small_box_sits_in_big_one():
    m = WorldModel()
    world = m.update(
        [det("table", 100, 100, 500, 400, tid=1), det("cup", 200, 180, 280, 260, tid=2)]
    )
    cup = next(o for o in world["objects"] if o["label"] == "cup")
    assert cup["on"] == "table"
    assert any(f.startswith("cup") and "on table" in f for f in world["facts"])


def test_on_relation_rejected_when_depths_disagree():
    m = WorldModel()
    depth = np.full((480, 640), 0.2, dtype=np.float32)
    depth[180:260, 200:280] = 0.95  # cup patch much closer than table (0.2)
    world = m.update(
        [
            det("table", 100, 100, 500, 400, tid=1),
            det("cup", 200, 180, 280, 260, tid=2),
        ],
        depth_map=depth,
    )
    cup = next(o for o in world["objects"] if o["label"] == "cup")
    assert "on" not in cup


def test_depth_bands_from_the_map():
    m = WorldModel()
    depth = np.zeros((480, 640), dtype=np.float32)
    depth[:, :320] = 0.9  # left object very close
    depth[:, 320:] = 0.1  # right object far
    world = m.update(
        [det("bottle", 10, 10, 100, 100, tid=1), det("car", 400, 10, 600, 300, tid=2)],
        depth_map=depth,
    )
    by = {o["label"]: o for o in world["objects"]}
    assert by["bottle"]["band"] == "near"
    assert by["car"]["band"] == "far"
    assert world["depth"] == "on"


def test_approaching_from_box_growth():
    m = WorldModel()
    # three updates so the KF velocity estimate is established
    m.update([det("person", 300, 200, 340, 300, tid=7)], now=100.0)
    m.update([det("person", 290, 190, 350, 320, tid=7)], now=100.5)
    world = m.update([det("person", 280, 180, 360, 340, tid=7)], now=101.0)
    person = next(o for o in world["objects"] if o["label"] == "person")
    assert person["motion"] == "approaching"


def test_approaching_from_depth_increase():
    m = WorldModel()
    far = np.full((480, 640), 0.4, dtype=np.float32)
    near = np.full((480, 640), 0.9, dtype=np.float32)
    m.update([det("dog", 100, 100, 200, 200, tid=3)], now=50.0, depth_map=far)
    world = m.update([det("dog", 100, 100, 200, 200, tid=3)], now=51.0, depth_map=near)
    dog = next(o for o in world["objects"] if o["label"] == "dog")
    assert dog["motion"] == "approaching"


def test_blocked_center_near_and_clear_when_empty():
    m = WorldModel()
    depth = np.full((480, 640), 0.9, dtype=np.float32)
    # without calibration, center-near is UNCERTAIN (conservative, not blocked)
    world = m.update(
        [det("person", 280, 100, 360, 400, tid=1)], now=10.0, depth_map=depth
    )
    assert world["path_state"] == "uncertain"
    assert world["blocked"] is False
    # track older than history_s (5s) is pruned when it stops re-appearing
    cleared = m.update([], now=106.0)
    assert cleared["path_state"] == "clear"
    assert cleared["blocked"] is False


def test_blocked_when_calibration_places_interval_below_margin():
    m = WorldModel(clear_margin_m=0.5)
    depth = np.full((480, 640), 0.9, dtype=np.float32)
    # seed the calibrator: score spread across [0.5, 0.95] all mapping to
    # 0.3 m — hi = 0.3 + 2*sigma = 0.4 m stays under the 0.5 m margin
    for s in (0.50, 0.60, 0.70, 0.80, 0.90, 0.95):
        m.calibrator.observe(s, 0.3)
    assert m.calibrator.ready
    world = m.update(
        [det("person", 280, 100, 360, 400, tid=1)], now=10.0, depth_map=depth
    )
    person = next(o for o in world["objects"] if o["label"] == "person")
    assert person["dist_m"] is not None
    assert person["dist_hi_m"] < 0.5
    assert world["path_state"] == "blocked"
    assert world["blocked"] is True


def test_history_is_pruned():
    m = WorldModel(history_s=2.0)
    m.update([det("bottle", 1, 1, 10, 10, tid=1)], now=100.0)
    world = m.update([], now=103.0)
    assert world["objects"] == []


# ---- scenesense plugin ----------------------------------------------------


def fake_depth_factory(Counter=None):
    import PIL.Image

    def factory(model_name):
        def pipe(image):
            if Counter is not None:
                Counter["n"] += 1
            arr = np.linspace(0, 255, 64 * 64, dtype=np.uint8).reshape(64, 64)
            return {"depth": PIL.Image.fromarray(arr)}

        return pipe

    return factory


def test_depth_to_score_map_normalises():
    import PIL.Image

    arr = np.array([[0, 127], [64, 255]], dtype=np.uint8)
    scores = depth_to_score_map({"depth": PIL.Image.fromarray(arr)})
    assert float(scores.min()) == pytest.approx(0.0)
    assert float(scores.max()) == pytest.approx(1.0)


def test_scenesense_runs_every_nth_pass_and_fills_world():
    counter = {"n": 0}
    plugin = SceneSense(every_n=2, pipeline_factory=fake_depth_factory(counter))
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    dets = [det("bottle", 10, 10, 100, 100, tid=1)]
    for _ in range(4):
        out = plugin.process_detections(frame, dets)
    assert out == dets  # detections untouched
    assert counter["n"] == 2  # depth ran on 2 of 4 passes
    world = plugin.world_state()
    assert world["depth"] == "on"
    assert any(f.startswith("bottle") for f in world["facts"])


def test_scenesense_degrades_when_depth_load_fails():
    def broken_factory(model_name):
        raise ImportError("no model")

    plugin = SceneSense(every_n=1, pipeline_factory=broken_factory)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    dets = [det("bottle", 10, 10, 100, 100, tid=1)]
    assert plugin.process_detections(frame, dets) == dets
    assert plugin.world_state()["depth"] == "off"
    assert any(f.startswith("bottle") for f in plugin.world_state()["facts"])
    assert plugin.stats()["passes"] == 1


def test_scenesense_create_reads_config(cfg):
    cfg["plugins"]["scenesense_every_n"] = 3
    assert create(cfg).every_n == 3


def test_shipped_config_enables_scenesense_only(cfg):
    # One detector pass: scenesense (depth + world model) is on; the
    # YOLO-World second detector is opt-in (see test_plugins).
    assert cfg["plugins"]["enabled"] == ["scenesense"]


def test_scenesense_depth_model_override_wins():
    seen = {}

    def factory(name):
        seen["name"] = name
        return lambda image: {"depth": image}

    plugin = SceneSense(pipeline_factory=factory, model_name="custom/Depth-Test")
    plugin._ensure_pipe()
    assert seen["name"] == "custom/Depth-Test"


def test_scenesense_default_model_follows_metric_flag():
    from software.plugins.scenesense import DEPTH_MODEL

    relative = {}
    SceneSense(
        pipeline_factory=lambda n: relative.setdefault("name", n), metric=False
    )._ensure_pipe()
    assert relative["name"] == DEPTH_MODEL

    metric = {}
    SceneSense(
        pipeline_factory=lambda n: metric.setdefault("name", n), metric=True
    )._ensure_pipe()
    assert metric["name"] == METRIC_DEPTH_MODEL


def test_scenesense_stats_flag_the_loading_window():
    from software.plugins.scenesense import DEPTH_MODEL

    plugin = SceneSense(pipeline_factory=lambda n: None, every_n=1)
    plugin._passes = 1  # a pass started but the depth pipe is not built yet
    assert plugin.stats()["loading"] is True
    plugin._pipe = object()
    assert plugin.stats()["loading"] is False
    assert plugin.stats()["model"] == DEPTH_MODEL


# ---- pipeline + deck ------------------------------------------------------


def test_live_feed_state_carries_world(cfg):
    from software.dashboard.live import LiveFeed

    feed = LiveFeed(cfg, source="mock")
    assert feed.state()["world"] == {}


def test_deck_page_has_the_surroundings_card():
    for token in (
        "SURROUNDINGS",
        'id="wfacts"',
        'id="wpath"',
        'id="wscene"',
        "feed.world",
        'id="wspec"',
        'id="wdegr"',
    ):
        assert token in DECK_PAGE, token


# ---- calibrator -----------------------------------------------------------


def test_calibrator_needs_pairs_and_spread():
    cal = InverseDepthCalibrator(min_pairs=4, min_spread=0.08)
    for s in (0.5, 0.52, 0.54, 0.56):  # enough pairs, too little spread
        cal.observe(s, 1.0)
    assert not cal.ready
    for s in (0.5, 0.6, 0.7, 0.8):  # spread now sufficient
        cal.observe(s, 1.0)
    assert cal.ready


def test_calibrator_recovers_inverse_depth_line():
    """Scores on 1/d = 2·s + 0.5 must be recovered by the fit."""
    cal = InverseDepthCalibrator()
    for s in (0.3, 0.45, 0.6, 0.75, 0.9):
        inv = 2.0 * s + 0.5
        cal.observe(s, 1.0 / inv)
    assert cal.ready
    dist, sigma = cal.predict(0.6)
    assert dist == pytest.approx(1.0 / 1.7, rel=0.05)
    assert sigma is not None and sigma >= 0.05


def test_calibrator_rejects_out_of_range():
    cal = InverseDepthCalibrator()
    cal.observe(0.5, 999.0)  # distance outside 0-20 m
    cal.observe(1.5, 1.0)  # score outside 0-1
    assert cal.pairs_used == 0


def test_calibration_from_ultrasonic_stream():
    """Live updates with a centred object + ultrasonic must ready the fit."""
    m = WorldModel()
    depth = np.full((480, 640), 0.5, dtype=np.float32)
    for i, cm in enumerate((100, 90, 80, 70, 60, 50)):
        depth[:, :] = 0.4 + i * 0.05
        m.update(
            [det("bottle", 290, 150, 350, 350, tid=1)],
            now=10.0 + i,
            depth_map=depth,
            distance_cm=cm,
        )
    assert m.calibrator.ready


def test_metric_interval_emitted_when_calibrated():
    m = WorldModel(k_sigma=2.0)
    for s in (0.5, 0.6, 0.7, 0.8, 0.9):
        m.calibrator.observe(s, 0.8)  # 1/d = 1.25 constant
    depth = np.full((480, 640), 0.7, dtype=np.float32)
    world = m.update([det("bottle", 10, 10, 100, 100, tid=1)], now=5.0, depth_map=depth)
    obj = world["objects"][0]
    assert obj["dist_m"] == pytest.approx(0.8, rel=0.1)
    assert obj["dist_lo_m"] < obj["dist_m"] < obj["dist_hi_m"]


# ---- ground-plane fallback ------------------------------------------------


def test_ground_distance_pinhole():
    """Floor point below the horizon gets a metric distance; above → None."""
    d = ground_distance_m(
        400.0, height_m=0.15, focal_px=600.0, pitch_deg=0.0, frame_h=480
    )
    assert d is not None and 0.1 < d < 3.0
    above = ground_distance_m(
        100.0, height_m=0.15, focal_px=600.0, pitch_deg=0.0, frame_h=480
    )
    assert above is None  # ray at/below horizon: no floor hit


def test_ground_distance_disabled_when_height_zero():
    assert (
        ground_distance_m(
            400.0, height_m=0.0, focal_px=600.0, pitch_deg=0.0, frame_h=480
        )
        is None
    )


def test_ground_plane_used_when_calibration_absent():
    m = WorldModel(ground={"height_m": 0.15, "focal_px": 600.0, "pitch_deg": 0.0})
    world = m.update([det("bottle", 280, 300, 360, 420, tid=1)], now=5.0)
    obj = world["objects"][0]
    assert obj["dist_m"] is not None  # floor-standing box got a metric estimate


# ---- watchdog + STL -------------------------------------------------------


def test_watchdog_flags_stale_world():
    m = WorldModel(deadline_s=1.5)
    assert m.status(now=0.0)["degraded"] is True  # never updated
    m.update([], now=10.0)
    assert m.status(now=10.5)["degraded"] is False
    assert m.status(now=12.0)["degraded"] is True  # 2 s stale > 1.5 deadline
    assert m.status(now=12.0)["age_s"] == pytest.approx(2.0)


def test_stl_violated_when_ultrasonic_under_margin():
    m = WorldModel(clear_margin_m=0.5, spec_window_s=2.0)
    m.update([], now=10.0, distance_cm=90)
    world = m.update([], now=11.0, distance_cm=30)  # 0.3 m < 0.5 m margin
    assert world["spec_rho_m"] == pytest.approx(-0.2, abs=0.05)
    assert world["spec_verdict"] == "violated"


def test_stl_satisfied_when_ultrasonic_clear():
    m = WorldModel(clear_margin_m=0.5, spec_window_s=2.0)
    m.update([], now=10.0, distance_cm=90)
    world = m.update([], now=11.0, distance_cm=120)
    assert world["spec_rho_m"] is not None and world["spec_rho_m"] > 0
    assert world["spec_verdict"] == "satisfied"


def test_stl_falls_back_to_metric_intervals():
    """No ultrasonic: the nearest metric interval's lower bound scores the spec."""
    m = WorldModel(clear_margin_m=0.5)
    for s in (0.5, 0.6, 0.7, 0.8, 0.9):
        m.calibrator.observe(s, 0.3)  # everything at 0.3 m < 0.5 margin
    depth = np.full((480, 640), 0.7, dtype=np.float32)
    world = m.update([det("bottle", 10, 10, 100, 100, tid=1)], now=5.0, depth_map=depth)
    assert world["spec_rho_m"] is not None and world["spec_rho_m"] < 0


# ---- metric depth (Depth-Anything-V2 metric checkpoint) -------------------


def test_band_of_metric_cuts():
    assert band_of_metric(0.8) == "near"
    assert band_of_metric(1.5) == "mid"
    assert band_of_metric(3.0) == "far"


def test_depth_to_metric_map_reads_predicted_depth():
    arr = np.array([[0.4, 1.2], [2.5, 0.9]], dtype=np.float32)
    out = depth_to_metric_map({"predicted_depth": arr, "depth": None})
    assert out is not None
    assert float(out[0, 1]) == pytest.approx(1.2)
    assert depth_to_metric_map({"depth": None}) is None


def test_metric_mode_uses_metres_and_skips_calibrator():
    m = WorldModel(metric=True)
    depth = np.full((480, 640), 1.5, dtype=np.float32)
    for i in range(5):
        world = m.update(
            [det("bottle", 10, 10, 100, 100, tid=1)],
            now=5.0 + i,
            depth_map=depth,
            distance_cm=90,  # present, but metric mode must not fit it
        )
    assert not m.calibrator.ready
    assert world["calibrated"] is True  # metric depth is absolute by construction
    obj = world["objects"][0]
    assert obj["dist_m"] == pytest.approx(1.5, abs=0.01)
    assert obj["band"] == "mid"  # 1.0 < 1.5 <= 2.5 m


def test_metric_mode_motion_uses_metre_delta():
    m = WorldModel(metric=True)
    far = np.full((480, 640), 1.0, dtype=np.float32)
    near = np.full((480, 640), 1.3, dtype=np.float32)
    m.update([det("dog", 100, 100, 200, 200, tid=3)], now=50.0, depth_map=far)
    world = m.update([det("dog", 100, 100, 200, 200, tid=3)], now=51.0, depth_map=near)
    assert world["objects"][0]["motion"] == "approaching"


def fake_metric_factory(Counter=None):
    def factory(model_name):
        def pipe(image):
            if Counter is not None:
                Counter["n"] += 1
            arr = np.full((64, 64), 1.5, dtype=np.float32)
            return {"predicted_depth": arr, "depth": None}

        return pipe

    return factory


def test_scenesense_metric_mode_reports_metres():
    plugin = SceneSense(every_n=1, pipeline_factory=fake_metric_factory(), metric=True)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    dets = [det("bottle", 10, 10, 100, 100, tid=1)]
    assert plugin.process_detections(frame, dets) == dets
    world = plugin.world_state()
    assert world["depth"] == "on"
    assert world["calibrated"] is True
    assert world["objects"][0]["dist_m"] == pytest.approx(1.5, abs=0.01)
    assert plugin.model_name == METRIC_DEPTH_MODEL


def test_scenesense_create_reads_metric_config(cfg):
    cfg["plugins"]["scenesense_metric_depth"] = True
    plugin = create(cfg)
    assert plugin.metric is True
    assert plugin.model.metric is True
    # empty scenesense_depth_model -> metric checkpoint is the mode default
    assert plugin.model_name == METRIC_DEPTH_MODEL
