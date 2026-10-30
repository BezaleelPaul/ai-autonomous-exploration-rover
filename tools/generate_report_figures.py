"""Publication-grade Technical Diagram Generator for AI Exploration Rover Report.

Generates high-resolution diagrams:
1. architecture_blocks.png: Clean multi-tier system architecture
2. tb6612_wiring.png: Orthogonal electrical schematic with exact silkscreen & pinout
3. sequence_timing.png: Real-time command & safety sequence diagram
4. power_tree.png: Power distribution & star ground architecture
5. resurrection_flowchart.png: Layer-by-layer diagnostic & bring-up flowchart

Outputs to diagrams/ and figures/.
Run: py -3.12 tools/generate_report_figures.py
"""

from __future__ import annotations

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIAGRAMS = os.path.join(ROOT, "diagrams")
FIGURES = os.path.join(ROOT, "figures")
os.makedirs(DIAGRAMS, exist_ok=True)
os.makedirs(FIGURES, exist_ok=True)

def save_fig(fig, name: str):
    for folder in (DIAGRAMS, FIGURES):
        p = os.path.join(folder, name)
        fig.savefig(p, dpi=250, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved {name} to diagrams/ and figures/")


# ---------------------------------------------------------------------------
# 1. System Architecture
# ---------------------------------------------------------------------------
def generate_architecture():
    fig, ax = plt.subplots(figsize=(13.5, 8.2), dpi=250)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    # Header title banner
    ax.text(50, 97, "AI-ASSISTED AUTONOMOUS EXPLORATION ROVER — SYSTEM ARCHITECTURE",
            ha="center", va="center", fontsize=13.5, fontweight="bold", color="#0F2D1E")
    ax.text(50, 94.2, "Three-Tier Distributed Control: User Interface  |  Wireless & Reflex Embedded Core  |  Perception & Physical Actuation",
            ha="center", va="center", fontsize=9.2, color="#4A5568")

    # Subgraph backgrounds (grouping cards)
    # 1. Operator / AI Tier (Left)
    ax.add_patch(patches.FancyBboxPatch((2, 6), 26, 85, boxstyle="round,pad=0.8",
                                        fc="#F0F4F8", ec="#94A3B8", lw=1.2, ls="--"))
    ax.text(15, 88.5, "OPERATOR & AI TIER", ha="center", fontsize=10, fontweight="bold", color="#1E293B")

    # 2. On-Rover Embedded Compute (Center)
    ax.add_patch(patches.FancyBboxPatch((31, 6), 36, 85, boxstyle="round,pad=0.8",
                                        fc="#F0FDF4", ec="#86EFAC", lw=1.2))
    ax.text(49, 88.5, "ON-ROVER DUAL-CORE EMBEDDED SYSTEM", ha="center", fontsize=10, fontweight="bold", color="#166534")

    # 3. Hardware Actuation & Sensing (Right)
    ax.add_patch(patches.FancyBboxPatch((70, 6), 28, 85, boxstyle="round,pad=0.8",
                                        fc="#FFFBEB", ec="#FCD34D", lw=1.2))
    ax.text(84, 88.5, "ACTUATION & SENSORS", ha="center", fontsize=10, fontweight="bold", color="#92400E")

    # Function to draw styled module cards
    def card(x, y, w, h, title, subtitle, items, header_bg, body_bg="#FFFFFF", border="#CBD5E1"):
        ax.add_patch(patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5",
                                            fc=body_bg, ec=border, lw=1.4))
        # Card header pill
        header_h = 4.2
        ax.add_patch(patches.FancyBboxPatch((x, y + h - header_h), w, header_h,
                                            boxstyle="round,pad=0.2",
                                            fc=header_bg, ec="none"))
        ax.text(x + w / 2, y + h - 2.1, title, ha="center", va="center",
                fontsize=9.2, fontweight="bold", color="#FFFFFF")
        if subtitle:
            ax.text(x + w / 2, y + h - 5.5, subtitle, ha="center", va="center",
                    fontsize=7.8, fontweight="bold", color="#334155")
        start_y = y + h - (7.2 if subtitle else 6.0)
        for i, item in enumerate(items):
            ax.text(x + 1.2, start_y - (i * 3.3), f"• {item}", ha="left", va="center",
                    fontsize=7.5, color="#334155")

    # --- Operator Tier Modules ---
    card(4, 52, 22, 33, "SMARTPHONE UI", "Driver Cockpit & Camera",
         ["IP Webcam MJPEG (:8080)",
          "Wi-Fi AP: AI_Rover_Control",
          "Web Pad: 192.168.4.1",
          "Hold-to-drive touch UI",
          "PWM Speed Slider (60-255)",
          "Live telemetry HUD overlay",
          "Sub-200ms touch response"],
         header_bg="#2563EB", body_bg="#EFF6FF", border="#93C5FD")

    card(4, 10, 22, 37, "LAPTOP AI TIER", "Perception & Mission Deck",
         ["Intel Core / OpenVINO CPU",
          "YOLO11n @ 320px (5-6 FPS)",
          "3-Zone Autonomous Steering",
          "ai_video_server.py (MJPEG)",
          "perception_node (Auto F/L/R/S)",
          "Emergency spacebar STOP",
          "Camera-freeze watchdog",
          "Telemetry record & logging"],
         header_bg="#4F46E5", body_bg="#EEF2FF", border="#A5B4FC")

    # --- Embedded Compute Modules ---
    card(33, 52, 32, 33, "ESP32 DEVKIT V1", "Wireless Gateway Bridge",
         ["Soft-AP 'AI_Rover_Control'",
          "HTTP Web Server (:80)",
          "REST endpoint: /cmd?c=F200",
          "Whitelist validator (F,B,L,R,S)",
          "Speed clamp (60-255 PWM)",
          "Hardware UART2 (GPIO17 TX2)",
          "One-way 3.3V->5V safe link",
          "Uptime & dropped packet JSON"],
         header_bg="#059669", body_bg="#F0FDF4", border="#86EFAC")

    card(33, 10, 32, 37, "ARDUINO UNO R3", "Real-Time Reflex Core",
         ["motion_safety.ino (7.5 KB)",
          "Gap-framed parser (15ms silence)",
          "15 cm ultrasonic forward gate",
          "500 ms link watchdog failsafe",
          "Non-blocking millis/micros FSM",
          "Dead-sensor block (DIST: -1)",
          "Dual PWM timer outputs (D5, D9)",
          "Direction GPIOs (D6, D7, D8, D10)",
          "USB live telemetry (9600 baud)"],
         header_bg="#0D9488", body_bg="#F0FDFA", border="#99F6E4")

    # --- Actuation & Sensor Modules ---
    card(72, 64, 24, 21, "2S LI-ION PACK", "7.4V Nominal Power Source",
         ["2x 18650 Li-ion cells",
          "SPST Rocker master switch",
          "Inline 3A fast fuse",
          "DIRECT heavy gauge wires",
          "NO breadboard rail flow"],
         header_bg="#DC2626", body_bg="#FEF2F2", border="#FCA5A5")

    card(72, 34, 24, 27, "TB6612FNG DRIVER", "Dual MOSFET H-Bridge",
         ["< 0.2V drop (replaces L298N)",
          "VM: 7.4V direct battery power",
          "VCC & STBY: 5V Arduino power",
          "PWMA (D5) / PWMB (D9)",
          "AIN1(D6), AIN2(D7), BIN1(D8), BIN2(D10)",
          "Silkscreen: AIN2 left of AIN1!",
          "PWMB at far right header pin"],
         header_bg="#D97706", body_bg="#FFFBEB", border="#FDE68A")

    card(72, 10, 24, 21, "SENSING & MOTORS", "Physical Hardware",
         ["HC-SR04 Sonar (Trig D2 / Echo D3)",
          "Dedicated 5V/GND from Arduino",
          "Left Motor: TT 1:48 (AO1/AO2)",
          "Right Motor: TT 1:48 (BO1/BO2)",
          "Chassis: Acrylic differential-drive"],
         header_bg="#475569", body_bg="#F8FAFC", border="#CBD5E1")

    # Clean orthogonal and curved arrows with non-colliding labels
    def arrow(x1, y1, x2, y2, label="", color="#1E293B", rad=0.0, lw=1.8, ls="-", label_y_offset=0.0):
        connection = f"arc3,rad={rad}" if rad != 0 else "arc3,rad=0"
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(arrowstyle="->,head_width=0.35,head_length=0.45",
                            color=color, lw=lw, ls=ls,
                            connectionstyle=connection)
        )
        if label:
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2 + label_y_offset
            ax.text(mx, my, label, ha="center", va="center", fontsize=7.2,
                    fontweight="bold", color=color,
                    bbox=dict(boxstyle="round,pad=0.22", fc="#FFFFFF", ec=color, lw=0.9))

    # 1. Phone -> ESP32: HTTP GET /cmd
    arrow(26, 68, 33, 68, "HTTP GET /cmd?c=F200\n(Wi-Fi 2.4 GHz)", color="#2563EB", lw=2.0)

    # 2. Phone -> Laptop: Video Stream
    arrow(15, 52, 15, 47, "MJPEG Video Stream (:8080)", color="#4F46E5", lw=1.8, ls="--")

    # 3. Laptop -> ESP32: Autonomous commands
    arrow(26, 32, 33, 58, "Autonomous HTTP\n/cmd?c=F/L/R", color="#4F46E5", rad=0.15, lw=1.8, ls="--")

    # 4. ESP32 -> Arduino: UART Link
    arrow(49, 52, 49, 47, "One-Way UART Link @ 9600 8N1\nGPIO17 (TX2) → Uno D4 (RX)", color="#059669", lw=2.2)

    # 5. Arduino -> Laptop: Telemetry
    arrow(33, 20, 26, 20, "USB Telemetry & Logging\n(DIST, CMD, STATE, ALERTS)", color="#0D9488", lw=1.8, ls=":")

    # 6. Battery -> TB6612: VM Power
    arrow(84, 64, 84, 61, "7.4V VM Direct Power (No Breadboard)", color="#DC2626", lw=2.4)

    # 7. Arduino -> TB6612: Logic & PWM
    arrow(65, 42, 72, 42, "PWM (D5, D9) + Dir (D6-D8, D10)\n+ 5V Logic & STBY", color="#D97706", lw=2.0)

    # 8. TB6612 -> Motors
    arrow(84, 34, 84, 31, "AO1/AO2 (Left) & BO1/BO2 (Right)", color="#92400E", lw=2.2)

    # 9. Arduino <-> Sonar
    arrow(65, 18, 72, 18, "Trig D2 / Echo D3\n+ 5V/GND Direct", color="#0D9488", lw=1.8)

    # Bottom Safety & Status Banner
    ax.add_patch(patches.FancyBboxPatch((2, 0.8), 96, 4.2, boxstyle="round,pad=0.3",
                                        fc="#0F2D1E", ec="none"))
    ax.text(50, 2.9, "SYSTEM SAFETY GUARANTEES: Boot-Stopped State  |  15 cm Hardware Sonar Gate  |  500 ms Radio Watchdog  |  Input Whitelist Armor",
            ha="center", va="center", fontsize=8.2, fontweight="bold", color="#A7F3D0")

    save_fig(fig, "architecture_blocks.png")


