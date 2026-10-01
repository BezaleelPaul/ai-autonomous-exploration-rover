"""Download/cache primary model for offline inference.
Usage: python scripts/download_model.py [--model facebook/detr-resnet-50]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from software.utils.config_loader import load_config
from software.ai.model_manager import ensure_model, warmup

cfg = load_config("config/config.yaml")
model = (
    sys.argv[sys.argv.index("--model") + 1]
    if "--model" in sys.argv
    else cfg["ai"]["model_name"]
)
mdir = cfg["ai"].get("model_dir")
print(f"Ensuring {model} -> {mdir} ...")
ok, msg = ensure_model(model, mdir)
print(f"ensure: {ok} ({msg})")
if ok:
    ok2, msg2 = warmup(model, mdir, cfg["ai"].get("device", "cpu"))
    print(f"warmup: {ok2} ({msg2})")
sys.exit(0 if ok else 1)
