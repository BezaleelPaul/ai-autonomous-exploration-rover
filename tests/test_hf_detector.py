import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from software.ai.detection import Detection
from software.ai.detector import HFDetector, create_detector


def test_hf_detector_output_schema():
    # Schema contract without loading weights: Detection must expose
    # label, score, bbox, center_x/y, width/height.
    d = Detection("bottle", 0.86, 100, 120, 300, 400)
    payload = d.to_dict()
    for k in [
        "class_name",
        "confidence",
        "x1",
        "y1",
        "x2",
        "y2",
        "center_x",
        "center_y",
        "width",
        "height",
        "timestamp",
    ]:
        assert k in payload
    assert d.center_x == 200 and d.center_y == 260
    assert d.width == 200 and d.height == 280


def test_create_detector_hf_uses_primary_model():
    cfg = {
        "ai": {
            "backend": "hf",
            "model_name": "facebook/detr-resnet-50",
            "confidence_threshold": 0.5,
            "allowed_classes": ["bottle"],
            "device": "cpu",
            "model_dir": "models/detr-resnet-50",
        }
    }
    det = create_detector(cfg)
    assert isinstance(det, HFDetector)
    assert det.model_name == "facebook/detr-resnet-50"
    assert not det.is_ready()  # lazy-load: no weights touched in unit test


def test_detector_replaceable_yolos_tiny():
    # Swap-in contract: changing model_name only must yield a valid detector
    # instance; navigation/safety code paths are untouched.
    cfg = {
        "ai": {
            "backend": "hf",
            "model_name": "hustvl/yolos-tiny",
            "confidence_threshold": 0.5,
            "allowed_classes": [],
            "device": "cpu",
            "model_dir": None,
        }
    }
    det = create_detector(cfg)
    assert isinstance(det, HFDetector)
    assert det.model_name == "hustvl/yolos-tiny"


def _populated(path: Path) -> str:
    path.mkdir()
    (path / "config.json").write_text("{}", encoding="utf-8")
    return str(path)


def test_model_dir_that_does_not_match_model_name_warns(tmp_path):
    # Regression: ai.model_dir silently shadows ai.model_name, so a benchmark
    # that changes only model_name keeps evaluating the local snapshot.
    model_dir = _populated(tmp_path / "local-detr")
    det = HFDetector(model_name="PekingU/rtdetr_v2_r18vd", model_dir=model_dir)
    with pytest.warns(UserWarning, match="shadows"):
        source = det._source()
    assert source == model_dir


def test_matching_or_absent_model_dir_does_not_warn(tmp_path):
    matching = _populated(tmp_path / "rtdetr_v2_r18vd")
    det = HFDetector(model_name="PekingU/rtdetr_v2_r18vd", model_dir=matching)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning here fails the test
        assert det._source() == matching

    # shipped config: the local dir name is a substring of the requested name
    shipped = _populated(tmp_path / "detr-resnet-50")
    det2 = HFDetector(model_name="facebook/detr-resnet-50", model_dir=shipped)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert det2._source() == shipped

    # missing dir -> falls back to model_name, no warning
    det3 = HFDetector(
        model_name="facebook/detr-resnet-50", model_dir=str(tmp_path / "absent")
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert det3._source() == "facebook/detr-resnet-50"
