#!/usr/bin/env python3
"""Install a trained model bundle into the repo.

    python scripts/install_model.py /tmp/ai-rover-model/rover6_bundle.zip
    python scripts/install_model.py bundle.zip --openvino   # point config at OpenVINO
    python scripts/install_model.py bundle.zip --no-default # just extract

It extracts the bundle into models/, validates the archive paths (no zip-slip),
prints the metrics from val_summary.json, and optionally updates
config/rover.json -> "weights".
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

import _bootstrap  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "rover.json"


def _safe_members(archive: zipfile.ZipFile, destination: Path) -> list[zipfile.ZipInfo]:
    members = []
    dest = destination.resolve()
    for info in archive.infolist():
        if info.is_dir():
            continue
        target = (dest / info.filename).resolve()
        if not str(target).startswith(str(dest) + "/") and target != dest:
            raise ValueError(f"unsafe path in archive: {info.filename}")
        members.append(info)
    return members


def install_bundle(
    bundle: str | Path,
    models_dir: str | Path = ROOT / "models",
    config_path: str | Path | None = DEFAULT_CONFIG,
    set_default: bool = True,
    prefer_openvino: bool = False,
) -> dict:
    """Extract a Kaggle bundle, validate it, and optionally set the default weights."""
    bundle = Path(bundle)
    if not bundle.is_file():
        raise FileNotFoundError(bundle)
    models = Path(models_dir)
    models.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(bundle) as archive:
        names = [i.filename for i in archive.infolist()]
        if not any(n.endswith(".pt") for n in names):
            raise ValueError("bundle contains no .pt weights")
        archive.extractall(models, members=[i for i in _safe_members(archive, models)])

    # Prefer the checkpoint that belongs to *this* bundle, so installing
    # rover6 into a models/ that already has rover24 does not pick the wrong one.
    prefix = bundle.stem.replace("_bundle", "")
    weights = sorted(models.rglob(f"{prefix}*_best.pt"))
    if not weights:
        weights = sorted(models.rglob("*_best.pt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not weights:
        weights = sorted(models.rglob("best.pt"))
    if not weights:
        raise ValueError("no *_best.pt found after extraction")
    weight_path = weights[0]

    metrics: dict = {}
    summary = next(iter(sorted(models.rglob("val_summary.json"))), None)
    if summary is not None:
        metrics = json.loads(summary.read_text(encoding="utf-8"))

    # Ultralytics only detects an OpenVINO export if the folder ends with
    # "_openvino_model"; bundles ship it as "<prefix>_openvino".
    for folder in list(models.glob("*_openvino")):
        if folder.is_dir():
            target = folder.with_name(f"{folder.name}_model")
            if target.exists():
                import shutil as _shutil
                _shutil.rmtree(target)
            folder.rename(target)

    openvino = models / f"{prefix}_openvino_model"
    if not openvino.is_dir():
        openvino = next((p for p in models.rglob("*_openvino_model") if p.is_dir()), None)
    chosen = openvino if (prefer_openvino and openvino is not None) else weight_path

    updated = None
    if set_default and config_path is not None:
        config_file = Path(config_path)
        if config_file.is_file():
            data = json.loads(config_file.read_text(encoding="utf-8"))
            try:
                relative = chosen.resolve().relative_to(ROOT)
                data["weights"] = str(relative)
            except ValueError:
                data["weights"] = str(chosen)
            config_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            updated = data["weights"]

    return {
        "weights": str(chosen),
        "config_weights": updated,
        "metrics": metrics,
        "openvino": str(openvino) if openvino else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install a trained model bundle")
    parser.add_argument("bundle", help="rover*_bundle.zip from Kaggle")
    parser.add_argument("--models", default=str(ROOT / "models"))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--no-default", action="store_true", help="do not change config/rover.json")
    parser.add_argument("--openvino", action="store_true", help="default to the OpenVINO export")
    args = parser.parse_args(argv)

    try:
        result = install_bundle(
            args.bundle,
            models_dir=args.models,
            config_path=args.config,
            set_default=not args.no_default,
            prefer_openvino=args.openvino,
        )
    except (FileNotFoundError, ValueError, zipfile.BadZipFile) as exc:
        print(f"[MODEL] {exc}", file=sys.stderr)
        return 2

    print(f"[MODEL] weights : {result['weights']}")
    if result["openvino"]:
        print(f"[MODEL] openvino: {result['openvino']}")
    if result["config_weights"]:
        print(f"[MODEL] config  : {args.config} -> {result['config_weights']}")
    metrics = result["metrics"]
    if metrics:
        print(
            "[MODEL] metrics : "
            f"mAP50={metrics.get('mAP50')} mAP50-95={metrics.get('mAP50_95')} "
            f"P={metrics.get('precision')} R={metrics.get('recall')}"
        )
        if metrics.get("note"):
            print(f"[MODEL] note    : {metrics['note']}")
    print("[MODEL] next: python scripts/ai_video_server.py --dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
