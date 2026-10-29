"""Mission run capture: decisions.csv + annotated frames + summary.json.

While recording, every pilot tick appends a CSV row (the why-chain, motors,
distance, verdicts) and an annotated JPEG is written when something *changes*:

  * the final command changed (decision change)
  * dashboard.record_every_s elapsed (periodic heartbeat frame)
  * a fresh firmware ALERT arrived
  * run start / stop bookkeeping, capped at MAX_FRAMES images

Each run lives in ``<dashboard.record_dir>/<ISO timestamp>/``. The dashboard
toggles it live via POST /api/recording and lists events via /api/events.
"""

from __future__ import annotations

import contextlib
import csv
import json
import logging
import threading
import time
from collections import Counter, deque
from pathlib import Path
from typing import Any

from software.dashboard.report import build_report

logger = logging.getLogger(__name__)

MAX_FRAMES = 500
MAX_EVENTS = 120

FIELDS = (
    "at",
    "mode",
    "armed",
    "proposed",
    "command",
    "allowed",
    "steering_reason",
    "safety_reason",
    "blockers",
    "distance_cm",
    "target",
    "confidence",
    "area_ratio",
    "zone",
    "target_present",
    "sent",
    "motor_left",
    "motor_right",
    "overlay",
)


def _row_from(decision: Any) -> dict[str, Any]:
    """Normalise DecisionRecord / dict / mapping-like into one CSV row."""
    data = decision.to_dict() if hasattr(decision, "to_dict") else dict(decision)
    motors = list(data.get("motors") or [0, 0])
    return {
        "at": data.get("at", 0.0),
        "mode": data.get("mode", ""),
        "armed": bool(data.get("armed", False)),
        "proposed": data.get("proposed", ""),
        "command": data.get("command", "S"),
        "allowed": bool(data.get("allowed", False)),
        "steering_reason": data.get("steering_reason", ""),
        "safety_reason": data.get("safety_reason", ""),
        "blockers": "|".join(data.get("blockers") or ()),
        "distance_cm": data.get("distance_cm"),
        "target": data.get("target") or "",
        "confidence": data.get("confidence", 0.0),
        "area_ratio": data.get("area_ratio", 0.0),
        "zone": data.get("zone") or "",
        "target_present": bool(data.get("target_present", False)),
        "sent": data.get("sent") or "",
        "motor_left": int(motors[0]) if len(motors) > 0 else 0,
        "motor_right": int(motors[1]) if len(motors) > 1 else 0,
        "overlay": data.get("overlay", ""),
    }


