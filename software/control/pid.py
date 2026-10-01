"""PID controller with anti-windup — foundation for closed-loop drive (Phase 9+).

Gains live in config/config.yaml `control:` and are read by `pid_from_config`.
Nothing here touches motors directly: the safety chain (SafetyManager ->
firmware watchdog) stays authoritative. Physical validation is HARDWARE
REQUIRED; unit tests only prove the math.
"""

from __future__ import annotations


class PID:
    """Discrete PID with clamped output and integral anti-windup."""

    def __init__(
        self,
        kp: float,
        ki: float = 0.0,
        kd: float = 0.0,
        out_min: float = -255.0,
        out_max: float = 255.0,
    ):
        if kp < 0 or ki < 0 or kd < 0:
            raise ValueError("PID gains must be >= 0")
        if out_min >= out_max:
            raise ValueError("out_min must be < out_max")
        self.kp = float(kp)
        self.ki = float(ki)
        self.kd = float(kd)
        self.out_min = float(out_min)
        self.out_max = float(out_max)
        self._integral = 0.0
        self._prev_error: float | None = None

    def reset(self) -> None:
        """Clear accumulated state (call on mode change or fault)."""
        self._integral = 0.0
        self._prev_error = None

    def update(self, error: float, dt: float) -> float:
        """Control output for `error` over elapsed `dt` seconds.

        dt <= 0 returns 0 (no time passed => no action, no division by zero).
        The integral term is clamped to the output range (anti-windup), and the
        final output is clamped to [out_min, out_max].
        """
        if dt <= 0:
            return 0.0
        p = self.kp * error
        self._integral += self.ki * error * dt
        self._integral = max(self.out_min, min(self.out_max, self._integral))
        d = 0.0
        if self._prev_error is not None:
            d = self.kd * (error - self._prev_error) / dt
        self._prev_error = error
        return max(self.out_min, min(self.out_max, p + self._integral + d))


def pid_from_config(cfg: dict) -> PID:
    """Build the drive PID from config.yaml `control:` gains."""
    ctl = cfg.get("control", {})
    return PID(
        kp=float(ctl.get("pid_kp", 0.0)),
        ki=float(ctl.get("pid_ki", 0.0)),
        kd=float(ctl.get("pid_kd", 0.0)),
    )
