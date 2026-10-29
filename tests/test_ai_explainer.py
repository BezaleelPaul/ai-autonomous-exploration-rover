"""CLIP explainer: backends, scoring, vlm gate, and the /api/explain surface."""

from __future__ import annotations

import types
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest
import torch

from software.ai.explainer import (
    ClipExplainer,
    create_explainer,
    crop_pil,
    format_scores,
    to_pil,
)
from software.dashboard.app import create_control_app
from software.dashboard.controls import ArduinoLink
from software.dashboard.deck_page import DECK_PAGE
from software.utils.config_loader import load_config

ROOT = Path(__file__).resolve().parents[1]


# ---- fakes ----------------------------------------------------------------


def fail_importer(name: str):
    raise ImportError(f"no module named {name}")


def make_fake_clip(text_rows: list[list[float]]):
    """A minimal clip-shaped module: load/tokenize + encode_image/encode_text."""

    class Model:
        def eval(self):
            return None

        def to(self, device):
            return self

        def encode_image(self, pixels):
            return torch.tensor([[1.0, 0.0]])

        def encode_text(self, tokens):
            return torch.tensor(text_rows[: len(tokens)])

    mod = types.ModuleType("clip")
    mod.load = lambda weights, device="cpu": (
        Model(),
        lambda image: torch.zeros(3, 8, 8),
    )
    mod.tokenize = lambda labels: torch.arange(len(labels))
    return mod


def clip_first(mod):
    def importer(name: str):
        if name == "clip":
            return mod
        raise ImportError(f"no module named {name}")

    return importer


class FakeExplainer:
    available = True
    backend = "clip"
    default_labels: ClassVar[list[str]] = ["bottle", "person"]

    def explain_frame(self, frame, labels, top=3):
        return "bottle 80% · person 15%"

    def explain_detection(self, frame, detection, labels, top=3):
        return "bottle 91% · chair 6%"

    def caption(self, frame):
        return "a bottle on a table"


class FakeFeed:
    def __init__(self, frame=...):
        self._frame = np.zeros((48, 64, 3), dtype=np.uint8) if frame is ... else frame

    def snapshot(self):
        dets = [
            {
                "class_name": "bottle",
                "confidence": 0.9,
                "x1": 1,
                "y1": 1,
                "x2": 30,
                "y2": 40,
            }
        ]
        return self._frame, dets


@pytest.fixture()
def cfg(tmp_path) -> dict:
    cfg = load_config(str(ROOT / "config" / "config.yaml"))
    cfg["dashboard"]["record_dir"] = str(tmp_path / "runs")
    return cfg


@pytest.fixture()
def link() -> ArduinoLink:
    link = ArduinoLink("", mock=True)
    link.connect()
    return link


@pytest.fixture()
def feed() -> FakeFeed:
    return FakeFeed()


# ---- pure helpers ---------------------------------------------------------


def test_format_scores_ranks_and_truncates():
    scores = [
        _s("cow", 0.10),
        _s("bottle", 0.87),
        _s("table", 0.03),
    ]
    text = format_scores(scores, top=2)
    assert text == "bottle 87% · cow 10%"
    assert format_scores([], top=2) == "no scores"


def test_crop_pil_clamps_out_of_range_boxes():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    image = crop_pil(frame, (-5, -5, 100, 100))
    assert image.size == (10, 10)


def test_to_pil_swaps_bgr_to_rgb():
    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    frame[..., 0] = 255  # blue channel
    image = to_pil(frame)
    assert image.getpixel((0, 0)) == (0, 0, 255)


def _s(label: str, score: float):
    from software.ai.explainer import Scored

    return Scored(label=label, score=score)


# ---- backend selection ----------------------------------------------------


def test_unavailable_when_no_backend_imports():
    explainer = ClipExplainer(importer=fail_importer)
    assert explainer.load() is False
    assert explainer.available is False
    assert "open-clip-torch" in explainer.reason
    assert "clip" in explainer.reason


