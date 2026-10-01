"""R5: manual motion is bounded — auto-STOP after rover.movement_timeout_s."""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from software.safety.manual_guard import ManualMotionGuard


class FakeSerial:
    def __init__(self):
        self.sent = []
        self._lock = threading.Lock()

    def send(self, cmd: str) -> bool:
        with self._lock:
            self.sent.append(cmd)
        return True


def test_single_command_auto_stops():
    ser = FakeSerial()
    g = ManualMotionGuard(ser.send, timeout_s=0.05)
    g.send("F")
    assert ser.sent == ["F"]
    threading.Event().wait(0.15)
    assert ser.sent == ["F", "S"]


def test_rapid_commands_reset_timer_single_stop():
    ser = FakeSerial()
    g = ManualMotionGuard(ser.send, timeout_s=0.1)
    g.send("F")
    threading.Event().wait(0.05)
    g.send("L")
    threading.Event().wait(0.2)
    # first timer cancelled by second send -> exactly one auto-STOP
    assert ser.sent == ["F", "L", "S"]


def test_stop_command_has_no_trailing_stop():
    ser = FakeSerial()
    g = ManualMotionGuard(ser.send, timeout_s=0.05)
    g.send("S")
    threading.Event().wait(0.12)
    assert ser.sent == ["S"]


def test_close_forces_stop():
    ser = FakeSerial()
    g = ManualMotionGuard(ser.send, timeout_s=10.0)
    g.send("B")
    g.close()
    assert ser.sent == ["B", "S"]
    threading.Event().wait(0.1)
    assert ser.sent == ["B", "S"]  # timer cancelled, no duplicate


def test_close_with_no_command_still_sends_stop():
    ser = FakeSerial()
    g = ManualMotionGuard(ser.send, timeout_s=10.0)
    g.close()
    assert ser.sent == ["S"]


def test_invalid_timeout_rejected():
    try:
        ManualMotionGuard(lambda c: True, timeout_s=0)
    except ValueError:
        return
    raise AssertionError("timeout_s <= 0 must raise ValueError")