# ---------------------------------------------------------------------------
# 2. Complete TB6612FNG Electrical Schematic (Orthogonal, Cleanly Routed)
# ---------------------------------------------------------------------------
def generate_tb6612_schematic():
    fig, ax = plt.subplots(figsize=(14.0, 9.0), dpi=250)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    ax.text(50, 97, "TB6612FNG DUAL MOTOR DRIVER & CONTROLLER WIRING SCHEMATIC",
            ha="center", va="center", fontsize=13.5, fontweight="bold", color="#1E293B")
    ax.text(50, 94.2, "Verified Production Pinout: Heavy Direct Power Wires  |  Common Star Ground  |  Non-Conflicting GPIO Allocation",
            ha="center", va="center", fontsize=9.0, color="#4A5568")

    # Helper to draw an IC / Component block with pins
    def draw_ic(x, y, w, h, title, left_pins=(), right_pins=(), top_pins=(), bottom_pins=(),
                fill="#F8FAFC", border="#334155"):
        ax.add_patch(patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3",
                                            fc=fill, ec=border, lw=1.6))
        ax.text(x + w/2, y + h - 2.5, title, ha="center", va="center",
                fontsize=9.2, fontweight="bold", color="#0F172A")
        pin_coords = {}

        # Left pins
        if left_pins:
            step = (h - 5) / (len(left_pins) + 1)
            for i, p in enumerate(left_pins):
                py = y + h - 4 - (i + 1) * step
                ax.plot([x - 1.2, x], [py, py], color=border, lw=1.2)
                ax.text(x + 0.6, py, p, ha="left", va="center", fontsize=7.2, color="#1E293B", family="monospace")
                pin_coords[p] = (x - 1.2, py)

        # Right pins
        if right_pins:
            step = (h - 5) / (len(right_pins) + 1)
            for i, p in enumerate(right_pins):
                py = y + h - 4 - (i + 1) * step
                ax.plot([x + w, x + w + 1.2], [py, py], color=border, lw=1.2)
                ax.text(x + w - 0.6, py, p, ha="right", va="center", fontsize=7.2, color="#1E293B", family="monospace")
                pin_coords[p] = (x + w + 1.2, py)

        # Top pins
        if top_pins:
            step = w / (len(top_pins) + 1)
            for i, p in enumerate(top_pins):
                px = x + (i + 1) * step
                ax.plot([px, px], [y + h, y + h + 1.2], color=border, lw=1.2)
                ax.text(px, y + h - 2, p, ha="center", va="top", fontsize=7.0, color="#1E293B", family="monospace")
                pin_coords[p] = (px, y + h + 1.2)

        # Bottom pins
        if bottom_pins:
            step = w / (len(bottom_pins) + 1)
            for i, p in enumerate(bottom_pins):
                px = x + (i + 1) * step
                ax.plot([px, px], [y - 1.2, y], color=border, lw=1.2)
                ax.text(px, y + 2, p, ha="center", va="bottom", fontsize=7.0, color="#1E293B", family="monospace")
                pin_coords[p] = (px, y - 1.2)

        return pin_coords

    # Components Placement:
    # 1. 2S Battery Pack (Top Left)
    batt_pins = draw_ic(4, 73, 16, 16, "2S LI-ION PACK\n7.4V Nominal",
                        right_pins=["V+", "V-"], fill="#FEF2F2", border="#DC2626")

    # 2. SPST Rocker Switch & Fuse (Top Center-Left)
    sw_pins = draw_ic(26, 75, 14, 12, "ROCKER SWITCH\n+ 3A Inline Fuse",
                      left_pins=["IN"], right_pins=["OUT"], fill="#FEF2F2", border="#DC2626")

    # 3. HC-SR04 Ultrasonic Sensor (Top Center-Right)
    sonar_pins = draw_ic(46, 74, 20, 14, "HC-SR04 ULTRASONIC\nObstacle Reflex Gate",
                         bottom_pins=["VCC", "TRIG", "ECHO", "GND"], fill="#F0FDFA", border="#0D9488")

    # 4. ESP32 DevKit V1 (Bottom Left)
    esp_pins = draw_ic(4, 10, 18, 16, "ESP32 DEVKIT V1\nWi-Fi Teleop Bridge",
                       right_pins=["GPIO17 (TX2)", "GND"], fill="#EFF6FF", border="#2563EB")

    # 5. Arduino Uno R3 (Center Left)
    uno_pins = draw_ic(28, 10, 24, 54, "ARDUINO UNO R3\nReflex Safety Core",
                       top_pins=["5V", "GND_TOP"],
                       left_pins=["D4 (RX)", "GND_IN"],
                       right_pins=["D2 (TRIG)", "D3 (ECHO)", "D5 (PWMA)", "D6 (AIN1)",
                                   "D7 (AIN2)", "D8 (BIN1)", "D9 (PWMB)", "D10 (BIN2)"],
                       fill="#F0FDF4", border="#16A34A")

    # 6. TB6612FNG Motor Driver (Center Right)
    tb_pins = draw_ic(60, 10, 22, 54, "TB6612FNG H-BRIDGE\nDual MOSFET (<0.2V Drop)",
                      top_pins=["VM (7.4V)", "GND_PWR"],
                      left_pins=["PWMA", "AIN2*", "AIN1*", "STBY", "BIN1", "BIN2", "PWMB*", "VCC", "GND_LOGIC"],
                      right_pins=["AO1", "AO2", "BO1", "BO2"],
                      fill="#FFFBEB", border="#D97706")

    # 7. Left Motor (Far Right Top)
    ml_pins = draw_ic(89, 44, 8, 16, "LEFT MOTOR\nTT 1:48 Gear",
                      left_pins=["M1+", "M1-"], fill="#F8FAFC", border="#475569")

    # 8. Right Motor (Far Right Bottom)
    mr_pins = draw_ic(89, 14, 8, 16, "RIGHT MOTOR\nTT 1:48 Gear",
                      left_pins=["M2+", "M2-"], fill="#F8FAFC", border="#475569")

    # Wire drawing helper with orthogonal routing
    def wire(p1, p2, color="#1E293B", lw=1.6, ls="-", label="", label_pos=0.5):
        x1, y1 = p1
        x2, y2 = p2
        # Orthogonal path: horizontal then vertical or vice versa
        mid_x = x1 + (x2 - x1) * 0.5
        ax.plot([x1, mid_x, mid_x, x2], [y1, y1, y2, y2], color=color, lw=lw, ls=ls)
        ax.plot([x1], [y1], "o", color=color, markersize=3.5)
        ax.plot([x2], [y2], "o", color=color, markersize=3.5)
        if label:
            lx = mid_x
            ly = (y1 + y2) * 0.5 if abs(y2 - y1) > 2 else y1 + 1.2
            ax.text(lx, ly, label, ha="center", va="center", fontsize=6.8,
                    fontweight="bold", color=color,
                    bbox=dict(boxstyle="round,pad=0.18", fc="#FFFFFF", ec=color, lw=0.7))

    # --- Connections ---
    # Power Path 1: Battery V+ -> Switch IN
    wire(batt_pins["V+"], sw_pins["IN"], color="#DC2626", lw=2.2, label="7.4V UNREG")

    # Power Path 2: Switch OUT -> TB6612 VM (Direct Heavy Wire)
    sw_out = sw_pins["OUT"]
    vm_in = tb_pins["VM (7.4V)"]
    ax.plot([sw_out[0], 66, 66, vm_in[0]], [sw_out[1], sw_out[1], vm_in[1] + 2, vm_in[1]],
            color="#DC2626", lw=2.4)
    ax.text(66, 75, "VM: Heavy Direct Wire (No Breadboard Rail)", ha="center", va="bottom",
            fontsize=7.2, fontweight="bold", color="#DC2626",
            bbox=dict(boxstyle="round,pad=0.2", fc="#FFFFFF", ec="#DC2626", lw=0.8))

    # Power Path 3: Battery V- -> TB6612 GND_PWR (Star Ground Junction)
    batt_neg = batt_pins["V-"]
    gnd_pwr = tb_pins["GND_PWR"]
    ax.plot([batt_neg[0], 76, 76, gnd_pwr[0]], [batt_neg[1], batt_neg[1], gnd_pwr[1] + 2, gnd_pwr[1]],
            color="#1E293B", lw=2.4)
    ax.text(76, 72, "BATTERY (-) STAR GROUND", ha="center", va="bottom",
            fontsize=7.0, fontweight="bold", color="#1E293B",
            bbox=dict(boxstyle="round,pad=0.2", fc="#FFFFFF", ec="#1E293B", lw=0.8))

    # Uno 5V & GND to Sonar
    wire(uno_pins["5V"], sonar_pins["VCC"], color="#EA580C", lw=1.6, label="5V REG")
    wire(uno_pins["GND_TOP"], sonar_pins["GND"], color="#1E293B", lw=1.6, label="GND")
    wire(uno_pins["D2 (TRIG)"], sonar_pins["TRIG"], color="#0D9488", lw=1.5, label="TRIG (D2)")
    wire(uno_pins["D3 (ECHO)"], sonar_pins["ECHO"], color="#0D9488", lw=1.5, label="ECHO (D3)")

    # ESP32 -> Uno UART & Ground
    wire(esp_pins["GPIO17 (TX2)"], uno_pins["D4 (RX)"], color="#2563EB", lw=2.0, label="UART 9600 8N1")
    wire(esp_pins["GND"], uno_pins["GND_IN"], color="#1E293B", lw=1.8, label="STAR GND")

    # Uno -> TB6612 PWM & Direction Signals
    # Exact mappings matching firmware truth:
    # D5 -> PWMA, D6 -> AIN1, D7 -> AIN2, D8 -> BIN1, D9 -> PWMB, D10 -> BIN2
    signal_pairs = [
        ("D5 (PWMA)", "PWMA", "#D97706"),
        ("D7 (AIN2)", "AIN2*", "#B45309"),
        ("D6 (AIN1)", "AIN1*", "#B45309"),
        ("D8 (BIN1)", "BIN1", "#78350F"),
        ("D10 (BIN2)", "BIN2", "#78350F"),
        ("D9 (PWMB)", "PWMB*", "#D97706"),
    ]
    for u_pin, t_pin, col in signal_pairs:
        p1 = uno_pins[u_pin]
        p2 = tb_pins[t_pin]
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=col, lw=1.5)
        ax.plot([p1[0]], [p1[1]], "o", color=col, markersize=3)
        ax.plot([p2[0]], [p2[1]], "o", color=col, markersize=3)

    # 5V and STBY tie to Arduino 5V
    p_stby = tb_pins["STBY"]
    p_vcc = tb_pins["VCC"]
    ax.plot([uno_pins["5V"][0], 55, 55, p_stby[0]], [uno_pins["5V"][1], uno_pins["5V"][1], p_stby[1], p_stby[1]],
            color="#EA580C", lw=1.6)
    ax.plot([55, p_vcc[0]], [p_vcc[1], p_vcc[1]], color="#EA580C", lw=1.6)
    ax.text(55, p_stby[1] + 1.2, "5V STBY + VCC", ha="center", fontsize=6.8, fontweight="bold", color="#EA580C",
            bbox=dict(boxstyle="round,pad=0.15", fc="#FFFFFF", ec="#EA580C", lw=0.6))

    # Common ground tie: TB6612 GND_LOGIC -> Uno GND
    p_gnd_log = tb_pins["GND_LOGIC"]
    ax.plot([p_gnd_log[0], 54, 54, uno_pins["GND_IN"][0]], [p_gnd_log[1], p_gnd_log[1], uno_pins["GND_IN"][1] - 2, uno_pins["GND_IN"][1] - 2],
            color="#1E293B", lw=1.6)

    # TB6612 -> Left Motor (AO1, AO2)
    wire(tb_pins["AO1"], ml_pins["M1+"], color="#334155", lw=1.8, label="AO1")
    wire(tb_pins["AO2"], ml_pins["M1-"], color="#334155", lw=1.8, label="AO2")

    # TB6612 -> Right Motor (BO1, BO2)
    wire(tb_pins["BO1"], mr_pins["M2+"], color="#334155", lw=1.8, label="BO1")
    wire(tb_pins["BO2"], mr_pins["M2-"], color="#334155", lw=1.8, label="BO2")

    # Silk screen critical warning banner
    ax.add_patch(patches.FancyBboxPatch((28, 2.5), 68, 5.2, boxstyle="round,pad=0.3",
                                        fc="#FEF3C7", ec="#D97706", lw=1.2))
    ax.text(62, 5.1, "CRITICAL SILKSCREEN TRAP DOCUMENTED (§3.2):",
            ha="center", va="center", fontsize=7.8, fontweight="bold", color="#92400E")
    ax.text(62, 3.6, "1) AIN2 sits BEFORE AIN1 on the board header.  2) PWMB is located at the far right header end (NOT next to STBY).",
            ha="center", va="center", fontsize=7.2, color="#78350F")

    save_fig(fig, "tb6612_wiring.png")


