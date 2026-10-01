"""R5: manual-mode motion guard.

Manual mode only transmits on keypress, so without this the Arduino would
keep executing the last drive command for up to comm_timeout_s (3s) after
the operator releases the key. This guard re-sends STOP when no new command
arrives within timeout_s (config: rover.movement_timeout_s), keeping manual
motion bounded to a short pulse per keypress.
"""

from __future__ import annotations

import threading
from collections.abc import Callable


class ManualMotionGuard:
    def __init__(self, send: Callable[[str], bool], timeout_s: float = 1.0):
        if timeout_s <= 0:
            raise ValueError("timeout_s must be > 0")
        self._send = send
        self._timeout_s = timeout_s
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def send(self, cmd: str) -> bool:
        cmd = (cmd or "S").upper()
        with self._lock:
            self._cancel_locked()
            ok = self._send(cmd)
            if cmd != "S":
                self._timer = threading.Timer(self._timeout_s, self._auto_stop_locked)
                self._timer.daemon = True
                self._timer.start()
            return bool(ok)

    def _auto_stop_locked(self) -> None:
        with self._lock:
            self._send("S")
            self._timer = None

    def _cancel_locked(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def close(self) -> None:
        """Cancel pending timer and force STOP (call on loop exit)."""
        with self._lock:
            self._cancel_locked()
            self._send("S")
