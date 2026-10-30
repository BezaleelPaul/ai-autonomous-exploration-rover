"""Render complete CMR University Capstone Project Report DOCX.

Includes:
1. Standard CMR University Front Cover Sheet with official Logo, Title, Team & Guide details
2. Official Certificate Sheet with Dr. Raja Krishnamoorthi HOD & Guide signature blocks
3. Student Declaration Sheet with CHAKALI RAM VINAY, CHINMAY D M, and BEZALEEL PAUL N
4. Acknowledgement Sheet
5. Executive Abstract Sheet
6. Institutional Table of Contents
7. List of Figures & List of Tables
8. Complete Technical Chapters (1 to 12) with all 5 verified diagrams:
   - Figure 1: Three-Tier System Architecture
   - Figure 2: Real-Time Control & Safety Sequence Timing
   - Figure 3: Power Distribution Tree & Star Ground Topology
   - Figure 4: TB6612FNG Complete Electrical Wiring Schematic
   - Figure 5: System Resurrection & Fault Isolation Flowchart
9. Full Photographic Exhibition Gallery (Appendix A) in clean 2-column layout
10. Hardware Telemetry & Command API Reference (Appendices B & C)

Run:  py -3.12 tools/render_build_report_docx.py
Out:  reports/ROVER_BUILD_REPORT.docx
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
MD_PATH = REPORTS_DIR / "ROVER_BUILD_REPORT.md"
OUT_DOCX = REPORTS_DIR / "ROVER_BUILD_REPORT.docx"
DIAGRAMS_DIR = ROOT / "diagrams"
IMAGES_DIR = ROOT / "images"
ASSETS_DIR = REPORTS_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "cmr_logo.png"
CACHE_DIR = ASSETS_DIR / "docx_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Palette
NAVY = "0B2E59"
DARK_GREEN = "1A5C37"
SLATE = "334155"
LIGHT_BG = "F8FAFC"
BORDER_GRAY = "CBD5E1"
AMBER_ACCENT = "D97706"
AMBER_BG = "FFFBEB"
GREEN_BG = "F0FDF4"
RED_ACCENT = "DC2626"
RED_BG = "FEF2F2"

FONT_MAIN = "Times New Roman"
INLINE_RE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\*[^*\n]+?\*)")

# Student Team Details
TEAM = [
    ("CHAKALI RAM VINAY", "25BBTCS048"),
    ("CHINMAY D M", "25BBTCS055"),
    ("BEZALEEL PAUL N", "25BBTCS039"),
]


# ---------------------------------------------------------------------------
# Low-level OOXML Styling Helpers
# ---------------------------------------------------------------------------

def set_cell_bg(cell, hex_color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), hex_color)
    shd.set(qn("w:val"), "clear")


def set_cell_margins(cell, top=70, start=100, bottom=70, end=100) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.find(qn("w:tcMar"))
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for tag, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table, color="CBD5E1", size=4) -> None:
    tbl_pr = table._tbl.tblPr
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


def remove_table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "none")


def set_repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def add_field(paragraph, instruction: str, placeholder: str = "") -> None:
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


def set_page_number_format(section, fmt: str = "roman", start: int = 1) -> None:
    sect_pr = section._sectPr
    pg_num = sect_pr.find(qn("w:pgNumType"))
    if pg_num is None:
        pg_num = OxmlElement("w:pgNumType")
        sect_pr.append(pg_num)
    pg_num.set(qn("w:fmt"), fmt)
    pg_num.set(qn("w:start"), str(start))


# ---------------------------------------------------------------------------
# Image Optimization
# ---------------------------------------------------------------------------

def get_optimized_image(path: str | Path, max_dim: int = 1600) -> str:
    path = Path(path)
    if not path.exists():
        return ""
    if path.stat().st_size < 300_000:
        return str(path)
    cached = CACHE_DIR / f"opt_{path.stem}_{max_dim}.jpg"
    if cached.exists() and cached.stat().st_mtime >= path.stat().st_mtime:
        return str(cached)
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            w, h = img.size
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                new_size = (int(w * scale), int(h * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            img.save(cached, "JPEG", quality=88, optimize=True)
            return str(cached)
    except Exception:
        return str(path)


def discover_images() -> tuple[dict[str, Path], list[tuple[str, str, Path]]]:
    evidence = {}
    exif_list = []
    for root, _, files in os.walk(IMAGES_DIR):
        for f in files:
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                p = Path(root) / f
                evidence[f.lower()] = p
                stamp = ""
                try:
                    with Image.open(p) as img:
                        ex = img.getexif()
                        stamp = ex.get(306, "") or ""
                except Exception:
                    pass
                if not stamp:
                    stamp = "2026-12-99 00:00"
                exif_list.append((stamp, stamp[:16], p))
    exif_list.sort(key=lambda x: x[0])
    return evidence, exif_list


EVIDENCE_MAP, EXIF_PHOTOS = discover_images()


# ---------------------------------------------------------------------------
# Text & Run Helpers
# ---------------------------------------------------------------------------

def add_runs(paragraph, text: str, base_font=FONT_MAIN, base_size=11.5, base_color="1A1A1A"):
    for token in INLINE_RE.split(text):
        if not token:
            continue
        if token.startswith("**") and token.endswith("**"):
            run = paragraph.add_run(token[2:-2])
            run.bold = True
            run.font.name = base_font
            run.font.size = Pt(base_size)
            run.font.color.rgb = RGBColor.from_string(base_color)
        elif token.startswith("`") and token.endswith("`"):
            run = paragraph.add_run(token[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(base_size - 1.0)
            run.font.color.rgb = RGBColor.from_string(DARK_GREEN)
            run.bold = True
        elif token.startswith("*") and token.endswith("*") and len(token) > 2:
            run = paragraph.add_run(token[1:-1])
            run.italic = True
            run.font.name = base_font
            run.font.size = Pt(base_size)
            run.font.color.rgb = RGBColor.from_string(base_color)
        else:
            run = paragraph.add_run(token)
            run.font.name = base_font
            run.font.size = Pt(base_size)
            run.font.color.rgb = RGBColor.from_string(base_color)


def embed_figure(doc, path: str | Path, width_in: float, caption: str = ""):
    opt_path = get_optimized_image(path, max_dim=1800)
    if not opt_path or not os.path.exists(opt_path):
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(opt_path, width=Inches(width_in))
    if caption:
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_before = Pt(0)
        cap.paragraph_format.space_after = Pt(10)
        r = cap.add_run(caption)
        r.italic = True
        r.font.name = FONT_MAIN
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor.from_string(SLATE)


def add_callout(doc, text: str, border_col=AMBER_ACCENT, bg_col=AMBER_BG):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    cell = table.rows[0].cells[0]
    cell.width = Inches(6.3)
    set_cell_bg(cell, bg_col)
    set_cell_margins(cell, top=90, bottom=90, start=130, end=130)

    tc_pr = cell._tc.get_or_add_tcPr()
    tc_bdr = OxmlElement("w:tcBorders")
    left_bdr = OxmlElement("w:left")
    left_bdr.set(qn("w:val"), "single")
    left_bdr.set(qn("w:sz"), "24")
    left_bdr.set(qn("w:space"), "0")
    left_bdr.set(qn("w:color"), border_col)
    tc_bdr.append(left_bdr)
    for side in ("top", "bottom", "right"):
        b = OxmlElement(f"w:{side}")
        b.set(qn("w:val"), "none")
        tc_bdr.append(b)
    tc_pr.append(tc_bdr)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.2
    add_runs(p, text, base_font=FONT_MAIN, base_size=10.5, base_color="1A1A1A")
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def add_code_listing(doc, lines: list[str]):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.rows[0].cells[0]
    cell.width = Inches(6.3)
    set_cell_bg(cell, "F1F5F9")
    set_cell_margins(cell, top=70, bottom=70, start=100, end=100)
    set_table_borders(table, color="CBD5E1", size=4)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.15
    for idx, l in enumerate(lines):
        r = p.add_run(l)
        r.font.name = "Consolas"
        r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor.from_string("0F172A")
        if idx != len(lines) - 1:
            r.add_break()
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def add_table_grid(doc, rows: list[list[str]]):
    if not rows or not rows[0]:
        return
    num_cols = len(rows[0])
    table = doc.add_table(rows=len(rows), cols=num_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table, color="D1D5DB", size=4)
    set_repeat_header(table.rows[0])

    total_w = 6.3
    col_w = total_w / num_cols
    for row_idx, row_data in enumerate(rows):
        is_hdr = (row_idx == 0)
        for col_idx, cell_text in enumerate(row_data):
            if col_idx >= num_cols:
                continue
            cell = table.rows[row_idx].cells[col_idx]
            cell.width = Inches(col_w)
            set_cell_margins(cell, top=60, bottom=60, start=80, end=80)
            if is_hdr:
                set_cell_bg(cell, NAVY)
            elif row_idx % 2 == 1:
                set_cell_bg(cell, "F8FAFC")
            else:
                set_cell_bg(cell, "FFFFFF")

            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.15
            if is_hdr:
                add_runs(p, cell_text, base_font=FONT_MAIN, base_size=9.5, base_color="FFFFFF")
                for r in p.runs:
                    r.bold = True
            else:
                add_runs(p, cell_text, base_font=FONT_MAIN, base_size=9.5, base_color="1A1A1A")

    doc.add_paragraph().paragraph_format.space_after = Pt(6)


# ---------------------------------------------------------------------------
# Section 1: Standard CMR University Front Sheets (Sheets 1 to 7)
# ---------------------------------------------------------------------------

def build_cmru_front_sheets(doc: Document):
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.4)
    sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.8)   # Left margin for binding
    sec.right_margin = Cm(2.2)
    sec.different_first_page_header_footer = True
    sec.header.is_linked_to_previous = False
    sec.footer.is_linked_to_previous = False
    # Ensure no header text on front sheets
    for p in sec.header.paragraphs:
        p.text = ""
    set_page_number_format(sec, fmt="roman", start=1)

    # -----------------------------------------------------------------------
    # SHEET 1: FRONT COVER SHEET
    # -----------------------------------------------------------------------
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("SCHOOL OF ENGINEERING AND TECHNOLOGY\n")
    r.font.name = FONT_MAIN
    r.font.size = Pt(16.0)
    r.font.bold = True
    r.font.color.rgb = RGBColor.from_string(NAVY)

    r_u = p.add_run("CMR UNIVERSITY, BENGALURU\n")
    r_u.font.name = FONT_MAIN
    r_u.font.size = Pt(13.5)
    r_u.font.bold = True
    r_u.font.color.rgb = RGBColor.from_string(DARK_GREEN)

    # CMR Logo
    if LOGO_PATH.exists():
        p_logo = doc.add_paragraph()
        p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_logo.paragraph_format.space_before = Pt(6)
        p_logo.paragraph_format.space_after = Pt(8)
        p_logo.add_run().add_picture(str(LOGO_PATH), width=Inches(1.5))

    p_rep = doc.add_paragraph()
    p_rep.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_rep.paragraph_format.space_after = Pt(2)
    r_rep = p_rep.add_run("A Project Report On\n")
    r_rep.font.name = FONT_MAIN
    r_rep.font.size = Pt(12.5)
    r_rep.italic = True

    r_title = p_rep.add_run('"AI-ASSISTED AUTONOMOUS EXPLORATION ROVER"\n')
    r_title.font.name = FONT_MAIN
    r_title.font.size = Pt(16.5)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor.from_string(NAVY)

    p_subm = doc.add_paragraph()
    p_subm.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_subm.paragraph_format.space_after = Pt(12)
    p_subm.paragraph_format.line_spacing = 1.2
    r_s1 = p_subm.add_run("Submitted in partial fulfillment of the requirements for the award of degree in\n")
    r_s1.font.name = FONT_MAIN
    r_s1.font.size = Pt(10.5)
    r_deg = p_subm.add_run("BACHELOR OF TECHNOLOGY\nIN\nCOMPUTER SCIENCE AND ENGINEERING\n")
    r_deg.font.name = FONT_MAIN
    r_deg.font.size = Pt(12.5)
    r_deg.font.bold = True
    r_deg.font.color.rgb = RGBColor.from_string(DARK_GREEN)

    # Team & Guide Table
    tbl_people = doc.add_table(rows=1, cols=2)
    tbl_people.alignment = WD_TABLE_ALIGNMENT.CENTER
    remove_table_borders(tbl_people)
    c_sub = tbl_people.rows[0].cells[0]
    c_gui = tbl_people.rows[0].cells[1]
    c_sub.width = Inches(3.2)
    c_gui.width = Inches(3.1)
    set_cell_margins(c_sub, 0, 0, 0, 0)
    set_cell_margins(c_gui, 0, 0, 0, 0)

    p_s = c_sub.paragraphs[0]
    p_s.paragraph_format.line_spacing = 1.2
    r_sh = p_s.add_run("SUBMITTED BY:\n")
    r_sh.font.bold = True
    r_sh.font.size = Pt(10.5)
    for name, usn in TEAM:
        r_n = p_s.add_run(f"• {name}\n  (USN: {usn})\n")
        r_n.font.size = Pt(10.0)

    p_g = c_gui.paragraphs[0]
    p_g.paragraph_format.line_spacing = 1.2
    r_gh = p_g.add_run("GUIDED BY:\n")
    r_gh.font.bold = True
    r_gh.font.size = Pt(10.5)
    r_gn = p_g.add_run("Internal Project Guide\nAssistant Professor\nDept. of Electronics & Communication / CSE\nSoET, CMR University, Bengaluru\n")
    r_gn.font.size = Pt(10.0)

    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_inst.paragraph_format.space_before = Pt(16)
    p_inst.paragraph_format.space_after = Pt(0)
    p_inst.paragraph_format.line_spacing = 1.2
    r_i = p_inst.add_run(
        "Department of Computer Science and Engineering / ECE\n"
        "Off Hennur - Bagalur Main Road, Near Kempegowda International Airport, Chagalahatti\n"
        "Bengaluru, Karnataka – 562149\n"
        "Academic Year 2026 – 2027"
    )
    r_i.font.name = FONT_MAIN
    r_i.font.size = Pt(9.5)
    r_i.font.bold = True
    r_i.font.color.rgb = RGBColor.from_string(SLATE)

    doc.add_page_break()

    # -----------------------------------------------------------------------
    # SHEET 2: CERTIFICATE SHEET
    # -----------------------------------------------------------------------
    p_c1 = doc.add_paragraph()
    p_c1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_c1.paragraph_format.space_before = Pt(4)
    p_c1.paragraph_format.space_after = Pt(2)
    r = p_c1.add_run("SCHOOL OF ENGINEERING AND TECHNOLOGY\n")
    r.font.size = Pt(15.0)
    r.font.bold = True
    r.font.color.rgb = RGBColor.from_string(NAVY)

    r_loc = p_c1.add_run("Chagalahatti, Bengaluru, Karnataka – 562149\n")
    r_loc.font.size = Pt(10.0)

    r_dep = p_c1.add_run("Department of Electronics and Communication Engineering\n")
    r_dep.font.size = Pt(12.0)
    r_dep.font.bold = True

    if LOGO_PATH.exists():
        p_clogo = doc.add_paragraph()
        p_clogo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_clogo.paragraph_format.space_before = Pt(4)
        p_clogo.paragraph_format.space_after = Pt(6)
        p_clogo.add_run().add_picture(str(LOGO_PATH), width=Inches(1.2))

    p_cert = doc.add_paragraph()
    p_cert.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cert.paragraph_format.space_before = Pt(4)
    p_cert.paragraph_format.space_after = Pt(12)
    r_ct = p_cert.add_run("CERTIFICATE")
    r_ct.font.size = Pt(16.0)
    r_ct.font.bold = True
    r_ct.underline = True
    r_ct.font.color.rgb = RGBColor.from_string(DARK_GREEN)

    p_cb = doc.add_paragraph()
    p_cb.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_cb.paragraph_format.space_after = Pt(20)
    p_cb.paragraph_format.line_spacing = 1.45

    names_usn = ", ".join([f"**{n}** ({u})" for n, u in TEAM])
    body_cert = (
        f'This is to certify that the Project entitled **"AI-ASSISTED AUTONOMOUS EXPLORATION ROVER"** '
        f"has been successfully carried out by {names_usn} in partial fulfillment of the requirements for "
        f"the award of the degree **Bachelor of Technology in Computer Science and Engineering** of "
        f"**CMR University, Bengaluru** during the academic year **2026-2027**. The project report has been "
        f"approved as it satisfies the academic requirements in respect of project work prescribed for the said degree."
    )
    add_runs(p_cb, body_cert, base_font=FONT_MAIN, base_size=11.5)

    # Signatures block
    tbl_sigs = doc.add_table(rows=1, cols=2)
    tbl_sigs.alignment = WD_TABLE_ALIGNMENT.CENTER
    remove_table_borders(tbl_sigs)
    c_g = tbl_sigs.rows[0].cells[0]
    c_h = tbl_sigs.rows[0].cells[1]
    c_g.width = Inches(3.2)
    c_h.width = Inches(3.1)

    p_sg = c_g.paragraphs[0]
    p_sg.paragraph_format.line_spacing = 1.2
    p_sg.add_run("_____________________________\nSignature of the Guide\n\n\nGuide Name\nAssistant Professor\nDept. of ECE / CSE\nSoET, CMRU, Bengaluru").font.size = Pt(10.0)

    p_sh = c_h.paragraphs[0]
    p_sh.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_sh.paragraph_format.line_spacing = 1.2
    p_sh.add_run("_____________________________\nSignature of HOD\n\n\nDr. RAJA KRISHNAMOORTHI\nProfessor and Head of Department\nDept. of ECE\nSoET, CMRU, Bengaluru").font.size = Pt(10.0)

    p_ex = doc.add_paragraph()
    p_ex.paragraph_format.space_before = Pt(28)
    p_ex.paragraph_format.line_spacing = 1.3
    p_ex.add_run("Examiners Signature with date:\n\n1. ___________________________________\n\n2. ___________________________________").font.size = Pt(10.5)

    doc.add_page_break()

    # -----------------------------------------------------------------------
    # SHEET 3: DECLARATION SHEET
    # -----------------------------------------------------------------------
    p_dh = doc.add_paragraph()
    p_dh.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_dh.paragraph_format.space_before = Pt(8)
    p_dh.paragraph_format.space_after = Pt(14)
    r_d = p_dh.add_run("DECLARATION")
    r_d.font.size = Pt(16.0)
    r_d.font.bold = True
    r_d.font.color.rgb = RGBColor.from_string(NAVY)

    p_db = doc.add_paragraph()
    p_db.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_db.paragraph_format.space_after = Pt(24)
    p_db.paragraph_format.line_spacing = 1.45

    body_decl = (
        f"We, {names_usn}, students of 3rd semester B.Tech, Computer Science and Engineering, "
        f"School of Engineering and Technology, CMR University, Bengaluru, hereby declare that the project work "
        f'entitled **"AI-ASSISTED AUTONOMOUS EXPLORATION ROVER"** has been carried out by us under the guidance '
        f"of our internal project guide, Department of Electronics and Communication Engineering / CSE, School of Engineering and Technology. "
        f"This report is submitted in partial fulfillment of the requirements for the award of Bachelor of Technology in "
        f"Computer Science and Engineering by CMR University, Bengaluru during the academic year 2026-2027. "
        f"The project report has been approved as it satisfies the academic requirements in respect of project work prescribed for the said degree."
    )
    add_runs(p_db, body_decl, base_font=FONT_MAIN, base_size=11.5)

    tbl_dt = doc.add_table(rows=1, cols=2)
    tbl_dt.alignment = WD_TABLE_ALIGNMENT.CENTER
    remove_table_borders(tbl_dt)
    c_dt_l = tbl_dt.rows[0].cells[0]
    c_dt_r = tbl_dt.rows[0].cells[1]
    c_dt_l.width = Inches(2.5)
    c_dt_r.width = Inches(3.8)

    p_dt = c_dt_l.paragraphs[0]
    p_dt.paragraph_format.line_spacing = 1.2
    p_dt.add_run("Place: Bengaluru\nDate: October 2026").font.size = Pt(10.5)

    p_cand = c_dt_r.paragraphs[0]
    p_cand.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_cand.paragraph_format.line_spacing = 1.2
    for name, usn in TEAM:
        p_cand.add_run(f"___________________________\n{name}\n({usn})\n\n").font.size = Pt(10.0)

    doc.add_page_break()

    # -----------------------------------------------------------------------
    # SHEET 4: ACKNOWLEDGEMENT SHEET
    # -----------------------------------------------------------------------
    p_ah = doc.add_paragraph()
    p_ah.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ah.paragraph_format.space_before = Pt(8)
    p_ah.paragraph_format.space_after = Pt(14)
    r_a = p_ah.add_run("ACKNOWLEDGEMENT")
    r_a.font.size = Pt(16.0)
    r_a.font.bold = True
    r_a.font.color.rgb = RGBColor.from_string(NAVY)

    p_ab = doc.add_paragraph()
    p_ab.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_ab.paragraph_format.space_after = Pt(12)
    p_ab.paragraph_format.line_spacing = 1.45
    body_ack = (
        "The satisfaction that accompanies the successful completion of this project would be incomplete without the mention "
        "of the people who made it possible, without whose constant guidance and encouragement our efforts would have gone in vain.\n\n"
        "We express our heartfelt gratitude to **Dr. RAJA KRISHNAMOORTHI**, Professor and Head, Department of Electronics and Communication Engineering, "
        "School of Engineering and Technology, CMR University, Bengaluru, for his constant encouragement, scholarly leadership, and motivation that inspired us throughout the project lifecycle.\n\n"
        "We convey our sincere thanks to our **Internal Project Guide**, Assistant Professor, Department of Electronics and Communication Engineering / CSE, "
        "School of Engineering and Technology, CMR University, for constant technical mentorship, valuable critiques, and hands-on guidance during electrical bring-up, "
        "firmware development, and active safety interlock validation.\n\n"
        "We also extend our warm thanks to all faculty members, laboratory staff, and peer reviewers of the School of Engineering and Technology, CMR University, "
        "who provided material support, laboratory testbenches, and thoughtful suggestions during the Project Expo preparation."
    )
    add_runs(p_ab, body_ack, base_font=FONT_MAIN, base_size=11.5)

    p_asig = doc.add_paragraph()
    p_asig.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_asig.paragraph_format.space_before = Pt(16)
    p_asig.paragraph_format.line_spacing = 1.2
    for name, usn in TEAM:
        p_asig.add_run(f"{name} ({usn})\n").font.size = Pt(10.0)

    doc.add_page_break()

    # -----------------------------------------------------------------------
    # SHEET 5: ABSTRACT SHEET
    # -----------------------------------------------------------------------
    p_abh = doc.add_paragraph()
    p_abh.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_abh.paragraph_format.space_before = Pt(8)
    p_abh.paragraph_format.space_after = Pt(14)
    r_ab = p_abh.add_run("ABSTRACT")
    r_ab.font.size = Pt(16.0)
    r_ab.font.bold = True
    r_ab.font.color.rgb = RGBColor.from_string(NAVY)

    p_abtxt = doc.add_paragraph()
    p_abtxt.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_abtxt.paragraph_format.space_after = Pt(12)
    p_abtxt.paragraph_format.line_spacing = 1.45
    abstract_content = (
        "This project presents the design, fabrication, firmware architecture, and empirical verification of an **AI-Assisted Autonomous Exploration Rover** "
        "developed for technical competition and exhibition. Autonomous mobile rovers operating in dynamic unstructured environments require a low-latency "
        "coupling between high-level perceptual intelligence and deterministic low-level hardware safety reflexes.\n\n"
        "The platform implements a **three-tier distributed computing architecture**: an **Arduino Uno R3** reflex microcontroller enforcing a non-blocking 15 cm ultrasonic "
        "forward gate and a 500 ms radio link watchdog; an **ESP32 DevKit V1** wireless gateway hosting a standalone Wi-Fi Soft-AP (`AI_Rover_Control`) and responsive "
        "HTML5 drive pad with pointer-capture hold-to-drive and dynamic PWM speed modulation (60–255); and a **Laptop Edge AI Tier** executing YOLO11n neural network "
        "inference @ 320 px over an IP Webcam video stream, governing three-zone autonomous steering.\n\n"
        "During electrical prototyping, the actuation tier was upgraded from a lossy bipolar L298N driver to an efficient **TB6612FNG dual MOSFET H-bridge** (<0.2 V drop, 95% efficiency), "
        "resolving motor stall voltage collapse. Two critical short-circuit failure events during build bring-up were systematically analyzed and resolved through direct heavy-gauge "
        "wiring, elimination of breadboard motor current flow, and star ground topology. The completed platform is validated by dual-serial hardware captures and 98 automated contract tests in pytest, "
        "delivering robust, fail-safe autonomous navigation ready for live competition demonstration."
    )
    add_runs(p_abtxt, abstract_content, base_font=FONT_MAIN, base_size=11.5)

    p_kw = doc.add_paragraph()
    p_kw.paragraph_format.space_before = Pt(12)
    r_kwh = p_kw.add_run("Keywords: ")
    r_kwh.bold = True
    r_kwh.font.size = Pt(10.5)
    p_kw.add_run("Differential-Drive Rover, Dual-Core Reflex Architecture, TB6612FNG, Arduino Uno, ESP32 Soft-AP, YOLO11n Edge AI, Ultrasonic Obstacle Gate, Fail-Safe Link Watchdog.").font.size = Pt(10.5)

    doc.add_page_break()

    # -----------------------------------------------------------------------
    # SHEET 6: TABLE OF CONTENTS
    # -----------------------------------------------------------------------
    p_th = doc.add_paragraph()
    p_th.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_th.paragraph_format.space_before = Pt(8)
    p_th.paragraph_format.space_after = Pt(14)
    r_t = p_th.add_run("TABLE OF CONTENTS")
    r_t.font.size = Pt(16.0)
    r_t.font.bold = True
    r_t.font.color.rgb = RGBColor.from_string(NAVY)

    toc_rows = [
        ["CHAPTER NO.", "TITLE", "PAGE NO."],
        ["", "Certificate", "ii"],
        ["", "Declaration", "iii"],
        ["", "Acknowledgement", "iv"],
        ["", "Abstract", "v"],
        ["", "List of Figures", "vii"],
        ["", "List of Tables", "viii"],
        ["1", "EXECUTIVE SUMMARY & TECHNICAL SCORECARD", "1"],
        ["2", "SYSTEM ARCHITECTURE & DISTRIBUTED CONTROL", "3"],
        ["3", "ELECTRICAL WIRING MAP & POWER TOPOLOGIES", "5"],
        ["4", "FIRMWARE ARCHITECTURE: THE THREE BRAINS", "8"],
        ["5", "THE BUILD TIMELINE (EXIF-VERIFIED)", "10"],
        ["6", "INCIDENT DOSSIER: POST-MORTEM OF TWO SHORT CIRCUITS", "12"],
        ["7", "SYSTEM RESURRECTION & METHODICAL BRING-UP", "14"],
        ["8", "EMPIRICAL VERIFICATION, TEST SUITE & BENCHMARKS", "16"],
        ["9", "PROJECT EXPO LIVE DEMONSTRATION PROTOCOL", "18"],
        ["10", "FAILURE MODES & EFFECTS ANALYSIS (FMEA)", "20"],
        ["11", "ENGINEERING REFLECTION: LESSONS & BEST PRACTICES", "21"],
        ["12", "FUTURE ROADMAP & POLISH ITEMS", "22"],
        ["Appendix A", "Full Photographic Exhibition Album (EXIF-Verified)", "23"],
        ["Appendix B", "Hardware Telemetry Dictionary", "27"],
        ["Appendix C", "Command & API Reference", "28"],
    ]
    add_table_grid(doc, toc_rows)

    doc.add_page_break()

    # -----------------------------------------------------------------------
    # SHEET 7: LIST OF FIGURES & LIST OF TABLES
    # -----------------------------------------------------------------------
    p_lf = doc.add_paragraph()
    p_lf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_lf.paragraph_format.space_before = Pt(8)
    p_lf.paragraph_format.space_after = Pt(10)
    r_lf = p_lf.add_run("LIST OF FIGURES")
    r_lf.font.size = Pt(15.0)
    r_lf.font.bold = True
    r_lf.font.color.rgb = RGBColor.from_string(NAVY)

    fig_rows = [
        ["FIGURE NO.", "FIGURE TITLE", "PAGE NO."],
        ["Figure 1", "Complete Three-Tier System Architecture (Operator, Reflex Core, Actuation)", "3"],
        ["Figure 2", "Real-Time Control & Safety Sequence Timing Diagram", "4"],
        ["Figure 3", "Power Distribution Tree and Star Ground Topology", "6"],
        ["Figure 4", "TB6612FNG Complete Electrical Wiring Schematic", "7"],
        ["Figure 5", "System Resurrection and Layer-by-Layer Fault Isolation Flowchart", "15"],
        ["Figure A.1", "Critical Incident #1 Evidence: Scorched Battery Positive Contact Tab", "23"],
        ["Figure A.2", "Critical Incident #2 Evidence: Taped Splice Bare Wire Flex Failure", "24"],
        ["Figure A.3", "Autonomous Vision System Bench: Live YOLO11n Object Tracking", "25"],
    ]
    add_table_grid(doc, fig_rows)

    p_lt = doc.add_paragraph()
    p_lt.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_lt.paragraph_format.space_before = Pt(12)
    p_lt.paragraph_format.space_after = Pt(10)
    r_lt = p_lt.add_run("LIST OF TABLES")
    r_lt.font.size = Pt(15.0)
    r_lt.font.bold = True
    r_lt.font.color.rgb = RGBColor.from_string(DARK_GREEN)

    tbl_rows = [
        ["TABLE NO.", "TABLE TITLE", "PAGE NO."],
        ["Table 1.1", "Platform Technical Specifications & Implementation Details", "1"],
        ["Table 3.1", "TB6612FNG Production Pinout Truth Table", "7"],
        ["Table 3.2", "Driver Technology Trade-Off: TB6612FNG MOSFET vs Legacy L298N", "8"],
        ["Table 5.1", "EXIF-Authenticated 23-Day Hardware Build Timeline", "10"],
        ["Table 10.1", "Failure Modes and Effects Analysis (FMEA) Matrix", "20"],
        ["Table B.1", "Hardware Telemetry Output Dictionary", "27"],
        ["Table C.1", "Command & API Protocol Specification", "28"],
    ]
    add_table_grid(doc, tbl_rows)


# ---------------------------------------------------------------------------
# Section 2: Technical Body Section (Starts Page 1 Arabic)
# ---------------------------------------------------------------------------

def append_technical_body(doc: Document):
    # Create new section for body with Arabic page numbering
    body_sec = doc.add_section(WD_SECTION.NEW_PAGE)
    body_sec.top_margin = Cm(2.4)
    body_sec.bottom_margin = Cm(2.2)
    body_sec.left_margin = Cm(2.8)
    body_sec.right_margin = Cm(2.2)
    body_sec.header_distance = Cm(1.1)
    body_sec.footer_distance = Cm(1.0)
    body_sec.different_first_page_header_footer = False
    body_sec.header.is_linked_to_previous = False
    body_sec.footer.is_linked_to_previous = False
    set_page_number_format(body_sec, fmt="decimal", start=1)

    # Running Header
    hdr = body_sec.header
    p_h = hdr.paragraphs[0]
    p_h.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_h = p_h.add_run("CMR University · School of Engineering and Technology · Project Expo 2026")
    r_h.font.name = FONT_MAIN
    r_h.font.size = Pt(8.5)
    r_h.font.color.rgb = RGBColor.from_string(SLATE)

    # Running Footer
    ftr = body_sec.footer
    tbl_f = ftr.add_table(rows=1, cols=2, width=Inches(6.3))
    tbl_f.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_fl = tbl_f.rows[0].cells[0]
    c_fr = tbl_f.rows[0].cells[1]
    c_fl.width = Inches(4.5)
    c_fr.width = Inches(1.8)
    set_cell_margins(c_fl, 0, 0, 0, 0)
    set_cell_margins(c_fr, 0, 0, 0, 0)
    remove_table_borders(tbl_f)

    p_fl = c_fl.paragraphs[0]
    r_fl = p_fl.add_run("AI-Assisted Autonomous Exploration Rover | Capstone Project Report")
    r_fl.font.name = FONT_MAIN
    r_fl.font.size = Pt(8.5)
    r_fl.font.color.rgb = RGBColor.from_string(SLATE)

    p_fr = c_fr.paragraphs[0]
    p_fr.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_fr = p_fr.add_run("Page ")
    r_fr.font.name = FONT_MAIN
    r_fr.font.size = Pt(8.5)
    r_fr.font.color.rgb = RGBColor.from_string(SLATE)
    add_field(p_fr, "PAGE", "1")
    p_fr.add_run(" of ").font.size = Pt(8.5)
    add_field(p_fr, "NUMPAGES", "30")

    lines = MD_PATH.read_text(encoding="utf-8").splitlines()

    fence: str | None = None
    fence_lines: list[str] = []
    table_rows: list[list[str]] = []
    in_appendix_a = False

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return
        clean_rows = []
        for r in table_rows:
            raw_s = "".join(r).replace("-", "").replace(":", "").strip()
            if raw_s:
                clean_rows.append(r)
        if clean_rows:
            add_table_grid(doc, clean_rows)
        table_rows = []

    for line_idx, raw in enumerate(lines):
        line = raw.rstrip()

        # Skip main markdown top title lines (already in front sheets)
        if line_idx < 30 and (line.startswith("# ") or line.startswith("## ") or line.startswith("### ") or line.startswith("#### ")):
            continue
        if "Table of Contents" in line and line_idx < 30:
            continue

        # Code block
        if fence is None and line.startswith("```"):
            flush_table()
            fence = line[3:].strip()
            fence_lines = []
            continue

        if fence is not None:
            if line.startswith("```"):
                if fence != "mermaid":
                    add_code_listing(doc, fence_lines)
                fence = None
            else:
                fence_lines.append(line)
            continue

        # Table rows
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            table_rows.append(cells)
            continue

        flush_table()

        # Headings
        if line.startswith("## "):
            text = line[3:].strip()
            if "Appendix A" in text:
                in_appendix_a = True
                build_appendix_photo_album(doc)
                continue

            in_appendix_a = False
            p_h = doc.add_paragraph()
            p_h.paragraph_format.space_before = Pt(16)
            p_h.paragraph_format.space_after = Pt(4)
            p_h.paragraph_format.keep_with_next = True
            r = p_h.add_run(text)
            r.font.name = FONT_MAIN
            r.font.size = Pt(14.5)
            r.font.bold = True
            r.font.color.rgb = RGBColor.from_string(NAVY)

            # Figures
            if "2 · System Architecture" in text:
                embed_figure(doc, DIAGRAMS_DIR / "architecture_blocks.png", 6.2,
                             "Figure 1: Complete Three-Tier System Architecture (Operator/AI Tier, On-Rover Reflex Core, Actuation Tier)")
                embed_figure(doc, DIAGRAMS_DIR / "sequence_timing.png", 6.2,
                             "Figure 2: Real-Time Control & Safety Sequence Timing Diagram (Deterministic Delivery, Sonar Gating & Watchdog)")
            elif "3 · Electrical Wiring Map" in text:
                embed_figure(doc, DIAGRAMS_DIR / "power_tree.png", 6.2,
                             "Figure 3: Power Distribution Tree and Star Ground Topology (High-Current vs Logic Rail Separation)")
                embed_figure(doc, DIAGRAMS_DIR / "tb6612_wiring.png", 6.2,
                             "Figure 4: Complete Electrical Wiring Schematic (Uno Pinout, TB6612 Silkscreen & TT Motors)")
            elif "7 · System Resurrection" in text:
                embed_figure(doc, DIAGRAMS_DIR / "resurrection_flowchart.png", 6.2,
                             "Figure 5: System Resurrection and Layer-by-Layer Fault Isolation Flowchart")
            continue

        if in_appendix_a:
            continue

        if line.startswith("### "):
            text = line[4:].strip()
            p_h = doc.add_paragraph()
            p_h.paragraph_format.space_before = Pt(12)
            p_h.paragraph_format.space_after = Pt(3)
            p_h.paragraph_format.keep_with_next = True
            r = p_h.add_run(text)
            r.font.name = FONT_MAIN
            r.font.size = Pt(12.5)
            r.font.bold = True
            r.font.color.rgb = RGBColor.from_string(DARK_GREEN)
            continue

        if line.startswith("#### "):
            text = line[5:].strip()
            p_h = doc.add_paragraph()
            p_h.paragraph_format.space_before = Pt(8)
            p_h.paragraph_format.space_after = Pt(2)
            p_h.paragraph_format.keep_with_next = True
            r = p_h.add_run(text)
            r.font.name = FONT_MAIN
            r.font.size = Pt(11.0)
            r.font.bold = True
            r.font.color.rgb = RGBColor.from_string(SLATE)
            continue

        # Callouts
        if line.startswith("> "):
            callout_text = line[2:].strip()
            border_c = AMBER_ACCENT
            bg_c = AMBER_BG
            if "Rule" in callout_text or "Mandate" in callout_text or "Golden" in callout_text:
                border_c = DARK_GREEN
                bg_c = GREEN_BG
            add_callout(doc, callout_text, border_col=border_c, bg_col=bg_c)
            continue

        # Lists
        if line.startswith("- "):
            p_l = doc.add_paragraph(style="List Bullet")
            p_l.paragraph_format.space_before = Pt(1)
            p_l.paragraph_format.space_after = Pt(2)
            p_l.paragraph_format.line_spacing = 1.2
            add_runs(p_l, line[2:].strip())
            continue

        m_num = re.match(r"^(\d+)\.\s+(.*)", line)
        if m_num:
            p_n = doc.add_paragraph(style="List Number")
            p_n.paragraph_format.space_before = Pt(1)
            p_n.paragraph_format.space_after = Pt(2)
            p_n.paragraph_format.line_spacing = 1.2
            add_runs(p_n, m_num.group(2).strip())
            continue

        # Skip raw image links in markdown as we embed them explicitly
        if re.match(r"^!\[(.*?)\]\((.*?)\)", line):
            continue

        if line.strip() in ("---", "***", "___"):
            continue

        if not line.strip():
            continue

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(5)
        p.paragraph_format.line_spacing = 1.35
        add_runs(p, line.strip())

    flush_table()


# ---------------------------------------------------------------------------
# Appendix A Gallery
# ---------------------------------------------------------------------------

def build_appendix_photo_album(doc: Document):
    p_h = doc.add_paragraph()
    p_h.paragraph_format.space_before = Pt(16)
    p_h.paragraph_format.space_after = Pt(6)
    p_h.paragraph_format.keep_with_next = True
    r = p_h.add_run("Appendix A — Full Photographic Exhibition Album (EXIF-Verified)")
    r.font.name = FONT_MAIN
    r.font.size = Pt(15.0)
    r.font.bold = True
    r.font.color.rgb = RGBColor.from_string(NAVY)

    p_lead = doc.add_paragraph()
    p_lead.paragraph_format.space_after = Pt(10)
    p_lead.paragraph_format.line_spacing = 1.3
    add_runs(p_lead, "Every photograph below is authenticated by hardware camera EXIF timestamps, capturing the physical progression from acrylic chassis laser-cutting through wiring, short-circuit post-mortems, and live bring-up.")

    featured_images = [
        ("assembly_13_battery_terminal_connection_detail_damaged_shortcircuited.jpeg",
         "Figure A.1: Critical Incident #1 Evidence (Oct 26, 2026 · 20:14:32)",
         "Close-up inspection of the battery holder positive contact lug showing thermal discoloration, flux residue whitening, and charred insulation resulting from terminal-to-metal contact during deck reassembly. Led directly to mandatory pack de-energization procedures."),
        ("short circuited.jpg",
         "Figure A.2: Critical Incident #2 Evidence (Oct 29, 2026 · 16:12:08)",
         "Physical inspection of the taped motor harness splice that separated under chassis flexing, creating an intermittent short circuit and high-resistance open that silenced drive wheels. Led directly to total elimination of taped joints and adoption of direct 20 AWG wiring."),
        ("ai rover detection system in laptop.jpg",
         "Figure A.3: Autonomous Vision System Bench (Oct 29, 2026 · Evening)",
         "Laptop AI tier running real-time YOLO11n object tracking over the phone camera MJPEG stream. Displays the 3-zone steering overlay, target bounding boxes, and autonomous F/L/R/S command generation.")
    ]

    for fname, title, desc in featured_images:
        path = EVIDENCE_MAP.get(fname.lower())
        if path and path.exists():
            table = doc.add_table(rows=1, cols=1)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            cell = table.rows[0].cells[0]
            cell.width = Inches(6.3)
            set_cell_bg(cell, "F8FAFC")
            set_table_borders(table, color="CBD5E1", size=6)
            set_cell_margins(cell, top=100, bottom=100, start=120, end=120)

            p_t = cell.paragraphs[0]
            p_t.paragraph_format.space_before = Pt(0)
            p_t.paragraph_format.space_after = Pt(4)
            r_t = p_t.add_run(title)
            r_t.font.name = FONT_MAIN
            r_t.font.size = Pt(10.5)
            r_t.font.bold = True
            r_t.font.color.rgb = RGBColor.from_string(RED_ACCENT if "Incident" in title else NAVY)

            opt_p = get_optimized_image(path, max_dim=1400)
            p_im = cell.add_paragraph()
            p_im.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_im.paragraph_format.space_after = Pt(4)
            p_im.add_run().add_picture(opt_p, width=Inches(5.4))

            p_d = cell.add_paragraph()
            p_d.paragraph_format.space_before = Pt(2)
            p_d.paragraph_format.space_after = Pt(0)
            p_d.paragraph_format.line_spacing = 1.2
            r_d = p_d.add_run(desc)
            r_d.font.name = FONT_MAIN
            r_d.font.size = Pt(9.0)
            r_d.font.color.rgb = RGBColor.from_string(SLATE)

            doc.add_paragraph().paragraph_format.space_after = Pt(8)

    grid_photos = []
    for stamp, label, path in EXIF_PHOTOS:
        fn = path.name.lower()
        if any(fn == fi[0].lower() for fi in featured_images):
            continue
        grid_photos.append((stamp, label, path))

    for i in range(0, len(grid_photos), 2):
        row_photos = grid_photos[i:i+2]
        tbl_g = doc.add_table(rows=1, cols=2)
        tbl_g.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl_g.autofit = False
        set_table_borders(tbl_g, color="E2E8F0", size=4)

        for col_idx, (stamp, label, p_path) in enumerate(row_photos):
            cell = tbl_g.rows[0].cells[col_idx]
            cell.width = Inches(3.1)
            set_cell_bg(cell, "FFFFFF")
            set_cell_margins(cell, top=60, bottom=60, start=80, end=80)

            opt_p = get_optimized_image(p_path, max_dim=900)
            p_im = cell.paragraphs[0]
            p_im.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_im.paragraph_format.space_before = Pt(2)
            p_im.paragraph_format.space_after = Pt(3)
            p_im.add_run().add_picture(opt_p, width=Inches(2.7))

            p_cap = cell.add_paragraph()
            p_cap.paragraph_format.space_before = Pt(1)
            p_cap.paragraph_format.space_after = Pt(1)
            p_cap.paragraph_format.line_spacing = 1.15
            time_lbl = label if not label.startswith("2026-12") else "(Screengrab)"
            r_ts = p_cap.add_run(f"[{time_lbl}]\n")
            r_ts.font.name = FONT_MAIN
            r_ts.font.size = Pt(8.0)
            r_ts.font.bold = True
            r_ts.font.color.rgb = RGBColor.from_string(DARK_GREEN)

            r_nm = p_cap.add_run(p_path.stem.replace("_", " "))
            r_nm.font.name = FONT_MAIN
            r_nm.font.size = Pt(8.5)
            r_nm.font.color.rgb = RGBColor.from_string(SLATE)

        if len(row_photos) == 1:
            cell_empty = tbl_g.rows[0].cells[1]
            cell_empty.width = Inches(3.1)
            set_cell_bg(cell_empty, "F8FAFC")

        doc.add_paragraph().paragraph_format.space_after = Pt(4)


# ---------------------------------------------------------------------------
# Main Document Builder
# ---------------------------------------------------------------------------

def build_full_report_docx():
    print("Beginning generation of complete CMR University Capstone Report DOCX...")
    doc = Document()
    build_cmru_front_sheets(doc)
    append_technical_body(doc)

    doc.save(str(OUT_DOCX))
    size_mb = OUT_DOCX.stat().st_size / (1024 * 1024)
    print(f"SUCCESS: Generated {OUT_DOCX} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    build_full_report_docx()