# ---------------------------------------------------------------------------
# 3. Real-Time Command & Timing Sequence Diagram
# ---------------------------------------------------------------------------
def generate_sequence_timing():
    fig, ax = plt.subplots(figsize=(13.0, 7.5), dpi=250)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    ax.text(50, 96, "ROVER REAL-TIME CONTROL & SAFETY SEQUENCE DIAGRAM",
            ha="center", va="center", fontsize=13.0, fontweight="bold", color="#0F2D1E")
    ax.text(50, 93, "Deterministic Message Flow, Sonar Gating, and Link Watchdog Lifecycle",
            ha="center", va="center", fontsize=8.8, color="#4A5568")

    # Lifelines:
    actors = [
        ("PHONE UI\n(Touch Pad)", 12, "#2563EB"),
        ("ESP32 BRIDGE\n(Soft-AP :80)", 34, "#059669"),
        ("UNO REFLEX\n(motion_safety)", 58, "#0D9488"),
        ("TB6612 / MOTORS\n(H-Bridge)", 84, "#D97706"),
    ]

    for title, x, col in actors:
        ax.add_patch(patches.FancyBboxPatch((x - 9, 83), 18, 7, boxstyle="round,pad=0.3",
                                            fc=col, ec="none"))
        ax.text(x, 86.5, title, ha="center", va="center", fontsize=8.2, fontweight="bold", color="#FFFFFF")
        ax.plot([x, x], [12, 83], color="#CBD5E1", lw=1.5, ls="--")

    # Step generator helper
    def msg(y, x1, x2, text, col="#1E293B", ls="-", note="", lw=1.6):
        ax.annotate("", xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle="->,head_width=0.35,head_length=0.45",
                                    color=col, lw=lw, ls=ls))
        mx = (x1 + x2) / 2
        ax.text(mx, y + 1.8, text, ha="center", va="bottom", fontsize=7.6, fontweight="bold", color=col)
        if note:
            ax.text(mx, y - 1.8, note, ha="center", va="top", fontsize=6.8, color="#64748B")

    # Sequence steps:
    # 1. User holds forward button
    msg(76, 12, 34, "HTTP GET /cmd?c=F200", col="#2563EB", note="Repeated every 200 ms while pressed")

    # 2. ESP32 validates whitelist and sends UART
    msg(70, 34, 58, "UART Bytes: 'F200'", col="#059669", note="9600 baud, 15ms gap framing delimiter")

    # 3. Uno checks obstacle sensor
    ax.add_patch(patches.Rectangle((53, 61), 10, 5, fc="#F0FDFA", ec="#0D9488", lw=1.2))
    ax.text(58, 63.5, "Non-blocking Sonar Check\n(DIST >= 15 cm ?)", ha="center", va="center",
            fontsize=6.8, fontweight="bold", color="#0D9488")

    # 4. Path is clear -> Motor PWM driven
    msg(55, 58, 84, "PWM=193, AIN1=HIGH, AIN2=LOW", col="#D97706", note="Both wheels drive forward with full torque")

    # 5. Continuous keep-alive ticks
    msg(47, 12, 34, "HTTP GET /cmd?c=F200 (tick 2)", col="#2563EB", note="Watchdog timer reset on reception")
    msg(42, 34, 58, "UART: 'F200'", col="#059669", note="Refreshes 500 ms safety deadline")

    # 6. Obstacle detected condition
    ax.add_patch(patches.FancyBboxPatch((8, 25), 84, 13, boxstyle="round,pad=0.5",
                                        fc="#FEF2F2", ec="#EF4444", lw=1.2))
    ax.text(12, 35, "EVENT: OBSTACLE DETECTED (< 15 cm) OR USER RELEASES PAD", fontsize=8.0,
            fontweight="bold", color="#B91C1C")

    # Arrow inside obstacle box: Sonar gate halts forward
    msg(30, 58, 84, "EMERGENCY MOTOR STOP (PWM=0)", col="#DC2626", lw=2.2,
        note="15 cm gate halts F; B/L/R escape commands still permitted")

    # Arrow inside obstacle box: Telemetry output
    msg(27, 58, 12, "USB / HUD: 'ALERT:OBSTACLE dist=11cm cmd=F'", col="#B91C1C", ls=":")

    # 7. Watchdog timeout scenario
    ax.text(50, 16.5, "FAILSAFE 2: Radio Link Silence > 500 ms -> Immediate Automatic STATE:TIMEOUT Stop",
            ha="center", fontsize=8.0, fontweight="bold", color="#B45309",
            bbox=dict(boxstyle="round,pad=0.3", fc="#FEF3C7", ec="#F59E0B", lw=1.0))

    save_fig(fig, "sequence_timing.png")


