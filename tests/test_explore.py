"""Explore roam loop + the Mars-rover-style mission report."""

from __future__ import annotations

from pathlib import Path

import pytest

from software.dashboard.deck_page import DECK_PAGE
from software.dashboard.explore import DONE, DRIVE, SCAN, TURN, Explorer
from software.dashboard.pilot import MODES, MissionPilot
from software.dashboard.report import build_report
from software.utils.config_loader import load_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def cfg() -> dict:
    return load_config(str(ROOT / "config" / "config.yaml"))


def make_explorer(**overrides) -> Explorer:
    base = {
        "blocked_cm": 40.0,
        "scan_s": 1.0,
        "turn_s": 0.5,
        "max_duration_s": 60.0,
        "max_turns": 4,
    }
    base.update(overrides)
    return Explorer(**base)


# ---- Explorer state machine ------------------------------------------------


def test_explorer_drives_while_clear():
    ex = make_explorer()
    ex.start(now=0.0)
    cmd, reason = ex.propose(now=0.1, distance_cm=120.0)
    assert cmd == "F"
    assert ex.state == DRIVE
    assert "explor" in reason


def test_explorer_scans_when_ultrasonic_blocked():
    ex = make_explorer()
    ex.start(now=0.0)
    cmd, reason = ex.propose(now=0.1, distance_cm=25.0)  # < blocked_cm
    assert cmd == "S"
    assert ex.state == SCAN
    assert "blocked" in reason


def test_explorer_scans_when_world_model_blocked():
    ex = make_explorer()
    ex.start(now=0.0)
    cmd, _ = ex.propose(now=0.1, distance_cm=120.0, world_blocked=True)
    assert cmd == "S"
    assert ex.state == SCAN


def test_explorer_turns_after_scan_dwell_then_resumes():
    ex = make_explorer()
    ex.start(now=0.0)
    ex.propose(now=0.1, distance_cm=25.0)  # -> SCAN
    cmd, _ = ex.propose(now=2.0, distance_cm=25.0)  # scan_s elapsed -> TURN
    assert cmd == "L"  # first pivot is left
    assert ex.state == TURN
    cmd, _ = ex.propose(now=2.2, distance_cm=25.0)  # still turning
    assert cmd == "L"
    cmd, _ = ex.propose(now=3.0, distance_cm=120.0)  # turn_s elapsed -> DRIVE
    assert cmd == "F"
    assert ex.state == DRIVE
    assert ex.turns == 1


def test_explorer_alternates_turn_direction():
    ex = make_explorer(max_turns=4)
    ex.start(now=0.0)
    seen = []
    for t in (0.1, 2.0, 3.0, 5.0, 6.0, 8.0):
        cmd, _ = ex.propose(now=t, distance_cm=25.0 if t in (0.1, 3.0, 6.0) else 120.0)
        if ex.state == TURN and cmd in ("L", "R") and (not seen or seen[-1] != cmd):
            seen.append(cmd)
    assert seen[0] == "L"
    assert "R" in seen


def test_explorer_stops_on_turn_budget():
    ex = make_explorer(max_turns=2)
    ex.start(now=0.0)
    # two full block->scan->turn cycles
    for start in (0.0, 10.0):
        ex.propose(now=start + 0.1, distance_cm=25.0)
        ex.propose(now=start + 2.0, distance_cm=25.0)
        ex.propose(now=start + 3.0, distance_cm=120.0)
    cmd, reason = ex.propose(now=20.0, distance_cm=120.0)
    assert cmd == "S"
    assert ex.state == DONE
    assert "budget" in reason


def test_explorer_stops_on_duration_budget():
    ex = make_explorer(max_duration_s=5.0)
    ex.start(now=0.0)
    cmd, reason = ex.propose(now=6.0, distance_cm=120.0)
    assert cmd == "S"
    assert ex.state == DONE
    assert "budget" in reason


def test_explorer_idle_before_start_and_after_stop():
    ex = make_explorer()
    cmd, _ = ex.propose(now=0.0, distance_cm=120.0)
    assert cmd == "S" and ex.state == DONE
    ex.start(now=0.0)
    ex.stop()
    cmd, _ = ex.propose(now=1.0, distance_cm=120.0)
    assert cmd == "S" and ex.state == DONE


def test_explorer_from_config_reads_shipped_keys(cfg):
    ex = Explorer.from_config(cfg)
    assert ex.blocked_cm == cfg["explore"]["blocked_cm"]
    assert ex.scan_s == cfg["explore"]["scan_s"]
    assert ex.turn_s == cfg["explore"]["turn_s"]
    assert ex.max_duration_s == cfg["explore"]["max_duration_s"]
    assert ex.max_turns == cfg["explore"]["max_turns"]


# ---- MissionPilot integration ---------------------------------------------


class _Feed:
    def __init__(self, world=None):
        self._world = world or {}

    def snapshot(self):
        import numpy as np

        return np.zeros((480, 640, 3), dtype=np.uint8), []

    def state(self) -> dict:
        return {"ai_age_s": 0.1, "world": self._world}


