"""Adversarial full-chain safety tests: steering mapping -> ObstacleAvoidance
-> SafetyManager -> ArduinoSerial.send, driven through RoverApp.step().

Hardware is mocked; results are SIMULATED (they prove software behaviour only,
never physical behaviour). Tests that assert REQUIRED safe behaviour and fail
document a real defect and are kept on purpose.
"""

from __future__ import annotations

import math
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from software.hardware.arduino_serial import VALID_COMMANDS, ArduinoSerial
from software.main import RoverApp
from software.safety.safety_manager import SafetyManager
from software.utils.config_loader import load_config

CFG = load_config("config/config.yaml")


class BrokenCamera:
    """Camera that is completely dead: no frames, unhealthy."""

    class stats:
        fps = 0.0

    def read(self):
        return None

    def is_healthy(self):
        return False

    def open(self):
        return False

    def close(self):
        return None


class StaleCamera:
    """Camera still handing out the last frame but reporting unhealthy
    (the frozen-frame / reconnect case)."""

    class stats:
        fps = 0.0

    def __init__(self):
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)

    def read(self):
        return self.frame

    def is_healthy(self):
        return False

    def close(self):
        return None


def _cfg_det(app: RoverApp, **props) -> None:
    # MockDetector-only attributes; set via setattr to keep static checkers happy.
    for key, val in props.items():
        setattr(app.detector, key, val)


def make_app(mode: str = "observe") -> tuple[RoverApp, list[str]]:
    # keep the test run from appending to the repository's logs/events.csv
    cfg = dict(CFG)
    cfg["logging"] = dict(CFG["logging"])
    cfg["logging"]["dir"] = tempfile.mkdtemp(prefix="rt_logs_")
    app = RoverApp(cfg, mode=mode, target="bottle", mock_hw=True)
    sent: list[str] = []
    real = app.serial.send

    def spy(cmd: str, speed: int | None = None) -> bool:
        sent.append(cmd)
        return bool(real(cmd))

    app.serial.send = spy  # type: ignore[method-assign]
    return app, sent


# ---------------------------------------------------------------- §6 matrix --
def test_ai_forward_with_close_obstacle_is_stop():
    app, sent = make_app()
    _cfg_det(app, position="CENTER")
    app.serial.set_mock_distance(10.0)
    for _ in range(30):
        app.step()
    assert sent and sent[-1] == "S", f"expected STOP, last sends={sent[-5:]}"
    app.shutdown()


def test_ai_left_with_close_obstacle_is_allowed_to_escape():
    app, sent = make_app()
    _cfg_det(app, position="LEFT")
    app.serial.set_mock_distance(10.0)
    for _ in range(30):
        app.step()
    # turning in place away from the obstacle is the designed escape
    assert sent[-1] in ("L", "S"), sent[-5:]
    assert sent[-1] != "F"
    app.shutdown()


def test_ai_right_with_close_obstacle_is_allowed_to_escape():
    app, sent = make_app()
    _cfg_det(app, position="RIGHT")
    app.serial.set_mock_distance(10.0)
    for _ in range(30):
        app.step()
    assert sent[-1] in ("R", "S"), sent[-5:]
    assert sent[-1] != "F"
    app.shutdown()


def test_ai_forward_with_obstacle_blocked_at_all_distances():
    for dist in (0.0, 1.0, 5.0, 10.0, 14.9, 15.0, 16.0, 30.0, 100.0, 400.0):
        app, sent = make_app()
        _cfg_det(app, position="CENTER")
        app.serial.set_mock_distance(dist)
        for _ in range(30):
            app.step()
        if dist < CFG["rover"]["emergency_stop_distance_cm"]:
            assert sent[-1] == "S", f"dist={dist} sent={sent[-1]}"
        app.shutdown()


def test_reverse_is_blocked_by_close_obstacle():
    """§6: AI=BACKWARD + obstacle CLOSE => STOP."""
    sm = SafetyManager(15.0, 30.0)
    v = sm.check("B", 10.0, True, True, 0.9, 0.5)
    assert v.command == "S"


# ------------------------------------------------------ failure injection ---
def test_camera_total_failure_stops_motion():
    app, sent = make_app()
    app.camera = BrokenCamera()  # type: ignore[assignment]
    for _ in range(20):
        app.step()
    assert app.state["command"] == "S"
    assert app.state["safety"] == "CAMERA_FAIL"
    assert all(c == "S" for c in sent), sent
    app.shutdown()


