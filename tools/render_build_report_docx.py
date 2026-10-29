"""Render reports/ROVER_BUILD_REPORT.md into a polished DOCX with embedded photos.

- Title page with cover photo
- Architecture block diagram (matplotlib) and TB6612 wiring schematic (schemdraw PNG)
- Markdown headings/tables/code/quotes/lists converted with Word styles
- Every report-referenced photo embedded below its table; incident photos inline
- Appendix A becomes a full EXIF-sorted photo album

Run:  py -3.12 tools/render_build_report_docx.py
Out:  reports/ROVER_BUILD_REPORT.docx
"""

from __future__ import annotations

import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = os.path.join(ROOT, "reports", "ROVER_BUILD_REPORT.md")
OUT = os.path.join(ROOT, "reports", "ROVER_BUILD_REPORT.docx")
IMAGES = os.path.join(ROOT, "images")
ARCH_PNG = os.path.join(ROOT, "diagrams", "architecture_blocks.png")
CIRCUIT_PNG = os.path.join(ROOT, "diagrams", "tb6612_wiring.png")

GREEN = RGBColor(0x1A, 0x5C, 0x37)
GRAY = RGBColor(0x66, 0x66, 0x66)

INLINE_RE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\*[^*\n]+?\*)")


# -- image discovery ------------------------------------------------------


def exif_photos() -> list[tuple[str, str, str]]:
    """Return [(sort_key, time_label, abs_path)] for every image, EXIF-sorted."""
    rows = []
    for dirpath, _, files in os.walk(IMAGES):
        for name in files:
            if not name.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            path = os.path.join(dirpath, name)
            stamp = ""
            try:
                exif = Image.open(path).getexif()
                stamp = exif.get(306, "") or ""
            except Exception:
                stamp = ""
            if not stamp:
                stamp = "2026-12-99 00:00:00"  # undated screenshots last
            rows.append((stamp, stamp[:16], path))
    rows.sort(key=lambda r: r[0])
    return rows


def evidence_map() -> dict[str, str]:
    table = {}
    for dirpath, _, files in os.walk(IMAGES):
        for name in files:
            if name.lower().endswith((".jpg", ".jpeg", ".png")):
                table[name.lower()] = os.path.join(dirpath, name)
    return table


EVIDENCE = evidence_map()


def find_images_in_table(rows: list[list[str]]) -> list[str]:
    hits = []
    for row in rows:
        for cell in row:
            for name in re.findall(r"`([^`]+?\.(?:jpe?g|png|jpeg))`", cell):
                if name.lower().strip() in EVIDENCE:
                    hits.append(name.lower().strip())
    return hits


# -- architecture diagram -------------------------------------------------


