"""Adversarial serial-protocol tests: malformed / empty / binary / flooded
input against the Python side of the link (software/hardware/arduino_serial.py).

Firmware-side behaviour for the same input classes is covered separately by
tests/test_redteam_firmware_host.py (SIMULATED).
"""

from __future__ import annotations

import random
import string
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from software.hardware.arduino_serial import VALID_COMMANDS, ArduinoSerial

FILLER = "DIST:STATUS:BATTERY:ERROR:"


def make_serial() -> ArduinoSerial:
    ser = ArduinoSerial(mock=False)
    ser.connected = True
    return ser


def dist_is_invariant(ser: ArduinoSerial) -> bool:
    d = ser.telemetry.distance_cm
    return d is None or (isinstance(d, float) and 0.0 <= d <= 500.0)


# ------------------------------------------------------------ fuzz parse ----
def test_fuzz_random_lines_never_crash_parser():
    rng = random.Random(20260925)
    ser = make_serial()
    alphabet = string.printable + "\x00\x01\x7f\x80" + "éñ漢"
    for _ in range(5000):
        line = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
        try:
            ser.parse_line(line)
        except Exception as exc:
            raise AssertionError(f"parse_line({line!r}) raised {exc!r}") from exc
        assert dist_is_invariant(ser), f"distance corrupted by {line!r}"


def test_fuzz_random_binary_like_lines_from_reader():
    """Mirror of the reader: bytes decoded with errors='ignore'."""
    rng = random.Random(7)
    ser = make_serial()
    for _ in range(3000):
        raw = bytes(rng.randrange(256) for _ in range(rng.randint(0, 64)))
        ser.parse_line(raw.decode("utf-8", errors="ignore"))
        assert dist_is_invariant(ser)


def test_impossible_distance_values_are_rejected():
    ser = make_serial()
    ser.parse_line("DIST:100.0")
    assert ser.telemetry.distance_cm == 100.0
    for bad in (
        "DIST:-1",
        "DIST:-0.1",
        "DIST:501",
        "DIST:900",
        "DIST:nan",
        "DIST:inf",
        "DIST:-inf",
        "DIST:1e400",
        "DIST:",
        "DIST:abc",
        "DIST:  ",
        "DIST:100;200",
        "DIST:0x10",
        "DIST:1_000",
    ):
        ser.parse_line(bad)
        assert ser.telemetry.distance_cm == 100.0, f"{bad} corrupted distance"
        ser.parse_line("STATUS:OK")  # keep link alive
    assert dist_is_invariant(ser)


def test_boundary_distances_accepted():
    ser = make_serial()
    for good, expected in (("DIST:0", 0.0), ("DIST:500", 500.0), ("DIST:499.9", 499.9)):
        ser.parse_line(good)
        assert ser.telemetry.distance_cm == expected


# ------------------------------------------------------------- flooding -----
def test_flooded_input_keeps_memory_bounded():
    ser = make_serial()
    for i in range(20000):
        ser.parse_line(f"junk line {i} " + "x" * 500)
    assert len(ser.telemetry.raw_lines) <= 50
    assert all(len(x) <= 500 for x in ser.telemetry.raw_lines)


def test_megabyte_line_does_not_blow_up():
    ser = make_serial()
    ser.parse_line("DIST:" + "9" * 1_000_000)
    ser.parse_line("y" * 1_000_000)
    assert len(ser.telemetry.raw_lines) <= 50
    assert all(len(x) <= 500 for x in ser.telemetry.raw_lines)
    assert dist_is_invariant(ser)


def test_flooded_valid_commands_all_accepted_in_mock_mode():
    ser = ArduinoSerial(mock=True)
    t0 = time.perf_counter()
    for _ in range(10000):
        assert ser.send("F") is True
    assert time.perf_counter() - t0 < 5.0


# --------------------------------------------------- link-health honesty ----
def test_unknown_lines_do_not_refresh_link_health():
    ser = make_serial()
    ser.parse_line("DIST:100.0")
    ser.parse_line("STATUS:OK")
    before = ser.last_telemetry_time
    time.sleep(0.01)
    for junk in ("hello", "DIST", "dist:100", "battery:12.0", "STATUS", "", "   "):
        ser.parse_line(junk)
    assert ser.last_telemetry_time == before, "junk line refreshed link health"