class RunRecorder:
    """Toggleable capture of the decision chain + annotated video stills."""

    def __init__(self, cfg: dict, feed=None, pilot=None, link=None) -> None:
        dashboard_cfg = cfg.get("dashboard", {})
        self.record_dir = str(dashboard_cfg.get("record_dir", "data/runs"))
        self.every_s = float(dashboard_cfg.get("record_every_s", 1.0))
        self._feed = feed
        self._pilot = pilot
        self._link = link
        self._lock = threading.Lock()
        self.recording = False
        self.run_path: Path | None = None
        self.frames = 0
        self.rows = 0
        self._started_at: float = 0.0
        self._csv_file = None
        self._writer = None
        self._last_command: str | None = None
        self._last_image_at = 0.0
        self._last_alert_at = 0.0
        self._cap_noted = False
        self._commands: Counter[str] = Counter()
        self._modes: Counter[str] = Counter()
        self._last_world: dict[str, Any] = {}
        self._duration_s = 0.0
        self.events: deque[str] = deque(maxlen=MAX_EVENTS)

    # ------------------------------------------------------------- toggle
    def start(self) -> str:
        """Open a fresh run directory. Idempotent while already recording."""
        with self._lock:
            if self.recording:
                return str(self.run_path)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            base = Path(self.record_dir)
            path = base / stamp
            suffix = 1
            while path.exists():
                path = base / f"{stamp}-{suffix}"
                suffix += 1
            path.mkdir(parents=True, exist_ok=True)
            self._csv_file = (path / "decisions.csv").open(
                "w", newline="", encoding="utf-8"
            )
            self._writer = csv.DictWriter(self._csv_file, fieldnames=FIELDS)
            self._writer.writeheader()
            self._csv_file.flush()
            self.run_path = path
            self.recording = True
            self.frames = 0
            self.rows = 0
            self._started_at = time.time()
            self._last_command = None
            self._last_image_at = 0.0
            self._last_alert_at = 0.0
            self._cap_noted = False
            self._commands = Counter()
            self._modes = Counter()
            self._last_world = {}
            self.events.clear()
            self._event(f"START recording -> {path.as_posix()}")
            return str(path)

    def stop(self) -> None:
        """Close the run and write summary.json. Idempotent."""
        with self._lock:
            if not self.recording:
                return
            self.recording = False
            self._duration_s = round(time.time() - self._started_at, 1)
            summary = {
                "path": str(self.run_path),
                "started_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime(self._started_at)
                ),
                "stopped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "duration_s": self._duration_s,
                "images": self.frames,
                "decisions": self.rows,
                "commands": dict(self._commands),
                "events": list(self.events),
            }
            self._event("STOP recording")
            summary["events"] = list(self.events)
            summary["modes"] = dict(self._modes)
            if self.run_path is not None:
                try:
                    (self.run_path / "summary.json").write_text(
                        json.dumps(summary, indent=2), encoding="utf-8"
                    )
                except OSError:
                    logger.exception("could not write summary.json")
                try:
                    report = build_report(
                        duration_s=summary["duration_s"],
                        decisions=self.rows,
                        images=self.frames,
                        commands=dict(self._commands),
                        events=list(self.events),
                        world=self._last_world,
                        mode_mix=dict(self._modes),
                        path=str(self.run_path),
                    )
                    (self.run_path / "report.md").write_text(report, encoding="utf-8")
                except OSError:
                    logger.exception("could not write report.md")
            if self._csv_file is not None:
                with contextlib.suppress(OSError):
                    self._csv_file.close()
                self._csv_file = None
                self._writer = None

    # -------------------------------------------------------------- write
    def record(self, decision: Any, *, now: float | None = None) -> bool:
        """Append one CSV row; snapshot a frame when something changed.

        Safe to call from the pilot tick thread while start/stop happens on the
        web thread: everything shares one lock and returns quietly when idle.
        """
        now = time.time() if now is None else now
        with self._lock:
            if not self.recording or self._writer is None:
                return False
            row = _row_from(decision)
            try:
                self._writer.writerow(row)
                self._csv_file.flush()
            except (OSError, ValueError):
                logger.exception("decisions.csv write failed")
                return False
            self.rows += 1
            self._commands[str(row["command"])] += 1
            if row["mode"]:
                self._modes[str(row["mode"])] += 1
            if self._feed is not None:
                try:
                    world = (self._feed.state() or {}).get("world") or {}
                except Exception:
                    world = {}
                if world.get("objects"):
                    self._last_world = dict(world)

            alert_at = 0.0
            if self._link is not None:
                try:
                    alert_at = float(self._link.telemetry().get("alert_at", 0.0) or 0.0)
                except Exception:
                    alert_at = 0.0
            command = str(row["command"])
            prev = self._last_command
            changed = prev is not None and command != prev
            first = prev is None
            periodic = now - self._last_image_at >= self.every_s
            alert = alert_at > 0 and alert_at > self._last_alert_at
            self._last_command = command
            self._last_alert_at = max(self._last_alert_at, alert_at)

            if not (first or changed or periodic or alert):
                return True
            if not changed and not first and not alert:
                self._last_image_at = now
            if self.frames >= MAX_FRAMES:
                if not self._cap_noted:
                    self._cap_noted = True
                    self._event(f"frame cap reached ({MAX_FRAMES}); still logging CSV")
                return True
            saved = self._save_frame(row, now)
            if saved:
                self.frames += 1
                if first:
                    self._event(f"run start: command {command}")
                elif changed:
                    self._event(f"command {prev} -> {command}: {row['safety_reason']}")
                if alert:
                    self._event("ALERT captured")
            return True

    def status(self, limit: int = 50) -> dict[str, Any]:
        with self._lock:
            duration = (
                time.time() - self._started_at if self.recording else self._duration_s
            )
            return {
                "recording": self.recording,
                "path": str(self.run_path) if self.run_path else None,
                "frames": self.frames,
                "decisions": self.rows,
                "dir": self.record_dir,
                "duration_s": round(max(0.0, duration), 1),
                "commands": dict(self._commands),
                "modes": dict(self._modes),
                "events": list(self.events)[-max(1, int(limit)) :],
            }

    def last_world(self) -> dict[str, Any]:
        """Most recent non-empty world snapshot seen while recording."""
        with self._lock:
            return dict(self._last_world)

    # ------------------------------------------------------------ internal
    def _event(self, message: str) -> None:
        self.events.append(f"{time.strftime('%H:%M:%S')} {message}")

    def _save_frame(self, row: dict[str, Any], now: float) -> bool:
        if self._feed is None or self.run_path is None:
            return False
        try:
            frame, dets = self._feed.snapshot()
        except Exception:
            return False
        if frame is None:
            return False
        try:
            import cv2

            image = frame.copy()
            for d in dets or []:
                cv2.rectangle(
                    image,
                    (int(d["x1"]), int(d["y1"])),
                    (int(d["x2"]), int(d["y2"])),
                    (0, 255, 0),
                    2,
                )
                cv2.putText(
                    image,
                    f"{d.get('class_name', '')} {float(d.get('confidence', 0)):.2f}",
                    (int(d["x1"]), max(12, int(d["y1"]) - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                )
            self._banner(image, row)
            name = f"frame_{self.frames:06d}.jpg"
            ok, buf = cv2.imencode(".jpg", image)
            if not ok:
                return False
            (self.run_path / name).write_bytes(bytes(buf))
            self._last_image_at = now
            return True
        except Exception:
            logger.exception("frame capture failed")
            return False

    @staticmethod
    def _banner(image, row: dict[str, Any]) -> None:
        import cv2

        h, w = image.shape[:2]
        strip = min(46, max(24, h // 9))
        cv2.rectangle(image, (0, 0), (w, strip), (0, 0, 0), -1)
        text = (
            f"{str(row.get('overlay', '')).upper()}  |  "
            f"{row.get('mode', '')} {row.get('command', '')} "
            f"L{row.get('motor_left', 0)} R{row.get('motor_right', 0)}  |  "
            f"{row.get('safety_reason', '')}"
        )
        cv2.putText(
            image,
            text[: max(10, w // 7)],
            (6, strip - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (60, 255, 60),
            1,
        )
