"""Smoke-test Arduino serial. Usage: python scripts/test_serial.py [--mock] [PORT]"""

import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from software.utils.config_loader import load_config
from software.hardware.arduino_serial import ArduinoSerial

mock = "--mock" in sys.argv
cfg = load_config("config/config.yaml")
port = (
    sys.argv[-1]
    if len(sys.argv) > 1 and "COM" in sys.argv[-1].upper() or "/dev" in sys.argv[-1]
    else cfg["serial"]["port"]
)
a = ArduinoSerial(port, cfg["serial"]["baud_rate"], mock=mock)
print("connect:", a.connect())
for cmd in ["S", "F", "S", "L", "S"]:
    print(cmd, "->", a.send(cmd))
    time.sleep(0.5)
    print("  telemetry:", a.telemetry)
a.disconnect()
print("serial test done")
