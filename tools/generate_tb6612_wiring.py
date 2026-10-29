"""Code-defined TB6612FNG wiring schematic (schemdraw) - current firmware truth.

Draws power + signal chain for the FINAL build:
battery -> switch/fuse -> TB6612FNG VM/GND, Uno <-> TB6612 control (D5-D10),
HC-SR04 on D2/D3 powered from Arduino 5V/GND, ESP32 TX2 (GPIO17) one-way
to Uno D4 at 9600 8N1. Motor and battery runs are DIRECT wires - never a
breadboard (see reports/ROVER_BUILD_REPORT.md section 3).

Outputs: diagrams/tb6612_wiring.png (+.svg) and figures/tb6612_wiring.png (+.svg).

Run:  py -3.12 tools/generate_tb6612_wiring.py
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")

import schemdraw
import schemdraw.elements as elm

OUT_NAME = "tb6612_wiring"


def _block(title: str, side_pins, size=(6, 5), fs=9):
    """Box with pins: list of (anchor_name, visible_label, side)."""
    ic = elm.Ic(size=size)
    for pin_name, side, label in side_pins:
        ic = ic.pin(name=pin_name, side=side)
    ic = ic.label(title, fontsize=fs)
    return ic


def build():
    d = schemdraw.Drawing(unit=1.0)

    batt = _block(
        "2S LI-ION PACK\n7.4 V nominal\n(direct wires only)",
        [("P", "B", "+"), ("N", "B", "-")],
        size=(7, 5),
        fs=10,
    )
    d += batt.at((16, 13))

    sw = _block(
        "ROCKER SWITCH\n+ inline 3A fuse",
        [("A", "L", "in"), ("B", "R", "out")],
        size=(5, 3),
    )
    d += sw.at((-10, 14))

    driver = _block(
        "TB6612FNG\nDUAL MOSFET H-BRIDGE\n(stby -> 5V)",
        [
            ("VM", "T", "VM+batt"),
            ("VCC", "T", "VCC+stby"),
            ("AO1", "R", "AO1"),
            ("AO2", "R", "AO2"),
            ("BO1", "R", "BO1"),
            ("BO2", "R", "BO2"),
            ("GNDD", "B", "GND"),
            ("PWMA", "L", "PWMA"),
            ("AIN2", "L", "AIN2"),
            ("AIN1", "L", "AIN1"),
            ("STBY", "L", "STBY"),
            ("BIN1", "L", "BIN1"),
            ("BIN2", "L", "BIN2"),
            ("PWMB", "L", "PWMB"),
        ],
        size=(6, 16),
        fs=10,
    )
    d += driver.at((20, -10))

    uno = _block(
        "ARDUINO UNO R3\n(USB telemetry -> laptop)",
        [
            ("GND", "L", "GND"),
            ("V5", "L", "5V"),
            ("PWMA", "R", "D5-PWMA"),
            ("AIN1", "R", "D6-AIN1"),
            ("AIN2", "R", "D7-AIN2"),
            ("PWMB", "R", "D9-PWMB"),
            ("BIN1", "R", "D8-BIN1"),
            ("BIN2", "R", "D10-BIN2"),
            ("D2", "R", "D2-TRIG"),
            ("D3", "R", "D3-ECHO"),
            ("D4", "R", "D4-RX"),
        ],
        size=(7, 18),
        fs=10,
    )
    d += uno.at((0, -9))

    sonar = _block(
        "HC-SR04\n15 cm forward gate",
        [
            ("VCC", "B", "VCC"),
            ("TRIG", "B", "TRIG"),
            ("ECHO", "B", "ECHO"),
            ("GND", "B", "GND"),
        ],
        size=(10, 5),
        fs=10,
    )
    d += sonar.at((3, 14))

    esp = _block(
        "ESP32 DEVKIT V1\nWi-Fi pad 192.168.4.1",
        [("TX2", "R", "GPIO17 TX2"), ("GNDE", "R", "GND")],
        size=(6, 4),
        fs=10,
    )
    d += esp.at((-14, -16))

    ml = _block(
        "LEFT MOTOR\nTT 1:48",
        [("A1", "L", "+"), ("A2", "L", "-")],
        size=(5, 4),
    )
    d += ml.at((33, -6))

    mr = _block(
        "RIGHT MOTOR\nTT 1:48",
        [("B1", "L", "+"), ("B2", "L", "-")],
        size=(5, 4),
    )
    d += mr.at((33, -14))

    # ----- control lines: Uno -> TB6612 (labels carry the silk note)
    for a_name, b_name, note in (
        ("PWMA", "PWMA", ""),
        ("AIN1", "AIN1", "silk order!"),
        ("AIN2", "AIN2", ""),
        ("PWMB", "PWMB", "far end!"),
        ("BIN1", "BIN1", ""),
        ("BIN2", "BIN2", ""),
    ):
        ln = elm.Line().at(getattr(uno, a_name)).to(getattr(driver, b_name))
        d += ln
        if note:
            d += (
                elm.Label()
                .at(((getattr(uno, a_name)) + (getattr(driver, b_name))) * 0.5)
                .label(note, fontsize=7)
            )

    # ----- power lines into the driver
    d += elm.Line().at(sw.B).to(driver.VM).label("VM  7.4 V", fontsize=8)
    d += elm.Line().at(sw.A).to(batt.P).label("battery +", fontsize=8)
    d += elm.Line().at(batt.N).to(driver.GNDD).label("battery -", fontsize=8)
    d += (
        elm.Line()
        .at(uno.V5)
        .tox(driver.VCC)
        .toy(driver.VCC)
        .label("5 V logic + STBY", fontsize=8)
    )
    d += elm.Line().at(uno.GND).to(driver.GNDD).label("common GND", fontsize=8)

    # ----- outputs to motors
    d += elm.Line().at(driver.AO1).to(ml.A1)
    d += elm.Line().at(driver.AO2).to(ml.A2)
    d += elm.Line().at(driver.BO1).to(mr.B1)
    d += elm.Line().at(driver.BO2).to(mr.B2)

    # ----- sonar to Uno
    d += elm.Line().at(sonar.TRIG).to(uno.D2).label("TRIG", fontsize=8)
    d += elm.Line().at(sonar.ECHO).to(uno.D3).label("ECHO", fontsize=8)
    d += elm.Line().at(sonar.VCC).tox(uno.V5).toy(uno.V5).label("5 V", fontsize=8)
    d += (
        elm.Line()
        .at(sonar.GND)
        .tox(uno.GND)
        .toy(uno.GND)
        .label("GND (direct)", fontsize=8)
    )

    # ----- ESP32 one-way link
    d += (
        elm.Line()
        .at(esp.TX2)
        .tox(uno.D4)
        .toy(uno.D4)
        .label("one-way 9600 8N1\nD4 (3.3 V-safe)", fontsize=8)
    )
    d += elm.Line().at(esp.GNDE).tox(uno.GND).label("GND", fontsize=8)

    # ----- notes
    d += (
        elm.Label()
        .at((-10, 8))
        .label(
            "PIN SILK TRAPS (see report 3.2):\nAIN2 is left of AIN1\nPWMB is last, not next to STBY",
            fontsize=8,
        )
    )

    out_dirs = ("diagrams", "figures")
    for folder in out_dirs:
        os.makedirs(folder, exist_ok=True)
        d.save(os.path.join(folder, f"{OUT_NAME}.png"), dpi=220)
        d.save(os.path.join(folder, f"{OUT_NAME}.svg"))
    print("saved", f"{out_dirs[0]}/{OUT_NAME}.png + svg")


if __name__ == "__main__":
    build()
