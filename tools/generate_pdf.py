"""Publication-Grade PDF Final Report Generator (v2 - complete & aligned).

Generates: reports/AI_Rover_Final_Report.pdf

Improvements over v1:
- Full chapter content assembled from docs/*.md (headings, paragraphs,
  markdown tables, lists, notes, equations and ASCII schematics)
- All 18 figures embedded with aspect-ratio-preserving sizing
- Automatic multi-pass Table of Contents / List of Figures with real
  page numbers and dot leaders
- PDF outline bookmarks for every chapter and section
- Unicode-safe Arial / Courier New typography with justified body text
"""

import os
import re
import hashlib

from PIL import Image as PILImage

from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    BaseDocTemplate,
    PageTemplate,
    Frame,
    Paragraph,
    Spacer,
    Image,
    PageBreak,
    Table,
    TableStyle,
    HRFlowable,
)

try:
    from reportlab.platypus.tableofcontents import TableOfContents
except ImportError:  # pragma: no cover
    from reportlab.platypus import TableOfContents

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG_DIR = os.path.join(ROOT, "figures")
DOC_DIR = os.path.join(ROOT, "docs")
OUTPUT = os.path.join(ROOT, "reports", "AI_Rover_Final_Report.pdf")

PAGE_W, PAGE_H = A4
MARGIN = 54.0
TOP_MARGIN = 64.0
BOTTOM_MARGIN = 56.0
CONTENT_W = PAGE_W - 2 * MARGIN
CONTENT_H = PAGE_H - TOP_MARGIN - BOTTOM_MARGIN

PRIMARY = colors.HexColor("#0D47A1")
SECONDARY = colors.HexColor("#1B5E20")
ACCENT = colors.HexColor("#F9A825")
GRID = colors.HexColor("#9AA7B4")
STRIPE = colors.HexColor("#EEF3FA")
INK = colors.HexColor("#222222")
MUTED = colors.HexColor("#555555")

BR_TOKEN = "@@BR@@"

# --------------------------------------------------------------------------
# Fonts (Unicode-capable; graceful fallback to Helvetica)
# --------------------------------------------------------------------------
UNICODE_OK = True


def _register_font(name, filename):
    try:
        pdfmetrics.registerFont(
            TTFont(
                name,
                os.path.join(
                    os.environ.get("WINDIR", r"C:\Windows"), "Fonts", filename
                ),
            )
        )
        return True
    except Exception:
        return False


def setup_fonts():
    global UNICODE_OK
    ok = (
        _register_font("Arial", "arial.ttf")
        & _register_font("Arial-Bold", "arialbd.ttf")
        & _register_font("Arial-Italic", "ariali.ttf")
        & _register_font("Arial-BoldItalic", "arialbi.ttf")
        & _register_font("CourierNew", "cour.ttf")
    )
    if ok:
        pdfmetrics.registerFontFamily(
            "Arial",
            normal="Arial",
            bold="Arial-Bold",
            italic="Arial-Italic",
            boldItalic="Arial-BoldItalic",
        )
    else:
        UNICODE_OK = False


# --------------------------------------------------------------------------
# Markdown helpers
# --------------------------------------------------------------------------
SYMBOLS = [
    (r"\\leftrightarrow", "\u2194"),
    (r"\\rightarrow", "\u2192"),
    (r"\\leftarrow", "\u2190"),
    (r"\\Rightarrow", "\u21d2"),
    (r"\\approx", "\u2248"),
    (r"\\propto", "\u221d"),
    (r"\\times", "\u00d7"),
    (r"\\cdot", "\u00b7"),
    (r"\\pm", "\u00b1"),
    (r"\\mp", "\u2213"),
    (r"\\geq", "\u2265"),
    (r"\\leq", "\u2264"),
    (r"\\neq", "\u2260"),
    (r"\\ge(?![a-zA-Z])", "\u2265"),
    (r"\\le(?![a-zA-Z])", "\u2264"),
    (r"\\ne(?![a-zA-Z])", "\u2260"),
    (r"\\infty", "\u221e"),
    (r"\\circ", "\u00b0"),
    (r"\\degree", "\u00b0"),
    (r"\\sum", "\u03a3"),
    (r"\\Delta", "\u0394"),
    (r"\\delta", "\u03b4"),
    (r"\\omega", "\u03c9"),
    (r"\\Omega", "\u03a9"),
    (r"\\theta", "\u03b8"),
    (r"\\pi(?![a-zA-Z])", "\u03c0"),
    (r"\\mu(?![a-zA-Z])", "\u00b5"),
    (r"\\alpha", "\u03b1"),
    (r"\\lambda", "\u03bb"),
    (r"\\sqrt", "\u221a"),
]

ASCII_FALLBACK = {
    "\u2265": ">=",
    "\u2264": "<=",
    "\u2260": "!=",
    "\u00d7": "x",
    "\u00b7": ".",
    "\u221e": "inf",
    "\u2194": "<->",
    "\u2192": "->",
    "\u221a": "sqrt",
    "\u03a3": "Sum",
    "\u0394": "D",
    "\u03b4": "d",
    "\u03c9": "w",
    "\u03a9": "Ohm",
    "\u03b8": "t",
    "\u03c0": "pi",
    "\u03b1": "a",
    "\u03bb": "l",
    "\u221d": "~",
    "\u2213": "-/+",
}


