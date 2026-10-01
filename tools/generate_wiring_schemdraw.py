"""Code-defined wiring schematic for the AI Visual Rover (schemdraw).

Draws the full power + signal chain as a regenerable schematic:
battery -> fuse -> switch -> LM2596 buck (5.00 V) and L298N 12 V feed,
Arduino UNO <-> L298N <-> TT motors, HC-SR04 on D11/D12, ESP32-CAM on
power wires only (video goes over Wi-Fi MJPEG to the laptop).

Pin map is firmware truth (arduino/rover_controller/rover_controller.ino and
docs/PINOUT.md): ENA=D5, IN1=D6, IN2=D7, IN3=D8, IN4=D9, ENB=D10,
TRIG=D11, ECHO=D12. D0/D1 are USB serial and are never wired.

Outputs: diagrams/wiring_schemdraw.{png,svg} and figures/wiring_schemdraw.{png,svg}.
"""

import os

import matplotlib

matplotlib.use("Agg")

import schemdraw
import schemdraw.elements as elm

OUT_NAME = "wiring_schemdraw"
OUT_DIRS = ("diagrams", "figures")
RAIL_5V = 15.5
BUS_GND = -14.0


def _block(title, side_pins, size=(6, 5), fs=9):
    ic = elm.Ic(size=size)
    for pin_name, side in side_pins:
        ic = ic.pin(name=pin_name, side=side)
    ic = ic.label(title, fontsize=fs)
    return ic


def _hv(d, a, b):
    """Wire from a to b: horizontal first, then vertical."""
    d += elm.Line().at(a).tox(b[0])
    d += elm.Line().toy(b[1])


