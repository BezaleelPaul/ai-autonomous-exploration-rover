"""Zero-shot explainability: CLIP scores what the rover is looking at.

The perception stack answers "why did you turn/stop" (zones + safety);
this layer answers "what IS that" — CLIP ranks text labels against the frame
(or a detection crop) with no training, and BLIP captions on demand when
``ai.vlm_enabled`` is turned on (default false: it would download ~1 GB).

Backends, in order of preference (both drive the same scoring code):
  1. OpenAI ``clip`` + the shipped ``weights/clip/ViT-B-32.pt`` (TorchScript)
  2. ``open_clip`` (requirements: open-clip-torch) — use it with an
     open_clip-native checkpoint; it rejects the TorchScript archive format
     on purpose (weights_only), so the shipped file goes through clip first.

If neither import loads, the explainer stays available=False with a reason
string the dashboard can show instead of scores.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = "weights/clip/ViT-B-32.pt"
OPEN_CLIP_MODEL = "ViT-B-32"
LOGIT_SCALE = 100.0


@dataclass(frozen=True)
class Scored:
    label: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "score": round(self.score, 4)}


def to_pil(frame):
    """cv2 BGR ndarray (or anything array-like) -> PIL RGB image."""
    from PIL import Image

    if isinstance(frame, Image.Image):
        return frame
    array = getattr(frame, "__array__", None)
    if array is not None:
        frame = array()
    if hasattr(frame, "shape") and len(frame.shape) == 3:
        return Image.fromarray(frame[..., ::-1])
    return Image.fromarray(frame)


def crop_pil(frame, box) -> Any:
    """Crop a Detection-like box (x1,y1,x2,y2) out of a BGR frame."""
    x1, y1, x2, y2 = (int(float(v)) for v in box)
    height, width = frame.shape[:2]
    x1 = max(0, min(x1, width - 1))
    x2 = max(x1 + 1, min(x2, width))
    y1 = max(0, min(y1, height - 1))
    y2 = max(y1 + 1, min(y2, height))
    return to_pil(frame[y1:y2, x1:x2])


def format_scores(scores: list[Scored], top: int = 3, as_sentence: bool = True) -> str:
    """Render the top-N labels: 'bottle 87% · table 9%' (or a list string)."""
    if not scores:
        return "no scores"
    ranked = sorted(scores, key=lambda s: s.score, reverse=True)[: max(1, top)]
    parts = [f"{s.label} {round(s.score * 100)}%" for s in ranked]
    if not as_sentence:
        return " | ".join(parts)
    return " · ".join(parts)


class ClipExplainer:
    """CLIP zero-shot label scoring over an optional local checkpoint."""

    def __init__(
        self,
        weights: str = DEFAULT_WEIGHTS,
        *,
        importer=None,
        device: str = "cpu",
        vlm_enabled: bool = False,
    ) -> None:
        self.weights = str(weights)
        self.device = device
        self.vlm_enabled = bool(vlm_enabled)
        self.backend = "none"
        self.reason = ""
        self.available = False
        self.default_labels: list[str] = []
        self._model = None
        self._preprocess = None
        self._tokenize = None
        self._importer = importer
        self._blip = None

    # ------------------------------------------------------------- loading
    def load(self) -> bool:
        """Import a backend and load the checkpoint. False = unavailable."""
        importer = self._importer
        if importer is None:
            import importlib

            importer = importlib.import_module

        try:
            import torch
        except Exception as exc:
            self.reason = f"torch unavailable: {exc}"
            return False

        errors: list[str] = []
        for backend in ("clip", "open_clip"):
            try:
                module = importer(backend)
                self._model, self._preprocess, self._tokenize = self._bind(
                    backend, module, torch
                )
            except Exception as exc:
                errors.append(f"{backend}: {exc}")
                continue
            self.backend = backend
            self.available = True
            self.reason = ""
            logger.info("CLIP explainer ready via %s (%s)", backend, self.weights)
            return True

        hint = (
            "CLIP unavailable — install open-clip-torch (pip install "
            "open-clip-torch) or keep weights/clip/ViT-B-32.pt next to the "
            "OpenAI clip package"
        )
        self.reason = hint + " | " + " | ".join(errors)
        return False

    def _bind(self, backend: str, module, torch):
        """Load the checkpoint and return (model, preprocess, tokenize)."""
        if backend == "open_clip":
            model, _, preprocess = module.create_model_and_transforms(
                OPEN_CLIP_MODEL, pretrained=self.weights
            )
            tokenize = module.get_tokenizer(OPEN_CLIP_MODEL)
        else:  # OpenAI clip: JIT checkpoint, local path skips the download
            model, preprocess = module.load(self.weights, device=self.device)
            tokenize = module.tokenize
        model.eval()
        if hasattr(model, "to"):
            model.to(self.device)
        return model, preprocess, tokenize

    # -------------------------------------------------------------- scoring
    def top_scores(self, image, labels: list[str]) -> list[Scored]:
        """Softmax probabilities of ``labels`` for one PIL image."""
        if not self.available or self._model is None:
            return []
        if not labels:
            return []
        import torch

        with torch.no_grad():
            pixels = self._preprocess(image).unsqueeze(0).to(self.device)
            texts = self._tokenize(list(labels)).to(self.device)
            image_features = self._model.encode_image(pixels)
            text_features = self._model.encode_text(texts)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            logits = LOGIT_SCALE * image_features @ text_features.T
            probs = logits.softmax(dim=-1)[0].float().cpu().tolist()
        return [
            Scored(label=str(label), score=max(0.0, min(1.0, float(p))))
            for label, p in zip(labels, probs, strict=True)
        ]

    def explain_frame(self, frame, labels: list[str], top: int = 3) -> str:
        """Rank labels against the whole frame (scene context)."""
        if not self.available:
            return f"unavailable: {self.reason}"
        try:
            return format_scores(self.top_scores(to_pil(frame), labels), top=top)
        except Exception as exc:
            logger.exception("CLIP frame scoring failed")
            return f"error: {exc}"

    def explain_detection(
        self, frame, detection, labels: list[str], top: int = 3
    ) -> str:
        """Rank labels against the detection's crop (what IS that object)."""
        if not self.available:
            return f"unavailable: {self.reason}"
        try:
            box = (
                detection["x1"],
                detection["y1"],
                detection["x2"],
                detection["y2"],
            )
            return format_scores(self.top_scores(crop_pil(frame, box), labels), top=top)
        except Exception as exc:
            logger.exception("CLIP crop scoring failed")
            return f"error: {exc}"

    # ------------------------------------------------------------- captions
    def caption(self, frame) -> str:
        """BLIP caption, on demand. Gated by ai.vlm_enabled (default false)."""
        if not self.vlm_enabled:
            return "caption off (set ai.vlm_enabled: true; downloads BLIP weights)"
        if not self.available:
            return f"unavailable: {self.reason}"
        try:
            torch, processor, blip = self._load_blip()
            image = to_pil(frame)
            inputs = processor(images=image, return_tensors="pt")
            with torch.no_grad():
                out = blip.generate(**inputs)
            return str(processor.decode(out[0], skip_special_tokens=True)).strip()
        except Exception as exc:
            logger.exception("BLIP caption failed")
            return f"error: {exc}"

    def _load_blip(self):
        if self._blip is not None:
            return self._blip
        import torch
        from transformers import BlipForConditionalGeneration, BlipProcessor

        name = "facebook/blip-image-captioning-base"
        processor = BlipProcessor.from_pretrained(name)
        model = BlipForConditionalGeneration.from_pretrained(name)
        model.eval()
        self._blip = (torch, processor, model)
        return self._blip


def create_explainer(cfg: dict, *, weights: str | None = None, importer=None):
    """Build from ``ai:`` config; never raises — unavailable carries a reason."""
    ai = cfg.get("ai", {})
    explainer = ClipExplainer(
        weights=weights or str(ai.get("clip_weights", DEFAULT_WEIGHTS)),
        importer=importer,
        device=str(ai.get("device", "cpu")),
        vlm_enabled=bool(ai.get("vlm_enabled", False)),
    )
    explainer.default_labels = [str(c) for c in ai.get("custom_classes", []) or []]
    explainer.load()
    return explainer
