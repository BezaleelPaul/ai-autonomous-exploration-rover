"""Model bundle installer tests (no Ultralytics needed)."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

from support import ROOT

sys.path.insert(0, str(ROOT / "scripts"))

from install_model import install_bundle  # noqa: E402


def make_bundle(path: Path, *, with_weights: bool = True, evil: bool = False,
                prefix: str = "rover6") -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        if with_weights:
            archive.writestr(f"{prefix}_best.pt", b"fake-torch-checkpoint")
        archive.writestr(f"{prefix}_openvino/openvino_model.xml", b"<xml/>")
        archive.writestr(f"{prefix}.onnx", b"fake-onnx")
        archive.writestr(
            "val_summary.json",
            json.dumps({"mAP50": 0.21, "mAP50_95": 0.119, "precision": 0.33,
                        "recall": 0.25, "note": "bootstrap"}),
        )
        archive.writestr("data.yaml", "nc: 6\nnames: [person, chair, table, backpack, bottle, plant]\n")
        if evil:
            archive.writestr("../escaped.txt", b"nope")
    return path


def test_install_extracts_and_updates_config(tmp_path):
    bundle = make_bundle(tmp_path / "rover6_bundle.zip")
    config = tmp_path / "rover.json"
    config.write_text(json.dumps({"gateway": "http://192.168.4.1", "weights": "yolo11n.pt"}))

    result = install_bundle(bundle, models_dir=tmp_path / "models", config_path=config)

    assert Path(result["weights"]).is_file()
    assert result["weights"].endswith("rover6_best.pt")
    assert result["openvino"] is not None
    assert result["metrics"]["mAP50"] == 0.21
    saved = json.loads(config.read_text())
    assert saved["weights"].endswith("rover6_best.pt")


def test_install_can_prefer_openvino(tmp_path):
    bundle = make_bundle(tmp_path / "b.zip")
    result = install_bundle(bundle, models_dir=tmp_path / "models", set_default=False,
                            prefer_openvino=True)
    assert "openvino" in result["weights"]


def test_install_without_config(tmp_path):
    bundle = make_bundle(tmp_path / "b.zip")
    result = install_bundle(bundle, models_dir=tmp_path / "models", config_path=None)
    assert result["config_weights"] is None


def test_install_does_not_touch_config_when_disabled(tmp_path):
    bundle = make_bundle(tmp_path / "b.zip")
    config = tmp_path / "rover.json"
    config.write_text(json.dumps({"weights": "keep-me.pt"}))
    install_bundle(bundle, models_dir=tmp_path / "models", config_path=config, set_default=False)
    assert json.loads(config.read_text())["weights"] == "keep-me.pt"


def test_install_rejects_zip_slip(tmp_path):
    bundle = make_bundle(tmp_path / "evil.zip", evil=True)
    with pytest.raises(ValueError):
        install_bundle(bundle, models_dir=tmp_path / "models", set_default=False)
    assert not (tmp_path.parent / "escaped.txt").exists()


def test_install_rejects_a_bundle_without_weights(tmp_path):
    bundle = make_bundle(tmp_path / "b.zip", with_weights=False)
    with pytest.raises(ValueError):
        install_bundle(bundle, models_dir=tmp_path / "models", set_default=False)


def test_install_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        install_bundle(tmp_path / "nope.zip", models_dir=tmp_path / "models")


def test_install_rejects_a_non_zip(tmp_path):
    path = tmp_path / "bad.zip"
    path.write_text("not a zip")
    with pytest.raises(zipfile.BadZipFile):
        install_bundle(path, models_dir=tmp_path / "models")


def test_install_prefers_the_matching_bundle_prefix(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    (models / "rover24_best.pt").write_bytes(b"other model")
    bundle = make_bundle(tmp_path / "rover6_bundle.zip")
    result = install_bundle(bundle, models_dir=models, set_default=False)
    assert result["weights"].endswith("rover6_best.pt")


def test_install_prefers_the_matching_openvino_folder(tmp_path):
    models = tmp_path / "models"
    (models / "rover6_openvino").mkdir(parents=True)
    (models / "rover6_openvino" / "best.xml").write_text("<xml/>")
    bundle = make_bundle(tmp_path / "rover24_bundle.zip", prefix="rover24")
    result = install_bundle(bundle, models_dir=models, set_default=False, prefer_openvino=True)
    assert result["openvino"].endswith("rover24_openvino_model")
