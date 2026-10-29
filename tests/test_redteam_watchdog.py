"""Watchdog / timeout-math red-team tests.

Three timers exist in the system:
  * rover.movement_timeout_s (default 1.0 s) - laptop ManualMotionGuard (R5)
  * safety.comm_timeout_s    (default 3.0 s) - laptop link-health gate
  * COMM_TIMEOUT_MS          (3000 ms)      - firmware backstop, independent
This module checks that no combination of them can leave motors commanded.
"""

from __future__ import annotations

import itertools
import re
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from software.control.steering import SearchRotation
from software.hardware.arduino_serial import ArduinoSerial
from software.main import RoverApp
from software.safety.manual_guard import ManualMotionGuard
from software.utils.config_loader import load_config

ROOT = Path(__file__).resolve().parents[1]
INO = (ROOT / "arduino" / "rover_controller" / "rover_controller.ino").read_text(
    encoding="utf-8"
)
CFG = load_config("config/config.yaml")


class RecordingSerial:
    def __init__(self) -> None:
        self.calls: list[tuple[float, str]] = []

    def send(self, cmd: str) -> bool:
        self.calls.append((time.time(), cmd))
        return True


def firmware_const(name: str) -> str:
    m = re.search(rf"const\s+[\w\s]+?\b{name}\s*=\s*([^;]+);", INO)
    assert m, f"{name} missing from firmware"
    return m.group(1).strip()


# ------------------------------------------------------------ timeout math --
def test_movement_timeout_is_shorter_than_link_timeout():
    movement = float(CFG["rover"]["movement_timeout_s"])
    comm = float(CFG["safety"]["comm_timeout_s"])
    assert movement > 0
    assert movement <= comm, (
        "manual guard timeout must fire before the link is declared dead"
    )


def test_firmware_backstop_matches_and_bounds_the_laptop_timeout():
    fw_ms = int(firmware_const("COMM_TIMEOUT_MS"))
    comm_s = float(CFG["safety"]["comm_timeout_s"])
    assert fw_ms == int(comm_s * 1000), "firmware/laptop timeout drift"
    assert fw_ms <= comm_s * 1000, (
        "firmware backstop must not be longer than the laptop-side timeout"
    )


def test_firmware_watchdog_actually_stops_and_clears_command():
    m = re.search(r"if\s*\(\s*commLost\s*\)\s*\{(.*?)\}", INO, re.DOTALL)
    assert m, "commLost branch not found"
    body = m.group(1)
    assert "stopMotors()" in body, "watchdog does not stop motors"
    assert "currentCmd = 'S'" in body, "watchdog does not clear the command"


def test_firmware_obstacle_guard_blocks_both_translations():
    m = re.search(r"bool blocked = (.*?);", INO)
    assert m, "blocked expression not found"
    expr = m.group(1)
    assert "'F'" in expr and "'B'" in expr, expr
    assert "EMERGENCY_STOP_CM" in expr


# --------------------------------------------------------- manual guard -----
def test_manual_guard_sends_stop_after_timeout_measured():
    ser = RecordingSerial()
    timeout = 0.4
    guard = ManualMotionGuard(ser.send, timeout)
    t0 = time.time()
    assert guard.send("F") is True
    deadline = time.time() + timeout + 2.0
    while time.time() < deadline:
        if ser.calls and ser.calls[-1][1] == "S":
            break
        time.sleep(0.01)
    stop_t = ser.calls[-1][0]
    elapsed = stop_t - t0
    assert ser.calls[-1][1] == "S", f"no auto-stop, calls={ser.calls}"
    assert elapsed >= timeout * 0.9, f"stopped too early at {elapsed:.3f}s"
    assert elapsed <= timeout + 1.0, f"stopped too late at {elapsed:.3f}s"
    guard.close()


def test_manual_guard_cancel_does_not_emit_extra_stop():
    ser = RecordingSerial()
    guard = ManualMotionGuard(ser.send, 0.3)
    guard.send("F")
    time.sleep(0.05)
    guard.send("S")  # operator pressed space: cancels the pending timer
    time.sleep(0.5)  # wait past the old timeout
    stops = [c for c in ser.calls if c[1] == "S"]
    assert len(stops) == 1, f"stale timer fired anyway: {ser.calls}"
    guard.close()


