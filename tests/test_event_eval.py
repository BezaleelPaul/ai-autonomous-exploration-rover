"""Dataset eval harness: telemetry parsing, statistics and safety contracts."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from software.telemetry.event_eval import (
    DISTANCE_STATES,
    EvalError,
    check_invariants,
    describe,
    distribution,
    load_events,
    percentile,
    split_runs,
    summarize,
)

ROOT = Path(__file__).resolve().parents[1]
SHIPPED_CSV = ROOT / "logs" / "events.csv"

HEADER = [
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
]


def make_row(**overrides) -> dict:
    row = {
        "timestamp": "2026-09-26T01:00:00",
        "mode": "observe",
        "target": "bottle",
        "confidence": "0.9",
        "position": "CENTER",
        "distance_cm": "100.0",
        "decision": "F",
        "safety": "SAFE",
        "infer_ms": "120.0",
        "fps": "17.8",
    }
    row.update(overrides)
    return row


def write_csv(
    path: Path, rows: Sequence[dict], header: Sequence[str] | None = None
) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(header or HEADER), extrasaction="ignore"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "evaluate_cli", ROOT / "scripts" / "evaluate.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- input validation -----------------------------------------------------


def test_load_events_missing_file_raises(tmp_path):
    with pytest.raises(EvalError, match="not found"):
        load_events(tmp_path / "absent.csv")


def test_load_events_directory_raises(tmp_path):
    with pytest.raises(EvalError, match="not a file"):
        load_events(tmp_path)


def test_load_events_missing_columns_raises(tmp_path):
    path = write_csv(tmp_path / "bad.csv", [make_row()], header=["timestamp"])
    with pytest.raises(EvalError, match="missing required columns"):
        load_events(path)


def test_load_events_no_valid_rows_raises(tmp_path):
    rows = [make_row(decision=""), make_row(timestamp="yesterday")]
    path = write_csv(tmp_path / "empty.csv", rows)
    with pytest.raises(EvalError, match="no valid telemetry rows"):
        load_events(path)


def test_load_events_counts_and_reports_malformed_rows(tmp_path):
    rows = [
        make_row(),
        make_row(decision=""),
        make_row(confidence="high"),
        make_row(),
    ]
    dataset = load_events(write_csv(tmp_path / "mixed.csv", rows))
    assert len(dataset.rows) == 2
    assert dataset.malformed == 2
    assert len(dataset.errors) == 2
    assert dataset.errors[0].startswith("line 3:")


# --- distance classification ---------------------------------------------


@pytest.mark.parametrize(
    ("cell", "expected_value", "expected_state"),
    [
        ("150.5", 150.5, "ok"),
        ("0.0", 0.0, "zero"),
        ("-1.0", -1.0, "negative"),
        ("nan", None, "non_finite"),
        ("inf", None, "non_finite"),
        ("True", None, "unparseable"),
        ("", None, "absent"),
        ("None", None, "absent"),
    ],
)
def test_distance_cells_are_classified_not_dropped(
    tmp_path, cell, expected_value, expected_state
):
    path = write_csv(tmp_path / "d.csv", [make_row(distance_cm=cell)])
    row = load_events(path).rows[0]
    assert row.distance_cm == expected_value
    assert row.distance_state == expected_state
    assert row.distance_state in DISTANCE_STATES


# --- statistics -----------------------------------------------------------


def test_percentile_interpolates_between_samples():
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == pytest.approx(2.5)
    assert percentile([1.0, 2.0, 3.0], 0.95) == pytest.approx(2.9)
    assert percentile([7.0], 0.95) == 7.0


def test_percentile_rejects_bad_quantile_and_handles_empty():
    assert percentile([], 0.5) is None
    with pytest.raises(ValueError, match="quantile"):
        percentile([1.0], 1.5)


def test_describe_reports_order_statistics():
    stats = describe([3.0, 1.0, 2.0])
    assert stats == {
        "count": 3,
        "mean": 2.0,
        "p50": 2.0,
        "p95": 2.9,
        "min": 1.0,
        "max": 3.0,
    }


def test_describe_of_nothing_is_all_nulls():
    assert describe([]) == {
        "count": 0,
        "mean": None,
        "p50": None,
        "p95": None,
        "min": None,
        "max": None,
    }


def test_distribution_is_sorted_by_frequency_and_shares_sum_to_one(tmp_path):
    rows = [make_row(decision="F"), make_row(decision="F"), make_row(decision="S")]
    dataset = load_events(write_csv(tmp_path / "dist.csv", rows))
    dist = distribution(dataset.rows, "decision")
    assert list(dist) == ["F", "S"]
    assert dist["F"] == {"rows": 2, "share": pytest.approx(0.6667, abs=1e-4)}
    assert sum(entry["share"] for entry in dist.values()) == pytest.approx(1.0)


def test_split_runs_breaks_where_the_timestamp_gap_is_large(tmp_path):
    rows = [
        make_row(timestamp="2026-09-26T01:00:00"),
        make_row(timestamp="2026-09-26T01:00:10"),
        make_row(timestamp="2026-09-26T01:30:00"),
        make_row(timestamp="2026-09-26T01:30:05"),
    ]
    dataset = load_events(write_csv(tmp_path / "runs.csv", rows))
    runs = split_runs(dataset.rows, gap_s=60.0)
    assert [len(run) for run in runs] == [2, 2]
    assert split_runs(()) == []


# --- invariants -----------------------------------------------------------

EXPECTED_INVARIANTS = (
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


def _rows(*overrides) -> tuple:
    path_rows = [make_row(**item) for item in overrides]
    with tempfile.TemporaryDirectory() as tmp:
        dataset = load_events(write_csv(Path(tmp) / "x.csv", path_rows))
    return dataset.rows


def test_invariants_pass_on_well_formed_rows():
    result = check_invariants(
        _rows(
            {},
            {"decision": "S", "safety": "COMM_LOST"},
            {"decision": "L", "safety": "CAUTION_CLOSE_OBSTACLE"},
            {"decision": "F", "safety": "CAUTION_SLOW_ZONE"},
            {"target": "-", "confidence": "0.0", "position": "NONE"},
        )
    )
    assert result["pass"] is True
    assert result["total_violations"] == 0
    assert tuple(result["checked"]) == EXPECTED_INVARIANTS


def test_blocking_reason_with_motion_is_a_violation():
    result = check_invariants(_rows({"decision": "F", "safety": "LOW_CONFIDENCE"}))
    assert result["pass"] is False
    assert result["violations"]["blocking_reason_implies_stop"] == 1


def test_turn_only_reason_translating_is_a_violation():
    result = check_invariants(
        _rows({"decision": "B", "safety": "CAUTION_UNKNOWN_DISTANCE"})
    )
    assert result["violations"]["turn_only_reason_never_translates"] == 1


def test_unusable_distance_with_motion_is_a_violation():
    result = check_invariants(_rows({"distance_cm": "nan", "decision": "F"}))
    assert result["violations"]["usable_distance_required_for_translation"] == 1


def test_command_outside_protocol_alphabet_is_a_violation():
    result = check_invariants(_rows({"decision": "X"}))
    assert result["violations"]["protocol_alphabet"] == 1


def test_confidence_out_of_range_and_reversed_timestamps_are_violations(tmp_path):
    rows = [
        make_row(confidence="1.4"),
        make_row(timestamp="2026-09-25T01:00:00"),
    ]
    dataset = load_events(write_csv(tmp_path / "bad.csv", rows))
    result = check_invariants(dataset.rows)
    assert result["violations"]["confidence_in_range"] == 1
    assert result["violations"]["timestamps_monotonic"] == 1


# --- summary --------------------------------------------------------------


def test_summarize_is_json_safe_and_reports_every_section(tmp_path):
    rows = [
        make_row(),
        make_row(mode="search", decision="S", safety="LOW_CONFIDENCE"),
        make_row(distance_cm="nan", decision="S", safety="CAUTION_UNKNOWN_DISTANCE"),
    ]
    report = summarize(load_events(write_csv(tmp_path / "s.csv", rows)))
    json.dumps(report)
    for key in (
        "source",
        "dataset",
        "modes",
        "decisions",
        "safety",
        "positions",
        "targets",
        "confidence",
        "distance_quality",
        "distance_cm",
        "inference_ms",
        "fps",
        "oscillation",
        "safety_summary",
        "invariants",
    ):
        assert key in report
    assert report["dataset"]["rows"] == 3
    assert report["distance_quality"]["non_finite"]["rows"] == 1
    assert report["invariants"]["pass"] is True


def test_summarize_counts_timed_rows_only_for_latency(tmp_path):
    rows = [
        make_row(infer_ms="0.0"),
        make_row(infer_ms="120.0"),
        make_row(infer_ms="180.0"),
    ]
    report = summarize(load_events(write_csv(tmp_path / "lat.csv", rows)))
    assert report["inference_ms"]["rows_with_timing"] == 2
    assert report["inference_ms"]["timing_coverage"] == pytest.approx(0.6667, abs=1e-4)
    assert report["inference_ms"]["within_target_lock"] is True


@pytest.mark.skipif(not SHIPPED_CSV.exists(), reason="no telemetry collected yet")
def test_shipped_events_csv_passes_every_invariant():
    report = summarize(load_events(SHIPPED_CSV))
    assert report["dataset"]["rows"] > 0
    assert report["invariants"]["pass"] is True, report["invariants"]["violations"]


# --- CLI ------------------------------------------------------------------


def test_cli_writes_json_report_and_exits_zero(tmp_path):
    cli = load_cli()
    csv_path = write_csv(tmp_path / "in.csv", [make_row()])
    out_path = tmp_path / "out.json"
    code = cli.main(["--csv", str(csv_path), "--out", str(out_path)])
    assert code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["dataset"]["rows"] == 1
    assert "generated_at" in payload


def test_cli_strict_turns_an_invariant_violation_into_exit_one(tmp_path):
    cli = load_cli()
    csv_path = write_csv(tmp_path / "bad.csv", [make_row(decision="X")])
    out_path = tmp_path / "out.json"
    assert cli.main(["--csv", str(csv_path), "--out", str(out_path)]) == 0
    assert cli.main(["--csv", str(csv_path), "--out", str(out_path), "--strict"]) == 1


def test_cli_missing_input_exits_two(tmp_path):
    cli = load_cli()
    code = cli.main(["--csv", str(tmp_path / "nope.csv"), "--no-write"])
    assert code == 2


def test_cli_min_rows_gate_exits_two(tmp_path):
    cli = load_cli()
    csv_path = write_csv(tmp_path / "one.csv", [make_row()])
    code = cli.main(["--csv", str(csv_path), "--min-rows", "5", "--no-write"])
    assert code == 2


def test_cli_renders_a_readable_report(tmp_path, capsys):
    cli = load_cli()
    csv_path = write_csv(tmp_path / "r.csv", [make_row(), make_row(decision="S")])
    code = cli.main(["--csv", str(csv_path), "--no-write"])
    printed = capsys.readouterr().out
    assert code == 0
    assert "Invariants" in printed
    assert "DECISION" in printed
    assert "Distance data" in printed
