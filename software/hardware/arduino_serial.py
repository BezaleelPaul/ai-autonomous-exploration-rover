"""Serial controller for Arduino UNO. Mock-capable for hardware-independent tests."""

from __future__ import annotations

import contextlib
import logging
import re
import threading
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

VALID_COMMANDS = {"F", "B", "L", "R", "S"}

TELEMETRY_PREFIXES = ("DIST:", "STATUS:", "BATTERY:", "ERROR:", "TICKS:")

# Serial-port auto-detect (dev-loop speedup): descriptions that look like the
# rover's USB-serial bridge, and system ports that must never be picked.
BOARD_PORT_HINT = re.compile(
    r"arduino|ch340|ch341|cp210|wch|usb-serial|usb serial|ftdi|esp32|heltec",
    re.I,
)
BOARD_PORT_DENY = re.compile(
    r"intel\(r\) .*sol|bluetooth|communications port \(com\d+\)", re.I
)

# Arduino SA USB-VID (UNO/Nano/Mega). The ESP32 devkit's CP210x bridge is also
# "board-like", so VID/manufacturer is what breaks the tie: commands belong to
# the Arduino (it owns the whitelist and the safety gate), not the WiFi bridge.
ARDUINO_USB_VID = 0x2341


def _is_arduino(port) -> bool:
    if getattr(port, "vid", None) == ARDUINO_USB_VID:
        return True
    blob = f"{port.description or ''} {getattr(port, 'manufacturer', None) or ''}"
    return "arduino" in blob.lower()


def detect_board_port() -> str | None:
    """Best-effort: the serial port that looks like the rover's Arduino.

    Several board-like ports (an Arduino plus an ESP32 bridge) are common; the
    Arduino wins so auto-detect never sends F/B/L/R/S to the WiFi bridge.
    Returns None when nothing is found and the caller keeps the config value.
    """
    try:
        import serial.tools.list_ports as lp

        matches = [
            p
            for p in lp.comports()
            if BOARD_PORT_HINT.search(p.description or "")
            and not BOARD_PORT_DENY.search(p.description or "")
        ]
    except Exception:
        return None
    if len(matches) == 1:
        return matches[0].device
    if len(matches) > 1:
        arduino = [p for p in matches if _is_arduino(p)]
        if arduino:
            logger.warning(
                "several board-like ports %s - using the Arduino %s",
                [p.device for p in matches],
                arduino[0].device,
            )
            return arduino[0].device
        logger.warning(
            "several board-like ports %s - set serial.port in config.yaml",
            [p.device for p in matches],
        )
        return matches[0].device
    return None


@dataclass
class Telemetry:
    distance_cm: float | None = None
    status: str = "UNKNOWN"
    battery: str | None = None
    # Wheel-encoder tick counts from firmware TICKS:<left>,<right> (Phase 9+).
    encoder_ticks: tuple[int, int] | None = None
    heading_deg: float = 0.0
    tilt_deg: float = 0.0
    temperature_c: float | None = None
    last_update: float = 0.0
    # C1 (red-team): True until a valid in-range DIST arrives, and re-set by
    # any invalid/out-of-range/no-echo DIST. While True the link is unsafe
    # even if STATUS:OK keeps arriving (dead sensor must fail safe).
    sensor_fault: bool = True
    raw_lines: list = field(default_factory=list)


# Values the firmware may emit after "STATUS:". Anything else is noise and
# must never be counted as a live heartbeat (red-team M3).
RECOGNISED_STATUS = ("OK", "STOP", "ERROR")