def test_stale_frame_with_unhealthy_camera_stops_motion():
    app, sent = make_app()
    app.camera = StaleCamera()  # type: ignore[assignment]
    _cfg_det(app, position="CENTER")
    for _ in range(20):
        app.step()
    assert app.state["command"] == "S"
    assert app.state["safety"] == "CAMERA_UNHEALTHY"
    assert all(c == "S" for c in sent), sent
    app.shutdown()


def test_serial_link_death_stops_motion():
    app, sent = make_app()
    _cfg_det(app, position="CENTER")
    app.serial.set_mock_distance(200.0)
    app.step()
    app.serial.connected = False  # link died
    for _ in range(20):
        app.step()
    assert app.state["command"] == "S"
    assert app.state["safety"] == "COMM_LOST"
    assert all(c == "S" for c in sent[-20:]), sent[-20:]
    app.shutdown()


def test_detector_crash_stops_motion():
    app, sent = make_app()
    _cfg_det(app, position="CENTER")

    def boom(_frame):
        raise RuntimeError("model exploded")

    app.detector.detect = boom  # type: ignore[method-assign]
    for _ in range(20):
        app.step()
    assert app.state["command"] == "S"
    assert all(c == "S" for c in sent), sent
    app.shutdown()


def test_unknown_distance_blocks_translation_in_full_chain():
    for bad in (None, float("nan"), float("inf"), -1.0, "100", True):
        app, sent = make_app()
        _cfg_det(app, position="CENTER")
        app.serial.telemetry.distance_cm = bad  # type: ignore[assignment]
        for _ in range(20):
            app.step()
        assert app.state["command"] == "S", f"distance={bad!r} -> {sent[-3:]}"
        app.shutdown()


def test_stale_distance_from_dead_sensor_does_not_allow_forward():
    """CRITICAL candidate: HC-SR04 starts reporting DIST:-1 (no echo).

    The parser discards -1 (outside 0..500), so the last good distance stays
    on record while STATUS:OK keeps the link 'healthy'. Both safety layers then
    see a healthy rover with a large clearance.
    """
    ser = ArduinoSerial(mock=False)
    ser.connected = True
    ser.parse_line("DIST:150.0")
    ser.parse_line("STATUS:OK")
    for _ in range(10):  # sensor dead from now on
        ser.parse_line("DIST:-1")
        ser.parse_line("STATUS:OK")
    assert ser.telemetry.distance_cm == 150.0, "stale distance retained"
    # NOTE (precondition corrected after the C1 fix): the original assertion
    # demanded `is_healthy(...) is True`, but that state is exactly the bug
    # (link reported healthy while the sensor is dead). The REQUIRED assertion
    # below (verdict must be S) is mathematically impossible while health
    # reads True, so the precondition now encodes the fixed contract:
    # a dead sensor makes the link unhealthy.
    assert ser.is_healthy(3.0) is False, "dead sensor must invalidate health"
    sm = SafetyManager(15.0, 30.0, 3.0)
    verdict = sm.check(
        "F", ser.telemetry.distance_cm, ser.is_healthy(3.0), True, 0.9, 0.5
    )
    assert verdict.command == "S", f"dead sensor allowed motion: {verdict}"


def test_out_of_range_telemetry_does_not_allow_forward():
    ser = ArduinoSerial(mock=False)
    ser.connected = True
    ser.parse_line("DIST:120.0")
    ser.parse_line("STATUS:OK")
    for line in ("DIST:900", "DIST:nan", "DIST:inf", "DIST:abc", "DIST:"):
        ser.parse_line(line)
        ser.parse_line("STATUS:OK")
    sm = SafetyManager(15.0, 30.0, 3.0)
    verdict = sm.check(
        "F", ser.telemetry.distance_cm, ser.is_healthy(3.0), True, 0.9, 0.5
    )
    assert verdict.command == "S", f"stale/garbage distance -> {verdict}"


