"""Finite-state decision engine: PERCEPTION -> DECISION -> SAFETY -> CONTROL."""

from __future__ import annotations

import time
from dataclasses import dataclass

STATES = (
    "IDLE",
    "MANUAL",
    "OBSERVE",
    "SEARCHING",
    "ALIGNING",
    "APPROACHING",
    "AVOIDING",
    "STOPPED",
    "EMERGENCY_STOP",
    "ERROR",
)


# Anti-oscillation: minimum time before reversing L<->R
@dataclass
class Decision:
    command: str
    state: str
    reason: str
    speed: int | None = None  # Protocol-v2 PWM for L/R turns (None = bare cmd)
    v_left: int | None = None  # Differential drive left wheel speed
    v_right: int | None = None  # Differential drive right wheel speed


class DecisionEngine:
    def __init__(
        self,
        center_tolerance: float = 0.06,
        min_command_duration_s: float = 0.4,
        cooldown_s: float = 0.2,
        stop_width_ratio: float = 0.45,
        steering_kp: float = 0.0,
        steering_min_pwm: int = 120,
    ):
        self.state = "IDLE"
        self.center_tol = center_tolerance
        self.min_cmd_dur = min_command_duration_s
        self.cooldown = cooldown_s
        self.stop_ratio = stop_width_ratio
        self.steering_kp = steering_kp
        self.steering_min_pwm = steering_min_pwm
        self._last_cmd = "S"
        self._last_cmd_time = 0.0
        self._last_dir = "S"  # last L/R to prevent flapping

    def _can_switch(self, new_cmd: str, now: float) -> bool:
        if new_cmd == self._last_cmd:
            return True
        # block rapid L<->R flips
        if {new_cmd, self._last_cmd} == {"L", "R"}:
            return (now - self._last_cmd_time) >= self.min_cmd_dur
        return (now - self._last_cmd_time) >= self.cooldown

    def decide(
        self,
        position: str,
        very_close: bool,
        target_present: bool,
        now: float | None = None,
        center_error: float = 0.0,
    ) -> Decision:
        now = now if now is not None else time.time()
        if not target_present:
            desired, state = "S", "SEARCHING"
        elif very_close:
            desired, state = "S", "STOPPED"
        elif position == "LEFT":
            desired, state = "L", "ALIGNING"
        elif position == "RIGHT":
            desired, state = "R", "ALIGNING"
        elif position == "CENTER":
            desired, state = "F", "APPROACHING"
        else:
            desired, state = "S", "OBSERVE"

        # STOP must never be delayed by the anti-oscillation hold (M4).
        if desired != "S" and not self._can_switch(desired, now):
            desired = self._last_cmd  # hold to avoid oscillation
            state = self.state
        else:
            self._last_cmd = desired
            self._last_cmd_time = now
            self.state = state

        # P-steering: proportional turn PWM on L/R (speed=None leaves the
        # firmware's bare-command behavior). Disabled when kp == 0.
        speed: int | None = None
        v_l: int | None = None
        v_r: int | None = None
        if desired in ("L", "R") and self.steering_kp > 0:
            speed = round(self.steering_kp * abs(center_error))
            speed = max(self.steering_min_pwm, min(255, speed))

        # Layer 5: Visual differential steering: v_L = v - k*e_x, v_R = v + k*e_x
        if desired in ("F", "L", "R"):
            e_x = 2.0 * center_error  # normalized horizontal error e_x in [-1.0, 1.0]
            base_v = 180
            k_diff = 60.0
            v_l = int(max(0, min(255, round(base_v - k_diff * e_x))))
            v_r = int(max(0, min(255, round(base_v + k_diff * e_x))))

        return Decision(
            desired,
            self.state,
            f"pos={position} close={very_close}",
            speed=speed,
            v_left=v_l,
            v_right=v_r,
        )

    def to_search(self) -> None:
        self.state = "SEARCHING"

    def emergency(self) -> Decision:
        # state-only marker: decide() keeps command history, so the next
        # decide() is never delayed by the anti-oscillation clock (M4)
        self.state = "EMERGENCY_STOP"
        return Decision("S", self.state, "emergency")
