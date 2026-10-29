"""One throttled command emitter, shared by every control path.

The Arduino safety executive stops the motors when no command arrives inside
its comm watchdog window, so a sustained motion command must be re-sent on a
heartbeat. Both the perception node and the mission pilot need exactly that
policy:

  * STOP is sent immediately whenever it changes (a stop is never delayed);
  * a motion command is sent on change once the cooldown has elapsed, and
    re-sent on the heartbeat so the watchdog never trips;
  * a rejected/failed write leaves the recorded state untouched so the next
    tick retries.

Keeping it in one place means the two control paths can never drift apart.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

STOP = "S"


class CommandEmitter:
    """Throttle + heartbeat for one command link."""

    def __init__(
        self,
        send: Callable[[str], object] | None,
        *,
        cooldown_s: float = 0.2,
        heartbeat_s: float = 1.0,
    ) -> None:
        self._send = send
        self.cooldown_s = float(cooldown_s)
        self.heartbeat_s = float(heartbeat_s)
        self.last_sent: str | None = None
        self.last_send_time = 0.0

    def reset(self, command: str | None = None, now: float | None = None) -> None:
        """Forget the throttle history (e.g. after a direct out-of-band STOP)."""
        if command is not None:
            self.last_sent = command
        self.last_send_time = time.time() if now is None else float(now)

    def emit(self, command: str, now: float) -> str | None:
        """Send ``command`` if the throttle allows; return it when written."""
        if self._send is None:
            return None
        elapsed = now - self.last_send_time
        changed = command != self.last_sent
        if command == STOP and changed:
            eligible = True
        else:
            eligible = (changed and elapsed >= self.cooldown_s) or (
                elapsed >= self.heartbeat_s
            )
        if not eligible:
            return None
        try:
            ok = bool(self._send(command))
        except ValueError:
            logger.warning("command %r rejected by the link", command)
            return None
        except Exception:
            logger.exception("command send failed")
            return None
        if ok:
            self.last_sent = command
            self.last_send_time = now
            return command
        return None
