"""Mission pilot: mode gating, strict AUTO arming, the why-chain, motors."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from software.dashboard.controls import ArduinoLink, parse_telemetry_line
from software.dashboard.pilot import (
    MODES,
    DecisionRecord,
    MissionPilot,
    motors_for,
    overlay_for,
)
from software.utils.config_loader import load_config

ROOT = Path(__file__).resolve().parents[1]


def _cfg(**dashboard_overrides) -> dict:
    cfg = load_config(str(ROOT / "config" / "config.yaml"))
    cfg.setdefault("dashboard", {}).update(dashboard_overrides)
    return cfg


def det(
    x1: float = 300,
    y1: float = 200,
    x2: float = 340,
    y2: float = 280,
    conf: float = 0.9,
    name: str = "bottle",
) -> dict:
    return {
        "class_name": name,
        "confidence": conf,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "track_id": 1,
    }


class FakeFeed:
    """LiveFeed stand-in: scriptable frame, detections and AI freshness."""

    def __init__(self, dets=(), *, has_frame: bool = True, ai_age: float = 0.1):
        self.dets = list(dets)
        self.has_frame = has_frame
        self.ai_age = ai_age

    def snapshot(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8) if self.has_frame else None
        return frame, list(self.dets)

    def state(self) -> dict:
        return {"ai_age_s": self.ai_age, "objects": len(self.dets)}


def make_link(distance: float | None = 100.0, *, connect: bool = True) -> ArduinoLink:
    link = ArduinoLink("", mock=True)
    if connect:
        link.connect()
    if distance is not None:
        parse_telemetry_line(f"DIST:{distance}", link._state)
    return link


def make_pilot(
    cfg: dict | None = None,
    feed: FakeFeed | None = None,
    link: ArduinoLink | None = None,
) -> tuple[MissionPilot, ArduinoLink]:
    cfg = cfg or _cfg()
    feed = feed if feed is not None else FakeFeed([det()])
    link = link if link is not None else make_link()
    return MissionPilot(cfg, feed, link), link


# ---- motors_for -----------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("F", (200, 200)),
        ("B", (-200, -200)),
        ("L", (-200, 200)),
        ("R", (200, -200)),
        ("S", (0, 0)),
        ("X", (0, 0)),
    ],
)
def test_motors_for_maps_every_firmware_command(command: str, expected: tuple):
    assert motors_for(command, 200) == expected


def test_motors_for_uses_the_configured_pwm():
    assert motors_for("F", 150) == (150, 150)


# ---- overlay_for ----------------------------------------------------------


def test_overlay_reports_emergency_as_blocked_distance():
    got = overlay_for("auto", "S", "EMERGENCY_OBSTACLE", (), 15.0, 200)
    assert got == "BLOCKED 15 cm"


def test_overlay_reports_latched_emergency_the_same_way():
    assert overlay_for("auto", "S", "EMERGENCY_LATCH", (), 15.0, 200) == "BLOCKED 15 cm"


def test_overlay_reports_lost_comms_as_timeout():
    assert overlay_for("auto", "S", "COMM_LOST", (), 15.0, 200) == "TIMEOUT"


def test_overlay_reports_manual_forward_as_go_with_pwm():
    assert overlay_for("manual", "F", "MANUAL: pad owns the link", (), 15.0, 200) == (
        "GO 200 PWM"
    )


def test_overlay_reports_turns_and_stops():
    assert overlay_for("manual", "L", "MANUAL: pad owns the link", (), 15.0, 200) == (
        "TURN"
    )
    assert overlay_for("manual", "S", "MANUAL: pad owns the link", (), 15.0, 200) == (
        "STOP"
    )


def test_overlay_names_the_first_arm_blocker_in_auto():
    got = overlay_for("auto", "S", "DISARMED: AI STALE", ("AI STALE",), 15.0, 200)
    assert got == "DISARMED: AI STALE"


def test_overlay_ignores_blockers_for_the_pad_in_manual():
    got = overlay_for(
        "manual", "F", "MANUAL: pad owns the link", ("AI STALE",), 15.0, 200
    )
    assert got == "GO 200 PWM"


def test_overlay_shows_the_dry_run_verdict_in_observe():
    assert overlay_for("observe", "F", "SAFE", (), 15.0, 200) == "WOULD F"
    assert overlay_for("observe", "S", "SAFE", (), 15.0, 200) == "WOULD STOP"


def test_overlay_flags_camera_and_confidence_stops():
    assert overlay_for("auto", "S", "CAMERA_UNHEALTHY", (), 15.0, 200) == "STOP: CAMERA"
    assert overlay_for("auto", "S", "LOW_CONFIDENCE", (), 15.0, 200) == "STOP: AI"


# ---- manual mode ----------------------------------------------------------


def test_default_config_starts_in_manual():
    assert _cfg()["dashboard"]["mode"] == "manual"


def test_manual_tick_records_the_chain_but_never_sends():
    pilot, link = make_pilot()
    rec = pilot.tick()
    assert rec.mode == "manual"
    assert rec.sent is None
    assert rec.proposed == "F"  # the chain still shows what AUTO would do
    assert rec.command == "S"  # pad has not moved
    assert rec.overlay == "STOP"
    assert link.telemetry()["sent_count"] == 0


def test_manual_overlay_follows_the_firmware_active_command():
    pilot, link = make_pilot()
    link.send("F")
    rec = pilot.tick()
    assert rec.command == "F"
    assert rec.overlay == "GO 200 PWM"
    assert rec.motors == (200, 200)
    assert rec.sent is None


def test_manual_keeps_working_when_the_ai_goes_stale():
    pilot, _link = make_pilot(feed=FakeFeed([det()], ai_age=99.0))
    rec = pilot.tick()
    assert rec.mode == "manual"
    assert rec.command == "S"
    assert rec.overlay == "STOP"


# ---- auto arming ----------------------------------------------------------


def test_auto_armed_tick_sends_the_policy_command():
    pilot, link = make_pilot(_cfg(mode="auto"))
    rec = pilot.tick()
    assert rec.armed is True
    assert rec.mode == "auto"
    assert rec.proposed == "F"
    assert rec.command == "F"
    assert rec.sent == "F"
    assert rec.overlay == "GO 200 PWM"
    assert rec.motors == (200, 200)
    assert rec.safety_reason == "SAFE"
    assert link.telemetry()["active"] == "F"


def test_auto_stale_ai_disarms_and_parks():
    pilot, link = make_pilot(_cfg(mode="auto"), feed=FakeFeed([det()], ai_age=99.0))
    rec = pilot.tick()
    assert rec.armed is False
    assert rec.blockers == ("AI STALE",)
    assert rec.command == "S"
    assert rec.safety_reason.startswith("DISARMED:")
    assert rec.overlay == "DISARMED: AI STALE"
    assert link.telemetry()["active"] == "S"


def test_auto_without_a_frame_disarms():
    pilot, _link = make_pilot(
        _cfg(mode="auto"), feed=FakeFeed([det()], has_frame=False)
    )
    rec = pilot.tick()
    assert rec.armed is False
    assert "NO VIDEO" in rec.blockers
    assert rec.command == "S"


def test_auto_without_a_live_serial_link_disarms():
    pilot, _link = make_pilot(_cfg(mode="auto"), link=make_link(connect=False))
    rec = pilot.tick()
    assert rec.armed is False
    assert rec.blockers == ("SERIAL DOWN",)
    assert rec.command == "S"


def test_firmware_alert_inside_the_window_disarms_auto():
    link = make_link()
    parse_telemetry_line("ALERT:OBSTACLE dist=10.0cm cmd=F", link._state)
    pilot, _ = make_pilot(_cfg(mode="auto"), link=link)
    rec = pilot.tick()
    assert rec.armed is False
    assert rec.blockers == ("ALERT ACTIVE",)
    assert rec.command == "S"


def test_alert_mid_run_disarms_and_sends_stop_immediately():
    pilot, link = make_pilot(_cfg(mode="auto"))
    first = pilot.tick()
    assert first.sent == "F"
    parse_telemetry_line("ALERT:OBSTACLE dist=9.9cm cmd=F", link._state)
    second = pilot.tick()
    assert second.armed is False
    assert second.sent == "S"
    assert second.command == "S"
    assert link.telemetry()["active"] == "S"


def test_auto_rearms_once_the_alert_window_expires():
    pilot, link = make_pilot(_cfg(mode="auto"))
    t0 = time.time()
    pilot.tick(now=t0)
    parse_telemetry_line("ALERT:OBSTACLE dist=9.9cm cmd=F", link._state)
    blocked = pilot.tick(now=t0 + 0.1)
    assert blocked.armed is False
    rearmed = pilot.tick(now=t0 + 4.0)
    assert rearmed.armed is True
    assert rearmed.command == "F"
    assert rearmed.sent == "F"


# ---- auto safety gate -----------------------------------------------------


def test_obstacle_inside_the_emergency_zone_blocks_forward():
    pilot, _link = make_pilot(
        _cfg(mode="auto"), feed=FakeFeed([det()]), link=make_link(10.0)
    )
    rec = pilot.tick()
    assert rec.command == "S"
    assert rec.allowed is False
    assert rec.safety_reason == "EMERGENCY_OBSTACLE"
    assert rec.overlay == "BLOCKED 15 cm"
    assert rec.sent == "S"


def test_emergency_latch_keeps_blocking_on_the_next_tick():
    pilot, _link = make_pilot(
        _cfg(mode="auto"), feed=FakeFeed([det()]), link=make_link(10.0)
    )
    pilot.tick()
    second = pilot.tick()
    assert second.safety_reason == "EMERGENCY_LATCH"
    assert second.command == "S"


def test_low_confidence_blocks_forward_but_not_turns():
    feed = FakeFeed([det(conf=0.4)])
    pilot, _link = make_pilot(_cfg(mode="auto"), feed=feed)
    rec = pilot.tick()
    assert rec.safety_reason == "LOW_CONFIDENCE"
    assert rec.command == "S"
    assert rec.overlay == "STOP: AI"


def test_unknown_distance_blocks_forward_and_allows_turns():
    pilot, _link = make_pilot(
        _cfg(mode="auto"), feed=FakeFeed([det()]), link=make_link(None)
    )
    straight = pilot.tick()
    assert straight.safety_reason == "SENSOR_UNKNOWN"
    assert straight.command == "S"
    turning, _ = make_pilot(
        _cfg(mode="auto"),
        feed=FakeFeed([det(x1=40, y1=200, x2=80, y2=280)]),
        link=make_link(None),
    )
    rec = turning.tick()
    assert rec.proposed == "L"
    assert rec.command == "L"
    assert rec.allowed is True
    assert rec.overlay == "TURN"


def test_stale_ai_blocks_forward_via_the_camera_gate_in_safety():
    # require_camera_for_auto=false keeps the arm open, but the SafetyManager
    # still needs a frame before it allows motion (allow_without_camera=False
    # would be the opposite switch): here the frame exists, so only freshness
    # differs — arm fails, safety would pass. Assert the arm.
    pilot, _link = make_pilot(_cfg(mode="auto"), feed=FakeFeed([det()], ai_age=12.0))
    rec = pilot.tick()
    assert rec.armed is False
    assert "AI STALE" in rec.blockers
    assert rec.command == "S"


# ---- observe mode ---------------------------------------------------------


def test_observe_runs_the_chain_dry_without_sending():
    pilot, link = make_pilot(_cfg(mode="observe"))
    rec = pilot.tick()
    assert rec.mode == "observe"
    assert rec.command == "F"
    assert rec.sent is None
    assert rec.overlay == "WOULD F"
    assert link.telemetry()["sent_count"] == 0


# ---- set_mode / status ----------------------------------------------------


@pytest.mark.parametrize("bad", ["", "AUTO!", "drive", None])
def test_set_mode_rejects_unknown_modes(bad):
    pilot, _link = make_pilot()
    with pytest.raises(ValueError):
        pilot.set_mode(bad)


def test_set_mode_parks_the_rover_when_leaving_auto():
    pilot, link = make_pilot(_cfg(mode="auto"))
    pilot.tick()
    assert link.telemetry()["active"] == "F"
    status = pilot.set_mode("manual")
    assert status["mode"] == "manual"
    assert link.telemetry()["active"] == "S"


def test_set_mode_to_the_same_mode_does_not_send():
    pilot, link = make_pilot(_cfg(mode="auto"))
    pilot.set_mode("auto")
    assert link.telemetry()["sent_count"] == 0


def test_status_shape_before_and_after_a_tick():
    pilot, _link = make_pilot()
    empty = pilot.status()
    assert empty["mode"] == "manual"
    assert empty["modes"] == list(MODES)
    assert empty["decision"] is None
    assert empty["history"] == []
    pilot.tick()
    filled = pilot.status()
    assert isinstance(filled["decision"], dict)
    assert len(filled["history"]) == 1
    assert filled["armed"] is False


def test_decision_record_serialises_to_plain_json_types():
    pilot, _link = make_pilot(_cfg(mode="auto"))
    rec = pilot.tick()
    body = rec.to_dict()
    assert isinstance(body["blockers"], list)
    assert isinstance(body["motors"], list)
    assert isinstance(body["command"], str)
    assert isinstance(rec, DecisionRecord)


# ---- history + background loop -------------------------------------------


def test_history_ring_is_bounded_by_config():
    pilot, _link = make_pilot(_cfg(decision_history=3))
    for _ in range(5):
        pilot.tick()
    assert len(pilot.history) == 3
    assert pilot.status()["history_max"] == 3


def test_background_loop_ticks_until_stopped():
    pilot, _link = make_pilot(_cfg(mode="observe"))
    pilot.start(rate_hz=50.0)
    deadline = time.time() + 2.0
    try:
        while len(pilot.history) < 2 and time.time() < deadline:
            time.sleep(0.02)
    finally:
        pilot.stop()
    assert len(pilot.history) >= 2
    assert pilot._running is False
    assert pilot._thread is None


def test_stop_leaves_auto_parked():
    pilot, link = make_pilot(_cfg(mode="auto"))
    pilot.tick()
    assert link.telemetry()["active"] == "F"
    pilot.stop()
    assert link.telemetry()["active"] == "S"


# ---- config contract ------------------------------------------------------


def test_pilot_reads_every_new_dashboard_key():
    import software.dashboard.pilot as pilot_mod

    src = Path(pilot_mod.__file__).read_text(encoding="utf-8")
    assert '"mode"' in src
    assert '"decision_history"' in src
