import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from software.hardware.arduino_serial import ArduinoSerial


def test_valid_commands_accepted():
    a = ArduinoSerial(mock=True)
    for c in ["F", "B", "L", "R", "S"]:
        assert a.send(c) is True


def test_invalid_command_rejected():
    a = ArduinoSerial(mock=True)
    with pytest.raises(ValueError):
        a.send("X")


def test_telemetry_parsing():
    a = ArduinoSerial(mock=True)
    a.parse_line("DIST:25.5")
    assert a.telemetry.distance_cm == 25.5
    a.parse_line("STATUS:STOP")
    assert a.telemetry.status == "STOP"
    a.parse_line("GARBAGE LINE")  # must not crash
    a.parse_line("DIST:notanumber")  # must not crash


def test_command_encoding_newline_protocol():
    # protocol: single char + newline; mock verifies acceptance path
    a = ArduinoSerial(mock=True, mock_distance_cm=100.0)
    assert a.send("f") is True  # case-insensitive
    a.set_mock_distance(10.0)
    assert a.telemetry.distance_cm == 10.0


def test_encoder_ticks_parsed_from_ticks_line():
    a = ArduinoSerial(mock=False)
    a.parse_line("TICKS:5,2")
    assert a.telemetry.encoder_ticks == (5, 2)
    a.parse_line("TICKS:0,120")
    assert a.telemetry.encoder_ticks == (0, 120)


def test_ticks_never_refresh_heartbeat_or_clear_fault():
    # Red-team M3: only DIST/STATUS are liveness; encoder telemetry and
    # garbage must never make a dead link look healthy.
    a = ArduinoSerial(mock=False)
    assert a.telemetry.sensor_fault is True  # no valid DIST yet
    a.parse_line("DIST:100.0")
    assert a.telemetry.sensor_fault is False
    beat = a.last_telemetry_time
    a.parse_line("DIST:-1")  # dead sensor -> fault re-set
    assert a.telemetry.sensor_fault is True
    a.parse_line("TICKS:7,7")
    assert a.telemetry.sensor_fault is True  # ticks do not clear the fault
    assert a.last_telemetry_time == beat  # ticks are not a heartbeat
    assert a.telemetry.encoder_ticks == (7, 7)


def test_malformed_ticks_ignored_without_crash():
    a = ArduinoSerial(mock=False)
    a.parse_line("TICKS:5,2")
    for bad in ("TICKS:", "TICKS:abc", "TICKS:1,2,3", "TICKS:1.5,2", "TICKS:,"):
        a.parse_line(bad)  # must not raise
    assert a.telemetry.encoder_ticks == (5, 2)  # last good value kept


# ------------------------------------------------- Protocol v2 speed suffix --
def test_speed_suffix_encoded_on_the_wire():
    a = ArduinoSerial(mock=True)
    assert a.send("F", speed=180) is True
    assert a.last_payload == "F180\n"
    assert a.send("L", speed=0) is True  # 0 is a legal PWM (coast)
    assert a.last_payload == "L0\n"
    assert a.send("S") is True
    assert a.last_payload == "S\n"  # no speed -> bare command (sticky fw speed)


def test_speed_suffix_validation():
    a = ArduinoSerial(mock=True)
    for bad in (256, -1, 1000):
        try:
            a.send("F", speed=bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"speed={bad} must be rejected")
    try:
        a.send("F", speed=True)  # bool is not a PWM value
    except ValueError:
        pass
    else:
        raise AssertionError("bool speed must be rejected")
    try:
        a.send("F", speed="120")  # type: ignore[arg-type]
    except ValueError:
        pass
    else:
        raise AssertionError("str speed must be rejected")
    assert a.last_payload is None  # nothing invalid ever hit the wire


# ------------------------------------------------- Port auto-detect (dev) ---
def test_detect_board_port_skips_system_ports(monkeypatch):
    import serial.tools.list_ports as lp

    from software.hardware.arduino_serial import detect_board_port

    class _P:
        def __init__(self, device, description):
            self.device = device
            self.description = description

    monkeypatch.setattr(
        lp,
        "comports",
        lambda: [
            _P("COM3", "Intel(R) Active Management Technology - SOL (COM3)"),
            _P("COM5", "USB-SERIAL CH340 (COM5)"),
        ],
    )
    assert detect_board_port() == "COM5"


def test_detect_board_port_returns_none_without_board(monkeypatch):
    import serial.tools.list_ports as lp

    from software.hardware.arduino_serial import detect_board_port

    class _P:
        def __init__(self, device, description):
            self.device = device
            self.description = description

    monkeypatch.setattr(
        lp,
        "comports",
        lambda: [_P("COM3", "Intel(R) Active Management Technology - SOL (COM3)")],
    )
    assert detect_board_port() is None
