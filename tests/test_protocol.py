"""Protocol tests: the laptop must accept/reject exactly what the Uno does."""

from __future__ import annotations

import pytest

from support import c_constants, read

from ai_rover import protocol
from ai_rover.protocol import (
    BATTERY_LOW_MV,
    BATTERY_RECOVER_MV,
    COMMANDS,
    FAULT_NAMES,
    GATE_SPEED_CM,
    MOTION_COMMANDS,
    REAR_GATE_CM,
    STALL_MIN_SPEED_MM_S,
    STALL_MS,
    STALL_RATIO_PCT,
    STATE_NAMES,
    ProtocolError,
    Telemetry,
    clamp_speed,
    crc8,
    encode_command,
    encode_telemetry,
    parse_command,
    parse_frame,
    parse_telemetry,
    required_gate_cm,
)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text,cmd,speed", [
    ("F", "F", None),
    ("f", "F", None),
    ("F200", "F", 200),
    ("f200", "F", 200),
    ("B60", "B", 60),
    ("L 90", "L", 90),
    ("R255", "R", 255),
    ("S", "S", None),
    ("s0", "S", None),
    ("F200\n", "F", 200),
    ("F200\r\n", "F", 200),
    ("l0", "L", 0),
])
def test_parse_accepts_valid_payloads(text, cmd, speed):
    packet = parse_command(text)
    assert packet.cmd == cmd
    assert packet.speed == speed


@pytest.mark.parametrize("text", [
    "",
    " ",
    "Z",
    "X200",
    "FF",
    "F20x",
    "F+20",
    "F-20",
    "F999",
    "F256",
    "F1234",
    "F  200",
    " F200",
    "F2.5",
    "F200junk",
    "F00000000",
])
def test_parse_rejects_invalid_payloads(text):
    with pytest.raises(ProtocolError):
        parse_command(text)


def test_parse_rejects_non_text():
    with pytest.raises(ProtocolError):
        parse_command(None)  # type: ignore[arg-type]
    with pytest.raises(ProtocolError):
        parse_command(200)  # type: ignore[arg-type]


def test_parse_rejects_unicode_digits():
    # C++ only accepts ASCII '0'..'9'; Arabic-Indic digits must not slip through.
    with pytest.raises(ProtocolError):
        parse_command("F٢٠٠")


def test_stop_drops_speed():
    packet = parse_command("S180")
    assert packet.cmd == "S"
    assert packet.speed is None
    assert packet.is_stop


def test_parse_frame_accepts_bytes():
    assert parse_frame(b"F200\n").speed == 200
    assert parse_frame("F200\n").cmd == "F"


def test_parse_frame_rejects_binary():
    with pytest.raises(ProtocolError):
        parse_frame(b"\xff\xfe")
    with pytest.raises(ProtocolError):
        parse_frame(b"F2\xd8\xa1")


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------
def test_encode_exact_wire_bytes():
    assert encode_command("F", 200) == "F200*B1\n"
    assert encode_command("S") == "S*BE\n"
    assert encode_command("s", 255) == "S*BE\n"
    assert encode_command("B", 60) == "B60*" + f"{crc8('B60'):02X}" + "\n"


def test_encode_legacy_form_without_crc():
    assert encode_command("F", 200, crc=False) == "F200\n"
    assert encode_command("S", crc=False) == "S\n"


def test_crc8_check_vector():
    assert crc8(b"123456789") == 0xF4
    assert crc8("123456789") == 0xF4
    assert crc8("") == 0


def test_parse_validates_the_crc():
    packet = parse_command("F200*B1")
    assert packet.cmd == "F"
    assert packet.speed == 200
    assert packet.has_crc is True
    # lowercase hex is accepted, the CRC covers the exact body bytes
    assert parse_command("F200*b1").has_crc is True


@pytest.mark.parametrize("text", [
    "F200*B2",    # wrong checksum
    "F200*B",     # too short
    "F200*B11",   # too long
    "F200*GG",    # not hex
    "F200*",      # empty checksum
    "*B1",        # no body
])
def test_parse_rejects_bad_crc(text):
    with pytest.raises(ProtocolError):
        parse_command(text)


def test_crc_can_be_required():
    with pytest.raises(ProtocolError):
        parse_command("F200", require_crc=True)
    assert parse_command("F200*B1", require_crc=True).has_crc


def test_encode_clamps_low_speed_to_stiction_floor():
    assert encode_command("F", 0, crc=False) == "F60\n"
    assert encode_command("F", 59, crc=False) == "F60\n"
    assert encode_command("F", 60, crc=False) == "F60\n"


def test_encode_rejects_out_of_range_speed():
    with pytest.raises(ProtocolError):
        encode_command("F", 256)
    with pytest.raises(ProtocolError):
        encode_command("F", -1)


def test_encode_rejects_bad_commands():
    for bad in ("", "FF", "Z", "1"):
        with pytest.raises(ProtocolError):
            encode_command(bad)
    with pytest.raises(ProtocolError):
        encode_command("F", 100.5)  # type: ignore[arg-type]
    with pytest.raises(ProtocolError):
        encode_command("F", True)  # type: ignore[arg-type]


def test_clamp_speed():
    assert clamp_speed(0) == 60
    assert clamp_speed(59) == 60
    assert clamp_speed(60) == 60
    assert clamp_speed(180) == 180
    assert clamp_speed(255) == 255
    assert clamp_speed(9999) == 255
    with pytest.raises(ProtocolError):
        clamp_speed(180.0)  # type: ignore[arg-type]


