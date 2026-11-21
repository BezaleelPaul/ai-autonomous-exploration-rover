"""Test support utilities: path resolution, source readers, and C header parsers."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Ensure software, scripts, and simulator are importable across all test runners
for extra in (ROOT / "software", ROOT / "scripts", ROOT / "simulator", ROOT):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))


def read(relpath: str | Path) -> str:
    """Read a text file relative to the repository ROOT."""
    path = Path(relpath)
    if not path.is_absolute():
        path = ROOT / path
    return path.read_text(encoding="utf-8")


def section(text: str, start: str, end: str | None = None) -> str:
    """Extract a slice of text between start marker and end marker."""
    i = text.find(start)
    if i == -1:
        raise ValueError(f"start marker {start!r} not found")
    if end is not None:
        j = text.find(end, i + len(start))
        if j != -1:
            return text[i:j]
    return text[i:]


def c_constants(text: str) -> dict[str, Any]:
    """Parse C/C++ constants (constexpr and #define) from source code."""
    constants: dict[str, Any] = {}
    pattern = re.compile(
        r'(?:constexpr\s+[a-zA-Z0-9_:<>*&]+\s+|#define\s+)([a-zA-Z0-9_]+)\s*=?\s*([^\s;]+)'
    )
    for match in pattern.finditer(text):
        name, val = match.groups()
        val = val.strip().rstrip('uUlLfF')
        try:
            if val.startswith(("0x", "0X")):
                constants[name] = int(val, 16)
            elif "." in val:
                constants[name] = float(val)
            else:
                constants[name] = int(val)
        except ValueError:
            constants[name] = val.strip('"')
    return constants