# ------------------------------------------------- emergency latch (R4) -----
def test_emergency_latch_engages_through_the_auto_chain():
    """R4 says the emergency latch engages on a very close obstacle.

    In the autonomous pipeline ObstacleAvoidance rewrites F/B to *S* before
    SafetyManager sees the command, so SafetyManager never takes the branch
    that sets emergency_latch. The hysteresis advertised by R4 therefore has
    no effect in observe/search/scan360.
    """
    app, sent = make_app()
    _cfg_det(app, position="CENTER")
    app.serial.set_mock_distance(5.0)  # < 0.7 * emergency => should latch
    for _ in range(10):
        app.step()
    assert sent[-1] == "S"
    assert app.safety.emergency_latch is True, (
        "emergency latch never engaged in the autonomous path (R4 ineffective)"
    )
    app.serial.set_mock_distance(20.0)  # cleared but still below slow_cm
    for _ in range(10):
        app.step()
    assert app.safety.emergency_latch is True, "latch must not release < slow_cm"
    app.serial.set_mock_distance(35.0)  # >= slow_cm => R4 release
    time.sleep(0.25)  # let the anti-oscillation cooldown elapse deterministically
    for _ in range(10):
        app.step()
    assert app.safety.emergency_latch is False, "latch must release >= slow_cm"
    assert sent[-1] == "F", f"expected motion after release, got {sent[-3:]}"
    app.shutdown()


def test_emergency_latch_works_on_the_manual_path():
    """Manual mode calls SafetyManager directly, so R4 must hold there."""
    app, _sent = make_app(mode="manual")

    def manual_check(cmd, dist):
        return app.safety.check(
            cmd, dist, True, True, 1.0, 0.0, allow_without_camera=True
        )

    v = manual_check("F", 5.0)
    assert v.command == "S" and app.safety.emergency_latch is True
    # 20 cm is clear of 0.7*emergency but still < slow_cm => stay latched
    assert manual_check("F", 20.0).command == "S"
    assert app.safety.emergency_latch is True
    # >= slow_cm => released (R4)
    assert manual_check("F", 35.0).command == "F"
    assert app.safety.emergency_latch is False
    app.shutdown()


def test_latch_release_never_happens_on_invalid_distance():
    sm = SafetyManager(15.0, 30.0, 3.0)
    sm.emergency_latch = True
    for bad in (None, float("nan"), "100"):
        sm.check("F", bad, True, True, 0.9, 0.5)
        assert sm.emergency_latch is True, f"released on {bad!r}"


# ------------------------------------------------------ command alphabet ----
def test_full_chain_never_emits_unknown_command_characters():
    app, sent = make_app()
    for dist in (None, -5.0, 0.0, 7.0, 14.0, 15.0, 29.0, 31.0, 100.0, 1e9, math.nan):
        for pos in ("LEFT", "CENTER", "RIGHT", "NONE"):
            _cfg_det(app, position=pos)
            app.serial.telemetry.distance_cm = dist
            app.step()
    assert sent, "no commands issued"
    bad = [c for c in sent if c not in VALID_COMMANDS]
    assert not bad, f"non-protocol command emitted: {bad[:10]}"


def test_shutdown_always_issues_stop():
    app, sent = make_app()
    _cfg_det(app, position="CENTER")
    app.step()
    app.shutdown()
    assert sent[-1] == "S"


# ------------------------------------------------- mode regressions (R) -----
def test_search_mode_must_rotate_until_target_found():
    """README/§10: 'search' rotates to acquire a target."""
    app, sent = make_app(mode="search")
    _cfg_det(app, emit=False)  # target genuinely absent
    for _ in range(60):
        app.step()
    motion = [c for c in sent if c in ("L", "R")]
    assert motion, (
        f"search mode never issued a rotation; last reasons={[app.state.get('safety')]}"
    )
    app.shutdown()


def test_scan360_mode_must_rotate():
    """README §9: `--mode scan360` performs a 360 scan."""
    app, sent = make_app(mode="scan360")
    for _ in range(60):
        app.step()
    motion = [c for c in sent if c in ("L", "R")]
    assert motion, "scan360 mode never issued a rotation command"
    app.shutdown()


def test_scan360_mode_approaches_when_target_visible():
    app, sent = make_app(mode="scan360")
    _cfg_det(app, position="CENTER")
    app.serial.set_mock_distance(200.0)
    for _ in range(60):
        app.step()
    assert any(c == "F" for c in sent), "scan360 ignored a centred visible target"
    app.shutdown()


# ------------------------------------------------- safety API boundaries ----
def test_safety_manager_must_reject_unknown_command_alphabet():
    sm = SafetyManager(15.0, 30.0, 3.0)
    for junk in ("FORWARD", "abc", "123", "FWD", "G", "\x00", "  "):
        verdict = sm.check(junk, 100.0, True, True, 0.9, 0.5)
        assert verdict.command in VALID_COMMANDS, (
            f"SafetyManager passed through {junk!r} -> {verdict.command!r}"
        )
