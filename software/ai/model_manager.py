"""Model download / cache / warmup helper (offline-first after initial setup).

Primary model: facebook/detr-resnet-50, cached under models/<slug>.
After first download, inference works offline (HF_HUB_OFFLINE=1 / local_files_only).
"""

from __future__ import annotations

import os
from pathlib import Path

PRIMARY_MODEL = "facebook/detr-resnet-50"
# Lightweight swap-in candidates (no code change needed — same interface):
#   "hustvl/yolos-tiny"  (~30M params, faster CPU)
#   "PekingU/rtdetr_r50vd" (RT-DETR, needs ultralytics/transformers support)


def cache_dir_for(model_name: str, base: str = "models") -> Path:
    slug = model_name.split("/")[-1]
    return Path(base) / slug


def ensure_model(
    model_name: str = PRIMARY_MODEL, model_dir: str | None = None
) -> tuple[bool, str]:
    """Download model to local dir if missing; verify offline cache otherwise.
    Returns (available, message). Never raises."""
    try:
        from huggingface_hub import snapshot_download

        target = Path(model_dir) if model_dir else cache_dir_for(model_name)
        # 1. explicit local dir already populated?
        if target.exists() and any(target.iterdir()):
            return True, f"cached at {target}"
        # 2. HF cache hit (offline check)?
        try:
            snapshot_download(model_name, local_files_only=True)
            # populate explicit dir for reproducibility
            target.mkdir(parents=True, exist_ok=True)
            snapshot_download(model_name, local_dir=str(target))
            return True, f"cached at {target}"
        except Exception:
            pass
        # 3. network download (first-time setup)
        target.mkdir(parents=True, exist_ok=True)
        snapshot_download(model_name, local_dir=str(target))
        return True, f"downloaded to {target}"
    except Exception as e:
        return False, str(e)


def warmup(
    model_name: str = PRIMARY_MODEL, model_dir: str | None = None, device: str = "cpu"
) -> tuple[bool, str]:
    """Load processor+model once to prove offline inference path works."""
    try:
        from software.ai.detector import HFDetector

        d = HFDetector(model_name, 0.5, [], device, model_dir)
        ok = d.load()
        return ok, "ready" if ok else (d.load_error or "load failed")
    except Exception as e:
        return False, str(e)


def offline_env() -> dict:
    return {
        "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE", "0"),
        "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE", "0"),
    }
