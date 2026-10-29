"""Kalman filter: convergence, stationary rejection, coasting uncertainty."""

from __future__ import annotations

import math

import pytest

from software.ai.kalman import BoxKalman


def test_velocity_converges_on_approach():
    """A box growing ~40 px/s must report positive size_rate within 3 frames."""
    kf = BoxKalman((320, 250, 40, 100))
    for i in range(1, 4):
        t = i * 0.25
        kf.predict(0.25)
        kf.correct((320, 250, 40 + 20 * t, 100 + 60 * t))
    assert kf.size_rate > 25.0


def test_stationary_object_has_zero_velocity():
    kf = BoxKalman((320, 250, 40, 100))
    for _ in range(8):
        kf.predict(0.25)
        kf.correct((320, 250, 40, 100))
    assert abs(kf.size_rate) < 1.0
    assert abs(kf.speed_px) < 1.0


def test_centre_velocity_from_lateral_motion():
    """Object sliding right at ~80 px/s must report positive vx."""
    kf = BoxKalman((100, 250, 40, 40))
    for i in range(1, 6):
        kf.predict(0.25)
        kf.correct((100 + 20 * i, 250, 40, 40))
    assert kf.x[4] == pytest.approx(80.0, rel=0.25)


def test_coasting_grows_position_sigma():
    """No measurement for 1 s must inflate the posterior uncertainty."""
    kf = BoxKalman((320, 250, 40, 100))
    for _ in range(4):
        kf.predict(0.25)
        kf.correct((320, 250, 40, 100))
    before = kf.pos_sigma_px
    kf.predict(1.0)
    assert kf.pos_sigma_px > before * 2


def test_correct_reduces_sigma():
    kf = BoxKalman((320, 250, 40, 100))
    kf.predict(0.25)
    before = kf.pos_sigma_px
    kf.correct((320, 250, 40, 100))
    assert kf.pos_sigma_px < before


def test_mahalanobis_large_for_outlier():
    """A wildly wrong measurement must produce a large normalised innovation."""
    kf = BoxKalman((320, 250, 40, 100))
    for _ in range(4):
        kf.predict(0.25)
        kf.correct((320, 250, 40, 100))
    kf.predict(0.25)
    kf.correct((900, 900, 400, 400))  # far outlier
    assert kf.mahalanobis > 3.0


def test_box_property_returns_position_state():
    kf = BoxKalman((10, 20, 30, 40))
    assert kf.box == (10.0, 20.0, 30.0, 40.0)
    assert math.isfinite(kf.pos_sigma_px)
