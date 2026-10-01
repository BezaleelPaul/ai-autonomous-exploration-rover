"""Smoke-test ESP32 stream. Usage: python scripts/test_camera.py [--mock]"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from software.utils.config_loader import load_config
from software.camera.esp32_stream import ESP32Stream

mock = "--mock" in sys.argv
cfg = load_config("config/config.yaml")
url = cfg["camera"]["esp32_url"]
s = ESP32Stream(url, mock=mock)
assert s.open(), "camera open failed"
for i in range(30):
    f = s.read()
    print(
        f"frame {i}: {'OK ' + str(f.shape) if f is not None else 'FAIL'} healthy={s.is_healthy()}"
    )
    if f is None:
        break
s.close()
print("camera test done")
