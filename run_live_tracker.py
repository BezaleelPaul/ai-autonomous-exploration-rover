"""Standalone High-Accuracy Live Ultralytics Object Tracker.

Uses official Ultralytics YOLO11s (high confidence) or YOLO-World (detect ANY custom object).
Zero project dependencies — pure official Ultralytics pipeline.

Usage:
    # 1. High-accuracy 80-class COCO tracking (bottle, person, phone, laptop, cup, chair, etc.):
    python run_live_tracker.py --model yolo11s.pt

    # 2. Open-Vocabulary tracking (detect ANY object: pen, keys, watch, phone, bottle, etc.):
    python run_live_tracker.py --world --classes "person,pen,cell phone,bottle,keys,watch,cup,laptop,book"

    # 3. Phone Camera Stream (IP Webcam / DroidCam / ESP32-CAM):
    python run_live_tracker.py --source "http://192.168.1.50:8080/video" --world
    python run_live_tracker.py --source "http://192.168.1.100:81/stream" --model yolo11s.pt

    # 4. Choose tracker algorithm:
    python run_live_tracker.py --tracker botsort.yaml    # Camera motion compensation
    python run_live_tracker.py --tracker bytetrack.yaml  # High speed multi-object
    python run_live_tracker.py --tracker tracktrack.yaml # Multi-cue association
"""

from __future__ import annotations

import argparse
import sys
import cv2
from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description="Live Ultralytics Object Tracking")
    parser.add_argument("--source", default=0, help="Webcam index (0) or video file path")
    parser.add_argument("--model", type=str, default="yolo11s.pt", help="Model weights (yolo11s.pt, yolov8s-worldv2.pt, etc.)")
    parser.add_argument("--world", action="store_true", help="Use YOLO-World open-vocabulary model (detect ANY object)")
    parser.add_argument(
        "--classes",
        type=str,
        default="person,pen,cell phone,bottle,cup,laptop,mouse,keys,watch,book,chair,backpack",
        help="Comma-separated custom classes (for YOLO-World)",
    )
    parser.add_argument("--tracker", type=str, default="bytetrack.yaml", help="Tracker config: bytetrack.yaml | botsort.yaml | tracktrack.yaml")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold (default: 0.25)")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference resolution (640 recommended for accuracy)")
    parser.add_argument("--fourier", action="store_true", help="Enable 2D Fourier Homomorphic High-Frequency Emphasis")
    args = parser.parse_args()

    # Determine source (integer for webcam, string for video)
    source = int(args.source) if str(args.source).isdigit() else args.source

    # Select model
    model_name = "yolov8s-worldv2.pt" if args.world else args.model
    tracker_name = args.tracker if args.tracker.endswith(".yaml") else f"{args.tracker}.yaml"

    print("=" * 70)
    print("  Official Ultralytics Live Multi-Object Tracking")
    print(f"  Model:   {model_name}")
    print(f"  Tracker: {tracker_name}")
    print(f"  Source:  {source}")
    print(f"  Res:     {args.imgsz}x{args.imgsz}")
    print(f"  Fourier: {'ON (2D Frequency HFE)' if args.fourier else 'OFF'}")
    print("=" * 70)

    model = YOLO(model_name)

    # If YOLO-World, set custom vocabulary
    if args.world or "world" in model_name.lower():
        custom_list = [c.strip() for c in args.classes.split(",") if c.strip()]
        print(f"[YOLO-World] Configured vocabulary ({len(custom_list)} classes): {custom_list}")
        model.set_classes(custom_list)

    # Open video capture with DirectShow on Windows for fast webcam grab
    if isinstance(source, int):
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(source)
    else:
        cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"Error: Unable to open video source '{source}'. Please check your webcam connection.")
        sys.exit(1)

    print("\nStarting live tracking window... (Click on the video window and press 'q' to quit)")

    try:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok or frame is None:
                print("Video stream ended or frame grab failed.")
                break

            infer_frame = frame
            if args.fourier:
                from software.camera.fourier_enhancer import fourier_enhance_frame

                infer_frame = fourier_enhance_frame(frame)

            # Run official ultralytics tracking pass
            results = model.track(
                infer_frame,
                persist=True,
                tracker=tracker_name,
                imgsz=args.imgsz,
                conf=args.conf,
                verbose=False,
            )

            # Draw official tracking boxes, labels, and IDs
            annotated_frame = results[0].plot()

            # Add HUD banner
            dets_count = len(results[0].boxes) if results[0].boxes is not None else 0
            cv2.putText(
                annotated_frame,
                f"Model: {model_name} | Tracker: {tracker_name} | Objects: {dets_count}",
                (15, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 100),
                2,
            )

            cv2.imshow("Ultralytics Live Tracking", annotated_frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Live tracking stopped.")


if __name__ == "__main__":
    main()
