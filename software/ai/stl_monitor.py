"""Quantitative Signal Temporal Logic (STL) over recorded traces.

A tiny, dependency-free STL fragment with the standard robustness semantics
used by RTAMT / the STL literature: every formula returns a *robustness*
degree rho — how far the signal is from violating the spec (rho > 0 satisfies,
rho < 0 violates, |rho| is the margin in the signal's units).

Supported:
* ``Signal``       — named (t, value) trace with windowed reads
* ``Pred``         — ``sig > m`` / ``sig < m`` (robustness = signed distance)
* ``Not`` / ``And`` / ``Or`` — classical connectives on robustness values
* ``Always(a, b, φ)``   — φ holds for the whole window [a, b] seconds ahead
* ``Eventually(a, b, φ)`` — φ holds at some point in [a, b]

Used by the world model to score live specs like
``always (ultrasonic_distance > 0.5 m)`` over the last N seconds and to
score recorded runs offline — turning "the demo worked" into "the demo
satisfied the spec with margin rho".
"""

from __future__ import annotations

import math


class Signal:
    """Named trace of (timestamp, value) pairs, newest kept last."""

    def __init__(self, name: str, maxlen: int = 512) -> None:
        self.name = name
        self.points: list[tuple[float, float]] = []
        self._maxlen = int(maxlen)

    def append(self, t: float, value: float) -> None:
        self.points.append((float(t), float(value)))
        if len(self.points) > self._maxlen:
            del self.points[: len(self.points) - self._maxlen]

    def window(self, t0: float, t1: float) -> list[tuple[float, float]]:
        return [(t, v) for t, v in self.points if t0 <= t <= t1]

    def latest(self, t_end: float, max_age: float) -> float | None:
        """Newest value no older than max_age relative to t_end."""
        best = None
        for t, v in self.points:
            if t <= t_end and t_end - t <= max_age:
                best = v
        return best


class _Node:
    def rho(self, traces: dict[str, Signal], t: float) -> float | None:
        raise NotImplementedError


class Pred(_Node):
    """``sig > m`` (gt=True) or ``sig < m`` (gt=False)."""

    def __init__(self, signal: str, threshold: float, gt: bool = True) -> None:
        self.signal = signal
        self.threshold = float(threshold)
        self.gt = bool(gt)

    def rho(self, traces: dict[str, Signal], t: float) -> float | None:
        sig = traces.get(self.signal)
        if sig is None:
            return None
        v = sig.latest(t, max_age=1.0)
        if v is None:
            return None
        return (v - self.threshold) if self.gt else (self.threshold - v)


class Not(_Node):
    def __init__(self, phi: _Node) -> None:
        self.phi = phi

    def rho(self, traces: dict[str, Signal], t: float) -> float | None:
        r = self.phi.rho(traces, t)
        return None if r is None else -r


class _Comm(_Node):
    is_and = True

    def __init__(self, *children: _Node) -> None:
        self.children = children

    def rho(self, traces: dict[str, Signal], t: float) -> float | None:
        vals = [c.rho(traces, t) for c in self.children]
        known = [v for v in vals if v is not None]
        if not known:
            return None
        return min(known) if self.is_and else max(known)


class And(_Comm):
    is_and = True


class Or(_Comm):
    is_and = False


class Always(_Node):
    """rho = min rho(φ) over the window [t + a, t + b]."""

    def __init__(self, a: float, b: float, phi: _Node) -> None:
        self.a = float(a)
        self.b = float(b)
        self.phi = phi

    def rho(self, traces: dict[str, Signal], t: float) -> float | None:
        if self.b < self.a:
            return None
        step = 0.1
        vals: list[float] = []
        now = t + self.a
        end = t + self.b
        while now <= end + 1e-9:
            r = self.phi.rho(traces, now)
            if r is not None:
                vals.append(r)
            now += step
        return min(vals) if vals else None


class Eventually(_Node):
    """rho = max rho(φ) over the window [t + a, t + b]."""

    def __init__(self, a: float, b: float, phi: _Node) -> None:
        self.a = float(a)
        self.b = float(b)
        self.phi = phi

    def rho(self, traces: dict[str, Signal], t: float) -> float | None:
        if self.b < self.a:
            return None
        step = 0.1
        vals: list[float] = []
        now = t + self.a
        end = t + self.b
        while now <= end + 1e-9:
            r = self.phi.rho(traces, now)
            if r is not None:
                vals.append(r)
            now += step
        return max(vals) if vals else None


def evaluate(
    phi: _Node, traces: dict[str, Signal], t: float | None = None
) -> float | None:
    """Robustness of ``phi`` at ``t`` (default: newest sample across traces)."""
    if t is None:
        t = max((p[-1][0] for p in traces.values() if p.points), default=0.0)
    return phi.rho(traces, t)


def classify(rho: float | None) -> str:
    """Three-state verdict from a robustness value (or None when unknown)."""
    if rho is None or (isinstance(rho, float) and math.isnan(rho)):
        return "unknown"
    if rho > 0:
        return "satisfied"
    if rho < 0:
        return "violated"
    return "boundary"
