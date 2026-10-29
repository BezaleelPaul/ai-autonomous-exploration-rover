"""Canonical control-layer steering helpers for the headless path.

This is the single home for the headless rover's decision primitives:

* :func:`command_for_position` - position -> command/state mapping. It delegates
  the actual zone -> command mapping to :func:`perception_node.zones.
  command_for_zone` so LEFT/RIGHT/FORWARD is defined exactly once (the same
  definition the Mission Deck's ``SteeringPolicy`` uses).
* :func:`p_steer_speed` - proportional turn PWM (Protocol v2).
* :class:`AntiOscillation` - blocks rapid L<->R flips; STOP is never delayed.
* :class:`SearchRotation` - finite rotate-to-acquire search (timeout + capped
  rotations, so it can never spin forever).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from software.perception_node.zones import (
    STOP,
    TURN_LEFT,
    TURN_RIGHT,
    Zone,
    command_for_zone,
)

#: Perceived position strings -> steering zones.
POSITION_ZONES: dict[str, Zone] = {
    "LEFT": Zone.LEFT,
    "CENTER": Zone.CENTER,
    "RIGHT": Zone.RIGHT,
}


def command_for_position(
    position: str, very_close: bool, target_present: bool
) -> tuple[str, str]:
    """Map a perceived target position to ``(command, state)``.

    Mirrors the historical decision engine exactly: no target or a very close
    target stops, otherwise the zone decides left/right/forward and an unknown
    position is observed (stop).
    """
    if not target_present:
        return STOP, "SEARCHING"
    if very_close:
        return STOP, "STOPPED"
    zone = POSITION_ZONES.get(position)
    if zone is None:
        return STOP, "OBSERVE"
    command = command_for_zone(zone)
    state = "APPROACHING" if zone is Zone.CENTER else "ALIGNING"
    return command, state


def p_steer_speed(
    command: str, center_error: float, kp: float, min_pwm: int
) -> int | None:
    """Proportional turn PWM for L/R commands, clamped to [min_pwm, 255].

    Returns ``None`` when P-steering is disabled (``kp <= 0``) or the command is
    not a turn, which leaves the firmware's open-loop speed in charge.
    """
    if command in (TURN_LEFT, TURN_RIGHT) and kp > 0:
        speed = round(kp * abs(center_error))
        return max(min_pwm, min(255, speed))
    return None


class AntiOscillation:
    """Rate-limits command changes to stop the rover flapping L<->R.

    ``STOP`` always passes immediately (a safety stop must never be delayed);
    an ``L``/``R`` reversal waits ``min_command_duration_s``; any other change
    waits ``cooldown_s``. A blocked change holds the previous command.
    """

    def __init__(
        self, min_command_duration_s: float = 0.4, cooldown_s: float = 0.2
    ) -> None:
        self.min_command_duration_s = float(min_command_duration_s)
        self.cooldown_s = float(cooldown_s)
        self.last_command = STOP
        self.last_command_time = 0.0

    def can_switch(self, new_command: str, now: float) -> bool:
        if new_command == self.last_command:
            return True
        if {new_command, self.last_command} == {TURN_LEFT, TURN_RIGHT}:
            return (now - self.last_command_time) >= self.min_command_duration_s
        return (now - self.last_command_time) >= self.cooldown_s

    def apply(self, command: str, now: float) -> str:
        """Return the command to issue, updating history when it is accepted.

        ``STOP`` always passes immediately, and a command may always *leave* a
        STOP state without waiting: STOP is not a state to oscillate against,
        so resuming must not be throttled (an emergency release must not wait
        out the anti-chatter window either). Only motion-to-motion changes are
        rate limited, which is what prevents the rover flapping L<->R.
        """
        if (
            command != STOP
            and self.last_command != STOP
            and not self.can_switch(command, now)
        ):
            return self.last_command
        self.last_command = command
        self.last_command_time = now
        return command


@dataclass
class RotationState:
    active: bool = False
    start_time: float = 0.0
    rotations: int = 0
    found: bool = False


class SearchRotation:
    """Rotate-in-place search with a timeout and a rotation cap.

    ``update`` returns ``(command, done, message)``; it yields ``"R"`` while
    scanning and ``"S"`` once the target is found, the timeout elapses, or the
    rotation cap is reached - so a search always terminates.
    """

    def __init__(
        self,
        timeout_s: float = 30.0,
        max_rotations: int = 2,
        rotation_duration_s: float = 20.0,
    ) -> None:
        self.timeout_s = float(timeout_s)
        self.max_rotations = int(max_rotations)
        self.rotation_duration_s = float(rotation_duration_s)
        self.state = RotationState()

    @property
    def active(self) -> bool:
        return self.state.active

    def start(self, now: float | None = None) -> None:
        self.state = RotationState(
            active=True, start_time=now if now is not None else time.time()
        )

    def stop(self) -> None:
        self.state.active = False

    def update(
        self, target_present: bool, now: float | None = None
    ) -> tuple[str, bool, str]:
        now = now if now is not None else time.time()
        if not self.state.active:
            return STOP, True, "not active"
        if target_present:
            self.state.found = True
            self.state.active = False
            return STOP, True, "target found"
        elapsed = now - self.state.start_time
        if elapsed > self.timeout_s:
            self.state.active = False
            return STOP, True, "search timeout"
        self.state.rotations = int(elapsed / self.rotation_duration_s)
        if self.state.rotations >= self.max_rotations:
            self.state.active = False
            return STOP, True, "max rotations reached"
        return TURN_RIGHT, False, f"scanning {elapsed:.1f}s"
