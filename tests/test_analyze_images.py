"""Batch image-folder analysis tests (OpenCV required, model faked)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

from support import ROOT

sys.path.insert(0, str(ROOT / "scripts"))

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")

from ai_rover.steering import Detection  # noqa: E402
from analyze_images import analyze, collect_images  # noqa: E402


class FakeDetector:
    def __init__(self, detections=None, fail_on=None):
        self.detections = detections if detections is not None else [
            Detection("person", 0.9, 10, 10, 60, 90),
            Detection("chair", 0.6, 70, 30, 120, 100),
        ]
        self.fail_on = fail_on
        self.calls = 0

    def detect(self, image):
        self.calls += 1
        if self.fail_on is not None and self.calls == self.fail_on:
            raise RuntimeError("model exploded")
        return list(self.detections)


def make_images(folder: Path, count: int = 3) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(count):
        path = folder / f"img_{i}.jpg"
        cv2.imwrite(str(path), np.zeros((120, 160, 3), dtype=np.uint8))
        paths.append(path)
    return paths


def test_collect_images_filters_and_sorts(tmp_path):
    make_images(tmp_path, 2)
    (tmp_path / "notes.txt").write_text("not an image")
    assert [p.name for p in collect_images(tmp_path, recursive=False)] == ["img_0.jpg", "img_1.jpg"]
    assert collect_images(tmp_path / "img_0.jpg", False)[0].name == "img_0.jpg"
    assert collect_images(tmp_path / "notes.txt", False) == []


def test_analyze_writes_csv_json_and_annotated_images(tmp_path):
    images = make_images(tmp_path / "in", 3)
    out = tmp_path / "out"
    summary = analyze(images, FakeDetector(), out)

    assert summary["images"] == 3
    assert summary["detections"] == 6
    assert summary["per_class"] == {"person": 3, "chair": 3}
    assert summary["images_without_detections"] == 0
    assert Path(out / "summary.json").is_file()
    assert json.loads((out / "summary.json").read_text())["images"] == 3

    with open(out / "detections.csv", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert set(rows[0]) >= {"image", "class", "confidence", "x1", "y1", "x2", "y2", "area_pct"}
    assert len(list((out / "annotated").glob("*.jpg"))) == 3


def test_analyze_respects_limit_and_no_draw(tmp_path):
    images = make_images(tmp_path / "in", 4)
    out = tmp_path / "out"
    summary = analyze(images, FakeDetector(), out, draw=False, limit=2)
    assert summary["images"] == 2
    assert not list((out / "annotated").glob("*.jpg"))


def test_analyze_counts_images_without_detections(tmp_path):
    images = make_images(tmp_path / "in", 2)
    summary = analyze(images, FakeDetector(detections=[]), tmp_path / "out", draw=False)
    assert summary["images"] == 2
    assert summary["images_without_detections"] == 2
    assert summary["detections"] == 0
    assert summary["per_class"] == {}


def test_analyze_skips_unreadable_files(tmp_path):
    images = make_images(tmp_path / "in", 1)
    broken = tmp_path / "in" / "broken.jpg"
    broken.write_text("not a jpeg")
    summary = analyze(images + [broken], FakeDetector(), tmp_path / "out", draw=False)
    assert summary["images"] == 1
    assert summary["detections"] == 2


def test_analyze_include_prompts_for_world_detectors(tmp_path):
    class FakeWorld(FakeDetector):
        prompts = ["door", "cone"]

    images = make_images(tmp_path / "in", 1)
    summary = analyze(images, FakeWorld(), tmp_path / "out", draw=False)
    assert summary["prompts"] == ["door", "cone"]
    assert summary["detector"] == "FakeWorld"
