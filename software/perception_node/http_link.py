"""HTTP transport to the ESP32 WiFi web bridge (``/cmd?c=F``).

Selected when ``perception.serial_mode`` is ``http``; mirrors the
``SerialLink`` surface (``connect``/``send``/``close``/``connected``) so the
node and tests treat both transports identically.
"""

from __future__ import annotations

import contextlib
import logging
import urllib.request

from software.hardware.arduino_serial import VALID_COMMANDS

logger = logging.getLogger(__name__)


class HttpLink:
    """Sends motion commands to the ESP32 soft-AP web API."""

    def __init__(self, base_url: str, *, timeout_s: float = 1.0, mock: bool = False):
        base = (base_url or "").strip().rstrip("/")
        if not base.startswith(("http://", "https://")):
            raise ValueError(f"rover_url must be an http(s) URL, got {base_url!r}")
        self.base_url = base
        self.timeout_s = float(timeout_s)
        self.mock = bool(mock)
        self.connected = False
        self.sent: list[str] = []

    def connect(self) -> bool:
        if self.mock:
            self.connected = True
            return True
        return self._ping()

    def _ping(self) -> bool:
        try:
            with urllib.request.urlopen(
                f"{self.base_url}/status", timeout=self.timeout_s
            ) as response:
                response.read(256)
            self.connected = True
            return True
        except Exception as exc:
            logger.warning("http bridge unreachable (%s): %s", self.base_url, exc)
            self.connected = False
            return False

    def send(self, command: str) -> bool:
        cmd = (command or "").strip().upper()
        if cmd not in VALID_COMMANDS:
            raise ValueError(
                f"invalid command {command!r}; expected one of {sorted(VALID_COMMANDS)}"
            )
        if self.mock:
            self.sent.append(cmd)
            return True
        try:
            with urllib.request.urlopen(
                f"{self.base_url}/cmd?c={cmd}", timeout=self.timeout_s
            ) as response:
                response.read(64)
            self.connected = True
            self.sent.append(cmd)
            return True
        except Exception as exc:
            logger.error("http send failed: %s", exc)
            self.connected = False
            return False

    def close(self) -> None:
        if self.connected:
            with contextlib.suppress(Exception):
                self.send("S")
        self.connected = False
