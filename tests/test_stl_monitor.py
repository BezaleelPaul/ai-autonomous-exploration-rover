"""Quantitative STL: robustness signs, connectives, windowed operators."""

from __future__ import annotations

import pytest

from software.ai.stl_monitor import (
    Always,
    And,
    Eventually,
    Not,
    Or,
    Pred,
    Signal,
    classify,
    evaluate,
)


def make_trace(name: str, points: list[tuple[float, float]]) -> dict[str, Signal]:
    sig = Signal(name)
    for t, v in points:
        sig.append(t, v)
    return {name: sig}


def test_predicate_robustness_is_signed_distance():
    traces = make_trace("d", [(0.0, 0.8), (1.0, 0.3)])
    p = Pred("d", 0.5, gt=True)
    assert evaluate(p, traces, t=0.0) == pytest.approx(0.3)  # 0.8 - 0.5
    assert evaluate(p, traces, t=1.0) == pytest.approx(-0.2)  # 0.3 - 0.5


def test_predicate_lt():
    traces = make_trace("d", [(0.0, 0.3)])
    p = Pred("d", 0.5, gt=False)
    assert evaluate(p, traces, t=0.0) == pytest.approx(0.2)  # 0.5 - 0.3


def test_not_negates_robustness():
    traces = make_trace("d", [(0.0, 0.8)])
    assert evaluate(Not(Pred("d", 0.5)), traces, t=0.0) == pytest.approx(-0.3)


def test_and_is_min_or_is_max():
    traces = {"a": Signal("a"), "b": Signal("b")}
    traces["a"].append(0.0, 0.8)
    traces["b"].append(0.0, 0.2)
    assert evaluate(
        And(Pred("a", 0.5), Pred("b", 0.5)), traces, t=0.0
    ) == pytest.approx(-0.3)
    assert evaluate(Or(Pred("a", 0.5), Pred("b", 0.5)), traces, t=0.0) == pytest.approx(
        0.3
    )


def test_always_takes_min_over_window():
    """A dip below the margin inside the window must drive rho negative."""
    traces = make_trace(
        "d", [(0.0, 0.9), (0.5, 0.9), (1.0, 0.2), (1.5, 0.9), (2.0, 0.9)]
    )
    spec = Always(0.0, 2.0, Pred("d", 0.5))
    rho = evaluate(spec, traces, t=0.0)
    assert rho == pytest.approx(-0.3)  # worst point 0.2 - 0.5


def test_always_satisfied_when_signal_stays_clear():
    traces = make_trace("d", [(0.0, 0.9), (1.0, 0.8), (2.0, 0.7)])
    spec = Always(0.0, 2.0, Pred("d", 0.5))
    assert evaluate(spec, traces, t=0.0) == pytest.approx(0.2)  # worst 0.7 - 0.5


def test_eventually_takes_max_over_window():
    traces = make_trace("d", [(0.0, 0.2), (1.0, 0.2), (1.5, 0.9), (2.0, 0.2)])
    spec = Eventually(0.0, 2.0, Pred("d", 0.5))
    assert evaluate(spec, traces, t=0.0) == pytest.approx(0.4)  # peak 0.9 - 0.5


def test_unknown_when_signal_missing():
    spec = Always(0.0, 1.0, Pred("ghost", 0.5))
    assert evaluate(spec, {}, t=0.0) is None


def test_classify_three_state():
    assert classify(0.3) == "satisfied"
    assert classify(-0.3) == "violated"
    assert classify(0.0) == "boundary"
    assert classify(None) == "unknown"


def test_clear_path_spec_matches_world_model_margin():
    """always(ultrasonic > 0.5) over 2 s: a 0.3 m reading violates by 0.2."""
    traces = make_trace("ultrasonic_m", [(8.0, 0.9), (9.0, 0.9), (10.0, 0.3)])
    spec = Always(0.0, 2.0, Pred("ultrasonic_m", 0.5))
    rho = evaluate(spec, traces, t=10.0)
    assert rho == pytest.approx(-0.2)
    assert classify(rho) == "violated"
