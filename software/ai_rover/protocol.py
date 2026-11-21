"""Wire protocol for the AI Rover (Python mirror of firmware/common/protocol.h).

Why a mirror?  The laptop tier must reject exactly what the Uno rejects, and
the dataset/Kaggle tooling must never emit a command the firmware would drop.
``tests/test_protocol.py`` cross-checks this module against the C++ header so
the two can never drift silently.

Frame on the wire:  ``<CMD>[<SPEED>][*<CRC>]\\n``
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Constants: keep in sync with firmware/libraries/AIRoverCore/src/protocol.h
FORWARD_GATE_CM = 15
GATE_SPEED_CM = 20
REAR_GATE_CM = 15
LINK_WATCHDOG_MS = 500
SONAR_PERIOD_MS = 60
COMMAND_GAP_US = 15_000
SPEED_MIN = 60
SPEED_MAX = 255
DEFAULT_SPEED = 180
MAX_FRAME_LEN = 16
MAX_ARG_LEN = 8
SONAR_MAX_CM = 400
BATTERY_LOW_MV = 6400
BATTERY_RECOVER_MV = 6800
TELEMETRY_PERIOD_MS = 200
STALL_MS = 1000
STALL_MIN_SPEED_MM_S = 60
STALL_RATIO_PCT = 15

COMMANDS = ("F", "B", "L", "R", "S")
MOTION_COMMANDS = frozenset("FBLR")
ALL_COMMANDS = frozenset(COMMANDS)

_HEX = set("0123456789abcdefABCDEF")

STATE_NAMES = ("STOP", "GO", "BLOCKED", "TIMEOUT", "FAULT")
FAULT_NAMES = ("NONE", "ESTOP", "BATTLOW", "STALL")


class ProtocolError(ValueError):
    """Raised when a command would be rejected by either firmware."""


@dataclass(frozen=True)
class Packet:
    """A validated command.

    ``speed`` is ``None`` when the sender omitted it (the firmware then reuses
    the last speed) and always ``None`` for a stop.
    """

    cmd: str
    speed: int | None = None
    has_crc: bool = False

    @property
    def is_stop(self) -> bool:
        return self.cmd == "S"

    def frame(self) -> str:
        """Encode as it appears on the UART (includes the CRC and newline)."""
        return encode_command(self.cmd, self.speed)


def crc8(data: str | bytes, crc: int = 0) -> int:
    """CRC-8/SMBUS (poly 0x07, init 0x00). ``crc8(b"123456789") == 0xF4``."""
    if isinstance(data, str):
        data = data.encode("ascii")
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def canonical_command(cmd: str) -> str:
    """Uppercase a command, raising if it is outside the whitelist."""
    if not isinstance(cmd, str) or len(cmd) != 1:
        raise ProtocolError(f"command must be a single character, got {cmd!r}")
    up = cmd.upper()
    if up not in ALL_COMMANDS:
        raise ProtocolError(f"unknown command {cmd!r}; allowed: F B L R S")
    return up


def clamp_speed(speed: int) -> int:
    """Clamp a PWM value into the TT-gearmotor usable window (60..255)."""
    if isinstance(speed, bool) or not isinstance(speed, int):
        raise ProtocolError(f"speed must be an int, got {type(speed).__name__}")
    return max(SPEED_MIN, min(SPEED_MAX, speed))


def required_gate_cm(speed: int) -> int:
    """Forward gate for a commanded PWM: 15 cm floor, +20 cm at full speed."""
    s = clamp_speed(speed)
    return FORWARD_GATE_CM + ((s - SPEED_MIN) * GATE_SPEED_CM) // (SPEED_MAX - SPEED_MIN)


def _build_body(cmd: str, speed: int | None) -> str:
    c = canonical_command(cmd)
    if c == "S" or speed is None:
        return c
    if isinstance(speed, bool) or not isinstance(speed, int):
        raise ProtocolError("speed must be an int or None")
    if not 0 <= speed <= 255:
        raise ProtocolError(f"speed {speed} outside 0..255")
    return f"{c}{clamp_speed(speed)}"


def encode_command(cmd: str, speed: int | None = None, crc: bool = True) -> str:
    """Build the exact bytes the ESP32 forwards: ``"F200*6B\\n"``.

    ``crc=False`` produces the legacy/human form ``"F200\\n"``, which the Uno
    accepts on the USB bench port but rejects on the ESP32 link.
    """
    body = _build_body(cmd, speed)
    if not crc:
        return body + "\n"
    return f"{body}*{crc8(body):02X}\n"


def parse_command(text: str, require_crc: bool = False) -> Packet:
    """Parse an HTTP ``/cmd?c=`` value, a UART frame or a telemetry line.

    Mirrors ``rover::parsePacket`` exactly, including the quirks:
    lowercase is accepted, one space is tolerated, at most three digits,
    values above 255 are rejected (not clamped), and a CRC suffix must be
    well-formed and correct when present.
    """
    if not isinstance(text, str):
        raise ProtocolError("command payload must be text")
    body = text.rstrip("\r\n")
    if not body:
        raise ProtocolError("empty command")
    if not body.isascii():
        raise ProtocolError("frame is not ASCII")

    has_crc = False
    if "*" in body:
        body_part, _, crc_part = body.partition("*")
        if len(crc_part) != 2 or any(ch not in _HEX for ch in crc_part):
            raise ProtocolError(f"malformed CRC suffix {crc_part!r}")
        expected = int(crc_part, 16)
        if crc8(body_part) != expected:
            raise ProtocolError("CRC mismatch")
        body = body_part
        has_crc = True
    elif require_crc:
        raise ProtocolError("CRC required on the ESP32 link")

    if len(body) > MAX_ARG_LEN:
        raise ProtocolError(f"payload longer than {MAX_ARG_LEN} characters")

    try:
        cmd = canonical_command(body[0])
    except ProtocolError:
        raise ProtocolError(f"unknown command {body[0]!r}; allowed: F B L R S") from None

    rest = body[1:]
    if rest.startswith(" "):
        rest = rest[1:]
    if rest == "":
        return Packet(cmd, None, has_crc)

    if not rest.isascii() or not rest.isdigit():
        raise ProtocolError(f"speed must be ASCII digits, got {rest!r}")
    if len(rest) > 3:
        raise ProtocolError("speed field longer than 3 digits")
    value = int(rest)
    if value > 255:
        raise ProtocolError(f"speed {value} outside 0..255")
    if cmd == "S":
        return Packet("S", None, has_crc)
    return Packet(cmd, value, has_crc)


def parse_frame(frame: bytes | str, require_crc: bool = False) -> Packet:
    """Parse a raw UART frame (bytes or str), validating ASCII."""
    if isinstance(frame, bytes):
        try:
            text = frame.decode("ascii")
        except UnicodeDecodeError:
            raise ProtocolError("frame is not ASCII") from None
    else:
        text = frame
    return parse_command(text, require_crc=require_crc)


@dataclass(frozen=True)
class Telemetry:
    """Uno -> ESP32 status frame (firmware version 1.3+)."""

    state: int
    cmd: str
    pwm: int
    dist_cm: int
    battery_mv: int
    fault: int
    speed_l_mm_s: int = 0
    speed_r_mm_s: int = 0
    x_mm: int = 0
    y_mm: int = 0
    theta_deg: int = 0
    odometer_mm: int = 0

    @property
    def state_name(self) -> str:
        return STATE_NAMES[self.state] if 0 <= self.state < len(STATE_NAMES) else "?"

    @property
    def fault_name(self) -> str:
        return FAULT_NAMES[self.fault] if 0 <= self.fault < len(FAULT_NAMES) else "?"

    @property
    def battery_v(self) -> float:
        return self.battery_mv / 1000.0

    def as_dict(self) -> dict:
        return {
            "state": self.state_name,
            "cmd": self.cmd,
            "pwm": self.pwm,
            "dist_cm": self.dist_cm,
            "battery_mv": self.battery_mv,
            "fault": self.fault_name,
            "speed_l_mm_s": self.speed_l_mm_s,
            "speed_r_mm_s": self.speed_r_mm_s,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "theta_deg": self.theta_deg,
            "odometer_mm": self.odometer_mm,
        }


def encode_telemetry(tlm: Telemetry, crc: bool = True) -> str:
    """Build the exact Uno telemetry line (with CRC and newline)."""
    body = (
        f"T,{int(tlm.state)},{tlm.cmd},{int(tlm.pwm)},{int(tlm.dist_cm)},{int(tlm.battery_mv)},"
        f"{int(tlm.fault)},{int(tlm.speed_l_mm_s)},{int(tlm.speed_r_mm_s)},"
        f"{int(tlm.x_mm)},{int(tlm.y_mm)},{int(tlm.theta_deg)},{int(tlm.odometer_mm)}"
    )
    if not crc:
        return body + "\n"
    return f"{body}*{crc8(body):02X}\n"


def parse_telemetry(line: str, require_crc: bool = True) -> Telemetry:
    """Validate and parse a ``T,...*HH`` telemetry frame."""
    if not isinstance(line, str):
        raise ProtocolError("telemetry must be text")
    body = line.strip()
    if not body.startswith("T,"):
        raise ProtocolError("not a telemetry frame")
    if "*" in body:
        body, _, crc_part = body.partition("*")
        if len(crc_part) != 2 or any(ch not in _HEX for ch in crc_part):
            raise ProtocolError("malformed telemetry CRC")
        if crc8(body) != int(crc_part, 16):
            raise ProtocolError("telemetry CRC mismatch")
    elif require_crc:
        raise ProtocolError("telemetry CRC required")

    parts = body.split(",")
    if len(parts) != 13 or parts[0] != "T":
        raise ProtocolError(f"expected 13 telemetry fields, got {len(parts)}")
    if len(parts[2]) != 1:
        raise ProtocolError("bad command field")
    try:
        values = [int(p) for p in (parts[1], *parts[3:])]
    except ValueError:
        raise ProtocolError("non-numeric telemetry field") from None
    state = values[0]
    if not 0 <= state <= 4:
        raise ProtocolError("telemetry state out of range")
    fault = values[4]
    if not 0 <= fault <= 3:
        raise ProtocolError("telemetry fault out of range")
    return Telemetry(
        state=state,
        cmd=parts[2],
        pwm=values[1],
        dist_cm=values[2],
        battery_mv=values[3],
        fault=fault,
        speed_l_mm_s=values[5],
        speed_r_mm_s=values[6],
        x_mm=values[7],
        y_mm=values[8],
        theta_deg=values[9],
        odometer_mm=values[10],
    )
