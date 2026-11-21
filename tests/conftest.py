"""Pytest path setup: makes every test module work standalone.

Before this file, modules that did not import ``support`` (e.g. test_steering)
only passed because an earlier test module had already inserted software/ into
sys.path. That masked import-order bugs.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "software", ROOT / "scripts", ROOT / "simulator"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))
