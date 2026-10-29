"""Auto-tune core: EXPLORE -> COMMIT -> MONITOR -> RE-ARM.

The rover ships with hand-measured starting values (README section 5). This
module lets a parameter *find its own* value at runtime and then **stabilise**:

1. **EXPLORE** — evaluate every candidate of a small, explicitly bounded
   ``SearchSpace``. The space is enumerated, never unbounded, so exploration
   always terminates.
2. **COMMIT** — keep the candidate with the lowest reported cost. Ties resolve
   to the ``anchor`` (the shipped default, or a value learned in a previous
   session), so a window with no usable signal cannot drift a parameter away
   from what the project shipped with.
3. **MONITOR** — keep scoring the committed value. While its cost stays inside
   the re-arm band the parameter is *stable* and the tuner reports ``stable``.
4. **RE-ARM** — a cost that degrades past ``rearm_ratio`` (a hard constraint
   broke, the host got busy) or improves past ``improve_ratio`` (the world got
   easier, so a better candidate may now exist) throws the space back to
   EXPLORE and **discards the stale measurements**.

**Hysteresis.** Cost alone is not a stable signal once a hard constraint is
already broken: a governor whose cost is dominated by a violation penalty (the
realtime governor's ``VIOLATION_PENALTY``) turns latency jitter into huge
apparent degrades and improves. Re-arming on that produced a measured thrash
loop — 16 commits / 15 re-arms in 90 s on an over-budget host, never settling.
So while the committed value is *already* infeasible, only a **change in
feasibility** re-arms; movement inside the infeasible region is treated as
noise. A feasible→infeasible transition still re-arms (real degradation), and
an infeasible→feasible transition still re-arms (the world got easier).

Nothing here knows about cameras, detectors or motors: the caller supplies a
scalar cost plus a feasibility flag, which keeps the whole algorithm testable
without hardware. Safety is out of scope by construction — a governor may only
move values inside its declared ``SearchSpace`` bounds, and the safety chain
never routes through this module.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

EXPLORING = "explore"
COMMITTING = "commit"

DEFAULT_REARM_RATIO = 1.5
DEFAULT_IMPROVE_RATIO = 0.5
DEFAULT_ABS_FLOOR = 0.02


@dataclass(frozen=True)
class SearchSpace:
    """One bounded dial: the full set of values the tuner is allowed to pick."""

    name: str
    candidates: tuple[Any, ...]
    default: Any

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("SearchSpace.name must not be empty")
        if not self.candidates:
            raise ValueError(f"SearchSpace {self.name!r} has no candidates")
        if len(set(self.candidates)) != len(self.candidates):
            raise ValueError(f"SearchSpace {self.name!r} has duplicate candidates")
        if self.default not in self.candidates:
            raise ValueError(
                f"SearchSpace {self.name!r} default {self.default!r} is not a candidate"
            )

    @property
    def order(self) -> tuple[Any, ...]:
        """Evaluation order: the anchor first, then the rest as declared."""
        rest = tuple(c for c in self.candidates if c != self.default)
        return (self.default, *rest)


@dataclass
class _SpaceState:
    space: SearchSpace
    value: Any
    anchor: Any
    phase: str = EXPLORING
    visited: dict[Any, tuple[float, bool]] = field(default_factory=dict)
    outstanding: set[Any] = field(default_factory=set)
    best_cost: float | None = None
    best_feasible: bool = True
    last_feasible: bool = True
    committed_at: float = 0.0
    commits: int = 0
    rearms: int = 0
    reports: int = 0
    last_action: str = "init"
    history: deque = field(default_factory=lambda: deque(maxlen=30))


def _as_result(raw: Any) -> tuple[float, bool]:
    """Accept ``cost`` or ``(cost, feasible)`` in ``report()``."""
    if isinstance(raw, tuple):
        if len(raw) != 2:
            raise ValueError(f"result tuple must be (cost, feasible), got {raw!r}")
        return float(raw[0]), bool(raw[1])
    return float(raw), True


class AutoTuner:
    """Explore-commit-monitor-rearm search over several independent dials."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        rearm_ratio: float = DEFAULT_REARM_RATIO,
        improve_ratio: float = DEFAULT_IMPROVE_RATIO,
        abs_floor: float = DEFAULT_ABS_FLOOR,
    ) -> None:
        if rearm_ratio <= 1.0:
            raise ValueError("rearm_ratio must be > 1.0 (a ratio, not a delta)")
        if not 0.0 < improve_ratio < 1.0:
            raise ValueError("improve_ratio must be in (0,1)")
        if abs_floor < 0.0:
            raise ValueError("abs_floor must be >= 0")
        self.enabled = bool(enabled)
        self.rearm_ratio = float(rearm_ratio)
        self.improve_ratio = float(improve_ratio)
        self.abs_floor = float(abs_floor)
        self._spaces: dict[str, _SpaceState] = {}

    # ----------------------------------------------------------- definition
    def add(self, space: SearchSpace, initial: Any = None) -> None:
        if space.name in self._spaces:
            raise ValueError(f"search space {space.name!r} already registered")
        value = space.default if initial is None else initial
        if value not in space.candidates:
            raise ValueError(
                f"initial value {value!r} is not a candidate of {space.name!r}"
            )
        self._spaces[space.name] = _SpaceState(space=space, value=value, anchor=value)

    def seed(self, name: str, value: Any) -> bool:
        """Adopt a value learned in a previous session as the starting point.

        Seeded values become the tie-break anchor, so an inconclusive window
        keeps the previously learned answer instead of falling back to the
        shipped default. Returns False when the value is outside the space
        (a stale overlay must never move the dial).
        """
        st = self._state(name)
        if value not in st.space.candidates:
            return False
        st.value = value
        st.anchor = value
        return True

    def _state(self, name: str) -> _SpaceState:
        try:
            return self._spaces[name]
        except KeyError:
            raise KeyError(f"unknown search space: {name!r}") from None

    # -------------------------------------------------------------- reading
    def value(self, name: str) -> Any:
        return self._state(name).value

    def values(self) -> dict[str, Any]:
        return {name: st.value for name, st in self._spaces.items()}

    def phase(self, name: str) -> str:
        return self._state(name).phase

    def names(self) -> tuple[str, ...]:
        return tuple(self._spaces)

    def next(self, name: str) -> tuple[Any, ...]:
        """Candidates still owed an evaluation, in anchor-first order.

        Returns ``()`` when the space is committed (nothing to explore) or
        when everything has already been handed out and not yet reported.
        """
        st = self._state(name)
        if not self.enabled or st.phase == COMMITTING:
            return ()
        order = (st.anchor, *(c for c in st.space.order if c != st.anchor))
        pending = tuple(
            c for c in order if c not in st.visited and c not in st.outstanding
        )
        st.outstanding.update(pending)
        return pending

    def report(self, name: str, results: Mapping[Any, Any]) -> None:
        """Record costs for candidates. Commits once the space is exhausted."""
        st = self._state(name)
        for candidate, raw in results.items():
            if candidate not in st.space.candidates:
                raise ValueError(f"{candidate!r} is not a candidate of {name!r}")
            cost, feasible = _as_result(raw)
            st.visited[candidate] = (cost, feasible)
            st.outstanding.discard(candidate)
            st.reports += 1
        if all(c in st.visited for c in st.space.candidates):
            self._commit(st)

    def _commit(self, st: _SpaceState) -> None:
        index = {c: i for i, c in enumerate(st.space.candidates)}
        # Lowest cost wins; ties prefer the anchor, then declaration order.
        best = min(
            st.space.candidates,
            key=lambda c: (
                st.visited[c][0],
                0 if c == st.anchor else 1,
                index[c],
            ),
        )
        cost, feasible = st.visited[best]
        st.value = best
        st.best_cost = cost
        st.best_feasible = feasible
        st.last_feasible = feasible
        st.phase = COMMITTING
        st.committed_at = time.time()
        st.commits += 1
        st.outstanding.clear()
        st.last_action = "commit"
        st.history.append(
            {
                "action": "commit",
                "value": best,
                "cost": round(cost, 6),
                "at": round(st.committed_at, 3),
            }
        )

    def monitor(self, name: str, cost: float, feasible: bool = True) -> str:
        """Score the committed value once per window.

        Returns ``stable`` while the value is still the right answer, or
        ``rearm`` when the world moved and exploration must start again.

        While the committed value is already infeasible the cost is
        penalty-dominated and a noisy sample can fake both a degrade and an
        improve, so only a change in feasibility re-arms (see the module
        docstring's Hysteresis note).
        """
        st = self._state(name)
        if not self.enabled:
            return "disabled"
        if st.phase == EXPLORING:
            return "exploring"
        if st.best_cost is None:
            return "unstable"
        cost = float(cost)
        delta = cost - st.best_cost
        reason = ""
        if delta > st.best_cost * self.rearm_ratio + self.abs_floor:
            reason = "degraded"
        elif delta < -(st.best_cost * self.improve_ratio + self.abs_floor):
            reason = "improved"
        if reason:
            if not feasible and not st.last_feasible:
                # Still infeasible with no change of state: this is measurement
                # noise, not the world moving. Re-exploring cannot help a value
                # that is already the most aggressive one it could pick.
                st.last_feasible = feasible
                st.last_action = "stable"
                return "stable"
            self._rearm(st, reason)
            return "rearm"
        st.last_feasible = feasible
        st.last_action = "stable"
        return "stable"

    def _rearm(self, st: _SpaceState, reason: str) -> None:
        st.visited.clear()
        st.outstanding.clear()
        st.phase = EXPLORING
        st.best_cost = None
        st.rearms += 1
        st.last_action = f"rearm:{reason}"
        st.history.append(
            {
                "action": "rearm",
                "reason": reason,
                "value": st.value,
                "at": round(time.time(), 3),
            }
        )

    # ------------------------------------------------------------- reporting
    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "params": {
                name: {
                    "value": st.value,
                    "default": st.space.default,
                    "phase": st.phase,
                    "cost": None if st.best_cost is None else round(st.best_cost, 6),
                    "feasible": st.best_feasible,
                    "candidates": len(st.space.candidates),
                    "evaluated": len(st.visited),
                    "commits": st.commits,
                    "rearms": st.rearms,
                    "action": st.last_action,
                    "changed": st.value != st.space.default,
                }
                for name, st in self._spaces.items()
            },
        }

    def learned(self) -> dict[str, Any]:
        """Dotted config keys whose committed value differs from the default."""
        return {
            name: st.value
            for name, st in self._spaces.items()
            if st.value != st.space.default
        }

    def history(self, name: str) -> list[dict[str, Any]]:
        return list(self._state(name).history)

    def costs(self, name: str) -> dict[Any, float]:
        return {c: cost for c, (cost, _ok) in self._state(name).visited.items()}


def apply_learned(tuner: AutoTuner, values: Mapping[str, Any]) -> list[str]:
    """Seed a tuner from a ``{dotted.key: value}`` overlay; returns what stuck."""
    applied: list[str] = []
    for dotted, value in values.items():
        if dotted not in tuner.names():
            continue
        if tuner.seed(dotted, value):
            applied.append(dotted)
    return applied
