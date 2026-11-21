"""Mission pilot: the deck's MANUAL / AUTO / OBSERVE decision chain.

One tick reads the newest frame plus Arduino telemetry, runs the shared
``SteeringPolicy`` (what the perception node uses) and the shared
``SafetyManager`` (every autonomous movement passes through it), then — only in
AUTO, and only while strictly armed — writes the gated command through the same
USB link the pad uses.

Strict arming, re-checked every tick (all must hold):
  * live serial link            (safety.require_serial_for_auto)
  * fresh AI on a live frame    (safety.require_camera_for_auto)
  * no firmware alert inside the comm window

Losing any one disarms immediately and parks the rover with ``S``. MANUAL
leaves the link to the pad; OBSERVE runs the chain dry so the why-panel shows
what AUTO would do without touching the motors.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any

from software.ai.detection import Detection
from software.control.command_emitter import CommandEmitter
from software.dashboard.explore import Explorer
from software.perception_node.node import policy_from_config
from software.perception_node.zones import STOP, best_target
from software.safety.safety_manager import SafetyManager

logger = logging.getLogger(__name__)

MODES: tuple[str, ...] = ("manual", "auto", "observe", "explore")
BLOCKED_OVERLAY = "BLOCKED {cm:.0f} cm"
TIMEOUT_OVERLAY = "TIMEOUT"


@dataclass(frozen=True)
class DecisionRecord:
    """One tick of the why-chain (JSON-serialisable; the deck renders these)."""

    at: float
    mode: str
    armed: bool
    proposed: str
    command: str
    allowed: bool
    steering_reason: str
    safety_reason: str
    blockers: tuple[str, ...]
    distance_cm: float | None
    target: str | None
    confidence: float
    area_ratio: float
    zone: str | None
    target_present: bool
    sent: str | None
    motors: tuple[int, int]
    overlay: str

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["blockers"] = list(self.blockers)
        out["motors"] = list(self.motors)
        return out


def motors_for(command: str, pwm: int) -> tuple[int, int]:
    """Tank-steer motor panel: (left, right) signed PWM for one command."""
    if command == "F":
        return (pwm, pwm)
    if command == "B":
        return (-pwm, -pwm)
    if command == "L":
        return (-pwm, pwm)
    if command == "R":
        return (pwm, -pwm)
    return (0, 0)


def overlay_for(
    mode: str,
    command: str,
    safety_reason: str,
    blockers: tuple[str, ...],
    emergency_cm: float,
    pwm: int,
) -> str:
    """Big status word for the deck: why the wheels are (not) turning."""
    if blockers and mode in ("auto", "explore"):
        return f"DISARMED: {blockers[0]}"
    if safety_reason in ("EMERGENCY_OBSTACLE", "EMERGENCY_LATCH"):
        return BLOCKED_OVERLAY.format(cm=emergency_cm)
    if safety_reason == "COMM_LOST":
        return TIMEOUT_OVERLAY
    if safety_reason == "CAMERA_UNHEALTHY":
        return "STOP: CAMERA"
    if safety_reason == "LOW_CONFIDENCE":
        return "STOP: AI"
    if mode == "observe":
        return f"WOULD {command}" if command != STOP else "WOULD STOP"
    if command in ("F", "B"):
        return f"GO {pwm} PWM"
    if command in ("L", "R"):
        return "TURN"
    return "STOP"


def _detection_from(raw: dict[str, Any]) -> Detection:
    """Rebuild a Detection from ``LiveFeed.snapshot()``'s plain dict."""
    return Detection(
        class_name=str(raw.get("class_name", "")),
        confidence=float(raw.get("confidence", 0.0) or 0.0),
        x1=float(raw.get("x1", 0.0) or 0.0),
        y1=float(raw.get("y1", 0.0) or 0.0),
        x2=float(raw.get("x2", 0.0) or 0.0),
        y2=float(raw.get("y2", 0.0) or 0.0),
        track_id=raw.get("track_id"),
    )


