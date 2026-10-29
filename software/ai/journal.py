"""Explorer journal: Gemini narrates the journey, entry by entry, as markdown.

On power-on the journal opens a fresh file, looks at the first frame and asks
Gemini to write an opening entry that *continues* whatever the previous
session left behind. From then on it appends an entry only when something
actually changed — a new object class, a new path verdict, a new mode — and
never more often than ``explorer.interval_s``. Shutdown writes a closing
journey summary.

Three rules, matching the rest of the stack:

* ADVISORY ONLY. One Gemini call measured 6.9 s on this host (thinking off);
  the H4 realtime gate needs 0.50 s. Nothing here may sit in the control
  loop — every call runs on a background worker thread, so the pilot's 4 Hz
  tick never blocks on it.
* FAIL SOFT. No ``GEMINI_API_KEY``, or a dead network, leaves
  ``available=False`` with a reason, exactly like the CLIP explainer. The
  deck, the pilot and the safety chain are untouched.
* THE KEY NEVER ENTERS THE REPO. Read from the environment at call time,
  never from config, never written to disk.
"""

from __future__ import annotations

import base64
import contextlib
import json
import logging
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
ENV_KEY = "GEMINI_API_KEY"
MAX_FAILURES = 3  # consecutive failures before the journal goes quiet
PREV_TAIL_LINES = 40  # lines of the previous journal quoted as context
QUEUE_MAX = 4  # bounded backlog; oldest entry is dropped when full
STOP_TIMEOUT_S = 45.0  # give a closing entry time to land on shutdown

ENTRY_PROMPT = """\
You are the explorer log of a small indoor rover. You are not the driver: you
decide nothing and nothing you write reaches the control loop. Your only job
is one short journal entry for the operator, in the voice of a careful
field explorer — plain, concrete, no theatre.

You are given MEASURED facts from the rover's own sensors and, if attached,
the current camera frame. Treat the MEASURED block as ground truth. Anything
you infer from the image is an estimate: say so, and never invent a sensor
reading or a number that is not in the block.

Format:
- 55-100 words, markdown, no preamble.
- First line is a short bold headline.
- Name what is visible; give rough distances only when the facts support it.
- If the facts are thin, or the world model is degraded, say what is missing.
- Quote the pilot's command letter verbatim (F, B, L, R, S). It is a drive
  command, not a compass bearing: never restate a letter as a direction such
  as north, south, east or west.
- Close with one concrete thing worth looking at next.
"""


def _env_api_key() -> str:
    """Read the key from the environment only. Never from config, never from disk."""
    return str(os.environ.get(ENV_KEY, "") or "").strip()


def _positive(value: Any, default: float) -> float:
    """Config values arrive as YAML; never let a bad dial crash construction."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return parsed if parsed > 0 else float(default)


class GeminiClient:
    """Minimal stdlib Gemini client. Injectable so tests never touch the network."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        max_tokens: int = 700,
        *,
        post: Callable[..., tuple[int, dict]] | None = None,
    ) -> None:
        self.api_key = str(api_key)
        self.model = str(model)
        self.max_tokens = int(max_tokens)
        self._post = post
        self.backend = "gemini" if self.api_key else "none"
        self.available = bool(self.api_key)
        self.reason = "" if self.api_key else f"set {ENV_KEY} in the environment"

    # -------------------------------------------------------------- transport
    def _http_post(self, path: str, payload: dict, timeout: float) -> tuple[int, dict]:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            API_BASE + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8", "ignore"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "ignore") or "{}"
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, {"error": {"message": body[:300]}}
        except Exception as exc:
            return 0, {"error": {"message": f"{type(exc).__name__}: {exc}"}}

    # ----------------------------------------------------------------- brief
    def write_entry(
        self,
        jpeg: bytes | None,
        facts: str,
        previous: str = "",
        kind: str = "update",
        timeout: float = 40.0,
    ) -> str:
        """One narrated entry. Raises on transport failure so the caller can back off."""
        if not self.available:
            return f"unavailable: {self.reason}"
        intro = {
            "opening": "The rover has just powered on. Write the opening entry.",
            "update": "Write one update entry.",
            "closing": "The rover is shutting down. Write the closing journey summary.",
        }.get(kind, "Write one update entry.")
        prompt = f"{ENTRY_PROMPT}\n\n{intro}\n\n{facts}\n" + (
            f"\n## Where we left off (previous journal)\n{previous}\n"
            if previous
            else ""
        )
        parts: list[dict[str, Any]] = [{"text": prompt}]
        if jpeg:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": base64.b64encode(jpeg).decode("ascii"),
                    }
                }
            )
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "maxOutputTokens": self.max_tokens,
                "temperature": 0.3,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        post = self._post or self._http_post
        status, body = post(f"/models/{self.model}:generateContent", payload, timeout)
        if status != 200:
            message = (body.get("error") or {}).get("message", "")[:200]
            raise RuntimeError(f"gemini HTTP {status}: {message}")
        candidates = body.get("candidates") or [{}]
        text = "".join(
            p.get("text", "")
            for p in (candidates[0].get("content") or {}).get("parts", [])
        ).strip()
        if not text:
            raise RuntimeError(
                f"gemini returned no text (finish={candidates[0].get('finishReason')})"
            )
        return text