class ArduinoSerial:
    """Thin wrapper over pyserial with mock mode + background reader.

    Protocol (documented in docs/hardware_protocol.md):
      PC -> Arduino: single char F|B|L|R|S [+ optional PWM 0..255] + '\\n'
      Arduino -> PC: 'DIST:<cm>', 'STATUS:OK|STOP|ERROR', 'TICKS:<l>,<r>', ...
    """

    def __init__(
        self,
        port: str = "COM3",
        baud_rate: int = 9600,
        command_timeout_s: float = 1.0,
        mock: bool = False,
        mock_distance_cm: float = 100.0,
        emergency_cm: float = 15.0,
        reconnect_attempts: int = 5,
    ):
        self.port = port
        self.baud_rate = baud_rate
        self.command_timeout_s = command_timeout_s
        self.mock = mock
        self.emergency_cm = emergency_cm
        self.reconnect_attempts = max(1, int(reconnect_attempts))
        self._mock_distance = mock_distance_cm
        self._ser = None
        self.telemetry = Telemetry()
        self._reader_thread: threading.Thread | None = None
        self._stop_reader = threading.Event()
        self.connected = False
        self.last_cmd_time = 0.0
        self.last_payload: str | None = None
        self.last_telemetry_time = time.time() if mock else 0.0
        if mock:
            self.connected = True
            self.telemetry.distance_cm = mock_distance_cm
            self.telemetry.status = "OK"
            self.telemetry.sensor_fault = False
            self.telemetry.last_update = time.time()
            self.last_telemetry_time = time.time()

    # ---------- connection ----------
    def connect(self) -> bool:
        if self.mock:
            self.connected = True
            return True
        if self._try_open(self.port):
            return True
        # Config failed (stale placeholder like COM3, or board moved): fall
        # back to auto-detect once so the dev loop never needs a config edit.
        detected = detect_board_port()
        if detected and detected != self.port:
            logger.warning(
                "serial.port %s failed to open; auto-detected %s",
                self.port,
                detected,
            )
            self.port = detected
            return self._try_open(detected)
        return False

    def _try_open(self, port: str) -> bool:
        for attempt in range(self.reconnect_attempts):
            try:
                import serial

                self._ser = serial.Serial(
                    port, self.baud_rate, timeout=self.command_timeout_s
                )
                time.sleep(2.0)  # Arduino auto-reset
                self.connected = True
                self._start_reader()
                return True
            except Exception:
                self.connected = False
                if attempt + 1 < self.reconnect_attempts:
                    time.sleep(0.5)
        return False

    def disconnect(self) -> None:
        self._stop_reader.set()
        with contextlib.suppress(Exception):
            self.send("S")
        if self._ser:
            with contextlib.suppress(Exception):
                self._ser.close()
        self.connected = False

    # ---------- commands ----------
    def send(self, cmd: str, speed: int | None = None) -> bool:
        """Send one command; optional Protocol-v2 PWM suffix (0..255)."""
        cmd = cmd.strip().upper()
        if cmd not in VALID_COMMANDS:
            raise ValueError(f"Invalid command {cmd!r}. Valid: {VALID_COMMANDS}")
        if speed is not None:
            if isinstance(speed, bool) or not isinstance(speed, int):
                raise ValueError(f"speed must be an int 0..255, got {speed!r}")
            if not (0 <= speed <= 255):
                raise ValueError(f"speed must be in 0..255, got {speed}")
        self.last_cmd_time = time.time()
        payload = cmd + ("" if speed is None else str(speed)) + "\n"
        self.last_payload = payload
        if self.mock:
            # mock Arduino safety: still record
            if self._mock_distance < self.emergency_cm and cmd == "F":
                self.telemetry.status = "STOP"
            return True
        if not self._ser or not self.connected:
            return False
        try:
            self._ser.write(payload.encode())
            return True
        except Exception:
            self.connected = False
            return False

    def stop(self) -> bool:
        return self.send("S")

    # ---------- telemetry ----------
    def parse_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        self.telemetry.raw_lines.append(line[-500:] if len(line) > 500 else line)
        self.telemetry.raw_lines = self.telemetry.raw_lines[-50:]
        now = time.time()
        if line.startswith("DIST:"):
            try:
                v = float(line.split(":", 1)[1])
            except ValueError:
                self.telemetry.sensor_fault = True  # garbage reading
                return
            if 0 <= v <= 500:
                self.telemetry.distance_cm = v
                self.telemetry.sensor_fault = False
                self.telemetry.last_update = now
                self.last_telemetry_time = now
            else:
                # Out-of-range / no-echo (-1): keep the last good value for
                # display but flag the sensor so the link reads unhealthy.
                self.telemetry.sensor_fault = True
        elif line.startswith("STATUS:"):
            value = line.split(":", 1)[1].strip()
            if value in RECOGNISED_STATUS:
                self.telemetry.status = value
                self.telemetry.last_update = now
                self.last_telemetry_time = now
            else:
                self.telemetry.status = "UNKNOWN"  # noise: never a heartbeat
        elif line.startswith("BATTERY:"):
            self.telemetry.battery = line.split(":", 1)[1].strip()
        elif line.startswith("TICKS:"):
            # Encoder counts are NOT a liveness signal: they must never
            # refresh the heartbeat (red-team M3). Malformed => ignored.
            try:
                left, right = line.split(":", 1)[1].split(",")
                self.telemetry.encoder_ticks = (int(left), int(right))
            except ValueError:
                pass
        elif line.startswith("IMU:"):
            try:
                parts = [float(p.strip()) for p in line.split(":", 1)[1].split(",")]
                if len(parts) >= 2:
                    self.telemetry.heading_deg = parts[0]
                    self.telemetry.tilt_deg = parts[1]
            except ValueError:
                pass
        elif line.startswith("TEMP:"):
            try:
                self.telemetry.temperature_c = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass

    def _start_reader(self) -> None:
        self._stop_reader.clear()
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        while not self._stop_reader.is_set():
            try:
                if self._ser and self._ser.in_waiting:
                    line = self._ser.readline().decode(errors="ignore")
                    self.parse_line(line)
                else:
                    time.sleep(0.02)
            except Exception:
                time.sleep(0.1)

    # ---------- health ----------
    def is_healthy(self, comm_timeout_s: float = 3.0) -> bool:
        """Link AND sensor health.

        Unhealthy when: not connected, telemetry older than comm_timeout_s,
        or the ultrasonic has not delivered a valid in-range reading
        (C1: a dead sensor must never read as a healthy rover).
        """
        if self.mock:
            return self.connected
        if not self.connected:
            return False
        if self.telemetry.sensor_fault:
            return False
        return (time.time() - self.last_telemetry_time) < comm_timeout_s

    def set_mock_distance(self, d: float) -> None:
        self._mock_distance = d
        self.telemetry.distance_cm = d
        self.last_telemetry_time = time.time()
