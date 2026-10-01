"""Multi-object detection accuracy benchmark on a labelled dataset.

Downloads COCO128 (128 labelled COCO images) if absent, runs the *shipped*
detector over it, and reports operating-point precision / recall / F1 plus
mAP@0.5 against the ground truth, with per-frame latency and an H4
realtime-closure check. Every number printed is MEASURED on this machine.

Usage:
    py -3.12 scripts/eval_detection.py [--data datasets/coco128]
        [--config config/config.yaml] [--set ai.yolo_imgsz=640]
        [--out logs/detection_eval.json] [--limit 128] [--iou 0.5]
        [--compare logs/baseline.json] [--json] [--no-write]

Exit codes: 0 success, 2 input/dataset error.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from software.ai.detection_metrics import (  # noqa: E402
    Box,
    GroundTruth,
    Prediction,
    evaluate,
)
from software.ai.detector import (  # noqa: E402
    BaseDetector,
    create_detector,
    detector_class_names,
)
from software.utils.config_loader import load_config  # noqa: E402

DATASET_URL = "https://github.com/ultralytics/yolov5/releases/download/v1.0/coco128.zip"
DEFAULT_DATA = ROOT / "datasets" / "coco128"
DEFAULT_CONFIG = ROOT / "config" / "config.yaml"
DEFAULT_OUT = ROOT / "logs" / "detection_eval.json"
AP_CONFIDENCE = 0.01  # low cut so AP sees the full ranked curve
LABEL = "MEASURED"


class DatasetError(RuntimeError):
    """Raised when the labelled dataset cannot be located or fetched."""


def _coerce(raw: str) -> object:
    lowered = raw.strip().lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    for cast in (int, float):
        try:
            return cast(raw)
        except ValueError:
            continue
    return raw


def apply_overrides(cfg: dict, overrides: list[str]) -> list[str]:
    """Apply ``a.b.c=value`` entries in place; returns what was applied."""
    applied: list[str] = []
    for entry in overrides:
        if "=" not in entry:
            raise ValueError(f"override {entry!r} must look like key=value")
        dotted, raw = entry.split("=", 1)
        keys = dotted.strip().split(".")
        node = cfg
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = _coerce(raw)
        applied.append(f"{dotted.strip()}={raw}")
    return applied


def ensure_dataset(data_dir: Path) -> Path:
    """Return a populated COCO128 root, downloading it when missing."""
    images = data_dir / "images" / "train2017"
    if images.is_dir() and any(images.glob("*.jpg")):
        return data_dir
    print(f"dataset not found at {data_dir}; downloading {DATASET_URL}")
    data_dir.parent.mkdir(parents=True, exist_ok=True)
    archive = data_dir.parent / "coco128.zip"
    tmp = data_dir.parent / "_coco128_extract"
    try:
        urllib.request.urlretrieve(DATASET_URL, archive)
        if tmp.exists():
            shutil.rmtree(tmp)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp)
        extracted = tmp / "coco128"
        if not (extracted / "images" / "train2017").is_dir():
            raise DatasetError("archive layout changed: coco128/images missing")
        if data_dir.exists():
            shutil.rmtree(data_dir)
        shutil.move(str(extracted), str(data_dir))
    except DatasetError:
        raise
    except Exception as exc:
        raise DatasetError(f"could not fetch COCO128: {exc}") from exc
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        archive.unlink(missing_ok=True)
    return data_dir


def _labels_to_ground_truths(
    label_path: Path, width: int, height: int, names: dict[int, str]
) -> list[GroundTruth]:
    """Convert a YOLO label line (class cx cy w h, normalised) to boxes."""
    out: list[GroundTruth] = []
    if not label_path.exists():
        return out
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        class_id = int(float(parts[0]))
        if class_id not in names:
            continue
        cx, cy, w, h = (float(v) for v in parts[1:])
        out.append(
            GroundTruth(
                box=Box(
                    (cx - w / 2) * width,
                    (cy - h / 2) * height,
                    (cx + w / 2) * width,
                    (cy + h / 2) * height,
                ),
                class_name=names[class_id].lower(),
            )
        )
    return out


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return round(ordered[index], 2)


def _cpu_load() -> int | None:
    """Best-effort CPU load reading (wmic is absent from recent Windows)."""
    try:
        import subprocess

        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor).LoadPercentage",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        for token in out.stdout.split():
            if token.strip().isdigit():
                return int(token)
        return None
    except Exception:
        return None


def _class_names(detector: BaseDetector) -> dict[int, str]:
    """Class names for either backend convention.

    Thin wrapper kept for tests; the canonical implementation (Ultralytics
    ``.names`` *and* Hugging Face ``_pipe`` + ``config.id2label``) lives in
    ``software.ai.detector.detector_class_names``.
    """
    return detector_class_names(detector)


def _build_detector(cfg: dict) -> tuple[BaseDetector, dict[int, str]]:
    """Construct the backend named by ``ai.backend`` and read its class names."""
    detector = create_detector(cfg)
    load = getattr(detector, "load", None)
    if not callable(load) or not load():
        raise DatasetError(
            f"detector failed to load: {getattr(detector, 'load_error', '?')}"
        )
    names: dict[int, str] = _class_names(detector)
    if not names:
        raise DatasetError("detector exposed no class names")
    return detector, names


def run_benchmark(args: argparse.Namespace) -> dict:
    import cv2

    data_dir = ensure_dataset(args.data)
    images_dir = data_dir / "images" / "train2017"
    labels_dir = data_dir / "labels" / "train2017"

    cfg = copy.deepcopy(load_config(str(args.config)))
    overrides = apply_overrides(cfg, args.set)
    operating_confidence = float(cfg.get("ai", {}).get("confidence_threshold", 0.5))

    images = sorted(images_dir.glob("*.jpg"))
    if args.limit:
        images = images[: args.limit]
    if not images:
        raise DatasetError(f"no images found under {images_dir}")

    # --- accuracy pass (low confidence so AP sees the full ranked curve) ----
    # ByteTrack is disabled here: it is stateful and COCO128 is a shuffled set
    # of unrelated stills, so motion compensation adds nothing but warnings.
    # The latency pass below still uses the shipped configuration.
    accuracy_cfg = copy.deepcopy(cfg)
    accuracy_cfg.setdefault("ai", {})["confidence_threshold"] = args.ap_conf
    accuracy_cfg["ai"]["yolo_track"] = False
    detector, names = _build_detector(accuracy_cfg)

    predictions: dict[str, list[Prediction]] = {}
    ground_truths: dict[str, list[GroundTruth]] = {}
    for image_path in images:
        frame = cv2.imread(str(image_path))
        if frame is None:
            continue
        height, width = frame.shape[:2]
        key = image_path.name
        ground_truths[key] = _labels_to_ground_truths(
            labels_dir / f"{image_path.stem}.txt", width, height, names
        )
        detections = detector.detect(frame)
        predictions[key] = [
            Prediction(
                box=Box(d.x1, d.y1, d.x2, d.y2),
                confidence=d.confidence,
                class_name=d.class_name,
            )
            for d in detections
        ]

    report = evaluate(
        predictions,
        ground_truths,
        iou_threshold=args.iou,
        operating_confidence=operating_confidence,
    )

    # --- latency pass at the shipped confidence ----------------------------
    latency_detector, _ = _build_detector(cfg)
    warmup = images[:3]
    for image_path in warmup:
        frame = cv2.imread(str(image_path))
        if frame is not None:
            latency_detector.detect(frame)

    samples = images[: max(1, args.latency_frames)]
    timings: list[float] = []
    for image_path in samples * max(1, args.latency_repeats):
        frame = cv2.imread(str(image_path))
        if frame is None:
            continue
        start = time.perf_counter()
        latency_detector.detect(frame)
        timings.append((time.perf_counter() - start) * 1000)

    interval = int(cfg.get("ai", {}).get("inference_interval", 1))
    lock_s = float(cfg.get("navigation", {}).get("target_lock_duration_s", 1.0))
    p50_ms = _percentile(timings, 0.5)
    refresh_s = interval * p50_ms / 1000.0

    multi = sum(1 for gts in ground_truths.values() if len(gts) >= 2)
    load_pct = _cpu_load()
    return {
        "label": LABEL,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "accuracy on labelled COCO128; latency on this host CPU",
        "dataset": {
            "name": "coco128",
            "path": str(data_dir.relative_to(ROOT)),
            "source_url": DATASET_URL,
            "images": len(ground_truths),
            "images_with_multiple_objects": multi,
            "ground_truth_objects": sum(len(v) for v in ground_truths.values()),
        },
        "overrides": overrides,
        "operating_confidence": operating_confidence,
        "iou_threshold": args.iou,
        **report,
        "latency_ms": {
            "frames": len(timings),
            "p50": p50_ms,
            "p95": _percentile(timings, 0.95),
            "mean": round(sum(timings) / len(timings), 2) if timings else 0.0,
            "cpu_load_percent": load_pct,
        },
        "h4_realtime": {
            "inference_interval": interval,
            "target_lock_s": lock_s,
            "refresh_s": round(refresh_s, 3),
            "closes_loop": bool(refresh_s < lock_s),
        },
        "config_snapshot": {
            key: cfg["ai"][key]
            for key in (
                "backend",
                "yolo_model",
                "yolo_imgsz",
                "confidence_threshold",
                "iou_threshold",
                "min_box_px",
                "yolo_track",
                "inference_interval",
            )
            if key in cfg.get("ai", {})
        },
    }


def _delta(current: float, previous: float) -> str:
    return f" ({current - previous:+.4f})" if previous is not None else ""


def render(report: dict, baseline: dict | None = None) -> str:
    op = report["operating_point"]
    ap = report["ap"]
    lat = report["latency_ms"]
    h4 = report["h4_realtime"]
    ds = report["dataset"]
    base_op = baseline["operating_point"] if baseline else None
    base_ap = baseline["ap"] if baseline else None

    def against(key: str, current: float, previous: float | None) -> str:
        if previous is None:
            return ""
        return _delta(current, previous)

    lines = [
        f"Label: {report['label']} | dataset: {ds['name']} "
        f"({ds['images']} images, {ds['images_with_multiple_objects']} with "
        f">=2 objects, {ds['ground_truth_objects']} objects)",
        f"Overrides: {', '.join(report['overrides']) or 'none (shipped config)'}",
        f"Operating conf {report['operating_confidence']} | IoU {report['iou_threshold']}",
        "",
        f"{'METRIC':<34}{'VALUE':>10}{'  DELTA vs BASELINE':>24}",
    ]
    for label, field in (
        ("precision", "precision"),
        ("recall", "recall"),
        ("f1", "f1"),
        ("multi-object recall", "multi_object_recall"),
        ("duplicate detections", "duplicate_detections"),
    ):
        current = op[field]
        previous = base_op[field] if base_op else None
        lines.append(f"{label:<34}{current:>10}{against('', current, previous):>24}")
    current = ap["mAP"]
    previous = base_ap["mAP"] if base_ap else None
    lines.append(
        f"{'mAP@0.5 (all classes)':<34}{current:>10}{against('', current, previous):>24}"
    )
    lines.append(f"{'classes evaluated':<34}{ap['classes_evaluated']:>10}{'':>24}")
    lines += [
        "",
        f"Latency (shipped conf): p50 {lat['p50']:.0f} ms  p95 {lat['p95']:.0f} ms "
        f"over {lat['frames']} frames (cpu load {lat['cpu_load_percent']}%)",
        f"H4 realtime: {h4['inference_interval']} x {lat['p50']:.0f} ms = "
        f"{h4['refresh_s']:.2f} s refresh vs {h4['target_lock_s']:.1f} s lock "
        f"-> {'CLOSES' if h4['closes_loop'] else 'BROKEN'}",
        f"Config: {json.dumps(report['config_snapshot'])}",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure multi-object detection accuracy on labelled data."
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override a config key (repeatable), e.g. --set ai.yolo_imgsz=640",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=0, help="max images (0 = all)")
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument(
        "--ap-conf",
        type=float,
        default=AP_CONFIDENCE,
        help="low confidence used for the accuracy pass (AP needs the curve)",
    )
    parser.add_argument("--latency-frames", type=int, default=40, help="images to time")
    parser.add_argument("--latency-repeats", type=int, default=2)
    parser.add_argument(
        "--compare", type=Path, default=None, help="baseline JSON to diff against"
    )
    parser.add_argument("--json", action="store_true", help="print only JSON")
    parser.add_argument("--no-write", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_benchmark(args)
    except (DatasetError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    baseline = None
    if args.compare and args.compare.exists():
        baseline = json.loads(args.compare.read_text(encoding="utf-8"))

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render(report, baseline))

    if not args.no_write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if not args.json:
            print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
