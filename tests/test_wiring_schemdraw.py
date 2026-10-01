"""Guards: the wiring schematic is code-defined and matches firmware truth.

`tools/generate_wiring_schemdraw.py` draws the power + signal chain from the
pin map, and `reports/AI_Rover_Wiring_and_Breadboard.pdf` is the printed
reference built from the same numbers. Both rot away silently the moment a pin
changes in `arduino/rover_controller/rover_controller.ino`, so this test ties
the drawing, the firmware and the published PDF together.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_wiring_schemdraw.py"
FIRMWARE = ROOT / "arduino" / "rover_controller" / "rover_controller.ino"
PDF = ROOT / "reports" / "AI_Rover_Wiring_and_Breadboard.pdf"

OUTPUTS = (
    ROOT / "diagrams" / "wiring_schemdraw.png",
    ROOT / "diagrams" / "wiring_schemdraw.svg",
    ROOT / "figures" / "wiring_schemdraw.png",
    ROOT / "figures" / "wiring_schemdraw.svg",
)

EXPECTED_PINS = {
    "ENA": 5,
    "IN1": 6,
    "IN2": 7,
    "IN3": 8,
    "IN4": 9,
    "ENB": 10,
    "TRIG_PIN": 11,
    "ECHO_PIN": 12,
}

# schematic label (as printed on the UNO block) per firmware constant
SCHEMATIC_LABEL = {
    "TRIG_PIN": "TRIG",
    "ECHO_PIN": "ECHO",
}

_CONST_RE = re.compile(r"const\s+int\s+(\w+)\s*=\s*(\d+)\s*;")


def _firmware_pins() -> dict:
    return {
        m.group(1): int(m.group(2))
        for m in _CONST_RE.finditer(FIRMWARE.read_text(encoding="utf-8"))
    }


def test_schematic_outputs_exist_in_both_directories():
    for path in OUTPUTS:
        assert path.exists(), (
            f"missing schematic output: {path.name} in {path.parent.name}"
        )
        assert path.stat().st_size > 0, f"empty schematic output: {path}"
    png = OUTPUTS[0].read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "wiring PNG is not a PNG"
    svg = OUTPUTS[1].read_text(encoding="utf-8", errors="replace")
    assert "<svg" in svg, "wiring SVG has no <svg> root"
    assert OUTPUTS[0].read_bytes() == OUTPUTS[2].read_bytes(), (
        "diagrams/ and figures/ PNGs differ - one copy is stale"
    )


def test_generator_labels_match_firmware_pin_map():
    pins = _firmware_pins()
    for name, value in EXPECTED_PINS.items():
        assert pins.get(name) == value, (
            f"firmware {name} changed to {pins.get(name)}; update the schematic"
        )
    source = GENERATOR.read_text(encoding="utf-8")
    for name, value in EXPECTED_PINS.items():
        label = SCHEMATIC_LABEL.get(name, name)
        assert f"D{value}/{label}" in source, (
            f"schematic source has no D{value}/{label} label"
        )
    assert "D0/D1: NEVER wire" in source, "schematic must keep the USB-serial warning"


def test_generator_writes_both_output_directories():
    source = GENERATOR.read_text(encoding="utf-8")
    assert 'OUT_DIRS = ("diagrams", "figures")' in source, (
        "outputs must land in diagrams/ and figures/"
    )


def test_published_wiring_pdf_matches_the_schematic():
    if not PDF.exists():
        pytest.skip("reports/AI_Rover_Wiring_and_Breadboard.pdf not generated")
    pypdf = pytest.importorskip("pypdf", reason="pypdf not installed")
    reader = pypdf.PdfReader(str(PDF))
    assert len(reader.pages) >= 1
    text = reader.pages[0].extract_text() or ""
    assert "Wiring" in text and "Breadboard" in text, (
        "PDF is not the wiring/breadboard guide"
    )
    assert "PINOUT" in text, "PDF must state its pin source of truth"