class _Link:
    def __init__(self, distance=100.0, connected=True):
        self._distance = distance
        self._connected = connected
        self.sent: list[str] = []

    def send(self, command: str) -> bool:
        self.sent.append(command)
        return self._connected

    def telemetry(self) -> dict:
        return {"connected": self._connected, "distance_cm": self._distance}


def test_pilot_accepts_explore_mode(cfg):
    pilot = MissionPilot(cfg, _Feed(), _Link())
    status = pilot.set_mode("explore")
    assert status["mode"] == "explore"
    assert "explore" in status["modes"]
    assert list(status["modes"]) == list(MODES)
    assert status["explore"]["state"] == DRIVE


def test_pilot_explore_drives_when_armed(cfg):
    import time

    pilot = MissionPilot(cfg, _Feed(), _Link(distance=100.0))
    pilot.set_mode("explore")
    # set_mode just sent STOP; motion needs the emit cooldown to elapse
    rec = pilot.tick(now=time.time() + 1.0)
    assert rec.mode == "explore"
    assert rec.armed is True
    assert rec.command == "F"
    assert rec.sent == "F"
    assert "explore" in rec.steering_reason


def test_pilot_explore_safety_still_gates(cfg):
    # explorer's own blocked_cm sits below the emergency band so it proposes
    # F at 12 cm; SafetyManager must still override to S (tier-1).
    pilot = MissionPilot(cfg, _Feed(), _Link(distance=12.0))
    pilot.set_mode("explore")
    pilot.explorer.blocked_cm = 10.0
    rec = pilot.tick(now=1000.0)
    assert rec.proposed == "F"
    assert rec.command == "S"
    assert "EMERGENCY" in rec.safety_reason


def test_pilot_explore_disarms_without_serial(cfg):
    pilot = MissionPilot(cfg, _Feed(), _Link(connected=False))
    pilot.set_mode("explore")
    rec = pilot.tick(now=1000.0)
    assert rec.armed is False
    assert rec.command == "S"
    assert "SERIAL" in rec.safety_reason


def test_pilot_explore_world_block_triggers_scan(cfg):
    pilot = MissionPilot(cfg, _Feed(world={"blocked": True}), _Link(distance=200.0))
    pilot.set_mode("explore")
    rec = pilot.tick(now=1000.0)
    assert rec.proposed == "S"
    assert pilot.explorer.state == SCAN


# ---- mission report --------------------------------------------------------


def test_build_report_renders_summary_world_and_events():
    md = build_report(
        duration_s=125.0,
        decisions=400,
        images=9,
        commands={"F": 200, "L": 80, "R": 60, "S": 60},
        events=["12:00:01 START recording", "12:01:00 ALERT captured"],
        world={
            "scene": "bottle, table in view",
            "facts": ["bottle center d=0.8±0.2m conf=0.91"],
            "objects": [{"label": "bottle"}],
            "path_state": "clear",
            "spec_rho_m": 0.12,
            "spec_verdict": "satisfied",
        },
        mode_mix={"explore": 350, "manual": 50},
        path="data/runs/demo",
    )
    assert "# MISSION REPORT" in md
    assert "2m 05s" in md
    assert "Decision ticks: 400" in md
    assert "F 50.0%" in md
    assert "bottle center" in md
    assert "Path verdict: clear" in md
    assert "rho=+0.12" in md
    assert "explore=350" in md
    assert "ALERT captured" in md


def test_build_report_degrades_with_no_world():
    md = build_report(duration_s=0.0, decisions=0, images=0)
    assert "# MISSION REPORT" in md
    assert "nothing recognised" in md
    assert "no commands sent" in md
    assert "no events" in md


# ---- recorder writes report.md ---------------------------------------------


def test_recorder_stop_writes_report_md(cfg, tmp_path):
    from software.dashboard.recorder import RunRecorder

    cfg = dict(cfg)
    cfg["dashboard"] = dict(cfg.get("dashboard", {}))
    cfg["dashboard"]["record_dir"] = str(tmp_path)
    rec = RunRecorder(cfg, feed=None, pilot=None, link=None)
    rec.start()
    rec.record(
        {
            "at": 1.0,
            "mode": "explore",
            "armed": True,
            "proposed": "F",
            "command": "F",
            "allowed": True,
            "steering_reason": "explore[drive]: exploring",
            "safety_reason": "SAFE",
            "blockers": [],
            "distance_cm": 90.0,
            "target": None,
            "confidence": 0.0,
            "area_ratio": 0.0,
            "zone": None,
            "target_present": False,
            "sent": "F",
            "motors": [200, 200],
            "overlay": "GO 200 PWM",
        }
    )
    rec.stop()
    run_dir = Path(rec.run_path)
    assert (run_dir / "summary.json").is_file()
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "# MISSION REPORT" in report
    assert "explore=1" in report


# ---- deck surface ----------------------------------------------------------


def test_deck_has_explore_button_and_report_link():
    assert 'data-mode="explore"' in DECK_PAGE
    assert 'id="exstate"' in DECK_PAGE
    assert 'href="/api/report"' in DECK_PAGE
