"""H4 regression — AI-in-the-loop freshness must beat the target lock.

Red-team finding H4 (TEST_REPORT §11): DETR-ResNet-50 measured 4135 ms/frame;
with inference_interval the detection refreshed every ~4.1 s while
`target_lock_duration_s` is 1.0 s, so the target was lost ~3 s of every cycle
and visual servoing could not close.

Fix: shipped default `ai.backend: yolo` (yolo11s, measured ~234 ms/frame @320).
This file MEASURES the loop on the host machine (label: MEASURED).
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from software.utils.config_loader import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_shipped_backend_closes_loop_config() -> None:
    """Config must default to the realtime-capable backend, not DETR."""
    cfg = load_config(str(ROOT / "config" / "config.yaml"))
    ai = cfg["ai"]
    assert ai["backend"] == "yolo", (
        f"shipped default backend must be realtime-capable (H4); got {ai['backend']!r}"
    )
    assert ai["inference_interval"] >= 1


def test_yolo_measured_freshness_beats_target_lock(monkeypatch) -> None:
    """interval x measured median inference < target_lock_duration_s (H4)."""
    cfg = load_config(str(ROOT / "config" / "config.yaml"))
    ai = cfg["ai"]
    weights = ROOT / str(ai.get("yolo_model", "yolo11s.pt"))
    if not weights.exists():
        pytest.skip(f"weights {weights.name} not present")
    pytest.importorskip("ultralytics")

    monkeypatch.chdir(ROOT)  # YOLO resolves relative weight paths from cwd
    from software.ai.detector import create_detector

    det = create_detector(cfg)
    load = getattr(det, "load", None)
    assert callable(load), "detector has no load()"
    assert load(), (
        "yolo load failed: "
        f"{getattr(det, 'load_error', None) or getattr(det, '_load_error', '?')}"
    )
    frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
    det.detect(frame)  # warm-up (first call includes lazy init)
    det.detect(frame)

    lat: list[float] = []
    for _ in range(8):
        t0 = time.perf_counter()
        det.detect(frame)
        lat.append(time.perf_counter() - t0)
    p50_s = float(np.median(lat))

    lock_s = float(cfg["navigation"]["target_lock_duration_s"])
    interval = int(ai["inference_interval"])
    effective_s = interval * p50_s
    assert effective_s < lock_s, (
        f"H4 regression: {interval} x {p50_s * 1000:.0f} ms = "
        f"{effective_s:.2f}s detection refresh >= {lock_s}s target-lock"
    )
