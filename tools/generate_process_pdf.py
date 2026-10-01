"""Team-facing process walkthrough PDF generator.

Source:  docs/PROCESS_WALKTHROUGH.md
Output:  reports/AI_Rover_Process_Walkthrough.pdf

Reuses the publication engine in tools/generate_pdf.py (fonts, styles,
markdown->flowables, figure embedding, TOC/LOF, outline bookmarks, numbered
canvas) so both PDFs share one look and one caption source.

Figure markers in the markdown use the form:  ![Figure: <filename>.png]
"""

import os
import re
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS_DIR)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import generate_pdf as gp  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    HRFlowable,
    PageBreak,
    Paragraph,
    Spacer,
)

DOC = os.path.join(ROOT, "docs", "PROCESS_WALKTHROUGH.md")
OUTPUT = os.path.join(ROOT, "reports", "AI_Rover_Process_Walkthrough.pdf")

FIG_RE = re.compile(r"^!\[Figure:\s*([^\]]+?)\s*\]\s*$")
SEC_RE = re.compile(r"^#\s+(\d+)\.\s+(.*)$")


def _cover(story, styles):
    """Standalone cover page for the walkthrough."""
    story.append(Spacer(1, 40))
    story.append(
        HRFlowable(width="40%", thickness=1.2, color=gp.PRIMARY, hAlign="CENTER")
    )
    story.append(Spacer(1, 18))
    story.append(
        Paragraph(
            "TEAM GUIDE &mdash; CAPSTONE ENGINEERING PROCESS", styles["CoverInst"]
        )
    )
    story.append(Spacer(1, 70))
    story.append(
        Paragraph(
            "AI-BASED VISION-GUIDED DIFFERENTIAL DRIVE ROVER<br/>PROCESS WALKTHROUGH",
            styles["CoverTitle"],
        )
    )
    story.append(Spacer(1, 22))
    story.append(
        Paragraph(
            "How the robot works, how everything is connected, how to run it,<br/>"
            "and how it was verified &mdash; start to finish",
            styles["Meta"],
        )
    )
    story.append(Spacer(1, 90))
    story.append(
        Paragraph(
            "Autonomous Robotics &amp; Embedded Systems Research Group<br/>"
            "Academic Session 2025&ndash;2026",
            styles["Meta"],
        )
    )
    story.append(Spacer(1, 70))
    story.append(
        HRFlowable(width="40%", thickness=1.2, color=gp.PRIMARY, hAlign="CENTER")
    )
    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>September 2026</b>", styles["Meta"]))
    story.append(PageBreak())


def _split(md_text):
    """Split markdown into text chunks and figure markers.

    A text chunk starts at a top-level '# ' section heading (or the very
    beginning) so a page break can be inserted before each new section.
    Returns a list of ("text" | "fig", payload) tuples.
    """
    tokens = []
    cur = []
    in_fence = False
    for line in md_text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            cur.append(line)
            continue
        if in_fence:
            cur.append(line)
            continue
        m = FIG_RE.match(line.strip())
        if m:
            if any(s.strip() for s in cur):
                tokens.append(("text", "\n".join(cur)))
            cur = []
            tokens.append(("fig", m.group(1)))
            continue
        if line.startswith("# ") and cur:
            if any(s.strip() for s in cur):
                tokens.append(("text", "\n".join(cur)))
            cur = [line]
            continue
        cur.append(line)
    if any(s.strip() for s in cur):
        tokens.append(("text", "\n".join(cur)))
    return tokens


def _section_chunk(chunk_md, styles, is_first):
    """Render one section: heading + rule + markdown body."""
    lines = chunk_md.splitlines()
    m = SEC_RE.match(lines[0].strip())
    if not m:
        # Not a numbered section (rare) - just render inline.
        return list(gp.md_to_flowables(chunk_md, styles, h1_style="ChapH1"))
    out = []
    if not is_first:
        out.append(PageBreak())
    out.append(
        Paragraph(gp.inline("%s. %s" % (m.group(1), m.group(2))), styles["ChapH1"])
    )
    out.append(HRFlowable(width="100%", thickness=1, color=gp.PRIMARY, spaceAfter=12))
    body = "\n".join(lines[1:])
    out.extend(gp.md_to_flowables(body, styles, h1_style="ChapH1"))
    return out


def build_walkthrough_pdf(output_path=OUTPUT):
    gp.setup_fonts()
    styles = gp.build_styles()
    doc = gp.ReportDoc(
        output_path,
        pagesize=gp.A4,
        title="AI Rover - Process Walkthrough (Team Guide)",
        author="Autonomous Robotics & Embedded Systems Research Group",
    )

    with open(DOC, "r", encoding="utf-8") as f:
        md_text = f.read()

    story = []
    _cover(story, styles)
    gp.toc_and_lof(story, styles)

    section_no = 0
    fig_index = 0
    first = True
    for kind, payload in _split(md_text):
        if kind == "fig":
            fig_index += 1
            gp.add_figure(story, payload, max(section_no, 1), fig_index, styles)
            continue
        m = SEC_RE.match(payload.splitlines()[0].strip())
        if m:
            section_no = int(m.group(1))
            fig_index = 0
        story.extend(_section_chunk(payload, styles, first))
        first = False

    doc.multiBuild(story, canvasmaker=gp.NumberedCanvas)
    print("[OK] Generated Process Walkthrough PDF: %s" % output_path)
    return output_path


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    target = sys.argv[1] if len(sys.argv) > 1 else OUTPUT
    build_walkthrough_pdf(target)
