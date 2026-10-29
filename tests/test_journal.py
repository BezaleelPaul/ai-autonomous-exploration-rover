"""Explorer journal: fail-soft wiring, throttle, continuity, measured facts.

No test here may reach the network — every GeminiClient is either key-less
(unavailable by design) or built with an injected transport.
"""

from __future__ import annotations

import time

import pytest

from software.ai.journal import (
    ENTRY_PROMPT,
    ENV_KEY,
    MAX_FAILURES,
    ExplorerJournal,
    GeminiClient,
    _facts_block,
    create_journal,
)


class FakeClient:
    """Stands in for GeminiClient; records every entry request."""

    def __init__(
        self, text: str = "**Headline**\n\nBody of the entry.", fail: bool = False
    ):
        self.calls: list[dict] = []
        self.text = text
        self.fail = fail
        self.backend = "gemini"
        self.available = True
        self.reason = ""

    def write_entry(self, jpeg, facts, previous="", kind="update", timeout=40.0):
        self.calls.append(
            {"jpeg": jpeg, "facts": facts, "previous": previous, "kind": kind}
        )
        if self.fail:
            raise RuntimeError("gemini HTTP 500: boom")
        return self.text


class FakeFeed:
    """Minimal LiveFeed stand-in: state() plus a snapshot() for the JPEG."""

    def __init__(self, state: dict | None = None, frame=None):
        self._state = state or {}
        self._frame = frame

    def state(self):
        return self._state

    def snapshot(self):
        return self._frame, []


def _drain(journal: ExplorerJournal, timeout: float = 5.0) -> None:
    """Block until the worker has finished every queued entry."""
    import threading

    done = threading.Event()
    threading.Thread(
        target=lambda: (journal._queue.join(), done.set()), daemon=True
    ).start()
    assert done.wait(timeout), "journal worker did not drain in time"


def _cfg(tmp_path, **explorer) -> dict:
    base = {
        "enabled": True,
        "interval_s": 60.0,
        "model": "gemini-2.5-flash",
        "max_tokens": 700,
        "journal_dir": str(tmp_path / "journal"),
    }
    base.update(explorer)
    return {"explorer": base}


