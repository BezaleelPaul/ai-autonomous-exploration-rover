"""Offline auto-calibration of the detector's operating point.

Runs the same labelled benchmark as ``scripts/eval_detection.py`` once per
candidate value of each offline dial, then keeps the cheapest one:

* ``ai.confidence_threshold`` — what counts as "seen" (precision/recall knob)
* ``ai.min_box_px``           — smallest box the rover will act on
* ``ai.iou_threshold``        — NMS merge aggressiveness (duplicates)

The cost of a candidate is its operating-point F1 (1 - f1), plus a hard
penalty when it breaks the H4 realtime closure measured by the benchmark, so
the tuner can never trade away the loop-closing refresh rate for accuracy.

Exploration is exhaustive and bounded — every candidate of every dial is
measured, then the cheapest is committed — so the run always terminates at a
value rather than a hunch. Convergence is a fixed point: a full pass over all
dials that leaves every value unchanged stops the sweep. Committed values are
written to ``config/learned.yaml`` with ``--write``; ``load_config`` merges
that file in as ``file < learned < environment`` on every later session, and
the online governor re-derives only the session-local inference interval.

This is *calibration*, not tuning on a test set: it runs against the labelled
COCO128 images the accuracy benchmark already uses, and it never touches
safety, serial, navigation or rover geometry.

Usage:
    py -3.12 scripts/autotune_detection.py [--data datasets/coco128]
        [--config config/config.yaml] [--limit 40] [--passes 3]
        [--write] [--out logs/autotune_detection.json] [--json]

Exit codes: 0 success, 2 input/dataset error.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import eval_detection  # noqa: E402
from software.autotune.core import apply_learned  # noqa: E402
from software.autotune.factory import (  # noqa: E402
    build_offline_tuner,
    write_learned,
)
from software.autotune.store import flatten, learned_overlay  # noqa: E402
from software.utils.config_loader import load_config  # noqa: E402

DEFAULT_CONFIG = ROOT / "config" / "config.yaml"
DEFAULT_OUT = ROOT / "logs" / "autotune_detection.json"
REALTIME_PENALTY = 1000.0
DEFAULT_PASSES = 3


def cost_of(report: dict[str, Any]) -> tuple[float, bool]:
    """``(cost, feasible)`` for one candidate: F1 deficit, gated on realtime."""
    f1 = float(report["operating_point"]["f1"])
    closes = bool(report["h4_realtime"]["closes_loop"])
    return (1.0 - f1) + (0.0 if closes else REALTIME_PENALTY), closes


def _measure(
    args: argparse.Namespace, base_set: list[str], overrides: list[str]
) -> dict:
    """One full labelled benchmark with the given dials applied."""
    trial = copy.copy(args)
    trial.set = list(base_set) + list(overrides)
    return eval_detection.run_benchmark(trial)


def _overrides_for(
    tuner_values: dict[str, Any], name: str, candidate: Any
) -> list[str]:
    dialled = dict(tuner_values)
    dialled[name] = candidate
    return [f"{key}={value}" for key, value in dialled.items()]


def sweep(
    tuner: Any,
    args: argparse.Namespace,
    base_set: list[str],
    *,
    log: bool = True,
) -> list[dict[str, Any]]:
    """Evaluate every owed candidate of every dial, then commit each dial."""
    rows: list[dict[str, Any]] = []
    for name in tuner.names():
        for candidate in tuner.next(name):
            started = time.time()
            overrides = _overrides_for(tuner.values(), name, candidate)
            report = _measure(args, base_set, overrides)
            cost, feasible = cost_of(report)
            op = report["operating_point"]
            tuner.report(name, {candidate: (cost, feasible)})
            row = {
                "dial": name,
                "candidate": candidate,
                "cost": round(cost, 6),
                "feasible": feasible,
                "f1": op["f1"],
                "precision": op["precision"],
                "recall": op["recall"],
                "duplicates": op["duplicate_detections"],
                "p50_ms": report["latency_ms"]["p50"],
                "seconds": round(time.time() - started, 1),
            }
            rows.append(row)
            if log:
                print(
                    f"  {name} = {candidate:<6} f1 {op['f1']:.3f} "
                    f"({op['precision']:.3f}/{op['recall']:.3f}) "
                    f"dup {op['duplicate_detections']} "
                    f"p50 {report['latency_ms']['p50']:.0f} ms "
                    f"-> cost {cost:.4f}" + ("" if feasible else "  [BREAKS H4]"),
                    flush=True,
                )
    return rows


def run_autotune(args: argparse.Namespace) -> dict[str, Any]:
    """Sweep every dial until the values stop changing; return a report dict."""
    cfg = load_config(str(args.config))
    settings_learned_path = str(cfg.get("autotune", {}).get("learned_path", ""))
    if args.write and not settings_learned_path:
        raise ValueError(
            "config.yaml has no autotune.learned_path; nothing to persist to"
        )

    started = time.time()
    values: dict[str, Any] = flatten(learned_overlay(settings_learned_path))
    seeded = dict(values)
    all_rows: list[dict[str, Any]] = []
    converged = False
    passes = 0
    for pass_index in range(args.passes):
        passes = pass_index + 1
        tuner, _settings = build_offline_tuner(copy.deepcopy(cfg))
        # Start this pass from the answer the previous pass committed, so the
        # sweep is coordinate descent and stops at a fixed point.
        apply_learned(tuner, values)
        if not tuner.enabled:
            break
        print(f"pass {passes}/{args.passes}:", flush=True)
        all_rows.extend(sweep(tuner, args, args.set))
        updated = tuner.values()
        if updated == values:
            converged = True
            print("  values unchanged -> converged", flush=True)
            break
        values = updated

    written = False
    final, settings = build_offline_tuner(copy.deepcopy(cfg))
    apply_learned(final, values)
    if args.write:
        written = write_learned(final, settings, source="autotune_detection")

    return {
        "label": "CALIBRATED",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": str(args.config),
        "learned_path": settings_learned_path,
        "seeded_from": seeded,
        "committed": final.values(),
        "changed": final.learned(),
        "passes": passes,
        "converged": converged,
        "written": written,
        "measurements": len(all_rows),
        "elapsed_s": round(time.time() - started, 1),
        "trials": all_rows,
    }


def render(report: dict[str, Any]) -> str:
    lines = [
        f"Label: {report['label']} | {report['passes']} pass(es), "
        f"{report['measurements']} measurements in {report['elapsed_s']:.0f} s "
        f"-> {'CONVERGED' if report['converged'] else 'pass limit reached'}",
        "",
        f"{'DIAL':<28}{'SEEDED':>10}{'COMMITTED':>12}{'DELTA':>10}",
    ]
    for dial, value in report["committed"].items():
        seeded = report["seeded_from"].get(dial)
        seeded_str = "-" if seeded is None else str(seeded)
        delta = "" if seeded == value else "changed"
        lines.append(f"{dial:<28}{seeded_str:>10}{value!s:>12}{delta:>10}")
    lines.append("")
    if report["written"]:
        lines.append(f"Persisted {report['learned_path']} (merged in by load_config)")
    elif not report["changed"]:
        lines.append("No change worth persisting; overlay left as it is")
    else:
        lines.append("Dry run: pass --write to persist the committed values")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Auto-calibrate the detector operating point on labelled data."
    )
    parser.add_argument("--data", type=Path, default=eval_detection.DEFAULT_DATA)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="held-fixed override for every trial (repeatable)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=40,
        help="images per trial (full eval is scripts/eval_detection.py)",
    )
    parser.add_argument(
        "--passes", type=int, default=DEFAULT_PASSES, help="max full sweeps"
    )
    parser.add_argument("--iou", type=float, default=0.5, help="eval match IoU")
    parser.add_argument("--latency-frames", type=int, default=20)
    parser.add_argument("--latency-repeats", type=int, default=1)
    parser.add_argument("--ap-conf", type=float, default=eval_detection.AP_CONFIDENCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--write",
        action="store_true",
        help="persist committed values to autotune.learned_path",
    )
    parser.add_argument("--json", action="store_true", help="print only JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.passes < 1:
        print("error: --passes must be >= 1", file=sys.stderr)
        return 2
    try:
        report = run_autotune(args)
    except (eval_detection.DatasetError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print()
        print(render(report))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not args.json:
        print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
