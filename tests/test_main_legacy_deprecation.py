"""The headless autonomous path in software/main.py is legacy/secondary.

The Mission Deck is the canonical autonomous rover, so RoverApp's autonomous
modes must flag the deprecation while --mode manual stays unsignalled.
"""

import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from software.main import LEGACY_AUTONOMOUS_MODES, LEGACY_NOTICE, RoverApp
from software.utils.config_loader import load_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg() -> dict:
    return load_config(str(ROOT / "config" / "config.yaml"))


def test_legacy_set_covers_the_autonomous_modes():
    assert {"observe", "search", "scan360"} == LEGACY_AUTONOMOUS_MODES
    assert "manual" not in LEGACY_AUTONOMOUS_MODES


@pytest.mark.parametrize("mode", ["observe", "search", "scan360"])
def test_autonomous_modes_emit_deprecation(cfg, mode):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        RoverApp(cfg, mode=mode, target="bottle", mock_hw=True)
    deprecated = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert any(LEGACY_NOTICE in str(w.message) for w in deprecated)


def test_manual_mode_is_not_deprecated(cfg):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        RoverApp(cfg, mode="manual", target="bottle", mock_hw=True)
    assert not [w for w in caught if issubclass(w.category, DeprecationWarning)]
