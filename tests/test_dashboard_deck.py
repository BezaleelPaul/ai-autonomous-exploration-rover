"""Mission deck HTTP surface: page switch, why-chain, mode, run capture."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from software.dashboard.app import create_control_app
from software.dashboard.controls import ArduinoLink
from software.dashboard.deck_page import DECK_PAGE
from software.dashboard.pilot import MissionPilot
from software.dashboard.recorder import RunRecorder
from software.utils.config_loader import load_config

ROOT = Path(__file__).resolve().parents[1]


def det(conf: float = 0.9) -> dict:
    return {
        "class_name": "bottle",
        "confidence": conf,
        "x1": 300,
        "y1": 200,
        "x2": 340,
        "y2": 280,
        "track_id": 1,
    }


class FakeFeed:
    def __init__(self) -> None:
        self.dets = [det()]
        self.source = "mock"

    def snapshot(self):
        return np.zeros((480, 640, 3), dtype=np.uint8), list(self.dets)

    def state(self) -> dict:
        return {
            "ai_age_s": 0.1,
            "objects": len(self.dets),
            "detections": [
                {
                    "label": d["class_name"],
                    "conf": d["confidence"],
                    "id": d.get("track_id"),
                    "pos": "C",
                    "cx": 0,
                    "w": 0,
                }
                for d in self.dets
            ],
        }

    def jpeg(self) -> bytes:
        return b"\xff\xd8fakeframe\xff\xd9"

    def set_source(self, url: str) -> str:
        from software.perception_node.stream import validate_stream_url

        self.source = validate_stream_url(url)
        return self.source


@pytest.fixture()
def cfg(tmp_path) -> dict:
    cfg = load_config(str(ROOT / "config" / "config.yaml"))
    cfg["dashboard"]["record_dir"] = str(tmp_path / "runs")
    return cfg


@pytest.fixture()
def link() -> ArduinoLink:
    link = ArduinoLink("", mock=True)
    link.connect()
    return link


@pytest.fixture()
def feed() -> FakeFeed:
    return FakeFeed()


@pytest.fixture()
def pilot(cfg, feed, link) -> MissionPilot:
    return MissionPilot(cfg, feed, link)


# ---- page switch ----------------------------------------------------------


def test_index_serves_the_mission_deck_when_a_pilot_exists(pilot, feed, link, cfg):
    rec = RunRecorder(cfg, feed, pilot, link)
    app = create_control_app(feed, link, pilot=pilot, recorder=rec)
    res = app.test_client().get("/")
    assert res.status_code == 200
    assert b"MISSION DECK" in res.data
    assert b"/api/decision" in res.data
    assert b"/api/mode" in res.data


def test_index_keeps_the_original_control_page_without_a_pilot(feed, link):
    app = create_control_app(feed, link)
    res = app.test_client().get("/")
    assert b"CONTROL DECK" in res.data
    assert b"MISSION DECK" not in res.data


def test_decision_and_mode_routes_do_not_exist_without_a_pilot(feed, link):
    app = create_control_app(feed, link)
    assert app.test_client().get("/api/decision").status_code == 404
    assert app.test_client().post("/api/mode", json={"mode": "auto"}).status_code == 404


def test_recording_routes_do_not_exist_without_a_recorder(feed, link, pilot):
    app = create_control_app(feed, link, pilot=pilot)
    assert app.test_client().get("/api/recording").status_code == 404
    assert app.test_client().get("/api/events").status_code == 404


# ---- deck page content ----------------------------------------------------


def test_deck_page_exposes_the_mode_switch_and_arm_checklist():
    for token in (
        'data-mode="manual"',
        'data-mode="observe"',
        'data-mode="auto"',
        'id="blockers"',
        "ARMED",
        "/api/mode",
    ):
        assert token in DECK_PAGE, token


def test_deck_page_renders_the_two_motor_graphic():
    for token in ('id="lb"', 'id="rb"', 'id="lp"', 'id="rp"', "TANK STEER"):
        assert token in DECK_PAGE, token


def test_deck_page_polls_the_why_chain_and_shows_the_banner():
    assert 'id="banner"' in DECK_PAGE
    assert "/api/decision" in DECK_PAGE
    assert 'id="whylog"' in DECK_PAGE
    assert "BLOCKED" in DECK_PAGE and "DISARMED" in DECK_PAGE


def test_deck_page_keeps_the_drive_pad_and_keyboard():
    for token in ('data-cmd="F"', 'data-key="w"', "keydown", "/api/cmd"):
        assert token in DECK_PAGE, token


# ---- /api/decision --------------------------------------------------------


def test_api_decision_reports_mode_and_empty_history_before_ticks(pilot, feed, link):
    app = create_control_app(feed, link, pilot=pilot)
    body = app.test_client().get("/api/decision").get_json()
    assert body["mode"] == "manual"
    assert body["modes"] == ["manual", "auto", "observe", "explore"]
    assert body["decision"] is None
    assert body["history"] == []


def test_api_decision_carries_the_full_chain_after_a_tick(pilot, feed, link):
    pilot.tick()
    app = create_control_app(feed, link, pilot=pilot)
    body = app.test_client().get("/api/decision").get_json()
    decision = body["decision"]
    assert decision["mode"] == "manual"
    assert decision["command"] == "S"
    assert decision["motors"] == [0, 0]
    assert decision["steering_reason"]
    assert decision["safety_reason"].startswith("MANUAL")
    assert len(body["history"]) == 1


def test_api_decision_survives_a_broken_pilot(feed, link, cfg):
    class BrokenPilot:
        def status(self):
            raise RuntimeError("pilot exploded")

    app = create_control_app(feed, link, pilot=BrokenPilot())
    res = app.test_client().get("/api/decision")
    assert res.status_code == 500
    assert "pilot exploded" in res.get_json()["error"]


# ---- /api/mode ------------------------------------------------------------


@pytest.mark.parametrize("mode", ["manual", "auto", "observe"])
def test_api_mode_switches_through_every_valid_mode(pilot, feed, link, mode):
    app = create_control_app(feed, link, pilot=pilot)
    res = app.test_client().post("/api/mode", json={"mode": mode})
    assert res.status_code == 200
    assert res.get_json()["mode"] == mode
    assert app.test_client().get("/api/decision").get_json()["mode"] == mode


@pytest.mark.parametrize("bad", ["", "drift", "AUTO!", "1"])
def test_api_mode_rejects_unknown_modes_with_400(pilot, feed, link, bad):
    app = create_control_app(feed, link, pilot=pilot)
    res = app.test_client().post("/api/mode", json={"mode": bad})
    assert res.status_code == 400
    assert res.get_json()["ok"] is False
    assert pilot.mode == "manual"


def test_api_mode_accepts_a_query_string_for_the_pad_js(pilot, feed, link):
    app = create_control_app(feed, link, pilot=pilot)
    res = app.test_client().post("/api/mode?mode=observe")
    assert res.status_code == 200
    assert res.get_json()["mode"] == "observe"


# ---- run recording --------------------------------------------------------


def test_post_recording_starts_and_stops_a_run(feed, link, pilot, cfg):
    rec = RunRecorder(cfg, feed, pilot, link)
    app = create_control_app(feed, link, pilot=pilot, recorder=rec)
    client = app.test_client()
    off = client.get("/api/recording").get_json()
    assert off["recording"] is False
    on = client.post("/api/recording", json={"on": True}).get_json()
    assert on["recording"] is True
    assert on["path"] and Path(on["path"]).is_dir()
    assert (Path(on["path"]) / "decisions.csv").is_file()
    again = client.post("/api/recording", json={"on": True}).get_json()
    assert again["path"] == on["path"]  # idempotent, no second directory
    stopped = client.post("/api/recording", json={"on": False}).get_json()
    assert stopped["recording"] is False
    assert (Path(on["path"]) / "summary.json").is_file()


def test_api_events_lists_recorder_activity(feed, link, pilot, cfg):
    rec = RunRecorder(cfg, feed, pilot, link)
    rec.start()
    app = create_control_app(feed, link, pilot=pilot, recorder=rec)
    body = app.test_client().get("/api/events?limit=5").get_json()
    assert body["recording"] is True
    assert any("START recording" in e for e in body["events"])
    assert body["decisions"] == 0
    rec.stop()


def test_api_events_limit_is_clamped(feed, link, pilot, cfg):
    rec = RunRecorder(cfg, feed, pilot, link)
    rec.start()
    app = create_control_app(feed, link, pilot=pilot, recorder=rec)
    body = app.test_client().get("/api/events?limit=banana").get_json()
    assert isinstance(body["events"], list)
    rec.stop()


def test_recorder_captures_pilot_ticks_through_on_tick(feed, link, cfg):
    rec = RunRecorder(cfg, feed, None, link)
    pilot = MissionPilot(cfg, feed, link, on_tick=rec.record)
    rec.start()
    app = create_control_app(feed, link, pilot=pilot, recorder=rec)
    pilot.tick()
    pilot.set_mode("observe")
    pilot.tick()
    body = app.test_client().get("/api/recording").get_json()
    assert body["decisions"] == 2
    assert body["frames"] >= 1
    rec.stop()


# ---- runtime stream URL switch -------------------------------------------


def test_stream_switch_repoints_the_feed(feed, link, pilot):
    app = create_control_app(feed, link, pilot=pilot)
    res = app.test_client().post(
        "/api/stream", json={"url": "http://192.168.1.77:8080/video"}
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert body["source"] == "http://192.168.1.77:8080/video"
    assert feed.source == "http://192.168.1.77:8080/video"


def test_stream_switch_completes_a_bare_origin(feed, link, pilot):
    app = create_control_app(feed, link, pilot=pilot)
    body = (
        app.test_client()
        .post("/api/stream", json={"url": "http://192.168.1.77:8080"})
        .get_json()
    )
    assert body["source"] == "http://192.168.1.77:8080/video"


def test_stream_switch_rejects_garbage_with_400(feed, link, pilot):
    app = create_control_app(feed, link, pilot=pilot)
    res = app.test_client().post("/api/stream", json={"url": "not-a-url"})
    assert res.status_code == 400
    assert res.get_json()["ok"] is False
    assert feed.source == "mock"


def test_stream_switch_requires_a_url(feed, link, pilot):
    app = create_control_app(feed, link, pilot=pilot)
    assert app.test_client().post("/api/stream", json={}).status_code == 400
    assert app.test_client().post("/api/stream").status_code == 400


def test_deck_page_has_the_stream_url_input():
    for token in ('id="camurl"', 'id="camset"', 'id="cammsg"', "/api/stream"):
        assert token in DECK_PAGE, token


def test_live_feed_set_source_validates_before_opening(cfg):
    from software.dashboard.live import LiveFeed

    feed = LiveFeed(cfg, source="mock")
    with pytest.raises(ValueError):
        feed.set_source("ftp://nope")
    assert feed.source == "mock"


# ---- multi-object readout -------------------------------------------------


def test_deck_page_has_the_multi_object_chips():
    for token in ('id="chips"', 'className="chip"', "detections"):
        assert token in DECK_PAGE, token


def test_api_state_lists_every_detection(feed, link, pilot):
    feed.dets.append(
        {
            "class_name": "cup",
            "confidence": 0.55,
            "x1": 10,
            "y1": 10,
            "x2": 40,
            "y2": 40,
            "track_id": 2,
        }
    )
    app = create_control_app(feed, link, pilot=pilot)
    body = app.test_client().get("/api/state").get_json()
    labels = [d["label"] for d in body["feed"]["detections"]]
    assert labels == ["bottle", "cup"]
    assert body["feed"]["objects"] == 2
