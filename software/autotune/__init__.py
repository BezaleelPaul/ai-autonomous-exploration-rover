"""Auto-tune: let a parameter find its own value, then stabilise.

EXPLORE -> COMMIT -> MONITOR -> RE-ARM (see :mod:`software.autotune.core`).
The algorithm is hardware-agnostic; :mod:`software.autotune.governors` turns
live rover signals into the scalar costs it searches, and
:mod:`software.autotune.store` remembers what it learned between sessions.
"""

from __future__ import annotations

from software.autotune.core import (
    COMMITTING,
    EXPLORING,
    AutoTuner,
    SearchSpace,
    apply_learned,
)
from software.autotune.factory import (
    AutotuneSettings,
    build_offline_tuner,
    build_realtime,
    build_tuner,
    detection_spaces,
    settings_from_config,
    write_learned,
)
from software.autotune.governors import INTERVAL_SPACE, RealtimeGovernor
from software.autotune.store import (
    DEFAULT_LEARNED_PATH,
    LEARNED_SECTIONS,
    learned_overlay,
    save_learned,
)

__all__ = [
    "COMMITTING",
    "DEFAULT_LEARNED_PATH",
    "EXPLORING",
    "INTERVAL_SPACE",
    "LEARNED_SECTIONS",
    "AutoTuner",
    "AutotuneSettings",
    "RealtimeGovernor",
    "SearchSpace",
    "apply_learned",
    "build_offline_tuner",
    "build_realtime",
    "build_tuner",
    "detection_spaces",
    "learned_overlay",
    "save_learned",
    "settings_from_config",
    "write_learned",
]
