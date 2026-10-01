"""Failsafe: default action is always STOP."""

from __future__ import annotations

from collections.abc import Callable


def safe_stop(send_fn: Callable[[str], bool]) -> bool:
    try:
        return bool(send_fn("S"))
    except Exception:
        return False
