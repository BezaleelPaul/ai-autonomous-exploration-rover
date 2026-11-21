#!/usr/bin/env python3
"""AI Rover — bootstrap 6-class model from a filtered COCO val2017 subset.

Runs as a Kaggle script kernel with the COCO 2017 dataset attached.

Why val2017?  It is only ~1 GB of images and includes the six rover classes with
real indoor/outdoor photography, so a usable bootstrap model can be produced in
one GPU session.  This is explicitly a *bootstrap*, not a benchmark: the split
comes from the same pool, so the reported mAP is optimistic.  Re-run
kaggle/rover_finetune.ipynb on rover-camera frames for the final model.
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

MAX_IMAGES = 0  # 0 = use every usable image
EPOCHS = 80
SEED = 0

ROVER_NAMES = ["person", "chair", "table", "backpack", "bottle", "plant"]
# COCO category IDs are 1-based and non-contiguous (person=1, chair=62, ...),
# so the mapping is built from the annotation file by *name*, never hard-coded.
COCO_NAME_TO_ROVER = {
    "person": 0,
    "chair": 1,
    "dining table": 2,
    "backpack": 3,
    "bottle": 4,
    "potted plant": 5,
}

T0 = time.time()


def log(msg: str) -> None:
    print(f"[coco6 +{time.time() - T0:6.0f}s] {msg}", flush=True)


def find_annotations() -> Path:
    candidates = sorted(Path("/kaggle/input").rglob("instances_val2017.json"))
    if not candidates:
        raise SystemExit("instances_val2017.json not found under /kaggle/input")
    log(f"annotations: {candidates[0]}")
    return candidates[0]


def find_images(ann: Path) -> Path:
    roots = [ann.parent.parent, ann.parent.parent.parent]
    for root in roots:
        for name in ("val2017", "val2017/val2017"):
            cand = root / name
            if cand.is_dir() and any(cand.glob("*.jpg")):
                log(f"images: {cand}")
                return cand
    for cand in Path("/kaggle/input").rglob("val2017"):
        if cand.is_dir() and any(cand.glob("*.jpg")):
            log(f"images (searched): {cand}")
            return cand
    raise SystemExit("val2017 jpg folder not found")


def main() -> int:
    ann_path = find_annotations()
    img_dir = find_images(ann_path)

    log("loading annotations")
    data = json.loads(ann_path.read_text())
    category_map: dict[int, int] = {}
    for category in data["categories"]:
        rover_id = COCO_NAME_TO_ROVER.get(str(category["name"]).strip().lower())
        if rover_id is not None:
            category_map[int(category["id"])] = rover_id
    log(f"category map: {category_map}")
    missing = set(ROVER_NAMES) - {str(c["name"]) for c in data["categories"]}
    if missing:
        log(f"WARNING: categories missing from annotations: {missing}")

    images = {int(im["id"]): im for im in data["images"]}
    per_image: dict[int, list[tuple[int, list[float]]]] = {}
    for a in data["annotations"]:
        rover_id = category_map.get(int(a["category_id"]))
        if rover_id is None or int(a.get("iscrowd", 0)) != 0:
            continue
        per_image.setdefault(int(a["image_id"]), []).append((rover_id, a["bbox"]))

    usable = [i for i in per_image if (img_dir / f"{i:012d}.jpg").is_file()]
    log(f"images with rover classes: {len(usable)}")
    random.Random(SEED).shuffle(usable)
    selected = usable[:MAX_IMAGES] if MAX_IMAGES else usable
    if len(selected) < 300:
        raise SystemExit(f"too few usable images: {len(selected)}")

    out = Path("/kaggle/working/rover6")
    for split in ("train", "val"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)

    n_val = max(1, int(round(len(selected) * 0.15)))
    val_ids, train_ids = selected[:n_val], selected[n_val:]
    class_counts = [0] * len(ROVER_NAMES)
    written = {"train": 0, "val": 0}

    for split, ids in (("train", train_ids), ("val", val_ids)):
        for image_id in ids:
            im = images[image_id]
            width, height = float(im["width"]), float(im["height"])
            lines = []
            for rover_id, (x, y, w, h) in per_image[image_id]:
                if w <= 0 or h <= 0:
                    continue
                cx = min(1.0, max(0.0, (x + w / 2) / width))
                cy = min(1.0, max(0.0, (y + h / 2) / height))
                bw = min(1.0, max(0.0, w / width))
                bh = min(1.0, max(0.0, h / height))
                if bw <= 0 or bh <= 0:
                    continue
                lines.append(f"{rover_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                class_counts[rover_id] += 1
            if not lines:
                continue
            name = f"{image_id:012d}.jpg"
            shutil.copy2(img_dir / name, out / "images" / split / name)
            (out / "labels" / split / f"{image_id:012d}.txt").write_text("\n".join(lines) + "\n")
            written[split] += 1

    yaml_path = out / "data.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "# AI Rover bootstrap: COCO val2017 filtered to 6 indoor classes",
                f"path: {out}",
                "train: images/train",
                "val: images/val",
                "nc: 6",
                "names:",
                *[f"  {i}: {n}" for i, n in enumerate(ROVER_NAMES)],
                "",
            ]
        )
    )
    stats = {
        "images_total": len(selected),
        "train": written["train"],
        "val": written["val"],
        "boxes_per_class": dict(zip(ROVER_NAMES, class_counts)),
        "source": "COCO val2017",
        "note": "bootstrap split from one pool; metrics are optimistic",
    }
    (Path("/kaggle/working") / "dataset_stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    log(f"dataset ready: {written} | {stats['boxes_per_class']}")

    # ------------------------------------------------------------------ train
    # The Kaggle script image does not ship Ultralytics; install it.
    try:
        import ultralytics  # noqa: F401
    except ImportError:
        log("installing ultralytics")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "ultralytics>=8.3.0"])
    from ultralytics import YOLO

    log("training yolo11n @320")
    results = YOLO("yolo11n.pt").train(
        data=str(yaml_path),
        epochs=EPOCHS,
        imgsz=320,
        batch=-1,
        device=0,
        workers=2,
        project="/kaggle/working/runs",
        name="rover6",
        seed=SEED,
        deterministic=True,
        pretrained=True,
        optimizer="auto",
        lr0=0.003,
        lrf=0.05,
        cos_lr=True,
        warmup_epochs=3.0,
        patience=20,
        cache="ram",
        plots=True,
        val=True,
        hsv_h=0.015,
        hsv_s=0.60,
        hsv_v=0.40,
        degrees=0.0,
        translate=0.10,
        scale=0.50,
        flipud=0.0,
        fliplr=0.50,
        mosaic=0.80,
        mixup=0.0,
        copy_paste=0.0,
        close_mosaic=10,
        erasing=0.20,
    )
    best = Path(results.save_dir) / "weights" / "best.pt"
    log(f"best: {best} exists={best.exists()}")
    if not best.exists():
        raise SystemExit("training produced no best.pt")

    # ------------------------------------------------------------- validate
    log("validating")
    metrics = YOLO(str(best)).val(data=str(yaml_path), imgsz=320, device=0, plots=True)
    per_class = {
        str(metrics.names[i]): round(float(metrics.box.maps[i]), 4)
        for i in range(len(getattr(metrics, "names", {})))
    }
    summary = {
        "mAP50": round(float(metrics.box.map50), 4),
        "mAP50_95": round(float(metrics.box.map), 4),
        "precision": round(float(metrics.box.mp), 4),
        "recall": round(float(metrics.box.mr), 4),
        "per_class": per_class,
        "imgsz": 320,
        "epochs": EPOCHS,
        "images": {"train": written["train"], "val": written["val"]},
        "note": "bootstrap: val is from the same COCO val2017 pool (optimistic)",
    }
    (Path("/kaggle/working") / "val_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    log("metrics: " + json.dumps(summary))

    # --------------------------------------------------------------- export
    log("exporting openvino + onnx")
    ov_dir = YOLO(str(best)).export(format="openvino", imgsz=320, half=True)
    onnx_path = YOLO(str(best)).export(format="onnx", imgsz=320, half=False)
    log(f"openvino: {ov_dir} | onnx: {onnx_path}")

    # Annotated predictions for the model card (8 images, not 360).
    try:
        import glob

        sample = glob.glob(str(out / "images" / "val" / "*.jpg"))[:8]
        YOLO(str(best)).predict(source=sample, imgsz=320, conf=0.35, save=True,
                                project="/kaggle/working/predictions", name="val")
        log("prediction samples saved")
    except Exception as exc:  # noqa: BLE001
        log(f"prediction samples failed: {exc}")

    # ---------------------------------------------------------------- bundle
    bundle = Path("/kaggle/working/rover6_bundle")
    shutil.rmtree(bundle, ignore_errors=True)
    bundle.mkdir(parents=True)
    shutil.copy2(best, bundle / "rover6_best.pt")
    shutil.copytree(ov_dir, bundle / "rover6_openvino", dirs_exist_ok=True)
    shutil.copy2(onnx_path, bundle / "rover6.onnx")
    shutil.copy2("/kaggle/working/val_summary.json", bundle / "val_summary.json")
    shutil.copy2("/kaggle/working/dataset_stats.json", bundle / "dataset_stats.json")
    shutil.copy2(yaml_path, bundle / "data.yaml")
    pred_dir = Path("/kaggle/working/predictions")
    if pred_dir.is_dir():
        shutil.copytree(pred_dir, bundle / "predictions", dirs_exist_ok=True)
    shutil.copy2(best, "/kaggle/working/rover6_best.pt")
    shutil.make_archive("/kaggle/working/rover6_bundle", "zip", bundle)

    # Keep the Kaggle output listing tiny: downloaded artefacts only.
    for name in ("results.png", "confusion_matrix.png", "val_batch0_pred.jpg"):
        src = Path("/kaggle/working/runs/rover6") / name
        if src.is_file():
            shutil.copy2(src, bundle.parent / f"rover6_{name}")
    shutil.rmtree("/kaggle/working/rover6", ignore_errors=True)
    shutil.rmtree("/kaggle/working/runs", ignore_errors=True)
    shutil.rmtree("/kaggle/working/predictions", ignore_errors=True)
    log("DONE bundle: /kaggle/working/rover6_bundle.zip")
    log("DONE summary: " + json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
