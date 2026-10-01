"""Capture frames from the ESP32-CAM into a labelled dataset.

The repo had zero footage, so every camera-side metric (FPS, frame age,
dropped frames, real-scene false-positive rate) was NOT YET MEASURED. This
tool records frames plus their per-frame metadata so those numbers can exist.

Usage:
  py -3.12 scripts/collect_camera_dataset.py --condition center_1.5m_500lux --frames 30
  py -3.12 scripts/collect_camera_dataset.py --source mock --condition empty_no_target --frames 5
  py -3.12 scripts/collect_camera_dataset.py --condition dark_10lux_1.5m --frames 30 --auto-label

Writes:
  <out>/images/<condition>/*.jpg     the frames
  <out>/labels/<condition>/*.txt     only with --auto-label: MODEL PREDICTIONS,
                                     not human ground truth
  <out>/manifest.csv                 one row per frame
  <out>/classes.txt                  class index -> label (only with --auto-label)
  logs/collect_camera.json           MEASURED capture stats (fps, frame age, dropped)

HARDWARE REQUIRED for real numbers; --source mock exists only so the tool can
be exercised without a camera.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from software.camera.esp32_stream import ESP32Stream  # noqa: E402
from software.camera.frame_manager import FrameManager  # noqa: E402
from software.utils.config_loader import load_config  # noqa: E402

DEFAULT_CONFIG = ROOT / "config" / "config.yaml"
DEFAULT_OUT = ROOT / "datasets" / "camera128"
DEFAULT_STATS = ROOT / "logs" / "collect_camera.json"

# Capture plan (SOURCE: design, not a measurement). Axes are the ones already
# documented in docs/26_EXPERIMENTAL_METHODOLOGY.md and docs/25_TEST_PLAN.md:
# lighting 10/100/500/2000 lux, distance, position, occlusion, clutter.
CONDITIONS: tuple[str, ...] = (
    "empty_no_target",
    "center_0.5m_500lux",
    "center_1.5m_500lux",
    "center_3.0m_500lux",
    "left_1.5m_500lux",
    "right_1.5m_500lux",
    "dark_10lux_1.5m",
    "dim_100lux_1.5m",
    "bright_2000lux_1.5m",
    "glare_direct_1.5m",
    "occluded_partial_1.5m",
    "occluded_heavy_1.5m",
    "multi_two_targets_1.5m",
    "clutter_background_1.5m",
    "moving_target_1.5m",
)

MANIFEST_FIELDS = (
    "file",
    "condition",
    "capture_ts",
    "frame_age_s",
    "width",
    "height",
    "stream_fps",
    "detections",
    "label_source",
    "source",
)


class CaptureError(Exception):
    """Input or hardware problem the caller should see as a usage error."""


def open_source(args: argparse.Namespace, cfg: dict):
    """Return (reader, label). reader() -> frame or None."""
    if args.source == "mock":
        stream = ESP32Stream("mock", mock=True)
        stream.open()
        return stream.read, "mock"

    if args.source == "webcam":
        import cv2

        cap = cv2.VideoCapture(args.device)
        if not cap.isOpened():
            raise CaptureError(f"webcam {args.device} could not be opened")

        def _webcam_read():
            ok, frame = cap.read()
            return frame if ok else None

        return _webcam_read, "webcam"

    url = args.url or cfg["camera"].get("esp32_url")
    if not url:
        raise CaptureError("no stream url; set --url or camera.esp32_url")
    stream = ESP32Stream(url, fps_target=cfg["camera"].get("fps_target"))
    if not stream.open():
        raise CaptureError(f"could not open {url} (is the ESP32-CAM on?)")
    return stream.read, "esp32"


def write_labels(
    rows: list[dict],
    frames: dict[str, Any],
    detector: Any,
    names: dict[int, str],
    out: Path,
) -> None:
    """Write YOLO-format labels. These are model predictions, not ground truth."""
    index = {label: idx for idx, label in names.items()}
    label_dir = out / "labels"
    label_dir.mkdir(parents=True, exist_ok=True)
    (out / "classes.txt").write_text(
        "\n".join(f"{idx} {label}" for idx, label in sorted(names.items())) + "\n",
        encoding="utf-8",
    )
    for row in rows:
        frame = frames[row["file"]]
        height, width = frame.shape[:2]
        detections = detector.detect(frame) or []
        row["detections"] = len(detections)
        row["label_source"] = "model_prediction (NOT ground truth)"
        lines = []
        for det in detections:
            if det.class_name not in index:
                continue
            cx = det.center_x / width
            cy = det.center_y / height
            w = det.width / width
            h = det.height / height
            lines.append(f"{index[det.class_name]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
        target = label_dir / (Path(row["file"]).stem + ".txt")
        target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def capture(args: argparse.Namespace) -> dict:
    cfg = load_config(args.config)
    reader, source_label = open_source(args, cfg)
    frames_mgr = FrameManager(
        inference_interval=1,
        max_frame_age_s=float(cfg.get("safety", {}).get("frame_timeout_s", 3.0)),
    )

    detector = None
    names: dict[int, str] = {}
    if args.auto_label:
        from software.ai.detector import create_detector, detector_class_names

        detector = create_detector(cfg)
        load = getattr(detector, "load", None)
        if not callable(load) or not load():
            raise CaptureError(
                f"detector failed to load: {getattr(detector, 'load_error', '?')}"
            )
        names = detector_class_names(detector)
        if not names:
            raise CaptureError("detector exposed no class names")

    image_dir = args.out / "images" / args.condition
    image_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    frames: dict[str, Any] = {}
    started = time.time()
    index = 0
    stale = 0
    failures = 0
    while index < args.frames:
        if args.seconds and (time.time() - started) >= args.seconds:
            break
        frame = reader()
        if frame is None:
            failures += 1
            if failures >= args.max_failures:
                raise CaptureError(f"{args.max_failures} consecutive unreadable frames")
        else:
            failures = 0
            capture_ts = time.time()
            frames_mgr.observe(frame, capture_time=capture_ts - args.ingest_lag_s)
            stored = frames_mgr.consume()
            if stored is None:
                continue
            age = frames_mgr.frame_age(now=capture_ts)
            if age is not None and age > frames_mgr.max_frame_age_s:
                stale += 1
            index += 1
            name = f"{args.condition}_{index:04d}.jpg"
            import cv2

            if not cv2.imwrite(str(image_dir / name), stored):
                raise CaptureError(f"could not write {image_dir / name}")
            height, width = stored.shape[:2]
            rel = str((image_dir / name).relative_to(args.out)).replace("\\", "/")
            rows.append(
                {
                    "file": rel,
                    "condition": args.condition,
                    "capture_ts": round(capture_ts, 3),
                    "frame_age_s": "" if age is None else round(age, 3),
                    "width": width,
                    "height": height,
                    "stream_fps": "",
                    "detections": "",
                    "label_source": "unlabelled",
                    "source": source_label,
                }
            )
            if detector is not None:
                frames[rel] = stored
        if args.interval > 0:
            time.sleep(args.interval)

    if detector is not None:
        write_labels(rows, frames, detector, names, args.out)

    args.out.mkdir(parents=True, exist_ok=True)
    capture_fps = round(len(rows) / max(1e-6, time.time() - started), 3)
    for row in rows:
        row["stream_fps"] = capture_fps
    with (args.out / "manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    stats = frames_mgr.stats()
    elapsed = max(1e-6, time.time() - started)
    return {
        "label": "MEASURED" if source_label != "mock" else "SIMULATED (mock source)",
        "condition": args.condition,
        "source": source_label,
        "frames_saved": len(rows),
        "capture_fps": capture_fps,
        "elapsed_s": round(elapsed, 3),
        "frame_age_s": stats["age_s"],
        "dropped": stats["dropped"],
        "stale_frames": stale,
        "dataset": str(args.out),
        "manifest": str(args.out / "manifest.csv"),
        "auto_labelled": bool(args.auto_label),
        "ground_truth": "NO — labels are model predictions"
        if args.auto_label
        else "NONE",
        "conditions_available": list(CONDITIONS),
        "note": (
            "Camera-side metrics require real hardware. --source mock produces "
            "SIMULATED numbers and must never be quoted as camera evidence."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture ESP32-CAM frames into a labelled dataset."
    )
    parser.add_argument(
        "--condition",
        required=True,
        choices=CONDITIONS,
        help="capture condition (lighting / position / occlusion)",
    )
    parser.add_argument(
        "--source", choices=("esp32", "webcam", "mock"), default="esp32"
    )
    parser.add_argument("--device", type=int, default=0, help="webcam index")
    parser.add_argument("--url", default=None, help="override camera.esp32_url")
    parser.add_argument("--frames", type=int, default=30, help="frames to save")
    parser.add_argument(
        "--seconds", type=float, default=0.0, help="time budget (0 = ignore)"
    )
    parser.add_argument(
        "--interval", type=float, default=0.5, help="seconds between saves"
    )
    parser.add_argument(
        "--ingest-lag-s", type=float, default=0.05, help="assumed capture->read lag"
    )
    parser.add_argument("--max-failures", type=int, default=20)
    parser.add_argument(
        "--auto-label", action="store_true", help="write PREDICTED YOLO labels"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--out-stats", type=Path, default=DEFAULT_STATS)
    parser.add_argument("--json", action="store_true", help="print only JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.frames < 1:
        print("error: --frames must be >= 1", file=sys.stderr)
        return 2
    if args.interval < 0:
        print("error: --interval must be >= 0", file=sys.stderr)
        return 2
    if (
        args.source != "mock"
        and args.condition == "empty_no_target"
        and args.auto_label
    ):
        print(
            "warning: auto-labelling an empty scene only proves the model "
            "finds nothing; it is not ground truth",
            file=sys.stderr,
        )
    try:
        summary = capture(args)
    except CaptureError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    args.out_stats.parent.mkdir(parents=True, exist_ok=True)
    args.out_stats.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"saved {summary['frames_saved']} frames -> {summary['dataset']}\n"
            f"  label: {summary['label']}  capture_fps={summary['capture_fps']} "
            f"frame_age={summary['frame_age_s']}s dropped={summary['dropped']}\n"
            f"  ground truth: {summary['ground_truth']}\n"
            f"  manifest: {summary['manifest']}\n"
            f"  stats: {args.out_stats}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
