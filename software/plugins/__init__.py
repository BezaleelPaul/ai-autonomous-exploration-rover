"""Pluggable vision enhancements for the perception pipeline.

System-level design: plugins sit *beside* the control loop, never in it.

    capture ──▶ [frame plugins] ──▶ detector ──▶ [detection plugins] ──▶ pilot

Every hook call is isolated and timed — a broken or slow plugin degrades
quality at worst, it can never stop video, detection or the safety chain.
Enabled plugins come from ``config/config.yaml``::

    plugins:
      enabled: ["world"]

Each entry names a module under ``software.plugins`` exposing ``create(cfg)``
returning a VisionPlugin. Load order = config order; a plugin that fails to
import or construct is logged and skipped.
"""

from __future__ import annotations

import importlib
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class VisionPlugin:
    """Hook contract. Override any subset; every method is optional."""

    name = "plugin"

    def start(self, cfg: dict) -> None:
        """Called once at pipeline start (load weights here, lazily if slow)."""

    def process_frame(self, frame: Any) -> Any:
        """Pre-AI hook: enhance/upscale the frame. Return None to keep it."""
        return frame

    def process_detections(self, frame: Any, dets: list) -> list:
        """Post-AI hook: merge/annotate/filter detections. Return None to keep."""
        return dets

    def stop(self) -> None:
        """Called once at shutdown."""

    def stats(self) -> dict:
        """Extra counters surfaced in /api/state under feed.plugins_stats."""
        return {}


def load_plugins(cfg: dict) -> list[VisionPlugin]:
    """Instantiate the enabled plugins; failures are logged, never raised."""
    names = [str(n) for n in (cfg.get("plugins", {}) or {}).get("enabled", []) or []]
    plugins: list[VisionPlugin] = []
    for name in names:
        if not name.replace("_", "").isalnum():
            logger.warning("plugin name %r rejected", name)
            continue
        try:
            module = importlib.import_module(f"software.plugins.{name}")
            plugin = module.create(cfg)
            plugin.start(cfg)
            plugins.append(plugin)
            logger.info("plugin loaded: %s", name)
        except Exception:
            logger.exception("plugin %r failed to load; skipping", name)
    return plugins


def run_frame_plugins(plugins: list, frame: Any) -> tuple[Any, dict[str, float]]:
    """Run pre-AI hooks in order; returns (frame, {plugin: ms})."""
    timings: dict[str, float] = {}
    for plugin in plugins:
        t0 = time.time()
        try:
            out = plugin.process_frame(frame)
            if out is not None:
                frame = out
        except Exception:
            logger.exception("plugin %s process_frame failed", plugin.name)
        finally:
            timings[plugin.name] = timings.get(plugin.name, 0.0) + round(
                (time.time() - t0) * 1000.0, 1
            )
    return frame, timings


def run_detection_plugins(
    plugins: list, frame: Any, dets: list
) -> tuple[list, dict[str, float]]:
    """Run post-AI hooks in order; returns (dets, {plugin: ms})."""
    timings: dict[str, float] = {}
    for plugin in plugins:
        t0 = time.time()
        try:
            out = plugin.process_detections(frame, dets)
            if out is not None:
                dets = out
        except Exception:
            logger.exception("plugin %s process_detections failed", plugin.name)
        finally:
            timings[plugin.name] = timings.get(plugin.name, 0.0) + round(
                (time.time() - t0) * 1000.0, 1
            )
    return dets, timings


def merge_timings(*timing_maps: dict[str, float]) -> dict[str, float]:
    """Sum per-plugin ms across the frame and detection passes."""
    merged: dict[str, float] = {}
    for timings in timing_maps:
        for name, ms in timings.items():
            merged[name] = round(merged.get(name, 0.0) + float(ms), 1)
    return merged
