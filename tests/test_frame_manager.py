"""FrameManager: latest-frame buffer, dropped-frame counting, frame age."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from software.camera.frame_manager import FrameInfo, FrameManager


def test_should_infer_follows_interval():
    fm = FrameManager(inference_interval=2)
    assert [fm.should_infer() for _ in range(4)] == [False, True, False, True]
    fm2 = FrameManager(inference_interval=1)
    assert all(fm2.should_infer() for _ in range(3))
    # interval is clamped to >= 1, never 0 (mod-by-zero would be fatal)
    fm0 = FrameManager(inference_interval=0)
    assert all(fm0.should_infer() for _ in range(3))


def test_observe_consume_round_trip():
    fm = FrameManager()
    info = fm.observe("frame-a", capture_time=100.0)
    assert isinstance(info, FrameInfo) and info.frame_id == 1
    assert fm.consume() == "frame-a"
    assert fm.consume() is None  # slot emptied by the first consume
    assert fm.stats()["received"] == 1 and fm.stats()["consumed"] == 1


def test_dropped_counts_frame_replaced_before_consumption():
    fm = FrameManager()
    fm.observe("a", capture_time=1.0)
    fm.observe("b", capture_time=2.0)  # 'a' never consumed -> dropped
    assert fm.stats()["dropped"] == 1
    assert fm.consume() == "b"  # latest-wins: only the newest frame is kept
    fm.observe("c", capture_time=3.0)
    assert fm.stats()["dropped"] == 1  # previous slot was already consumed
    assert fm.stats()["received"] == 3 and fm.stats()["consumed"] == 1


def test_frame_age_is_none_when_capture_time_unknown():
    fm = FrameManager()
    assert fm.frame_age() is None  # no frame at all
    fm.observe("a", capture_time=0.0)  # arrival time not supplied
    assert fm.frame_age() is None  # unknown age must not read as 0
    assert fm.stats()["age_s"] is None


def test_frame_age_measures_staleness():
    fm = FrameManager(max_frame_age_s=3.0)
    fm.observe("a", capture_time=1000.0)
    assert fm.frame_age(now=1001.25) == pytest.approx(1.25)
    assert not fm.is_stale(now=1002.0)
    assert fm.is_stale(now=1003.5)  # FM-03 freeze threshold


def test_observe_rejects_none_frame():
    fm = FrameManager()
    with pytest.raises(ValueError, match="must not be None"):
        fm.observe(None, capture_time=1.0)


def test_stats_shape():
    fm = FrameManager(inference_interval=3, max_frame_age_s=1.5)
    fm.observe("a", capture_time=500.0)
    stats = fm.stats()
    assert set(stats) == {
        "received",
        "consumed",
        "dropped",
        "age_s",
        "stale",
        "inference_interval",
        "max_frame_age_s",
    }
    assert stats["inference_interval"] == 3
    assert stats["max_frame_age_s"] == 1.5
    assert stats["dropped"] == 0 and stats["consumed"] == 0


def test_reset_clears_buffer_and_counters():
    fm = FrameManager(inference_interval=2)
    fm.observe("a", capture_time=10.0)
    fm.observe("b", capture_time=20.0)
    fm.reset()
    assert fm.consume() is None
    assert fm.frame_age() is None
    assert fm.stats()["received"] == 0 and fm.stats()["dropped"] == 0
    # throttling counter is reset too, so the interval pattern restarts
    assert [fm.should_infer() for _ in range(2)] == [False, True]
