"""Config loading + validation."""

from __future__ import annotations

import copy
import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Environment overrides (.env.example): file values are the defaults,
# environment variables win when present.
_ENV_OVERRIDES = {
    "ESP32_STREAM_URL": ("camera", "esp32_url", str),
    "ARDUINO_PORT": ("serial", "port", str),
    "ARDUINO_BAUD": ("serial", "baud_rate", int),
    "AI_MODEL_NAME": ("ai", "model_name", str),
    "TARGET_CLASS": ("ai", "target_class", str),
    "LOG_LEVEL": ("logging", "level", str),
}

# "read the path out of autotune.learned_path" (None means "no overlay").
_FROM_CONFIG = object()


def load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def _apply_env_overrides(cfg: dict[str, Any]) -> None:
    for env_name, (section, key, cast) in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_name)
        if not raw:
            continue
        try:
            value: Any = cast(raw)
        except (TypeError, ValueError):
            continue  # malformed env value: keep the file value
        cfg.setdefault(section, {})[key] = value


def _resolve_learned_path(
    cfg: dict[str, Any], learned_path: str | Path | object
) -> Path | None:
    """Where the learned overlay lives (``autotune.learned_path``)."""
    if learned_path is _FROM_CONFIG:
        raw = (cfg.get("autotune", {}) or {}).get("learned_path", "")
        learned_path = raw if raw is not None else ""
    if not learned_path:
        return None
    return Path(str(learned_path))


def _merge_learned_overlay(
    cfg: dict[str, Any], path: Path | None
) -> dict[str, Any] | None:
    """Merge remembered values on top of the shipped config.

    Precedence becomes **file < learned < environment**. The overlay only
    carries perception dials (``software.autotune.store.LEARNED_SECTIONS``) and
    it is dropped wholesale when the result fails ``validate_config``: a stale
    or hand-mangled overlay must degrade to the shipped values, never brick a
    session.
    """
    if path is None or not path.is_file():
        return None
    from software.autotune.store import learned_overlay

    overlay = learned_overlay(path)
    if not overlay:
        return None
    trial = copy.deepcopy(cfg)
    for section, values in overlay.items():
        node = trial.setdefault(section, {})
        if not isinstance(node, dict):
            continue
        node.update(values)
    try:
        validate_config(trial)
    except ValueError as exc:
        logger.warning("ignoring learned overlay %s: %s", path, exc)
        return None
    return trial


def load_config(
    config_path: str | Path = "config/config.yaml",
    thresholds_path: str | Path | None = "config/thresholds.yaml",
    learned_path: str | Path | object = _FROM_CONFIG,
) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    # cfg["thresholds"] is always present after load_config (empty dict when
    # thresholds.yaml is absent); safety code reads its ultrasonic cutoffs.
    if thresholds_path and Path(thresholds_path).exists():
        cfg["thresholds"] = load_yaml(thresholds_path)
    else:
        cfg.setdefault("thresholds", {})
    merged = _merge_learned_overlay(cfg, _resolve_learned_path(cfg, learned_path))
    if merged is not None:
        cfg = merged
    _apply_env_overrides(cfg)
    validate_config(cfg)
    return cfg