def draw_architecture() -> None:
    fig, ax = plt.subplots(figsize=(11.5, 6.4), dpi=200)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 64)
    ax.axis("off")

    def box(x, y, w, h, title, lines, face):
        ax.add_patch(
            plt.Rectangle(
                (x, y),
                w,
                h,
                facecolor=face,
                edgecolor="#333",
                lw=1.4,
                zorder=2,
                joinstyle="round",
            )
        )
        ax.text(
            x + w / 2,
            y + h - 3.4,
            title,
            ha="center",
            va="top",
            fontsize=10.5,
            fontweight="bold",
            zorder=3,
        )
        ax.text(
            x + w / 2,
            y + h - 7.4,
            "\n".join(lines),
            ha="center",
            va="top",
            fontsize=8.2,
            zorder=3,
            color="#222",
        )

    def arrow(x1, y1, x2, y2, label, style="->", color="#1a5c37", dash=False):
        ax.annotate(
            label,
            xy=(x2, y2),
            xytext=(x1, y1),
            ha="center",
            va="center",
            fontsize=8,
            color=color,
            zorder=4,
            arrowprops={
                "arrowstyle": style,
                "color": color,
                "lw": 1.6,
                "linestyle": "--" if dash else "-",
            },
        )

    box(
        3,
        40,
        22,
        20,
        "PHONE",
        [
            "IP Webcam app",
            "http://:8080/video",
            "Rover pad browser",
            "(join AI_Rover_Control)",
        ],
        "#e8f0fe",
    )
    box(
        3,
        12,
        22,
        20,
        "LAPTOP AI TIER",
        [
            "ai_video_server.py",
            "YOLO11n @320 px boxes",
            "perception_node pilot",
            "decides F/L/R/S",
            "Mission Deck control",
        ],
        "#fff3cd",
    )
    box(
        38,
        40,
        26,
        20,
        "ESP32 DEVKIT V1",
        [
            "Wi-Fi soft-AP 192.168.4.1",
            "drive pad + speed slider",
            "/cmd  whitelist F..S + PWM",
            "/cam + /status NVS",
        ],
        "#e2f0d9",
    )
    box(
        38,
        6,
        26,
        26,
        "ARDUINO UNO R3",
        [
            "gap-framed parser (15 ms)",
            "15 cm forward gate",
            "500 ms link watchdog",
            "non-blocking sonar FSM",
            "telemetry over USB",
        ],
        "#fde2e2",
    )
    box(
        74,
        34,
        23,
        14,
        "TB6612FNG",
        [
            "dual MOSFET H-bridge",
            "VM 7.4 V battery",
            "STBY/VCC 5 V",
        ],
        "#ffe6cc",
    )
    box(
        74,
        6,
        23,
        14,
        "HC-SR04",
        [
            "Trig D2 / Echo D3",
            "5 V + GND direct",
            "60 ms ping period",
        ],
        "#dcc7e6",
    )
    box(74, 52, 23, 8, "2 x TT MOTORS", ["AO1/2 left - BO1/2 right"], "#444")
    ax.text(76.5, 57.4, "MOTORS", color="#fff", fontsize=10.5, fontweight="bold")
    ax.text(76.5, 53.2, "AO1/2 left  Â·  BO1/2 right", color="#fff", fontsize=8)

    battery = (74, 61, 23, 8)
    ax.add_patch(
        plt.Rectangle(
            battery[:2],
            battery[2],
            battery[3],
            facecolor="#dffbe4",
            edgecolor="#333",
            lw=1.4,
        )
    )
    ax.text(85.5, 65, "BATTERY 2S 7.4 V", ha="center", fontsize=10.5, fontweight="bold")
    ax.text(85.5, 62, "direct wires - never a breadboard", ha="center", fontsize=8)

    box(74, 22, 23, 8, "MOTORS", ["left: AO1/AO2 - right: BO1/BO2"], "#efefef")

    arrow(25, 50, 38, 50, "HTTP GET /cmd?c=F200")
    arrow(25, 45, 60, 45, "MJPEG stream", dash=True)
    arrow(51, 43, 51, 40, "")
    arrow(64, 50, 44, 32, "UART one-way 9600\nGPIO17 -> D4", color="#8a5ac2")
    arrow(64, 18, 74, 40, "PWM + IN pins")
    arrow(74, 34, 64, 30, "", color="#c0392b")
    arrow(74, 33, 64, 28, "", color="#c0392b")
    arrow(97, 52, 97, 56, "7.4 V")
    arrow(97, 30, 97, 40, "")
    arrow(25, 24, 38, 14, "autonomous F/L/R/S", dash=True)
    arrow(14, 40, 14, 32, "video", dash=True)
    plt.tight_layout()
    os.makedirs(os.path.dirname(ARCH_PNG), exist_ok=True)
    fig.savefig(ARCH_PNG, bbox_inches="tight")
    plt.close(fig)


# -- md parsing helpers ---------------------------------------------------


def split_table_row(line: str) -> list[str]:
    line = line.strip().strip("|")
    return [c.strip() for c in line.split("|")]


def is_sep_row(line: str) -> bool:
    body = line.replace("|", "").replace("-", "").replace(":", "").strip()
    return body == "" and "-" in line


