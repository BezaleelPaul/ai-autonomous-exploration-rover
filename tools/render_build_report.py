"""Render reports/ROVER_BUILD_REPORT.md to a styled HTML with live Mermaid diagrams.

Run:  py -3.12 tools/render_build_report.py
Out:  reports/ROVER_BUILD_REPORT.html
"""

from __future__ import annotations

import pathlib
import re

import markdown

SRC = pathlib.Path("reports/ROVER_BUILD_REPORT.md")
DST = pathlib.Path("reports/ROVER_BUILD_REPORT.html")

MERMAID_RE = re.compile(
    r'<pre><code class="language-mermaid">(.*?)</code></pre>', re.DOTALL
)

TEMPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>AI Exploration Rover - Documented Build Report</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({startOnLoad:true,theme:'neutral'});</script>
<style>
body{font-family:Georgia,serif;max-width:900px;margin:40px auto;padding:0 24px;
     line-height:1.6;color:#222;background:#fdfcfa}
h1{font-size:2rem;border-bottom:3px solid #1a7f37;padding-bottom:8px}
h2{color:#1a5c37;border-bottom:1px solid #ddd;padding-bottom:4px;margin-top:2rem}
h3{color:#333;margin-top:1.4rem}
table{border-collapse:collapse;width:100%;font-size:.92rem;margin:1rem 0}
th{background:#1a7f37;color:#fff;text-align:left;padding:8px}
td{border:1px solid #ddd;padding:6px 8px;vertical-align:top}
tr:nth-child(even){background:#f4f9f6}
blockquote{background:#fffbe6;border-left:5px solid #f0a500;margin:1rem 0;
           padding:.7rem 1rem}
code,pre{font-family:Consolas,monospace;font-size:.88rem;background:#f2f2f2;
         border-radius:6px}
pre{padding:12px;overflow-x:auto;border:1px solid #e2e2e2}
.mermaid{background:#fff;border:1px solid #e2e2e2;border-radius:8px;padding:10px;
         overflow-x:auto}
strong{color:#111}
hr{border:0;border-top:2px dashed #ccc;margin:2rem 0}
</style></head><body>"""


def render() -> None:
    src = SRC.read_text(encoding="utf-8")
    body = markdown.markdown(src, extensions=["extra", "tables", "fenced_code"])
    body = MERMAID_RE.sub(r'<div class="mermaid">\1</div>', body)
    DST.write_text(TEMPLATE + body + "</body></html>", encoding="utf-8")
    print(f"HTML written: {DST} ({DST.stat().st_size} bytes)")


if __name__ == "__main__":
    render()
