"""Documentation consistency: links resolve and documented routes exist."""

from __future__ import annotations

import re

import pytest

from support import ROOT, read

MD_FILES = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md")), ROOT / "kaggle" / "README.md"]
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


@pytest.mark.parametrize("path", MD_FILES, ids=lambda p: p.name)
def test_relative_links_resolve(path):
    text = path.read_text(encoding="utf-8")
    for target in LINK.findall(text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        clean = target.split("#")[0].strip()
        if not clean:
            continue
        resolved = (path.parent / clean).resolve()
        assert resolved.exists(), f"{path.name}: broken link {target}"


def test_every_http_route_is_documented():
    sketch = read("firmware/esp32/wifi_bridge/wifi_bridge.ino")
    routes = set(re.findall(r'server\.on\("([^"]+)"', sketch))
    api = read("docs/API.md")
    for route in routes:
        assert f"`{route}" in api or route in api, f"route {route} missing from docs/API.md"


def test_makefile_targets_used_in_readme_exist():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    targets = set(re.findall(r"^([a-z][a-z0-9-]*):", makefile, re.MULTILINE))
    for target in ("test", "compile", "compile-uno", "compile-esp", "flash-uno", "flash-esp32", "smoke"):
        assert target in targets, f"Makefile missing {target}"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for used in re.findall(r"make ([a-z][a-z0-9-]*)", readme):
        assert used in targets or used in ("compile",), f"README uses missing target make {used}"


def test_wiring_doc_pins_match_firmware():
    wiring = read("docs/WIRING.md")
    expected = {
        "kPwma": "D5", "kAin1": "D6", "kAin2": "D7",
        "kBin1": "D8", "kBin2": "D10", "kPwmb": "D9",
        "kTrig": "D11", "kEcho": "D12",
        "kLinkRx": "D4", "kLinkTx": "A2",
        "kPinHeartbeat": "A5", "kPinEstop": "A1",
        "kPinBattery": "A0", "kPinFaultOut": "A4",
        "kRearTrig": "D2", "kRearEcho": "D3",
        "kEncoderLeft": "D2", "kEncoderRight": "D3",
    }
    for name, label in expected.items():
        assert re.search(rf"{name}\s*=\s*\d+", read("firmware/libraries/AIRoverCore/src/pins.h")), name
        assert label in wiring, f"{label} ({name}) not in WIRING.md"


def test_wiring_documents_the_hardening_hardware():
    wiring = read("docs/WIRING.md")
    for token in ("E-stop", "555", "100k", "47k", "GPIO13", "GPIO14", "CRC",
                  "encoder", "INT0", "OTA"):
        assert token in wiring, token


def test_api_documents_crc_and_uno_health():
    api = read("docs/API.md")
    for token in ("CRC-8", "*B1", "T,<state>", "uno", "429", "alive", "battery_mv",
                  "odometry", "OTA", "token", "401"):
        assert token in api, token


def test_bringup_covers_the_new_safety_tests():
    bringup = read("docs/BRINGUP.md")
    for token in ("E-stop", "BATTLOW", "CRC", "watchdog reset", "VBAT",
                  "encoder", "OTA", "calibrat"):
        assert token in bringup, token



def test_final_docs_exist():
    for name in ("docs/FMEA_v2.md", "docs/FINAL_DEMO.md", "CHANGELOG.md"):
        assert (ROOT / name).is_file(), name
    fmea = read("docs/FMEA_v2.md")
    for token in ("Stall", "E-stop", "CRC", "Severity", "Residual"):
        assert token in fmea, token
    demo = read("docs/FINAL_DEMO.md")
    for token in ("Pre-flight", "Demo", "Fallback", "Q&A"):
        assert token in demo, token


def test_readme_links_the_new_docs():
    readme = read("README.md")
    assert "docs/FMEA_v2.md" in readme
    assert "docs/FINAL_DEMO.md" in readme
    assert "simulator/virtual_rover.py" in readme


def test_api_doc_lists_all_telemetry_tokens():
    sketch = read("firmware/arduino/motion_safety/motion_safety.ino")
    api = read("docs/API.md")
    for token in ("BOOT:STOP", "DIST:", "ALERT:OBSTACLE", "ACT: PWMA="):
        assert token in sketch
        assert token in api, f"{token} missing from docs/API.md"


def test_config_documented_values_match_file():
    config = read("config/rover.json")
    assert '"left_bound": 0.33' in config
    assert '"right_bound": 0.66' in config
    assert '"stop_area": 0.28' in config
    assert "0.33" in read("docs/TRAINING.md") or "0.33" in read("README.md")
