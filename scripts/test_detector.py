"""Smoke-test detector. Usage: python scripts/test_detector.py [--mock]"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from software.utils.config_loader import load_config
from software.ai.detector import create_detector

cfg = load_config("config/config.yaml")
if "--mock" in sys.argv:
    cfg["ai"]["backend"] = "mock"
det = create_detector(cfg)
frame = np.zeros((480, 640, 3), dtype=np.uint8)
dets = det.detect(frame)
print(f"backend={type(det).__name__} detections={len(dets)}")
for d in dets:
    print(" ", d.to_dict())
print("detector test done")
