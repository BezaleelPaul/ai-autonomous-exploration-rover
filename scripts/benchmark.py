"""Benchmark the configured detector (ai.backend): latency, FPS, CPU, RAM.
Loads via create_detector (yolo | hf | color | mock); falls back to mock if
weights unavailable. Also sweeps resolution + frame-skip to recommend config.

Usage: python scripts/benchmark.py [--runs 10]
Writes: logs/benchmark.json + prints table.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from software.ai.detector import MockDetector, create_detector
from software.utils.config_loader import load_config


def stats(times):
    a = np.array(times)
    return {
        "mean_ms": round(float(a.mean()), 1),
        "p50_ms": round(float(np.median(a)), 1),
        "p95_ms": round(float(np.percentile(a, 95)), 1),
        "min_ms": round(float(a.min()), 1),
    }


def bench_detector(det, frames, runs=10):
    if len(frames):
        det.detect(frames[0])  # warm-up: exclude lazy init / first-track cost
    lat = []
    for f in frames[:runs]:
        t0 = time.perf_counter()
        det.detect(f)
        lat.append((time.perf_counter() - t0) * 1000.0)
    return stats(lat)


def main():
    runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 10
    cfg = load_config("config/config.yaml")
    ai = cfg["ai"]
    try:
        import psutil

        proc = psutil.Process()
    except Exception:
        psutil = None
        proc = None
    try:
        import torch

        torch.set_num_threads(max(1, (proc.cpu_num() if proc else 4) if False else 4))
    except Exception:
        pass

    det = create_detector(cfg)
    backend = type(det).__name__
    t0 = time.time()
    load = getattr(det, "load", None)
    loaded = load() if callable(load) else True
    load_s = round(time.time() - t0, 1)
    if not loaded:
        print(
            f"load failed ({getattr(det, 'load_error', '?')}); "
            "benchmarking mock pipeline instead."
        )
        det = MockDetector()
        backend = "MockDetector(fallback)"

    mem0 = proc.memory_info().rss / 1e6 if proc else 0
    out = {
        "model": getattr(det, "model_name", "n/a"),
        "backend": backend,
        "load_s": load_s,
        "device": ai.get("device", "cpu"),
        "runs": runs,
    }
    # resolution sweep
    for w, h in [(640, 480), (416, 312), (320, 240)]:
        frames = [
            np.random.randint(0, 255, (h, w, 3), dtype=np.uint8) for _ in range(runs)
        ]
        s = bench_detector(det, frames, runs)
        fps = round(1000.0 / max(s["mean_ms"], 1e-6), 1)
        out[f"{w}x{h}"] = {**s, "fps": fps}
        print(f"{w}x{h}: {s['mean_ms']}ms mean, {fps} FPS")
    # frame-skip projection: effective cmd rate = fps / interval
    for interval in [1, 2, 3, 4]:
        base = out["640x480"]["fps"]
        out[f"skip_x{interval}_eff_fps"] = round(base / interval, 1)
    if proc:
        out["cpu_percent"] = proc.cpu_percent(interval=0.5)
        out["rss_mb"] = round(proc.memory_info().rss / 1e6, 1)
        out["rss_delta_mb"] = round(out["rss_mb"] - mem0, 1)
    Path("logs").mkdir(exist_ok=True)
    Path("logs/benchmark.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    # recommendation (p50 at ~shipped imgsz; yolo resizes input to ai.yolo_imgsz)
    p50 = out["320x240"]["p50_ms"]
    if backend.startswith("Mock"):
        print("RECOMMEND: real-model benchmark pending — set ai.backend and run again.")
    elif p50 > 500:
        print(
            "RECOMMEND: p50 > 500 ms at imgsz 320 — use a smaller model "
            "(ai.yolo_model: yolo11n.pt)."
        )
    else:
        print(
            f"RECOMMEND: p50 {p50} ms @ imgsz 320 — inference_interval 2 "
            "closes the 1.0 s target-lock (H4)."
        )


if __name__ == "__main__":
    main()
