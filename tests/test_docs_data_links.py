"""Data-link consistency: docs, generators, and figures vs. actual wiring.

Ground truth verified in code:
  * ``esp32/camera_stream/camera_stream.ino`` serves Wi-Fi MJPEG on ``/stream``
    (its ``Serial`` is debug-only) - there is no ESP32->Arduino UART.
  * ``software/hardware/arduino_serial.py`` is the only command link:
    laptop USB serial -> Arduino, 9600 baud, tokens ``F/B/L/R/S``.
  * Therefore the ESP32-CAM is wired to 5V + GND only, no level shifter is
    fitted, and Arduino D0/D1 stay free (USB serial).

Every doc/generator/figure must agree with that, so a future regeneration
cannot silently reintroduce the obsolete level-shifter UART link.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Docs that describe the wiring / pinout / data links or carry BOM + FMEA rows.
DESIGN_DOCS = [
    "docs/01_PROJECT_OVERVIEW.md",
    "docs/05_OBJECTIVES.md",
    "docs/08_HARDWARE_ARCHITECTURE.md",
    "docs/10_ESP32_AI_PIPELINE.md",
    "docs/21_CIRCUIT_CONNECTIONS.md",
    "docs/22_PIN_CONFIGURATION.md",
    "docs/28_FAILURE_ANALYSIS.md",
    "docs/31_BILL_OF_MATERIALS.md",
]

# Phrases that state the wired board-to-board UART link exists in this build.
FORBIDDEN_CLAIMS = [
    "Level Shifter HV",
    "Level Shifter LV",
    "via level shifter",
    "to level shifter",
    "Commands to UNO",
    "Telemetry Ingest from Arduino UNO",
    "UART Packet Dispatch",
    "Logic Level Shifting [MANDATORY]",
    "Bidirectional Logic Level Shifter",
    "Bidirectional MOSFET logic level shifter",
    "Mandatory bidirectional level shifter",
    "LOGIC LEVEL\nSHIFTER",
    "LEVEL SHIFTER",
]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_design_docs_do_not_claim_a_wired_esp32_uart_link():
    for rel in DESIGN_DOCS:
        text = read(rel)
        for claim in FORBIDDEN_CLAIMS:
            assert claim not in text, f"{rel} still claims {claim!r}"


def test_wiring_schedule_wires_esp32_power_only_and_keeps_d0_d1_free():
    doc = read("docs/21_CIRCUIT_CONNECTIONS.md")
    esp_rows = [
        line
        for line in doc.splitlines()
        if line.startswith("|") and "ESP32-CAM" in line
    ]
    assert esp_rows, "wiring schedule must contain ESP32-CAM rows"
    for row in esp_rows:
        assert re.search(r"\b5V\b|\bGND\b", row), f"non-power ESP32 wire: {row}"
    assert "Pin 0 (RX)" not in doc, "D0 must stay unwired (USB serial only)"
    assert "Pin 1 (TX)" not in doc, "D1 must stay unwired (USB serial only)"
    assert "DATA LINKS" in doc
    assert "Wi-Fi MJPEG" in doc and "USB serial" in doc


def test_pin_configuration_documents_the_host_usb_link():
    doc = read("docs/22_PIN_CONFIGURATION.md")
    assert "Laptop (USB Serial)" in doc, "D0/D1 host must be the laptop USB link"
    assert "Debug/flash UART - NOT WIRED" in doc, "ESP32 GPIO1/GPIO3 must be unwired"
    assert "Level Shifter" not in doc


def test_bom_contains_no_level_shifter_component():
    for rel in ("docs/31_BILL_OF_MATERIALS.md", "BOM.csv"):
        text = read(rel)
        assert "Logic Level Shifter" not in text, f"{rel} still buys a level shifter"
    assert "No Level Shifter Required" in read("docs/31_BILL_OF_MATERIALS.md")


def test_generators_cannot_reintroduce_the_uart_link():
    for rel in (
        "tools/generate_tables.py",
        "tools/generate_docs.py",
        "tools/create_bom.py",
        "tools/generate_diagrams.py",
        "tools/generate_figures.py",
    ):
        text = read(rel)
        for claim in FORBIDDEN_CLAIMS:
            assert claim not in text, f"{rel} would regenerate {claim!r}"
    # Regenerating the wiring schedule must keep the companion links too.
    tables = read("tools/generate_tables.py")
    assert "wiring_schemdraw.png" in tables
    assert "DATA LINKS" in tables


def test_figures_are_drawn_from_the_corrected_generators():
    for rel in (
        "tools/generate_diagrams.py",
        "tools/generate_figures.py",
    ):
        text = read(rel)
        assert "LAPTOP (HOST)" in text, f"{rel} should route links via the laptop"
