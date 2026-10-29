"""Shared command emitter: STOP immediate, motion throttled, heartbeat resend."""

from __future__ import annotations

from software.control.command_emitter import STOP, CommandEmitter


def _recorder() -> tuple[list[str], object]:
    sent: list[str] = []

    def send(command: str) -> bool:
        sent.append(command)
        return True

    return sent, send


def test_stop_is_sent_immediately_on_change():
    sent, send = _recorder()
    em = CommandEmitter(send, cooldown_s=5.0, heartbeat_s=5.0)
    assert em.emit("F", 100.0) == "F"
    assert em.emit(STOP, 100.0001) == "S"  # a stop never waits for the cooldown
    assert sent == ["F", "S"]


def test_motion_respects_cooldown_but_heartbeats():
    sent, send = _recorder()
    em = CommandEmitter(send, cooldown_s=0.5, heartbeat_s=2.0)
    assert em.emit("F", 10.0) == "F"
    assert em.emit("F", 10.2) is None  # same command, inside the cooldown
    assert em.emit("L", 10.3) is None  # a change still waits for the cooldown
    assert em.emit("F", 12.5) == "F"  # heartbeat re-sends the held command
    assert sent == ["F", "F"]


def test_change_after_cooldown_is_sent():
    sent, send = _recorder()
    em = CommandEmitter(send, cooldown_s=0.2, heartbeat_s=2.0)
    em.emit("F", 1.0)
    assert em.emit("L", 1.5) == "L"
    assert sent == ["F", "L"]


def test_repeat_stop_within_heartbeat_is_throttled():
    sent, send = _recorder()
    em = CommandEmitter(send, cooldown_s=0.5, heartbeat_s=5.0)
    assert em.emit(STOP, 1.0) == "S"
    assert em.emit(STOP, 1.1) is None
    assert sent == ["S"]


def test_failed_send_does_not_advance_state():
    em = CommandEmitter(lambda cmd: False, cooldown_s=0.0, heartbeat_s=0.0)
    assert em.emit("F", 1.0) is None
    assert em.last_sent is None
    assert em.last_send_time == 0.0


def test_rejected_command_is_swallowed():
    def boom(cmd: str) -> bool:
        raise ValueError("not whitelisted")

    em = CommandEmitter(boom, cooldown_s=0.0, heartbeat_s=0.0)
    assert em.emit("X", 1.0) is None
    assert em.last_sent is None


def test_reset_records_an_out_of_band_command():
    em = CommandEmitter(lambda cmd: True, cooldown_s=0.2, heartbeat_s=1.0)
    em.emit("F", 1.0)
    em.reset(STOP, 1.5)
    assert em.last_sent == STOP
    assert em.last_send_time == 1.5
    assert em.emit(STOP, 1.6) is None  # already stopped
    assert em.emit("F", 1.8) == "F"  # 0.3 s >= cooldown


def test_no_send_callable_is_a_noop():
    em = CommandEmitter(None)
    assert em.emit("F", 1.0) is None
