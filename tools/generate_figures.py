"""Technical Vector SVG Circuit Diagram Generator.

Generates high-precision, publication-grade SVG schematic conforming to Phase 6:
- Strict distinction between POWER, GROUND, and SIGNAL
- Verified pinouts for Arduino UNO, ESP32-CAM, L298N, HC-SR04, TT Motors, Buck Converter, and Battery
- Clear separation between Motor Power (7.4V unregulated) and Logic Power (5.0V regulated)
- Common Star Ground
"""

import os
import svgwrite


def generate_svg_circuit(output_path="figures/circuit_diagram.svg"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    dwg = svgwrite.Drawing(output_path, profile="full", size=("1200px", "800px"))

    # Background
    dwg.add(dwg.rect(insert=(0, 0), size=("100%", "100%"), fill="#ffffff"))

    # Title
    dwg.add(
        dwg.text(
            "Figure 6.3: Complete Hardware Circuit & Electrical Wiring Schematic",
            insert=(600, 40),
            text_anchor="middle",
            font_size="22px",
            font_family="Arial",
            font_weight="bold",
            fill="#111111",
        )
    )

    # Style definitions
    style_power = {"stroke": "#d32f2f", "stroke_width": 3, "fill": "none"}
    style_gnd = {"stroke": "#212121", "stroke_width": 3, "fill": "none"}
    style_signal = {"stroke": "#1565c0", "stroke_width": 2, "fill": "none"}
    style_motor = {"stroke": "#e65100", "stroke_width": 2.5, "fill": "none"}

    # Legend Box
    dwg.add(
        dwg.rect(
            insert=(880, 60),
            size=(290, 100),
            rx=5,
            ry=5,
            fill="#f8f9fa",
            stroke="#6c757d",
            stroke_width=1.5,
        )
    )
    dwg.add(
        dwg.text(
            "WIRING SCHEMATIC LEGEND",
            insert=(1025, 80),
            text_anchor="middle",
            font_size="13px",
            font_family="Arial",
            font_weight="bold",
        )
    )
    # Legend lines
    dwg.add(dwg.line(start=(900, 100), end=(940, 100), **style_power))
    dwg.add(
        dwg.text(
            "POWER: +7.4V / +5.0V Rail",
            insert=(950, 104),
            font_size="12px",
            font_family="Arial",
        )
    )
    dwg.add(dwg.line(start=(900, 122), end=(940, 122), **style_gnd))
    dwg.add(
        dwg.text(
            "COMMON GROUND (GND)",
            insert=(950, 126),
            font_size="12px",
            font_family="Arial",
        )
    )
    dwg.add(dwg.line(start=(900, 144), end=(940, 144), **style_signal))
    dwg.add(
        dwg.text(
            "SIGNAL / PWM / UART (TTL)",
            insert=(950, 148),
            font_size="12px",
            font_family="Arial",
        )
    )

    # Helper function to create component box
    def draw_box(x, y, w, h, title, subtitle, bg="#ffffff", border="#333333"):
        dwg.add(
            dwg.rect(
                insert=(x, y),
                size=(w, h),
                rx=8,
                ry=8,
                fill=bg,
                stroke=border,
                stroke_width=2,
            )
        )
        dwg.add(
            dwg.text(
                title,
                insert=(x + w / 2, y + 25),
                text_anchor="middle",
                font_size="15px",
                font_family="Arial",
                font_weight="bold",
                fill=border,
            )
        )
        if subtitle:
            dwg.add(
                dwg.text(
                    subtitle,
                    insert=(x + w / 2, y + 42),
                    text_anchor="middle",
                    font_size="11px",
                    font_family="Arial",
                    fill="#555555",
                )
            )

    # 1. Battery Pack (2S Li-ion 7.4V)
    draw_box(
        40,
        180,
        160,
        140,
        "BATTERY PACK",
        "2S Li-ion (7.4V - 8.4V)",
        "#fffde7",
        "#f57f17",
    )
    dwg.add(
        dwg.text(
            "(+) 7.4V Terminal",
            insert=(120, 260),
            text_anchor="middle",
            font_size="12px",
            font_family="Arial",
            font_weight="bold",
            fill="#d32f2f",
        )
    )
    dwg.add(
        dwg.text(
            "(-) GND Terminal",
            insert=(120, 290),
            text_anchor="middle",
            font_size="12px",
            font_family="Arial",
            font_weight="bold",
            fill="#212121",
        )
    )

    # 2. Buck Converter (LM2596)
    draw_box(
        260,
        180,
        170,
        140,
        "BUCK CONVERTER",
        "LM2596 (7.4V -> 5.0V / 3A)",
        "#e8f5e9",
        "#2e7d32",
    )
    dwg.add(
        dwg.text(
            "IN+ (7.4V)     OUT+ (5.0V)",
            insert=(345, 260),
            text_anchor="middle",
            font_size="11px",
            font_family="Arial",
        )
    )
    dwg.add(
        dwg.text(
            "IN- (GND)      OUT- (GND)",
            insert=(345, 290),
            text_anchor="middle",
            font_size="11px",
            font_family="Arial",
        )
    )

    # 3. ESP32-CAM
    draw_box(
        500,
        150,
        220,
        200,
        "ESP32-CAM",
        "Edge Perception (3.3V Core)",
        "#e1f5fe",
        "#0288d1",
    )
    dwg.add(
        dwg.text(
            "5V (Power In)    GND",
            insert=(610, 220),
            text_anchor="middle",
            font_size="12px",
            font_family="monospace",
        )
    )
    dwg.add(
        dwg.text(
            "No data wires: video leaves",
            insert=(610, 260),
            text_anchor="middle",
            font_size="11px",
            font_family="monospace",
        )
    )
    dwg.add(
        dwg.text(
            "as Wi-Fi MJPEG to laptop",
            insert=(610, 290),
            text_anchor="middle",
            font_size="11px",
            font_family="monospace",
        )
    )
    dwg.add(
        dwg.text(
            "OV2640 DVP Bus (Internal)",
            insert=(610, 320),
            text_anchor="middle",
            font_size="11px",
            font_family="monospace",
        )
    )

    # 4. Laptop (host) - receives Wi-Fi video, sends USB serial to the Arduino
    draw_box(
        780,
        180,
        160,
        140,
        "LAPTOP (HOST)",
        "Wi-Fi in / USB serial out",
        "#f3e5f5",
        "#7b1fa2",
    )
    dwg.add(
        dwg.text(
            "Wi-Fi MJPEG <- ESP32",
            insert=(860, 260),
            text_anchor="middle",
            font_size="11px",
            font_family="monospace",
        )
    )
    dwg.add(
        dwg.text(
            "USB serial -> Arduino",
            insert=(860, 290),
            text_anchor="middle",
            font_size="11px",
            font_family="monospace",
        )
    )

    # 5. Arduino UNO R3
    draw_box(
        740,
        380,
        240,
        340,
        "ARDUINO UNO R3",
        "Supervisor & Safety (5.0V TTL)",
        "#e8f5e9",
        "#1b5e20",
    )
    pins = [
        "5V (Logic In)      GND",
        "Pin 0 (RX) <- Laptop USB",
        "Pin 1 (TX) -> Laptop USB",
        "Pin 5 (ENA PWM) -> L298N",
        "Pin 6 (IN1)     -> L298N",
        "Pin 7 (IN2)     -> L298N",
        "Pin 8 (IN3)     -> L298N",
        "Pin 9 (IN4)     -> L298N",
        "Pin 10 (ENB PWM)-> L298N",
        "Pin 11 (TRIG)   -> HC-SR04",
        "Pin 12 (ECHO)   <- HC-SR04",
    ]
    for idx, p in enumerate(pins):
        dwg.add(
            dwg.text(
                p,
                insert=(760, 450 + idx * 24),
                font_size="11px",
                font_family="monospace",
                fill="#1b5e20",
            )
        )

    # 6. L298N Dual H-Bridge Driver
    draw_box(
        380,
        420,
        240,
        300,
        "L298N DRIVER",
        "Dual Full-Bridge Motor Controller",
        "#fff3e0",
        "#e65100",
    )
    l298_labels = [
        "12V Terminal <- Battery (+7.4V)",
        "GND Terminal <- Common Ground",
        "ENA / ENB   <- PWM 5 / 10",
        "IN1 - IN4   <- Pins 6 - 9",
        "OUT1 / OUT2 -> LEFT MOTOR",
        "OUT3 / OUT4 -> RIGHT MOTOR",
    ]
    for idx, lb in enumerate(l298_labels):
        dwg.add(
            dwg.text(
                lb,
                insert=(400, 490 + idx * 30),
                font_size="11px",
                font_family="monospace",
                fill="#bf360c",
            )
        )

    # 7. Left Motor & Right Motor
    draw_box(
        40,
        420,
        180,
        120,
        "LEFT MOTOR",
        "TT DC Gear Motor (1:48, 6V)",
        "#efebe9",
        "#4e342e",
    )
    dwg.add(
        dwg.text(
            "Decoupled w/ 0.1uF",
            insert=(130, 490),
            text_anchor="middle",
            font_size="11px",
            font_family="Arial",
        )
    )

    draw_box(
        40,
        580,
        180,
        120,
        "RIGHT MOTOR",
        "TT DC Gear Motor (1:48, 6V)",
        "#efebe9",
        "#4e342e",
    )
    dwg.add(
        dwg.text(
            "Decoupled w/ 0.1uF",
            insert=(130, 650),
            text_anchor="middle",
            font_size="11px",
            font_family="Arial",
        )
    )

    # 8. HC-SR04 Ultrasonic Sensor
    draw_box(
        1020, 480, 150, 180, "HC-SR04", "Front Ranging (40 kHz)", "#e0f2f1", "#00796b"
    )
    dwg.add(
        dwg.text(
            "VCC -> 5V Logic",
            insert=(1095, 545),
            text_anchor="middle",
            font_size="11px",
            font_family="monospace",
        )
    )
    dwg.add(
        dwg.text(
            "GND -> Common",
            insert=(1095, 575),
            text_anchor="middle",
            font_size="11px",
            font_family="monospace",
        )
    )
    dwg.add(
        dwg.text(
            "TRIG <- Pin 11",
            insert=(1095, 605),
            text_anchor="middle",
            font_size="11px",
            font_family="monospace",
        )
    )
    dwg.add(
        dwg.text(
            "ECHO -> Pin 12",
            insert=(1095, 635),
            text_anchor="middle",
            font_size="11px",
            font_family="monospace",
        )
    )

    # Common Star Ground Rail across bottom
    dwg.add(
        dwg.rect(
            insert=(40, 750), size=(1130, 20), rx=4, ry=4, fill="#212121", stroke="none"
        )
    )
    dwg.add(
        dwg.text(
            "COMMON STAR GROUND BUS (0V REFERENCE) — ALL GROUNDS INTERCONNECTED AT SINGLE CHASSIS JUNCTION",
            insert=(605, 764),
            text_anchor="middle",
            font_size="11px",
            font_family="Arial",
            font_weight="bold",
            fill="#ffffff",
        )
    )

    # Wiring Connections
    # Battery to Buck IN
    dwg.add(dwg.line(start=(200, 255), end=(260, 255), **style_power))
    # Battery to L298N 12V terminal
    dwg.add(dwg.path(d="M 200,240 L 230,240 L 230,450 L 380,450", **style_power))

    # Buck 5V Out to ESP32 and Arduino
    dwg.add(dwg.path(d="M 430,255 L 500,255", **style_power))
    dwg.add(dwg.path(d="M 430,255 L 460,255 L 460,390 L 740,390", **style_power))

    # ESP32 -(Wi-Fi MJPEG: no physical wire)-> Laptop, Laptop -USB serial- Arduino
    dwg.add(
        dwg.line(
            start=(720, 260), end=(780, 260), stroke_dasharray="6,4", **style_signal
        )
    )
    dwg.add(
        dwg.line(
            start=(720, 290), end=(780, 290), stroke_dasharray="6,4", **style_signal
        )
    )
    dwg.add(
        dwg.text(
            "Wi-Fi MJPEG (wireless)",
            insert=(750, 248),
            text_anchor="middle",
            font_size="9px",
            font_family="Arial",
            fill="#1565c0",
        )
    )
    dwg.add(dwg.path(d="M 940,260 L 960,260 L 960,470 L 940,470", **style_signal))
    dwg.add(dwg.path(d="M 940,290 L 970,290 L 970,500 L 940,500", **style_signal))
    dwg.add(
        dwg.text(
            "USB serial 9600",
            insert=(1012, 400),
            font_size="9px",
            font_family="Arial",
            fill="#1565c0",
        )
    )

    # Arduino to L298N Signals
    dwg.add(dwg.path(d="M 740,530 L 620,530", **style_signal))
    dwg.add(dwg.path(d="M 740,560 L 620,560", **style_signal))

    # L298N to Motors
    dwg.add(dwg.line(start=(380, 480), end=(220, 480), **style_motor))
    dwg.add(dwg.line(start=(380, 640), end=(220, 640), **style_motor))

    # Arduino to HC-SR04
    dwg.add(dwg.line(start=(980, 605), end=(1020, 605), **style_signal))
    dwg.add(dwg.line(start=(980, 635), end=(1020, 635), **style_signal))

    dwg.save()

    # Copy to docs/figures
    os.makedirs("docs/figures", exist_ok=True)
    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()
    with open("docs/figures/circuit_diagram.svg", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[OK] Generated SVG circuit diagram: {output_path}")


if __name__ == "__main__":
    generate_svg_circuit()