# ---------------------------------------------------------------------------
# 4. Power Distribution & Star Ground Architecture
# ---------------------------------------------------------------------------
def generate_power_tree():
    fig, ax = plt.subplots(figsize=(12.5, 7.0), dpi=250)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    ax.text(50, 96, "ROVER POWER DISTRIBUTION TREE & STAR GROUND TOPOLOGY",
            ha="center", va="center", fontsize=13.0, fontweight="bold", color="#0F2D1E")
    ax.text(50, 93, "Separation of High-Current Motor Rails from Sensitive 5V/3.3V Logic Rails",
            ha="center", va="center", fontsize=8.8, color="#4A5568")

    # Power Source Card
    ax.add_patch(patches.FancyBboxPatch((4, 52), 22, 34, boxstyle="round,pad=0.5",
                                        fc="#FEF2F2", ec="#DC2626", lw=1.6))
    ax.text(15, 81, "2S LI-ION PACK\n7.4V Nominal (8.4V Peak)", ha="center", fontsize=9.2, fontweight="bold", color="#991B1B")
    ax.text(15, 71, "• 2x 18650 Li-ion cells\n• Peak discharge: ~15A\n• SPST master rocker\n• 3A fast blow fuse",
            ha="center", fontsize=7.8, color="#4B5563")

    # High-current Rail (Top)
    ax.add_patch(patches.FancyBboxPatch((38, 56), 26, 30, boxstyle="round,pad=0.5",
                                        fc="#FFFBEB", ec="#D97706", lw=1.6))
    ax.text(51, 81, "HIGH-CURRENT RAIL\n(Motor Power: VM)", ha="center", fontsize=9.2, fontweight="bold", color="#92400E")
    ax.text(51, 69, "• Heavy 20 AWG direct wires\n• ZERO breadboard rail flow\n• TB6612 VM input\n• Motor stall surge: 1.5–2.0A",
            ha="center", fontsize=7.8, color="#78350F")

    # Actuators (Top Right)
    ax.add_patch(patches.FancyBboxPatch((74, 56), 22, 30, boxstyle="round,pad=0.5",
                                        fc="#F8FAFC", ec="#64748B", lw=1.6))
    ax.text(85, 81, "TT GEARMOTORS\n(2x 1:48 Differential)", ha="center", fontsize=9.2, fontweight="bold", color="#1E293B")
    ax.text(85, 69, "• Left: AO1/AO2 tabs\n• Right: BO1/BO2 tabs\n• Direct soldered harness\n• Full torque delivered",
            ha="center", fontsize=7.8, color="#475569")

    # Logic Rail (Bottom)
    ax.add_patch(patches.FancyBboxPatch((38, 10), 26, 36, boxstyle="round,pad=0.5",
                                        fc="#F0FDF4", ec="#16A34A", lw=1.6))
    ax.text(51, 41, "LOGIC POWER BUS\n(Arduino 5V Regulator)", ha="center", fontsize=9.2, fontweight="bold", color="#166534")
    ax.text(51, 26, "• Uno 5V internal LDO\n• TB6612 VCC logic\n• TB6612 STBY enable\n• HC-SR04 sonar VCC\n• Low current (<150 mA)",
            ha="center", fontsize=7.8, color="#15803D")

    # Logic Devices (Bottom Right)
    ax.add_patch(patches.FancyBboxPatch((74, 10), 22, 36, boxstyle="round,pad=0.5",
                                        fc="#EFF6FF", ec="#2563EB", lw=1.6))
    ax.text(85, 41, "MICROCONTROLLERS\n& SENSORS", ha="center", fontsize=9.2, fontweight="bold", color="#1E40AF")
    ax.text(85, 26, "• Arduino Uno R3 (5V)\n• ESP32 DevKit V1 (3.3V)\n• HC-SR04 Sonar\n• Dedicated GND paths\n• No brownout risk",
            ha="center", fontsize=7.8, color="#1D4ED8")

    # Arrows
    def p_arrow(x1, y1, x2, y2, label, col):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->,head_width=0.4,head_length=0.5", color=col, lw=2.2))
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2
        ax.text(mx, my + 2, label, ha="center", va="bottom", fontsize=7.5, fontweight="bold", color=col,
                bbox=dict(boxstyle="round,pad=0.2", fc="#FFFFFF", ec=col, lw=0.8))

    p_arrow(26, 71, 38, 71, "7.4V Direct Wire", "#DC2626")
    p_arrow(64, 71, 74, 71, "H-Bridge Switched Power", "#D97706")
    p_arrow(15, 52, 38, 28, "Arduino Barrel / USB Jack", "#16A34A")
    p_arrow(64, 28, 74, 28, "5V Regulated Rail", "#16A34A")

    # Star Ground Callout Box
    ax.add_patch(patches.FancyBboxPatch((4, 10), 28, 36, boxstyle="round,pad=0.5",
                                        fc="#F8FAFC", ec="#0F172A", lw=1.6))
    ax.text(18, 41, "COMMON STAR GROUND\n(Zero Ground Loops)", ha="center", fontsize=9.0, fontweight="bold", color="#0F172A")
    ax.text(18, 24, "• Battery (-) lug\n• TB6612 PGND\n• Arduino Uno GND\n• ESP32 DevKit GND\n\nPrevents motor noise\nfrom resetting Uno/ESP32",
            ha="center", fontsize=7.6, color="#334155")

    save_fig(fig, "power_tree.png")


