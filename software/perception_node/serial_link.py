"""Write-only command link from the laptop to the rover (F/B/L/R/S at 9600 8N1).

Two selectable transports, per the two-tier spec:

* ``usb``       - a direct USB COM port (board auto-detect, Bluetooth excluded)
* ``bluetooth`` - the Bluetooth Classic SPP virtual COM port of the ESP32 bridge
* ``auto``      - explicit ``port`` first, then USB detect, then Bluetooth detect

An explicit port always wins, so a fixed BT adapter (e.g. ``COM5``) works in
any mode. The link never reads telemetry: tier-2 telemetry goes to the Arduino
USB Serial Monitor, not back over this one-way path.
"""

from __future__ import annotations

import contextlib
import logging
import re
import time

from software.hardware.arduino_serial import VALID_COMMANDS, detect_board_port

logger = logging.getLogger(__name__)

SERIAL_MODES: tuple[str, ...] = ("auto", "usb", "bluetooth")

# pyserial descriptions for a Bluetooth Classic SPP virtual serial port.
BLUETOOTH_HINT = re.compile(
    r"bluetooth|standard serial over bluetooth|bth\b|outgoing",
    re.I,
)


def _comports() -> list:
    import serial.tools.list_ports as lp

    return list(lp.comports())


def detect_bluetooth_port() -> str | None:
    """Best-effort: the single Bluetooth SPP virtual COM port, if any."""
    try:
        matches = [
            p
            for p in _comports()
            if BLUETOOTH_HINT.search(f"{p.description or ''} {p.hwid or ''}")
        ]
    except Exception:
        return None
    if len(matches) == 1:
        return matches[0].device
    if matches:
        logger.warning(
            "several Bluetooth ports %s - set perception.serial_port",
            [p.device for p in matches],
        )
        return matches[0].device
    return None


def resolve_serial_port(mode: str = "auto", preferred: str | None = None) -> str | None:
    """Pick the output port: explicit -> USB detect -> Bluetooth detect."""
    if mode not in SERIAL_MODES:
        raise ValueError(f"serial mode must be one of {SERIAL_MODES}, got {mode!r}")
    if preferred:
        return preferred
    if mode == "usb":
        return detect_board_port()
    if mode == "bluetooth":
        return detect_bluetooth_port()
    return detect_board_port() or detect_bluetooth_port()


def _open_serial(port: str, baud_rate: int, timeout_s: float) -> object:
    import serial

    return serial.Serial(
        port,
        baud_rate,
        timeout=timeout_s,
        write_timeout=timeout_s,
    )


class SerialLink:
    """Reconnecting, validated, single-character command sender."""

    def __init__(
        self,
        port: str | None = None,
        baud_rate: int = 9600,
        mode: str = "auto",
        timeout_s: float = 1.0,
        reconnect_attempts: int = 5,
        retry_backoff_s: float = 1.0,
        mock: bool = False,
    ) -> None:
        if mode not in SERIAL_MODES:
            raise ValueError(f"serial mode must be one of {SERIAL_MODES}, got {mode!r}")
        if baud_rate <= 0:
            raise ValueError(f"baud_rate must be > 0, got {baud_rate}")
        if reconnect_attempts < 1:
            raise ValueError("reconnect_attempts must be >= 1")
        self.mode = mode
        self.preferred_port = port
        self.baud_rate = int(baud_rate)
        self.timeout_s = float(timeout_s)
        self.reconnect_attempts = int(reconnect_attempts)
        self.retry_backoff_s = float(retry_backoff_s)
        self.mock = bool(mock)
        self.port: str | None = port
        self.connected = False
        self.sent: list[str] = []
        self._handle: object | None = None
        self._last_attempt = 0.0

    def connect(self) -> bool:
        """Open the link; failure is non-fatal (``send`` retries with backoff)."""
        if self.mock:
            self.connected = True
            return True
        port = resolve_serial_port(self.mode, self.preferred_port)
        if not port:
            logger.error(
                "no serial port found (mode=%s, port=%s) - check the cable / BT pairing",
                self.mode,
                self.preferred_port,
            )
            self.connected = False
            return False
        return self._open(port)

    def _open(self, port: str) -> bool:
        settle_s = (
            2.0 if port != self.preferred_port or self.mode != "bluetooth" else 0.2
        )
        for attempt in range(1, self.reconnect_attempts + 1):
            try:
                self._handle = _open_serial(port, self.baud_rate, self.timeout_s)
            except Exception as exc:
                logger.warning(
                    "open %s failed (%s/%s): %s",
                    port,
                    attempt,
                    self.reconnect_attempts,
                    exc,
                )
                time.sleep(0.5)
                continue
            self.port = port
            self.connected = True
            self._last_attempt = time.time()
            # An Arduino resets on DTR when its port opens: give it time to boot
            # so the first command is not swallowed by the bootloader.
            if settle_s:
                time.sleep(settle_s)
            logger.info("serial link up on %s @ %s baud", port, self.baud_rate)
            return True
        self.connected = False
        return False

    def _close_port(self) -> None:
        handle, self._handle = self._handle, None
        self.connected = False
        if handle is None:
            return
        with contextlib.suppress(Exception):
            handle.close()

    def _reconnect(self) -> bool:
        if self.mock:
            self.connected = True
            return True
        now = time.time()
        if (now - self._last_attempt) < self.retry_backoff_s:
            return False
        self._last_attempt = now
        self._close_port()
        port = resolve_serial_port(self.mode, self.preferred_port)
        return bool(port) and self._open(port)

    def send(self, command: str) -> bool:
        """Send one validated command; returns False when the link is down.

        Raises ``ValueError`` for anything outside the firmware whitelist, so a
        typo in the caller can never reach the motors.
        """
        cmd = (command or "").strip().upper()
        if cmd not in VALID_COMMANDS:
            raise ValueError(
                f"invalid command {command!r}; expected one of {sorted(VALID_COMMANDS)}"
            )
        if self.mock:
            self.sent.append(cmd)
            return True
        if not self.connected and not self._reconnect():
            return False
        try:
            self._handle.write(cmd.encode("ascii"))
            self.sent.append(cmd)
            return True
        except Exception as exc:
            logger.error("serial write failed on %s: %s", self.port, exc)
            self._close_port()
            return False

    def close(self) -> None:
        """Always leave the rover stopped, then release the port."""
        if self.mock:
            if self.connected:
                self.sent.append("S")
            self.connected = False
            return
        with contextlib.suppress(Exception):
            if self.connected and self._handle is not None:
                self._handle.write(b"S")
        self._close_port()

    @property
    def last_sent(self) -> str | None:
        return self.sent[-1] if self.sent else None
