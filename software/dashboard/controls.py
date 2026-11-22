"""Command + telemetry link to the Arduino safety executive over one USB port.

The dashboard owns the single serial port: it writes one whitelisted character
(F/B/L/R/S) per press and folds the firmware's telemetry lines back into a
snapshot the page can render. While a motion key is held the link re-sends that
command on a heartbeat, because ``arduino/motion_safety`` stops the motors
whenever no command arrives within its comm watchdog window.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

VALID_COMMANDS: tuple[str, ...] = ("F", "B", "L", "R", "S")
MOTION_COMMANDS: tuple[str, ...] = ("F", "B", "L", "R")
DEFAULT_BAUD_RATE = 9600
BOOT_DRAIN_S = 2.0
HEARTBEAT_INTERVAL_S = 1.0

# Mirrors arduino/motion_safety/motion_safety.ino telemetry prefixes.
DIST_PREFIX = "DIST:"
CMD_PREFIX = "CMD:"
STATE_PREFIX = "STATE:"
STATUS_PREFIX = "STATUS:"
ALERT_PREFIX = "ALERT:"


def validate_command(command: str) -> str:
    """Return the canonical command or raise ``ValueError``."""
    cmd = (command or "").strip().upper()
    if cmd not in VALID_COMMANDS:
        raise ValueError(f"invalid command: {command!r}")
    return cmd


def parse_telemetry_line(line: str, state: dict[str, Any]) -> dict[str, Any]:
    """Fold one firmware telemetry line into ``state`` and return it."""
    text = (line or "").strip()
    if text.startswith("[UNO]"):
        text = text[5:].strip()
    if not text:
        return state
    if text.startswith(DIST_PREFIX):
        raw_part = text[len(DIST_PREFIX) :].strip()
        raw = raw_part.split()[0] if raw_part else ""
        try:
            value = float(raw)
        except ValueError:
            return state
        # -1.0 (or any negative) means the echo never returned: no distance.
        state["distance_cm"] = value if value >= 0 else None
        state["echo_ok"] = value >= 0
        return state
    if text.startswith(ALERT_PREFIX):
        state["alert"] = text
        state["alert_at"] = time.time()
        return state
    if text.startswith("BOOT"):
        state["status"] = "STOP"
    tokens = text.split()
    for i, part in enumerate(tokens):
        if part == "CMD:" and i + 1 < len(tokens):
            state["command"] = tokens[i + 1]
        elif part.startswith(CMD_PREFIX):
            val = part.split(":", 1)[1]
            if val:
                state["command"] = val
        elif part == "STATE:" and i + 1 < len(tokens):
            state["state"] = tokens[i + 1]
        elif part.startswith(STATE_PREFIX):
            val = part.split(":", 1)[1]
            if val:
                state["state"] = val
        elif part == "STATUS:" and i + 1 < len(tokens):
            state["status"] = tokens[i + 1]
        elif part.startswith(STATUS_PREFIX):
            val = part.split(":", 1)[1]
            if val:
                state["status"] = val
    return state


def _open_port(port: str, baud_rate: int) -> object:
    import serial

    return serial.Serial(port, baud_rate, timeout=0.2, write_timeout=1.0)


class ArduinoLink:
    """Bidirectional USB link: send commands, read telemetry, keep alive."""

    def __init__(
        self,
        port: str,
        baud_rate: int = DEFAULT_BAUD_RATE,
        *,
        mock: bool = False,
        open_port: Callable[[str, int], object] | None = None,
        boot_s: float = BOOT_DRAIN_S,
        heartbeat_s: float = HEARTBEAT_INTERVAL_S,
    ) -> None:
        self.port = port
        self.baud_rate = baud_rate
        self.mock = mock
        self.connected = False
        self._open_port = open_port
        self._boot_s = boot_s
        self._heartbeat_s = heartbeat_s
        self._lock = threading.Lock()
        self._serial: object | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._active = "S"
        self._last_write = 0.0
        self._history: list[dict[str, Any]] = []
        self._state: dict[str, Any] = {
            "port": port,
            "mock": mock,
            "distance_cm": None,
            "echo_ok": True,
            "state": "STOP",
            "command": "S",
            "status": "STOP",
            "active": "S",
            "alert": None,
            "alert_at": 0.0,
            "telemetry_at": 0.0,
            "sent_count": 0,
        }

    # ---- lifecycle ----
    def connect(self) -> bool:
        """Open the port, drain the bootloader, start the reader threads."""
        if self.mock:
            self.connected = True
            return True
        try:
            opener = self._open_port or _open_port
            self._serial = opener(self.port, self.baud_rate)
        except Exception as exc:
            logger.warning("could not open %s: %s", self.port, exc)
            self.connected = False
            return False
        self._drain_boot()
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        self.connected = True
        return True

    def close(self) -> None:
        self._running = False
        ser = self._serial
        self._serial = None
        if ser is not None:
            with contextlib.suppress(Exception):
                ser.close()
        self.connected = False

    # ---- writes ----
    def send(self, command: str) -> bool:
        """Send one whitelisted command and make it the heartbeat subject."""
        cmd = validate_command(command)
        with self._lock:
            self._active = cmd
        ok = self._write(cmd)
        if ok:
            with self._lock:
                self._state["sent_count"] = int(self._state["sent_count"]) + 1
                self._history.append({"cmd": cmd, "at": time.time()})
                del self._history[:-16]
        return ok

    def release(self) -> bool:
        """Stop the active motion command (what a key/button release sends)."""
        return self.send("S")

    def pump(self) -> bool:
        """Re-send the held motion command if the heartbeat is due."""
        with self._lock:
            active = str(self._state.get("active", "S"))
        if active not in MOTION_COMMANDS:
            return False
        now = time.monotonic()
        if now - self._last_write < self._heartbeat_s:
            return False
        return self._write(active)

    def _write(self, cmd: str) -> bool:
        if not self.mock:
            ser = self._serial
            if ser is None:
                return False
            try:
                ser.write(cmd.encode("ascii"))
                flush = getattr(ser, "flush", None)
                if callable(flush):
                    flush()
            except Exception as exc:
                logger.warning("serial write failed: %s", exc)
                return False
        self._last_write = time.monotonic()
        with self._lock:
            if self.mock:
                self._state["command"] = cmd
            self._state["active"] = cmd
        return True

    # ---- reads ----
    def telemetry(self) -> dict[str, Any]:
        with self._lock:
            snap = dict(self._state)
            snap["history"] = list(self._history)
        snap["connected"] = self.connected
        seen = float(snap.pop("telemetry_at", 0.0))
        snap["telemetry_age_s"] = round(time.time() - seen, 2) if seen > 0 else -1.0
        return snap

    def _drain_boot(self) -> None:
        """Skip the ~2 s reset after DTR toggles so boot garbage isn't telemetry."""
        ser = self._serial
        if ser is None or self._boot_s <= 0:
            return
        deadline = time.time() + self._boot_s
        while time.time() < deadline:
            try:
                if ser.readline():
                    continue
            except Exception:
                break
            time.sleep(0.05)

    def _read_loop(self) -> None:
        while self._running:
            ser = self._serial
            if ser is None:
                break
            try:
                raw = ser.readline()
            except Exception as exc:
                logger.warning("serial read failed: %s", exc)
                break
            if not raw:
                time.sleep(0.05)
                continue
            line = raw.decode("ascii", "replace")
            with self._lock:
                parse_telemetry_line(line, self._state)
                self._state["telemetry_at"] = time.time()

    def _heartbeat_loop(self) -> None:
        while self._running:
            time.sleep(0.2)
            self.pump()
