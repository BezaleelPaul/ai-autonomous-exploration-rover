"""Run recorder: run directories, CSV rows, trigger rules, summary, cap."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from software.dashboard import recorder as recorder_mod
from software.dashboard.controls import ArduinoLink, parse_telemetry_line
from software.dashboard.pilot import DecisionRecord
from software.dashboard.recorder import FIELDS, RunRecorder, _row_from
from software.utils.config_loader import load_config

ROOT = Path(__file__).resolve().parents[1]


class FakeFeed:
    def __init__(self) -> None:
        self.dets = [
            {
                "class_name": "bottle",
                "confidence": 0.9,
                "x1": 300,
                "y1": 200,
                "x2": 340,
                "y2": 280,
            }
        ]

    def snapshot(self):
        return np.zeros((480, 640, 3), dtype=np.uint8), list(self.dets)


def decision(command: str = "F", mode: str = "auto", **over) -> dict:
    base = {
        "at": 1.0,
        "mode": mode,
        "armed": mode == "auto",
        "proposed": command,
        "command": command,
        "allowed": command != "S",
        "steering_reason": "target centred and far enough",
        "safety_reason": "SAFE",
        "blockers": [],
        "distance_cm": 100.0,
        "target": "bottle",
        "confidence": 0.9,
        "area_ratio": 0.01,
        "zone": "CENTER",
        "target_present": True,
        "sent": command if mode == "auto" else None,
        "motors": [200, 200] if command == "F" else [0, 0],
        "overlay": "GO 200 PWM",
    }
    base.update(over)
    return base


@pytest.fixture()
def cfg(tmp_path) -> dict:
    cfg = load_config(str(ROOT / "config" / "config.yaml"))
    cfg["dashboard"]["record_dir"] = str(tmp_path / "runs")
    cfg["dashboard"]["record_every_s"] = 1.0
    return cfg


@pytest.fixture()
def rec(cfg) -> RunRecorder:
    return RunRecorder(cfg, FakeFeed(), None, None)


# ---- row normalisation ----------------------------------------------------


def test_row_from_maps_a_decision_record():
    record = DecisionRecord(
        at=5.0,
        mode="auto",
        armed=True,
        proposed="F",
        command="F",
        allowed=True,
        steering_reason="target centred and far enough",
        safety_reason="SAFE",
        blockers=(),
        distance_cm=80.0,
        target="bottle",
        confidence=0.9,
        area_ratio=0.01,
        zone="CENTER",
        target_present=True,
        sent="F",
        motors=(200, 200),
        overlay="GO 200 PWM",
    )
    row = _row_from(record)
    assert row["command"] == "F"
    assert row["motor_left"] == 200
    assert row["motor_right"] == 200
    assert row["blockers"] == ""
    assert row["distance_cm"] == 80.0


def test_row_from_joins_blockers_and_keeps_badges():
    row = _row_from(decision(blockers=["AI STALE", "SERIAL DOWN"], command="S"))
    assert row["blockers"] == "AI STALE|SERIAL DOWN"
    assert row["command"] == "S"


# ---- lifecycle ------------------------------------------------------------


def test_start_creates_a_dated_run_with_the_csv_header(rec: RunRecorder, tmp_path):
    path = rec.start()
    run = Path(path)
    assert run.is_dir()
    assert run.parent == tmp_path / "runs"
    with (run / "decisions.csv").open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert tuple(header) == FIELDS
    assert rec.status()["recording"] is True
    rec.stop()


def test_start_twice_keeps_the_same_directory(rec: RunRecorder):
    first = rec.start()
    second = rec.start()
    assert first == second
    rec.stop()


def test_record_before_start_is_a_silent_noop(rec: RunRecorder):
    assert rec.record(decision()) is False
    assert rec.status()["frames"] == 0
    assert rec.recording is False


def test_stop_writes_summary_and_is_idempotent(rec: RunRecorder):
    rec.start()
    rec.record(decision("F"), now=100.0)
    rec.record(decision("S", safety_reason="EMERGENCY_OBSTACLE"), now=100.1)
    rec.stop()
    run = Path(rec.status()["path"])
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    assert summary["decisions"] == 2
    assert summary["images"] >= 2
    assert summary["commands"]["F"] == 1
    assert summary["commands"]["S"] == 1
    assert any("STOP recording" in e for e in summary["events"])
    assert rec.recording is False
    rec.stop()  # second stop must not raise or duplicate
    assert rec.status()["recording"] is False


# ---- CSV rows -------------------------------------------------------------


def test_each_record_appends_a_csv_row(rec: RunRecorder):
    rec.start()
    rec.record(decision("F"), now=10.0)
    rec.record(decision("L", motors=[-200, 200]), now=10.1)
    rec.stop()
    run = Path(rec.status()["path"])
    with (run / "decisions.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert rows[0]["command"] == "F"
    assert rows[1]["command"] == "L"
    assert rows[1]["motor_left"] == "-200"
    assert rows[1]["safety_reason"] == "SAFE"


# ---- image triggers -------------------------------------------------------


def test_first_record_saves_a_frame(rec: RunRecorder):
    rec.start()
    assert rec.record(decision("F"), now=50.0) is True
    assert rec.frames == 1
    assert any(Path(rec.run_path).glob("frame_*.jpg"))
    rec.stop()


def test_unchanged_command_inside_the_window_saves_no_new_frame(rec: RunRecorder):
    rec.start()
    rec.record(decision("F"), now=50.0)
    rec.record(decision("F"), now=50.2)
    rec.record(decision("F"), now=50.4)
    assert rec.frames == 1
    assert rec.status()["decisions"] == 3
    rec.stop()


def test_command_change_saves_a_frame_and_logs_the_reason(rec: RunRecorder):
    rec.start()
    rec.record(decision("F"), now=50.0)
    rec.record(
        decision("S", safety_reason="EMERGENCY_OBSTACLE", motors=[0, 0]),
        now=50.2,
    )
    assert rec.frames == 2
    assert any(
        "command F -> S" in e and "EMERGENCY_OBSTACLE" in e
        for e in rec.status()["events"]
    )
    rec.stop()


def test_periodic_capture_respects_record_every_s(rec: RunRecorder):
    rec.start()
    rec.record(decision("F"), now=50.0)
    rec.record(decision("F"), now=50.5)  # 0.5 s < 1.0 s: skipped
    assert rec.frames == 1
    rec.record(decision("F"), now=51.6)  # 1.6 s after the last image: kept
    assert rec.frames == 2
    rec.stop()


def test_fresh_alert_triggers_a_capture(cfg):
    link = ArduinoLink("", mock=True)
    link.connect()
    rec = RunRecorder(cfg, FakeFeed(), None, link)
    rec.start()
    rec.record(decision("F"), now=70.0)
    assert rec.frames == 1
    parse_telemetry_line("ALERT:OBSTACLE dist=9.9cm cmd=F", link._state)
    rec.record(decision("F"), now=70.1)
    assert rec.frames == 2
    assert any("ALERT captured" in e for e in rec.status()["events"])
    rec.stop()


def test_frame_cap_stops_images_but_keeps_logging_csv(rec: RunRecorder, monkeypatch):
    monkeypatch.setattr(recorder_mod, "MAX_FRAMES", 2)
    rec.start()
    for i in range(4):
        rec.record(decision("F" if i % 2 == 0 else "S"), now=100.0 + i * 5)
    assert rec.frames == 2
    assert rec.status()["decisions"] == 4
    assert any("frame cap reached" in e for e in rec.status()["events"])
    assert rec.recording is True
    rec.stop()


def test_frame_trigger_is_skipped_without_a_frame(tmp_path):
    cfg = load_config(str(ROOT / "config" / "config.yaml"))
    cfg["dashboard"]["record_dir"] = str(tmp_path / "runs")

    class NoFeed:
        def snapshot(self):
            return None, []

    rec = RunRecorder(cfg, NoFeed(), None, None)
    rec.start()
    rec.record(decision("F"), now=10.0)
    assert rec.frames == 0
    assert rec.status()["decisions"] == 1
    rec.stop()


# ---- status ---------------------------------------------------------------


def test_events_are_bounded_and_returned_most_recent_first(rec: RunRecorder):
    rec.start()
    for i in range(200):
        rec.record(decision("F" if i % 2 == 0 else "S"), now=i * 10.0)
    body = rec.status(limit=3)
    assert len(body["events"]) <= 3
    assert len(rec.events) <= recorder_mod.MAX_EVENTS
    rec.stop()


def test_status_reports_the_configured_dir(rec: RunRecorder, cfg):
    assert rec.status()["dir"] == cfg["dashboard"]["record_dir"]
