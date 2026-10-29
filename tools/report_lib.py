#!/usr/bin/env python3
"""Shared helpers for building the AI Rover narrative report.

This module owns document styling, table/figure helpers, image preparation,
and the benchmark charts.  The content itself lives in
``tools/generate_story_report.py``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageOps
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"
FIGURES = ROOT / "figures"
REPORTS = ROOT / "reports"
ASSETS = REPORTS / "assets"
CHART_DIR = FIGURES / "report"
LOGS = ROOT / "logs"

NAVY = "0B2E59"
BLUE = "1F4E79"
STEEL = "2E5C8A"
LIGHT_BLUE = "EAF1F8"
LIGHT_GREY = "F2F2F2"
MID_GREY = "7F7F7F"
WHITE = "FFFFFF"
GREEN = "2E7D32"
AMBER = "B26A00"
RED = "B00020"


# ---------------------------------------------------------------------------
# Low-level OOXML helpers
# ---------------------------------------------------------------------------


def _set_run_font(
    run,
    name: str = "Times New Roman",
    size: float | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
    color: str | None = None,
) -> None:
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)


def _set_cell_bg(cell, color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), color)
    shd.set(qn("w:val"), "clear")


def _set_cell_margins(cell, top=60, start=80, bottom=60, end=80) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.find(qn("w:tcMar"))
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for tag, value in (
        ("top", top),
        ("start", start),
        ("bottom", bottom),
        ("end", end),
    ):
        node = tc_mar.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def _set_table_borders(table, color: str = "BFBFBF", size: int = 4) -> None:
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), str(size))
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def _set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def _set_col_widths(table, widths_inches: list[float]) -> None:
    for row in table.rows:
        for idx, width in enumerate(widths_inches):
            if idx < len(row.cells):
                row.cells[idx].width = Inches(width)


def _add_field(paragraph, instruction: str, placeholder: str = "") -> None:
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {instruction} "
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = placeholder
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(text)
    run._r.append(fld_end)


def _add_seq_field(paragraph, kind: str) -> None:
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" SEQ {kind} \\* ARABIC "
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(text)
    run._r.append(fld_end)


def _set_page_number_format(section, fmt: str, start: int = 1) -> None:
    sect_pr = section._sectPr
    pg_num = sect_pr.find(qn("w:pgNumType"))
    if pg_num is None:
        pg_num = OxmlElement("w:pgNumType")
        sect_pr.append(pg_num)
    pg_num.set(qn("w:fmt"), fmt)
    pg_num.set(qn("w:start"), str(start))


def _add_bottom_border(paragraph, color: str = "BFBFBF", size: int = 6) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = p_pr.find(qn("w:pBdr"))
    if p_bdr is None:
        p_bdr = OxmlElement("w:pBdr")
        p_pr.append(p_bdr)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), color)
    p_bdr.append(bottom)


# ---------------------------------------------------------------------------
# Document styling and page furniture
# ---------------------------------------------------------------------------


def page_setup(section) -> None:
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.4)
    section.bottom_margin = Cm(2.2)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.2)
    section.header_distance = Cm(1.1)
    section.footer_distance = Cm(1.0)


def style_document(doc: Document) -> None:
    styles = doc.styles

    normal = styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(11.5)
    normal.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
    normal.paragraph_format.line_spacing = 1.45
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), "Times New Roman")

    h1 = styles["Heading 1"]
    h1.font.name = "Times New Roman"
    h1.font.size = Pt(16)
    h1.font.bold = True
    h1.font.color.rgb = RGBColor.from_string(NAVY)
    h1.paragraph_format.space_before = Pt(6)
    h1.paragraph_format.space_after = Pt(10)
    h1.paragraph_format.keep_with_next = True

    h2 = styles["Heading 2"]
    h2.font.name = "Times New Roman"
    h2.font.size = Pt(13.5)
    h2.font.bold = True
    h2.font.color.rgb = RGBColor.from_string(BLUE)
    h2.paragraph_format.space_before = Pt(12)
    h2.paragraph_format.space_after = Pt(6)
    h2.paragraph_format.keep_with_next = True

    h3 = styles["Heading 3"]
    h3.font.name = "Times New Roman"
    h3.font.size = Pt(12)
    h3.font.bold = True
    h3.font.color.rgb = RGBColor.from_string(STEEL)
    h3.paragraph_format.space_before = Pt(8)
    h3.paragraph_format.space_after = Pt(4)
    h3.paragraph_format.keep_with_next = True

    caption = styles["Caption"]
    caption.font.name = "Times New Roman"
    caption.font.size = Pt(9)
    caption.font.italic = True
    caption.font.color.rgb = RGBColor.from_string("444444")
    caption.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.space_before = Pt(3)
    caption.paragraph_format.space_after = Pt(10)
    caption.paragraph_format.line_spacing = 1.0

    for name in ("List Bullet", "List Number"):
        st = styles[name]
        st.font.name = "Times New Roman"
        st.font.size = Pt(11.5)
        st.paragraph_format.space_after = Pt(3)
        st.paragraph_format.line_spacing = 1.35

    kicker = styles.add_style("ChapterKicker", 1)
    kicker.font.name = "Calibri"
    kicker.font.size = Pt(10)
    kicker.font.bold = True
    kicker.font.color.rgb = RGBColor.from_string(MID_GREY)
    kicker.paragraph_format.space_before = Pt(0)
    kicker.paragraph_format.space_after = Pt(2)
    kicker.paragraph_format.page_break_before = True
    kicker.paragraph_format.keep_with_next = True

    front = styles.add_style("FrontHeading", 1)
    front.font.name = "Times New Roman"
    front.font.size = Pt(16)
    front.font.bold = True
    front.font.color.rgb = RGBColor.from_string(NAVY)
    front.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    front.paragraph_format.space_before = Pt(0)
    front.paragraph_format.space_after = Pt(14)
    front.paragraph_format.page_break_before = True
    front.paragraph_format.keep_with_next = True

    small = styles.add_style("SmallNote", 1)
    small.font.name = "Times New Roman"
    small.font.size = Pt(9.5)
    small.font.italic = True
    small.font.color.rgb = RGBColor.from_string("555555")
    small.paragraph_format.space_after = Pt(6)


def add_header(section, left_text: str, right_text: str = "CMR University") -> None:
    header = section.header
    header.is_linked_to_previous = False
    paragraph = header.paragraphs[0]
    paragraph.text = ""
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    tab_stops = paragraph.paragraph_format.tab_stops
    usable = section.page_width - section.left_margin - section.right_margin
    tab_stops.add_tab_stop(usable, alignment=2)  # right aligned
    run = paragraph.add_run(left_text)
    _set_run_font(run, "Calibri", 8.5, color=MID_GREY)
    run = paragraph.add_run("\t" + right_text)
    _set_run_font(run, "Calibri", 8.5, color=MID_GREY)
    _add_bottom_border(paragraph, "D0D7E2", 4)


def add_page_footer(section, fmt: str = "decimal", start: int = 1) -> None:
    _set_page_number_format(section, fmt, start)
    footer = section.footer
    footer.is_linked_to_previous = False
    paragraph = footer.paragraphs[0]
    paragraph.text = ""
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("Page ")
    _set_run_font(run, "Calibri", 9, color=MID_GREY)
    _add_field(paragraph, "PAGE", "1")
    run = paragraph.add_run(" of ")
    _set_run_font(run, "Calibri", 9, color=MID_GREY)
    _add_field(paragraph, "NUMPAGES", "1")
    for r in paragraph.runs:
        _set_run_font(r, "Calibri", 9, color=MID_GREY)


def new_section(
    doc: Document, fmt: str, start: int = 1, header_text: str | None = None
):
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    page_setup(section)
    add_page_footer(section, fmt, start)
    if header_text:
        add_header(section, header_text)
    return section


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------


def add_body(
    doc: Document,
    text: str,
    bold_lead: str | None = None,
    align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    space_after: float = 6,
    italic: bool = False,
    size: float | None = None,
):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    if bold_lead:
        run = p.add_run(bold_lead)
        _set_run_font(run, "Times New Roman", size or 11.5, bold=True, color=NAVY)
    run = p.add_run(text)
    _set_run_font(run, "Times New Roman", size or 11.5, italic=italic)
    return p


def add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.left_indent = Cm(0.75)
        p.paragraph_format.first_line_indent = Cm(-0.4)
        run = p.add_run(item)
        _set_run_font(run, "Times New Roman", 11.2)


def add_numbered(doc: Document, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph(style="List Number")
        p.paragraph_format.left_indent = Cm(0.75)
        p.paragraph_format.first_line_indent = Cm(-0.4)
        run = p.add_run(item)
        _set_run_font(run, "Times New Roman", 11.2)


def add_chapter(doc: Document, number: str, title: str, page_break: bool = True) -> None:
    kicker = doc.add_paragraph(style="ChapterKicker")
    kicker.paragraph_format.page_break_before = page_break
    run = kicker.add_run(number.upper())
    _set_run_font(run, "Calibri", 10, bold=True, color=MID_GREY)
    doc.add_heading(title, level=1)


def add_front_heading(doc: Document, title: str, page_break: bool = True) -> None:
    p = doc.add_paragraph(style="FrontHeading")
    p.paragraph_format.page_break_before = page_break
    run = p.add_run(title.upper())
    _set_run_font(run, "Times New Roman", 16, bold=True, color=NAVY)


def add_callout(
    doc: Document, title: str, text: str, fill: str = LIGHT_BLUE, border: str = BLUE
) -> None:
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    cell = table.cell(0, 0)
    _set_cell_bg(cell, fill)
    _set_cell_margins(cell, 120, 160, 120, 160)
    _set_table_borders(table, border, 8)
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run(title)
    _set_run_font(run, "Calibri", 10.5, bold=True, color=border)
    p2 = cell.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    run = p2.add_run(text)
    _set_run_font(run, "Times New Roman", 10.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_table(
    doc: Document,
    headers: list[str],
    rows: list[list[str]],
    widths: list[float] | None = None,
    caption: str | None = None,
    font_size: float = 8.5,
    header_bg: str = NAVY,
    zebra: bool = True,
    first_col_bold: bool = False,
) -> None:
    if caption:
        p = doc.add_paragraph(style="Caption")
        run = p.add_run("Table ")
        _set_run_font(run, "Times New Roman", 9, italic=True, color="444444")
        _add_seq_field(p, "Table")
        run = p.add_run(f": {caption}")
        _set_run_font(run, "Times New Roman", 9, italic=True, color="444444")

    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.allow_autofit = False
    _set_table_borders(table, "C9D3E0", 4)

    header_row = table.rows[0]
    _set_repeat_table_header(header_row)
    for idx, header in enumerate(headers):
        cell = header_row.cells[idx]
        _set_cell_bg(cell, header_bg)
        _set_cell_margins(cell)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run(header)
        _set_run_font(run, "Calibri", font_size, bold=True, color=WHITE)

    for r_idx, row in enumerate(rows):
        cells = table.add_row().cells
        for c_idx, value in enumerate(row):
            cell = cells[c_idx]
            _set_cell_margins(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            if zebra and r_idx % 2 == 1:
                _set_cell_bg(cell, LIGHT_GREY)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.05
            if c_idx > 0 and len(str(value)) < 14:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(str(value))
            _set_run_font(
                run,
                "Calibri",
                font_size,
                bold=(first_col_bold and c_idx == 0),
                color="1A1A1A",
            )

    if widths:
        _set_col_widths(table, widths)

    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(2)
    spacer.paragraph_format.line_spacing = 1.0


def add_figure(
    doc: Document, path: Path, caption: str, max_w: float = 6.1, max_h: float = 4.35
) -> None:
    with Image.open(path) as im:
        iw, ih = im.size
    aspect = ih / iw
    width = max_w
    height = width * aspect
    if height > max_h:
        height = max_h
        width = height / aspect
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.keep_with_next = True
    run = p.add_run()
    run.add_picture(str(path), width=Inches(width), height=Inches(height))

    cap = doc.add_paragraph(style="Caption")
    run = cap.add_run("Figure ")
    _set_run_font(run, "Times New Roman", 9, italic=True, color="444444")
    _add_seq_field(cap, "Figure")
    run = cap.add_run(f": {caption}")
    _set_run_font(run, "Times New Roman", 9, italic=True, color="444444")


def add_toc(doc: Document) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    _add_field(
        p,
        'TOC \\o "1-3" \\h \\z \\u',
        "Right-click and choose Update Field to build the table of contents.",
    )


def add_table_of_figures(doc: Document) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    _add_field(
        p,
        'TOC \\h \\z \\c "Figure"',
        "Right-click and choose Update Field to build the list of figures.",
    )


def add_table_of_tables(doc: Document) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    _add_field(
        p,
        'TOC \\h \\z \\c "Table"',
        "Right-click and choose Update Field to build the list of tables.",
    )


def add_horizontal_rule(doc: Document) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(8)
    _add_bottom_border(p, "D0D7E2", 6)


# ---------------------------------------------------------------------------
# Image preparation and charts
# ---------------------------------------------------------------------------


PHOTO_SOURCES = {
    "motor": IMAGES / "components" / "hw_tt_dc_gear_motor.jpg",
    "esp32_front": IMAGES / "components" / "hw_esp32_cam_front_ov2640.jpg",
    "esp32_back": IMAGES / "components" / "hw_esp32_devkit_board_back.jpg",
    "esp32_usb": IMAGES / "components" / "hw_esp32_cam_connected_usb.jpg",
    "power": IMAGES
    / "components"
    / "hw_power_18650_battery_pack_and_lm2596_buck_converter.jpg",
    "arduino": IMAGES / "components" / "hw_arduino_uno_wired.jpg",
    "ultra_bracket": IMAGES
    / "components"
    / "hw_ultrasonic_sensor_hcsr04_with_bracket.jpg",
    "ultra_detail": IMAGES
    / "components"
    / "hw_ultrasonic_sensor_transducer_detail.jpg",
    "ultra_pinout": IMAGES / "components" / "hw_ultrasonic_sensor_hcsr04_pinout.jpg",
    "tb_top": IMAGES / "components" / "hw_tb6612fng_motor_driver_top.jpg",
    "tb_pinout": IMAGES / "components" / "hw_tb6612fng_motor_driver_pinout.jpg",
    "asm01": IMAGES / "assembly" / "assembly_01_chassis_battery_holder_and_switch.jpeg",
    "asm02": IMAGES / "assembly" / "assembly_02_chassis_dual_tt_motors_mounted.jpeg",
    "asm03": IMAGES / "assembly" / "assembly_03_chassis_wheels_and_caster_mounted.jpeg",
    "asm04": IMAGES / "assembly" / "assembly_04_chassis_top_view_with_wheels.jpeg",
    "asm05": IMAGES / "assembly" / "assembly_05_ultrasonic_sensor_rear_mount.jpeg",
    "asm06": IMAGES / "assembly" / "assembly_06_ultrasonic_sensor_mount_detail.jpeg",
    "asm07": IMAGES / "assembly" / "assembly_07_system_bench_wiring_test.jpeg",
    "asm08": IMAGES / "assembly" / "assembly_08_chassis_electronics_placement.jpeg",
    "asm09": IMAGES / "assembly" / "assembly_09_twotier_prototype_side_view.jpeg",
    "asm10": IMAGES / "assembly" / "assembly_10_twotier_prototype_top_view.jpeg",
    "asm11": IMAGES / "assembly" / "assembly_11_chassis_bottom_wiring_routing.jpeg",
    "asm12": IMAGES / "assembly" / "assembly_12_motor_wiring_insulated_joints.jpeg",
    "asm13": IMAGES
    / "assembly"
    / "assembly_13_battery_terminal_connection_detail_damaged_shortcircuited.jpeg",
    "flash": IMAGES / "testing_telemetry" / "test_esp32_firmware_flashing_esptool.jpg",
    "yolo": IMAGES / "testing_telemetry" / "telemetry_live_yolo_tracking_ip_webcam.jpg",
    "dashboard": IMAGES
    / "testing_telemetry"
    / "telemetry_missionpilot_dashboard_and_terminal.jpg",
    "wifi1": IMAGES / "testing_telemetry" / "test_esp32cam_wifi_stream_mobile_01.jpg",
    "wifi2": IMAGES / "testing_telemetry" / "test_esp32cam_wifi_stream_mobile_02.jpg",
}

DIAGRAM_SOURCES = {
    "d_sys": FIGURES / "01_system_architecture.png",
    "d_flow": FIGURES / "02_data_flow.png",
    "d_hw": FIGURES / "03_hardware_architecture.png",
    "d_power": FIGURES / "04_power_architecture.png",
    "d_esp": FIGURES / "05_esp32_pipeline.png",
    "d_decide": FIGURES / "06_decision_pipeline.png",
    "d_arduino": FIGURES / "07_arduino_pipeline.png",
    "d_safety": FIGURES / "08_safety_hierarchy.png",
    "d_fsm": FIGURES / "09_state_machine.png",
    "d_control": FIGURES / "10_control_loop.png",
    "d_diff": FIGURES / "11_differential_drive_geometry.png",
    "d_target": FIGURES / "12_target_position.png",
    "d_zones": FIGURES / "13_left_center_right_zones.png",
    "d_protocol": FIGURES / "14_communication_protocol.png",
    "d_block": FIGURES / "15_full_robot_block_diagram.png",
    "d_scan": FIGURES / "360_degree_scan_diagram.png",
    "d_circuit": FIGURES / "circuit_diagram.png",
    "d_wiring": FIGURES / "wiring_schemdraw.png",
    "d_control_resp": FIGURES / "control_response_kp_comparison.png",
}


def prepare_assets() -> dict[str, Path]:
    """Resize and normalise every image used in the report."""
    ASSETS.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}

    logo_src = Path(
        r"C:\Users\bezal\AppData\Local\Temp\opencode\docx1\a\word\media\image1.png"
    )
    logo_dst = ASSETS / "cmr_logo.png"
    if logo_src.exists():
        shutil.copy2(logo_src, logo_dst)
        out["logo"] = logo_dst

    for key, src in {**PHOTO_SOURCES, **DIAGRAM_SOURCES}.items():
        if not src.exists():
            raise FileNotFoundError(f"Missing source image: {src}")
        suffix = ".png" if src.suffix.lower() == ".png" else ".jpg"
        dst = ASSETS / f"{key}{suffix}"
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            if suffix == ".jpg":
                im = im.convert("RGB")
                im.thumbnail((1800, 1800), Image.LANCZOS)
                im.save(dst, "JPEG", quality=88, optimize=True)
            else:
                im.thumbnail((2200, 2200), Image.LANCZOS)
                im.save(dst, "PNG", optimize=True)
        out[key] = dst

    return out


def _style_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#BFC8D6")
    ax.spines["bottom"].set_color("#BFC8D6")
    ax.tick_params(colors="#333333", labelsize=9)
    ax.grid(axis="y", color="#E3E8EF", linewidth=0.8)
    ax.set_axisbelow(True)


def make_charts() -> dict[str, Path]:
    """Generate the four report charts from measured JSON logs."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    CHART_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "figure.dpi": 200,
        }
    )
    out: dict[str, Path] = {}

    models = [
        ("YOLO11n", "detection_cand_yolo11n.json", "#4C78A8"),
        ("YOLO11s", "detection_cand_yolo11s.json", "#0B2E59"),
        ("YOLO26n", "detection_cand_yolo26n.json", "#F58518"),
        ("YOLO26s", "detection_cand_yolo26s.json", "#E45756"),
        ("RT-DETRv2-R18", "detection_cand_rtdetrv2_r18.json", "#72B7B2"),
    ]
    rows = []
    for name, filename, color in models:
        data = json.loads((LOGS / filename).read_text(encoding="utf-8"))
        op = data["operating_point"]
        rows.append(
            (
                name,
                op["recall"],
                op["mAP"] if "mAP" in op else data["ap"]["mAP"],
                data["latency_ms"]["p50"],
                color,
            )
        )

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.8))
    names = [r[0] for r in rows]
    colors = [r[4] for r in rows]

    ax = axes[0]
    values = [r[1] * 100 for r in rows]
    bars = ax.barh(names[::-1], values[::-1], color=colors[::-1], height=0.6)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Recall at confidence 0.25 (%)")
    ax.set_title("Detection recall on COCO128 (929 objects)")
    _style_axes(ax)
    ax.grid(axis="x", color="#E3E8EF", linewidth=0.8)
    ax.grid(axis="y", visible=False)
    for bar, value in zip(bars, values[::-1]):
        ax.text(
            value + 1.5,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.1f}%",
            va="center",
            fontsize=8,
            color="#333333",
        )

    ax = axes[1]
    lat = [r[3] for r in rows]
    bars = ax.barh(names[::-1], lat[::-1], color=colors[::-1], height=0.6)
    ax.set_xscale("log")
    ax.set_xlabel("Median inference latency (ms, log scale)")
    ax.set_title("Median latency on the 2C/4T host CPU")
    _style_axes(ax)
    ax.grid(axis="x", color="#E3E8EF", linewidth=0.8)
    ax.grid(axis="y", visible=False)
    for bar, value in zip(bars, lat[::-1]):
        ax.text(
            value * 1.12,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.0f} ms",
            va="center",
            fontsize=8,
            color="#333333",
        )

    fig.suptitle(
        "Model accuracy versus real-time latency",
        fontsize=11,
        fontweight="bold",
        color="#0B2E59",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    path = CHART_DIR / "model_benchmark.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    out["c_models"] = path

    runtimes = [
        ("PyTorch (.pt)", "detection_yolo11s_pt.json", "#4C78A8"),
        ("ONNX Runtime", "detection_yolo11s_onnx.json", "#0B2E59"),
        ("OpenVINO", "detection_yolo11s_openvino.json", "#72B7B2"),
    ]
    labels, lat, colors = [], [], []
    for label, filename, color in runtimes:
        data = json.loads((LOGS / filename).read_text(encoding="utf-8"))
        labels.append(label)
        lat.append(data["latency_ms"]["p50"])
        colors.append(color)

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    bars = ax.bar(labels, lat, color=colors, width=0.55)
    ax.set_ylabel("Median latency (ms)")
    ax.set_title("YOLO11s runtime backend comparison (160 frames, 100% CPU load)")
    _style_axes(ax)
    for bar, value in zip(bars, lat):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 12,
            f"{value:.0f} ms",
            ha="center",
            fontsize=9,
            color="#333333",
        )
    ax.set_ylim(0, max(lat) * 1.22)
    fig.tight_layout()
    path = CHART_DIR / "runtime_benchmark.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    out["c_runtime"] = path

    eval_data = json.loads((LOGS / "eval.json").read_text(encoding="utf-8"))
    safety = eval_data["safety"]
    order = [
        ("CAUTION_CLOSE_OBSTACLE", "Close obstacle"),
        ("LOW_CONFIDENCE", "Low confidence"),
        ("CAUTION_UNKNOWN_DISTANCE", "Unknown distance"),
        ("SENSOR_OUT_OF_RANGE", "Sensor out of range"),
        ("COMM_LOST", "Communication lost"),
        ("CAUTION_SLOW_ZONE", "Slow zone"),
        ("CAMERA_UNHEALTHY", "Camera unhealthy"),
    ]
    labels = [label for key, label in order]
    values = [safety[key]["rows"] for key, _ in order]
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    bars = ax.barh(labels[::-1], values[::-1], color="#B00020", height=0.6)
    ax.set_xlabel("Event rows (out of 9,118)")
    ax.set_title("Non-safe safety states recorded during the event-log campaign")
    _style_axes(ax)
    ax.grid(axis="x", color="#E3E8EF", linewidth=0.8)
    ax.grid(axis="y", visible=False)
    for bar, value in zip(bars, values[::-1]):
        ax.text(
            value + 3,
            bar.get_y() + bar.get_height() / 2,
            str(value),
            va="center",
            fontsize=8,
            color="#333333",
        )
    ax.set_xlim(0, max(values) * 1.18)
    fig.tight_layout()
    path = CHART_DIR / "safety_events.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    out["c_safety"] = path

    from datetime import date

    milestones = [
        (date(2026, 10, 3), "HC-SR04\narrives"),
        (date(2026, 10, 6), "Chassis\nrolling"),
        (date(2026, 10, 8), "ESP32-CAM\nfirmware"),
        (date(2026, 10, 9), "Power pack\nultrasonic"),
        (date(2026, 10, 19), "Bench wiring\nYOLO live"),
        (date(2026, 10, 20), "Two-tier\nstack"),
        (date(2026, 10, 22), "Wi-Fi\nstream"),
        (date(2026, 10, 23), "Insulated\njoints"),
        (date(2026, 10, 26), "Driver upgrade\nshort circuit"),
    ]
    fig, ax = plt.subplots(figsize=(10.0, 3.0))
    ax.axhline(0, color="#0B2E59", linewidth=2, zorder=1)
    xs = [m[0] for m in milestones]
    for idx, (day, label) in enumerate(milestones):
        ax.scatter(day, 0, s=70, color="#0B2E59" if idx != 8 else "#B00020", zorder=3)
        offset = 0.55 if idx % 2 == 0 else -0.55
        va = "bottom" if offset > 0 else "top"
        ax.plot([day, day], [0, offset * 0.75], color="#9FB3C8", linewidth=1, zorder=2)
        ax.text(
            day,
            offset,
            label,
            ha="center",
            va=va,
            fontsize=7.6,
            color="#1A1A1A",
            linespacing=1.1,
        )
    ax.set_ylim(-1.35, 1.35)
    ax.set_yticks([])
    ax.set_xlabel("October 2026")
    ax.set_title("Photo-documented build timeline (dates taken from image metadata)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color("#BFC8D6")
    ax.tick_params(axis="x", labelsize=8)
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()
    path = CHART_DIR / "build_timeline.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    out["c_timeline"] = path

    return out