# ---------------------------------------------------------------------------
# 5. Resurrection Flowchart (Bring-up & Fault Isolation)
# ---------------------------------------------------------------------------
def generate_resurrection_flowchart():
    fig, ax = plt.subplots(figsize=(13.0, 7.8), dpi=250)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    ax.text(50, 96, "SYSTEM RESURRECTION & LAYER-BY-LAYER BRING-UP FLOWCHART",
            ha="center", va="center", fontsize=13.0, fontweight="bold", color="#0F2D1E")
    ax.text(50, 93, "Methodical Hardware & Firmware Isolation Protocol Executed on October 29, 2026",
            ha="center", va="center", fontsize=8.8, color="#4A5568")

    # Flowchart steps
    def step_box(x, y, w, h, step_no, title, desc, fc="#F8FAFC", ec="#64748B", tc="#0F172A"):
        ax.add_patch(patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4",
                                            fc=fc, ec=ec, lw=1.4))
        ax.text(x + 1.5, y + h - 2.4, f"STEP {step_no}: {title}", ha="left", va="center",
                fontsize=8.2, fontweight="bold", color=tc)
        ax.text(x + 1.5, y + (h - 2.4) / 2, desc, ha="left", va="center",
                fontsize=7.2, color="#334155")

    # Step 1: Initial failure
    step_box(4, 76, 27, 13, "1", "WHEELS COMPLETELY DEAD",
             "Motors emit faint hum but do not turn.\nSuspect: Motor driver, battery pack, or code.",
             fc="#FEF2F2", ec="#EF4444", tc="#B91C1C")

    # Step 2: Direct Battery Test
    step_box(36, 76, 27, 13, "2", "DIRECT BATTERY TOUCH TEST",
             "7.4V directly applied to TT motor tabs.\nResult: BOTH motors spin at high RPM.\nConclusion: Battery & motors healthy!",
             fc="#F0FDF4", ec="#22C55E", tc="#15803D")

    # Step 3: Breadboard Rail Split Discovery
    step_box(68, 76, 28, 13, "3", "POWER PATH AUDIT",
             "Found: Breadboard power rail has middle split!\nMotor current was routed through flimsy jumpers,\ncausing severe voltage drop under stall load.",
             fc="#FFFBEB", ec="#F59E0B", tc="#B45309")

    # Step 4: Direct Wiring Fix
    step_box(68, 45, 28, 13, "4", "DIRECT POWER WIRING FIX",
             "Removed motor current from breadboard.\nSoldered direct 20 AWG wires from battery\nthrough switch to TB6612 VM and GND.",
             fc="#F0FDF4", ec="#22C55E", tc="#15803D")

    # Step 5: Silkscreen Pinout Trap
    step_box(36, 45, 27, 13, "5", "TB6612 SILKSCREEN AUDIT",
             "Discovered critical hardware pin traps:\n1. AIN2 sits BEFORE AIN1.\n2. PWMB is at far end of row.\nRewired Arduino D5-D10 exactly to pins.",
             fc="#FFFBEB", ec="#F59E0B", tc="#B45309")

    # Step 6: Wheel Bring-up Sketch
    step_box(4, 45, 27, 13, "6", "WHEEL_TEST_HOLD.INO VERIFICATION",
             "Flashed isolated full-torque test.\nBoth wheels spun forward, reverse, and turn\nat full torque without stutter or stall!",
             fc="#F0FDF4", ec="#22C55E", tc="#15803D")

    # Step 7: Full Stack Integration
    step_box(4, 12, 42, 18, "7", "PRODUCTION FIRMWARE INTEGRATION",
             "Flashed motion_safety.ino (Uno) + wifi_bridge.ino (ESP32).\n"
             "• 15 cm forward obstacle gate verified live with HC-SR04\n"
             "• 500 ms link watchdog verified upon Wi-Fi disconnect\n"
             "• Whitelist validation rejecting malformed inputs",
             fc="#F0FDFA", ec="#0D9488", tc="#0F766E")

    # Step 8: Live Wi-Fi Drive Proven
    step_box(52, 12, 44, 18, "8", "LIVE WI-FI DRIVE PAD & AI PERCEPTION PROVEN",
             "Complete system operating live and robust:\n"
             "• Touch pad on smartphone holds rover in continuous drive\n"
             "• PWM slider dynamically modulates speed (60-255 PWM)\n"
             "• Laptop AI tier running YOLO11n object tracking\n"
             "• 98 automated contract tests passing in test suite",
             fc="#EFF6FF", ec="#3B82F6", tc="#1D4ED8")

    # Flow arrows
    def f_arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->,head_width=0.35,head_length=0.45",
                                    color="#0F172A", lw=2.0))

    f_arrow(31, 82.5, 36, 82.5)
    f_arrow(63, 82.5, 68, 82.5)
    f_arrow(82, 76, 82, 58)
    f_arrow(68, 51.5, 63, 51.5)
    f_arrow(36, 51.5, 31, 51.5)
    f_arrow(17.5, 45, 17.5, 30)
    f_arrow(46, 21, 52, 21)

    save_fig(fig, "resurrection_flowchart.png")


if __name__ == "__main__":
    print("Generating publication-grade diagrams...")
    generate_architecture()
    generate_tb6612_schematic()
    generate_sequence_timing()
    generate_power_tree()
    generate_resurrection_flowchart()
    print("All diagrams generated successfully!")
