"""MVP purchase list (Word) generator.

Output: reports/AI_Rover_MVP_Purchase_List.docx

Scope: the MVP hardware buy-list in Indian Rupees (kit + separate power
route decided 2026-09-27). Prices are Indian online-market estimates.
Regenerate with:  py -3.12 tools/generate_mvp_purchase_docx.py
"""

import os
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "reports", "AI_Rover_MVP_Purchase_List.docx")

REQUIRED = [
    (
        "2WD chassis kit",
        "1",
        "1,000 - 1,300",
        "Robokreeda / Robu.in / Amazon.in",
        "Plate + 2x TT motors (1:48) + 2x 65mm wheels + caster + "
        "standoffs + L298N driver. ORDER FIRST (ships slowest).",
    ),
    (
        "Arduino UNO R3 (CH340 clone) + USB-B cable",
        "1",
        "400 - 600",
        "Robu.in / Probots / Amazon.in",
        "Clone is enough; official board not needed. Cable usually included.",
    ),
    (
        "ESP32-CAM AI-Thinker + OV2640",
        "2",
        "500 - 700",
        "Robu.in / Amazon.in",
        "Buy a SPARE - flashing/bricking is common. Wi-Fi video only.",
    ),
    (
        "HC-SR04 ultrasonic sensor",
        "1",
        "0 - 120",
        "Often already in the kit",
        "Emergency stop at <15 cm. NEVER skip - it is safety layer 1.",
    ),
    (
        "LM2596 buck converter (7-24V in -> 5V/3A out)",
        "1",
        "90 - 150",
        "Robu.in / Amazon.in",
        "Clean 5 V logic rail; keeps motors electrically separate.",
    ),
    (
        "2S 18650 Li-ion pack 7.4 V / 2600 mAh, BMS + charger",
        "1",
        "900 - 1,300",
        "Amazon.in / battery supplier",
        "Lithium ships slowest - ORDER IN WEEK 1. Add ~400-600 if the "
        "charger is sold separately.",
    ),
    (
        "2-slot 18650 holder + rocker switch + 3 A fuse",
        "1",
        "150 - 250",
        "Electronics distributor",
        "Master power switch + overcurrent protection (lab safety rule).",
    ),
    (
        "Jumper wires (M-M, M-F, 40-pin sets) + M3 standoffs",
        "1 set",
        "250 - 350",
        "Robu.in / Amazon.in",
        "Full wiring schedule: docs/21_CIRCUIT_CONNECTIONS.md.",
    ),
]

OPTIONAL = [
    (
        "TowerPro SG90 micro servo",
        "1",
        "100 - 150",
        "Stage 4+",
        "Only for the optional 360-degree panoramic scan extension.",
    ),
    (
        "Spare 18650 cells / second battery pack",
        "1",
        "600 - 900",
        "If runtime is too short",
        "Buy only after the first runtime measurement.",
    ),
]

NOT_NEEDED = [
    "Logic level shifter - the build has NO wired ESP32-to-Arduino UART "
    "(ESP32 is power-only: 5 V + GND; video via Wi-Fi, commands via "
    "laptop USB serial).",
    "Bluetooth module (HC-05/HC-06) - unused; links are Wi-Fi MJPEG and USB serial.",
    "Official (genuine) Arduino board - the CH340 clone is sufficient.",
    "Extra breadboards - the design wires point-to-point per the schedule.",
]

TOTALS = [
    ("Parts subtotal (required)", "INR 3,300 - 4,800 (typical ~3,900)"),
    ("Shipping (2-3 orders) + 10-15% spares", "INR 500 - 700"),
    ("MVP BUDGET TO KEEP READY", "INR 4,000 - 5,500"),
    ("Optional extras (servo, spare pack)", "+ INR 700 - 1,050 later"),
]

WHERE = [
    ("Robu.in, Robokits India, Probots.co.in", "Electronics, boards, sensors"),
    ("Amazon.in", "Chassis kits, battery packs, wire sets"),
    (
        "IndiaMart / local electronics market",
        "Cells, chargers, fuse holders (cheapest)",
    ),
]