class ExplorerJournal:
    """Appends explorer-voice entries to ``journal.md`` in a per-session run dir."""

    def __init__(
        self,
        cfg: dict,
        feed=None,
        link=None,
        *,
        client: GeminiClient | None = None,
        now: Callable[[], float] = time.time,
    ) -> None:
        explorer = (cfg or {}).get("explorer", {})
        if not isinstance(explorer, dict):
            explorer = {}
        self.enabled = bool(explorer.get("enabled", False))
        self.interval_s = _positive(explorer.get("interval_s", 60.0), 60.0)
        self.journal_dir = str(
            explorer.get("journal_dir", "data/journal") or "data/journal"
        )
        self._feed = feed
        self._link = link
        self._now = now
        self._client = client
        self._model = str(
            explorer.get("model", "gemini-2.5-flash") or "gemini-2.5-flash"
        )
        self._max_tokens = int(_positive(explorer.get("max_tokens", 700), 700))
        self._queue: queue.Queue[tuple[str, str] | None] = queue.Queue(
            maxsize=QUEUE_MAX
        )
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._scene_sig: tuple | None = None
        self._pilot_sig: tuple | None = None
        self._last_entry_at = 0.0
        self._failures = 0
        self._entries = 0
        self._stopping = False
        self.path: Path | None = None
        self.reason = ""
        self.backend = "none"
        self.available = False
        self.entries = 0

    # ---------------------------------------------------------------- status
    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "available": self.available,
                "backend": self.backend,
                "reason": self.reason,
                "enabled": self.enabled,
                "entries": self._entries,
                "failures": self._failures,
                "path": str(self.path) if self.path else None,
                "model": self._model,
                "interval_s": self.interval_s,
            }

    def text(self) -> str:
        """Journal so far, read back from disk (single source of truth)."""
        if self.path is None or not self.path.exists():
            return ""
        try:
            return self.path.read_text(encoding="utf-8")
        except OSError:
            logger.exception("journal read failed")
            return ""

    # -------------------------------------------------------------- lifecycle
    def start(self) -> str | None:
        """Open the run dir, remember the previous journal, queue the opening entry."""
        if not self.enabled:
            self.reason = "explorer.enabled is false"
            return None
        if self._client is None:
            key = _env_api_key()
            self._client = GeminiClient(key, self._model, self._max_tokens)
        self.backend = self._client.backend
        self.available = self._client.available
        self.reason = self._client.reason
        if not self.available:
            logger.info("explorer journal off: %s", self.reason)
            return None

        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = Path(self.journal_dir)
        path = base / stamp
        suffix = 1
        while path.exists():
            path = base / f"{stamp}-{suffix}"
            suffix += 1
        try:
            path.mkdir(parents=True, exist_ok=True)
            self.path = path / "journal.md"
            previous = self._previous_tail()
            self._append(
                "# EXPLORER JOURNAL",
                "",
                f"Session opened {time.strftime('%Y-%m-%d %H:%M:%S')} · model {self._model}",
            )
        except OSError:
            logger.exception("journal dir unavailable")
            self.available = False
            self.reason = "journal dir unavailable"
            return None

        self._stopping = False
        self._thread = threading.Thread(
            target=self._worker, name="explorer-journal", daemon=True
        )
        self._thread.start()
        self._last_entry_at = self._now()
        # The opening entry already describes this scene, so don't narrate it twice.
        self._scene_sig = _scene_signature(self._world())
        self._pilot_sig = None
        self._enqueue("opening", previous)
        logger.info("explorer journal -> %s", self.path.as_posix())
        return str(self.path)

    def stop(self) -> None:
        """Queue a closing entry and let the worker drain before exit."""
        if self._thread is None:
            return
        self._stopping = True
        if self.available:
            self._enqueue("closing", "")
            deadline = time.time() + STOP_TIMEOUT_S
            while time.time() < deadline:
                if self._queue.empty():
                    break
                time.sleep(0.2)
        self._queue.put(None)
        self._thread.join(timeout=STOP_TIMEOUT_S)
        self._thread = None

    # ------------------------------------------------------------------ tick
    def tick(self, decision: Any = None) -> bool:
        """Called from the pilot's on_tick. Cheap, non-blocking, usually a no-op."""
        if not self.available or self._stopping or self._thread is None:
            return False
        now = self._now()
        world = self._world()
        scene_sig = _scene_signature(world)
        pilot_sig = _pilot_signature(decision)
        # Throttle first, then narrate only on a real change.
        if now - self._last_entry_at < self.interval_s:
            return False
        if scene_sig == self._scene_sig:
            if self._pilot_sig is None:
                # First decision after power-on: adopt it as the baseline
                # instead of narrating the mode we just powered up in.
                self._pilot_sig = pilot_sig
                return False
            if pilot_sig == self._pilot_sig:
                return False  # same scene, same pilot state: nothing to say
        self._scene_sig = scene_sig
        self._pilot_sig = pilot_sig
        self._last_entry_at = now
        self._enqueue("update", "", decision=decision, world=world)
        return True

    # -------------------------------------------------------------- internals
    def _enqueue(
        self,
        kind: str,
        previous: str = "",
        decision: Any = None,
        world: dict[str, Any] | None = None,
    ) -> None:
        if not self.available:
            return
        if self._failures >= MAX_FAILURES:
            return
        world = self._world() if world is None else world
        payload = json.dumps(
            {
                "kind": kind,
                "previous": previous,
                "decision": _decision_facts(decision),
                "world": world or {},
            }
        )
        try:
            self._queue.put_nowait((kind, payload))
        except queue.Full:
            with contextlib.suppress(queue.Empty):
                self._queue.get_nowait()
            try:
                self._queue.put_nowait((kind, payload))
            except queue.Full:
                logger.warning("journal queue full; entry dropped")

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                return
            kind, payload = item
            try:
                data = json.loads(payload)
                self._write_entry(kind, data)
            except Exception:
                logger.exception("journal entry failed")
                self._failures += 1
                if self._failures >= MAX_FAILURES:
                    logger.warning(
                        "explorer journal going quiet after %d failures", self._failures
                    )
            finally:
                self._queue.task_done()

    def _write_entry(self, kind: str, data: dict[str, Any]) -> None:
        if self.path is None:
            return
        facts = _facts_block(
            data.get("decision") or {}, data.get("world") or {}, self._link
        )
        jpeg = self._jpeg()
        text = self._client.write_entry(
            jpeg, facts, previous=str(data.get("previous") or ""), kind=kind
        )
        stamp = time.strftime("%H:%M:%S")
        headline = text.splitlines()[0].strip().strip("*# ").strip() if text else kind
        body = text.splitlines()[1:] if text else []
        self._append(
            "",
            f"## [{stamp}] {headline}",
            "",
            *body,
        )
        self._entries += 1
        self.entries = self._entries
        self._failures = 0
        logger.info("journal entry (%s): %s", kind, headline[:80])

    def _append(self, *lines: str) -> None:
        if self.path is None:
            return
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
            handle.flush()

    def _jpeg(self, max_side: int = 640) -> bytes | None:
        """Current frame as JPEG, downscaled so the upload stays cheap."""
        if self._feed is None:
            return None
        try:
            frame, _ = self._feed.snapshot()
        except Exception:
            return None
        if frame is None:
            return None
        try:
            import cv2

            image = frame
            height, width = image.shape[:2]
            longest = max(height, width)
            if longest > max_side:
                scale = max_side / longest
                image = cv2.resize(
                    image,
                    (int(width * scale), int(height * scale)),
                    interpolation=cv2.INTER_AREA,
                )
            ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 72])
            return bytes(buf) if ok else None
        except Exception:
            logger.exception("journal frame encode failed")
            return None

    def _world(self) -> dict[str, Any]:
        if self._feed is None:
            return {}
        try:
            state = self._feed.state() or {}
        except Exception:
            return {}
        world = state.get("world")
        if isinstance(world, dict):
            return world
        return state

    def _previous_tail(self) -> str:
        """Last lines of the most recent journal on disk, for continuity across power cycles."""
        base = Path(self.journal_dir)
        if not base.exists():
            return ""
        candidates = sorted(base.glob("*/journal.md"))
        if not candidates:
            return ""
        try:
            lines = candidates[-1].read_text(encoding="utf-8").splitlines()
        except OSError:
            return ""
        return "\n".join(lines[-PREV_TAIL_LINES:])


