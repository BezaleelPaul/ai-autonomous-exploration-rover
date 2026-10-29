"""Wire the auto-tuner to ``config/config.yaml``.

Config keys are read here (and only where noted), so ``config/config.yaml``
stays the single description of every dial the tuner may move:

* ``autotune.enabled``        — master switch (off = shipped values, forever)
* ``autotune.window_s``       — how long one candidate is measured
* ``autotune.budget_margin``  — refresh budget as a fraction of the target lock
* ``autotune.max_interval``   — ceiling of the inference-interval search
* ``autotune.rearm_ratio``    — degrade past this multiple -> explore again
* ``autotune.improve_ratio``  — improve past this fraction -> explore again
* ``autotune.learned_path``   — overlay file, read by ``load_config`` and by
  :func:`write_learned` (empty string disables persistence)

The shipped defaults double as each search space's tie-break anchor, so an
inconclusive measurement can never move a dial away from what the project
ships with.

Two tuners, one algorithm:

* **online** — :func:`build_tuner` + :func:`build_realtime`, run by
  ``LiveFeed`` every session. Its only dial is ``ai.inference_interval``,
  which is deliberately *not* persisted: the right interval depends on how
  busy the host is right now, so it is re-derived each session.
* **offline** — :func:`detection_spaces` + :func:`write_learned`, run by
  ``scripts/autotune_detection.py`` against labelled images. Its dials
  (``ai.confidence_threshold``, ``ai.min_box_px``, ``ai.iou_threshold``)
  describe the model's operating point and *are* persisted, because that
  does not change between runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from software.autotune.core import AutoTuner, SearchSpace, apply_learned
from software.autotune.governors import INTERVAL_SPACE, RealtimeGovernor
from software.autotune.store import (
    DEFAULT_LEARNED_PATH,
    flatten,
    group_by_section,
    learned_overlay,
    save_learned,
)

# Session-local dials that must never be written back to the overlay.
PERSIST_EXCLUDE: tuple[str, ...] = (INTERVAL_SPACE,)


@dataclass(frozen=True)
class AutotuneSettings:
    enabled: bool
    learned_path: str
    window_s: float
    budget_margin: float
    max_interval: int
    rearm_ratio: float
    improve_ratio: float
    target_lock_s: float


def settings_from_config(cfg: dict[str, Any]) -> AutotuneSettings:
    raw = cfg.get("autotune", {}) or {}
    lock = cfg.get("navigation", {}).get("target_lock_duration_s", 2.0)
    return AutotuneSettings(
        enabled=bool(raw.get("enabled", True)),
        learned_path=str(raw.get("learned_path", DEFAULT_LEARNED_PATH)),
        window_s=float(raw.get("window_s", 2.0)),
        budget_margin=float(raw.get("budget_margin", 0.25)),
        max_interval=max(1, int(raw.get("max_interval", 8))),
        rearm_ratio=float(raw.get("rearm_ratio", 1.5)),
        improve_ratio=float(raw.get("improve_ratio", 0.5)),
        target_lock_s=float(lock),
    )


def _anchor(candidates: tuple[Any, ...], shipped: Any) -> Any:
    """Nearest candidate to the shipped value (which must be representable)."""
    if shipped in candidates:
        return shipped
    try:
        numeric = [
            (abs(float(c) - float(shipped)), i) for i, c in enumerate(candidates)
        ]
    except (TypeError, ValueError):
        return candidates[0]
    return candidates[min(numeric)[1]]


def interval_space(settings: AutotuneSettings, cfg: dict[str, Any]) -> SearchSpace:
    """The inference-interval dial: every integer up to ``max_interval``."""
    shipped = int(cfg.get("ai", {}).get("inference_interval", 1) or 1)
    candidates = tuple(range(1, settings.max_interval + 1))
    return SearchSpace(
        name=INTERVAL_SPACE,
        candidates=candidates,
        default=_anchor(candidates, shipped),
    )


def build_tuner(
    cfg: dict[str, Any], settings: AutotuneSettings | None = None
) -> tuple[AutoTuner, AutotuneSettings]:
    """Create the online tuner and register its search space."""
    settings = settings or settings_from_config(cfg)
    tuner = AutoTuner(
        enabled=settings.enabled,
        rearm_ratio=settings.rearm_ratio,
        improve_ratio=settings.improve_ratio,
    )
    tuner.add(interval_space(settings, cfg))
    return tuner, settings


def build_realtime(
    tuner: AutoTuner,
    settings: AutotuneSettings,
    *,
    interval: int,
) -> RealtimeGovernor:
    return RealtimeGovernor(
        tuner,
        interval=interval,
        budget_s=settings.budget_margin * settings.target_lock_s,
        window_s=settings.window_s,
        lo=1,
        hi=settings.max_interval,
    )


def detection_spaces(cfg: dict[str, Any]) -> list[SearchSpace]:
    """Offline operating-point dials (see ``scripts/autotune_detection.py``)."""
    ai = cfg.get("ai", {})
    specs: tuple[tuple[str, tuple[Any, ...], Any], ...] = (
        (
            "ai.confidence_threshold",
            (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50),
            ai.get("confidence_threshold", 0.25),
        ),
        ("ai.min_box_px", (0, 4, 8, 12, 16), ai.get("min_box_px", 8)),
        ("ai.iou_threshold", (0.4, 0.5, 0.6, 0.7), ai.get("iou_threshold", 0.5)),
    )
    return [
        SearchSpace(name=name, candidates=cands, default=_anchor(cands, shipped))
        for name, cands, shipped in specs
    ]


def build_offline_tuner(
    cfg: dict[str, Any], settings: AutotuneSettings | None = None
) -> tuple[AutoTuner, AutotuneSettings]:
    """Tuner for the labelled-data calibration run (seeds from the overlay)."""
    settings = settings or settings_from_config(cfg)
    tuner = AutoTuner(
        enabled=True,
        rearm_ratio=settings.rearm_ratio,
        improve_ratio=settings.improve_ratio,
    )
    for space in detection_spaces(cfg):
        tuner.add(space)
    if settings.learned_path:
        apply_learned(tuner, flatten(learned_overlay(settings.learned_path)))
    return tuner, settings


def learned_sections(
    tuner: AutoTuner, exclude: tuple[str, ...] = PERSIST_EXCLUDE
) -> dict[str, dict[str, Any]]:
    """Committed, non-default values worth remembering, grouped by section."""
    values = {k: v for k, v in tuner.learned().items() if k not in exclude}
    return group_by_section(values)


def write_learned(
    tuner: AutoTuner, settings: AutotuneSettings, *, source: str = "autotune"
) -> bool:
    """Persist the committed operating point; False when there is nothing new."""
    if not settings.learned_path:
        return False
    sections = learned_sections(tuner)
    if not sections:
        return False
    current = learned_overlay(settings.learned_path)
    if all(current.get(sec) == vals for sec, vals in sections.items()):
        return False
    save_learned(settings.learned_path, sections, source=source)
    return True