def test_command_sets():
    assert set(COMMANDS) == {"F", "B", "L", "R", "S"}
    assert MOTION_COMMANDS == {"F", "B", "L", "R"}


def test_packet_frame_roundtrip():
    packet = parse_command("R120")
    frame = encode_command(packet.cmd, packet.speed)
    assert frame.endswith("\n") and "*" in frame
    again = parse_command(frame, require_crc=True)
    assert (again.cmd, again.speed) == (packet.cmd, packet.speed)


# ---------------------------------------------------------------------------
# Cross-language parity with firmware/libraries/AIRoverCore/src/protocol.h
# ---------------------------------------------------------------------------
def test_constants_match_firmware_header():
    header = c_constants(read("firmware/libraries/AIRoverCore/src/protocol.h"))
    assert header["kForwardGateCm"] == protocol.FORWARD_GATE_CM == 15
    assert header["kLinkWatchdogMs"] == protocol.LINK_WATCHDOG_MS == 500
    assert header["kSonarPeriodMs"] == protocol.SONAR_PERIOD_MS == 60
    assert header["kCommandGapUs"] == protocol.COMMAND_GAP_US == 15000
    assert header["kSpeedMin"] == protocol.SPEED_MIN == 60
    assert header["kSpeedMax"] == protocol.SPEED_MAX == 255
    assert header["kDefaultSpeed"] == protocol.DEFAULT_SPEED == 180
    assert header["kMaxFrameLen"] == protocol.MAX_FRAME_LEN == 16
    assert header["kSonarMaxCm"] == protocol.SONAR_MAX_CM == 400
    assert header["kGateSpeedCm"] == protocol.GATE_SPEED_CM == 20
    assert header["kRearGateCm"] == protocol.REAR_GATE_CM == 15
    assert header["kBatteryLowMv"] == protocol.BATTERY_LOW_MV == 6400
    assert header["kBatteryRecoverMv"] == protocol.BATTERY_RECOVER_MV == 6800
    assert header["kTelemetryPeriodMs"] == protocol.TELEMETRY_PERIOD_MS == 200
    assert header["kStallMs"] == protocol.STALL_MS == 1000
    assert header["kStallMinSpeedMmS"] == protocol.STALL_MIN_SPEED_MM_S == 60
    assert header["kStallRatioPct"] == protocol.STALL_RATIO_PCT == 15


def test_parser_parity_table_matches_header():
    """Every ACCEPT case must be parseable by the C++ rules (documented here)."""
    accepted = ["F", "b", "L60", "r 255", "S", "S0", "F 1"]
    rejected = ["", "Q", "F999", "F1234", "F1 0", "F  1"]
    for payload in accepted:
        assert parse_command(payload)
    for payload in rejected:
        with pytest.raises(ProtocolError):
            parse_command(payload)


# ---------------------------------------------------------------------------
# Speed-scaled gate, telemetry frames
# ---------------------------------------------------------------------------
def test_required_gate_matches_firmware_curve():
    assert required_gate_cm(60) == 15
    assert required_gate_cm(180) == 27
    assert required_gate_cm(200) == 29
    assert required_gate_cm(255) == 35
    assert required_gate_cm(0) == 15    # clamped to the stiction floor
    assert required_gate_cm(999) == 35  # clamped to full speed


def _sample_telemetry() -> Telemetry:
    return Telemetry(1, "F", 180, 42, 7580, 0, 320, -320, 1200, 300, 45, 1250)


def test_telemetry_roundtrip():
    tlm = _sample_telemetry()
    line = encode_telemetry(tlm)
    assert line.startswith("T,1,F,180,42,7580,0,320,-320,1200,300,45,1250*")
    assert line.endswith("\n")
    assert parse_telemetry(line) == tlm


def test_telemetry_names():
    tlm = Telemetry(3, "S", 0, -1, 7400, 2)
    assert tlm.state_name == "TIMEOUT"
    assert tlm.fault_name == "BATTLOW"
    assert tlm.battery_v == 7.4
    assert STATE_NAMES[4] == "FAULT"
    assert FAULT_NAMES[3] == "STALL"


def test_telemetry_crc_is_required_by_default():
    with pytest.raises(ProtocolError):
        parse_telemetry(encode_telemetry(_sample_telemetry(), crc=False))
    assert parse_telemetry(encode_telemetry(_sample_telemetry(), crc=False), require_crc=False)


def test_telemetry_crc_is_checked():
    line = encode_telemetry(_sample_telemetry())
    body, _, crc_part = line.strip().partition("*")
    with pytest.raises(ProtocolError):
        parse_telemetry(f"{body}*00\n")
    assert crc_part  # sanity


@pytest.mark.parametrize("line", [
    "T,1,F",
    "T,1,F,1,2,3,4,5,6,7,8,9,10,11,12*00\n",   # too many fields
    "not telemetry",
    "",
])
def test_telemetry_rejects_malformed(line):
    with pytest.raises(ProtocolError):
        parse_telemetry(line)


@pytest.mark.parametrize("body", [
    "T,9,F,1,2,3,4,5,6,7,8,9,10",    # state out of range
    "T,1,F,1,2,3,9,5,6,7,8,9,10",    # fault out of range
    "T,1,FF,1,2,3,4,5,6,7,8,9,10",   # command not one char
    "T,1,F,x,2,3,4,5,6,7,8,9,10",    # non-numeric
])
def test_telemetry_rejects_out_of_range_fields(body):
    with pytest.raises(ProtocolError):
        parse_telemetry(f"{body}*{crc8(body):02X}\n")
