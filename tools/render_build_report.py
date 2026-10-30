"""Render reports/ROVER_BUILD_REPORT.md to a modern, responsive HTML report.

Run:  py -3.12 tools/render_build_report.py
Out:  reports/ROVER_BUILD_REPORT.html
"""

from __future__ import annotations

import pathlib
import re
import markdown

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "reports" / "ROVER_BUILD_REPORT.md"
DST = ROOT / "reports" / "ROVER_BUILD_REPORT.html"

MERMAID_RE = re.compile(
    r'<pre><code class="language-mermaid">(.*?)</code></pre>', re.DOTALL
)

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Autonomous Exploration Rover — Capstone Project Expo 2026</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({startOnLoad:true, theme:'neutral'});</script>
<style>
:root {
  --primary: #0b2e59;
  --secondary: #1a5c37;
  --text: #1e293b;
  --bg: #f8fafc;
  --card-bg: #ffffff;
  --border: #e2e8f0;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  max-width: 960px;
  margin: 30px auto;
  padding: 0 24px;
  line-height: 1.65;
  color: var(--text);
  background: var(--bg);
}
.report-container {
  background: var(--card-bg);
  padding: 40px 48px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.06);
  border: 1px solid var(--border);
}
h1 {
  font-size: 2.2rem;
  color: var(--primary);
  border-bottom: 3px solid var(--secondary);
  padding-bottom: 12px;
  margin-top: 0;
  line-height: 1.25;
}
h2 {
  font-size: 1.5rem;
  color: var(--primary);
  border-bottom: 1px solid var(--border);
  padding-bottom: 6px;
  margin-top: 2.4rem;
}
h3 {
  font-size: 1.2rem;
  color: var(--secondary);
  margin-top: 1.6rem;
}
h4 {
  font-size: 1.05rem;
  color: #475569;
}
table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.90rem;
  margin: 1.4rem 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
th {
  background: var(--primary);
  color: #ffffff;
  text-align: left;
  padding: 10px 12px;
  font-weight: 600;
}
td {
  border: 1px solid var(--border);
  padding: 8px 12px;
  vertical-align: top;
}
tr:nth-child(even) {
  background: #f8fafc;
}
blockquote {
  background: #fffbeb;
  border-left: 5px solid #d97706;
  margin: 1.4rem 0;
  padding: 0.8rem 1.2rem;
  border-radius: 0 8px 8px 0;
  color: #78350f;
}
code, pre {
  font-family: "Cascadia Code", Consolas, "Courier New", monospace;
  font-size: 0.88rem;
  background: #f1f5f9;
  border-radius: 6px;
}
code {
  padding: 2px 6px;
  color: #0f766e;
}
pre {
  padding: 14px 16px;
  overflow-x: auto;
  border: 1px solid #cbd5e1;
  line-height: 1.45;
}
pre code {
  padding: 0;
  color: #0f172a;
  background: transparent;
}
.mermaid {
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  overflow-x: auto;
  margin: 1.5rem 0;
}
img {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 1.5rem auto;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
hr {
  border: 0;
  border-top: 1px dashed var(--border);
  margin: 2.5rem 0;
}
ul, ol {
  padding-left: 24px;
}
li {
  margin-bottom: 6px;
}
.badge {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: bold;
  background: #dcfce7;
  color: #166534;
}
</style>
</head>
<body>
<div class="report-container">
"""

def render() -> None:
    src = SRC.read_text(encoding="utf-8")
    body = markdown.markdown(src, extensions=["extra", "tables", "fenced_code"])
    body = MERMAID_RE.sub(r'<div class="mermaid">\1</div>', body)
    DST.write_text(TEMPLATE + body + "</div></body></html>", encoding="utf-8")
    print(f"HTML written: {DST} ({DST.stat().st_size} bytes)")


if __name__ == "__main__":
    render()