ORDER_SEQUENCE = [
    "Battery pack (+ charger) first - courier restrictions on lithium "
    "make it the slowest item.",
    "Chassis kit second - it contains the motors, wheels, caster and L298N driver.",
    "Everything else same week - all are in-stock items.",
]

CHECKLIST = [
    "Every required line received and checked against the table",
    "Battery pack charges to 8.4 V and the switch cuts power",
    "Buck output measured at 5.0 V before connecting any board",
    "Two ESP32-CAM boards present (one is the spare)",
]


def _heading(doc, text, level):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x0D, 0x47, 0xA1)
    return h


def _table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    hdr = t.rows[0].cells
    for i, htext in enumerate(headers):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        run = p.add_run(htext)
        run.bold = True
        run.font.size = Pt(9)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(val))
            run.font.size = Pt(9)
    return t


def build(output_path=OUTPUT):
    doc = Document()

    # Title block
    title = doc.add_heading("AI Visual Smart Rover - MVP Purchase List", level=0)
    for run in title.runs:
        run.font.color.rgb = RGBColor(0x0D, 0x47, 0xA1)
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub.add_run(
        "Kit + separate power route  |  All prices in INR (Indian online "
        "market estimates, Sep 2026)  |  Generated 2026-09-27"
    )
    run.italic = True
    run.font.size = Pt(9)

    doc.add_paragraph(
        "MVP = drive, see, decide, stop safely. Nothing beyond that: no "
        "servo, no second battery, no extras. The full project BOM is "
        "documented in docs/31_BILL_OF_MATERIALS.md; this document is the "
        "shopping list to start and finish the physical build."
    )

    # Budget summary
    _heading(doc, "1. Budget Summary", level=1)
    _table(doc, ["Item", "Amount (INR)"], TOTALS)

    # Required
    _heading(doc, "2. Buy Now - Required for MVP", level=1)
    _table(
        doc,
        ["Component", "Qty", "Est. price (INR)", "Where", "Notes"],
        REQUIRED,
    )
    p = doc.add_paragraph()
    r = p.add_run(
        "Rule: never power the motors from the Arduino 5V pin - motors take "
        "raw battery via the L298N, logic takes the buck's 5 V rail."
    )
    r.bold = True
    r.font.size = Pt(9)

    # Optional
    _heading(doc, "3. Buy Later - Optional", level=1)
    _table(
        doc,
        ["Component", "Qty", "Est. price (INR)", "When", "Notes"],
        OPTIONAL,
    )

    # Not needed
    _heading(doc, "4. Do NOT Buy (saves money)", level=1)
    for item in NOT_NEEDED:
        doc.add_paragraph(item, style="List Bullet")

    # Ordering
    _heading(doc, "5. Ordering Sequence", level=1)
    for i, step in enumerate(ORDER_SEQUENCE, start=1):
        doc.add_paragraph("%d. %s" % (i, step), style="List Number")

    # Where
    _heading(doc, "6. Where to Buy", level=1)
    _table(doc, ["Source", "Best for"], WHERE)

    # Checklist
    _heading(doc, "7. Receiving Checklist", level=1)
    for item in CHECKLIST:
        doc.add_paragraph("[  ] " + item, style="List Bullet")

    _heading(doc, "8. Next Step After Buying", level=1)
    doc.add_paragraph(
        "Stage 1 (bare drive): wire per docs/21_CIRCUIT_CONNECTIONS.md, "
        "flash with arduino-cli upload --fqbn arduino:avr:uno -p COMx "
        "arduino/rover_controller, then run python -m software.main. "
        "Gate: motors obey F/B/L/R/S and stop within 3.6 s when serial "
        "goes silent.",
        style="List Bullet",
    )

    doc.save(output_path)
    print("[OK] Generated MVP purchase list: %s" % output_path)
    return output_path


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    build(sys.argv[1] if len(sys.argv) > 1 else OUTPUT)
