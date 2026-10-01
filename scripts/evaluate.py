"""Evaluate collected control-loop telemetry (dataset eval harness).

Reads the CSV produced by the running app, checks every row against the
protocol/safety contracts, and prints a report plus a JSON summary.

Usage:
    python scripts/evaluate.py [--csv logs/events.csv] [--out logs/eval.json]
                               [--min-rows 1] [--strict] [--json]

Exit codes: 0 success, 1 invariants violated (--strict only), 2 input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from software.telemetry.event_eval import (  # noqa: E402
    EvalError,
    load_events,
    summarize,
)

DEFAULT_CSV = ROOT / "logs" / "events.csv"
DEFAULT_OUT = ROOT / "logs" / "eval.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate telemetry collected in logs/events.csv."
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="input CSV")
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help="output JSON path"
    )
    parser.add_argument(
        "--min-rows",
        type=int,
        default=1,
        help="fail when fewer valid rows than this are available",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when a safety/protocol invariant is violated",
    )
    parser.add_argument(
        "--json", action="store_true", help="print only the JSON summary"
    )
    parser.add_argument(
        "--no-write", action="store_true", help="skip writing the JSON report"
    )
    return parser


def _bar(fraction: float, width: int = 24) -> str:
    filled = max(0, min(width, round(fraction * width)))
    return "#" * filled + "-" * (width - filled)


def render(report: dict) -> str:
    """Format the summary dict as a fixed-width console report."""
    data = report["dataset"]
    conf = report["confidence"]
    inference = report["inference_ms"]
    safety = report["safety_summary"]
    lines = [
        f"Source: {report['source']}",
        (
            f"Rows: {data['rows']} valid, {data['malformed_rows']} malformed | "
            f"{data['first_timestamp']} -> {data['last_timestamp']} "
            f"({data['span_s']:.0f} s) | runs: {data['runs']}"
        ),
        "",
        f"{'MODE':<12}{'ROWS':>7}{'STOP%':>8}{'F/B%':>8}{'SAFE%':>8}{'DET%':>8}",
    ]
    for mode, detail in report["modes"].items():
        lines.append(
            f"{mode:<12}{detail['rows']:>7}"
            f"{detail['stop_rate'] * 100:>7.1f}%"
            f"{detail['forward_back_rate'] * 100:>7.1f}%"
            f"{(1 - detail['safety_intervention_rate']) * 100:>7.1f}%"
            f"{detail['detected_rate'] * 100:>7.1f}%"
        )

    lines += ["", f"{'DECISION':<10}{'ROWS':>7}{'SHARE':>9}"]
    for cmd, detail in report["decisions"].items():
        lines.append(f"{cmd:<10}{detail['rows']:>7}{detail['share'] * 100:>8.1f}%")
        lines.append(f"  {_bar(detail['share'])}")

    lines += ["", f"{'SAFETY REASON':<28}{'ROWS':>7}{'SHARE':>9}"]
    for reason, detail in report["safety"].items():
        lines.append(f"{reason:<28}{detail['rows']:>7}{detail['share'] * 100:>8.1f}%")

    lines += [
        "",
        (
            f"Detection rate : {conf['detection_rate'] * 100:.1f}% "
            f"({conf['detected_rows']} rows)"
        ),
        (
            f"Confidence     : p50 {conf['p50']}  p95 {conf['p95']}  "
            f"mean {conf['mean']}  max {conf['max']}"
        ),
        (
            f"Distance (cm)  : p50 {report['distance_cm']['p50']}  "
            f"p95 {report['distance_cm']['p95']}  min {report['distance_cm']['min']}  "
            f"({report['distance_cm']['count']} usable readings)"
        ),
        (
            "Distance data  : "
            + ", ".join(
                f"{state} {detail['rows']}"
                for state, detail in report["distance_quality"].items()
            )
        ),
        (
            f"Inference      : {inference['rows_with_timing']} timed rows "
            f"(coverage {inference['timing_coverage'] * 100:.1f}%)  "
            f"p50 {inference['p50']} ms  p95 {inference['p95']} ms  "
            f"within 1.0 s lock: {inference['within_target_lock']}"
        ),
        (
            f"Throughput     : p50 {report['fps']['p50']} FPS  "
            f"p95 {report['fps']['p95']} FPS"
        ),
        (
            f"Oscillation    : {report['oscillation']['command_switches']} command "
            f"switches (rate {report['oscillation']['switch_rate']})"
        ),
        (
            f"Safety         : {safety['interventions']} interventions "
            f"({safety['intervention_rate'] * 100:.1f}%), STOP "
            f"{safety['stop_rate'] * 100:.1f}%, motion "
            f"{safety['motion_rate'] * 100:.1f}%"
        ),
        "",
        f"Invariants     : {'PASS' if report['invariants']['pass'] else 'FAIL'} "
        f"({len(report['invariants']['checked'])} checked, "
        f"{report['invariants']['total_violations']} violations)",
    ]
    for name, count in report["invariants"]["violations"].items():
        if count:
            lines.append(f"  VIOLATED {name}: {count}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        dataset = load_events(args.csv)
    except EvalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if len(dataset.rows) < args.min_rows:
        print(
            f"error: only {len(dataset.rows)} valid rows (--min-rows {args.min_rows})",
            file=sys.stderr,
        )
        return 2

    report = summarize(dataset)
    report["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render(report))

    if not args.no_write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if not args.json:
            print(f"\nWrote {args.out}")

    if args.strict and not report["invariants"]["pass"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
