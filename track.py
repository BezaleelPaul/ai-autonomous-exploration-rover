"""Ready-to-run YOLO26 multi-object tracking test script.

Usage:
    python track.py [--video test.mp4] [--tracker tracktrack.yaml] [--model yolo26n.pt]
                    [--conf 0.15] [--imgsz 480] [--sahi]

Press 'q' in the display window to exit.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import cv2
import numpy as np
from ultralytics import YOLO

from software.perception.multi_object_tracker import MultiObjectTracker


def main() -> None:
    parser = argparse.ArgumentParser(description="Test YOLO multi-object tracking on video or webcam.")
    parser.add_argument("--video", type=str, default="test.mp4", help="Video path or camera index (default: test.mp4)")
    parser.add_argument("--tracker", type=str, default="tracktrack.yaml", help="Tracker config: tracktrack.yaml | botsort.yaml | bytetrack.yaml | fasttrack.yaml | ocsort.yaml")
    parser.add_argument("--model", type=str, default="yolo26n.pt", help="Model weights (yolo26n.pt, yolo11s.pt, etc.)")
    parser.add_argument("--imgsz", type=int, default=480, help="Inference resolution (default: 480)")
    parser.add_argument("--conf", type=float, default=0.15, help="Confidence threshold (default: 0.15)")
    parser.add_argument("--point-tracking", action="store_true", default=True, help="Enable point tracking deformation recovery")
    args = parser.parse_args()

    # Normalize tracker name
    tracker_name = args.tracker
    if not tracker_name.endswith(".yaml") and not tracker_name.endswith(".yml"):
        tracker_name = f"{tracker_name}.yaml"

    print(f"[Track] Loading model: {args.model}")
    print(f"[Track] Using tracker: {tracker_name} at resolution {args.imgsz}")

    model = YOLO(args.model)

    # Open video source (file or webcam index or simulated fallback)
    source = args.video
    if source.isdigit():
        source = int(source)
    elif not os.path.isfile(source):
        print(f"[Track] Note: Video file '{source}' not found. Falling back to default webcam (index 0)...")
        source = 0

    if isinstance(source, int):
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(source)
    else:
        cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"[Track] Error: Could not open video source {source}. Generating synthetic target frames for test.")
        synthetic_mode = True
    else:
        synthetic_mode = False

    mot = MultiObjectTracker(enable_point_tracking=args.point_tracking)
    frame_idx = 0

    print("[Track] Press 'q' to quit.")

    try:
        while True:
            if synthetic_mode:
                # Synthetic target frame for testing without a camera
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                frame[:] = (30, 30, 35)
                cx = int(320 + 150 * np.sin(frame_idx * 0.05))
                cy = int(240 + 60 * np.cos(frame_idx * 0.05))
                cv2.rectangle(frame, (cx - 35, cy - 65), (cx + 35, cy + 65), (0, 220, 255), -1)
                cv2.putText(frame, "SIMULATED BOTTLE TARGET", (cx - 90, cy - 75), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
                time.sleep(0.03)
                ok = True
            else:
                ok, frame = cap.read()
                if not ok:
                    print("[Track] Video stream finished or disconnected.")
                    break

            frame_idx += 1

            # Run tracking pass
            t0 = time.perf_counter()
            try:
                results = model.track(
                    frame,
                    persist=True,
                    tracker=tracker_name,
                    imgsz=args.imgsz,
                    conf=args.conf,
                    verbose=False,
                )
                annotated = results[0].plot()
            except Exception as e:
                annotated = frame.copy()
                cv2.putText(annotated, f"Track error: {e}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            dt_ms = (time.perf_counter() - t0) * 1000.0
            fps = 1000.0 / dt_ms if dt_ms > 0 else 0.0

            # Telemetry overlay
            cv2.putText(annotated, f"Tracker: {tracker_name} | {dt_ms:.1f}ms ({fps:.1f} FPS)", (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 120), 2)

            cv2.imshow("YOLO26 Tracking", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        if not synthetic_mode:
            cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