def test_manual_guard_close_emits_exactly_one_stop():
    ser = RecordingSerial()
    guard = ManualMotionGuard(ser.send, 5.0)
    guard.send("F")
    guard.close()
    assert ser.calls[-1][1] == "S"
    time.sleep(0.05)
    assert len([c for c in ser.calls if c[1] == "S"]) == 1


# ------------------------------------------------- link health -> STOP ------
def test_stale_telemetry_forces_stop_for_every_command_class():
    ser = ArduinoSerial(mock=False)
    ser.connected = True
    ser.parse_line("DIST:200.0")
    ser.parse_line("STATUS:OK")
    ser.last_telemetry_time = time.time() - 10.0  # silence for 10 s
    from software.safety.safety_manager import SafetyManager

    sm = SafetyManager(15.0, 30.0, 3.0)
    for cmd in ("F", "B", "L", "R", "S"):
        v = sm.check(cmd, 200.0, ser.is_healthy(3.0), True, 0.9, 0.5)
        assert v.command == "S", f"{cmd} survived comm loss -> {v}"


def test_laptop_stops_issuing_motion_when_serial_dies_mid_run():
    tmp = tempfile.mkdtemp(prefix="rt_logs_")
    cfg = dict(CFG)
    cfg["logging"] = dict(CFG["logging"])
    cfg["logging"]["dir"] = tmp
    app = RoverApp(cfg, mode="observe", target="bottle", mock_hw=True)
    sent: list[str] = []
    real = app.serial.send

    def spy(cmd: str, speed: int | None = None) -> bool:
        sent.append(cmd)
        return real(cmd)

    app.serial.send = spy  # type: ignore[method-assign]
    app.detector  # mock detector present
    for _ in range(20):
        app.step()
    app.serial.connected = False
    for _ in range(20):
        app.step()
    assert all(c == "S" for c in sent[-20:]), sent[-20:]
    app.shutdown()


def test_largest_gap_between_commands_stays_below_firmware_timeout(tmp_path):
    """Measure the real pacing of the autonomous loop (mock hardware)."""
    cfg = dict(CFG)
    cfg["logging"] = dict(CFG["logging"])
    cfg["logging"]["dir"] = str(tmp_path)
    app = RoverApp(cfg, mode="observe", target="bottle", mock_hw=True)
    stamps: list[float] = []
    real = app.serial.send

    def spy(cmd: str, speed: int | None = None) -> bool:
        stamps.append(time.perf_counter())
        return real(cmd)

    app.serial.send = spy  # type: ignore[method-assign]
    for _ in range(50):
        app.step()
    app.shutdown()
    assert len(stamps) >= 40
    gaps = [b - a for a, b in itertools.pairwise(stamps)]
    max_gap = max(gaps)
    fw_s = int(firmware_const("COMM_TIMEOUT_MS")) / 1000.0
    assert max_gap < fw_s, f"command gap {max_gap:.3f}s exceeds firmware {fw_s}s"
    # recorded for the report (this is a measurement, not a claim about hardware)
    print(
        f"\nMEASURED max inter-command gap = {max_gap * 1000:.1f} ms "
        f"(mean {sum(gaps) / len(gaps) * 1000:.1f} ms, n={len(gaps)})"
    )


# ------------------------------------------------------- search timing ------
def test_search_rotation_cap_is_reachable_within_its_own_timeout():
    timeout = float(CFG["navigation"]["search_timeout_s"])
    duration = float(CFG["rover"]["search_rotation_duration_s"])
    max_rot = int(CFG["navigation"]["max_search_rotations"])
    reachable = int(timeout // duration)
    assert reachable >= max_rot, (
        f"max_search_rotations={max_rot} can never be reached: "
        f"timeout {timeout}s / rotation {duration}s = {reachable}"
    )


def test_search_always_terminates():
    s = SearchRotation(timeout_s=0.5, max_rotations=100, rotation_duration_s=0.1)
    s.start(now=0.0)
    cmd, done, _ = s.update(False, now=10.0)
    assert done and cmd == "S"


def test_search_stops_immediately_when_target_appears():
    s = SearchRotation()
    s.start(now=0.0)
    cmd, done, msg = s.update(True, now=0.1)
    assert done and cmd == "S" and "found" in msg
