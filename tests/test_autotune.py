"""Auto-tune: explore -> commit -> monitor -> re-arm, and its persistence.

The rover ships with hand-measured values. These tests cover the machinery
that lets a value *find its own* value and then **stabilise**:

* :mod:`software.autotune.core` — the algorithm itself, hardware-free.
* :mod:`software.autotune.governors` — the online realtime governor.
* :mod:`software.autotune.factory` — config wiring and the offline dials.
* :mod:`software.autotune.store` / ``load_config`` — the learned overlay.
* ``LiveFeed`` — the interval gate actually wired into the live pipeline.
* ``scripts/autotune_detection.py`` — the offline calibration sweep.

Safety, serial, navigation and rover geometry are never auto-tuned, and the
tests below pin that by construction (the dial set is explicit and closed).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import scripts.autotune_detection as autotune_script
from software.autotune.core import (
    COMMITTING,
    EXPLORING,
    AutoTuner,
    SearchSpace,
    apply_learned,
)
from software.autotune.factory import (
    PERSIST_EXCLUDE,
    build_offline_tuner,
    build_realtime,
    build_tuner,
    detection_spaces,
    interval_space,
    learned_sections,
    settings_from_config,
    write_learned,
)
from software.autotune.governors import (
    INTERVAL_SPACE,
    VIOLATION_PENALTY,
    RealtimeGovernor,
    ema,
)
from software.autotune.store import (
    LEARNED_SECTIONS,
    flatten,
    group_by_section,
    learned_overlay,
    save_learned,
)
from software.dashboard.live import LiveFeed
from software.utils.config_loader import load_config, validate_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "config.yaml"


@pytest.fixture
def cfg() -> dict[str, Any]:
    return load_config(str(CONFIG))


# --------------------------------------------------------------------- core
class TestSearchSpace:
    def test_rejects_empty_or_duplicate_candidates(self) -> None:
        with pytest.raises(ValueError, match="has no candidates"):
            SearchSpace(name="x", candidates=(), default=1)
        with pytest.raises(ValueError, match="duplicate"):
            SearchSpace(name="x", candidates=(1, 1), default=1)

    def test_default_must_be_a_candidate(self) -> None:
        with pytest.raises(ValueError, match="not a candidate"):
            SearchSpace(name="x", candidates=(1, 2), default=3)

    def test_order_puts_the_anchor_first(self) -> None:
        space = SearchSpace(name="x", candidates=(5, 3, 1), default=3)
        assert space.order == (3, 5, 1)


class TestAutoTuner:
    def _tuner(self, *, enabled: bool = True) -> AutoTuner:
        tuner = AutoTuner(enabled=enabled)
        tuner.add(SearchSpace(name="dial", candidates=(1, 2, 4), default=2))
        return tuner

    def test_next_is_anchor_first_and_owed_only_once(self) -> None:
        tuner = self._tuner()
        assert tuner.next("dial") == (2, 1, 4)
        assert tuner.next("dial") == ()

    def test_committed_space_owes_nothing(self) -> None:
        tuner = self._tuner()
        tuner.report("dial", {2: 0.5, 1: 0.2, 4: 0.9})
        assert tuner.phase("dial") == COMMITTING
        assert tuner.next("dial") == ()
        assert tuner.value("dial") == 1

    def test_ties_resolve_to_the_anchor(self) -> None:
        tuner = self._tuner()
        tuner.report("dial", {2: 0.4, 1: 0.4, 4: 0.9})
        assert tuner.value("dial") == 2

    def test_partial_report_keeps_candidates_outstanding(self) -> None:
        tuner = self._tuner()
        assert tuner.next("dial") == (2, 1, 4)
        tuner.report("dial", {2: 0.4})
        # 1 and 4 are handed out but not yet answered, so they are not owed
        # again; once the outstanding ones land the space commits.
        assert tuner.phase("dial") == EXPLORING
        assert tuner.next("dial") == ()
        tuner.report("dial", {1: 0.2, 4: 0.9})
        assert tuner.phase("dial") == COMMITTING
        assert tuner.value("dial") == 1

    def test_unknown_space_and_unknown_candidate_are_rejected(self) -> None:
        tuner = self._tuner()
        with pytest.raises(KeyError, match="unknown search space"):
            tuner.value("nope")
        with pytest.raises(ValueError, match="is not a candidate"):
            tuner.report("dial", {9: 1.0})

    def test_report_accepts_cost_or_cost_feasible(self) -> None:
        tuner = self._tuner()
        tuner.report("dial", {2: 0.5, 1: (0.1, False), 4: 0.9})
        assert tuner.value("dial") == 1
        assert tuner.status()["params"]["dial"]["feasible"] is False

    def test_monitor_is_stable_inside_the_band(self) -> None:
        tuner = self._tuner()
        tuner.report("dial", {2: 0.4, 1: 0.2, 4: 0.9})  # commits at cost 0.2
        assert tuner.monitor("dial", 0.21) == "stable"
        assert tuner.monitor("dial", 0.3) == "stable"

    def test_monitor_rearms_on_degrade(self) -> None:
        tuner = self._tuner()
        tuner.report("dial", {2: 0.4, 1: 0.2, 4: 0.9})
        assert tuner.monitor("dial", 1.0) == "rearm"
        assert tuner.phase("dial") == EXPLORING
        assert tuner.next("dial") == (2, 1, 4)

    def test_monitor_rearms_on_improve(self) -> None:
        tuner = self._tuner()
        tuner.report("dial", {2: 0.4, 1: 0.4, 4: 0.4})  # all tie -> anchor
        assert tuner.monitor("dial", 0.05) == "rearm"

    def test_infeasible_commit_ignores_cost_noise(self) -> None:
        # Committed while already over budget. Costs that swing across both
        # re-arm thresholds are latency noise once a hard constraint is broken.
        tuner = self._tuner()
        tuner.report("dial", {2: (900.0, False), 1: (500.0, False), 4: (1300.0, False)})
        assert tuner.value("dial") == 1
        for noisy in (1300.0, 100.0, 1500.0, 50.0, 1400.0, 0.0):
            assert tuner.monitor("dial", noisy, feasible=False) == "stable"
        # The measured thrash was 16 commits / 15 re-arms: it must be zero here.
        assert tuner.status()["params"]["dial"]["rearms"] == 0

    def test_infeasible_commit_rearms_once_it_becomes_feasible(self) -> None:
        # The host got faster, so a roomier candidate may now close the loop.
        tuner = self._tuner()
        tuner.report("dial", {2: (900.0, False), 1: (500.0, False), 4: (1300.0, False)})
        assert tuner.monitor("dial", 0.1, feasible=True) == "rearm"

    def test_feasible_commit_still_rearms_when_it_breaks(self) -> None:
        # Hysteresis must not swallow a real feasible -> infeasible degrade.
        tuner = self._tuner()
        tuner.report("dial", {2: 0.4, 1: 0.2, 4: 0.9})
        assert tuner.monitor("dial", 1.0, feasible=False) == "rearm"

    def test_monitor_reports_its_mode_before_commit(self) -> None:
        tuner = self._tuner()
        assert tuner.monitor("dial", 0.2) == "exploring"

    def test_disabled_tuner_never_explores(self) -> None:
        tuner = self._tuner(enabled=False)
        assert tuner.next("dial") == ()
        assert tuner.monitor("dial", 9.9) == "disabled"

    def test_seed_outside_the_space_is_refused(self) -> None:
        tuner = self._tuner()
        assert tuner.seed("dial", 99) is False
        assert tuner.value("dial") == 2
        assert tuner.seed("dial", 4) is True
        assert tuner.value("dial") == 4

    def test_learned_only_reports_dials_that_moved(self) -> None:
        tuner = self._tuner()
        assert tuner.learned() == {}
        tuner.report("dial", {2: 0.4, 1: 0.2, 4: 0.9})
        assert tuner.learned() == {"dial": 1}

    def test_history_records_commits_and_rearms(self) -> None:
        tuner = self._tuner()
        tuner.report("dial", {2: 0.4, 1: 0.2, 4: 0.9})
        tuner.monitor("dial", 5.0)
        history = tuner.history("dial")
        assert [h["action"] for h in history] == ["commit", "rearm"]
        assert history[0]["value"] == 1
        assert history[1]["reason"] == "degraded"

    def test_apply_learned_ignores_unknown_dials(self) -> None:
        tuner = self._tuner()
        assert apply_learned(tuner, {"dial": 4, "safety.emergency_stop": 1}) == ["dial"]
        assert tuner.value("dial") == 4

    def test_constructor_rejects_nonsense_bands(self) -> None:
        with pytest.raises(ValueError, match="rearm_ratio"):
            AutoTuner(rearm_ratio=0.5)
        with pytest.raises(ValueError, match="improve_ratio"):
            AutoTuner(improve_ratio=1.5)


# -------------------------------------------------------------- governors
class TestRealtimeGovernor:
    #: A synthetic but *consistent* host: the detector answers in 80 ms and a
    #: whole loop pass (enhance + detect + idle sleep) takes 100 ms, so
    #: ``infer_ms <= per_frame`` as it must be in the real pipeline.
    PASS_S = 0.1
    INFER_MS = 80.0

    def _gov(
        self,
        cfg: dict[str, Any],
        *,
        interval: int = 2,
        budget_s: float = 0.5,
        window_s: float = 0.0,
    ) -> RealtimeGovernor:
        tuner, settings = build_tuner(cfg)
        return RealtimeGovernor(
            tuner,
            interval=interval,
            budget_s=budget_s,
            window_s=window_s,
            lo=1,
            hi=settings.max_interval,
        )

    def _drive(
        self,
        gov: RealtimeGovernor,
        *,
        pass_s: float,
        infer_ms: float = INFER_MS,
        n: int = 6,
    ) -> str:
        """Feed ``n`` observations, one per loop pass of ``pass_s`` seconds."""
        now = 1_000.0
        action = "init"
        for _ in range(n):
            now += pass_s * gov.interval
            action = gov.observe(now, infer_ms)
        return action

    def test_first_sample_only_warms_up(self) -> None:
        gov = self._gov(load_config(str(CONFIG)))
        assert gov.observe(1.0, 100.0) == "warmup"

    def test_ema_seeds_then_blends(self) -> None:
        assert ema(None, 10.0, 0.3) == 10.0
        assert ema(10.0, 20.0, 0.3) == pytest.approx(13.0)

    def test_idle_host_commits_the_largest_feasible_interval(self) -> None:
        # per_frame 0.1 s, budget 0.5 s -> the roomiest closing interval is 5.
        gov = self._gov(load_config(str(CONFIG)))
        self._drive(gov, pass_s=self.PASS_S)
        assert gov.interval == 5
        assert gov.tuner.phase(INTERVAL_SPACE) == COMMITTING
        assert gov.predict(5, gov.per_frame()) <= gov.budget_s

    def test_busy_host_falls_back_to_interval_one(self) -> None:
        # per_frame 0.36 s: only k=1 stays inside the 0.5 s budget.
        gov = self._gov(load_config(str(CONFIG)))
        self._drive(gov, pass_s=0.36, infer_ms=300.0)
        assert gov.interval == 1

    def test_committed_interval_is_rearmed_when_the_host_slows_down(self) -> None:
        gov = self._gov(load_config(str(CONFIG)))
        self._drive(gov, pass_s=self.PASS_S)
        assert gov.tuner.phase(INTERVAL_SPACE) == COMMITTING
        now = 10_000.0
        actions = []
        for _ in range(8):
            now += 0.35 * gov.interval
            actions.append(gov.observe(now, 250.0))
        # the degraded value is thrown back to exploration...
        assert "rearm" in actions
        assert "explore" in actions
        # ...and the search re-finds a value that closes the loop again.
        assert gov.interval == 1
        assert gov.predict(1, gov.per_frame()) <= gov.budget_s
        assert actions[-1] == "stable"

    def test_over_budget_host_settles_instead_of_thrashing(self) -> None:
        # Live measurement on the 8 GB host: 16 commits / 15 re-arms in 90 s,
        # because every window flipped feasibility on latency jitter and the
        # violation penalty turned that into huge apparent cost moves. A host
        # that cannot close the loop at interval 1 must commit once and settle.
        gov = self._gov(load_config(str(CONFIG)))
        now = 1_000.0
        jitter = (0.9, 0.6, 1.3, 0.7, 1.1, 0.65, 1.4, 0.8, 1.0, 0.75) * 3
        actions = []
        for pass_s in jitter:
            now += pass_s * max(1, gov.interval)
            actions.append(gov.observe(now, 900.0))

        params = gov.tuner.status()["params"][INTERVAL_SPACE]
        assert gov.interval == 1  # most aggressive candidate
        assert params["commits"] <= 2  # explore once, commit
        assert params["rearms"] <= 1  # no churn on noise
        assert actions[-1] == "stable"

    def test_no_candidate_is_applied_during_exploration(self) -> None:
        gov = self._gov(load_config(str(CONFIG)), interval=2, window_s=60.0)
        # The window outlives the whole drive, so only warmup/measure run and
        # the shipped interval stays in force: an exploratory candidate is
        # never applied to the live loop while the tuner is deciding.
        actions = []
        now = 1_000.0
        for _ in range(6):
            now += 0.2
            actions.append(gov.observe(now, self.INFER_MS))
        assert gov.interval == 2
        assert set(actions) <= {"warmup", "measure"}
        assert gov.tuner.phase(INTERVAL_SPACE) == EXPLORING

    def test_cost_ranks_feasible_above_violating(self) -> None:
        gov = self._gov(load_config(str(CONFIG)))
        per_frame = 0.1
        # inside the budget a roomier interval is strictly better
        assert gov.cost(1, per_frame) > gov.cost(5, per_frame)
        # 0.6 s overshoots the 0.5 s budget and no headroom buys it back
        assert gov.cost(6, per_frame) > gov.cost(5, per_frame) + 1.0
        # overshooting further is worse still
        assert gov.cost(8, per_frame) > gov.cost(6, per_frame)

    def test_candidate_exactly_at_budget_is_feasible(self) -> None:
        gov = self._gov(load_config(str(CONFIG)))
        # 5 * 0.10000000000000003 == 0.5000000000000002 (float error), but the
        # boundary candidate must still count as feasible and pay no penalty,
        # otherwise it is re-armed forever for drifting 2e-16 of a second.
        per_frame = 0.10000000000000003
        assert gov.predict(5, per_frame) > gov.budget_s
        assert gov.within_budget(5, per_frame) is True
        assert gov.cost(5, per_frame) == pytest.approx(gov.cost(5, 0.1))

    def test_per_frame_falls_back_to_inference_latency(self) -> None:
        gov = self._gov(load_config(str(CONFIG)))
        assert gov.per_frame() == 0.0
        gov._infer_ms = 120.0
        assert gov.per_frame() == pytest.approx(0.12)

    def test_status_is_json_serialisable(self) -> None:
        gov = self._gov(load_config(str(CONFIG)))
        self._drive(gov, pass_s=self.PASS_S)
        assert json.loads(json.dumps(gov.status()))["interval"] == 5

    def test_disabled_tuner_freezes_the_interval(self) -> None:
        cfg = load_config(str(CONFIG))
        cfg["autotune"] = {**cfg["autotune"], "enabled": False}
        tuner, settings = build_tuner(cfg)
        gov = RealtimeGovernor(
            tuner,
            interval=3,
            budget_s=0.5,
            window_s=0.0,
            lo=1,
            hi=settings.max_interval,
        )
        assert gov.observe(1.0, 100.0) == "disabled"
        assert gov.interval == 3


# ----------------------------------------------------------------- factory
class TestFactory:
    def test_settings_default_when_the_section_is_missing(self) -> None:
        settings = settings_from_config({"navigation": {"target_lock_duration_s": 2.0}})
        assert settings.enabled is True
        assert settings.window_s == 2.0
        assert settings.target_lock_s == 2.0

    def test_budget_is_margin_times_target_lock(self) -> None:
        cfg = load_config(str(CONFIG))
        tuner, settings = build_tuner(cfg)
        gov = build_realtime(tuner, settings, interval=2)
        assert gov.budget_s == pytest.approx(
            cfg["autotune"]["budget_margin"]
            * cfg["navigation"]["target_lock_duration_s"]
        )

    def test_interval_space_is_bounded_and_anchored_on_the_shipped_value(self) -> None:
        cfg = load_config(str(CONFIG))
        settings = settings_from_config(cfg)
        space = interval_space(settings, cfg)
        assert space.candidates == tuple(range(1, settings.max_interval + 1))
        assert space.default == cfg["ai"]["inference_interval"]
        assert space.order[0] == space.default

    def test_build_tuner_exposes_exactly_the_online_dial(self) -> None:
        tuner, _ = build_tuner(load_config(str(CONFIG)))
        assert tuner.names() == (INTERVAL_SPACE,)

    def test_detection_spaces_are_the_closed_offline_set(self) -> None:
        cfg = load_config(str(CONFIG))
        assert {s.name for s in detection_spaces(cfg)} == {
            "ai.confidence_threshold",
            "ai.min_box_px",
            "ai.iou_threshold",
        }
        anchors = {s.name: s.default for s in detection_spaces(cfg)}
        assert anchors["ai.confidence_threshold"] == cfg["ai"]["confidence_threshold"]
        assert anchors["ai.min_box_px"] == cfg["ai"]["min_box_px"]

    def test_offline_tuner_seeds_from_the_overlay(self, tmp_path: Path) -> None:
        overlay = tmp_path / "learned.yaml"
        overlay.write_text(
            yaml.safe_dump({"ai": {"confidence_threshold": 0.40}}), encoding="utf-8"
        )
        cfg = load_config(str(CONFIG))
        settings = dataclasses.replace(
            settings_from_config(cfg), learned_path=str(overlay)
        )
        tuner, _ = build_offline_tuner(cfg, settings)
        assert tuner.value("ai.confidence_threshold") == 0.40
        # the seeded value also becomes the tie-break anchor
        assert tuner.next("ai.confidence_threshold")[0] == 0.40

    def test_online_dial_is_never_persisted(self, cfg: dict[str, Any]) -> None:
        tuner, settings = build_tuner(cfg)
        tuner.seed(INTERVAL_SPACE, 7)
        assert INTERVAL_SPACE in PERSIST_EXCLUDE
        assert learned_sections(tuner) == {}
        assert write_learned(tuner, settings) is False


# ------------------------------------------------------------------- store
class TestStore:
    def test_missing_or_unreadable_overlay_is_empty(self, tmp_path: Path) -> None:
        assert learned_overlay(tmp_path / "nope.yaml") == {}
        assert learned_overlay(None) == {}
        bad = tmp_path / "bad.yaml"
        bad.write_text("::not yaml::", encoding="utf-8")
        assert learned_overlay(bad) == {}

    def test_only_allow_listed_sections_survive(self, tmp_path: Path) -> None:
        path = tmp_path / "learned.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "ai": {"confidence_threshold": 0.3},
                    "safety": {"comm_timeout_s": 99},
                    "plugins": {"enabled": True},
                }
            ),
            encoding="utf-8",
        )
        overlay = learned_overlay(path)
        assert set(overlay) <= set(LEARNED_SECTIONS)
        assert "safety" not in overlay
        assert overlay["ai"]["confidence_threshold"] == 0.3

    def test_save_merges_per_section_and_keeps_the_rest(self, tmp_path: Path) -> None:
        path = tmp_path / "learned.yaml"
        save_learned(path, {"ai": {"confidence_threshold": 0.3}}, source="first")
        save_learned(path, {"camera": {"enhance_clahe": False}}, source="second")
        overlay = learned_overlay(path)
        assert overlay["ai"]["confidence_threshold"] == 0.3
        assert overlay["camera"]["enhance_clahe"] is False
        assert "safety" not in overlay
        assert not list(tmp_path.glob("*.tmp"))

    def test_group_and_flatten_round_trip(self) -> None:
        values = {"ai.confidence_threshold": 0.3, "camera.enhance_clahe": False}
        assert flatten(group_by_section(values)) == values

    def test_group_drops_foreign_and_nested_keys(self) -> None:
        assert group_by_section(
            {"safety.x": 1, "ai.a.b": 2, "ai.confidence_threshold": 0.3}
        ) == {"ai": {"confidence_threshold": 0.3}}

    def test_write_learned_skips_a_no_op(self, tmp_path: Path) -> None:
        overlay = tmp_path / "learned.yaml"
        overlay.write_text(
            yaml.safe_dump({"ai": {"confidence_threshold": 0.40}}), encoding="utf-8"
        )
        cfg = load_config(str(CONFIG))
        settings = dataclasses.replace(
            settings_from_config(cfg), learned_path=str(overlay)
        )
        tuner, _ = build_offline_tuner(cfg, settings)
        assert write_learned(tuner, settings) is False
        assert write_learned(tuner, settings, source="x") is False

    def test_write_learned_persists_a_new_value(self, tmp_path: Path) -> None:
        cfg = load_config(str(CONFIG))
        settings = dataclasses.replace(
            settings_from_config(cfg), learned_path=str(tmp_path / "learned.yaml")
        )
        tuner, _ = build_offline_tuner(cfg, settings)
        tuner.seed("ai.confidence_threshold", 0.40)
        assert write_learned(tuner, settings, source="unit") is True
        assert learned_overlay(settings.learned_path) == {
            "ai": {"confidence_threshold": 0.40}
        }


# ------------------------------------------------------- load_config wiring
class TestConfigLoaderIntegration:
    def test_shipped_config_declares_every_autotune_dial(self) -> None:
        shipped = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        assert set(shipped["autotune"]) == {
            "enabled",
            "learned_path",
            "window_s",
            "budget_margin",
            "max_interval",
            "rearm_ratio",
            "improve_ratio",
        }

    def test_overlay_is_merged_on_top_of_the_shipped_values(
        self, tmp_path: Path
    ) -> None:
        overlay = tmp_path / "learned.yaml"
        overlay.write_text(
            yaml.safe_dump({"ai": {"confidence_threshold": 0.40}}), encoding="utf-8"
        )
        merged = load_config(str(CONFIG), learned_path=overlay)
        assert merged["ai"]["confidence_threshold"] == 0.40
        assert merged["ai"]["target_confidence"] == 0.5  # untouched
        shipped = load_config(str(CONFIG), learned_path="")
        assert shipped["ai"]["confidence_threshold"] == 0.25

    def test_broken_overlay_is_dropped_not_fatal(self, tmp_path: Path) -> None:
        overlay = tmp_path / "learned.yaml"
        overlay.write_text(
            yaml.safe_dump({"ai": {"confidence_threshold": 7.0}}), encoding="utf-8"
        )
        cfg = load_config(str(CONFIG), learned_path=overlay)
        assert cfg["ai"]["confidence_threshold"] == 0.25

    def test_environment_still_wins_over_the_overlay(
        self, tmp_path, monkeypatch
    ) -> None:
        overlay = tmp_path / "learned.yaml"
        overlay.write_text(
            yaml.safe_dump({"ai": {"model_name": "learned.pt"}}), encoding="utf-8"
        )
        monkeypatch.setenv("AI_MODEL_NAME", "env.pt")
        cfg = load_config(str(CONFIG), learned_path=overlay)
        assert cfg["ai"]["model_name"] == "env.pt"

    def test_the_config_key_reference_rule_holds_for_autotune(self) -> None:
        # Every autotune leaf key must be read somewhere under software/.
        shipped = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        source = "\n".join(
            p.read_text(encoding="utf-8") for p in (ROOT / "software").rglob("*.py")
        )
        for key in shipped["autotune"]:
            assert f'"{key}"' in source, f"autotune.{key} is never read in software/"

    @pytest.mark.parametrize(
        ("mutation", "match"),
        [
            ({"rearm_ratio": 1.0}, "rearm_ratio"),
            ({"improve_ratio": 0.0}, "improve_ratio"),
            ({"budget_margin": 0}, "budget_margin"),
            ({"max_interval": 0}, "max_interval"),
            ({"window_s": 0}, "window_s"),
        ],
    )
    def test_out_of_range_autotune_values_are_rejected(
        self, cfg: dict[str, Any], mutation: dict[str, Any], match: str
    ) -> None:
        cfg["autotune"].update(mutation)
        with pytest.raises(ValueError, match=match):
            validate_config(cfg)

    def test_inference_interval_must_be_positive(self, cfg: dict[str, Any]) -> None:
        cfg["ai"]["inference_interval"] = 0
        with pytest.raises(ValueError, match="inference_interval"):
            validate_config(cfg)


# ------------------------------------------------------------- live pipeline
class TestLiveFeedWiring:
    def test_state_exposes_the_tuner(self, cfg: dict[str, Any]) -> None:
        feed = LiveFeed(cfg, source="mock")
        state = feed.state()
        assert state["inference_interval"] == cfg["ai"]["inference_interval"]
        block = state["autotune"]
        assert block["enabled"] is True
        assert INTERVAL_SPACE in block["params"]
        assert block["realtime"]["interval"] == state["inference_interval"]

    def test_autotune_status_is_json_serialisable(self, cfg: dict[str, Any]) -> None:
        feed = LiveFeed(cfg, source="mock")
        assert json.loads(json.dumps(feed.autotune_status()))["enabled"] is True

    def test_inference_gate_fires_every_nth_pass_including_the_first(
        self, cfg: dict[str, Any]
    ) -> None:
        feed = LiveFeed(cfg, source="mock")
        feed._infer_interval = 3
        feed._infer_seq = 2
        assert [feed._should_infer() for _ in range(7)] == [
            True,
            False,
            False,
            True,
            False,
            False,
            True,
        ]

    def test_sync_interval_adopts_the_governor_and_restarts_the_gate(
        self, cfg: dict[str, Any]
    ) -> None:
        feed = LiveFeed(cfg, source="mock")
        feed._infer_seq = 5
        feed._rt.interval = 4
        feed._sync_interval()
        assert feed._infer_interval == 4
        assert feed._infer_seq == 3  # the next pass infers

    def test_disabled_autotune_keeps_the_shipped_interval(
        self, cfg: dict[str, Any]
    ) -> None:
        cfg["autotune"] = {**cfg["autotune"], "enabled": False}
        feed = LiveFeed(cfg, source="mock")
        assert feed._rt.interval == cfg["ai"]["inference_interval"]
        assert feed.autotune_status()["enabled"] is False


# ------------------------------------------------------- offline calibration
def _fake_report(f1: float) -> dict[str, Any]:
    return {
        "operating_point": {
            "f1": f1,
            "precision": f1,
            "recall": f1,
            "duplicate_detections": 0,
        },
        "h4_realtime": {"closes_loop": True},
        "latency_ms": {"p50": 100.0},
    }


@pytest.fixture
def offline_args(tmp_path: Path) -> argparse.Namespace:
    shipped = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    shipped["autotune"]["learned_path"] = str(tmp_path / "learned.yaml")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(shipped), encoding="utf-8")
    return autotune_script.build_parser().parse_args(
        ["--config", str(config_path), "--passes", "3", "--write"]
    )


def _conf_of(overrides: list[str]) -> float:
    for entry in overrides:
        if entry.startswith("ai.confidence_threshold="):
            return float(entry.split("=", 1)[1])
    return 0.25


def _peak_at(best: float):
    """A stand-in benchmark whose best F1 sits at ``best`` on the conf dial.

    The other two dials are flat, so they must fall back to their anchors.
    """

    def measure(args, base_set, overrides):
        return _fake_report(f1=1.0 - abs(_conf_of(overrides) - best))

    return measure


class TestOfflineCalibration:
    def test_cost_is_f1_deficit_gated_on_realtime(self) -> None:
        cost, feasible = autotune_script.cost_of(_fake_report(0.8))
        assert cost == pytest.approx(0.2)
        assert feasible is True
        broken = {
            "operating_point": {"f1": 1.0},
            "h4_realtime": {"closes_loop": False},
        }
        cost, feasible = autotune_script.cost_of(broken)
        assert cost >= VIOLATION_PENALTY
        assert feasible is False

    def test_sweep_commits_the_cheapest_candidate(
        self, offline_args, monkeypatch
    ) -> None:
        monkeypatch.setattr(autotune_script, "_measure", _peak_at(0.40))
        report = autotune_script.run_autotune(offline_args)
        assert report["committed"]["ai.confidence_threshold"] == 0.40
        # dials with nothing to gain keep their shipped anchors
        assert report["committed"]["ai.min_box_px"] == 8
        assert report["committed"]["ai.iou_threshold"] == 0.5

    def test_sweep_converges_and_persists_once(self, offline_args, monkeypatch) -> None:
        monkeypatch.setattr(autotune_script, "_measure", _peak_at(0.40))
        report = autotune_script.run_autotune(offline_args)
        assert report["converged"] is True
        assert report["written"] is True
        assert report["passes"] >= 2  # the second pass is the fixed point
        assert report["changed"] == {"ai.confidence_threshold": 0.40}
        assert learned_overlay(report["learned_path"]) == {
            "ai": {"confidence_threshold": 0.40}
        }

    def test_dry_run_never_writes(self, offline_args, monkeypatch) -> None:
        monkeypatch.setattr(autotune_script, "_measure", _peak_at(0.40))
        offline_args.write = False
        report = autotune_script.run_autotune(offline_args)
        assert report["written"] is False
        assert not Path(report["learned_path"]).exists()

    def test_render_names_the_outcome(self, offline_args, monkeypatch) -> None:
        monkeypatch.setattr(autotune_script, "_measure", _peak_at(0.40))
        text = autotune_script.render(autotune_script.run_autotune(offline_args))
        assert "CONVERGED" in text
        assert "Persisted" in text
        assert "ai.confidence_threshold" in text

    def test_pass_limit_is_reported_honestly(self, offline_args, monkeypatch) -> None:
        # The optimum moves after the first sweep, so no fixed point exists
        # within the pass limit and the report must say so rather than claim
        # convergence.
        counter = {"n": 0}
        moving = _peak_at(0.15)

        def measure(args, base_set, overrides):
            counter["n"] += 1
            if counter["n"] > 9:  # every conf candidate of pass 1
                return _fake_report(f1=1.0 - abs(_conf_of(overrides) - 0.45))
            return moving(args, base_set, overrides)

        monkeypatch.setattr(autotune_script, "_measure", measure)
        offline_args.passes = 2
        offline_args.write = False
        report = autotune_script.run_autotune(offline_args)
        assert report["converged"] is False
        assert report["passes"] == 2
        assert report["committed"]["ai.confidence_threshold"] == 0.45

    def test_passes_must_be_positive(self) -> None:
        assert autotune_script.main(["--passes", "0"]) == 2

    def test_report_is_json_serialisable(self, offline_args, monkeypatch) -> None:
        monkeypatch.setattr(autotune_script, "_measure", _peak_at(0.25))
        offline_args.write = False
        report = autotune_script.run_autotune(offline_args)
        assert json.loads(json.dumps(report))["label"] == "CALIBRATED"
        assert report["changed"] == {}  # nothing better than the shipped value


# ------------------------------------------------------------------- policy
class TestSafetyIsOutOfScope:
    DIALS = (
        "safety.emergency_stop_distance_cm",
        "safety.slow_down_distance_cm",
        "safety.comm_timeout_s",
        "serial.baud_rate",
        "serial.port",
        "navigation.center_boundary",
        "ai.target_confidence",
        "rover.width_cm",
        "rover.length_cm",
    )

    @pytest.mark.parametrize("dial", DIALS)
    def test_no_tuner_can_be_given_a_safety_dial(self, dial: str) -> None:
        tuner = AutoTuner()
        tuner.add(
            SearchSpace(
                name="ai.confidence_threshold", candidates=(0.25,), default=0.25
            )
        )
        with pytest.raises(KeyError):
            tuner.seed(dial, 1)

    def test_learned_sections_exclude_the_physical_machine(self) -> None:
        assert set(LEARNED_SECTIONS) == {"ai", "camera", "plugins"}

    def test_shipped_target_confidence_is_not_a_tuner_dial(self) -> None:
        cfg = load_config(str(CONFIG))
        names = {s.name for s in detection_spaces(cfg)} | {INTERVAL_SPACE}
        assert "ai.target_confidence" not in names