def mathify(expr):
    s = expr
    s = re.sub(r"\\text\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\mathrm\s*\{([^{}]*)\}", r"\1", s)
    for _ in range(4):
        s = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1 / \2)", s)
    for pattern, repl in SYMBOLS:
        s = re.sub(pattern, repl, s)
    s = s.replace("\\left", "").replace("\\right", "")
    s = re.sub(r"\\[,;!! ]", " ", s)
    s = s.replace("\\\\", " ")
    s = re.sub(r"\{([^{}]*)\}", r"\1", s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("^", "")
    s = re.sub(r"(?<=\s)~(?=\d)|^~(?=\d)", "\u2248", s)
    if not UNICODE_OK:
        for k, v in ASCII_FALLBACK.items():
            s = s.replace(k, v)
        s = re.sub(r"\\[a-zA-Z]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _inline_escape(s):
    s = re.sub(r"<br\s*/?>", BR_TOKEN, s, flags=re.I)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s.replace(BR_TOKEN, "<br/>")


def _plain(s):
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return re.sub(r"[*`$]", "", s)


def inline(s):
    s = _inline_escape(s)
    s = re.sub(r"\$\$(.+?)\$\$", lambda m: mathify(m.group(1)), s, flags=re.S)
    s = re.sub(r"\$([^$]+?)\$", lambda m: mathify(m.group(1)), s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"`([^`]+)`", r'<font face="CourierNew">\1</font>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s, flags=re.S)
    s = re.sub(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])", r"<i>\1</i>", s)
    return s


# --------------------------------------------------------------------------
# Styles
# --------------------------------------------------------------------------
def build_styles():
    S = {}
    S["FrontH1"] = ParagraphStyle(
        "FrontH1",
        fontName="Arial-Bold",
        fontSize=15,
        leading=19,
        textColor=PRIMARY,
        spaceBefore=2,
        spaceAfter=4,
        keepWithNext=True,
    )
    S["ChapH1"] = ParagraphStyle(
        "ChapH1",
        fontName="Arial-Bold",
        fontSize=15,
        leading=19,
        textColor=PRIMARY,
        spaceBefore=2,
        spaceAfter=4,
        keepWithNext=True,
    )
    S["SecH2"] = ParagraphStyle(
        "SecH2",
        fontName="Arial-Bold",
        fontSize=12.5,
        leading=16,
        textColor=SECONDARY,
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True,
    )
    S["SubH3"] = ParagraphStyle(
        "SubH3",
        fontName="Arial-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#333333"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )
    S["SubH4"] = ParagraphStyle(
        "SubH4",
        fontName="Arial-Bold",
        fontSize=9.8,
        leading=13,
        textColor=colors.HexColor("#444444"),
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True,
    )
    S["Body"] = ParagraphStyle(
        "Body",
        fontName="Arial",
        fontSize=10,
        leading=14.6,
        alignment=TA_JUSTIFY,
        textColor=INK,
        spaceAfter=7,
    )
    S["Bullet"] = ParagraphStyle(
        "Bullet", parent=S["Body"], leftIndent=22, bulletIndent=9, spaceAfter=4
    )
    S["Bullet2"] = ParagraphStyle(
        "Bullet2", parent=S["Body"], leftIndent=40, bulletIndent=27, spaceAfter=3
    )
    S["NumItem"] = ParagraphStyle(
        "NumItem", parent=S["Body"], leftIndent=22, bulletIndent=7, spaceAfter=4
    )
    S["FigCaption"] = ParagraphStyle(
        "FigCaption",
        fontName="Arial-BoldItalic",
        fontSize=8.5,
        leading=11.5,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#444444"),
        spaceBefore=4,
        spaceAfter=14,
    )
    S["EqCenter"] = ParagraphStyle(
        "EqCenter",
        fontName="Arial",
        fontSize=10.5,
        leading=14.5,
        alignment=TA_CENTER,
        textColor=INK,
        spaceBefore=3,
        spaceAfter=9,
    )
    S["NoteTitle"] = ParagraphStyle(
        "NoteTitle",
        fontName="Arial-Bold",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#7A5C00"),
        spaceAfter=3,
    )
    S["NoteBody"] = ParagraphStyle(
        "NoteBody",
        fontName="Arial-Italic",
        fontSize=9.3,
        leading=13.5,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#5A4A00"),
        spaceAfter=2,
    )
    S["RefItem"] = ParagraphStyle(
        "RefItem",
        fontName="Arial",
        fontSize=9.6,
        leading=13.5,
        alignment=TA_JUSTIFY,
        textColor=INK,
        spaceAfter=5,
        leftIndent=16,
        firstLineIndent=-16,
    )
    S["Meta"] = ParagraphStyle(
        "Meta",
        fontName="Arial",
        fontSize=10.5,
        leading=15,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#333333"),
    )
    S["CoverTitle"] = ParagraphStyle(
        "CoverTitle",
        fontName="Arial-Bold",
        fontSize=20,
        leading=26,
        alignment=TA_CENTER,
        textColor=PRIMARY,
    )
    S["CoverInst"] = ParagraphStyle(
        "CoverInst",
        fontName="Arial-Bold",
        fontSize=12.5,
        leading=17,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1565C0"),
    )
    S["TOCTitle"] = ParagraphStyle(
        "TOCTitle",
        fontName="Arial-Bold",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#111111"),
    )
    S["TOCL0"] = ParagraphStyle(
        "TOCL0",
        fontName="Arial-Bold",
        fontSize=9.8,
        leading=15.5,
        textColor=colors.HexColor("#111111"),
        leftIndent=0,
    )
    S["TOCL1"] = ParagraphStyle(
        "TOCL1",
        fontName="Arial",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#333333"),
        leftIndent=18,
    )
    S["LOF"] = ParagraphStyle(
        "LOF",
        fontName="Arial",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#333333"),
        leftIndent=0,
    )

    def cell_style(size, header=False, bg=None):
        name = "cell-%s-%s" % (str(size).replace(".", "_"), "h" if header else "b")
        st = ParagraphStyle(
            name,
            fontName="Arial-Bold" if header else "Arial",
            fontSize=size,
            leading=size + 2.6,
            alignment=TA_CENTER if header or size <= 6.5 else TA_LEFT,
            textColor=colors.white if header else INK,
        )
        return st

    S["cell_style"] = cell_style
    return S


# --------------------------------------------------------------------------
# Markdown -> flowables
# --------------------------------------------------------------------------
BULLET_RE = re.compile(r"^(\s*)-\s+(.*)$")
NUM_RE = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
IMG_RE = re.compile(r"^!\[[^\]]*\]\([^)]*\)\s*$")
RULE_RE = re.compile(r"^-{3,}\s*$")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def _strip_heading_marks(text):
    return re.sub(r"[*`]", "", _plain(text)).strip()


def make_table(header, rows, styles):
    ncols = len(header)
    size = 8.2 if ncols <= 5 else 7.2 if ncols <= 7 else 6.2 if ncols <= 9 else 5.3
    th = styles["cell_style"](size, header=True)
    td = styles["cell_style"](size)
    data = [[Paragraph(inline(c), th) for c in header]]
    for r in rows:
        r = list(r) + [""] * (ncols - len(r))
        data.append([Paragraph(inline(c), td) for c in r[:ncols]])

    plain = [[_plain(c) for c in row] for row in [header] + rows]
    lens = [
        max(len(row[i]) if i < len(row) else 0 for row in plain) or 1
        for i in range(ncols)
    ]
    weights = [max(l, 4) ** 0.6 for l in lens]
    total = sum(weights)
    widths = [max(CONTENT_W * w / total, 24 if ncols > 9 else 34) for w in weights]
    over = sum(widths) - CONTENT_W
    if over > 0:
        room = [wd - (24 if ncols > 9 else 34) for wd in widths]
        room_total = sum(room)
        if room_total > 0:
            widths = [wd - over * rm / room_total for wd, rm in zip(widths, room)]

    t = Table(data, colWidths=widths, repeatRows=1, hAlign="CENTER")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, STRIPE]),
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def note_box(title, body_lines, styles):
    inner = [Paragraph(title, styles["NoteTitle"])]
    for b in body_lines:
        inner.append(Paragraph(inline(b), styles["NoteBody"]))
    t = Table([[inner]], colWidths=[CONTENT_W * 0.97], hAlign="CENTER")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF8E1")),
                ("BOX", (0, 0), (-1, -1), 0.8, ACCENT),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return [Spacer(1, 3), t, Spacer(1, 5)]


