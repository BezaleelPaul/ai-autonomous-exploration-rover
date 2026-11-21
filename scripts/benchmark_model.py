#!/usr/bin/env python3
"""Measure inference speed on *your* machine, at several input sizes.

    python scripts/benchmark_model.py                       # config weights
    python scripts/benchmark_model.py --weights models/rover24.onnx --imgsz 256,320,416
    python scripts/benchmark_model.py --image sample.jpg --runs 5

Use it to pick `imgsz` and `zones.speed` before the demo. On a slow CPU the
first inference can take 10–60 s (model load + graph optimisation); the warm-up
absorbs it and is excluded from the numbers.
"""

from __future__ import annotations

import argparse
import time

import _bootstrap  # noqa: F401

from ai_rover import AppConfig
from ai_rover.vision import make_detector


def benchmark(detector, image, sizes, runs=3, log=print) -> list[dict]:
    results = []
    for size in sizes:
        detector.imgsz = size
        detector.detect(image)  # warm up this shape
        started = time.perf_counter()
        detections = []
        for _ in range(runs):
            detections = detector.detect(image)
        seconds = (time.perf_counter() - started) / runs
        row = {
            "imgsz": size,
            "ms": round(seconds * 1000, 1),
            "fps": round(1.0 / seconds, 2),
            "detections": len(detections),
        }
        results.append(row)
        log(f"[BENCH] imgsz={size:<4} {row['ms']:7.1f} ms  {row['fps']:4.2f} FPS  dets={row['detections']}")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark the rover detector")
    parser.add_argument("--weights", default=None, help="default: config weights")
    parser.add_argument("--imgsz", default="256,320,416", help="comma separated sizes")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--conf", type=float, default=0.30)
    parser.add_argument("--image", default=None, help="real image (default: synthetic 640x480)")
    args = parser.parse_args(argv)

    cfg = AppConfig.load()
    weights = args.weights or cfg.weights
    sizes = [int(s) for s in args.imgsz.split(",") if s.strip()]

    import numpy as np

    if args.image:
        import cv2

        image = cv2.imread(args.image)
        if image is None:
            print(f"[BENCH] cannot read {args.image}")
            return 2
    else:
        image = np.zeros((480, 640, 3), dtype=np.uint8)

    print(f"[BENCH] loading {weights} (first inference can take a while) ...")
    detector = make_detector(weights, sizes[0], args.conf, args.device)
    detector.warmup()
    rows = benchmark(detector, image, sizes, args.runs)

    best = max(rows, key=lambda r: r["fps"])
    print(f"[BENCH] fastest: imgsz={best['imgsz']} at {best['fps']} FPS")
    if best["fps"] < 2:
        print("[BENCH] under 2 FPS: drive slowly and keep zones.speed <= 120;")
        print("[BENCH] the ultrasonic gate is the hard stop, not the model.")
    elif best["fps"] < 5:
        print("[BENCH] 2–5 FPS: fine for the demo; keep zones.speed around 120–140.")
    else:
        print("[BENCH] 5+ FPS: comfortable for the default speed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
