"""Deterministic Diagram and Technical Illustration Generator for AI Visual Rover.

Generates high-resolution (300 DPI), publication-quality vector and raster figures
for academic and technical documentation without using generative image hallucinations.
All diagrams follow strict electrical, kinematic, and architectural specifications.
"""

import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.path import Path
import numpy as np


def setup_canvas(width=10, height=6, dpi=300):
    fig, ax = plt.subplots(figsize=(width, height), dpi=dpi)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def save_figure(fig, filename, dirs=("diagrams", "figures", "docs/figures")):
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        fig.savefig(
            os.path.join(d, filename), dpi=300, bbox_inches="tight", facecolor="white"
        )
    plt.close(fig)
    print(f"[OK] Generated diagram: {filename}")


# ---------------------------------------------------------------------------
# 01. System Architecture
# ---------------------------------------------------------------------------
def gen_01_system_architecture():
    fig, ax = setup_canvas(11, 7)
    ax.text(
        50,
        95,
        "Figure 5.1: Distributed Edge-Intelligence Rover System Architecture",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
        color="#111111",
    )

    # Laptop box (Dev only)
    ax.add_patch(
        patches.FancyBboxPatch(
            (4, 60),
            22,
            26,
            boxstyle="round,pad=1.0",
            fc="#f8f9fa",
            ec="#6c757d",
            ls="--",
            lw=1.5,
        )
    )
    ax.text(
        15,
        82,
        "DEVELOPMENT / TELEMETRY\n(LAPTOP / WORKSTATION)",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#495057",
    )
    ax.text(
        15,
        71,
        "- Telemetry Dashboard\n- Calibration Scripts\n- Flash / OTA Firmware\n- Off-line Benchmarking",
        ha="center",
        fontsize=8,
        color="#6c757d",
    )
    ax.text(
        15,
        62,
        "[NOT REQUIRED FOR AUTONOMY]",
        ha="center",
        fontsize=7.5,
        fontweight="bold",
        color="#dc3545",
    )

    # ESP32 Box (Edge Perception)
    ax.add_patch(
        patches.FancyBboxPatch(
            (35, 52), 28, 36, boxstyle="round,pad=1.2", fc="#e8f4f8", ec="#0288d1", lw=2
        )
    )
    ax.text(
        49,
        84,
        "PERCEPTION COPROCESSOR\n(ESP32-CAM / ESP32-S3)",
        ha="center",
        fontsize=10,
        fontweight="bold",
        color="#01579b",
    )
    ax.text(
        37,
        73,
        "• OV2640 Image Capture\n• Visual Preprocessing (CLAHE)\n• TinyML / Centroid Detection\n• Target Position Estimation\n• Navigation State Machine",
        ha="left",
        fontsize=8.5,
        color="#0d47a1",
    )
    ax.text(
        49,
        55,
        "Edge Intelligence Subsystem",
        ha="center",
        fontsize=8,
        style="italic",
        color="#0288d1",
    )

    # Arduino UNO Box (Safety & Actuation)
    ax.add_patch(
        patches.FancyBboxPatch(
            (72, 52), 25, 36, boxstyle="round,pad=1.2", fc="#e8f5e9", ec="#2e7d32", lw=2
        )
    )
    ax.text(
        84.5,
        84,
        "SAFETY & ACTUATION SUPERVISOR\n(ARDUINO UNO R3)",
        ha="center",
        fontsize=9.5,
        fontweight="bold",
        color="#1b5e20",
    )
    ax.text(
        74,
        72,
        "• Command Validation\n• Hardware Watchdog (3s)\n• HC-SR04 Emergency Cutoff\n• 2-Channel PWM Generation\n• Low-level Direction Logic",
        ha="left",
        fontsize=8.5,
        color="#1b5e20",
    )
    ax.text(
        84.5,
        55,
        "Hardware Safety Barrier",
        ha="center",
        fontsize=8,
        style="italic",
        color="#2e7d32",
    )

    # Drivetrain & Motors
    ax.add_patch(
        patches.FancyBboxPatch(
            (72, 8),
            25,
            34,
            boxstyle="round,pad=1.0",
            fc="#fff3e0",
            ec="#e65100",
            lw=1.8,
        )
    )
    ax.text(
        84.5,
        38,
        "DRIVETRAIN & ACTUATORS",
        ha="center",
        fontsize=10,
        fontweight="bold",
        color="#bf360c",
    )
    ax.text(
        74,
        27,
        "• L298N Dual H-Bridge Driver\n• Dual DC TT Gear Motors\n• Left & Right Drive Wheels\n• Open-loop PWM Differential",
        ha="left",
        fontsize=8.5,
        color="#bf360c",
    )

    # Ultrasonic Sensor
    ax.add_patch(
        patches.FancyBboxPatch(
            (35, 12),
            28,
            28,
            boxstyle="round,pad=1.0",
            fc="#f3e5f5",
            ec="#7b1fa2",
            lw=1.8,
        )
    )
    ax.text(
        49,
        36,
        "OBSTACLE DETECTION SENSOR",
        ha="center",
        fontsize=9.5,
        fontweight="bold",
        color="#4a148c",
    )
    ax.text(
        37,
        25,
        "• HC-SR04 Front Ultrasonic\n• 40 kHz Acoustic Ranging\n• 15 cm Hardware Stop Latch\n• Independent Range Overrides",
        ha="left",
        fontsize=8.5,
        color="#4a148c",
    )

    # Interconnect Arrows
    # Laptop <-> ESP32 (Wi-Fi MJPEG video + telemetry)
    ax.annotate(
        "",
        xy=(35, 75),
        xytext=(26, 75),
        arrowprops=dict(arrowstyle="<->", color="#6c757d", ls="--", lw=1.5),
    )
    ax.text(
        30.5,
        78.5,
        "Wi-Fi MJPEG\nvideo + telemetry",
        ha="center",
        fontsize=7,
        color="#6c757d",
    )

    # No board-to-board wire: commands/telemetry use laptop USB serial -> Arduino
    ax.text(
        67.5,
        74,
        "no wired\nboard-to-board\nlink",
        ha="center",
        fontsize=7,
        style="italic",
        color="#c62828",
    )
    ax.annotate(
        "",
        xy=(15, 45),
        xytext=(15, 60),
        arrowprops=dict(arrowstyle="->", color="#0288d1", lw=2.0, ls="--"),
    )
    ax.annotate(
        "",
        xy=(78, 45),
        xytext=(15, 45),
        arrowprops=dict(arrowstyle="<->", color="#0288d1", lw=2.0, ls="--"),
    )
    ax.annotate(
        "",
        xy=(78, 52),
        xytext=(78, 45),
        arrowprops=dict(arrowstyle="<->", color="#0288d1", lw=2.0, ls="--"),
    )
    ax.text(
        46,
        47,
        "USB Serial 9600 baud: commands 'F','B','L','R','S' ->  <- telemetry 'DIST:','STATUS:'",
        ha="center",
        fontsize=7.2,
        fontweight="bold",
        color="#0288d1",
    )

    # Arduino -> L298N
    ax.annotate(
        "",
        xy=(84.5, 42),
        xytext=(84.5, 52),
        arrowprops=dict(arrowstyle="->", color="#d84315", lw=2.5),
    )
    ax.text(
        88, 47, "PWM + DIR", ha="left", fontsize=8, fontweight="bold", color="#d84315"
    )

    # HC-SR04 -> Arduino
    ax.annotate(
        "",
        xy=(72, 26),
        xytext=(63, 26),
        arrowprops=dict(arrowstyle="->", color="#7b1fa2", lw=2.0),
    )
    ax.text(67.5, 28, "Trig / Echo", ha="center", fontsize=8, color="#7b1fa2")

    save_figure(fig, "01_system_architecture.png")