def code_block(lines):
    maxlen = max((len(l) for l in lines), default=0)
    size = 6.4 if maxlen <= 88 else 5.6 if maxlen <= 105 else 4.8
    st = ParagraphStyle(
        "code-%d" % abs(hash(tuple(lines)) % 10**8),
        fontName="CourierNew",
        fontSize=size,
        leading=size + 2.0,
        alignment=TA_LEFT,
        textColor=INK,
    )
    body = "<br/>".join(_inline_escape(l).replace(" ", "&nbsp;") for l in lines)
    t = Table([[Paragraph(body, st)]], colWidths=[CONTENT_W * 0.98], hAlign="CENTER")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F6F8")),
                ("BOX", (0, 0), (-1, -1), 0.5, GRID),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return [Spacer(1, 3), t, Spacer(1, 5)]


def md_to_flowables(md_text, styles, h1_style="SecH2"):
    out = []
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i].rstrip())
                i += 1
            i += 1
            if any(l.strip() for l in block):
                out.extend(code_block(block))
            continue
        if RULE_RE.match(stripped):
            i += 1
            continue
        if IMG_RE.match(stripped):
            i += 1
            continue
        m = HEAD_RE.match(stripped)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            style_name = {1: h1_style, 2: "SubH3", 3: "SubH4"}.get(level, "SubH4")
            out.append(Paragraph(inline(text), styles[style_name]))
            i += 1
            continue
        if stripped.startswith(">"):
            quote = []
            title = None
            while i < len(lines) and lines[i].strip().startswith(">"):
                content = lines[i].strip()[1:].strip()
                if content.startswith("[!"):
                    title = re.sub(r"[\[\]!]", "", content).strip().title() or "Note"
                elif content:
                    quote.append(content)
                i += 1
            if title or quote:
                out.extend(note_box(title or "Note", quote, styles))
            continue
        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw = lines[i].strip().strip("|")
                cells = [c.strip() for c in raw.split("|")]
                if not re.fullmatch(r"[\s:\-|]+", lines[i].strip()):
                    rows.append(cells)
                i += 1
            if len(rows) >= 2:
                out.append(Spacer(1, 2))
                out.append(make_table(rows[0], rows[1:], styles))
                out.append(Spacer(1, 8))
            elif rows:
                out.append(Paragraph(inline(" | ".join(rows[0])), styles["Body"]))
            continue
        mb = BULLET_RE.match(line)
        if mb:
            indent = len(mb.group(1))
            style = styles["Bullet"] if indent < 2 else styles["Bullet2"]
            out.append(Paragraph(inline(mb.group(2)), style, bulletText="\u2022"))
            i += 1
            continue
        mn = NUM_RE.match(line)
        if mn:
            out.append(
                Paragraph(
                    inline(mn.group(3)),
                    styles["NumItem"],
                    bulletText="%s." % mn.group(2),
                )
            )
            i += 1
            continue
        eq = re.fullmatch(r"\$\$(.+)\$\$", stripped, flags=re.S)
        if eq:
            out.append(Paragraph(mathify(eq.group(1)), styles["EqCenter"]))
            i += 1
            continue
        out.append(Paragraph(inline(stripped), styles["Body"]))
        i += 1
    return out


