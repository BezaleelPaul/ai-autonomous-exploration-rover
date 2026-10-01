"""Regression tests for ``scripts/collect_camera_dataset.py``.

The collector is the only path to real camera-side metrics (FPS, frame age,
dropped frames, real-scene false-positive rate), all of which are still
NOT YET MEASURED because no ESP32-CAM footage exists. These tests exercise the
tool against the mock source only, and assert the two properties that must not
regress: the 15-condition capture plan, and the guarantee that mock output is
labelled SIMULATED so it can never be quoted as camera evidence.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "collect_camera_dataset_cli", ROOT / "scripts" / "collect_camera_dataset.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def collector():
    return load_cli()


def _args(collector, tmp_path: Path, *extra: str):
    return collector.build_parser().parse_args(
        [
            "--condition",
            "center_1.5m_500lux",
            "--source",
            "mock",
            "--frames",
            "3",
            "--interval",
            "0",
            "--out",
            str(tmp_path / "ds"),
            "--out-stats",
            str(tmp_path / "stats.json"),
            *extra,
        ]
    )


def test_capture_plan_covers_documented_axes(collector):
    """The plan must keep all 15 lighting/position/occlusion conditions."""
    assert len(collector.CONDITIONS) == 15
    assert len(set(collector.CONDITIONS)) == 15, "duplicate capture condition"
    for required in (
        "empty_no_target",
        "dark_10lux_1.5m",
        "bright_2000lux_1.5m",
        "occluded_heavy_1.5m",
        "multi_two_targets_1.5m",
        "clutter_background_1.5m",
        "moving_target_1.5m",
    ):
        assert required in collector.CONDITIONS, f"missing condition {required}"


def test_parser_rejects_unknown_condition_and_exposes_defaults(collector):
    with pytest.raises(SystemExit):
        collector.build_parser().parse_args(["--condition", "not_a_real_condition"])
    args = collector.build_parser().parse_args(["--condition", "dark_10lux_1.5m"])
    assert args.source == "esp32"
    assert args.frames == 30
    assert args.interval == 0.5
    assert args.auto_label is False


def test_mock_capture_writes_manifest_rows(collector, tmp_path):
    args = _args(collector, tmp_path)
    summary = collector.capture(args)

    out = tmp_path / "ds"
    manifest = out / "manifest.csv"
    assert manifest.exists()
    with manifest.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert tuple(rows[0].keys()) == collector.MANIFEST_FIELDS
    assert len(rows) == 3
    assert summary["frames_saved"] == 3
    for row in rows:
        assert row["condition"] == "center_1.5m_500lux"
        assert row["source"] == "mock"
        assert float(row["stream_fps"]) > 0, "stream_fps left unfilled"
        assert float(row["frame_age_s"]) >= 0
        assert int(row["width"]) > 0 and int(row["height"]) > 0
        assert (out / row["file"]).exists(), "manifest row points at a missing file"


def test_mock_capture_is_labelled_simulated_without_auto_label(collector, tmp_path):
    """Mock output must never be mistakable for camera evidence or truth."""
    args = _args(collector, tmp_path)
    summary = collector.capture(args)

    out = tmp_path / "ds"
    assert summary["label"] == "SIMULATED (mock source)"
    assert summary["ground_truth"] == "NONE"
    assert summary["auto_labelled"] is False
    assert summary["dropped"] == 0
    assert "must never be quoted as camera evidence" in summary["note"]
    assert not (out / "labels").exists(), "labels written without --auto-label"
    assert not (out / "classes.txt").exists()


def test_main_writes_stats_and_returns_zero(collector, tmp_path, capsys):
    stats_path = tmp_path / "stats.json"
    argv = [
        "--condition",
        "empty_no_target",
        "--source",
        "mock",
        "--frames",
        "2",
        "--interval",
        "0",
        "--out",
        str(tmp_path / "ds"),
        "--out-stats",
        str(stats_path),
        "--json",
    ]
    assert collector.main(argv) == 0
    written = json.loads(stats_path.read_text(encoding="utf-8"))
    assert written["frames_saved"] == 2
    assert written["label"] == "SIMULATED (mock source)"
    printed = json.loads(capsys.readouterr().out)
    assert printed["manifest"] == str(tmp_path / "ds" / "manifest.csv")