# ---------------------------------------------------------------------------
# 02. Data Flow Architecture
# ---------------------------------------------------------------------------
def gen_02_data_flow():
    fig, ax = setup_canvas(11, 6)
    ax.text(
        50,
        93,
        "Figure 5.2: End-to-End System Data Flow Pipeline",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    stages = [
        ("OV2640\nImage Sensor", "Raw VGA\nJPEG Frames", "#e3f2fd", "#1565c0"),
        (
            "Frame Acquisition\n& Normalization",
            "RGB Array\nEnhancement",
            "#e1f5fe",
            "#0288d1",
        ),
        (
            "Target Perception\n(TinyML / Blob)",
            "Bounding Box\n(x, y, w, h, conf)",
            "#e8f5e9",
            "#2e7d32",
        ),
        (
            "Position Estimator\n& Error Calc",
            "Heading Error\nZone (L/C/R)",
            "#fff8e1",
            "#f57f17",
        ),
        (
            "Decision Engine\n(FSM)",
            "Movement Intent\n(STATE, CMD)",
            "#fff3e0",
            "#e65100",
        ),
        (
            "Safety Supervisor\n(Arduino Watchdog)",
            "Gated Actuation\nOverride / Pass",
            "#ffebee",
            "#c62828",
        ),
        (
            "H-Bridge Driver\n& TT Motors",
            "Differential Speed\n(v_L, v_R)",
            "#f3e5f5",
            "#6a1b9a",
        ),
    ]

    x_positions = np.linspace(8, 92, len(stages))
    for i, (name, data, bg, fg) in enumerate(stages):
        x = x_positions[i]
        ax.add_patch(
            patches.FancyBboxPatch(
                (x - 5.5, 35), 11, 35, boxstyle="round,pad=0.5", fc=bg, ec=fg, lw=1.5
            )
        )
        ax.text(
            x,
            62,
            name,
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
            color=fg,
        )
        ax.axhline(
            50, xmin=(x - 5.0) / 100, xmax=(x + 5.0) / 100, color=fg, lw=0.5, ls=":"
        )
        ax.text(
            x,
            43,
            data,
            ha="center",
            va="center",
            fontsize=7,
            style="italic",
            color="#333333",
        )

        if i < len(stages) - 1:
            next_x = x_positions[i + 1]
            ax.annotate(
                "",
                xy=(next_x - 5.8, 52),
                xytext=(x + 5.8, 52),
                arrowprops=dict(arrowstyle="->", color="#37474f", lw=1.8),
            )

    # ESP32 vs Arduino Boundaries
    ax.add_patch(
        patches.Rectangle((1.5, 25), 65, 52, fill=False, ec="#0288d1", ls="--", lw=1.2)
    )
    ax.text(
        34,
        28,
        "ESP32-CAM EDGE COMPUTING DOMAIN",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#0288d1",
    )

    ax.add_patch(
        patches.Rectangle((69.5, 25), 29, 52, fill=False, ec="#2e7d32", ls="--", lw=1.2)
    )
    ax.text(
        84,
        28,
        "ARDUINO SAFETY DOMAIN",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#2e7d32",
    )

    save_figure(fig, "02_data_flow.png")


# ---------------------------------------------------------------------------
# 03. Hardware Architecture & Pin Interconnect
# ---------------------------------------------------------------------------
def gen_03_hardware_architecture():
    fig, ax = setup_canvas(11, 7)
    ax.text(
        50,
        94,
        "Figure 6.1: Hardware Wiring, Pin Allocations, and Data-Link Topology",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    # Arduino Block
    ax.add_patch(
        patches.FancyBboxPatch(
            (5, 15), 25, 70, boxstyle="round,pad=0.8", fc="#e8f5e9", ec="#2e7d32", lw=2
        )
    )
    ax.text(
        17.5,
        81,
        "ARDUINO UNO R3\n(ATmega328P - 5V Logic)",
        ha="center",
        fontsize=10,
        fontweight="bold",
        color="#1b5e20",
    )

    uno_pins = [
        ("D0 (RX)", "<- Laptop USB (host commands)"),
        ("D1 (TX)", "-> Laptop USB (host telemetry)"),
        ("D5 (PWM)", "-> L298N ENA (Left Motor Speed)"),
        ("D6 (DO)", "-> L298N IN1 (Left Forward)"),
        ("D7 (DO)", "-> L298N IN2 (Left Reverse)"),
        ("D8 (DO)", "-> L298N IN3 (Right Forward)"),
        ("D9 (DO)", "-> L298N IN4 (Right Reverse)"),
        ("D10 (PWM)", "-> L298N ENB (Right Motor Speed)"),
        ("D11 (DO)", "-> HC-SR04 TRIG (Trigger 10us)"),
        ("D12 (DI)", "<- HC-SR04 ECHO (Echo Return)"),
        ("5V / GND", "Logic Power / Common Ground"),
    ]
    for idx, (p, d) in enumerate(uno_pins):
        y = 73 - idx * 5.2
        ax.text(7, y, f"{p}: {d}", fontsize=7.2, family="monospace", color="#1b5e20")

    # Data-Link Note (ESP32 is power-only; no wired UART between boards)
    ax.add_patch(
        patches.FancyBboxPatch(
            (36, 50),
            18,
            30,
            boxstyle="round,pad=0.5",
            fc="#fff9c4",
            ec="#fbc02d",
            lw=1.8,
        )
    )
    ax.text(
        45,
        76,
        "DATA LINKS\n(NO WIRED UART)",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#f57f17",
    )
    ax.text(
        45,
        68,
        "Video: ESP32 -> Wi-Fi MJPEG\n-> laptop /stream",
        ha="center",
        fontsize=7.5,
        family="monospace",
    )
    ax.text(
        45,
        58,
        "Commands: laptop -> USB\n-> Arduino D0/D1 (9600)",
        ha="center",
        fontsize=7.5,
        family="monospace",
    )
    ax.text(
        45,
        52,
        "[ESP32 WIRED TO 5V + GND ONLY]",
        ha="center",
        fontsize=6.5,
        fontweight="bold",
        color="#b71c1c",
    )

    # ESP32 Block
    ax.add_patch(
        patches.FancyBboxPatch(
            (60, 45), 35, 40, boxstyle="round,pad=0.8", fc="#e1f5fe", ec="#0288d1", lw=2
        )
    )
    ax.text(
        77.5,
        81,
        "ESP32-CAM (AI-Thinker)\n(3.3V Logic - Xtensa LX6)",
        ha="center",
        fontsize=10,
        fontweight="bold",
        color="#01579b",
    )

    esp_pins = [
        ("GPIO 1 (TXD0)", "-> Debug/flash UART (not wired)"),
        ("GPIO 3 (RXD0)", "<- Not connected (video via Wi-Fi)"),
        ("GPIO 32 (PWDN)", "-> OV2640 Power Down Line"),
        ("GPIO 0 (XCLK)", "-> OV2640 System Clock (20MHz)"),
        ("GPIO 26/27", "-> SCCB SIOD / SIOC (I2C Cam Config)"),
        ("GPIO 35-36, 18-21", "<- DVP Parallel Video Data Bus"),
        ("VCC (5V in) / GND", "Power via Buck Converter / Common GND"),
    ]
    for idx, (p, d) in enumerate(esp_pins):
        y = 73 - idx * 4.2
        ax.text(62, y, f"{p}: {d}", fontsize=7.2, family="monospace", color="#01579b")

    # L298N Driver Block
    ax.add_patch(
        patches.FancyBboxPatch(
            (36, 10),
            22,
            32,
            boxstyle="round,pad=0.8",
            fc="#ffe0b2",
            ec="#e65100",
            lw=1.8,
        )
    )
    ax.text(
        47,
        38,
        "L298N MOTOR DRIVER",
        ha="center",
        fontsize=9.5,
        fontweight="bold",
        color="#bf360c",
    )
    ax.text(
        38,
        30,
        "ENA/ENB: Speed PWM\nIN1-IN4: Direction H-Bridge\n12V Term: Motor Power\n5V Reg: Internal Logic\nGND: Common Ground",
        fontsize=7.2,
        family="monospace",
    )

    # Motors Block
    ax.add_patch(
        patches.FancyBboxPatch(
            (65, 10),
            30,
            28,
            boxstyle="round,pad=0.8",
            fc="#fbe9e7",
            ec="#d84315",
            lw=1.5,
        )
    )
    ax.text(
        80,
        33,
        "TT DC GEAR MOTORS",
        ha="center",
        fontsize=9.5,
        fontweight="bold",
        color="#bf360c",
    )
    ax.text(
        67,
        24,
        "OUT1/OUT2 -> Left Motor (1:48)\nOUT3/OUT4 -> Right Motor (1:48)\nDecoupled with 0.1uF ceramic\ncapacitors across terminals",
        fontsize=7.2,
        family="monospace",
    )

    save_figure(fig, "03_hardware_architecture.png")


# ---------------------------------------------------------------------------
# 04. Power Architecture
# ---------------------------------------------------------------------------
def gen_04_power_architecture():
    fig, ax = setup_canvas(10, 6.5)
    ax.text(
        50,
        94,
        "Figure 6.2: Power Distribution & Decoupling Architecture",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    # Battery
    ax.add_patch(
        patches.FancyBboxPatch(
            (5, 45), 20, 32, boxstyle="round,pad=0.8", fc="#fffde7", ec="#f57f17", lw=2
        )
    )
    ax.text(
        15,
        72,
        "BATTERY PACK\n(2S 18650 Li-ion)",
        ha="center",
        fontsize=10,
        fontweight="bold",
        color="#e65100",
    )
    ax.text(
        15,
        59,
        "Nominal: 7.4 V\nFully Charged: 8.4 V\nCapacity: ~2600 mAh\nDischarge: >= 5A continuous",
        ha="center",
        fontsize=8,
        color="#bf360c",
    )

    # Power Switch & Fuse
    ax.add_patch(
        patches.FancyBboxPatch(
            (30, 52),
            12,
            18,
            boxstyle="round,pad=0.5",
            fc="#eceff1",
            ec="#455a64",
            lw=1.5,
        )
    )
    ax.text(
        36,
        63,
        "MAIN SWITCH\n& 3A FUSE",
        ha="center",
        fontsize=8,
        fontweight="bold",
        color="#263238",
    )
    ax.annotate(
        "",
        xy=(30, 61),
        xytext=(25, 61),
        arrowprops=dict(arrowstyle="->", color="#d32f2f", lw=2.5),
    )

    # Buck Converter (Step Down to 5V)
    ax.add_patch(
        patches.FancyBboxPatch(
            (48, 58), 24, 24, boxstyle="round,pad=0.8", fc="#e8f5e9", ec="#2e7d32", lw=2
        )
    )
    ax.text(
        60,
        77,
        "STEP-DOWN BUCK CONVERTER\n(LM2596 / MP1584)",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#1b5e20",
    )
    ax.text(
        60,
        66,
        "Input: 7.4V - 8.4V\nOutput: 5.0V Regulated (3A)\nEfficiency: ~88-92%",
        ha="center",
        fontsize=7.8,
        color="#2e7d32",
    )

    # Connect switch to Buck and L298N
    ax.annotate(
        "",
        xy=(48, 70),
        xytext=(42, 65),
        arrowprops=dict(arrowstyle="->", color="#d32f2f", lw=2.5),
    )
    ax.annotate(
        "",
        xy=(48, 28),
        xytext=(42, 57),
        arrowprops=dict(arrowstyle="->", color="#d32f2f", lw=2.5),
    )
    ax.text(
        42,
        43,
        "7.4V Motor Rail\n(Unregulated)",
        fontsize=7.5,
        fontweight="bold",
        color="#d32f2f",
    )

    # L298N Motor Driver Power
    ax.add_patch(
        patches.FancyBboxPatch(
            (48, 12), 24, 26, boxstyle="round,pad=0.8", fc="#ffe0b2", ec="#e65100", lw=2
        )
    )
    ax.text(
        60,
        33,
        "L298N MOTOR DRIVER\n(Inductive Load Stage)",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#bf360c",
    )
    ax.text(
        60,
        22,
        "Motor VCC: 7.4V Terminal\nInternal Drop: ~1.8V - 2.5V\nEffective Motor V: ~5.0V - 5.6V",
        ha="center",
        fontsize=7.8,
        color="#bf360c",
    )

    # 5V Clean Logic Subsystems (ESP32 & Arduino)
    ax.add_patch(
        patches.FancyBboxPatch(
            (78, 66),
            18,
            20,
            boxstyle="round,pad=0.6",
            fc="#e1f5fe",
            ec="#0288d1",
            lw=1.8,
        )
    )
    ax.text(
        87, 80, "ESP32-CAM", ha="center", fontsize=9, fontweight="bold", color="#01579b"
    )
    ax.text(
        87,
        72,
        "5V In (Onboard LDO -> 3.3V)\nPeak current: ~300mA",
        ha="center",
        fontsize=7.2,
        color="#0288d1",
    )

    ax.add_patch(
        patches.FancyBboxPatch(
            (78, 40),
            18,
            20,
            boxstyle="round,pad=0.6",
            fc="#e8f5e9",
            ec="#388e3c",
            lw=1.8,
        )
    )
    ax.text(
        87,
        54,
        "ARDUINO UNO",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#1b5e20",
    )
    ax.text(
        87,
        46,
        "5V Pin In\nSteady current: ~45mA",
        ha="center",
        fontsize=7.2,
        color="#2e7d32",
    )

    # Connect Buck 5V Out
    ax.annotate(
        "",
        xy=(78, 76),
        xytext=(72, 72),
        arrowprops=dict(arrowstyle="->", color="#1565c0", lw=2),
    )
    ax.annotate(
        "",
        xy=(78, 50),
        xytext=(72, 68),
        arrowprops=dict(arrowstyle="->", color="#1565c0", lw=2),
    )
    ax.text(
        73,
        62,
        "Clean 5.0V\nLogic Rail",
        ha="center",
        fontsize=7.5,
        fontweight="bold",
        color="#1565c0",
    )

    # Common Ground Star Network across bottom
    ax.add_patch(patches.Rectangle((5, 4), 90, 4, fc="#263238", ec="none"))
    ax.text(
        50,
        6,
        "COMMON STAR GROUND JUNCTION (GND) — ZERO-VOLT REFERENCE PLANE",
        ha="center",
        va="center",
        fontsize=8.5,
        fontweight="bold",
        color="white",
    )

    save_figure(fig, "04_power_architecture.png")


# ---------------------------------------------------------------------------
# 05. ESP32 AI & Perception Pipeline
# ---------------------------------------------------------------------------
def gen_05_esp32_pipeline():
    fig, ax = setup_canvas(10, 8.5)
    ax.text(
        50,
        96,
        "Figure 8.1: ESP32 Edge Perception & Decision Pipeline",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    stages = [
        (
            "1. OmniVision OV2640 Sensor",
            "DVP 8-bit bus capture @ 15 FPS (VGA / QVGA)",
            "#e0f7fa",
            "#00838f",
        ),
        (
            "2. DMA Frame Buffer Allocation",
            "fb_count=2 in 4MB External SPI PSRAM",
            "#e1f5fe",
            "#0277bd",
        ),
        (
            "3. Preprocessing & ISP Enhancement",
            "CLAHE contrast normalization + unsharp masking",
            "#ede7f6",
            "#512da8",
        ),
        (
            "4. Edge AI Inference / Target Detection",
            "int8 Quantized CNN (FOMO / MobileNet) or Color HSV Centroid",
            "#e8f5e9",
            "#2e7d32",
        ),
        (
            "5. Bounding Box & Confidence Gate",
            "Threshold filtering (conf >= 0.50, min_box >= 20px)",
            "#fffde7",
            "#f57f17",
        ),
        (
            "6. Target Spatial Position Estimation",
            "x_center = x + w/2, error = x_center - 0.50",
            "#fff3e0",
            "#e65100",
        ),
        (
            "7. Navigation State Machine (FSM)",
            "Transitions: SEARCHING -> ALIGNING -> APPROACHING",
            "#fbe9e7",
            "#d84315",
        ),
        (
            "8. Command Serial Transmitter",
            "Tokens 'F','L','R','S' -> laptop (Wi-Fi) -> Arduino via USB serial",
            "#f3e5f5",
            "#7b1fa2",
        ),
    ]

    y_start = 88
    for i, (title, desc, bg, fg) in enumerate(stages):
        y = y_start - i * 9.8
        ax.add_patch(
            patches.FancyBboxPatch(
                (15, y - 6.5), 70, 7.5, boxstyle="round,pad=0.5", fc=bg, ec=fg, lw=1.8
            )
        )
        ax.text(20, y - 1.5, title, fontsize=9.5, fontweight="bold", color=fg)
        ax.text(20, y - 4.5, desc, fontsize=8, color="#37474f", style="italic")

        if i < len(stages) - 1:
            ax.annotate(
                "",
                xy=(50, y - 6.5),
                xytext=(50, y - 8.8),
                arrowprops=dict(arrowstyle="->", color="#37474f", lw=2.0),
            )

    # ESP32 Boundary Annotation
    ax.add_patch(
        patches.Rectangle((10, 7), 80, 85, fill=False, ec="#00838f", ls="--", lw=1.5)
    )
    ax.text(
        88,
        10,
        "ESP32 BOUNDARY",
        rotation=90,
        fontsize=9,
        fontweight="bold",
        color="#00838f",
    )

    save_figure(fig, "05_esp32_pipeline.png")


# ---------------------------------------------------------------------------
# 06. Decision Pipeline & 07. Arduino Pipeline
# ---------------------------------------------------------------------------
def gen_06_decision_pipeline():
    fig, ax = setup_canvas(10, 6)
    ax.text(
        50,
        93,
        "Figure 8.2: Target Heading Decision & Zone Mapping Logic",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    # Zones visual
    ax.add_patch(patches.Rectangle((15, 30), 70, 45, fc="#f5f5f5", ec="#333333", lw=2))
    ax.axvline(15 + 70 * 0.33, 0.30, 0.75, color="#1565c0", ls="--", lw=1.8)
    ax.axvline(15 + 70 * 0.66, 0.30, 0.75, color="#1565c0", ls="--", lw=1.8)

    # Deadband
    cx = 15 + 70 * 0.50
    dw = 70 * 0.06
    ax.add_patch(
        patches.Rectangle(
            (cx - dw, 30), 2 * dw, 45, fc="#c8e6c9", ec="#2e7d32", alpha=0.5
        )
    )

    ax.text(
        26,
        65,
        "LEFT ZONE\n(0.00 <= x < 0.33)\nTurn Left ('L')",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#1565c0",
    )
    ax.text(
        50,
        65,
        "CENTER ZONE\n(0.33 <= x <= 0.66)\nDeadband: ±0.06\nDrive Forward ('F')",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#2e7d32",
    )
    ax.text(
        74,
        65,
        "RIGHT ZONE\n(0.66 < x <= 1.00)\nTurn Right ('R')",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#1565c0",
    )

    # Formula
    ax.text(
        50,
        15,
        "Target Center:  $x_{center} = x + \\frac{w}{2}$      |      Heading Error:  $e = x_{center} - 0.50$\n"
        "Approach Termination: Stop ('S') if $\\frac{w}{W_{frame}} \\geq 0.45$ (Proximity Limit)",
        ha="center",
        fontsize=9.5,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.6", fc="#fff9c4", ec="#fbc02d"),
    )

    save_figure(fig, "06_decision_pipeline.png")


def gen_07_arduino_pipeline():
    fig, ax = setup_canvas(10, 6.5)
    ax.text(
        50,
        94,
        "Figure 7.1: Arduino UNO Execution Loop & Safety Arbitration Pipeline",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    steps = [
        (
            "UART Ingest",
            "Read incoming ASCII command char\n('F','B','L','R','S') via Serial.read()",
            15,
            65,
        ),
        (
            "Timeout Check",
            "commLost = (now - lastCmdTime > 3000ms)\nTrue => Force 'S', Trigger Watchdog",
            50,
            65,
        ),
        (
            "Ultrasonic Echo",
            "Read HC-SR04 pulseIn(ECHO)\nCalculate dist = dur * 0.0343 / 2.0",
            85,
            65,
        ),
        (
            "Safety Interlock",
            "blocked = (dist > 0 and dist < 15cm\nand (cmd=='F' or cmd=='B'))",
            32,
            28,
        ),
        (
            "Actuation / Cutoff",
            "If commLost or blocked: stopMotors()\nElse: drive(currentCmd, DEFAULT_SPEED)",
            68,
            28,
        ),
    ]

    for title, desc, x, y in steps:
        ax.add_patch(
            patches.FancyBboxPatch(
                (x - 14, y - 10),
                28,
                20,
                boxstyle="round,pad=0.6",
                fc="#e8f5e9",
                ec="#2e7d32",
                lw=1.8,
            )
        )
        ax.text(
            x,
            y + 5,
            title,
            ha="center",
            fontsize=9.5,
            fontweight="bold",
            color="#1b5e20",
        )
        ax.text(
            x,
            y - 3,
            desc,
            ha="center",
            fontsize=7.5,
            color="#37474f",
            family="monospace",
        )

    # Connectors
    ax.annotate(
        "", xy=(36, 65), xytext=(29, 65), arrowprops=dict(arrowstyle="->", lw=2)
    )
    ax.annotate(
        "", xy=(71, 65), xytext=(64, 65), arrowprops=dict(arrowstyle="->", lw=2)
    )
    ax.annotate(
        "", xy=(50, 48), xytext=(50, 55), arrowprops=dict(arrowstyle="->", lw=2)
    )
    ax.annotate(
        "", xy=(54, 28), xytext=(46, 28), arrowprops=dict(arrowstyle="->", lw=2)
    )

    save_figure(fig, "07_arduino_pipeline.png")


# ---------------------------------------------------------------------------
# 08. Safety Hierarchy
# ---------------------------------------------------------------------------
def gen_08_safety_hierarchy():
    fig, ax = setup_canvas(10, 7)
    ax.text(
        50,
        95,
        "Figure 10.1: Multi-Tier Safety Priority Pyramid",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    tiers = [
        (
            "PRIORITY 1: EMERGENCY HARDWARE STOP",
            "Manual E-Stop Latch / Critical Fault -> Cut motor power immediately",
            16,
            "#b71c1c",
            "white",
        ),
        (
            "PRIORITY 2: ULTRASONIC COLLISION BARRIER",
            "HC-SR04 reading < 15.0 cm -> Hardware override halts forward drive",
            26,
            "#c62828",
            "white",
        ),
        (
            "PRIORITY 3: COMMUNICATION WATCHDOG",
            "No valid UART heartbeat for > 3000 ms -> Autonomous timeout stop",
            36,
            "#d32f2f",
            "white",
        ),
        (
            "PRIORITY 4: COMMAND VALIDITY FILTER",
            "Unrecognized packet received -> Reject command, retain previous safe state",
            46,
            "#f57c00",
            "white",
        ),
        (
            "PRIORITY 5: AI CONFIDENCE & INTEGRITY GATE",
            "Confidence < 0.50 or camera frozen > 3.0 s -> Inhibit autonomous pursuit",
            56,
            "#fbc02d",
            "#212121",
        ),
        (
            "PRIORITY 6: NOMINAL NAVIGATION COMMANDS",
            "Goal tracking, alignment, approach ('F','L','R') executed under supervision",
            66,
            "#388e3c",
            "white",
        ),
    ]

    for idx, (title, desc, width, bg, fg) in enumerate(tiers):
        y = 80 - idx * 11
        w = 30 + idx * 11
        ax.add_patch(
            patches.FancyBboxPatch(
                (50 - w / 2, y - 4),
                w,
                8,
                boxstyle="round,pad=0.4",
                fc=bg,
                ec="#333333",
                lw=1.2,
            )
        )
        ax.text(
            50, y + 1.2, title, ha="center", fontsize=8.5, fontweight="bold", color=fg
        )
        ax.text(50, y - 2.2, desc, ha="center", fontsize=7.2, color=fg)

    save_figure(fig, "08_safety_hierarchy.png")


# ---------------------------------------------------------------------------
# 09. State Machine Diagram
# ---------------------------------------------------------------------------
def gen_09_state_machine():
    fig, ax = setup_canvas(10, 7)
    ax.text(
        50,
        95,
        "Figure 7.2: Decision Engine Finite State Machine (FSM) Transitions",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    states = {
        "IDLE": (15, 75, "#eceff1", "#37474f"),
        "SEARCHING": (50, 75, "#fff8e1", "#f57f17"),
        "ALIGNING": (85, 75, "#e1f5fe", "#0288d1"),
        "APPROACHING": (85, 35, "#e8f5e9", "#2e7d32"),
        "AVOIDING": (50, 35, "#fff3e0", "#e65100"),
        "STOPPED": (15, 35, "#ffebee", "#c62828"),
        "EMERGENCY_STOP": (50, 10, "#b71c1c", "white"),
    }

    for name, (x, y, bg, fg) in states.items():
        tc = "white" if bg == "#b71c1c" else fg
        ax.add_patch(
            patches.FancyBboxPatch(
                (x - 11, y - 6), 22, 12, boxstyle="round,pad=0.6", fc=bg, ec=fg, lw=2
            )
        )
        ax.text(
            x,
            y,
            name,
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            color=tc,
        )

    # Transitions
    def draw_arrow(s1, s2, label, offset=(0, 0)):
        x1, y1 = states[s1][0], states[s1][1]
        x2, y2 = states[s2][0], states[s2][1]
        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops=dict(
                arrowstyle="->", color="#37474f", lw=1.5, shrinkA=18, shrinkB=18
            ),
        )
        mx, my = (x1 + x2) / 2 + offset[0], (y1 + y2) / 2 + offset[1]
        ax.text(
            mx,
            my,
            label,
            fontsize=7.2,
            ha="center",
            backgroundcolor="white",
            color="#263238",
        )

    draw_arrow("IDLE", "SEARCHING", "Start Mission", (0, 3))
    draw_arrow("SEARCHING", "ALIGNING", "Target Detected", (0, 3))
    draw_arrow("ALIGNING", "APPROACHING", "Target Centered", (4, 0))
    draw_arrow("APPROACHING", "STOPPED", "Target Reached (w>45%)", (0, -3))
    draw_arrow("APPROACHING", "AVOIDING", "Obstacle Detected (<30cm)", (0, 3))
    draw_arrow("AVOIDING", "SEARCHING", "Path Cleared", (0, 0))
    draw_arrow("SEARCHING", "STOPPED", "Timeout Exceeded", (-12, -15))

    ax.text(
        50,
        22,
        "Any State ---> Critical Obstacle (<15cm) / Comm Loss ---> EMERGENCY_STOP",
        ha="center",
        fontsize=8,
        fontweight="bold",
        color="#b71c1c",
        bbox=dict(boxstyle="round,pad=0.4", fc="#ffebee", ec="#c62828"),
    )

    save_figure(fig, "09_state_machine.png")


# ---------------------------------------------------------------------------
# 10. Control Loop Block Diagram
# ---------------------------------------------------------------------------
def gen_10_control_loop():
    fig, ax = setup_canvas(10, 5)
    ax.text(
        50,
        92,
        "Figure 9.1: Proportional Heading Control Closed-Loop Architecture",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    # Summing junction
    circle = patches.Circle((20, 50), 3, fc="#f5f5f5", ec="#333333", lw=1.8)
    ax.add_patch(circle)
    ax.text(20, 50, "+", ha="center", va="center", fontsize=12, fontweight="bold")
    ax.text(18.5, 43, "-", ha="center", va="center", fontsize=12, fontweight="bold")

    # Setpoint
    ax.annotate("", xy=(17, 50), xytext=(5, 50), arrowprops=dict(arrowstyle="->", lw=2))
    ax.text(
        10,
        54,
        "Target Center\n$x_{ref} = 0.50$",
        ha="center",
        fontsize=8,
        fontweight="bold",
    )

    # Proportional Controller
    ax.add_patch(
        patches.Rectangle((28, 40), 16, 20, fc="#e3f2fd", ec="#1565c0", lw=1.8)
    )
    ax.text(
        36,
        52,
        "CONTROLLER",
        ha="center",
        fontsize=8.5,
        fontweight="bold",
        color="#1565c0",
    )
    ax.text(
        36,
        45,
        "$\\omega = K_p \\cdot e$\n($K_p \\approx 0.6$)",
        ha="center",
        fontsize=7.8,
    )
    ax.annotate(
        "", xy=(28, 50), xytext=(23, 50), arrowprops=dict(arrowstyle="->", lw=2)
    )
    ax.text(25.5, 53, "Error $e$", ha="center", fontsize=7.5)

    # Rover Plant Dynamics
    ax.add_patch(
        patches.Rectangle((52, 40), 20, 20, fc="#e8f5e9", ec="#2e7d32", lw=1.8)
    )
    ax.text(
        62,
        52,
        "ROVER KINEMATICS",
        ha="center",
        fontsize=8.5,
        fontweight="bold",
        color="#2e7d32",
    )
    ax.text(
        62,
        45,
        "$\\dot{\\theta} = \\omega = \\frac{r}{L}(\\omega_R - \\omega_L)$\n$\\dot{x} = v \\cos\\theta$",
        ha="center",
        fontsize=7.5,
    )
    ax.annotate(
        "", xy=(52, 50), xytext=(44, 50), arrowprops=dict(arrowstyle="->", lw=2)
    )
    ax.text(48, 53, "$\\omega_{cmd}$", ha="center", fontsize=8)

    # Output
    ax.annotate(
        "", xy=(88, 50), xytext=(72, 50), arrowprops=dict(arrowstyle="->", lw=2)
    )
    ax.text(80, 53, "Robot Yaw $\\theta$", ha="center", fontsize=8, fontweight="bold")

    # Feedback Sensor (Camera)
    ax.add_patch(
        patches.Rectangle((42, 10), 22, 16, fc="#fff3e0", ec="#e65100", lw=1.8)
    )
    ax.text(
        53,
        20,
        "OV2640 CAMERA",
        ha="center",
        fontsize=8.5,
        fontweight="bold",
        color="#e65100",
    )
    ax.text(53, 14, "$x_{meas} = x_{bbox} + \\frac{w}{2}$", ha="center", fontsize=7.8)

    # Feedback lines
    ax.plot([82, 82, 64], [50, 18, 18], color="#333333", lw=1.8)
    ax.annotate(
        "", xy=(42, 18), xytext=(42, 18), arrowprops=dict(arrowstyle="->", lw=2)
    )
    ax.plot([42, 20, 20], [18, 18, 47], color="#333333", lw=1.8)
    ax.annotate(
        "", xy=(20, 47), xytext=(20, 30), arrowprops=dict(arrowstyle="->", lw=2)
    )

    save_figure(fig, "10_control_loop.png")


# ---------------------------------------------------------------------------
# 11. Differential Drive Kinematic Geometry
# ---------------------------------------------------------------------------
def gen_11_differential_drive_geometry():
    fig, ax = setup_canvas(10, 7.5)
    ax.text(
        50,
        94,
        "Figure 9.2: Differential Drive Mobile Robot Kinematic Model",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    # Robot chassis body
    ax.add_patch(
        patches.FancyBboxPatch(
            (35, 30), 30, 40, boxstyle="round,pad=1.0", fc="#e0e0e0", ec="#424242", lw=2
        )
    )
    ax.text(
        50,
        52,
        "ROVER CHASSIS\n(Width = 180 mm)",
        ha="center",
        fontsize=10,
        fontweight="bold",
        color="#212121",
    )

    # Front Caster / Direction Indicator
    ax.add_patch(patches.Circle((50, 68), 3, fc="#90a4ae", ec="#37474f", lw=1.5))
    ax.annotate(
        "",
        xy=(50, 84),
        xytext=(50, 68),
        arrowprops=dict(arrowstyle="->", color="#d32f2f", lw=3.0),
    )
    ax.text(
        50,
        86,
        "FORWARD (x-axis)\nLinear Velocity $v$",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#d32f2f",
    )

    # Left Wheel
    ax.add_patch(patches.Rectangle((30, 35), 5, 20, fc="#263238", ec="black", lw=1.5))
    ax.text(
        25,
        45,
        "LEFT WHEEL\nRadius $r = 32.5$ mm\nVelocity $v_L = r\\omega_L$",
        ha="right",
        fontsize=8,
        fontweight="bold",
    )
    ax.annotate(
        "",
        xy=(32.5, 62),
        xytext=(32.5, 45),
        arrowprops=dict(arrowstyle="->", color="#1565c0", lw=2.5),
    )

    # Right Wheel
    ax.add_patch(patches.Rectangle((65, 35), 5, 20, fc="#263238", ec="black", lw=1.5))
    ax.text(
        75,
        45,
        "RIGHT WHEEL\nRadius $r = 32.5$ mm\nVelocity $v_R = r\\omega_R$",
        ha="left",
        fontsize=8,
        fontweight="bold",
    )
    ax.annotate(
        "",
        xy=(67.5, 62),
        xytext=(67.5, 45),
        arrowprops=dict(arrowstyle="->", color="#1565c0", lw=2.5),
    )

    # Track width L dimension line
    ax.annotate(
        "",
        xy=(32.5, 25),
        xytext=(67.5, 25),
        arrowprops=dict(arrowstyle="<->", color="#e65100", lw=2.0),
    )
    ax.text(
        50,
        21,
        "Track Width $L = 180$ mm",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#e65100",
    )

    # Center of mass / ICC point
    ax.plot(50, 45, "ro", markersize=6)
    ax.text(52, 42, "Center of Axis ($C$)", fontsize=8, fontweight="bold")

    # Angular rotation arrow around C
    arc = patches.Arc(
        (50, 45), 18, 18, angle=0, theta1=45, theta2=225, color="#7b1fa2", lw=2, ls="--"
    )
    ax.add_patch(arc)
    ax.text(
        50,
        32,
        "Angular Velocity $\\omega$",
        ha="center",
        fontsize=8.5,
        fontweight="bold",
        color="#7b1fa2",
    )

    # Kinematic Equations Box
    eq_text = (
        "Forward Kinematics:\n"
        "  $v = \\frac{r}{2} (\\omega_R + \\omega_L)$\n"
        "  $\\omega = \\frac{r}{L} (\\omega_R - \\omega_L)$\n\n"
        "Turning Radius:\n"
        "  $R = \\frac{v}{\\omega} = \\frac{L}{2} \\frac{\\omega_R + \\omega_L}{\\omega_R - \\omega_L}$"
    )
    ax.text(
        50,
        8,
        eq_text,
        ha="center",
        fontsize=9,
        family="serif",
        bbox=dict(boxstyle="round,pad=0.6", fc="#fffde7", ec="#fbc02d", lw=1.5),
    )

    save_figure(fig, "11_differential_drive_geometry.png")


# ---------------------------------------------------------------------------
# 12. Target Position & 13. Left Center Right Zones
# ---------------------------------------------------------------------------
def gen_12_and_13_zones():
    # 12. Target Position
    fig, ax = setup_canvas(10, 6)
    ax.text(
        50,
        94,
        "Figure 8.3: Bounding Box Centroid and Error Calculation",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    # Camera frame
    ax.add_patch(patches.Rectangle((15, 20), 70, 60, fc="#eceff1", ec="#37474f", lw=2))
    ax.text(
        17,
        76,
        "CAMERA IMAGE PLANE (640 x 480)",
        fontsize=8,
        fontweight="bold",
        color="#455a64",
    )

    # Centerline
    ax.axvline(50, 0.20, 0.80, color="#d32f2f", ls="--", lw=1.5)
    ax.text(
        50,
        82,
        "Image Optical Center ($x_{ref} = 0.50$)",
        ha="center",
        fontsize=8.5,
        fontweight="bold",
        color="#d32f2f",
    )

    # Bounding box
    bx, by, bw, bh = 60, 35, 16, 30
    ax.add_patch(patches.Rectangle((bx, by), bw, bh, fc="#bbdefb", ec="#1565c0", lw=2))
    ax.text(
        bx + bw / 2,
        by + bh / 2,
        "TARGET\n(Bottle/Object)",
        ha="center",
        va="center",
        fontsize=8.5,
        fontweight="bold",
        color="#0d47a1",
    )

    # Centroid
    cx = bx + bw / 2
    cy = by + bh / 2
    ax.plot(cx, cy, "ro", markersize=7)
    ax.text(
        cx,
        cy - 4,
        f"Target Center $x_c = {cx / 100:.2f}$",
        ha="center",
        fontsize=8,
        fontweight="bold",
    )

    # Error vector
    ax.annotate(
        "",
        xy=(cx, 50),
        xytext=(50, 50),
        arrowprops=dict(arrowstyle="<->", color="#e65100", lw=2.5),
    )
    ax.text(
        (50 + cx) / 2,
        53,
        "Error $e = x_c - 0.50 > 0$\nCommand: TURN RIGHT",
        ha="center",
        fontsize=8.5,
        fontweight="bold",
        color="#e65100",
    )

    save_figure(fig, "12_target_position.png")

    # 13. Left Center Right Zones
    fig, ax = setup_canvas(10, 6)
    ax.text(
        50,
        94,
        "Figure 8.4: Discrete Vision Zone Partitioning with Deadband",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    # 3 Zones
    ax.add_patch(
        patches.Rectangle((10, 25), 26.6, 55, fc="#e3f2fd", ec="#1565c0", lw=1.5)
    )
    ax.add_patch(
        patches.Rectangle((36.6, 25), 26.6, 55, fc="#e8f5e9", ec="#2e7d32", lw=1.5)
    )
    ax.add_patch(
        patches.Rectangle((63.2, 25), 26.8, 55, fc="#fff3e0", ec="#e65100", lw=1.5)
    )

    # Center Deadband
    ax.add_patch(
        patches.Rectangle(
            (50 - 4.8, 25), 9.6, 55, fc="#c8e6c9", ec="#1b5e20", ls="--", lw=1.5
        )
    )

    ax.text(
        23.3,
        55,
        "LEFT SECTOR\n[0.00, 0.33)\n\nSteer Left ('L')\n$\\omega > 0$",
        ha="center",
        fontsize=9.5,
        fontweight="bold",
        color="#1565c0",
    )
    ax.text(
        50,
        60,
        "DEADBAND\n(±0.06)\nNo Oscillation",
        ha="center",
        fontsize=7.5,
        fontweight="bold",
        color="#1b5e20",
    )
    ax.text(
        50,
        38,
        "CENTER SECTOR\n[0.33, 0.66]\n\nDrive Straight ('F')",
        ha="center",
        fontsize=9.5,
        fontweight="bold",
        color="#2e7d32",
    )
    ax.text(
        76.6,
        55,
        "RIGHT SECTOR\n(0.66, 1.00]\n\nSteer Right ('R')\n$\\omega < 0$",
        ha="center",
        fontsize=9.5,
        fontweight="bold",
        color="#e65100",
    )

    # Boundaries
    ax.text(36.6, 20, "Left Bound = 0.33", ha="center", fontsize=8, fontweight="bold")
    ax.text(63.2, 20, "Right Bound = 0.66", ha="center", fontsize=8, fontweight="bold")

    save_figure(fig, "13_left_center_right_zones.png")


# ---------------------------------------------------------------------------
# 14. Communication Protocol & 15. Full Robot Block Diagram
# ---------------------------------------------------------------------------
def gen_14_communication_protocol():
    fig, ax = setup_canvas(10, 6)
    ax.text(
        50,
        94,
        "Figure 7.3: Serial Protocol Timing & Watchdog Communication Sequence",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    # Lifelines
    ax.plot([25, 25], [20, 85], color="#0288d1", lw=2)
    ax.text(
        25,
        88,
        "ESP32-CAM (Master)",
        ha="center",
        fontsize=10,
        fontweight="bold",
        color="#01579b",
    )

    ax.plot([75, 75], [20, 85], color="#2e7d32", lw=2)
    ax.text(
        75,
        88,
        "Arduino UNO (Slave)",
        ha="center",
        fontsize=10,
        fontweight="bold",
        color="#1b5e20",
    )

    # Message exchanges
    arrows = [
        (80, "->", "'F\\n' (Drive Forward)", "#0288d1"),
        (72, "<-", "'STATUS:OK\\n'", "#2e7d32"),
        (64, "<-", "'DIST:42.5\\n' (200ms Telemetry)", "#7b1fa2"),
        (56, "->", "'R\\n' (Turn Right)", "#0288d1"),
        (48, "<-", "'DIST:14.2\\n' (Obstacle < 15cm)", "#c62828"),
        (40, "<-", "'STATUS:STOP\\n' (Emergency Override)", "#c62828"),
        (30, "x", "[Communication Lost > 3000ms]", "#d32f2f"),
        (22, "<-", "LOCAL WATCHDOG FIRES -> MOTORS HALT", "#b71c1c"),
    ]

    for y, direction, text, col in arrows:
        if direction == "->":
            ax.annotate(
                "",
                xy=(73, y),
                xytext=(27, y),
                arrowprops=dict(arrowstyle="->", color=col, lw=1.8),
            )
            ax.text(
                50, y + 1.5, text, ha="center", fontsize=8, fontweight="bold", color=col
            )
        elif direction == "<-":
            ax.annotate(
                "",
                xy=(27, y),
                xytext=(73, y),
                arrowprops=dict(arrowstyle="->", color=col, lw=1.8),
            )
            ax.text(
                50, y + 1.5, text, ha="center", fontsize=8, fontweight="bold", color=col
            )
        elif direction == "x":
            ax.text(
                50,
                y,
                text,
                ha="center",
                fontsize=8.5,
                fontweight="bold",
                color=col,
                bbox=dict(boxstyle="square,pad=0.3", fc="#ffebee", ec="#ef5350"),
            )

    save_figure(fig, "14_communication_protocol.png")


def gen_15_full_robot_block_diagram():
    fig, ax = setup_canvas(11, 7.5)
    ax.text(
        50,
        95,
        "Figure 5.3: Complete Hardware Subsystem Interconnection & Signal Topology",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    # Battery
    ax.add_patch(
        patches.FancyBboxPatch(
            (4, 65),
            16,
            22,
            boxstyle="round,pad=0.6",
            fc="#fff9c4",
            ec="#fbc02d",
            lw=1.8,
        )
    )
    ax.text(
        12,
        79,
        "2S LI-ION\n7.4V BATTERY",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#e65100",
    )
    ax.text(12, 70, "Fused @ 3A", ha="center", fontsize=7.5)

    # Buck
    ax.add_patch(
        patches.FancyBboxPatch(
            (25, 65),
            16,
            22,
            boxstyle="round,pad=0.6",
            fc="#e8f5e9",
            ec="#388e3c",
            lw=1.8,
        )
    )
    ax.text(
        33,
        79,
        "BUCK CONVERTER\n(5.0V / 3A)",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#1b5e20",
    )
    ax.text(33, 70, "Logic Supply", ha="center", fontsize=7.5)

    # ESP32
    ax.add_patch(
        patches.FancyBboxPatch(
            (47, 55), 24, 32, boxstyle="round,pad=0.8", fc="#e1f5fe", ec="#0288d1", lw=2
        )
    )
    ax.text(
        59,
        81,
        "ESP32-CAM MODULE",
        ha="center",
        fontsize=10,
        fontweight="bold",
        color="#01579b",
    )
    ax.text(
        49,
        68,
        "• OV2640 Camera\n• TinyML / Centroid Detection\n• Target Heading Calc\n• Video -> Wi-Fi MJPEG",
        ha="left",
        fontsize=7.8,
    )

    # Laptop (host) - bridges Wi-Fi video in and USB serial out to the Arduino
    ax.add_patch(
        patches.FancyBboxPatch(
            (76, 68),
            18,
            18,
            boxstyle="round,pad=0.5",
            fc="#f3e5f5",
            ec="#8e24aa",
            lw=1.5,
        )
    )
    ax.text(
        85,
        80,
        "LAPTOP (HOST)",
        ha="center",
        fontsize=8.5,
        fontweight="bold",
        color="#4a148c",
    )
    ax.text(85, 72, "Wi-Fi video in\nUSB serial out", ha="center", fontsize=7.5)
    ax.text(73.5, 79, "Wi-Fi\nMJPEG", ha="center", fontsize=6.8, color="#0288d1")
    ax.text(88.5, 64, "USB\n9600", ha="center", fontsize=6.8, color="#2e7d32")

    # Arduino
    ax.add_patch(
        patches.FancyBboxPatch(
            (74, 15), 22, 45, boxstyle="round,pad=0.8", fc="#e8f5e9", ec="#2e7d32", lw=2
        )
    )
    ax.text(
        85,
        54,
        "ARDUINO UNO",
        ha="center",
        fontsize=10,
        fontweight="bold",
        color="#1b5e20",
    )
    ax.text(
        76,
        34,
        "• Command Parser\n• Safety Watchdog\n• PWM Drivers (D5, D10)\n• Direction (D6-D9)\n• HC-SR04 Ranging",
        ha="left",
        fontsize=7.5,
    )

    # L298N
    ax.add_patch(
        patches.FancyBboxPatch(
            (44, 15), 22, 32, boxstyle="round,pad=0.8", fc="#ffe0b2", ec="#e65100", lw=2
        )
    )
    ax.text(
        55,
        41,
        "L298N DRIVER",
        ha="center",
        fontsize=9.5,
        fontweight="bold",
        color="#bf360c",
    )
    ax.text(
        46,
        27,
        "• Dual BJT H-Bridge\n• Motor Supply: 7.4V\n• Logic Supply: 5.0V\n• Heatsinked Stage",
        ha="left",
        fontsize=7.5,
    )

    # Motors
    ax.add_patch(
        patches.FancyBboxPatch(
            (15, 15),
            22,
            32,
            boxstyle="round,pad=0.8",
            fc="#efebe9",
            ec="#4e342e",
            lw=1.8,
        )
    )
    ax.text(
        26,
        41,
        "TT DC MOTORS",
        ha="center",
        fontsize=9.5,
        fontweight="bold",
        color="#3e2723",
    )
    ax.text(
        17,
        27,
        "• Left & Right 1:48\n• 65mm Wheels\n• Open-loop Drive\n• Decoupled Caps",
        ha="left",
        fontsize=7.5,
    )

    # HC-SR04
    ax.add_patch(
        patches.FancyBboxPatch(
            (4, 42),
            16,
            18,
            boxstyle="round,pad=0.5",
            fc="#e0f2f1",
            ec="#00897b",
            lw=1.5,
        )
    )
    ax.text(
        12, 53, "HC-SR04", ha="center", fontsize=9, fontweight="bold", color="#004d40"
    )
    ax.text(12, 46, "Ultrasonic Range\n(D11/D12)", ha="center", fontsize=7.5)

    # Connectors
    ax.annotate(
        "",
        xy=(25, 76),
        xytext=(20, 76),
        arrowprops=dict(arrowstyle="->", lw=2, color="#e65100"),
    )
    ax.annotate(
        "",
        xy=(47, 76),
        xytext=(41, 76),
        arrowprops=dict(arrowstyle="->", lw=2, color="#2e7d32"),
    )
    ax.annotate(
        "",
        xy=(76, 76),
        xytext=(71, 76),
        arrowprops=dict(arrowstyle="<->", lw=2, color="#0288d1"),
    )
    ax.annotate(
        "",
        xy=(85, 60),
        xytext=(85, 68),
        arrowprops=dict(arrowstyle="<->", lw=2, color="#2e7d32"),
    )
    ax.annotate(
        "",
        xy=(66, 30),
        xytext=(74, 30),
        arrowprops=dict(arrowstyle="<-", lw=2, color="#d84315"),
    )
    ax.annotate(
        "",
        xy=(37, 30),
        xytext=(44, 30),
        arrowprops=dict(arrowstyle="<-", lw=2, color="#4e342e"),
    )
    ax.annotate(
        "",
        xy=(74, 20),
        xytext=(20, 48),
        arrowprops=dict(arrowstyle="<-", lw=1.5, color="#00897b", ls="--"),
    )

    save_figure(fig, "15_full_robot_block_diagram.png")


# ---------------------------------------------------------------------------
# Phase 6: Circuit Diagram (Deterministic Vector / High-Res)
# ---------------------------------------------------------------------------
def gen_circuit_diagram():
    fig, ax = setup_canvas(12, 8)
    ax.text(
        50,
        95,
        "Figure 6.3: Complete Electrical Schematic & Wiring Diagram",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    # Legend for line colors
    ax.add_patch(patches.Rectangle((70, 85), 26, 8, fc="#f8f9fa", ec="#6c757d", lw=1))
    ax.plot([72, 76], [90, 90], color="#d32f2f", lw=2.5)
    ax.text(
        77, 90, "POWER (+7.4V / +5.0V)", va="center", fontsize=7.5, fontweight="bold"
    )
    ax.plot([72, 76], [87, 87], color="#212121", lw=2.5)
    ax.text(77, 87, "COMMON GROUND (GND)", va="center", fontsize=7.5, fontweight="bold")
    ax.plot([72, 76], [84, 84], color="#1565c0", lw=2)
    ax.text(
        77, 84, "LOGIC / SENSOR SIGNAL", va="center", fontsize=7.5, fontweight="bold"
    )

    # Battery
    ax.add_patch(
        patches.FancyBboxPatch(
            (4, 55),
            14,
            25,
            boxstyle="round,pad=0.5",
            fc="#fff9c4",
            ec="#fbc02d",
            lw=1.8,
        )
    )
    ax.text(
        11,
        74,
        "BATTERY\n7.4V (2S)",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#e65100",
    )
    ax.text(
        11,
        62,
        "(+) 7.4V [Red]\n(-) GND [Black]",
        ha="center",
        fontsize=7.5,
        family="monospace",
    )

    # Buck Converter
    ax.add_patch(
        patches.FancyBboxPatch(
            (23, 55),
            16,
            25,
            boxstyle="round,pad=0.5",
            fc="#e8f5e9",
            ec="#388e3c",
            lw=1.8,
        )
    )
    ax.text(
        31,
        74,
        "BUCK CONVERTER\n(LM2596)",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#1b5e20",
    )
    ax.text(
        31,
        62,
        "IN+ / IN- (7.4V)\nOUT+ (+5.0V)\nOUT- (GND)",
        ha="center",
        fontsize=7.5,
        family="monospace",
    )

    # Arduino UNO
    ax.add_patch(
        patches.FancyBboxPatch(
            (46, 38), 24, 46, boxstyle="round,pad=0.8", fc="#e8f5e9", ec="#2e7d32", lw=2
        )
    )
    ax.text(
        58,
        80,
        "ARDUINO UNO R3",
        ha="center",
        fontsize=10,
        fontweight="bold",
        color="#1b5e20",
    )
    ax.text(
        48,
        73,
        "5V (Power In)    GND\nD0 (RX)          D1 (TX)\nD5 (ENA PWM)     D10 (ENB PWM)\nD6 (IN1)         D7 (IN2)\nD8 (IN3)         D9 (IN4)\nD11 (TRIG)       D12 (ECHO)",
        fontsize=7.2,
        family="monospace",
    )

    # ESP32-CAM
    ax.add_patch(
        patches.FancyBboxPatch(
            (76, 45), 20, 36, boxstyle="round,pad=0.8", fc="#e1f5fe", ec="#0288d1", lw=2
        )
    )
    ax.text(
        86,
        76,
        "ESP32-CAM",
        ha="center",
        fontsize=10,
        fontweight="bold",
        color="#01579b",
    )
    ax.text(
        78,
        68,
        "5V (VCC In)\nGND\n(data wires: none)\nOV2640 Bus",
        fontsize=7.2,
        family="monospace",
    )

    # Laptop (host): ESP32 video arrives over Wi-Fi, commands leave over USB serial
    ax.add_patch(
        patches.FancyBboxPatch(
            (68, 15),
            18,
            18,
            boxstyle="round,pad=0.4",
            fc="#ede7f6",
            ec="#512da8",
            lw=1.5,
        )
    )
    ax.text(
        77,
        28,
        "LAPTOP (HOST)",
        ha="center",
        fontsize=8,
        fontweight="bold",
        color="#4a148c",
    )
    ax.text(
        77,
        20,
        "Wi-Fi MJPEG in\nUSB serial out -> Arduino\n(D0/D1, 9600 baud)",
        ha="center",
        fontsize=7,
        family="monospace",
    )

    # L298N Driver
    ax.add_patch(
        patches.FancyBboxPatch(
            (23, 10), 20, 35, boxstyle="round,pad=0.8", fc="#ffe0b2", ec="#e65100", lw=2
        )
    )
    ax.text(
        33,
        40,
        "L298N DRIVER",
        ha="center",
        fontsize=9.5,
        fontweight="bold",
        color="#bf360c",
    )
    ax.text(
        25,
        32,
        "12V Terminal (7.4V Bat)\nGND (Common)\nENA / ENB (PWM)\nIN1-IN4 (Direction)\nOUT1/2 (Motor L)\nOUT3/4 (Motor R)",
        fontsize=7,
        family="monospace",
    )

    # Left & Right Motors
    ax.add_patch(
        patches.FancyBboxPatch(
            (4, 30),
            14,
            18,
            boxstyle="round,pad=0.5",
            fc="#fbe9e7",
            ec="#d84315",
            lw=1.5,
        )
    )
    ax.text(
        11, 42, "LEFT MOTOR\n(6V TT Gear)", ha="center", fontsize=8, fontweight="bold"
    )
    ax.add_patch(
        patches.FancyBboxPatch(
            (4, 8), 14, 18, boxstyle="round,pad=0.5", fc="#fbe9e7", ec="#d84315", lw=1.5
        )
    )
    ax.text(
        11, 20, "RIGHT MOTOR\n(6V TT Gear)", ha="center", fontsize=8, fontweight="bold"
    )

    # HC-SR04
    ax.add_patch(
        patches.FancyBboxPatch(
            (48, 10),
            16,
            20,
            boxstyle="round,pad=0.5",
            fc="#e0f2f1",
            ec="#00897b",
            lw=1.5,
        )
    )
    ax.text(
        56, 25, "HC-SR04", ha="center", fontsize=9, fontweight="bold", color="#004d40"
    )
    ax.text(
        56,
        17,
        "VCC (5V), GND\nTRIG (D11)\nECHO (D12)",
        ha="center",
        fontsize=7.2,
        family="monospace",
    )

    save_figure(fig, "circuit_diagram.png")


# ---------------------------------------------------------------------------
# Phase 19: 360-Degree Panoramic Scanning Diagram
# ---------------------------------------------------------------------------
def gen_360_degree_scan():
    fig, ax = setup_canvas(10, 7.5)
    ax.text(
        50,
        94,
        "Figure 19.1: Optional Extension — Discrete Panoramic Scanning System",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
    )

    angles = [0, 45, 90, 135, 180, 225, 270, 315]
    cx, cy, r = 50, 48, 28

    # Outer circle representing 360 scanning horizon
    circle = patches.Circle((cx, cy), r, fill=False, ec="#90a4ae", ls="--", lw=1.5)
    ax.add_patch(circle)

    # Robot in center
    ax.add_patch(
        patches.FancyBboxPatch(
            (cx - 8, cy - 8),
            16,
            16,
            boxstyle="round,pad=0.5",
            fc="#eceff1",
            ec="#37474f",
            lw=2,
        )
    )
    ax.text(
        cx,
        cy,
        "ESP32-CAM\n+\nSG90 SERVO",
        ha="center",
        va="center",
        fontsize=8,
        fontweight="bold",
    )

    for a in angles:
        rad = np.deg2rad(a)
        x = cx + r * np.sin(rad)
        y = cy + r * np.cos(rad)
        ax.plot([cx, x], [cy, y], color="#1565c0", ls=":", lw=1.2)
        ax.plot(x, y, "o", color="#0288d1", markersize=8)
        label = f"{a}°"
        if a == 0:
            label += " (Front)"
        elif a == 90:
            label += " (Right)"
        elif a == 180:
            label += " (Rear)"
        elif a == 270:
            label += " (Left)"
        ax.text(
            cx + (r + 4.5) * np.sin(rad),
            cy + (r + 4.5) * np.cos(rad),
            label,
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
            color="#0d47a1",
        )

    ax.text(
        50,
        10,
        "MODE CLASSIFICATION: DISCRETE PANORAMIC SCANNING (OPTIONAL EXTENSION)\n"
        "Camera stops at 8 discrete sector waypoints (45° steps) to eliminate motion blur during AI inference.\n"
        "DO NOT claim continuous 360-degree real-time panoramic computer vision.",
        ha="center",
        fontsize=8.5,
        fontweight="bold",
        color="#b71c1c",
        bbox=dict(boxstyle="round,pad=0.5", fc="#ffebee", ec="#c62828", lw=1.2),
    )

    save_figure(fig, "360_degree_scan_diagram.png")


def generate_all_diagrams():
    print("Generating comprehensive deterministic diagram suite...")
    gen_01_system_architecture()
    gen_02_data_flow()
    gen_03_hardware_architecture()
    gen_04_power_architecture()
    gen_05_esp32_pipeline()
    gen_06_decision_pipeline()
    gen_07_arduino_pipeline()
    gen_08_safety_hierarchy()
    gen_09_state_machine()
    gen_10_control_loop()
    gen_11_differential_drive_geometry()
    gen_12_and_13_zones()
    gen_14_communication_protocol()
    gen_15_full_robot_block_diagram()
    gen_circuit_diagram()
    gen_360_degree_scan()
    print("[SUCCESS] All deterministic diagrams and technical illustrations generated.")


if __name__ == "__main__":
    generate_all_diagrams()
