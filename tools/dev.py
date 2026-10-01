"""Fast dev loop: one command for gates, watch mode for tweak-test cycles.

Usage (repo root):
  py -3.12 tools\\dev.py                 # ruff + full pytest, once
  py -3.12 tools\\dev.py --quick         # ruff + pytest -x (stop first fail)
  py -3.12 tools\\dev.py --watch         # re-run quick gates on file changes
  py -3.12 tools\\dev.py --fix           # apply ruff autofixes first
  py -3.12 tools\\dev.py --hw            # also run hardware checks (board attached)

Exit code: 0 = all gates green, 1 = something failed.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

WATCH_EXTS = {".py", ".ino", ".yaml", ".yml", ".json", ".toml", ".md"}
WATCH_DIRS = {"tests", "software", "arduino", "esp32", "config", "docs", "tools"}
WATCH_SKIP = {"__pycache__", ".git", "node_modules", ".venv"}


def _run(label: str, cmd: list[str]) -> bool:
    print(f"--- {label} ", flush=True)
    t0 = time.perf_counter()
    rc = subprocess.call(cmd, cwd=ROOT)
    dt = time.perf_counter() - t0
    ok = rc == 0
    print(f"--- {label}: {'OK' if ok else 'FAIL'} ({dt:.1f}s)\n", flush=True)
    return ok


def gates(quick: bool, fix: bool) -> bool:
    ok = True
    if fix:
        ok &= _run(
            "ruff --fix", [PY, "-m", "ruff", "check", "--fix", "software", "tests"]
        )
    ok &= _run("ruff", [PY, "-m", "ruff", "check", "software", "tests"])
    pytest_args = [PY, "-m", "pytest", "tests", "-q"]
    if quick:
        pytest_args.append("-x")
    ok &= _run("pytest", pytest_args)
    return ok


def hw_checks() -> bool:
    return _run("hw_check all", [PY, "tools/hw_check.py", "all"])


def _snapshot() -> dict[Path, float]:
    out: dict[Path, float] = {}
    for d in WATCH_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.suffix in WATCH_EXTS and not any(s in p.parts for s in WATCH_SKIP):
                try:
                    out[p] = p.stat().st_mtime
                except OSError:
                    pass
    return out


def watch(quick: bool) -> None:
    print("watching for changes (Ctrl+C to stop)", flush=True)
    prev = _snapshot()
    while True:
        time.sleep(1.0)
        cur = _snapshot()
        changed = [p for p, m in cur.items() if prev.get(p) != m]
        if not changed:
            continue
        rel = ", ".join(str(p.relative_to(ROOT)) for p in sorted(changed)[:5])
        print(f"\n=== change: {rel} ===", flush=True)
        ok = gates(quick=quick, fix=False)
        print("=== PASS ===" if ok else "=== FAIL ===", flush=True)
        prev = cur


def main() -> int:
    ap = argparse.ArgumentParser(description="fast dev loop")
    ap.add_argument(
        "--quick", action="store_true", help="pytest -x (stop on first fail)"
    )
    ap.add_argument("--watch", action="store_true", help="re-run gates on file changes")
    ap.add_argument("--fix", action="store_true", help="apply ruff autofixes first")
    ap.add_argument("--hw", action="store_true", help="also run hardware checks")
    args = ap.parse_args()

    if args.watch:
        try:
            watch(quick=True)
        except KeyboardInterrupt:
            print("\nstopped")
        return 0

    ok = gates(quick=args.quick, fix=args.fix)
    if args.hw:
        ok &= hw_checks()
    print("ALL GREEN" if ok else "FAILURES ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