def test_clip_backend_scores_softmax_over_labels():
    mod = make_fake_clip([[3.0, 0.0], [0.0, 3.0], [1.0, 2.0]])
    explainer = ClipExplainer(importer=clip_first(mod))
    assert explainer.load() is True
    assert explainer.backend == "clip"
    scores = explainer.top_scores(
        to_pil(np.zeros((8, 8, 3), np.uint8)), ["dog", "cat", "car"]
    )
    assert sum(s.score for s in scores) == pytest.approx(1.0, abs=1e-4)
    assert scores[0].label == "dog"


def test_explain_frame_formats_the_top_label():
    mod = make_fake_clip([[3.0, 0.0], [0.0, 3.0]])
    explainer = ClipExplainer(importer=clip_first(mod))
    explainer.load()
    text = explainer.explain_frame(np.zeros((8, 8, 3), np.uint8), ["dog", "cat"])
    assert text.startswith("dog")


def test_explain_frame_reports_errors_without_raising():
    class BrokenPreprocess:
        def __call__(self, image):
            raise RuntimeError("boom")

    mod = make_fake_clip([[1.0, 0.0], [0.0, 1.0]])
    explainer = ClipExplainer(importer=clip_first(mod))
    explainer.load()
    explainer._preprocess = BrokenPreprocess()
    text = explainer.explain_frame(np.zeros((8, 8, 3), np.uint8), ["dog", "cat"])
    assert text.startswith("error:")


def test_explain_frame_unavailable_carries_the_reason():
    explainer = ClipExplainer(importer=fail_importer)
    explainer.load()
    assert "unavailable:" in explainer.explain_frame(
        np.zeros((4, 4, 3), np.uint8), ["dog"]
    )


# ---- BLIP caption gate ----------------------------------------------------


def test_caption_is_off_by_default():
    explainer = ClipExplainer(importer=fail_importer, vlm_enabled=False)
    explainer.load()
    text = explainer.caption(np.zeros((4, 4, 3), np.uint8))
    assert text.startswith("caption off")
    assert "vlm_enabled" in text


def test_caption_when_enabled_but_backend_unavailable():
    explainer = ClipExplainer(importer=fail_importer, vlm_enabled=True)
    explainer.load()
    assert explainer.caption(np.zeros((4, 4, 3), np.uint8)).startswith("unavailable:")


# ---- config wiring --------------------------------------------------------


def test_create_explainer_reads_ai_config_and_never_raises(cfg):
    cfg["ai"]["vlm_enabled"] = False
    explainer = create_explainer(cfg, importer=fail_importer)
    assert explainer.available is False
    assert explainer.vlm_enabled is False
    assert "bottle" in explainer.default_labels


def test_vlm_enabled_defaults_to_false_in_config(cfg):
    assert cfg["ai"]["vlm_enabled"] is False


# ---- /api/explain ---------------------------------------------------------


def test_explain_route_absent_without_an_explainer(feed, link):
    app = create_control_app(feed, link)
    assert app.test_client().get("/api/explain").status_code == 404


def test_explain_route_returns_frame_and_target_scores(link):
    feed = FakeFeed()
    app = create_control_app(feed, link, explainer=FakeExplainer())
    res = app.test_client().get("/api/explain")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["backend"] == "clip"
    assert data["label"] == "bottle"
    assert "bottle" in data["frame"]
    assert "bottle" in data["target"]
    assert "caption" not in data


def test_explain_caption_is_opt_in(link):
    app = create_control_app(FakeFeed(), link, explainer=FakeExplainer())
    data = app.test_client().get("/api/explain?caption=1").get_json()
    assert data["caption"] == "a bottle on a table"


def test_explain_returns_503_when_there_is_no_frame(link):
    app = create_control_app(FakeFeed(frame=None), link, explainer=FakeExplainer())
    res = app.test_client().get("/api/explain")
    assert res.status_code == 503
    assert res.get_json()["ok"] is False


# ---- deck page ------------------------------------------------------------


def test_deck_page_polls_explain_and_has_the_clip_row():
    for token in ('id="clip"', "pollExplain", "/api/explain"):
        assert token in DECK_PAGE, token
