#!/usr/bin/env python3
"""AI Rover — 24-class model (COCO train2017 + val2017) + edge-case evaluation.

Why this over the 6-class bootstrap:
  * 24 rover-relevant classes instead of 6 (people, furniture, small objects,
    pets, street furniture) -> broader "can it see this?" coverage.
  * Trains on COCO train2017 (up to 12k images) and validates on val2017,
    which is the honest split direction.
  * Quantifies edge cases instead of claiming them: small objects, dark scenes,
    cluttered/overlapping boxes, and Gaussian blur.

Still not "any object": for arbitrary prompts use the open-vocabulary mode in
the app (`yolov8s-worldv2.pt`). This kernel produces a fast fixed-class model.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

MAX_TRAIN = 12000
EPOCHS = 60
SEED = 0

ROVER_NAMES = [
    "person", "bicycle", "car", "bench", "cat", "dog",
    "backpack", "handbag", "suitcase", "bottle", "cup", "bowl",
    "chair", "couch", "potted plant", "bed", "dining table",
    "laptop", "cell phone", "book", "clock", "vase", "scissors", "teddy bear",
]
NAME_TO_ROVER = {name: i for i, name in enumerate(ROVER_NAMES)}

T0 = time.time()


def log(msg: str) -> None:
    print(f"[rover24 +{time.time() - T0:6.0f}s] {msg}", flush=True)


def pip_install(package: str) -> None:
    log(f"installing {package}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", package])


def find_file(name: str) -> Path:
    """Find a dataset file even when Kaggle mounts it behind a symlink.

    Path.rglob() does not reliably follow symlinked dataset directories, so walk
    explicitly with followlinks=True and log the search roots.
    """
    top = sorted(p.name for p in Path("/kaggle/input").iterdir())
    log(f"/kaggle/input entries: {top[:10]}")

    def _raise(err):
        log(f"walk error: {err}")

    for root, _dirs, files in os.walk("/kaggle/input", followlinks=True, onerror=_raise):
        if name in files:
            found = Path(root) / name
            log(f"found {name}: {found}")
            return found
    raise SystemExit(f"{name} not found under /kaggle/input")


def find_inputs() -> tuple[Path, Path, Path]:
    ann_train = find_file("instances_train2017.json")
    ann_val = find_file("instances_val2017.json")
    root = ann_train.parent.parent
    img_train = root / "train2017"
    img_val = root / "val2017"
    if not img_train.is_dir():
        # fall back to any sibling layout
        for candidate in root.glob("**/train2017"):
            if candidate.is_dir():
                img_train = candidate
                break
    if not img_val.is_dir():
        for candidate in root.glob("**/val2017"):
            if candidate.is_dir():
                img_val = candidate
                break
    if not (img_train.is_dir() and img_val.is_dir()):
        raise SystemExit(f"image dirs not found under {root}: {sorted(p.name for p in root.iterdir())[:20]}")
    log(f"train annotations: {ann_train}")
    log(f"val annotations  : {ann_val}")
    log(f"images           : {img_train} | {img_val}")
    return ann_train, ann_val, root


def load_annotations(path: Path) -> dict:
    """Parse COCO JSON fast. orjson is ~10x faster; json is the fallback.

    (ijson's pure-Python backend took 37 minutes on the 470 MB train file and
    returns Decimal coordinates, so it is deliberately not used.)
    """
    try:
        import orjson

        return orjson.loads(path.read_bytes())
    except ImportError:
        return json.loads(path.read_text())


def build_index(data: dict) -> tuple[dict[int, int], dict[int, dict], dict[int, list]]:
    """category_id -> rover id (by name), image metadata, boxes per image."""
    mapping: dict[int, int] = {}
    for category in data["categories"]:
        rover_id = NAME_TO_ROVER.get(str(category["name"]).strip().lower())
        if rover_id is not None:
            mapping[int(category["id"])] = rover_id

    meta = {
        int(image["id"]): {
            "file_name": image["file_name"],
            "width": float(image["width"]),
            "height": float(image["height"]),
        }
        for image in data["images"]
    }
    per_image: dict[int, list[tuple[int, list[float]]]] = {}
    for ann in data["annotations"]:
        rover_id = mapping.get(int(ann["category_id"]))
        if rover_id is None or int(ann.get("iscrowd", 0)) != 0:
            continue
        bbox = [float(v) for v in ann["bbox"]]
        per_image.setdefault(int(ann["image_id"]), []).append((rover_id, bbox))
    return mapping, meta, per_image


def yolo_lines(boxes: list[tuple[int, list[float]]], width: float, height: float) -> list[str]:
    lines = []
    for rover_id, (x, y, w, h) in boxes:
        if w <= 0 or h <= 0:
            continue
        cx = min(1.0, max(0.0, (x + w / 2) / width))
        cy = min(1.0, max(0.0, (y + h / 2) / height))
        bw = min(1.0, max(0.0, w / width))
        bh = min(1.0, max(0.0, h / height))
        if bw <= 0 or bh <= 0:
            continue
        lines.append(f"{rover_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    return lines


def write_split(out: Path, split: str, ids: list[int], meta: dict, boxes: dict, img_dir: Path) -> int:
    (out / "images" / split).mkdir(parents=True, exist_ok=True)
    (out / "labels" / split).mkdir(parents=True, exist_ok=True)
    written = 0
    for image_id in ids:
        info = meta.get(image_id)
        if info is None:
            continue
        lines = yolo_lines(boxes[image_id], info["width"], info["height"])
        if not lines:
            continue
        src = img_dir / info["file_name"]
        if not src.is_file():
            continue
        shutil.copy2(src, out / "images" / split / info["file_name"])
        (out / "labels" / split / f"{Path(info['file_name']).stem}.txt").write_text("\n".join(lines) + "\n")
        written += 1
    return written


def data_yaml(out: Path) -> Path:
    path = out / "data.yaml"
    path.write_text(
        "\n".join(
            [
                "# AI Rover 24-class (COCO train2017 -> val2017)",
                f"path: {out}",
                "train: images/train",
                "val: images/val",
                f"nc: {len(ROVER_NAMES)}",
                "names:",
                *[f"  {i}: {n}" for i, n in enumerate(ROVER_NAMES)],
                "",
            ]
        )
    )
    return path


# ---------------------------------------------------------------------------
# Edge-case buckets
# ---------------------------------------------------------------------------
def iou(a, b) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    iy = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def brightness(path: Path) -> float:
    import cv2

    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    return float(image.mean()) if image is not None else 255.0


def write_bucket(name: str, ids: list[int], meta: dict, boxes: dict, img_dir: Path, root: Path,
                 blur: bool = False) -> Path | None:
    if len(ids) < 20:
        log(f"bucket {name}: only {len(ids)} images, skipped")
        return None
    bucket = root / name
    (bucket / "images").mkdir(parents=True, exist_ok=True)
    (bucket / "labels").mkdir(parents=True, exist_ok=True)
    import cv2

    for image_id in ids:
        info = meta[image_id]
        src = img_dir / info["file_name"]
        if not src.is_file():
            continue
        lines = yolo_lines(boxes[image_id], info["width"], info["height"])
        if not lines:
            continue
        if blur:
            image = cv2.imread(str(src))
            if image is None:
                continue
            image = cv2.GaussianBlur(image, (5, 5), 2.5)
            cv2.imwrite(str(bucket / "images" / info["file_name"]), image)
        else:
            shutil.copy2(src, bucket / "images" / info["file_name"])
        (bucket / "labels" / f"{Path(info['file_name']).stem}.txt").write_text("\n".join(lines) + "\n")
    (bucket / "data.yaml").write_text(
        "\n".join(
            [
                f"path: {bucket}",
                "train: images",
                "val: images",
                f"nc: {len(ROVER_NAMES)}",
                "names:",
                *[f"  {i}: {n}" for i, n in enumerate(ROVER_NAMES)],
                "",
            ]
        )
    )
    log(f"bucket {name}: {len(ids)} images")
    return bucket / "data.yaml"


def main() -> int:
    try:
        import cv2  # noqa: F401
        import ultralytics  # noqa: F401
    except ImportError:
        pip_install("ultralytics>=8.3.0")
    try:
        import orjson  # noqa: F401
    except ImportError:
        pip_install("orjson")

    ann_train, ann_val, root = find_inputs()

    log("loading train annotations (470 MB)")
    train_data = load_annotations(ann_train)
    mapping_train, train_meta, train_boxes = build_index(train_data)
    del train_data
    log(f"classes found: {len(mapping_train)}/{len(ROVER_NAMES)} (train)")
    train_ids = [i for i in train_boxes if (root / "train2017" / train_meta[i]["file_name"]).is_file()]
    random.Random(SEED).shuffle(train_ids)
    train_ids = train_ids[:MAX_TRAIN]
    log(f"selected {len(train_ids)} train images")

    log("loading val annotations")
    val_data = load_annotations(ann_val)
    mapping_val, val_meta, val_boxes = build_index(val_data)
    del val_data
    log(f"classes found: {len(mapping_val)}/{len(ROVER_NAMES)} (val)")
    val_ids = [i for i in val_boxes if (root / "val2017" / val_meta[i]["file_name"]).is_file()]
    random.Random(SEED).shuffle(val_ids)
    log(f"selected {len(val_ids)} val images")

    out = Path("/kaggle/working/rover24")
    n_train = write_split(out, "train", train_ids, train_meta, train_boxes, root / "train2017")
    n_val = write_split(out, "val", val_ids, val_meta, val_boxes, root / "val2017")
    yaml_path = data_yaml(out)
    class_counts = [0] * len(ROVER_NAMES)
    for boxes in train_boxes.values():
        for rover_id, _ in boxes:
            class_counts[rover_id] += 1
    stats = {
        "images": {"train": n_train, "val": n_val},
        "boxes_per_class_train": dict(zip(ROVER_NAMES, class_counts)),
        "source": "COCO train2017 -> val2017",
        "classes": ROVER_NAMES,
    }
    Path("/kaggle/working/dataset_stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    log(f"dataset: {n_train} train / {n_val} val")

    # ------------------------------------------------------------------ train
    from ultralytics import YOLO

    log(f"training {len(ROVER_NAMES)} classes, {EPOCHS} epochs @320")
    results = YOLO("yolo11n.pt").train(
        data=str(yaml_path), epochs=EPOCHS, imgsz=320, batch=-1, device=0, workers=2,
        project="/kaggle/working/runs", name="rover24", seed=SEED, deterministic=True,
        pretrained=True, optimizer="auto", lr0=0.004, lrf=0.05, cos_lr=True,
        warmup_epochs=3.0, patience=15, cache="ram", plots=True, val=True,
        hsv_h=0.015, hsv_s=0.6, hsv_v=0.4, translate=0.1, scale=0.5,
        fliplr=0.5, mosaic=0.8, mixup=0.0, close_mosaic=10, erasing=0.2,
    )
    best = Path(results.save_dir) / "weights" / "best.pt"
    if not best.exists():
        raise SystemExit("no best.pt")
    log(f"best: {best}")

    # --------------------------------------------------------------- baseline
    model = YOLO(str(best))
    base = model.val(data=str(yaml_path), imgsz=320, device=0, plots=True)
    per_class = {
        str(base.names[i]): round(float(base.box.maps[i]), 4)
        for i in range(len(getattr(base, "names", {})))
    }
    summary = {
        "mAP50": round(float(base.box.map50), 4),
        "mAP50_95": round(float(base.box.map), 4),
        "precision": round(float(base.box.mp), 4),
        "recall": round(float(base.box.mr), 4),
        "per_class": per_class,
        "images": {"train": n_train, "val": n_val},
        "epochs": EPOCHS,
        "classes": len(ROVER_NAMES),
        "note": "COCO train2017 -> val2017; not a rover-camera benchmark",
    }
    log("baseline: " + json.dumps(summary["mAP50"]))

    # ---------------------------------------------------------------- buckets
    edge: dict = {"baseline": {"images": n_val, "mAP50": summary["mAP50"], "mAP50_95": summary["mAP50_95"]}}
    buckets: dict[str, list[int]] = {"small": [], "dark": [], "cluttered": []}
    for image_id in val_ids:
        boxes = val_boxes[image_id]
        info = val_meta[image_id]
        areas = [w * h for _, (_, _, w, h) in boxes]
        if areas and sum(1 for a in areas if a < 32 * 32) / len(areas) >= 0.6:
            buckets["small"].append(image_id)
        if brightness(root / "val2017" / info["file_name"]) < 60:
            buckets["dark"].append(image_id)
        if len(boxes) > 1 and any(
            iou(boxes[i][1], boxes[j][1]) > 0.2
            for i in range(len(boxes)) for j in range(i + 1, len(boxes))
        ):
            buckets["cluttered"].append(image_id)
    buckets["blurred"] = random.Random(SEED).sample(val_ids, min(250, len(val_ids)))
    log({k: len(v) for k, v in buckets.items()})

    edge_dir = Path("/kaggle/working/edge")
    for name, ids in buckets.items():
        yaml_bucket = write_bucket(name, ids[:500], val_meta, val_boxes, root / "val2017", edge_dir,
                                   blur=(name == "blurred"))
        if yaml_bucket is None:
            edge[name] = {"skipped": True, "images": len(ids)}
            continue
        metrics = YOLO(str(best)).val(data=str(yaml_bucket), imgsz=320, device=0, plots=False, verbose=False)
        edge[name] = {
            "images": min(500, len(ids)),
            "mAP50": round(float(metrics.box.map50), 4),
            "mAP50_95": round(float(metrics.box.map), 4),
            "recall": round(float(metrics.box.mr), 4),
        }
        log(f"{name}: mAP50={edge[name]['mAP50']}")

    edge["delta_vs_baseline"] = {
        k: round(v["mAP50"] - summary["mAP50"], 4)
        for k, v in edge.items()
        if isinstance(v, dict) and "mAP50" in v and k != "baseline"
    }
    Path("/kaggle/working/edge_cases.json").write_text(json.dumps(edge, indent=2) + "\n")
    Path("/kaggle/working/val_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    # --------------------------------------------------------------- export
    ov_dir = YOLO(str(best)).export(format="openvino", imgsz=320, half=True)
    onnx_path = YOLO(str(best)).export(format="onnx", imgsz=320, half=False)

    try:
        import glob

        sample = glob.glob(str(out / "images" / "val" / "*.jpg"))[:8]
        YOLO(str(best)).predict(source=sample, imgsz=320, conf=0.35, save=True,
                                project="/kaggle/working/predictions", name="val")
    except Exception as exc:  # noqa: BLE001
        log(f"prediction samples failed: {exc}")

    bundle = Path("/kaggle/working/rover24_bundle")
    shutil.rmtree(bundle, ignore_errors=True)
    bundle.mkdir(parents=True)
    shutil.copy2(best, bundle / "rover24_best.pt")
    shutil.copytree(ov_dir, bundle / "rover24_openvino", dirs_exist_ok=True)
    shutil.copy2(onnx_path, bundle / "rover24.onnx")
    for name in ("val_summary.json", "edge_cases.json", "dataset_stats.json"):
        shutil.copy2(f"/kaggle/working/{name}", bundle / name)
    shutil.copy2(yaml_path, bundle / "data.yaml")
    for plot in ("results.png", "confusion_matrix.png", "val_batch0_pred.jpg"):
        src = Path("/kaggle/working/runs/rover24") / plot
        if src.is_file():
            shutil.copy2(src, bundle / plot)
    if Path("/kaggle/working/predictions").is_dir():
        shutil.copytree("/kaggle/working/predictions", bundle / "predictions", dirs_exist_ok=True)
    shutil.copy2(best, "/kaggle/working/rover24_best.pt")
    shutil.make_archive("/kaggle/working/rover24_bundle", "zip", bundle)

    # keep the output listing tiny
    for path in ("/kaggle/working/rover24", "/kaggle/working/runs", "/kaggle/working/edge",
                 "/kaggle/working/predictions"):
        shutil.rmtree(path, ignore_errors=True)
    log("DONE bundle: /kaggle/working/rover24_bundle.zip")
    log("DONE summary: " + json.dumps(summary))
    log("DONE edge: " + json.dumps(edge))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
