"""Offline evaluation of control-loop telemetry captured in ``logs/events.csv``.

The harness is pure analysis: it reads the CSV written by
:class:`software.telemetry.event_logger.EventLogger`, validates every row
against the protocol/safety contracts the firmware and ``SafetyManager``
enforce, and returns a JSON-safe summary dict. No row is mutated and no
caller data is modified.

Run it with ``python scripts/evaluate.py``.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from pathlib import Path

EVENT_HEADER = (
    "timestamp",
    "mode",
    "target",
    "confidence",
    "position",
    "distance_cm",
    "decision",
    "safety",
    "infer_ms",
    "fps",
)

#: Serial protocol command alphabet (Protocol v2 allows a PWM suffix, but the
#: logger records the bare command actually actuated).
PROTOCOL_COMMANDS = frozenset("FBLRS")

#: ``SafetyManager.check`` reasons that can only ever emit STOP. Because
#: ``ObstacleAvoidance.override`` only downgrades F/B to S, a blocked verdict
#: can never surface as motion in the log.
BLOCKING_REASONS = frozenset(
    {
        "INVALID_COMMAND",
        "EMERGENCY_LATCH",
        "COMM_LOST",
        "CAMERA_UNHEALTHY",
        "SENSOR_INVALID",
        "SENSOR_UNKNOWN",
        "SENSOR_OUT_OF_RANGE",
        "EMERGENCY_OBSTACLE",
        "LOW_CONFIDENCE",
    }
)

#: Verdicts that only ever permit a turn in place (never translation).
TURN_ONLY_REASONS = frozenset({"CAUTION_UNKNOWN_DISTANCE", "CAUTION_CLOSE_OBSTACLE"})

SLOW_ZONE_REASON = "CAUTION_SLOW_ZONE"
NO_TARGET = "-"
NO_POSITION = "NONE"

#: Two consecutive rows further apart than this are treated as separate runs.
DEFAULT_RUN_GAP_S = 60.0

#: H4 realtime gate: a detection refresh must beat the 1.0 s target-lock.
TARGET_LOCK_S = 1.0

#: Cap on retained per-row parse errors so a corrupt file cannot exhaust RAM.
MAX_ERROR_SAMPLES = 20

_INVARIANT_NAMES = (
    "protocol_alphabet",
    "blocking_reason_implies_stop",
    "turn_only_reason_never_translates",
    "slow_zone_reason_is_forward",
    "no_target_has_zero_confidence",
    "no_target_has_no_position",
    "confidence_in_range",
    "latency_and_fps_non_negative",
    "timestamps_monotonic",
    "usable_distance_required_for_translation",
)

#: Classification of the raw ``distance_cm`` cell, used to keep the range
#: statistics honest and to report data quality instead of hiding it.
DISTANCE_STATES = (
    "ok",
    "absent",
    "non_finite",
    "negative",
    "zero",
    "unparseable",
)


class EvalError(Exception):
    """Raised when the telemetry file cannot be read or makes no sense."""


@dataclass(frozen=True)
class EventRow:
    """One validated telemetry row."""

    timestamp: datetime
    mode: str
    target: str
    confidence: float
    position: str
    distance_cm: float | None
    distance_state: str
    decision: str
    safety: str
    infer_ms: float
    fps: float


@dataclass(frozen=True)
class EventDataset:
    """Validated rows plus a count of everything that had to be skipped."""

    source: str
    rows: tuple[EventRow, ...]
    malformed: int
    errors: tuple[str, ...]


def _to_float(value) -> float | None:
    """Parse a CSV cell into a float, or None when it is absent/unparseable."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "nan", "null"}:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        return None
    return parsed


def _require_float(raw: dict, key: str) -> float:
    parsed = _to_float(raw.get(key))
    if parsed is None:
        raise ValueError(f"{key} is not a number ({raw.get(key)!r})")
    return parsed


