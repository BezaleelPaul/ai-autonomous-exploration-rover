"""Explore mode: a roam loop for the mission deck ("drop it in a room").

Pure state machine — no I/O. Each tick the pilot feeds ``(now, distance_cm,
world_blocked)`` and gets back ``(command, reason)``:

  drive  → forward while the path is clear
  scan   → stop and let scenesense/CLIP refresh the world facts
  turn   → pivot ~90 deg (alternating L/R so the rover zig-zags coverage)
  done   → time or turn budget exhausted; park

SafetyManager stays tier-1: every proposed command still passes the shared
safety gate in MissionPilot before it reaches the USB link.
"""

from __future__ import annotations

from typing import Any

STOP = "S"
DRIVE = "drive"
SCAN = "scan"
TURN = "turn"
DONE = "done"


class Explorer:
    """Roam loop state machine: drive → blocked → scan → turn → repeat."""

    def __init__(
        self,
        *,
        blocked_cm: float = 40.0,
        turn_s: float = 0.6,
        scan_s: float = 1.5,
        max_duration_s: float = 180.0,
        max_turns: int = 8,
    ) -> None:
        self.blocked_cm = float(blocked_cm)
        self.turn_s = float(turn_s)
        self.scan_s = float(scan_s)
        self.max_duration_s = float(max_duration_s)
        self.max_turns = int(max_turns)
        self.state = DONE
        self.turns = 0
        self._turn_dir = "L"
        self._since = 0.0
        self._started = 0.0

    @classmethod
    def from_config(cls, cfg: dict) -> Explorer:
        e = cfg.get("explore", {}) or {}
        return cls(
            blocked_cm=float(e.get("blocked_cm", 40.0)),
            turn_s=float(e.get("turn_s", 0.6)),
            scan_s=float(e.get("scan_s", 1.5)),
            max_duration_s=float(e.get("max_duration_s", 180.0)),
            max_turns=int(e.get("max_turns", 8)),
        )

    def start(self, now: float) -> None:
        """(Re)arm the loop; called when the pilot enters explore mode."""
        self.state = DRIVE
        self.turns = 0
        self._turn_dir = "L"
        self._started = now
        self._since = now

    def stop(self) -> None:
        self.state = DONE

    def propose(
        self, now: float, distance_cm, world_blocked: bool = False
    ) -> tuple[str, str]:
        """Advance one tick; returns (command, reason) for the safety gate."""
        if self.state == DONE:
            return STOP, "explore idle"
        if (now - self._started) >= self.max_duration_s or self.turns >= self.max_turns:
            self.state = DONE
            return STOP, "explore complete (budget)"
        blocked = bool(world_blocked)
        if isinstance(distance_cm, (int, float)) and distance_cm < self.blocked_cm:
            blocked = True
        if self.state == DRIVE:
            if blocked:
                self.state = SCAN
                self._since = now
                return STOP, "blocked - scanning"
            return "F", "exploring"
        if self.state == SCAN:
            if (now - self._since) >= self.scan_s:
                self.state = TURN
                self._since = now
                return self._turn_dir, "turning to new heading"
            return STOP, "scanning"
        # TURN: hold the pivot until turn_s elapses, then advance
        if (now - self._since) >= self.turn_s:
            self.turns += 1
            self._turn_dir = "R" if self._turn_dir == "L" else "L"
            self.state = DRIVE
            return "F", "heading clear - advancing"
        return self._turn_dir, "turning to new heading"

    def status(self) -> dict[str, Any]:
        return {"state": self.state, "turns": self.turns}
