"""Test local webcam + run AI model on live frames.
Usage:
  python scripts/test_webcam.py --frames 3              # headless: infer + save annotated jpg
  python scripts/test_webcam.py --show                  # live window (Q quits)
  python scripts/test_webcam.py --backend mock --show   # no weights needed
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from software.utils.config_loader import load_config
from software.ai.detector import create_detector


def annotate(frame: np.ndarray, dets) -> np.ndarray:
    try:
        import cv2
    except ImportError:
        return frame
    out = frame.copy()
    for d in dets:
        cv2.rectangle(
            out, (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2)), (0, 255, 0), 2
        )
        cv2.putText(
            out,
            f"{d.class_name} {d.confidence:.2f}",
            (int(d.x1), max(0, int(d.y1) - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cam", type=int, default=0)
    p.add_argument(
        "--backend", default=None, help="override config ai.backend (hf|mock|color)"
    )
    p.add_argument("--conf", type=float, default=None)
    p.add_argument("--show", action="store_true")
    p.add_argument("--frames", type=int, default=200)
    p.add_argument("--save", default="logs/webcam_annotated.jpg")
    args = p.parse_args()

    try:
        import cv2
    except ImportError:
        print("ERROR: opencv not installed. Run: pip install opencv-python")
        sys.exit(1)

    cfg = load_config("config/config.yaml")
    if args.backend:
        cfg["ai"]["backend"] = args.backend
    if args.conf is not None:
        cfg["ai"]["confidence_threshold"] = args.conf

    cap = cv2.VideoCapture(args.cam)
    if not cap.isOpened():
        print(
            f"ERROR: cannot open webcam index {args.cam}. "
            "Try --cam 1, or check another app isn't using the camera."
        )
        sys.exit(1)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Webcam {args.cam}: {w}x{h}")

    det = create_detector(cfg)
    print(f"Detector: {type(det).__name__} (model={cfg['ai'].get('model_name')})")
    load = getattr(det, "load", None)
    if callable(load):
        t0 = time.time()
        ok = load()
        print(
            f"Model load: {ok} in {time.time() - t0:.1f}s"
            + (f" ({getattr(det, 'load_error', '')})" if not ok else "")
        )

    Path("logs").mkdir(exist_ok=True)
    n, lat, grab_fails = 0, [], 0
    t_start = time.time()
    try:
        while n < args.frames:
            ok, frame = cap.read()
            if not ok or frame is None:
                grab_fails += 1
                if grab_fails > 15:
                    print(
                        "ERROR: webcam busy or disconnected (is the dashboard or another app using it?)."
                    )
                    print(
                        "Fix: close http://127.0.0.1:5000 browser tabs / stop scripts/dashboard.py, then retry."
                    )
                    sys.exit(2)
                time.sleep(0.2)
                continue
            grab_fails = 0
            if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
                print(f"WARN: unexpected frame {frame.shape} {frame.dtype}, skipping")
                continue
            t0 = time.time()
            try:
                from software.camera.enhance import enhance_for_inference

                cam_cfg = cfg.get("camera", {})
                probe = enhance_for_inference(
                    frame,
                    clahe=cam_cfg.get("enhance_clahe", True),
                    sharpen=cam_cfg.get("enhance_sharpen", True),
                    denoise=cam_cfg.get("enhance_denoise", False),
                )
            except Exception:
                probe = frame
            dets = det.detect(probe) or []
            ms = (time.time() - t0) * 1000.0
            lat.append(ms)
            n += 1
            fps = n / max(time.time() - t_start, 1e-6)
            print(
                f"frame {n}: {len(dets)} obj, {ms:.0f}ms, {fps:.1f} FPS"
                + "".join(
                    f" | {d.class_name} {d.confidence:.2f} cx={d.center_x:.0f}"
                    for d in dets
                )
            )
            shown = annotate(frame, dets)
            cv2.imwrite(args.save, shown)
            if args.show:
                cv2.imshow("webcam + AI (Q quits)", shown)
                if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                    break
    finally:
        cap.release()
        if args.show:
            cv2.destroyAllWindows()
    if lat:
        a = np.array(lat)
        print(
            f"done: {n} frames, infer mean {a.mean():.0f}ms p50 {np.median(a):.0f}ms, "
            f"saved -> {args.save}"
        )


if __name__ == "__main__":
    main()