def add_runs(paragraph, text: str):
    """Add md inline styled runs (bold / code / italic)."""
    for token in INLINE_RE.split(text):
        if not token:
            continue
        if token.startswith("**") and token.endswith("**"):
            run = paragraph.add_run(token[2:-2])
            run.bold = True
        elif token.startswith("`") and token.endswith("`"):
            run = paragraph.add_run(token[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(9.5)
            run.font.color.rgb = GREEN
        elif token.startswith("*") and token.endswith("*") and len(token) > 2:
            run = paragraph.add_run(token[1:-1])
            run.italic = True
        else:
            paragraph.add_run(token)
    return paragraph


def shade(cell, fill: str) -> None:
    cell._tc.get_or_add_tcPr().append(
        parse_xml(r'<w:shd %s w:fill="%s"/>' % (nsdecls("w"), fill))
    )


def add_code_block(doc, lines: list[str]) -> None:
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.rows[0].cells[0]
    shade(cell, "F2F2F2")
    para = cell.paragraphs[0]
    for idx, line in enumerate(lines):
        run = para.add_run(line)
        run.font.name = "Consolas"
        run.font.size = Pt(8.5)
        if idx != len(lines) - 1:
            run.add_break()
    doc.add_paragraph()


def add_table(doc, rows: list[list[str]]) -> None:
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = "Table Grid"
    for r, row in enumerate(rows):
        for c, cell_text in enumerate(row):
            if c >= len(table.rows[r].cells):
                continue
            cell = table.rows[r].cells[c]
            if r == 0:
                shade(cell, "DDEEDD")
            para = cell.paragraphs[0]
            add_runs(para, cell_text)
            if r == 0:
                for run in para.runs:
                    run.bold = True
                    run.font.size = Pt(9.5)
                continue
            for run in para.runs:
                run.font.size = Pt(9)
    doc.add_paragraph()


def embed(doc, path: str, width_in: float, caption: str = "") -> None:
    if not os.path.exists(path):
        return
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    try:
        para.add_run().add_picture(path, width=Inches(width_in))
    except Exception:
        return
    if caption:
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = cap.add_run(caption)
        run.italic = True
        run.font.size = Pt(9)
        run.font.color.rgb = GRAY


def clean_label(path: str, exif_rows) -> str:
    match = next((r for r in exif_rows if r[2].lower() == path.lower()), None)
    stamp, label, _ = match if match else ("", "", path)
    if stamp.startswith("9999") or stamp == "":
        return os.path.basename(path)
    rel = path.replace("\\", "/").split("/images/")[-1]
    return f"{label}  -  {rel}"


EXIF_ROWS = []


# -- main build -----------------------------------------------------------


def build_doc() -> None:
    exif_rows = exif_photos()
    draw_architecture()

    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(1.9)
        section.bottom_margin = Cm(1.9)
        section.left_margin = Cm(2.0)
        section.right_margin = Cm(2.0)

    with open(MD, encoding="utf-8") as md_file:
        lines = md_file.read().splitlines()
    fence = None
    fence_lines: list[str] = []
    table_rows: list[list[str]] = []
    table_open = False
    mermaid_index = 0
    saw_sonar_table = False
    printed_title = False

    def flush_table() -> None:
        nonlocal table_rows, table_open
        if not table_rows:
            return
        rows = [r for r in table_rows if not is_sep_row("|" + "|".join(r))]
        add_table(doc, rows)
        hits = find_images_in_table(rows)
        for name in hits:
            path = EVIDENCE[name]
            is_incident = "shortcircuited" in name or "short circuited" in name
            embed(doc, path, 5.7 if is_incident else 4.0, clean_label(path, exif_rows))
        table_rows = []
        table_open = False

    for raw in lines:
        line = raw.rstrip()
        # 1) fenced code / diagrams
        if fence is None and line.startswith("```"):
            flush_table()
            fence = line[3:].strip()
            fence_lines = []
            continue
        if fence is not None:
            if line.startswith("```"):
                if fence == "mermaid":
                    mermaid_index += 1
                    if mermaid_index == 1:
                        embed(
                            doc,
                            ARCH_PNG,
                            6.1,
                            "Figure 1 - system architecture (rendered)",
                        )
                    else:
                        p = doc.add_paragraph()
                        r = p.add_run(
                            "(live Mermaid diagram rendered in the companion "
                            "HTML report)"
                        )
                        r.italic = True
                        r.font.color.rgb = GRAY
                else:
                    add_code_block(doc, fence_lines)
                fence = None
            else:
                fence_lines.append(line)
            continue
        # 2) tables
        if line.startswith("|"):
            table_rows.append(split_table_row(line))
            table_open = True
            continue
        flush_table()
        # 3) headings
        if line.startswith("### "):
            doc.add_heading(add_heading_text := line[4:].strip(), level=2)
            saw_sonar_table = saw_sonar_table or ("3.2" in add_heading_text)
            continue
        if line.startswith("## "):
            text = line[3:].strip()
            doc.add_heading(text, level=1)
            if (
                text.startswith("3 Â·")
                or text.startswith("3 Â· Wiring")
                or "Complete Wiring Map" in text
            ):
                embed(
                    doc,
                    CIRCUIT_PNG,
                    6.1,
                    "Figure 2 - TB6612FNG wiring schematic "
                    "(generated with schemdraw, firmware truth)",
                )
            if text.startswith("Appendix A"):
                for stamp, label, path in exif_rows:
                    name = os.path.basename(path).lower()
                    bmp = EVIDENCE.get(name, "")
                    if not bmp:
                        continue
                    caption = (
                        (
                            label
                            if not label.startswith("2026-12")
                            else "(undated screenshot)"
                        )
                        + "  -  "
                        + name
                    )
                    embed(doc, bmp, 3.4, caption)
            continue
        if line.startswith("# "):
            if not printed_title:
                h = doc.add_heading(line[2:].strip(), level=0)
                for run in h.runs if hasattr(h, "runs") else []:
                    run.font.size = Pt(24)
                printed_title = True
            continue
        # 4) quotes, lists, paragraphs
        if line.startswith("> "):
            para = doc.add_paragraph(style="Intense Quote")
            add_runs(para, line[2:])
            continue
        m = re.match(r"^(\d+)\.\s+(.*)", line)
        if m:
            para = doc.add_paragraph(style="List Number")
            add_runs(para, m.group(2))
            continue
        if line.startswith("- "):
            para = doc.add_paragraph(style="List Bullet")
            add_runs(para, line[2:])
            continue
        if not line.strip():
            continue
        para = doc.add_paragraph()
        add_runs(para, line)

    flush_table()
    doc.save(OUT)
    print("saved", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    build_doc()
