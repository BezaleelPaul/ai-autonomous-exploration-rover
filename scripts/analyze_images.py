#!/usr/bin/env python3
"""Batch-analyse every image in a folder (or a single image).

Writes annotated copies + `detections.csv` + `summary.json`. Works with the
fixed-class model and with open-vocabulary prompts.

    # fixed 24/6-class model
    python scripts/analyze_images.py --images dataset/images/val --out reports/val

    # any object, text prompts (YOLO-World)
    python scripts/analyze_images.py --world "door,cable,cone,fire extinguisher" \
        --images dataset/images/val --out reports/world

    # single image
    python scripts/analyze_images.py --images shot.jpg --out reports/one
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

import _bootstrap  # noqa: F401  (adds software/ to sys.path)

from ai_rover import AppConfig, WorldDetector, make_detector

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def collect_images(source: Path, recursive: bool) -> list[Path]:
    if source.is_file():
        return [source] if source.suffix.lower() in IMAGE_EXTS else []
    if not source.is_dir():
        raise FileNotFoundError(source)
    iterator = source.rglob("*") if recursive else source.glob("*")
    return sorted(p for p in iterator if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def _annotate(image, detections):
    import cv2

    for det in detections:
        x1, y1, x2, y2 = int(det.x1), int(det.y1), int(det.x2), int(det.y2)
        cv2.rectangle(image, (x1, y1), (x2, y2), (34, 211, 238), 2)
        label = f"{det.cls} {det.conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(image, (x1, max(0, y1 - th - 8)), (x1 + tw + 6, max(0, y1 - 2)), (12, 9, 6), -1)
        cv2.putText(image, label, (x1 + 3, max(12, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (235, 240, 250), 1, cv2.LINE_AA)
    return image


def analyze(
    images: list[Path],
    detector,
    out_dir: Path,
    draw: bool = True,
    limit: int | None = None,
    log=print,
) -> dict:
    """Run the detector over every image; returns the summary dict."""
    import cv2

    out_dir = Path(out_dir)
    (out_dir / "annotated").mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    counts: Counter = Counter()
    confidences: list[float] = []
    empty = 0
    processed = 0
    started = time.time()
    paths = images[:limit] if limit else images

    for path in paths:
        image = cv2.imread(str(path))
        if image is None:
            log(f"[ANALYZE] skip unreadable {path}")
            continue
        processed += 1
        height, width = image.shape[0], image.shape[1]
        detections = detector.detect(image)
        if not detections:
            empty += 1
        for det in detections:
            counts[det.cls] += 1
            confidences.append(float(det.conf))
            rows.append(
                {
                    "image": path.name,
                    "class": det.cls,
                    "confidence": round(float(det.conf), 4),
                    "x1": round(float(det.x1), 1),
                    "y1": round(float(det.y1), 1),
                    "x2": round(float(det.x2), 1),
                    "y2": round(float(det.y2), 1),
                    "width": width,
                    "height": height,
                    "area_pct": round(det.area_ratio(width, height) * 100, 2),
                }
            )
        if draw:
            cv2.imwrite(str(out_dir / "annotated" / path.name), _annotate(image, detections))
        if processed % 25 == 0:
            log(f"[ANALYZE] {processed}/{len(paths)} images, {len(rows)} detections")

    if rows:
        with open(out_dir / "detections.csv", "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    summary = {
        "images": processed,
        "images_without_detections": empty,
        "detections": len(rows),
        "per_class": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "mean_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
        "detector": type(detector).__name__,
        "prompts": getattr(detector, "prompts", None) or None,
        "seconds": round(time.time() - started, 2),
        "output": str(out_dir),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch image analysis")
    parser.add_argument("--images", required=True, help="image file or folder")
    parser.add_argument("--out", default="reports/analysis")
    parser.add_argument("--weights", default=None, help="model path (default: config weights)")
    parser.add_argument("--world", default=None, help="open-vocabulary prompts, comma separated")
    parser.add_argument("--classes", default=None, help="fixed-model class filter, comma separated")
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument("--conf", type=float, default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--no-draw", action="store_true")
    args = parser.parse_args(argv)

    cfg = AppConfig.load()
    source = Path(args.images)
    try:
        images = collect_images(source, args.recursive)
    except FileNotFoundError:
        print(f"[ANALYZE] no such path: {source}", file=sys.stderr)
        return 2
    if not images:
        print(f"[ANALYZE] no images under {source}", file=sys.stderr)
        return 2

    prompts = [p.strip() for p in args.world.split(",") if p.strip()] if args.world else None
    classes = [c.strip() for c in args.classes.split(",") if c.strip()] if args.classes else None
    imgsz = args.imgsz or cfg.imgsz
    conf = args.conf if args.conf is not None else (0.30 if prompts else cfg.conf)
    device = args.device or cfg.device

    if prompts:
        detector = WorldDetector("yolov8s-worldv2.pt", imgsz, conf, device, prompts)
        print(f"[ANALYZE] open-vocabulary prompts: {prompts}")
    else:
        weights = args.weights or cfg.weights
        detector = make_detector(weights, imgsz, conf, device, classes)
        print(f"[ANALYZE] detector={type(detector).__name__} weights={weights} classes={classes or 'all'}")

    summary = analyze(images, detector, Path(args.out), draw=not args.no_draw, limit=args.limit)
    print(json.dumps(summary, indent=2))
    return 0 if summary["images"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