# ------------------------------------------------------------------ helpers
def _scene_signature(world: dict[str, Any]) -> tuple:
    """Cheap fingerprint of what is visible — changed scene means a new entry."""
    labels = sorted(
        {
            str(o.get("label") or o.get("class_name") or "")
            for o in (world.get("objects") or [])
            if isinstance(o, dict)
        }
        - {""}
    )
    return (
        tuple(labels),
        str(world.get("path_state") or ""),
        bool(world.get("degraded")),
        bool(world.get("target_present")),
    )


def _pilot_signature(decision: Any) -> tuple:
    """Cheap fingerprint of the pilot's state (mode + command)."""
    if hasattr(decision, "to_dict"):
        decision = decision.to_dict()
    if not isinstance(decision, dict):
        return ("", "")
    return (str(decision.get("mode") or ""), str(decision.get("command") or ""))


def _decision_facts(decision: Any) -> dict[str, Any]:
    if decision is None:
        return {}
    if hasattr(decision, "to_dict"):
        decision = decision.to_dict()
    if not isinstance(decision, dict):
        return {}
    keep = (
        "mode",
        "command",
        "armed",
        "safety_reason",
        "steering_reason",
        "distance_cm",
        "target",
        "confidence",
        "zone",
        "target_present",
    )
    return {k: decision.get(k) for k in keep if k in decision}


