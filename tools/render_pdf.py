#!/usr/bin/env python3
"""Render the generated DOCX report to PDF through Pandoc and headless Chrome.

Word's PDF export hangs in the headless session, so the report is converted to
HTML with Pandoc and printed by Chrome.  A first pass measures the page number
of every heading, figure, and table; the second pass writes those numbers into
the table of contents and lists, then Chrome prints the final PDF.  Page
footers and PDF bookmarks are added with PyMuPDF.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import fitz
import pypandoc
from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "reports" / "AI_Rover_Project_Report.docx"
HTML_PATH = ROOT / "reports" / "AI_Rover_Project_Report_print.html"
TOC_SOURCE = ROOT / "reports" / "AI_Rover_Project_Report_toc_source.html"
PASS1 = ROOT / "reports" / "_report_pass1.pdf"
PASS2 = ROOT / "reports" / "_report_pass2.pdf"
PDF_PATH = ROOT / "reports" / "AI_Rover_Project_Report.pdf"
MEDIA_DIR = ROOT / "reports" / "pdf_media"

CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]

FRONT_HEADINGS = {
    "ACKNOWLEDGEMENT",
    "DECLARATION",
    "ABSTRACT",
    "DOCUMENTATION NOTE",
    "TABLE OF CONTENTS",
    "LIST OF FIGURES",
    "LIST OF TABLES",
    "LIST OF ABBREVIATIONS",
}

CSS = r"""
@page { size: A4; margin: 2.2cm 2.0cm 2.0cm 2.2cm; }
html, body { background: #fff; }
body {
  margin: 0;
  padding: 0;
  max-width: none;
  font-family: "Times New Roman", serif;
  color: #1a1a1a;
  font-size: 11.5pt;
  line-height: 1.45;
}
.cover { text-align: center; }
.cover p { text-align: center; }
.cover p.toc-entry { text-align: left; }
.cover table { width: 90%; margin: 10pt auto; }
.cover table th { background: none; color: #1a1a1a; border: none; font-size: 10.5pt; }
.cover blockquote { font-size: 18pt; font-weight: bold; color: #0B2E59; margin: 8pt auto 16pt; width: 92%; }
.certificate { break-before: page; text-align: center; }
.certificate p { text-align: center; }
.certificate table { width: 90%; margin: 20pt auto; }
.certificate table th { background: none; color: #1a1a1a; border: none; }
.cert-title { font-size: 18pt; font-weight: bold; color: #0B2E59; text-align: center; margin: 10pt 0 14pt; }
.front-heading {
  break-before: page;
  font-size: 16pt;
  font-weight: bold;
  color: #0B2E59;
  text-align: center;
  margin: 0 0 14pt;
}
.kicker {
  break-before: page;
  font-family: Calibri, sans-serif;
  font-size: 10pt;
  font-weight: bold;
  color: #7F7F7F;
  text-transform: uppercase;
  text-align: left;
  margin: 0 0 2pt;
}
h1 { font-size: 16pt; color: #0B2E59; margin: 0 0 10pt; break-before: auto; break-after: avoid; }
h2 { font-size: 13.5pt; color: #1F4E79; margin: 12pt 0 6pt; break-after: avoid; }
h3 { font-size: 12pt; color: #2E5C8A; margin: 8pt 0 4pt; break-after: avoid; }
p { font-family: "Times New Roman", serif; font-size: 11.5pt; line-height: 1.45; text-align: justify; margin: 0 0 6pt; }
li { font-family: "Times New Roman", serif; font-size: 11.2pt; line-height: 1.35; margin-bottom: 2pt; }
figure { break-inside: avoid; text-align: center; margin: 8pt 0; }
figure img { max-width: 100%; max-height: 11.5cm; width: auto; height: auto; }
figcaption { font-size: 9pt; font-style: italic; color: #444; text-align: center; }
figcaption p { font-size: 9pt; font-style: italic; color: #444; text-align: center; }
table { width: 100%; border-collapse: collapse; margin: 6pt 0 10pt; font-size: 8.4pt; }
th { background: #0B2E59; color: #fff; font-family: Calibri, sans-serif; font-weight: bold; padding: 4pt; border: 0.5pt solid #C9D3E0; text-align: center; }
td { border: 0.5pt solid #C9D3E0; padding: 3pt 4pt; vertical-align: middle; font-family: Calibri, sans-serif; }
tbody tr:nth-child(even) { background: #F2F2F2; }
caption { caption-side: top; text-align: center; font-size: 9pt; font-style: italic; color: #444; margin-bottom: 3pt; }
.toc-entry { display: flex; justify-content: space-between; gap: 8pt; font-size: 10pt; text-align: left; margin: 0 0 2pt; }
.toc-entry a { flex: 1; text-decoration: none; color: #1a1a1a; }
.toc-entry .page { white-space: nowrap; }
blockquote { margin: 8pt 0; padding: 0 12pt; border: none; }
"""


def _is_blank(node) -> bool:
    return isinstance(node, NavigableString) and not str(node).strip()


def _wrap_range(
    start: Tag, end: Tag | None, css_class: str, soup: BeautifulSoup
) -> Tag:
    wrapper = soup.new_tag("div")
    wrapper["class"] = css_class
    start.insert_before(wrapper)
    node = start
    while node is not None and node is not end:
        next_node = node.next_sibling
        if not _is_blank(node) or node is start:
            wrapper.append(node.extract())
        else:
            node.extract()
        node = next_node
    return wrapper


def _convert_to_html(docx: Path, output: Path) -> None:
    pypandoc.convert_file(
        str(docx),
        "html",
        outputfile=str(output),
        extra_args=["--standalone", f"--extract-media={MEDIA_DIR}"],
    )


def _parse_toc_entries() -> dict[str, list[str]]:
    soup = BeautifulSoup(TOC_SOURCE.read_text(encoding="utf-8"), "lxml")
    entries: dict[str, list[str]] = {"toc": [], "lof": [], "lot": []}
    section = None
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if text in (
            "TABLE OF CONTENTS",
            "LIST OF FIGURES",
            "LIST OF TABLES",
            "LIST OF ABBREVIATIONS",
        ):
            section = {
                "TABLE OF CONTENTS": "toc",
                "LIST OF FIGURES": "lof",
                "LIST OF TABLES": "lot",
            }.get(text)
            continue
        a = p.find("a", href=True)
        if a is None or a.find("span") is None:
            continue
        if section in entries:
            entries[section].append(a["href"])
    return entries


def _add_class(tag: Tag, name: str) -> None:
    classes = list(tag.get("class", []))
    if name not in classes:
        classes.append(name)
    tag["class"] = classes


def _decorate_html(page_map: dict[str, str] | None = None) -> None:
    soup = BeautifulSoup(HTML_PATH.read_text(encoding="utf-8"), "lxml")

    header = soup.find("header", id="title-block-header")
    if header is not None:
        header.decompose()

    for wrapper in soup.find_all("div", class_=["cover", "certificate"]):
        wrapper.unwrap()

    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if text in FRONT_HEADINGS:
            _add_class(p, "front-heading")
        elif (
            re.fullmatch(r"CHAPTER \d+", text)
            or re.fullmatch(r"APPENDIX [A-E]", text)
            or text == "REFERENCES"
        ):
            _add_class(p, "kicker")
        elif text == "CERTIFICATE":
            _add_class(p, "cert-title")

    for p in soup.find_all("p"):
        for span in p.find_all("span", class_="page"):
            span.decompose()
        a = p.find("a", href=True)
        if a is None:
            continue
        span = a.find("span")
        if span is None:
            continue
        label = span.get_text(strip=True)
        if re.fullmatch(r"[0-9ivxlcdm]+", label, flags=re.IGNORECASE):
            span.decompose()
            _add_class(p, "toc-entry")

    if page_map:
        for p in soup.find_all("p", class_="toc-entry"):
            a = p.find("a", href=True)
            if a is None:
                continue
            page = page_map.get(a["href"])
            if page:
                span = soup.new_tag("span")
                span["class"] = "page"
                span.string = page
                p.append(span)

    school_marks = [
        p
        for p in soup.find_all("p")
        if p.get_text(strip=True) == "SCHOOL OF ENGINEERING AND TECHNOLOGY"
    ]
    cert_start = school_marks[1] if len(school_marks) > 1 else None
    front_start = soup.find("p", class_="front-heading")
    cover_start = next(
        (child for child in soup.body.children if isinstance(child, Tag)),
        None,
    )
    if cert_start is not None and front_start is not None:
        cert_wrap = _wrap_range(cert_start, front_start, "certificate", soup)
        if cover_start is not None and cover_start is not cert_wrap:
            _wrap_range(cover_start, cert_wrap, "cover", soup)

    style = soup.new_tag("style")
    style.string = CSS
    soup.head.append(style)
    HTML_PATH.write_text(str(soup), encoding="utf-8")


def _chrome_path() -> Path:
    for candidate in CHROME_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Chrome or Edge was not found")


def _print_pdf(html_path: Path, pdf_path: Path) -> None:
    if pdf_path.exists():
        pdf_path.unlink()
    chrome = _chrome_path()
    uri = html_path.resolve().as_uri()
    cmd = [
        str(chrome),
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--allow-file-access-from-files",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path.resolve()}",
        uri,
    ]
    subprocess.run(
        cmd, timeout=300, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if not pdf_path.exists():
        raise RuntimeError(f"Chrome did not produce {pdf_path}")


def _roman(number: int) -> str:
    values = [
        (1000, "m"),
        (900, "cm"),
        (500, "d"),
        (400, "cd"),
        (100, "c"),
        (90, "xc"),
        (50, "l"),
        (40, "xl"),
        (10, "x"),
        (9, "ix"),
        (5, "v"),
        (4, "iv"),
        (1, "i"),
    ]
    out = []
    for value, symbol in values:
        while number >= value:
            out.append(symbol)
            number -= value
    return "".join(out)


def _extract_blocks(
    pdf_path: Path,
) -> tuple[
    int, list[tuple[int, float, str]], list[tuple[int, str]], list[tuple[int, str]]
]:
    doc = fitz.open(pdf_path)
    body_start = None
    for index in range(doc.page_count):
        if "CHAPTER 1" in doc[index].get_text():
            body_start = index
            break
    if body_start is None:
        raise RuntimeError("Could not find the start of Chapter 1 in the PDF")

    headings: list[tuple[int, float, str]] = []
    figures: list[tuple[int, str]] = []
    tables: list[tuple[int, str]] = []
    for index in range(body_start, doc.page_count):
        page = doc[index]
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            spans = [
                span
                for line in block.get("lines", [])
                for span in line.get("spans", [])
                if span.get("text", "").strip()
            ]
            if not spans:
                continue
            text = " ".join(span["text"].strip() for span in spans).strip()
            if not text:
                continue
            if text.startswith("Page "):
                continue
            size = max(span["size"] for span in spans)
            if text.startswith("Figure "):
                figures.append((index - body_start + 1, text))
            elif text.startswith("Table "):
                tables.append((index - body_start + 1, text))
            elif size >= 12.0:
                headings.append((index - body_start + 1, size, text))
    doc.close()
    return body_start, headings, figures, tables


def _build_page_map(
    pdf_path: Path,
) -> tuple[dict[str, str], list[tuple[int, float, str]], int]:
    entries = _parse_toc_entries()
    body_start, headings, figures, tables = _extract_blocks(pdf_path)

    page_map: dict[str, str] = {}
    for href, (page, _size, _text) in zip(entries["toc"], headings):
        page_map[href] = str(page)
    for href, (page, _text) in zip(entries["lof"], figures):
        page_map[href] = str(page)

    doc = fitz.open(pdf_path)
    front_page = None
    for index in range(body_start):
        if "LIST OF ABBREVIATIONS" in doc[index].get_text():
            front_page = _roman(index - 1)
            break
    doc.close()
    if entries["lot"]:
        if front_page:
            page_map[entries["lot"][0]] = front_page
        for href, (page, _text) in zip(entries["lot"][1:], tables):
            page_map[href] = str(page)
    return page_map, headings, body_start


def _add_furniture(
    pdf_path: Path, headings: list[tuple[int, float, str]], body_start: int
) -> None:
    doc = fitz.open(pdf_path)
    total_body = doc.page_count - body_start
    for index in range(doc.page_count):
        page = doc[index]
        if index < 2:
            continue
        if index < body_start:
            label = _roman(index - 1)
        else:
            label = f"Page {index - body_start + 1} of {total_body}"
        width = fitz.get_text_length(label, fontname="Times-Roman", fontsize=9)
        page.insert_text(
            ((page.rect.width - width) / 2, 812),
            label,
            fontname="Times-Roman",
            fontsize=9,
            color=(0.45, 0.45, 0.45),
        )
        if index >= body_start:
            header = "AI Vision-Guided Rover"
            page.insert_text(
                (56, 30),
                header,
                fontname="Times-Roman",
                fontsize=8.5,
                color=(0.45, 0.45, 0.45),
            )
            right = "CMR University"
            rw = fitz.get_text_length(right, fontname="Times-Roman", fontsize=8.5)
            page.insert_text(
                (page.rect.width - 56 - rw, 30),
                right,
                fontname="Times-Roman",
                fontsize=8.5,
                color=(0.45, 0.45, 0.45),
            )

    toc = []
    for page, size, text in headings:
        level = 1 if size >= 15 else 2 if size >= 13 else 3
        toc.append([level, text, page + body_start])
    doc.set_toc(toc)
    doc.set_metadata(
        {
            "title": "AI-Based Vision-Guided Autonomous Rover with Distributed Edge Intelligence and Safety Control",
            "author": "KUNDURU NAGENDRA REDDY (18BBTCS053)",
            "subject": "B.Tech project report, CMR University, 2026-2027",
            "keywords": "autonomous rover, ESP32-CAM, YOLO, Arduino, safety, TB6612FNG",
        }
    )
    tmp = pdf_path.with_suffix(".tmp.pdf")
    doc.save(str(tmp), garbage=4, deflate=True)
    doc.close()
    tmp.replace(pdf_path)


def main() -> None:
    _convert_to_html(DOCX, TOC_SOURCE)
    _convert_to_html(DOCX, HTML_PATH)
    _decorate_html()
    _print_pdf(HTML_PATH, PASS1)
    page_map, headings, body_start = _build_page_map(PASS1)
    for _ in range(2):
        _convert_to_html(DOCX, HTML_PATH)
        _decorate_html(page_map)
        _print_pdf(HTML_PATH, PASS2)
        page_map2, headings2, body_start2 = _build_page_map(PASS2)
        if page_map2 == page_map:
            break
        page_map = page_map2
    _add_furniture(PASS2, headings2, body_start2)
    if PDF_PATH.exists():
        PDF_PATH.unlink()
    PASS2.replace(PDF_PATH)
    print(f"Wrote {PDF_PATH}")


if __name__ == "__main__":
    main()