def build():
    d = schemdraw.Drawing(unit=1.0)

    buck = _block(
        "LM2596 BUCK\nset 5.00 V",
        [("IN+", "T"), ("IN-", "L"), ("OUT-", "R"), ("OUT+", "R")],
        size=(6, 4),
    )
    d += buck.at((-18, -2))

    uno = _block(
        "ARDUINO UNO R3\nUSB serial -> laptop\nD0/D1: NEVER wire",
        [
            ("GND", "L"),
            ("5V", "L"),
            ("D5/ENA", "R"),
            ("D6/IN1", "R"),
            ("D7/IN2", "R"),
            ("D8/IN3", "R"),
            ("D9/IN4", "R"),
            ("D10/ENB", "R"),
            ("D12/ECHO", "R"),
            ("D11/TRIG", "R"),
        ],
        size=(7, 14),
        fs=10,
    )
    d += uno.at((0, 0))

    driver = _block(
        "L298N DUAL H-BRIDGE\nremove ENA/ENB jumpers",
        [
            ("ENA", "L"),
            ("IN1", "L"),
            ("IN2", "L"),
            ("IN3", "L"),
            ("IN4", "L"),
            ("ENB", "L"),
            ("12V", "T"),
            ("GND", "B"),
            ("OUT1", "R"),
            ("OUT2", "R"),
            ("OUT3", "R"),
            ("OUT4", "R"),
        ],
        size=(7, 12),
    )
    d += driver.at((12, -4))

    sonar = _block(
        "HC-SR04 (cm)",
        [("VCC", "B"), ("TRIG", "B"), ("ECHO", "B"), ("GND", "B")],
        size=(6, 5),
    )
    d += sonar.at((4, 16))

    cam = _block(
        "ESP32-CAM\n5V + GND only\nvideo: Wi-Fi MJPEG",
        [("5V", "L"), ("GND", "L")],
        size=(6, 5),
    )
    d += cam.at((-24, 16))

    motor_top = _block(
        "RIGHT MOTOR\nTT 1:48 (ch B)",
        [("+", "L"), ("-", "L")],
        size=(5, 4),
    )
    d += motor_top.at((24, 3))

    motor_bot = _block(
        "LEFT MOTOR\nTT 1:48 (ch A)",
        [("+", "L"), ("-", "L")],
        size=(5, 4),
    )
    d += motor_bot.at((24, -7))

    # --- power chain: battery -> fuse -> switch -> node N1 ---
    d += (
        elm.Battery()
        .at((-26, 26))
        .right()
        .label("2S Li-ion 7.4 V", loc="bottom", ofst=(-1, 0))
    )
    d += elm.Fuse().right().label("F1 3A", loc="top", ofst=(0, 1))
    d += elm.Switch().right().label("SW1 power", loc="top", ofst=(0, 0.3))
    n1 = d.here
    d += elm.Dot().at(n1)

    # battery negative: down the far left edge to the ground bus
    d += elm.Line().at((-26, 26)).tox(-30)
    d += elm.Line().toy(BUS_GND)

    # N1 -> L298N 12V (top pin): along the top row, then down
    _hv(d, n1, driver.absanchors["12V"])

    # N1 -> buck IN+ : down the far-left lane, then in
    p = buck.absanchors["IN+"]
    d += elm.Line().at(n1).toy(24)
    d += elm.Line().tox(-28)
    d += elm.Line().toy(p[1])
    d += elm.Line().tox(p[0])

    # buck IN- -> ground bus (around the left of the buck)
    p = buck.absanchors["IN-"]
    d += elm.Line().at(p).tox(-19.2)
    d += elm.Line().toy(BUS_GND)

    # --- 5 V rail (y=15.5): OUT+ riser -> cam feed -> UNO 5V -> sonar VCC ---
    out_p = buck.absanchors["OUT+"]
    d += elm.Line().at(out_p).toy(RAIL_5V)
    d += elm.Line().at((-25.5, RAIL_5V)).tox(sonar.absanchors["VCC"][0])
    d += elm.Dot().at((out_p[0], RAIL_5V))
    d += elm.Line().at(cam.absanchors["5V"]).tox(-25.5)
    d += elm.Line().toy(RAIL_5V)
    d += elm.Line().at(uno.absanchors["5V"]).toy(RAIL_5V)
    d += elm.Dot().at((uno.absanchors["5V"][0], RAIL_5V))

    # buck OUT- -> ground bus (straight down)
    d += elm.Line().at(buck.absanchors["OUT-"]).toy(BUS_GND)

    # --- signals: UNO <-> L298N (staggered lanes; order-preserving) ---
    fan = [
        ("D5/ENA", "ENA", 7.7),
        ("D6/IN1", "IN1", 8.16),
        ("D7/IN2", "IN2", 8.62),
        ("D8/IN3", "IN3", 9.08),
        ("D9/IN4", "IN4", 9.54),
        ("D10/ENB", "ENB", 10.0),
    ]
    for u_pin, d_pin, lane in fan:
        a = uno.absanchors[u_pin]
        b = driver.absanchors[d_pin]
        d += elm.Line().at(a).tox(lane)
        d += elm.Line().toy(b[1])
        d += elm.Line().tox(b[0])

    # --- signals: UNO D11/D12 -> HC-SR04 (two lanes up the right) ---
    a = uno.absanchors["D11/TRIG"]
    b = sonar.absanchors["TRIG"]
    d += elm.Line().at(a).tox(8.1)
    d += elm.Line().toy(14.6)
    d += elm.Line().tox(b[0])
    d += elm.Line().toy(b[1])
    a = uno.absanchors["D12/ECHO"]
    b = sonar.absanchors["ECHO"]
    d += elm.Line().at(a).tox(8.6)
    d += elm.Line().toy(RAIL_5V)
    d += elm.Line().tox(b[0])

    # --- L298N outputs -> motors (order-preserving lanes) ---
    mot_wires = [
        ("OUT4", motor_top, "-", 22.0),
        ("OUT3", motor_top, "+", 21.55),
        ("OUT2", motor_bot, "-", 21.1),
        ("OUT1", motor_bot, "+", 20.65),
    ]
    for out_pin, motor, m_pin, lane in mot_wires:
        a = driver.absanchors[out_pin]
        b = motor.absanchors[m_pin]
        d += elm.Line().at(a).tox(lane)
        d += elm.Line().toy(b[1])
        d += elm.Line().tox(b[0])

    # --- ground bus: every GND return drops to one line (star ground) ---
    gnd_runs = [
        (uno.absanchors["GND"], None),
        (buck.absanchors["IN-"], -19.2),
        (cam.absanchors["GND"], -27.0),
        (driver.absanchors["GND"], 16.5),
        (sonar.absanchors["GND"], 20.0),
    ]
    for tip, jog_x in gnd_runs:
        if jog_x is not None:
            d += elm.Line().at(tip).tox(jog_x)
        d += elm.Line().toy(BUS_GND)

    d += elm.Line().at((-30, BUS_GND)).tox(24)
    d += elm.Ground().at((-21, BUS_GND))
    for x in (-30.0, -27.0, -21.0, -19.2, -11.5, -0.5, 16.5, 20.0):
        d += elm.Dot().at((x, BUS_GND))

    # --- notes ---
    d += elm.Label(label="STAR GROUND - all GND returns meet here").at(
        (-10, BUS_GND - 3)
    )
    d += elm.Label(
        label="AI Visual Rover - wiring per docs/PINOUT.md + rover_controller.ino"
    ).at((-4, 30))

    return d


def main():
    d = build()
    for out_dir in OUT_DIRS:
        os.makedirs(out_dir, exist_ok=True)
        d.save(os.path.join(out_dir, OUT_NAME + ".png"))
        d.save(os.path.join(out_dir, OUT_NAME + ".svg"))
        print("[OK] Generated wiring schematic in", out_dir)


if __name__ == "__main__":
    main()
