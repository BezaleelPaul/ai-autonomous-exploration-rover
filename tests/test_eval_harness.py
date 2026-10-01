"""Regression tests for the eval harness class-name discovery.

Bug found during the model benchmark: ``_build_detector`` read only
``detector._model.names`` — the Ultralytics convention. Hugging Face detectors
keep the model in a ``_pipe`` tuple and expose ``config.id2label``, so the
``hf`` backend loaded successfully and then failed with
``detector exposed no class names``. That made every HF model unbenchmarkable.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "eval_detection_cli", ROOT / "scripts" / "eval_detection.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness():
    return load_cli()


def test_class_names_reads_ultralytics_names_attr(harness):
    detector = SimpleNamespace(
        _model=SimpleNamespace(names={0: "person", 42: "bottle"})
    )
    assert harness._class_names(detector) == {0: "person", 42: "bottle"}


def test_class_names_reads_hf_id2label_from_pipe(harness):
    model = SimpleNamespace(
        config=SimpleNamespace(id2label={0: "person", 1: "bicycle"})
    )
    detector = SimpleNamespace(_pipe=(object(), model, object()))
    assert harness._class_names(detector) == {0: "person", 1: "bicycle"}


def test_class_names_handles_string_keys_and_missing_model(harness):
    model = SimpleNamespace(config=SimpleNamespace(id2label={"3": "car"}))
    detector = SimpleNamespace(_pipe=(object(), model, object()))
    assert harness._class_names(detector) == {3: "car"}
    assert harness._class_names(SimpleNamespace()) == {}
    assert harness._class_names(SimpleNamespace(_model=SimpleNamespace())) == {}