def _facts_block(
    decision: dict[str, Any], world: dict[str, Any], link: Any = None
) -> str:
    """Ground the model in measured numbers so it cannot invent them."""
    lines = ["## MEASURED (ground truth from the rover's own sensors)"]
    if decision:
        lines.append(
            f"- pilot: mode={decision.get('mode', '?')} command={decision.get('command', '?')} "
            f"armed={decision.get('armed', '?')}"
        )
        if decision.get("safety_reason"):
            lines.append(f"- safety: {decision.get('safety_reason')}")
        if decision.get("distance_cm") is not None:
            lines.append(f"- ultrasonic: {decision.get('distance_cm')} cm")
        if decision.get("target"):
            lines.append(
                f"- target: {decision.get('target')} conf={decision.get('confidence')}"
            )
    if link is not None:
        try:
            telemetry = link.telemetry() or {}
        except Exception:
            telemetry = {}
        if telemetry.get("distance_cm") is not None:
            lines.append(f"- ultrasonic: {telemetry.get('distance_cm')} cm")
        if telemetry.get("battery"):
            lines.append(f"- battery: {telemetry.get('battery')}")
    scene = str(world.get("scene") or "")
    if scene:
        lines.append(f"- scene: {scene}")
    objects = world.get("objects") or []
    for obj in objects[:6]:
        if not isinstance(obj, dict):
            continue
        name = obj.get("label") or obj.get("class_name") or "?"
        conf = obj.get("confidence")
        rng = obj.get("range_m")
        parts = [str(name)]
        if conf is not None:
            parts.append(f"conf {float(conf):.2f}")
        if rng is not None:
            parts.append(f"range {float(rng):.2f} m")
        lines.append(f"- detected: {' '.join(parts)}")
    if not objects:
        lines.append("- detected: nothing")
    facts = world.get("facts") or []
    for fact in facts[:5]:
        lines.append(f"- world: {fact}")
    path_state = str(world.get("path_state") or "unknown")
    lines.append(f"- path verdict: {path_state}")
    if world.get("degraded"):
        lines.append("- NOTE: the world model reports DEGRADED (ranges are untrusted)")
    return "\n".join(lines)


def create_journal(cfg: dict, feed=None, link=None, **kwargs) -> ExplorerJournal:
    """Build from ``explorer:`` config; never raises — unavailable carries a reason."""
    journal = ExplorerJournal(cfg, feed, link, **kwargs)
    return journal