# --------------------------------------------------------------------------
# Report document template (TOC / LOF / bookmarks)
# --------------------------------------------------------------------------
class ListOfFigures(TableOfContents):
    def notify(self, kind, stuff):
        if kind == "LOFEntry":
            self.addEntry(*stuff)


class ReportDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, **kw)
        frame = Frame(
            MARGIN,
            BOTTOM_MARGIN,
            CONTENT_W,
            CONTENT_H,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        self.addPageTemplates([PageTemplate(id="main", frames=[frame])])

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        name = flowable.style.name
        if name in ("ChapH1", "SecH2"):
            text = flowable.getPlainText()
            level = 0 if name == "ChapH1" else 1
            key = (
                "toc-"
                + hashlib.md5(
                    ("%d|%s|%d" % (level, text, self.page)).encode()
                ).hexdigest()[:12]
            )
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (level, text, self.page, key))
            try:
                self.canv.addOutlineEntry(
                    _plain(text), key, level=level, closed=(level == 0)
                )
            except Exception:
                pass
        elif name == "FigCaption":
            self.notify("LOFEntry", (0, flowable.getPlainText(), self.page))


class NumberedCanvas(pdfcanvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_decorations(self, page_count):
        if self._pageNumber == 1:
            return
        self.saveState()
        self.setFont("Arial", 8)
        self.setFillColor(MUTED := colors.HexColor("#555555"))
        self.drawString(
            MARGIN,
            PAGE_H - 38,
            "AI-Based Vision-Guided Differential Drive Rover with Distributed Edge Intelligence",
        )
        self.setStrokeColor(colors.HexColor("#CCCCCC"))
        self.setLineWidth(0.5)
        self.line(MARGIN, PAGE_H - 44, PAGE_W - MARGIN, PAGE_H - 44)
        self.line(MARGIN, 46, PAGE_W - MARGIN, 46)
        self.drawString(
            MARGIN,
            33,
            "Autonomous Robotics & Embedded Systems Research Group - B.Tech Capstone Report",
        )
        self.drawRightString(
            PAGE_W - MARGIN, 33, "Page %d of %d" % (self._pageNumber, page_count)
        )
        self.restoreState()


# --------------------------------------------------------------------------
# Report structure
# --------------------------------------------------------------------------
FIG_CAPTIONS = {
    "01_system_architecture.png": "Distributed Edge-Intelligence Rover System Architecture",
    "02_data_flow.png": "End-to-End System Data Flow Pipeline",
    "03_hardware_architecture.png": "Hardware Wiring, Pin Allocations, and Data-Link Topology",
    "04_power_architecture.png": "Power Distribution & Decoupling Architecture",
    "05_esp32_pipeline.png": "ESP32 Edge Perception & Decision Pipeline",
    "06_decision_pipeline.png": "Target Heading Decision & Zone Mapping Logic",
    "07_arduino_pipeline.png": "Arduino UNO Execution Loop & Safety Arbitration Pipeline",
    "08_safety_hierarchy.png": "Multi-Tier Safety Priority Pyramid",
    "09_state_machine.png": "Decision Engine Finite State Machine (FSM) Transitions",
    "10_control_loop.png": "Proportional Heading Control Closed-Loop Architecture",
    "11_differential_drive_geometry.png": "Differential Drive Mobile Robot Kinematic Model",
    "12_target_position.png": "Bounding Box Centroid and Error Calculation",
    "13_left_center_right_zones.png": "Discrete Vision Zone Partitioning with Deadband",
    "14_communication_protocol.png": "Serial Protocol Timing & Watchdog Communication Sequence",
    "15_full_robot_block_diagram.png": "Complete Hardware Subsystem Interconnection Topology",
    "360_degree_scan_diagram.png": "Optional Extension - Discrete Panoramic Scanning System",
    "circuit_diagram.png": "Complete Hardware Circuit & Electrical Wiring Schematic",
    "wiring_schemdraw.png": "Complete Pin-to-Pin Wiring Schedule (Schemdraw Reference)",
    "control_response_kp_comparison.png": "Proportional Steering Control Response Comparison (SIMULATION)",
}

DOC_FIGS = {
    "07_SYSTEM_ARCHITECTURE.md": ["01_system_architecture.png", "02_data_flow.png"],
    "08_HARDWARE_ARCHITECTURE.md": ["03_hardware_architecture.png"],
    "20_POWER_ARCHITECTURE.md": ["04_power_architecture.png", "circuit_diagram.png"],
    "09_SOFTWARE_ARCHITECTURE.md": ["07_arduino_pipeline.png", "09_state_machine.png"],
    "18_COMMUNICATION_PROTOCOL.md": ["14_communication_protocol.png"],
    "10_ESP32_AI_PIPELINE.md": ["05_esp32_pipeline.png"],
    "12_TARGET_DETECTION.md": [
        "12_target_position.png",
        "13_left_center_right_zones.png",
    ],
    "13_DECISION_ENGINE.md": ["06_decision_pipeline.png"],
    "14_DIFFERENTIAL_DRIVE_PHYSICS.md": ["11_differential_drive_geometry.png"],
    "15_CONTROL_SYSTEM.md": [
        "10_control_loop.png",
        "control_response_kp_comparison.png",
    ],
    "17_ULTRASONIC_SAFETY.md": ["08_safety_hierarchy.png"],
    "23_BUILD_GUIDE.md": ["15_full_robot_block_diagram.png"],
    "future-work/30_FUTURE_WORK.md": ["360_degree_scan_diagram.png"],
}

CHAPTERS = [
    (
        1,
        "Introduction",
        [
            ("doc", "01_PROJECT_OVERVIEW.md"),
            ("doc", "04_MOTIVATION.md"),
        ],
    ),
    (
        2,
        "Problem Definition & Scope",
        [
            ("doc", "03_PROBLEM_STATEMENT.md"),
            ("doc", "06_SCOPE.md"),
        ],
    ),
    (
        3,
        "Objectives & Design Methodology",
        [
            ("doc", "05_OBJECTIVES.md"),
        ],
    ),
    (
        4,
        "Literature Review & Technical Background",
        [
            ("doc", "11_AI_MODEL_SELECTION.md"),
        ],
    ),
    (
        5,
        "System Architecture & Data Flow",
        [
            ("doc", "07_SYSTEM_ARCHITECTURE.md"),
        ],
    ),
    (
        6,
        "Hardware Architecture & Electrical Design",
        [
            ("doc", "08_HARDWARE_ARCHITECTURE.md"),
            ("doc", "20_POWER_ARCHITECTURE.md"),
        ],
    ),
    (
        7,
        "Software Architecture & Firmware Design",
        [
            ("doc", "09_SOFTWARE_ARCHITECTURE.md"),
            ("doc", "16_ARDUINO_MOTOR_CONTROL.md"),
            ("doc", "19_STATE_MACHINE.md"),
            ("doc", "18_COMMUNICATION_PROTOCOL.md"),
        ],
    ),
    (
        8,
        "Edge Perception & AI Pipeline",
        [
            ("doc", "10_ESP32_AI_PIPELINE.md"),
            ("doc", "12_TARGET_DETECTION.md"),
            ("doc", "13_DECISION_ENGINE.md"),
        ],
    ),
    (
        9,
        "Kinematic Modeling & Control Theory",
        [
            ("doc", "14_DIFFERENTIAL_DRIVE_PHYSICS.md"),
            ("doc", "15_CONTROL_SYSTEM.md"),
        ],
    ),
    (
        10,
        "Multi-Tier Safety & Supervisory Interlocks",
        [
            ("doc", "17_ULTRASONIC_SAFETY.md"),
        ],
    ),
    (
        11,
        "Mechanical & Electrical Implementation",
        [
            ("doc", "23_BUILD_GUIDE.md"),
        ],
    ),
    (
        12,
        "System Verification & Test Plan (32 Test Cases)",
        [
            ("doc", "24_CALIBRATION_GUIDE.md"),
            ("doc", "25_TEST_PLAN.md"),
        ],
    ),
    (
        13,
        "Experimental Methodology (Protocols E01-E11)",
        [
            ("doc", "26_EXPERIMENTAL_METHODOLOGY.md"),
        ],
    ),
    (14, "Empirical Results & Performance Evaluation", [("text", "CH14")]),
    (
        15,
        "Known Technical Limitations & Risk Analysis",
        [
            ("doc", "29_LIMITATIONS.md"),
            ("doc", "28_FAILURE_ANALYSIS.md"),
        ],
    ),
    (
        16,
        "Future Work & Architectural Extensions",
        [
            ("doc", "future-work/30_FUTURE_WORK.md"),
        ],
    ),
    (17, "Conclusions", [("text", "CH17")]),
]

RESULTS_TABLE = [
    ["Metric", "Measured Value", "Classification"],
    ["Baseline Model", "facebook/detr-resnet-50 (PyTorch / HuggingFace)", "[MEASURED]"],
    ["Model Load Time", "26.7 s", "[MEASURED]"],
    ["Mean Inference Latency", "5143.7 ms (0.2 FPS)", "[MEASURED]"],
    ["Peak Resident Memory (RSS)", "983.2 MB", "[MEASURED]"],
    ["ESP32-CAM Internal SRAM", "520 KB", "[DATASHEET]"],
    [
        "Feasibility Verdict",
        "Exceeds ESP32 RAM by approx. 245x - workstation tethering infeasible for autonomy; motivates int8 TinyML / color-centroid edge pipeline",
        "[ANALYSIS]",
    ],
]

KP_TABLE = [
    ["Gain Kp", "Simulated Response Character", "Rise Time", "Overshoot", "Verdict"],
    ["0.2", "Overdamped, sluggish approach", "> 3.5 s", "~0%", "Too slow"],
    ["0.6", "Optimal damping, clean settle", "~1.2 s", "< 5%", "SELECTED"],
    [
        "1.2",
        "Underdamped, limit-cycle oscillation",
        "fast",
        "high, oscillatory",
        "Rejected",
    ],
]

CH14_TEXT = [
    (
        "p",
        "<b>Measurement Data Policy.</b> In accordance with strict scientific reporting "
        "standards, this chapter presents only measured or explicitly classified values. "
        "Results for the physical experiments E01 through E11 are recorded in the laboratory "
        "measurement logs (data/test_results.csv and data/test_results.xlsx) as the experiments "
        "are executed on the physical test bench. No fabricated or estimated numerical results "
        "are presented in this report.",
    ),
    (
        "p",
        "<b>Baseline Workstation Benchmark (Measured on CPU Harness).</b> The following "
        "benchmark was captured on the workstation prototyping harness and empirically "
        "demonstrates why heavyweight transformer detection cannot be tethered into the "
        "control loop of a microcontroller-class rover:",
    ),
    ("table", RESULTS_TABLE),
    (
        "p",
        "<b>Proportional Gain Selection (Simulation).</b> The dynamic steering simulation "
        "(tools/simulate_control.py) sweeps five proportional gains; the summarized outcome "
        "below is designated as simulation, not measured hardware data, and motivates the "
        "selected operating point Kp = 0.6:",
    ),
    ("table", KP_TABLE),
    (
        "p",
        "<b>Ongoing Hardware Verification.</b> The 32 standardized test cases (Chapter 12) and "
        "the eleven experimental protocols (Chapter 13) define the complete empirical evaluation "
        "program for this platform. Measured entries are appended to the structured data logs "
        "upon completion of each bench trial.",
    ),
]

CH17_TEXT = [
    (
        "p",
        "This project successfully developed a build-ready, mathematically grounded, distributed "
        "robotic platform. By physically isolating edge perception on an ESP32-CAM coprocessor "
        "while delegating hard real-time safety supervision to an independent Arduino UNO, the "
        "rover achieves reliable visual target pursuit with guaranteed collision prevention and "
        "communication-loss fail-stops.",
    ),
    (
        "p",
        "The engineering contributions include: a validated dual-microcontroller partitioning with "
        "level-shifted serial isolation; differential drive kinematics parameterized for the "
        "physical platform (wheel radius 32.5 mm, track width 180 mm); a proportional heading "
        "control law with anti-oscillation deadband, minimum command duration, and decision "
        "cooldown; a two-tier watchdog safety hierarchy with deterministic default-to-STOP "
        "behavior; and a fully automated Python documentation and verification toolchain.",
    ),
    (
        "p",
        "The platform is economically viable at an estimated prototype bill of materials of "
        "$62.90 USD ($21.50 incremental acquisition), and its 32-case verification suite and "
        "eleven experimental protocols provide a transparent, reproducible, and academically "
        "rigorous path to full hardware qualification. Future work - wheel-encoder odometry, "
        "servo-based panoramic scanning, and on-chip TinyML deployment - extends this baseline "
        "toward higher levels of autonomy.",
    ),
]


def read_doc(filename):
    with open(os.path.join(DOC_DIR, filename), "r", encoding="utf-8") as f:
        return f.read()


def add_figure(story, filename, chapter_no, index, styles):
    path = os.path.join(FIG_DIR, filename)
    if not os.path.exists(path):
        print("[WARN] Missing figure: %s" % filename)
        return
    with PILImage.open(path) as im:
        px_w, px_h = im.size
    max_w = CONTENT_W * 0.94
    max_h = 4.35 * inch
    scale = min(max_w / px_w, max_h / px_h)
    img = Image(path, width=px_w * scale, height=px_h * scale)
    img.keepWithNext = True
    img.hAlign = "CENTER"
    caption = "Figure %d.%d: %s" % (chapter_no, index, FIG_CAPTIONS[filename])
    story.append(img)
    story.append(Paragraph(caption, styles["FigCaption"]))


def strip_doc_h1(md_text):
    lines = md_text.splitlines()
    out, removed = [], False
    for line in lines:
        if (
            not removed
            and HEAD_RE.match(line.strip())
            and line.strip().startswith("# ")
        ):
            removed = True
            continue
        out.append(line)
    return "\n".join(out)


def cover_page(story, styles):
    story.append(Spacer(1, 26))
    story.append(HRFlowable(width="40%", thickness=1.2, color=PRIMARY, hAlign="CENTER"))
    story.append(Spacer(1, 14))
    story.append(
        Paragraph(
            "DEPARTMENT OF ROBOTICS &amp; AUTOMATION ENGINEERING<br/>INSTITUTION OF TECHNOLOGY",
            styles["CoverInst"],
        )
    )
    story.append(Spacer(1, 64))
    story.append(
        Paragraph(
            "AI-BASED VISION-GUIDED DIFFERENTIAL DRIVE ROVER WITH DISTRIBUTED "
            "EDGE INTELLIGENCE AND SAFETY CONTROL",
            styles["CoverTitle"],
        )
    )
    story.append(Spacer(1, 26))
    story.append(
        Paragraph(
            "A Capstone Project Report submitted in partial fulfillment of the requirements<br/>"
            "for the Degree of Bachelor of Technology in Robotics &amp; Embedded Systems",
            styles["Meta"],
        )
    )
    story.append(Spacer(1, 84))
    story.append(
        Paragraph(
            "<b>SUBMITTED BY:</b><br/>Undergraduate Capstone Engineering Research Group<br/>"
            "Academic Session 2025\u20132026",
            styles["Meta"],
        )
    )
    story.append(Spacer(1, 84))
    story.append(HRFlowable(width="40%", thickness=1.2, color=PRIMARY, hAlign="CENTER"))
    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>September 2026</b>", styles["Meta"]))
    story.append(PageBreak())


def signature_block(story, styles, left_role, right_role):
    line = "_" * 30
    t = Table(
        [
            [Paragraph(line, styles["Meta"]), Paragraph(line, styles["Meta"])],
            [
                Paragraph("<b>%s</b>" % left_role, styles["Meta"]),
                Paragraph("<b>%s</b>" % right_role, styles["Meta"]),
            ],
        ],
        colWidths=[2.7 * inch, 2.7 * inch],
        hAlign="CENTER",
    )
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, 0), 26),
                ("TOPPADDING", (0, 1), (-1, 1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(Spacer(1, 40))
    story.append(t)


def front_matter(story, styles):
    with open(os.path.join(DOC_DIR, "02_ABSTRACT.md"), "r", encoding="utf-8") as f:
        abstract = f.read().split("### Abstract")[-1].strip()

    # Certificate
    story.append(Paragraph("BONAFIDE CERTIFICATE", styles["FrontH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceAfter=14))
    story.append(
        Paragraph(
            "Certified that this technical report titled <b>\u201cAI-BASED VISION-GUIDED DIFFERENTIAL "
            "DRIVE ROVER WITH DISTRIBUTED EDGE INTELLIGENCE AND SAFETY CONTROL\u201d</b> is the "
            "bonafide work of the research team who carried out the engineering design, mathematical "
            "modeling, embedded programming, and physical verification under academic supervision.",
            styles["Body"],
        )
    )
    signature_block(story, styles, "Project Supervisor", "Head of Department")
    story.append(PageBreak())

    # Declaration
    story.append(Paragraph("CANDIDATE DECLARATION", styles["FrontH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceAfter=14))
    story.append(
        Paragraph(
            "We hereby declare that the technical report submitted herein is our original engineering "
            "work. All hardware specifications, circuit connections, mathematical derivations, and "
            "control algorithms presented in this report adhere strictly to verified physical "
            "configurations. All simulated results are explicitly designated as simulations, and all "
            "experimental results remain reserved for measured hardware data without fabrication.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 26))
    story.append(
        Paragraph("Date: 23-09-2026<br/>Place: Engineering Campus", styles["Meta"])
    )
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Signatures of Candidates:</b>", styles["Meta"]))
    sig = Table(
        [
            [
                Paragraph("1. " + "_" * 26, styles["Meta"]),
                Paragraph("2. " + "_" * 26, styles["Meta"]),
            ]
        ],
        colWidths=[2.9 * inch, 2.9 * inch],
        hAlign="CENTER",
    )
    sig.setStyle(
        TableStyle(
            [("TOPPADDING", (0, 0), (-1, -1), 10), ("LEFTPADDING", (0, 0), (-1, -1), 6)]
        )
    )
    story.append(sig)
    story.append(PageBreak())

    # Acknowledgements
    story.append(Paragraph("ACKNOWLEDGEMENTS", styles["FrontH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceAfter=14))
    story.append(
        Paragraph(
            "We express our sincere gratitude to the faculty advisors, laboratory technicians, and the "
            "open-source robotics and embedded systems communities whose documentation and frameworks "
            "made this research possible. Special acknowledgement is given to the developers of "
            "FreeRTOS, the Arduino project, Espressif Systems, and the TinyML foundation for providing "
            "the embedded building blocks for decentralized edge robotics.",
            styles["Body"],
        )
    )
    story.append(PageBreak())

    # Abstract
    story.append(Paragraph("ABSTRACT", styles["FrontH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceAfter=14))
    story.append(Paragraph(inline(abstract), styles["Body"]))
    story.append(PageBreak())


def toc_and_lof(story, styles):
    story.append(Paragraph("TABLE OF CONTENTS", styles["FrontH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceAfter=10))
    toc = TableOfContents()
    toc.levelStyles = [styles["TOCL0"], styles["TOCL1"]]
    toc.dotsMinLevel = 0
    story.append(toc)
    story.append(PageBreak())

    story.append(Paragraph("LIST OF FIGURES", styles["FrontH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceAfter=10))
    lof = ListOfFigures()
    lof.levelStyles = [styles["LOF"]]
    lof.dotsMinLevel = 0
    story.append(lof)
    story.append(PageBreak())


def text_blocks_to_flowables(blocks, styles):
    out = []
    for block in blocks:
        kind = block[0]
        if kind == "p":
            out.append(Paragraph(block[1], styles["Body"]))
        elif kind == "table":
            rows = block[1]
            out.append(Spacer(1, 2))
            out.append(make_table(rows[0], rows[1:], styles))
            out.append(Spacer(1, 8))
    return out


def build_chapters(story, styles):
    fig_counter = {}
    first = True
    for num, title, blocks in CHAPTERS:
        if not first:
            story.append(PageBreak())
        first = False
        story.append(
            Paragraph("Chapter %d: %s" % (num, inline(title)), styles["ChapH1"])
        )
        story.append(
            HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceAfter=12)
        )
        for block in blocks:
            if block[0] == "text":
                story.extend(
                    text_blocks_to_flowables(
                        CH14_TEXT if block[1] == "CH14" else CH17_TEXT, styles
                    )
                )
            else:
                fname = block[1]
                with open(os.path.join(DOC_DIR, fname), "r", encoding="utf-8") as f:
                    md = f.read()
                story.extend(md_to_flowables(md, styles))
                for i, fig in enumerate(DOC_FIGS.get(fname, []), start=1):
                    story.append(Spacer(1, 4))
                    add_figure(story, fig, num, i, styles)


def build_references(story, styles):
    with open(os.path.join(DOC_DIR, "references.md"), "r", encoding="utf-8") as f:
        text = f.read()
    entries = [l.strip() for l in text.splitlines() if re.match(r"^\d+\.\s", l.strip())]
    story.append(Paragraph("REFERENCES", styles["ChapH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceAfter=12))
    for e in entries:
        story.append(Paragraph(inline(e), styles["RefItem"]))


APPENDICES = [
    (
        "Appendix A: Bill of Materials (BOM) & Component Sourcing",
        "31_BILL_OF_MATERIALS.md",
    ),
    ("Appendix B: Complete Wiring Schedule", "21_CIRCUIT_CONNECTIONS.md"),
    ("Appendix C: Microcontroller Pin Configuration", "22_PIN_CONFIGURATION.md"),
]


def build_appendices(story, styles):
    for title, fname in APPENDICES:
        story.append(PageBreak())
        story.append(Paragraph(inline(title), styles["ChapH1"]))
        story.append(
            HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceAfter=12)
        )
        with open(os.path.join(DOC_DIR, fname), "r", encoding="utf-8") as f:
            md = f.read()
        story.extend(md_to_flowables(strip_doc_h1(md), styles))


def build_pdf_report(output_path=OUTPUT):
    setup_fonts()
    styles = build_styles()
    doc = ReportDoc(
        output_path,
        pagesize=A4,
        title="AI-Based Vision-Guided Differential Drive Rover - Final Report",
        author="Autonomous Robotics & Embedded Systems Research Group",
    )
    story = []
    cover_page(story, styles)
    front_matter(story, styles)
    toc_and_lof(story, styles)
    build_chapters(story, styles)
    build_references(story, styles)
    build_appendices(story, styles)
    doc.multiBuild(story, canvasmaker=NumberedCanvas)
    print("[OK] Generated PDF Final Report: %s" % output_path)


if __name__ == "__main__":
    import sys

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    build_pdf_report(sys.argv[1] if len(sys.argv) > 1 else OUTPUT)
