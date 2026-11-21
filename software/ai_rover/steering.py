"""Three-zone steering policy: detections in, F/L/R/S out.

Policy (matches the project report):
    * pick the nearest object (largest bounding-box area)
    * area >= stop_area  -> S   (proximity brake)
    * centroid x in [0, 0.33)  -> L
    * centroid x in [0.33, 0.66] -> F
    * centroid x in (0.66, 1.0]  -> R

Two anti-jitter mechanisms keep the rover from twitching at zone boundaries:
an explicit hysteresis band and a consecutive-frame debounce.  A stop is
never debounced.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable, Sequence

from .protocol import DEFAULT_SPEED, MOTION_COMMANDS, ProtocolError


@dataclass(frozen=True)
class Detection:
    """One detected object. Coordinates are pixels, origin top-left."""

    cls: str
    conf: float
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    def area_ratio(self, frame_w: int, frame_h: int) -> float:
        if frame_w <= 0 or frame_h <= 0:
            return 0.0
        return self.area / float(frame_w * frame_h)


@dataclass
class ZoneConfig:
    left_bound: float = 0.33     # centroid <  left_bound          -> LEFT
    right_bound: float = 0.66    # centroid >  right_bound         -> RIGHT
    stop_area: float = 0.28      # bbox area / frame area          -> STOP
    hysteresis: float = 0.05     # dead-band around each boundary
    min_conf: float = 0.35
    target_classes: frozenset[str] = frozenset()  # empty = every class
    speed: int = 140
    switch_frames: int = 2       # consecutive frames before changing direction
    no_target_cmd: str = "S"     # "F" = keep exploring, "S" = fail-safe
    ttc_stop_s: float = 0.8      # bbox-growth time-to-collision brake; 0 = off

    def __post_init__(self) -> None:
        if not isinstance(self.target_classes, frozenset):
            self.target_classes = frozenset(self.target_classes)
        if not 0.0 < self.left_bound < self.right_bound < 1.0:
            raise ProtocolError("zones must satisfy 0 < left_bound < right_bound < 1")
        if not 0.0 < self.stop_area <= 1.0:
            raise ProtocolError("stop_area must be in (0, 1]")
        if not 0.0 <= self.hysteresis < 0.5:
            raise ProtocolError("hysteresis must be in [0, 0.5)")
        if not 60 <= self.speed <= 255:
            raise ProtocolError("speed must be in 60..255")
        if self.switch_frames < 1:
            raise ProtocolError("switch_frames must be >= 1")
        if self.no_target_cmd not in MOTION_COMMANDS and self.no_target_cmd != "S":
            raise ProtocolError("no_target_cmd must be F/B/L/R/S")
        if not 0.0 <= self.min_conf <= 1.0:
            raise ProtocolError("min_conf must be in 0..1")
        if not 0.0 <= self.ttc_stop_s <= 10.0:
            raise ProtocolError("ttc_stop_s must be in 0..10 s")


@dataclass(frozen=True)
class Decision:
    cmd: str
    zone: str = "NONE"
    speed: int | None = None
    area_ratio: float = 0.0
    confidence: float = 0.0
    target: Detection | None = None
    reason: str = ""
    switched: bool = True

    @property
    def is_stop(self) -> bool:
        return self.cmd == "S"

    def as_dict(self) -> dict:
        return {
            "cmd": self.cmd,
            "zone": self.zone,
            "speed": self.speed,
            "area_ratio": round(self.area_ratio, 4),
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
        }


class ZoneSteering:
    """Stateful zone policy (hysteresis + debounce live here)."""

    def __init__(self, config: ZoneConfig | None = None) -> None:
        self.config = config or ZoneConfig()
        self.last_decision: Decision | None = None
        self._pending_cmd: str | None = None
        self._pending_frames = 0
        self._last_area: float | None = None
        self._last_area_at: float | None = None

    # -- helpers -----------------------------------------------------------
    def filter(self, detections: Iterable[Detection]) -> list[Detection]:
        kept: list[Detection] = []
        for det in detections:
            if det.conf < self.config.min_conf:
                continue
            if det.width <= 0 or det.height <= 0:
                continue
            if self.config.target_classes and det.cls not in self.config.target_classes:
                continue
            kept.append(det)
        return kept

    def _zone(self, cx_norm: float) -> str:
        cfg = self.config
        h = cfg.hysteresis
        previous = self.last_decision.zone if self.last_decision else "NONE"

        left_edge = cfg.left_bound
        right_edge = cfg.right_bound
        if previous == "LEFT":
            left_edge += h
        elif previous == "RIGHT":
            right_edge -= h
        # previous CENTER (or first frame) keeps the nominal boundaries.

        if cx_norm < left_edge:
            return "LEFT"
        if cx_norm > right_edge:
            return "RIGHT"
        return "CENTER"

    # -- public API --------------------------------------------------------
    # -- time-to-collision ------------------------------------------------
    def _update_ttc(self, area_ratio: float, now: float | None) -> float | None:
        """Estimate seconds to contact from the growth rate of the target box.

        A monocular camera has no depth, but a box that grows quickly means the
        object is closing fast.  This is the software-only brake that
        compensates for a missing depth sensor.
        """
        if now is None or self.config.ttc_stop_s <= 0:
            return None
        previous_area = self._last_area
        previous_at = self._last_area_at
        self._last_area = area_ratio
        self._last_area_at = now
        if previous_area is None or previous_at is None:
            return None
        dt = now - previous_at
        if not 0.02 <= dt <= 1.5:
            return None
        growth = (area_ratio - previous_area) / dt
        if growth <= 0.02 or area_ratio < 0.01:
            return None
        return area_ratio / growth

    def decide(
        self,
        detections: Sequence[Detection],
        frame_w: int,
        frame_h: int,
        now: float | None = None,
    ) -> Decision:
        if frame_w <= 0 or frame_h <= 0:
            raise ProtocolError("frame dimensions must be positive")

        cfg = self.config
        candidates = self.filter(detections)
        if not candidates:
            self._last_area = None
            self._last_area_at = None
            decision = Decision(
                cmd=cfg.no_target_cmd,
                zone="NONE",
                speed=cfg.speed if cfg.no_target_cmd in MOTION_COMMANDS else None,
                reason="no target",
            )
            return self._commit(decision, immediate=True)

        target = max(candidates, key=lambda d: d.area_ratio(frame_w, frame_h))
        ratio = target.area_ratio(frame_w, frame_h)
        cx_norm = min(1.0, max(0.0, target.cx / float(frame_w)))

        ttc = self._update_ttc(ratio, now)
        if ttc is not None and ttc < cfg.ttc_stop_s:
            decision = Decision(
                cmd="S",
                zone=self._zone(cx_norm),
                speed=None,
                area_ratio=ratio,
                confidence=target.conf,
                target=target,
                reason=f"closing fast (TTC {ttc:.2f}s)",
            )
            return self._commit(decision, immediate=True)

        if ratio >= cfg.stop_area:
            decision = Decision(
                cmd="S",
                zone=self._zone(cx_norm),
                speed=None,
                area_ratio=ratio,
                confidence=target.conf,
                target=target,
                reason=f"area brake ({ratio:.0%} >= {cfg.stop_area:.0%})",
            )
            return self._commit(decision, immediate=True)

        zone = self._zone(cx_norm)
        cmd = {"LEFT": "L", "CENTER": "F", "RIGHT": "R"}[zone]
        decision = Decision(
            cmd=cmd,
            zone=zone,
            speed=cfg.speed,
            area_ratio=ratio,
            confidence=target.conf,
            target=target,
            reason=f"{target.cls} at cx={cx_norm:.2f}",
        )
        return self._commit(decision, immediate=False)

    # -- debounce ----------------------------------------------------------
    def _commit(self, decision: Decision, immediate: bool) -> Decision:
        previous = self.last_decision
        # A stop is immediate, and so is starting again from a stop: there is
        # no direction to jitter between. Only go->go reversals are debounced.
        if (
            immediate
            or previous is None
            or previous.cmd == "S"
            or decision.cmd == previous.cmd
        ):
            self._pending_cmd = None
            self._pending_frames = 0
            self.last_decision = decision
            return decision

        if decision.cmd == self._pending_cmd:
            self._pending_frames += 1
        else:
            self._pending_cmd = decision.cmd
            self._pending_frames = 1

        if self._pending_frames >= self.config.switch_frames:
            self._pending_cmd = None
            self._pending_frames = 0
            self.last_decision = decision
            return decision

        # Hold the previous motion, but report the fresh zone/hazard data.
        held = replace(
            previous,
            zone=decision.zone,
            area_ratio=decision.area_ratio,
            confidence=decision.confidence,
            target=decision.target,
            reason="debounce hold: " + decision.reason,
            switched=False,
        )
        return held

    def reset(self) -> None:
        self.last_decision = None
        self._pending_cmd = None
        self._pending_frames = 0
        self._last_area = None
        self._last_area_at = None
