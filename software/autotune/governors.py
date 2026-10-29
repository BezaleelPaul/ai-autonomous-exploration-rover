"""Online governors: turn a live signal into a scalar cost the tuner can rank.

Only one governor runs online, and it exists because of a *measured* defect
(README section 5, red-team H4): inference latency is load-sensitive, so a
fixed ``ai.inference_interval`` either wastes CPU when the host is idle or
breaks the realtime contract when it is busy.

``RealtimeGovernor`` keeps the detection refresh inside
``autotune.budget_margin x navigation.target_lock_duration_s`` and, subject to
that contract, spends the leftover headroom on the *largest* interval (so the
slow world-model plugins keep a CPU budget of their own). It explores
analytically — one latency sample predicts every candidate — so no candidate
is ever applied during exploration and the loop never runs degraded while it
decides. Once committed it is re-checked every window and thrown back to
exploration when the world changes.
"""

from __future__ import annotations

from typing import Any

from software.autotune.core import COMMITTING, AutoTuner

INTERVAL_SPACE = "ai.inference_interval"

DEFAULT_WINDOW_S = 2.0
DEFAULT_BUDGET_MARGIN = 0.25
DEFAULT_ALPHA = 0.3
# Seconds of over-budget refresh are worth this much headroom: any violation,
# however small, must outweigh the "prefer a roomier interval" term.
VIOLATION_PENALTY = 1000.0
# A candidate exactly at the budget must count as feasible. Accumulated float
# error (5 * 0.10000000000000003 = 0.5000000000000002) otherwise marks the
# boundary candidate infeasible and adds a ~1e-10 penalty that trips re-arm.
FEASIBILITY_EPS = 1e-9


def ema(previous: float | None, sample: float, alpha: float) -> float:
    """Exponentially weighted mean; the first sample seeds it."""
    if previous is None:
        return float(sample)
    return alpha * float(sample) + (1.0 - alpha) * previous


class RealtimeGovernor:
    """Adaptive inference pacing against the H4 freshness budget."""

    space = INTERVAL_SPACE

    def __init__(
        self,
        tuner: AutoTuner,
        *,
        interval: int = 1,
        budget_s: float,
        window_s: float = DEFAULT_WINDOW_S,
        lo: int = 1,
        hi: int = 8,
        alpha: float = DEFAULT_ALPHA,
    ) -> None:
        if budget_s <= 0:
            raise ValueError("budget_s must be > 0")
        self.tuner = tuner
        self.lo = max(1, int(lo))
        self.hi = max(self.lo, int(hi))
        self.budget_s = float(budget_s)
        self.window_s = float(window_s)
        self.alpha = float(alpha)
        self.interval = max(self.lo, min(self.hi, int(interval)))
        self._infer_ms: float | None = None
        self._refresh_s: float | None = None
        self._last_at: float | None = None
        self._window_start = 0.0
        self.action = "init"

    # ------------------------------------------------------------- measuring
    def observe(self, now: float, infer_ms: float) -> str:
        """Feed one completed inference; returns the action taken."""
        if not self.tuner.enabled:
            self.action = "disabled"
            return self.action
        self._infer_ms = ema(self._infer_ms, infer_ms, self.alpha)
        if self._last_at is not None:
            refresh = now - self._last_at
            if 0.0 < refresh < 60.0:
                self._refresh_s = ema(self._refresh_s, refresh, self.alpha)
        self._last_at = now
        if self._window_start <= 0.0:
            self._window_start = now
            self.action = "warmup"
            return self.action
        if now - self._window_start < self.window_s:
            self.action = "measure"
            return self.action
        self._window_start = now
        return self.evaluate(now)

    def evaluate(self, now: float) -> str:
        """Close the measurement window: explore analytically, else monitor."""
        per_frame = self.per_frame()
        if per_frame <= 0.0:
            self.action = "hold"
            return self.action
        owed = self.tuner.next(self.space)
        if owed:
            self.tuner.report(
                self.space,
                {
                    k: (
                        self.cost(k, per_frame),
                        self.within_budget(k, per_frame),
                    )
                    for k in owed
                },
            )
            self._apply()
            self.action = "explore"
            return self.action
        if self.tuner.phase(self.space) != COMMITTING:
            self.action = "hold"
            return self.action
        k = int(self.tuner.value(self.space))
        self.action = self.tuner.monitor(
            self.space,
            self.cost(k, per_frame),
            self.within_budget(k, per_frame),
        )
        self._apply()
        return self.action

    # ------------------------------------------------------------ cost model
    def per_frame(self) -> float:
        """Seconds one loop pass costs (refresh / interval, else infer only)."""
        if self._refresh_s is not None and self.interval >= 1:
            return self._refresh_s / float(self.interval)
        if self._infer_ms is not None:
            return self._infer_ms / 1000.0
        return 0.0

    def predict(self, interval: int, per_frame: float) -> float:
        """Modelled detection refresh (seconds) at ``interval``."""
        return float(interval) * per_frame

    def within_budget(self, interval: int, per_frame: float) -> bool:
        """Does ``interval`` close the H4 loop? Exactly-at-budget counts as yes."""
        return self.predict(interval, per_frame) <= self.budget_s + FEASIBILITY_EPS

    def cost(self, interval: int, per_frame: float) -> float:
        """Lower is better: stay inside the budget, then use the headroom.

        ``1 - normalised interval`` rewards the largest interval that still
        closes the loop; the penalty term makes any over-budget prediction
        lose to every feasible candidate regardless of headroom.
        """
        span = max(1, self.hi - self.lo)
        headroom = 1.0 - (float(interval) - self.lo) / span
        overrun = self.predict(interval, per_frame) - self.budget_s - FEASIBILITY_EPS
        violation = max(0.0, overrun)
        return headroom + VIOLATION_PENALTY * (violation / max(self.budget_s, 1e-9))

    # ------------------------------------------------------------- applying
    def _apply(self) -> None:
        wanted = max(self.lo, min(self.hi, int(self.tuner.value(self.space))))
        if wanted == self.interval:
            return
        self.interval = wanted
        # The refresh EMA was measured at the old pacing: drop it so the next
        # window is judged on the new interval instead of a stale product.
        self._refresh_s = None
        self._last_at = None

    def status(self) -> dict[str, Any]:
        return {
            "interval": self.interval,
            "budget_s": round(self.budget_s, 3),
            "window_s": self.window_s,
            "per_frame_ms": (
                None if self.per_frame() <= 0 else round(self.per_frame() * 1000, 1)
            ),
            "predict_refresh_s": (
                None
                if self.per_frame() <= 0
                else round(self.predict(self.interval, self.per_frame()), 3)
            ),
            "action": self.action,
        }
