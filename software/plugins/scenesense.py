"""Surroundings understanding: monocular depth + the Rover World Model.

Runs on the plugin cadence (``plugins.scenesense_every_n``): estimates a
relative depth map with a small Depth-Anything checkpoint, hands detections +
depth to :class:`software.ai.world_model.WorldModel`, and publishes the result
(``scene`` / ``facts`` / ``path_state`` / ``spec_rho_m`` / ``degraded``) into
``/api/state`` → feed.world for the deck's SURROUNDINGS card.

The ultrasonic ranger (pushed via ``note_distance``) serves two roles:
scale reference for the inverse-depth least-squares calibrator, and the
signal for the STL clear-path spec. Depth loads lazily on the first frame
(boot stays fast) and failures degrade to geometry-only facts — the plugin
never breaks detection or control.
"""

from __future__ import annotations

import logging
import time

from software.ai.world_model import WorldModel
from software.plugins import VisionPlugin

logger = logging.getLogger(__name__)

DEPTH_MODEL = "depth-anything/Depth-Anything-V2-Small-hf"
# Metric fine-tune (Depth-Anything-V2, Apache-2.0): outputs metres directly
# via the `predicted_depth` tensor, so the world model skips the ultrasonic
# inverse-depth fit. Indoor Hypersim checkpoint (max_depth 20 m).
METRIC_DEPTH_MODEL = "depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf"


def depth_to_score_map(result) -> "object | None":
    """Pipeline output (PIL image, brighter=closer) → float map in [0, 1]."""
    import numpy as np

    image = result.get("depth") if isinstance(result, dict) else result
    if image is None:
        return None
    array = np.asarray(image, dtype=np.float32)
    if array.size == 0:
        return None
    lo, hi = float(array.min()), float(array.max())
    if hi - lo < 1e-6:
        return None
    return (array - lo) / (hi - lo)


def depth_to_metric_map(result) -> "object | None":
    """Metric pipeline output (`predicted_depth` tensor, metres) → float map.

    The metric checkpoint regresses absolute depth, so no normalisation is
    applied — values are already metres and feed WorldModel(metric=True).
    """
    import numpy as np

    pred = result.get("predicted_depth") if isinstance(result, dict) else None
    if pred is None:
        return None
    try:
        array = pred.detach().cpu().numpy()
    except AttributeError:
        array = np.asarray(pred, dtype=np.float32)
    array = np.squeeze(np.asarray(array, dtype=np.float32))
    if array.ndim != 2 or array.size == 0:
        return None
    return array


class SceneSense(VisionPlugin):
    name = "scenesense"

    def __init__(
        self,
        every_n: int = 2,
        frame_w: int = 640,
        frame_h: int = 480,
        pipeline_factory=None,
        *,
        deadline_s: float = 1.5,
        k_sigma: float = 2.0,
        clear_m: float = 0.5,
        spec_window_s: float = 2.0,
        ground: dict | None = None,
        metric: bool = False,
        model_name: str = "",
    ) -> None:
        self.every_n = max(1, int(every_n))
        self.metric = bool(metric)
        # Metric mode defaults to the metric checkpoint; a non-empty
        # model_name override wins in both modes.
        if model_name:
            self.model_name = model_name
        else:
            self.model_name = METRIC_DEPTH_MODEL if self.metric else DEPTH_MODEL
        self.model = WorldModel(
            frame_w=frame_w,
            frame_h=frame_h,
            k_sigma=k_sigma,
            deadline_s=deadline_s,
            clear_margin_m=clear_m,
            spec_window_s=spec_window_s,
            ground=ground,
            metric=self.metric,
        )
        self._pipe = None
        self._factory = pipeline_factory
        self._load_failed = False
        self._calls = 0
        self._passes = 0
        self.last_ms = 0.0
        self._distance_cm: float | None = None

    def start(self, cfg: dict) -> None:
        camera = cfg.get("camera", {})
        self.model.frame_w = int(camera.get("width", 640))
        self.model.frame_h = int(camera.get("height", 480))

    def note_distance(self, distance_cm: float | None) -> None:
        """Push the newest ultrasonic reading (cm) into the world model."""
        try:
            cm = None if distance_cm is None else float(distance_cm)
            self._distance_cm = cm if (cm is not None and cm > 0) else None
        except (TypeError, ValueError):
            self._distance_cm = None

    def _ensure_pipe(self):
        if self._pipe is not None or self._load_failed:
            return self._pipe
        model_name = self.model_name
        factory = self._factory
        if factory is None:

            def factory(prompt):
                from transformers import pipeline

                return pipeline("depth-estimation", model=prompt)

        try:
            self._pipe = factory(model_name)
        except Exception:
            logger.exception("depth model unavailable; geometry-only world model")
            self._load_failed = True
        return self._pipe

    def _depth_map(self, frame):
        pipe = self._ensure_pipe()
        if pipe is None or frame is None:
            return None
        import cv2
        from PIL import Image

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = pipe(Image.fromarray(rgb))
        if self.metric:
            return depth_to_metric_map(result)
        return depth_to_score_map(result)

    def process_frame(self, frame):
        return None  # never mutates the frame

    def process_detections(self, frame, dets: list) -> list:
        self._calls += 1
        if frame is None:
            return dets
        if (self._calls % self.every_n) != 0:
            return dets
        self._passes += 1
        t0 = time.time()
        try:
            depth = self._depth_map(frame)
            self.model.update(dets, depth_map=depth, distance_cm=self._distance_cm)
        finally:
            self.last_ms = round((time.time() - t0) * 1000.0, 1)
        return dets

    def world_state(self) -> dict:
        return self.model.status()

    def stats(self) -> dict:
        loading = self._pipe is None and not self._load_failed and self._passes > 0
        return {
            "calls": self._calls,
            "passes": self._passes,
            "last_ms": self.last_ms,
            "depth": self.model.last.get("depth", "off"),
            "calibrated": self.calibrator_ready(),
            "loading": loading,
            "model": self.model_name,
        }

    def calibrator_ready(self) -> bool:
        return bool(self.model.calibrator.ready)


def create(cfg: dict) -> SceneSense:
    plugins_cfg = cfg.get("plugins", {}) or {}
    camera = cfg.get("camera", {}) or {}
    return SceneSense(
        every_n=int(plugins_cfg.get("scenesense_every_n", 2)),
        deadline_s=float(plugins_cfg.get("world_deadline_s", 1.5)),
        k_sigma=float(plugins_cfg.get("world_k_sigma", 2.0)),
        clear_m=float(plugins_cfg.get("world_clear_m", 0.5)),
        spec_window_s=float(plugins_cfg.get("world_spec_window_s", 2.0)),
        ground=camera.get("ground_plane", {}) or {},
        metric=bool(plugins_cfg.get("scenesense_metric_depth", False)),
        model_name=str(plugins_cfg.get("scenesense_depth_model", "") or ""),
    )
