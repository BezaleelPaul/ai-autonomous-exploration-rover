"""Multi-Tracker and Distant Object Detection Benchmark Utility.

Benchmarks Ultralytics tracking algorithms (TrackTrack, BoT-SORT, ByteTrack,
FastTracker, OC-SORT) and SAHI Sliced Inference on video or image sequences.
Measures:
- Simultaneous multiple object tracking count & ID stability
- Distant / small object detection recall
- Inference latency (ms) & real-time FPS
- Tracking recovery across occlusions and camera motion

Usage:
    py -3.12 scripts/benchmark_trackers.py [--video test.mp4] [--model yolo26n.pt]
        [--trackers tracktrack,botsort,bytetrack,fasttrack,ocsort]
        [--sahi] [--imgsz 320] [--conf 0.25] [--limit 50]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from software.ai.detector import YoloDetector
from software.perception.multi_object_tracker import MultiObjectTracker


AVAILABLE_TRACKERS = [
    "tracktrack.yaml",
    "botsort.yaml",
    "bytetrack.yaml",
    "fasttrack.yaml",
    "ocsort.yaml",
]


def load_frames(
    video_path: str | None = None,
    image_dir: str | None = None,
    limit: int = 50,
) -> list[np.ndarray]:
    """Load frames from video file, directory of images, or generate synthetic test frames."""
    import cv2

    frames: list[np.ndarray] = []

    if video_path and os.path.isfile(video_path):
        cap = cv2.VideoCapture(video_path)
        while cap.isOpened() and len(frames) < limit:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            frames.append(frame)
        cap.release()
        if frames:
            return frames

    if image_dir and os.path.isdir(image_dir):
        image_files = sorted(
            glob.glob(os.path.join(image_dir, "*.jpg"))
            + glob.glob(os.path.join(image_dir, "*.png"))
        )[:limit]
        for img_path in image_files:
            f = cv2.imread(img_path)
            if f is not None:
                frames.append(f)
        if frames:
            return frames

    # Fallback to recorded runs or COCO sample images
    run_images = sorted(glob.glob(str(ROOT / "data" / "runs" / "**" / "*.jpg"), recursive=True))[:limit]
    if run_images:
        for p in run_images:
            f = cv2.imread(p)
            if f is not None:
                frames.append(f)
        if frames:
            return frames

    coco_images = sorted(glob.glob(str(ROOT / "datasets" / "coco128" / "images" / "train2017" / "*.jpg")))[:limit]
    if coco_images:
        for p in coco_images:
            f = cv2.imread(p)
            if f is not None:
                frames.append(f)
        if frames:
            return frames

    # Synthetic fallback: 640x480 moving objects of various sizes
    for i in range(min(30, limit)):
        f = np.zeros((480, 640, 3), dtype=np.uint8)
        f[:] = (35, 35, 40)
        # Large nearby object
        cx1 = int(200 + 80 * np.sin(i * 0.2))
        cy1 = int(250 + 40 * np.cos(i * 0.2))
        cv2.rectangle(f, (cx1 - 40, cy1 - 70), (cx1 + 40, cy1 + 70), (0, 200, 255), -1)
        # Small distant object
        cx2 = int(450 - 50 * np.cos(i * 0.15))
        cy2 = int(140 + 20 * np.sin(i * 0.15))
        cv2.rectangle(f, (cx2 - 12, cy2 - 18), (cx2 + 12, cy2 + 18), (50, 255, 50), -1)
        frames.append(f)

    return frames


def evaluate_tracker(
    tracker_name: str,
    frames: list[np.ndarray],
    model_name: str = "yolo26n.pt",
    imgsz: int = 320,
    conf_thresh: float = 0.25,
    sahi_enabled: bool = False,
    enable_point_tracking: bool = True,
) -> dict:
    """Benchmark a specific tracker across the frame sequence."""
    tracker_cfg = tracker_name if tracker_name.endswith(".yaml") else f"{tracker_name}.yaml"
    detector = YoloDetector(
        model=model_name,
        confidence_threshold=conf_thresh,
        imgsz=imgsz,
        track=True,
        tracker=tracker_cfg,
        sahi_enabled=sahi_enabled,
        sahi_slice_size=imgsz,
        sahi_overlap=0.20,
    )
    detector.load()

    mot = MultiObjectTracker(enable_point_tracking=enable_point_tracking)

    latencies_ms: list[float] = []
    total_detections = 0
    unique_track_ids: set[int] = set()
    distant_detections = 0  # Bounding box area < 3% of frame
    coasting_frames_count = 0

    for i, frame in enumerate(frames):
        h, w = frame.shape[:2]
        frame_area = float(w * h)

        t0 = time.perf_counter()
        dets = detector.detect(frame)
        tracks = mot.update(dets, frame=frame)
        dt = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(dt)

        total_detections += len(dets)
        for d in dets:
            if d.track_id is not None:
                unique_track_ids.add(d.track_id)
            box_area = d.width * d.height
            if (box_area / frame_area) < 0.03:
                distant_detections += 1

        for tr in tracks:
            unique_track_ids.add(tr.track_id)
            if tr.is_coasting:
                coasting_frames_count += 1

    p50 = float(np.median(latencies_ms)) if latencies_ms else 0.0
    p95 = float(np.percentile(latencies_ms, 95)) if latencies_ms else 0.0
    mean_fps = (1000.0 / p50) if p50 > 0 else 0.0

    return {
        "tracker": tracker_name,
        "sahi_enabled": sahi_enabled,
        "frames_tested": len(frames),
        "total_detections": total_detections,
        "avg_detections_per_frame": round(total_detections / max(1, len(frames)), 2),
        "distant_objects_detected": distant_detections,
        "unique_tracks": len(unique_track_ids),
        "coasted_recovery_events": coasting_frames_count,
        "latency_p50_ms": round(p50, 1),
        "latency_p95_ms": round(p95, 1),
        "fps_p50": round(mean_fps, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Ultralytics trackers and SAHI detection.")
    parser.add_argument("--video", type=str, default=None, help="Path to input test video")
    parser.add_argument("--images", type=str, default=None, help="Directory of input test images")
    parser.add_argument("--model", type=str, default="yolo26n.pt", help="YOLO model checkpoint")
    parser.add_argument(
        "--trackers",
        type=str,
        default="tracktrack,botsort,bytetrack,fasttrack,ocsort",
        help="Comma-separated tracker list",
    )
    parser.add_argument("--sahi", action="store_true", help="Enable SAHI sliced inference")
    parser.add_argument("--compare-sahi", action="store_true", help="Compare standard vs SAHI mode")
    parser.add_argument("--imgsz", type=int, default=320, help="Inference resolution")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--limit", type=int, default=20, help="Frame count limit")
    parser.add_argument("--out", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()

    trackers = [t.strip() for t in args.trackers.split(",") if t.strip()]
    frames = load_frames(args.video, args.images, limit=args.limit)
    print(f"[Benchmark] Loaded {len(frames)} frames. Model: {args.model}, Resolution: {args.imgsz}")

    results = []

    for tracker in trackers:
        print(f"[Benchmark] Testing tracker: {tracker} (Standard)...")
        res_std = evaluate_tracker(
            tracker,
            frames,
            model_name=args.model,
            imgsz=args.imgsz,
            conf_thresh=args.conf,
            sahi_enabled=False,
        )
        results.append(res_std)

        if args.sahi or args.compare_sahi:
            print(f"[Benchmark] Testing tracker: {tracker} (SAHI Sliced)...")
            res_sahi = evaluate_tracker(
                tracker,
                frames,
                model_name=args.model,
                imgsz=args.imgsz,
                conf_thresh=args.conf,
                sahi_enabled=True,
            )
            results.append(res_sahi)

    print("\n" + "=" * 92)
    print(
        f"{'Tracker':<18} | {'SAHI':<6} | {'Dets/Frame':<10} | {'Distant Objs':<12} | {'Tracks':<6} | {'p50 (ms)':<8} | {'FPS':<6}"
    )
    print("-" * 92)
    for r in results:
        sahi_str = "ON" if r["sahi_enabled"] else "OFF"
        print(
            f"{r['tracker']:<18} | {sahi_str:<6} | {r['avg_detections_per_frame']:<10} | "
            f"{r['distant_objects_detected']:<12} | {r['unique_tracks']:<6} | "
            f"{r['latency_p50_ms']:<8} | {r['fps_p50']:<6}"
        )
    print("=" * 92)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"[Benchmark] Results saved to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
