"""Persisted auto-tune state: ``config/learned.yaml``.

`load_config` merges this overlay on top of the shipped ``config.yaml`` so a
value the tuner found in one session is still in effect after a restart. The
file is a *runtime artifact*, not a source file: it is git-ignored, it is
recreated by the tuner, and it is discarded wholesale if it ever fails
``validate_config`` (a broken overlay must never brick a session — the same
fail-open rule the serial auto-detect follows).

Only the sections in :data:`LEARNED_SECTIONS` are ever read or written. The
geometry, serial and safety sections (``rover``, ``safety``, ``serial``,
``navigation``, ``thresholds``) describe the physical machine and the safety
envelope, so no tuner is allowed to touch them.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

DEFAULT_LEARNED_PATH = "config/learned.yaml"
LEARNED_SECTIONS: tuple[str, ...] = ("ai", "camera", "plugins")
_META_KEY = "_meta"


def _read(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def learned_overlay(path: str | Path | None) -> dict[str, Any]:
    """Allow-listed ``{section: {key: value}}`` from the overlay file."""
    raw = _read(path)
    out: dict[str, Any] = {}
    for section in LEARNED_SECTIONS:
        values = raw.get(section)
        if isinstance(values, dict) and values:
            out[section] = dict(values)
    return out


def flatten(sections: Mapping[str, Any]) -> dict[str, Any]:
    """``{section: {...}}`` -> ``{"section.key": value}`` (tuner space names)."""
    flat: dict[str, Any] = {}
    for section, values in sections.items():
        if not isinstance(values, Mapping):
            continue
        for key, value in values.items():
            flat[f"{section}.{key}"] = value
    return flat


def save_learned(
    path: str | Path | None,
    sections: Mapping[str, Any],
    *,
    source: str = "autotune",
) -> dict[str, Any]:
    """Merge ``sections`` into the overlay (each given section replaces its
    own block, untouched sections survive) and write it atomically.

    Returns the full overlay that was written.
    """
    if not path:
        return {}
    provided = {
        k: dict(v)
        for k, v in sections.items()
        if k in LEARNED_SECTIONS and isinstance(v, Mapping)
    }
    if not provided:
        return learned_overlay(path)
    merged = learned_overlay(path)
    merged.update(provided)
    payload: dict[str, Any] = dict(merged)
    payload[_META_KEY] = {
        "source": str(source),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f"{p.name}.tmp")
        tmp.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        return learned_overlay(path)
    return merged


def group_by_section(values: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """``{"camera.enhance_clahe": False}`` -> ``{"camera": {"enhance_clahe": False}}``."""
    grouped: dict[str, dict[str, Any]] = {}
    for dotted, value in values.items():
        if "." not in str(dotted):
            continue
        section, key = str(dotted).split(".", 1)
        if section not in LEARNED_SECTIONS or "." in key:
            continue
        grouped.setdefault(section, {})[key] = value
    return grouped