class MissionPilot:
    """Decision chain + strict AUTO gate for the rover mission deck."""

    def __init__(
        self, cfg: dict, feed, link, *, target: str | None = None, on_tick=None
    ) -> None:
        ai = cfg.get("ai", {})
        camera = cfg.get("camera", {})
        perception = cfg.get("perception", {})
        rover = cfg.get("rover", {})
        safety_cfg = cfg.get("safety", {})
        dashboard_cfg = cfg.get("dashboard", {})
        self._feed = feed
        self._link = link
        self._on_tick = on_tick
        self.target = str(target or ai.get("target_class", "bottle")).lower()
        self.policy = policy_from_config(cfg)
        self.safety = SafetyManager(
            emergency_cm=float(rover.get("emergency_stop_distance_cm", 15.0)),
            slow_cm=float(rover.get("slow_down_distance_cm", 30.0)),
            comm_timeout_s=float(safety_cfg.get("comm_timeout_s", 3.0)),
            sensor_invalid_limit=int(safety_cfg.get("sensor_invalid_limit", 5)),
        )
        self.require_camera = bool(safety_cfg.get("require_camera_for_auto", True))
        self.require_serial = bool(safety_cfg.get("require_serial_for_auto", True))
        self.alert_clear_s = float(safety_cfg.get("comm_timeout_s", 3.0))
        self.min_confidence = float(ai.get("target_confidence", 0.5))
        self.emergency_cm = float(rover.get("emergency_stop_distance_cm", 15.0))
        self.pwm = int(rover.get("max_speed_pwm", 200))
        self.camera_fresh_s = float(camera.get("frozen_frame_timeout_s", 3.0))
        self.frame_w = int(camera.get("width", 640))
        self.frame_h = int(camera.get("height", 480))
        self.cooldown_s = float(perception.get("command_cooldown_s", 0.2))
        self.heartbeat_s = float(perception.get("heartbeat_interval_s", 1.0))
        mode = str(dashboard_cfg.get("mode", "manual")).strip().lower()
        self.mode = mode if mode in MODES else "manual"
        self.explorer = Explorer.from_config(cfg)
        if self.mode == "explore":
            self.explorer.start(time.time())
        self.history: deque[DecisionRecord] = deque(
            maxlen=max(1, int(dashboard_cfg.get("decision_history", 60)))
        )
        self._history_lock = threading.Lock()
        self._armed = False
        self._blockers: tuple[str, ...] = ()
        self._last_record: DecisionRecord | None = None
        self._emitter = CommandEmitter(
            getattr(link, "send", None),
            cooldown_s=self.cooldown_s,
            heartbeat_s=self.heartbeat_s,
        )
        self._running = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------- arming
    def arm_check(
        self,
        tele: dict[str, Any],
        *,
        has_frame: bool,
        ai_age_s: float,
        now: float,
    ) -> list[str]:
        """Strict AUTO blockers: empty list == may move."""
        blockers: list[str] = []
        if self.require_serial and not bool(tele.get("connected")):
            blockers.append("SERIAL DOWN")
        if self.require_camera and not has_frame:
            blockers.append("NO VIDEO")
        if self.require_camera and not (0.0 <= ai_age_s <= self.camera_fresh_s):
            blockers.append("AI STALE")
        alert_at = float(tele.get("alert_at", 0.0) or 0.0)
        if alert_at > 0 and now - alert_at <= self.alert_clear_s:
            blockers.append("ALERT ACTIVE")
        return blockers

    def set_mode(self, mode: str) -> dict[str, Any]:
        """Switch modes; any change parks the rover with STOP first."""
        wanted = str(mode or "").strip().lower()
        if wanted not in MODES:
            raise ValueError(f"invalid mode: {mode!r}")
        if wanted != self.mode:
            if wanted == "explore":
                self.explorer.start(time.time())
            else:
                self.explorer.stop()
            self.mode = wanted
            with contextlib.suppress(Exception):
                self._link.send(STOP)
            self._emitter.reset(STOP, time.time())
            logger.info("mode -> %s", wanted)
        return self.status()

    # --------------------------------------------------------------- tick
    def tick(self, now: float | None = None) -> DecisionRecord:
        """Run one decision cycle (2-5 Hz from the deck thread)."""
        now = time.time() if now is None else now
        frame, raw = self._snapshot()
        detections = [_detection_from(d) for d in raw or []]
        target = best_target(
            [d for d in detections if d.class_name.lower() == self.target]
        )
        width = float(frame.shape[1]) if frame is not None else float(self.frame_w)
        height = float(frame.shape[0]) if frame is not None else float(self.frame_h)
        steer = self.policy.decide(target, width, height)

        tele = self._telemetry()
        distance = tele.get("distance_cm")
        serial_ok = bool(tele.get("connected"))
        ai_age = self._ai_age()
        blockers = tuple(
            self.arm_check(tele, has_frame=frame is not None, ai_age_s=ai_age, now=now)
        )
        armed = self.mode in ("auto", "explore") and not blockers

        # explore: the roam loop proposes; safety still gates every command.
        proposed = steer.command
        steer_reason = steer.reason
        if self.mode == "explore":
            explore_cmd, explore_reason = self.explorer.propose(
                now,
                distance if isinstance(distance, (int, float)) else None,
                self._world_blocked(),
            )
            proposed = explore_cmd
            steer_reason = f"explore[{self.explorer.state}]: {explore_reason}"

        confidence = float(target.confidence) if target is not None else 0.0
        # Roaming has no target: the confidence gate only exists to stop the
        # rover chasing noise while targeting, so explore passes it outright
        # (camera freshness + ultrasonic still gate every movement).
        gate_conf = 1.0 if self.mode == "explore" else confidence
        verdict = self.safety.check(
            proposed,
            distance,
            serial_ok,
            frame is not None,
            ai_confidence=gate_conf,
            min_confidence=self.min_confidence,
            allow_without_camera=not self.require_camera,
        )

        sent: str | None = None
        if self.mode == "manual":
            command = str(tele.get("active", STOP))
            allowed, reason = True, "MANUAL: pad owns the link"
        elif self.mode == "observe":
            command, allowed, reason = verdict.command, verdict.allowed, verdict.reason
        elif armed:
            command, allowed, reason = verdict.command, verdict.allowed, verdict.reason
            sent = self._emit(command, now)
        else:
            command, allowed = STOP, False
            reason = f"DISARMED: {', '.join(blockers)}"
            sent = self._emit(STOP, now)

        self._armed = armed
        self._blockers = blockers
        overlay = overlay_for(
            self.mode, command, reason, blockers, self.emergency_cm, self.pwm
        )
        record = DecisionRecord(
            at=now,
            mode=self.mode,
            armed=armed,
            proposed=proposed,
            command=command,
            allowed=allowed,
            steering_reason=steer_reason,
            safety_reason=reason,
            blockers=blockers,
            distance_cm=(
                float(distance) if isinstance(distance, (int, float)) else None
            ),
            target=self.target if target is not None else None,
            confidence=confidence,
            area_ratio=round(float(steer.area_ratio), 4),
            zone=str(steer.zone) if steer.zone is not None else None,
            target_present=target is not None,
            sent=sent,
            motors=motors_for(command, self.pwm),
            overlay=overlay,
        )
        self._last_record = record
        with self._history_lock:
            self.history.append(record)
        if self._on_tick is not None:
            try:
                self._on_tick(record)
            except Exception:
                logger.exception("pilot on_tick callback failed")
        return record

    # ------------------------------------------------------------ outputs
    def status(self) -> dict[str, Any]:
        rec = self._last_record
        with self._history_lock:
            history_list = [r.to_dict() for r in list(self.history)]
        return {
            "mode": self.mode,
            "modes": list(MODES),
            "armed": self._armed,
            "blockers": list(self._blockers),
            "explore": self.explorer.status(),
            "decision": rec.to_dict() if rec else None,
            "history": history_list,
            "history_max": self.history.maxlen,
        }

    # ---------------------------------------------------------- lifecycle
    def start(self, rate_hz: float = 4.0) -> None:
        """Drive tick() in the background (the deck renders between ticks)."""
        if self._running:
            return
        self._running = True

        def loop() -> None:
            period = 1.0 / max(0.2, float(rate_hz))
            while self._running:
                try:
                    self.tick()
                except Exception:
                    logger.exception("pilot tick failed")
                time.sleep(period)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop ticking and leave the rover parked."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self.mode in ("auto", "explore"):
            with contextlib.suppress(Exception):
                self._link.send(STOP)
            self._emitter.reset(STOP, time.time())

    # ------------------------------------------------------------- helpers
    def _snapshot(self):
        if self._feed is None:
            return None, []
        try:
            return self._feed.snapshot()
        except Exception:
            logger.exception("feed snapshot failed")
            return None, []

    def _ai_age(self) -> float:
        if self._feed is None:
            return -1.0
        try:
            state = self._feed.state()
        except Exception:
            return -1.0
        try:
            return float(state.get("ai_age_s", -1.0))
        except (TypeError, ValueError):
            return -1.0

    def _telemetry(self) -> dict[str, Any]:
        if self._link is None:
            return {"connected": False, "active": STOP}
        try:
            return self._link.telemetry()
        except Exception:
            return {"connected": False, "active": STOP}

    def _world_blocked(self) -> bool:
        """True when the world model's path verdict is 'blocked' (advisory)."""
        if self._feed is None:
            return False
        try:
            state = self._feed.state()
        except Exception:
            return False
        world = state.get("world") if isinstance(state, dict) else None
        return bool(isinstance(world, dict) and world.get("blocked"))

    def _emit(self, command: str, now: float) -> str | None:
        """Throttled send: STOP is immediate, motion respects cooldown+heartbeat."""
        return self._emitter.emit(command, now)
