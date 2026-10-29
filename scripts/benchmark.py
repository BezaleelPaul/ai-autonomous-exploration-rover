"""Benchmark the configured detector (ai.backend): latency, FPS, CPU, RAM.
Loads via create_detector (yolo | hf | color | mock); falls back to mock if
weights unavailable. Also sweeps resolution + frame-skip to recommend config.

Engine shootout (CPU-only machines): exports each model once and compares
torch vs onnxruntime vs openvino so ai.export can point at the fastest path.

Usage:
  python scripts/benchmark.py [--runs 10]                      # legacy sweep
  python scripts/benchmark.py --engines torch,onnx,openvino    # engine shootout
      [--models yolo11n.pt,yolo26n.pt] [--imgsz 320,256] [--force-export]
Writes: logs/benchmark.json (+ logs/infer_bench.json) and, for the shootout,
reports/INFER_BENCH.md.
"""

import gc
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from software.ai.detector import MockDetector, create_detector
from software.utils.config_loader import load_config

ENGINES = ("torch", "onnx", "openvino")


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


def _arg(name, default=""):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def _rss_mb() -> float:
    try:
        import psutil

        return round(psutil.Process().memory_info().rss / 1e6, 1)
    except Exception:
        return 0.0


def ensure_export(
    model_path: str, fmt: str, imgsz: int = 320, force: bool = False
) -> str | None:
    """Export once per (model, fmt); returns the artifact path or None."""
    stem = Path(model_path).with_suffix("")
    if fmt == "onnx":
        target = Path(f"{stem}.onnx")
        present = target.is_file()
    else:
        target = Path(f"{stem}_openvino_model")
        present = target.is_dir() and any(target.glob("*.xml"))
    if present and not force:
        return str(target)
    try:
        from ultralytics import YOLO

        print(f"exporting {model_path} -> {fmt} (imgsz {imgsz}) ...")
        out = YOLO(model_path).export(format=fmt, imgsz=imgsz, device="cpu")
        return str(out)
    except Exception as exc:
        print(f"export failed for {model_path} [{fmt}]: {exc}")
        return None


def bench_engine(
    model: str, engine: str, imgsz: int, runs: int, force_export: bool = False
) -> dict:
    """One shootout row: load + timed detections through YoloDetector."""
    from software.ai.detector import YoloDetector

    row = {"model": model, "engine": engine, "imgsz": imgsz, "runs": runs}
    if engine != "torch" and ensure_export(model, engine, imgsz, force_export) is None:
        row["error"] = "export failed"
        return row
    det = YoloDetector(
        model=model,
        confidence_threshold=0.25,
        imgsz=imgsz,
        track=True,
        export=engine,
    )
    t0 = time.time()
    loaded = det.load()
    row["load_s"] = round(time.time() - t0, 1)
    if not loaded:
        row["error"] = str(getattr(det, "_load_error", "load failed"))
        del det
        gc.collect()
        return row
    frames = [
        np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8) for _ in range(runs)
    ]
    row.update(bench_detector(det, frames, runs))
    row["fps"] = round(1000.0 / max(row["p50_ms"], 1e-6), 1)
    row["loaded_engine"] = getattr(det, "engine", engine)
    row["track_fallback"] = bool(getattr(det, "_track_unavailable", False))
    row["rss_mb"] = _rss_mb()
    del det
    gc.collect()
    return row


def write_report(rows: list[dict], winner: dict | None) -> str:
    lines = [
        "# Inference engine benchmark (CPU-only)",
        "",
        f"Measured {time.strftime('%Y-%m-%d %H:%M')} · random 640x480 frames · "
        "p50 = median latency",
        "",
        "| model | engine | imgsz | p50 ms | p95 ms | mean ms | FPS | load s | RSS MB | notes |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        if "error" in r:
            lines.append(
                f"| {r['model']} | {r['engine']} | {r['imgsz']} | — | — | — | — | "
                f"{r.get('load_s', '—')} | — | ERROR: {r['error']} |"
            )
            continue
        notes = []
        if r.get("track_fallback"):
            notes.append("ByteTrack fell back to predict")
        if r.get("loaded_engine") and r["loaded_engine"] != r["engine"]:
            notes.append(f"loaded {r['loaded_engine']}")
        lines.append(
            f"| {r['model']} | {r['engine']} | {r['imgsz']} | {r['p50_ms']} | "
            f"{r['p95_ms']} | {r['mean_ms']} | {r['fps']} | {r['load_s']} | "
            f"{r['rss_mb']} | {'; '.join(notes) or 'ok'} |"
        )
    lines.append("")
    if winner:
        lines.append(
            f"**Winner:** `{winner['model']}` via `{winner['engine']}` at imgsz "
            f"{winner['imgsz']} — p50 {winner['p50_ms']} ms ({winner['fps']} FPS).\n"
        )
        lines.append("```yaml")
        lines.append(f'ai.export: "{winner["engine"]}"')
        lines.append(f'ai.yolo_model: "{winner["model"]}"')
        lines.append(f"ai.yolo_imgsz: {winner['imgsz']}")
        lines.append("```")
    else:
        lines.append("**Winner:** none (every candidate failed).")
    Path("reports").mkdir(exist_ok=True)
    Path("reports/INFER_BENCH.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "\n".join(lines)


def run_engine_shootout(runs: int) -> None:
    models = [m for m in _arg("--models", "yolo11n.pt,yolo26n.pt").split(",") if m]
    engines = [
        e for e in _arg("--engines", ",".join(ENGINES)).split(",") if e in ENGINES
    ] or list(ENGINES)
    imgszs = [int(i) for i in _arg("--imgsz", "320,256").split(",") if i]
    force = "--force-export" in sys.argv

    rows: list[dict] = []
    for model in models:
        for imgsz in imgszs:
            for engine in engines:
                # exported artifacts bake one input size: only the first imgsz
                if engine != "torch" and imgsz != imgszs[0]:
                    continue
                print(f"bench {model} / {engine} @ {imgsz} ...")
                rows.append(bench_engine(model, engine, imgsz, runs, force))

    usable = [r for r in rows if "error" not in r]
    winner = min(usable, key=lambda r: r["p50_ms"]) if usable else None
    Path("logs").mkdir(exist_ok=True)
    Path("logs/infer_bench.json").write_text(json.dumps(rows, indent=2))
    print(write_report(rows, winner))
    if winner:
        print(
            f'RECOMMEND: ai.export "{winner["engine"]}" with '
            f'ai.yolo_model "{winner["model"]}" @ imgsz {winner["imgsz"]} '
            f"-> p50 {winner['p50_ms']} ms"
        )


def legacy_sweep(runs: int) -> None:
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
            f"load failed ({getattr(det, '_load_error', '?')}); "
            "benchmarking mock pipeline instead."
        )
        det = MockDetector()
        backend = "MockDetector(fallback)"

    mem0 = proc.memory_info().rss / 1e6 if proc else 0
    out = {
        "model": getattr(det, "model_name", "n/a"),
        "backend": backend,
        "engine": getattr(det, "engine", "n/a"),
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


def main():
    runs = int(_arg("--runs", "10"))
    if "--engines" in sys.argv:
        run_engine_shootout(runs)
    else:
        legacy_sweep(runs)


if __name__ == "__main__":
    main()
