"""Closed loop: camera -> YOLO -> three-zone policy -> HTTP -> ESP32 -> Uno.

Two safety rules live here, not in the policy:

1. **Heartbeat.**  The Uno stops after 500 ms of silence, so the pilot re-sends
   the current decision every ``heartbeat_s`` (default 0.2 s) even when the
   decision did not change.
2. **Stale camera failsafe.**  If the phone stops streaming, the pilot sends a
   single STOP and goes silent.  It never keeps driving on a frozen frame.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from .protocol import ProtocolError
from .steering import Decision, ZoneSteering


@dataclass
class PilotConfig:
    max_fps: float = 8.0
    heartbeat_s: float = 0.2
    max_frame_age_s: float = 1.5
    log_every: int = 0  # 0 = only on change
    dry_run: bool = False
    stop_on_exit: bool = True

    def __post_init__(self) -> None:
        if self.max_fps <= 0:
            raise ProtocolError("max_fps must be positive")
        if not 0.05 <= self.heartbeat_s <= 0.45:
            raise ProtocolError("heartbeat_s must be 0.05..0.45 (Uno watchdog is 0.5 s)")
        if self.max_frame_age_s <= 0:
            raise ProtocolError("max_frame_age_s must be positive")


@dataclass
class PilotStats:
    frames: int = 0
    detections: int = 0
    commands_sent: int = 0
    command_failures: int = 0
    stale_events: int = 0
    last_cmd: str = "S"
    last_reason: str = ""
    started_at: float = 0.0

    def as_dict(self) -> dict:
        return {
            "frames": self.frames,
            "detections": self.detections,
            "commands_sent": self.commands_sent,
            "command_failures": self.command_failures,
            "stale_events": self.stale_events,
            "last_cmd": self.last_cmd,
            "last_reason": self.last_reason,
        }


class VisionPilot:
    """Drives one rover from one camera stream."""

    def __init__(
        self,
        source,
        detector,
        steering: ZoneSteering | None = None,
        client=None,
        config: PilotConfig | None = None,
        logger: Callable[[str], None] = print,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.source = source
        self.detector = detector
        self.steering = steering or ZoneSteering()
        self.client = client
        self.config = config or PilotConfig()
        self.log = logger
        self._clock = clock
        self._sleep = sleep
        self.stats = PilotStats(started_at=clock())
        self.last_decision: Decision | None = None
        self.last_detections: list = []
        self._last_sent: tuple[str, int | None] | None = None
        self._last_send_at = 0.0
        self._last_logged: tuple[str, str, str] | None = None
        self._stale = False

    # -- one iteration -----------------------------------------------------
    def step(self) -> Decision | None:
        frame = self.source.read(max_age=self.config.max_frame_age_s)
        if frame is None:
            self._handle_stale()
            return None

        if self._stale:
            self._stale = False
            self.log("[PILOT] camera recovered")

        image = frame.image
        height, width = image.shape[0], image.shape[1]
        detections = self.detector.detect(image)
        decision = self.steering.decide(detections, width, height, now=self._clock())

        self.last_detections = detections
        self.stats.frames += 1
        self.stats.detections += len(detections)
        self.stats.last_cmd = decision.cmd
        self.stats.last_reason = decision.reason
        self.last_decision = decision

        if self.config.log_every and (self.stats.frames % self.config.log_every == 0):
            self.log(self.describe(decision, width, height, len(detections)))
        elif not self._same_as_previous(decision):
            self.log(self.describe(decision, width, height, len(detections)))

        self._send(decision)
        return decision

    def _same_as_previous(self, decision: Decision) -> bool:
        # Log on command/zone changes only. The reason string contains a live
        # centroid, so including it would print every frame.
        previous = self._last_logged
        self._last_logged = (decision.cmd, decision.zone)
        return previous == self._last_logged

    def _send(self, decision: Decision) -> None:
        if self.client is None or self.config.dry_run:
            return
        now = self._clock()
        key = (decision.cmd, decision.speed)
        due = self._last_sent is None or key != self._last_sent
        heartbeat = (now - self._last_send_at) >= self.config.heartbeat_s
        if not (due or heartbeat):
            return
        ok = self.client.send(decision.cmd, decision.speed)
        self._last_sent = key
        self._last_send_at = now
        self.stats.commands_sent += 1
        if not ok:
            self.stats.command_failures += 1
            self.log(f"[PILOT] send failed cmd={decision.cmd}")

    def _handle_stale(self) -> None:
        if self._stale:
            return
        self._stale = True
        self.stats.stale_events += 1
        self.log("[PILOT] camera stale -> STOP (failsafe)")
        if self.client is not None and not self.config.dry_run:
            self.client.stop(attempts=2)

    # -- loop --------------------------------------------------------------
    def run(self, max_frames: int | None = None) -> PilotStats:
        period = 1.0 / self.config.max_fps
        next_at = self._clock()
        iterations = 0
        while max_frames is None or iterations < max_frames:
            iterations += 1
            try:
                self.step()
            except ProtocolError as exc:
                self.log(f"[PILOT] protocol error: {exc}")
            except Exception as exc:  # keep the rover alive on unexpected model errors
                self.log(f"[PILOT] error: {exc}")
            next_at += period
            delay = next_at - self._clock()
            if delay > 0:
                self._sleep(delay)
            else:
                next_at = self._clock()
        self.shutdown()
        return self.stats

    def shutdown(self) -> None:
        if self.config.stop_on_exit and self.client is not None and not self.config.dry_run:
            self.client.stop(attempts=3)
            self.log("[PILOT] shutdown STOP")

    # -- reporting ---------------------------------------------------------
    def describe(self, decision: Decision, width: int, height: int, count: int) -> str:
        return (
            f"[PILOT] {width}x{height} det={count} obj={decision.target.cls if decision.target else '-'} "
            f"zone={decision.zone} area={decision.area_ratio:.1%} -> {decision.cmd}"
            f"{'' if decision.speed is None else f'{decision.speed}'} ({decision.reason})"
        )