def _positive(name: str, value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be > 0")


def validate_config(cfg: dict[str, Any]) -> None:
    required_top = ["camera", "ai", "rover", "serial", "navigation", "safety"]
    for key in required_top:
        if key not in cfg:
            raise ValueError(f"Missing config section: {key}")
    # sanity checks
    nav = cfg["navigation"]
    if not (0 < nav["left_boundary"] < nav["center_boundary"] < 1.0):
        raise ValueError(
            "navigation zone boundaries must satisfy 0 < left < center < 1"
        )
    if cfg["ai"]["confidence_threshold"] < 0 or cfg["ai"]["confidence_threshold"] > 1:
        raise ValueError("confidence_threshold must be in [0,1]")
    # optional: separates "which objects we report" from "which we act on"
    target_conf = cfg["ai"].get("target_confidence")
    if target_conf is not None and (target_conf < 0 or target_conf > 1):
        raise ValueError("target_confidence must be in [0,1]")
    rover = cfg["rover"]
    if rover["emergency_stop_distance_cm"] >= rover["slow_down_distance_cm"]:
        raise ValueError("emergency_stop_distance must be < slow_down_distance")

    # documented optional keys: range checks keep them honest when present
    camera = cfg.get("camera", {})
    _positive("camera.fps_target", camera.get("fps_target"))
    _positive("camera.jpeg_timeout_s", camera.get("jpeg_timeout_s"))
    for key in ("width_cm", "length_cm", "turning_duration_s", "max_speed_pwm"):
        _positive(f"rover.{key}", rover.get(key))
    if rover.get("max_speed_pwm") is not None and rover["max_speed_pwm"] > 255:
        raise ValueError("max_speed_pwm must be <= 255")
    margin = rover.get("safety_margin_cm")
    if margin is not None and margin < 0:
        raise ValueError("safety_margin_cm must be >= 0")
    min_obstacle = rover.get("min_obstacle_distance_cm")
    if min_obstacle is not None and min_obstacle < rover["emergency_stop_distance_cm"]:
        raise ValueError(
            "min_obstacle_distance_cm must be >= emergency_stop_distance_cm"
        )
    attempts = cfg["serial"].get("reconnect_attempts")
    if attempts is not None and attempts < 1:
        raise ValueError("reconnect_attempts must be >= 1")
    heartbeat = cfg["serial"].get("heartbeat_interval_s")
    comm_timeout = cfg.get("safety", {}).get("comm_timeout_s")
    if heartbeat is not None and comm_timeout is not None and heartbeat >= comm_timeout:
        raise ValueError("heartbeat_interval_s must be < safety.comm_timeout_s")
    # Phase 9+ closed-loop drive foundation (docs/future-work/30)
    ctl = cfg.get("control", {})
    _positive("control.encoder_ppr", ctl.get("encoder_ppr"))
    _positive("control.wheel_diameter_cm", ctl.get("wheel_diameter_cm"))
    for gain in ("pid_kp", "pid_ki", "pid_kd", "velocity_kp", "steering_kp"):
        v = ctl.get(gain)
        if v is not None and v < 0:
            raise ValueError(f"control.{gain} must be >= 0")
    for key in ("velocity_target_tps", "velocity_period_ms"):
        _positive(f"control.{key}", ctl.get(key))
    for key in ("velocity_pwm_ff", "steering_min_pwm"):
        v = ctl.get(key)
        if v is not None and not (0 <= v <= 255):
            raise ValueError(f"control.{key} must be in 0..255")
    # Auto-tune: the tuner may only move dials inside these ranges, so the
    # bounds live here (the same clamp every config source goes through).
    interval = cfg["ai"].get("inference_interval")
    if interval is not None and int(interval) < 1:
        raise ValueError("ai.inference_interval must be >= 1")
    auto = cfg.get("autotune", {})
    if not isinstance(auto, dict):
        raise ValueError("autotune must be a mapping")
    _positive("autotune.window_s", auto.get("window_s"))
    budget = auto.get("budget_margin")
    if budget is not None and not (0.0 < float(budget) <= 1.0):
        raise ValueError("autotune.budget_margin must be in (0,1]")
    max_interval = auto.get("max_interval")
    if max_interval is not None and int(max_interval) < 1:
        raise ValueError("autotune.max_interval must be >= 1")
    rearm = auto.get("rearm_ratio")
    if rearm is not None and float(rearm) <= 1.0:
        raise ValueError("autotune.rearm_ratio must be > 1.0")
    improve = auto.get("improve_ratio")
    if improve is not None and not (0.0 < float(improve) < 1.0):
        raise ValueError("autotune.improve_ratio must be in (0,1]")
    learned = auto.get("learned_path")
    if learned is not None and not isinstance(learned, str):
        raise ValueError("autotune.learned_path must be a string")