def _classify_distance(value) -> tuple[float | None, str]:
    """Split the raw distance cell into ``(value, state)``.

    ``value`` is None for anything non-finite so downstream statistics only
    ever see real numbers; ``state`` keeps *why* it was rejected so the report
    can surface sensor/data defects instead of hiding them.
    """
    if value is None:
        return None, "absent"
    text = str(value).strip()
    if not text or text.lower() in {"none", "null"}:
        return None, "absent"
    if text.lower() == "nan":
        return None, "non_finite"
    if text.lower() in {"inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}:
        return None, "non_finite"
    try:
        parsed = float(text)
    except ValueError:
        return None, "unparseable"
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        return None, "non_finite"
    if parsed < 0.0:
        return parsed, "negative"
    if parsed == 0.0:
        return parsed, "zero"
    return parsed, "ok"


def _parse_row(raw: dict) -> EventRow:
    """Convert one CSV mapping into an :class:`EventRow`.

    Raises ``ValueError`` with a human-readable reason on any defect; the
    caller counts the row as malformed instead of aborting the whole run.
    """
    timestamp = str(raw.get("timestamp") or "").strip()
    if not timestamp:
        raise ValueError("timestamp is empty")
    try:
        parsed_ts = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise ValueError(f"timestamp {timestamp!r} is not ISO-8601") from exc

    mode = str(raw.get("mode") or "").strip()
    decision = str(raw.get("decision") or "").strip().upper()
    safety = str(raw.get("safety") or "").strip()
    if not mode:
        raise ValueError("mode is empty")
    if not decision:
        raise ValueError("decision is empty")
    if not safety:
        raise ValueError("safety is empty")

    distance_cm, distance_state = _classify_distance(raw.get("distance_cm"))
    return EventRow(
        timestamp=parsed_ts,
        mode=mode,
        target=str(raw.get("target") or "").strip() or NO_TARGET,
        confidence=_require_float(raw, "confidence"),
        position=str(raw.get("position") or "").strip() or NO_POSITION,
        distance_cm=distance_cm,
        distance_state=distance_state,
        decision=decision,
        safety=safety,
        infer_ms=_require_float(raw, "infer_ms"),
        fps=_require_float(raw, "fps"),
    )


def load_events(path: str | Path) -> EventDataset:
    """Read and validate a telemetry CSV.

    Raises :class:`EvalError` when the file is missing, the header does not
    match the logger schema, or not a single row parses. Individual bad rows
    are counted rather than fatal.
    """
    csv_path = Path(path)
    if not csv_path.exists():
        raise EvalError(f"telemetry file not found: {csv_path}")
    if not csv_path.is_file():
        raise EvalError(f"telemetry path is not a file: {csv_path}")

    try:
        handle = csv_path.open(newline="", encoding="utf-8")
    except OSError as exc:
        raise EvalError(f"cannot open telemetry file: {csv_path}") from exc

    rows: list[EventRow] = []
    errors: list[str] = []
    malformed = 0
    with handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        missing = [name for name in EVENT_HEADER if name not in header]
        if missing:
            raise EvalError(
                f"{csv_path} is missing required columns: {', '.join(missing)}"
            )
        for line_no, raw in enumerate(reader, start=2):
            if raw is None:
                continue
            try:
                rows.append(_parse_row(raw))
            except ValueError as exc:
                malformed += 1
                if len(errors) < MAX_ERROR_SAMPLES:
                    errors.append(f"line {line_no}: {exc}")

    if not rows:
        raise EvalError(
            f"{csv_path} contains no valid telemetry rows ({malformed} malformed)"
        )
    return EventDataset(
        source=str(csv_path),
        rows=tuple(rows),
        malformed=malformed,
        errors=tuple(errors),
    )


def percentile(sorted_values: list[float], quantile: float) -> float | None:
    """Linear-interpolation percentile of an already sorted, non-empty list."""
    if not sorted_values:
        return None
    if not 0.0 <= quantile <= 1.0:
        raise ValueError(f"quantile must be within [0, 1], got {quantile!r}")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = quantile * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _round(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(value, digits)


def describe(values) -> dict:
    """Count/mean/p50/p95/min/max for a sequence of numbers (unsorted OK)."""
    data = sorted(float(v) for v in values)
    if not data:
        return {
            "count": 0,
            "mean": None,
            "p50": None,
            "p95": None,
            "min": None,
            "max": None,
        }
    return {
        "count": len(data),
        "mean": _round(sum(data) / len(data)),
        "p50": _round(percentile(data, 0.5)),
        "p95": _round(percentile(data, 0.95)),
        "min": _round(data[0]),
        "max": _round(data[-1]),
    }


def _share(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def distribution(rows: tuple[EventRow, ...], attribute: str) -> dict:
    """``{value: {"rows": n, "share": f}}`` sorted by descending frequency."""
    total = len(rows)
    counts = Counter(str(getattr(row, attribute)) for row in rows)
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        key: {"rows": count, "share": _share(count, total)} for key, count in ordered
    }


def _switch_rate(rows: tuple[EventRow, ...]) -> tuple[int, float]:
    if len(rows) < 2:
        return 0, 0.0
    switches = sum(1 for prev, cur in pairwise(rows) if prev.decision != cur.decision)
    return switches, round(switches / (len(rows) - 1), 4)


def _mode_detail(rows: tuple[EventRow, ...], mode_rows: tuple[EventRow, ...]) -> dict:
    total = len(mode_rows)
    motion = sum(1 for row in mode_rows if row.decision in {"F", "B"})
    switches, rate = _switch_rate(mode_rows)
    return {
        "rows": total,
        "share": _share(total, len(rows)),
        "stop_rate": _share(sum(1 for row in mode_rows if row.decision == "S"), total),
        "forward_back_rate": _share(motion, total),
        "safety_intervention_rate": _share(
            sum(1 for row in mode_rows if row.safety != "SAFE"), total
        ),
        "detected_rate": _share(
            sum(1 for row in mode_rows if row.target != NO_TARGET), total
        ),
        "command_switches": switches,
        "switch_rate": rate,
    }


def split_runs(
    rows: tuple[EventRow, ...], gap_s: float = DEFAULT_RUN_GAP_S
) -> list[tuple[EventRow, ...]]:
    """Split rows into runs wherever the timestamp gap exceeds ``gap_s``."""
    if not rows:
        return []
    runs: list[list[EventRow]] = [[rows[0]]]
    for prev, cur in pairwise(rows):
        delta = (cur.timestamp - prev.timestamp).total_seconds()
        if delta > gap_s:
            runs.append([])
        runs[-1].append(cur)
    return [tuple(run) for run in runs]


def check_invariants(rows: tuple[EventRow, ...]) -> dict:
    """Validate logged rows against the safety/protocol contracts.

    Every invariant is derived from ``SafetyManager.check`` +
    ``ObstacleAvoidance.override`` (which only downgrades F/B to S) and from
    how ``RoverApp.step`` fills the log fields.
    """
    violations: Counter = Counter()
    previous_ts: datetime | None = None

    for row in rows:
        if row.decision not in PROTOCOL_COMMANDS:
            violations["protocol_alphabet"] += 1
        if row.safety in BLOCKING_REASONS and row.decision != "S":
            violations["blocking_reason_implies_stop"] += 1
        if row.safety in TURN_ONLY_REASONS and row.decision in {"F", "B"}:
            violations["turn_only_reason_never_translates"] += 1
        if row.safety == SLOW_ZONE_REASON and row.decision != "F":
            violations["slow_zone_reason_is_forward"] += 1
        if row.target == NO_TARGET:
            if row.confidence != 0.0:
                violations["no_target_has_zero_confidence"] += 1
            if row.position != NO_POSITION:
                violations["no_target_has_no_position"] += 1
        if not 0.0 <= row.confidence <= 1.0:
            violations["confidence_in_range"] += 1
        if row.infer_ms < 0.0 or row.fps < 0.0:
            violations["latency_and_fps_non_negative"] += 1
        if row.distance_state != "ok" and row.decision in {"F", "B"}:
            violations["usable_distance_required_for_translation"] += 1
        if previous_ts is not None and row.timestamp < previous_ts:
            violations["timestamps_monotonic"] += 1
        previous_ts = row.timestamp

    found = {name: int(violations[name]) for name in _INVARIANT_NAMES}
    return {
        "checked": list(_INVARIANT_NAMES),
        "violations": found,
        "total_violations": int(sum(violations.values())),
        "pass": not violations,
    }


def summarize(dataset: EventDataset, run_gap_s: float = DEFAULT_RUN_GAP_S) -> dict:
    """Produce the full JSON-safe evaluation report for a validated dataset."""
    rows = dataset.rows
    total = len(rows)
    timestamps = [row.timestamp for row in rows]
    span_s = round((timestamps[-1] - timestamps[0]).total_seconds(), 3)

    runs = split_runs(rows, run_gap_s)
    switches, switch_rate = _switch_rate(rows)

    detected = [row for row in rows if row.target != NO_TARGET]
    timed = [row for row in rows if row.infer_ms > 0.0]
    inference = describe(row.infer_ms for row in timed)
    p50_ms = inference["p50"]
    inference["rows_with_timing"] = inference.pop("count")
    inference["timing_coverage"] = _share(len(timed), total)
    inference["within_target_lock"] = (
        None if p50_ms is None else p50_ms <= TARGET_LOCK_S * 1000.0
    )

    mode_names = sorted({row.mode for row in rows})
    mode_groups = {
        name: tuple(row for row in rows if row.mode == name) for name in mode_names
    }
    return {
        "source": dataset.source,
        "dataset": {
            "rows": total,
            "malformed_rows": dataset.malformed,
            "error_samples": list(dataset.errors),
            "first_timestamp": timestamps[0].isoformat(timespec="seconds"),
            "last_timestamp": timestamps[-1].isoformat(timespec="seconds"),
            "span_s": span_s,
            "runs": len(runs),
            "run_gap_s": run_gap_s,
            "largest_run_rows": max((len(run) for run in runs), default=0),
        },
        "modes": {
            name: _mode_detail(rows, group) for name, group in mode_groups.items()
        },
        "decisions": distribution(rows, "decision"),
        "safety": distribution(rows, "safety"),
        "positions": distribution(rows, "position"),
        "targets": distribution(rows, "target"),
        "confidence": {
            "detection_rate": _share(len(detected), total),
            "detected_rows": len(detected),
            **describe(row.confidence for row in detected),
        },
        "distance_quality": {
            state: {"rows": count, "share": _share(count, total)}
            for state, count in sorted(
                Counter(row.distance_state for row in rows).items()
            )
            if count
        },
        "distance_cm": describe(
            row.distance_cm
            for row in rows
            if row.distance_state == "ok" and row.distance_cm is not None
        ),
        "inference_ms": inference,
        "fps": describe(row.fps for row in rows if row.fps > 0.0),
        "oscillation": {
            "command_switches": switches,
            "switch_rate": switch_rate,
        },
        "safety_summary": {
            "interventions": sum(1 for row in rows if row.safety != "SAFE"),
            "intervention_rate": _share(
                sum(1 for row in rows if row.safety != "SAFE"), total
            ),
            "stop_rate": _share(sum(1 for row in rows if row.decision == "S"), total),
            "motion_rate": _share(
                sum(1 for row in rows if row.decision in {"F", "B"}), total
            ),
        },
        "invariants": check_invariants(rows),
    }