def test_only_recognised_status_values_may_refresh_link_health():
    """A noise-corrupted 'STATUS:<garbage>' line must not prove the link is up."""
    ser = make_serial()
    ser.parse_line("DIST:100.0")
    before = ser.last_telemetry_time
    time.sleep(0.01)
    ser.parse_line("STATUS:" + "z" * 100)
    assert ser.last_telemetry_time == before, (
        "unrecognised STATUS payload counted as a live heartbeat"
    )


def test_link_goes_unhealthy_after_comm_timeout():
    ser = make_serial()
    ser.parse_line("DIST:100.0")
    ser.parse_line("STATUS:OK")
    assert ser.is_healthy(3.0) is True
    ser.last_telemetry_time = time.time() - 3.5
    assert ser.is_healthy(3.0) is False
    assert ser.is_healthy(30.0) is True


def test_disconnected_serial_is_unhealthy():
    ser = ArduinoSerial(mock=False)  # never connected
    assert ser.connected is False
    assert ser.is_healthy(3.0) is False
    assert ser.is_healthy(0.0) is False


def test_send_on_disconnected_serial_returns_false_without_raising():
    ser = ArduinoSerial(mock=False)
    assert ser.send("S") is False


# ------------------------------------------------------- command alphabet ---
def test_invalid_commands_are_rejected():
    ser = ArduinoSerial(mock=True)
    for bad in ("FORWARD", "abc", "123", "", "  ", "G", "FWD", "SS", "F S", "\n"):
        try:
            ser.send(bad)
        except ValueError:
            continue
        raise AssertionError(f"send({bad!r}) did not raise ValueError")


def test_valid_commands_are_accepted_after_normalisation():
    ser = ArduinoSerial(mock=True)
    for good in ("F", "f", " F ", "B", "L", "R", "S", "s"):
        assert ser.send(good) is True


def test_send_never_silently_emits_something_not_in_the_protocol():
    rng = random.Random(99)
    ser = ArduinoSerial(mock=True)
    for _ in range(2000):
        junk = "".join(rng.choice(string.printable) for _ in range(rng.randint(0, 8)))
        try:
            ser.send(junk)
        except ValueError:
            continue
        # if it did not raise, it must have been a real protocol character
        assert junk.strip().upper() in VALID_COMMANDS


def test_send_with_non_string_input_is_rejected():
    """Boundary validation: send() must not accept non-strings silently."""
    ser = ArduinoSerial(mock=True)
    for bad in (None, 1, 1.5, ["F"], {"cmd": "F"}):
        try:
            ser.send(bad)  # type: ignore[arg-type]
        except (AttributeError, TypeError, ValueError):
            continue
        raise AssertionError(f"send({bad!r}) was accepted")


# ------------------------------------------------------- threading/races ----
def test_concurrent_parse_and_send_do_not_corrupt_state():
    ser = make_serial()
    errors: list[BaseException] = []
    stop = threading.Event()

    def reader(seed: int) -> None:
        rng = random.Random(seed)
        try:
            for _ in range(4000):
                ser.parse_line(f"DIST:{rng.uniform(0, 400):.1f}")
                ser.parse_line("STATUS:OK")
                if rng.random() < 0.1:
                    ser.parse_line("garbage " + "x" * rng.randint(1, 100))
        except BaseException as exc:
            errors.append(exc)
        finally:
            stop.set()

    def writer() -> None:
        try:
            while not stop.is_set():
                ser.send("S")
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=reader, args=(i,)) for i in range(4)]
    threads.append(threading.Thread(target=writer))
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors
    assert dist_is_invariant(ser)
    assert len(ser.telemetry.raw_lines) <= 50


def test_disconnect_sends_stop_before_closing():
    ser = ArduinoSerial(mock=True)
    calls: list[str] = []
    real = ser.send

    def spy(cmd: str, speed: int | None = None) -> bool:
        calls.append(cmd)
        return real(cmd)

    ser.send = spy  # type: ignore[method-assign]
    ser.disconnect()
    assert "S" in calls
    assert ser.connected is False