# ------------------------------------------------------------------ fail-soft
def test_no_key_is_fail_soft(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    journal = ExplorerJournal(_cfg(tmp_path))
    journal.start()

    assert journal.available is False
    assert ENV_KEY in journal.reason
    assert journal.start() is None
    assert journal.tick() is False
    journal.stop()  # must not raise
    assert not (tmp_path / "journal").exists()


def test_disabled_by_config_never_opens_a_run(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_KEY, "not-a-real-key")
    journal = ExplorerJournal(_cfg(tmp_path, enabled=False))
    assert journal.start() is None
    assert journal.available is False
    assert "enabled" in journal.reason
    assert not (tmp_path / "journal").exists()


def test_create_journal_never_raises_on_garbage_config(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    for cfg in (
        {},
        {"explorer": None},
        {"explorer": "nope"},
        {"explorer": {"interval_s": "x"}},
    ):
        journal = create_journal(cfg)
        assert journal.available is False
        journal.stop()


def test_client_without_key_reports_unavailable(monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    client = GeminiClient("")
    assert client.available is False
    assert ENV_KEY in client.reason
    assert client.write_entry(None, "facts").startswith("unavailable")


# ------------------------------------------------------------------ lifecycle
def test_start_writes_header_and_opening_entry(tmp_path):
    client = FakeClient()
    journal = ExplorerJournal(_cfg(tmp_path), client=client)
    path = journal.start()
    _drain(journal)
    journal.stop()

    assert path and path.endswith("journal.md")
    text = (tmp_path / "journal").glob("*/journal.md")
    content = next(text).read_text(encoding="utf-8")
    assert "# EXPLORER JOURNAL" in content
    assert "Headline" in content
    assert [c["kind"] for c in client.calls] == ["opening", "closing"]


def test_opening_entry_continues_the_previous_journal(tmp_path):
    older = tmp_path / "journal" / "20200101-000000"
    older.mkdir(parents=True)
    (older / "journal.md").write_text(
        "# EXPLORER JOURNAL\n\n## [10:00:00] Left off facing a blue doorway\n",
        encoding="utf-8",
    )
    client = FakeClient()
    journal = ExplorerJournal(_cfg(tmp_path), client=client)
    journal.start()
    _drain(journal)
    journal.stop()

    opening = next(c for c in client.calls if c["kind"] == "opening")
    assert "blue doorway" in opening["previous"]


def test_entries_are_timestamped_markdown(tmp_path):
    import re

    client = FakeClient()
    journal = ExplorerJournal(_cfg(tmp_path), client=client)
    journal.start()
    _drain(journal)
    journal.stop()

    content = next((tmp_path / "journal").glob("*/journal.md")).read_text(
        encoding="utf-8"
    )
    assert re.search(r"^## \[\d{2}:\d{2}:\d{2}\] ", content, re.MULTILINE)


# -------------------------------------------------------------------- ticking
def test_tick_respects_the_interval(tmp_path):
    clock = [1_000_000.0]
    client = FakeClient()
    feed = FakeFeed({"objects": [{"label": "bottle", "confidence": 0.9}]})
    journal = ExplorerJournal(
        _cfg(tmp_path), client=client, feed=feed, now=lambda: clock[0]
    )
    journal.start()
    _drain(journal)
    calls = len(client.calls)

    # Same scene, inside the throttle window: the opening entry just landed.
    assert journal.tick({"mode": "manual", "command": "S"}) is False
    _drain(journal)
    assert len(client.calls) == calls

    # Past the window, still the same scene fingerprint: nothing to say.
    clock[0] += 120.0
    assert journal.tick({"mode": "manual", "command": "S"}) is False
    _drain(journal)
    assert len(client.calls) == calls

    journal.stop()


def test_tick_fires_on_a_changed_scene(tmp_path):
    clock = [1_000_000.0]
    state = {"objects": [{"label": "bottle", "confidence": 0.9}], "path_state": "clear"}
    client = FakeClient()
    feed = FakeFeed(state)
    journal = ExplorerJournal(
        _cfg(tmp_path), client=client, feed=feed, now=lambda: clock[0]
    )
    journal.start()
    _drain(journal)
    calls = len(client.calls)

    state["objects"] = [{"label": "person", "confidence": 0.8}]
    clock[0] += 120.0
    assert journal.tick({"mode": "manual", "command": "S"}) is True
    _drain(journal)
    assert len(client.calls) == calls + 1
    assert client.calls[-1]["kind"] == "update"

    journal.stop()


def test_tick_leaves_the_pilot_alone_when_unavailable(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    journal = ExplorerJournal(_cfg(tmp_path), feed=FakeFeed({"objects": []}))
    journal.start()
    started = time.time()
    assert journal.tick({"mode": "auto", "command": "F"}) is False
    assert time.time() - started < 0.5  # non-blocking by construction
    journal.stop()


# ------------------------------------------------------------------- backing off
def test_repeated_failures_put_the_journal_to_sleep(tmp_path):
    client = FakeClient(fail=True)
    clock = [1_000_000.0]
    state = {"objects": [{"label": "bottle"}]}
    journal = ExplorerJournal(
        _cfg(tmp_path), client=client, feed=FakeFeed(state), now=lambda: clock[0]
    )
    journal.start()
    _drain(journal)

    for step in range(1, MAX_FAILURES + 4):
        clock[0] += 120.0
        state["objects"] = [{"label": f"thing{step}"}]
        journal.tick({"mode": "manual", "command": "S"})
        _drain(journal)

    # The opening plus at most MAX_FAILURES retries: no unbounded retry storm.
    assert len(client.calls) <= MAX_FAILURES + 1
    assert journal.status()["failures"] >= MAX_FAILURES
    journal.stop()


# --------------------------------------------------------------------- facts
def test_facts_block_reports_measured_numbers_only():
    decision = {
        "mode": "auto",
        "command": "F",
        "armed": True,
        "distance_cm": 42.0,
        "target": "bottle",
        "confidence": 0.77,
        "safety_reason": "",
    }
    world = {
        "scene": "indoor room",
        "path_state": "clear",
        "objects": [{"label": "bottle", "confidence": 0.9, "range_m": 1.2}],
        "facts": ["bottle near"],
        "degraded": True,
    }
    text = _facts_block(decision, world)

    assert "MEASURED" in text
    assert "ultrasonic: 42.0 cm" in text
    assert "detected: bottle conf 0.90 range 1.20 m" in text
    assert "path verdict: clear" in text
    assert "DEGRADED" in text
    assert "target: bottle conf=0.77" in text


def test_facts_block_survives_thin_world_models():
    assert "MEASURED" in _facts_block({}, {})
    assert "detected: nothing" in _facts_block({}, {"objects": []})
    # Degraded world models still produce a coherent block.
    text = _facts_block({}, {"degraded": True, "path_state": "blocked"})
    assert "blocked" in text


def test_prompt_keeps_commands_verbatim_not_compass_directions():
    # Observed live: command=F was narrated as "commanded to move South".
    assert "verbatim" in ENTRY_PROMPT
    assert "compass" in ENTRY_PROMPT


def test_status_exposes_what_the_deck_needs(tmp_path):
    client = FakeClient()
    journal = ExplorerJournal(_cfg(tmp_path), client=client)
    status = journal.status()
    for key in (
        "available",
        "backend",
        "reason",
        "enabled",
        "entries",
        "path",
        "model",
    ):
        assert key in status
    assert status["enabled"] is True
    assert status["model"] == "gemini-2.5-flash"


# ------------------------------------------------------------------- transport
def test_client_parses_a_good_response_via_injected_transport():
    def post(path, payload, timeout):
        assert path.endswith(":generateContent")
        assert payload["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}
        return 200, {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": "  **Seen**\nok  "}]},
                }
            ]
        }

    client = GeminiClient("k", post=post)
    assert client.write_entry(None, "facts") == "**Seen**\nok"


def test_client_raises_on_http_errors_so_the_journal_can_back_off():
    def post(path, payload, timeout):
        return 500, {"error": {"message": "quota"}}

    client = GeminiClient("k", post=post)
    with pytest.raises(RuntimeError, match="500"):
        client.write_entry(None, "facts")


def test_client_raises_on_an_empty_completion():
    def post(path, payload, timeout):
        return 200, {"candidates": [{"finishReason": "SAFETY"}]}

    client = GeminiClient("k", post=post)
    with pytest.raises(RuntimeError, match="no text"):
        client.write_entry(None, "facts")
