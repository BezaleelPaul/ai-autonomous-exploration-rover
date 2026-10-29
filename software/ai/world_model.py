"""Rover world model: spatial understanding with calibrated uncertainty.

Turns the detection stream into a short-term model of the surroundings and —
unlike a heuristic box-log — every claim carries an *interval* instead of a
point value:

* **tracking** — one constant-velocity Kalman filter per object
  (``software/ai/kalman.py``); the posterior position sigma is the
  principled uncertainty (coasting through occlusions widens it)
* **metric scale** — relative monocular depth is calibrated to metres by
  recursive least squares against the ultrasonic ranger: while the rover
  runs, (depth-score, 1/distance) pairs from the centred nearest object fit
  ``1/d = a·s + b``; the fit residual becomes the metric sigma. Optional
  ground-plane fallback (pinhole model, config `camera.ground_plane`) gives
  a geometric distance for floor-standing objects when height is calibrated
* **facts with intervals** — ``bottle left near d=1.2±0.4m conf=0.81``
  instead of crisp labels; band-only facts stay available when uncalibrated
* **three-state path verdict** — CLEAR (every interval above the margin),
  UNCERTAIN (some interval straddles it), BLOCKED (some interval fully
  inside) — interval arithmetic instead of a binary gate
* **STL spec** — ``always (ultrasonic > clear_margin)`` evaluated with
  quantitative robustness (``software/ai/stl_monitor.py``); rho > 0 satisfied,
  rho < 0 violated, reported live
* **watchdog** — the age of the last world update is checked against
  ``plugins.world_deadline_s``; stale perception reports DEGRADED instead
  of failing open

Advisory only: nothing here commands motors — the ultrasonic SafetyManager
stays the tier-1 authority.
"""

from __future__ import annotations

import math
import time
from typing import Any

from software.ai.kalman import BoxKalman
from software.ai.stl_monitor import Always, Pred, Signal, classify, evaluate

NEAR_CUT = 0.66
MID_CUT = 0.33
CONTAINMENT = 0.55
DEPTH_TOL = 0.25
MOTION_DELTA = 0.08
SIZE_RATE_APPROACH = 25.0  # px/s mean growth that counts as approaching
SIZE_RATE_RECEDE = -25.0
COAST_S = 2.0  # keep predicting a lost track this long
# Metric-mode constants: the depth map is already metres (Depth-Anything-V2
# metric checkpoint), so banding/motion use metre cuts instead of [0,1] scores.
METRIC_NEAR_M = 1.0
METRIC_MID_M = 2.5
METRIC_MOTION_DELTA_M = 0.15


def _area(box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _contains(outer, inner) -> bool:
    return (
        inner[0] >= outer[0]
        and inner[1] >= outer[1]
        and inner[2] <= outer[2]
        and inner[3] <= outer[3]
    )


def side_of(cx: float, frame_w: float) -> str:
    frac = cx / frame_w if frame_w else 0.5
    return "left" if frac < 0.34 else ("right" if frac > 0.66 else "center")


def band_of(score: float) -> str:
    if score >= NEAR_CUT:
        return "near"
    return "mid" if score >= MID_CUT else "far"


def band_of_metric(dist_m: float) -> str:
    """Band a metric distance (metres) instead of a [0,1] relative score."""
    if dist_m <= METRIC_NEAR_M:
        return "near"
    return "mid" if dist_m <= METRIC_MID_M else "far"


def ground_distance_m(
    y_bottom_px: float,
    *,
    height_m: float,
    focal_px: float,
    pitch_deg: float,
    frame_h: int,
) -> float | None:
    """Pinhole floor-hit distance for a box bottom (None if the ray is
    at/below the horizon — no floor intersection)."""
    if height_m <= 0 or focal_px <= 0:
        return None
    cy = frame_h / 2.0
    angle = math.radians(pitch_deg) + math.atan2(y_bottom_px - cy, focal_px)
    if angle <= math.radians(5.0):
        return None
    return float(height_m / math.tan(angle))


class InverseDepthCalibrator:
    """Least-squares fit of 1/d = a·score + b from (ultrasonic, depth) pairs.

    The ultrasonic ranger stands in for the "known reference object": each
    tick where a centred, closest detection carries a depth score we log
    (score, 1/distance). With enough spread the fit is a principled
    relative→metric conversion; the residual sigma propagates into every
    distance interval the model emits.
    """

    def __init__(self, min_pairs: int = 4, min_spread: float = 0.08, maxlen: int = 60):
        self.pairs: list[tuple[float, float]] = []
        self.min_pairs = int(min_pairs)
        self.min_spread = float(min_spread)
        self.maxlen = int(maxlen)
        self._a = 0.0
        self._b = 0.0
        self._resid = 0.0
        self._ready = False

    def observe(self, score: float, distance_m: float) -> None:
        if not (0.0 < distance_m < 20.0) or not (0.0 < score < 1.0):
            return
        self.pairs.append((float(score), 1.0 / float(distance_m)))
        if len(self.pairs) > self.maxlen:
            del self.pairs[: len(self.pairs) - self.maxlen]
        self._refit()

    def _refit(self) -> None:
        self._ready = False
        if len(self.pairs) < self.min_pairs:
            return
        xs = [p[0] for p in self.pairs]
        if max(xs) - min(xs) < self.min_spread:
            return
        n = len(self.pairs)
        mx = sum(xs) / n
        ys = [p[1] for p in self.pairs]
        my = sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        if sxx <= 1e-9:
            return
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
        a = sxy / sxx
        b = my - a * mx
        resid = math.sqrt(
            sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys, strict=True))
            / max(1, n - 2)
        )
        self._a, self._b, self._resid, self._ready = a, b, resid, True

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def pairs_used(self) -> int:
        return len(self.pairs)

    def predict(self, score: float) -> tuple[float | None, float | None]:
        """(distance_m, sigma_m) for a depth score; None while uncalibrated."""
        if not self._ready:
            return None, None
        inv = self._a * float(score) + self._b
        if inv <= 1e-3:
            return None, None
        dist = 1.0 / inv
        sigma = max(0.05, self._resid / inv**2)
        return dist, sigma


class _Track:
    __slots__ = (
        "conf",
        "depth_score",
        "first_t",
        "key",
        "kf",
        "label",
        "last_seen",
        "on",
        "prev_depth_score",
    )

    def __init__(self, key: str, label: str, box, conf: float, now: float) -> None:
        self.key = key
        self.label = label
        self.kf = BoxKalman(box)
        self.last_seen = now
        self.first_t = now
        self.depth_score: float | None = None
        self.prev_depth_score: float | None = None
        self.conf = float(conf)
        self.on: str | None = None


class WorldModel:
    """Kalman-tracked spatial memory with interval-valued facts."""

    def __init__(
        self,
        history_s: float = 5.0,
        frame_w: int = 640,
        frame_h: int = 480,
        *,
        k_sigma: float = 2.0,
        deadline_s: float = 1.5,
        clear_margin_m: float = 0.5,
        spec_window_s: float = 2.0,
        ground: dict | None = None,
        metric: bool = False,
    ) -> None:
        self.history_s = float(history_s)
        self.frame_w = int(frame_w)
        self.frame_h = int(frame_h)
        self.k_sigma = float(k_sigma)
        self.deadline_s = float(deadline_s)
        self.clear_margin_m = float(clear_margin_m)
        self.spec_window_s = float(spec_window_s)
        self.metric = bool(metric)
        g = ground or {}
        self.ground_height_m = float(g.get("height_m", 0.0) or 0.0)
        self.ground_focal_px = float(g.get("focal_px", 600.0) or 600.0)
        self.ground_pitch_deg = float(g.get("pitch_deg", 0.0) or 0.0)
        self.calibrator = InverseDepthCalibrator()
        self.ultrasonic = Signal("ultrasonic_m")
        self._tracks: dict[str, _Track] = {}
        self._last_update: float | None = None
        self.last: dict[str, Any] = self._empty()

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "scene": "nothing recognised yet",
            "facts": [],
            "objects": [],
            "blocked": False,
            "path_state": "unknown",
            "block_reason": None,
            "depth": "off",
            "calibrated": False,
            "spec_rho_m": None,
            "spec_verdict": "unknown",
            "degraded": True,
            "age_s": None,
        }

    # ------------------------------------------------------------ tracking
    def _key(self, det, index: int) -> str:
        tid = getattr(det, "track_id", None)
        if tid is not None:
            return f"t{tid}"
        cx = (det.x1 + det.x2) / 2.0
        cy = (det.y1 + det.y2) / 2.0
        return f"{det.class_name}:{int(cx // 64)}:{int(cy // 64)}:{index}"

    def _depth_score(self, depth_map, box) -> float | None:
        if depth_map is None:
            return None
        try:
            h, w = depth_map.shape[:2]
            x1 = max(0, min(w - 1, int(box[0])))
            x2 = max(x1 + 1, min(w, int(box[2])))
            y1 = max(0, min(h - 1, int(box[1])))
            y2 = max(y1 + 1, min(h, int(box[3])))
            patch = depth_map[y1:y2, x1:x2]
            if patch.size == 0:
                return None
            return float(patch.mean())
        except Exception:
            return None

    # ------------------------------------------------------------ update
    def update(
        self,
        dets: list,
        *,
        now: float | None = None,
        depth_map=None,
        distance_cm: float | None = None,
    ) -> dict:
        """Ingest one frame of detections (+depth, +ultrasonic cm) → world dict."""
        now = time.time() if now is None else now
        self._last_update = now
        if distance_cm is not None:
            try:
                cm = float(distance_cm)
            except (TypeError, ValueError):
                cm = -1.0
            if 0.0 < cm < 400.0:
                self.ultrasonic.append(now, cm / 100.0)
        self._step_tracks(dets, now, depth_map)
        self._calibrate_from_ultrasonic(distance_cm)
        entries = self._summarise(now, depth_map)
        path_state, reason = self._path(entries)
        rho = self._spec_rho(now, entries)
        labels: list[str] = []
        for e in entries:
            if e["label"] not in labels:
                labels.append(e["label"])
        scene = (
            ", ".join(labels[:5]) + " in view" if labels else "nothing recognised yet"
        )
        self.last = {
            "scene": scene,
            "facts": [self._fact(e) for e in entries[:8]],
            "objects": entries[:12],
            "blocked": path_state == "blocked",
            "path_state": path_state,
            "block_reason": reason,
            "depth": "on" if depth_map is not None else "off",
            # Metric depth is absolute by construction; relative mode needs the
            # ultrasonic fit (calibrator.ready) before intervals are metric.
            "calibrated": self.metric or self.calibrator.ready,
            "spec_rho_m": rho,
            "spec_verdict": classify(rho) if rho is not None else "unknown",
            "degraded": False,
            "age_s": 0.0,
            "updated_at": now,
        }
        return self.last

    def _step_tracks(self, dets: list, now: float, depth_map) -> None:
        for i, det in enumerate(dets):
            key = self._key(det, i)
            box = (det.x1, det.y1, det.x2, det.y2)
            track = self._tracks.get(key)
            if track is None:
                track = _Track(key, det.class_name, box, det.confidence, now)
                self._tracks[key] = track
            else:
                dt = max(1e-3, now - track.last_seen)
                track.kf.predict(dt)
                track.kf.correct(box)
                track.last_seen = now
                track.conf = float(det.confidence)
                if det.class_name:
                    track.label = det.class_name
            track.prev_depth_score = track.depth_score
            track.depth_score = self._depth_score(depth_map, box)
        for key in [k for k, t in self._tracks.items() if now - t.last_seen > COAST_S]:
            del self._tracks[key]

    def _calibrate_from_ultrasonic(self, distance_cm) -> None:
        """Fit 1/d = a·s + b while a centred closest object is in view.

        Skipped in metric mode: the depth map is already metres, so there is
        nothing to fit — the ultrasonic still feeds the STL clear-path spec.
        """
        if self.metric or distance_cm is None:
            return
        try:
            dist = float(distance_cm) / 100.0
        except (TypeError, ValueError):
            return
        if not (0.1 < dist < 4.0):
            return
        best = None
        for t in self._tracks.values():
            if t.depth_score is None:
                continue
            cx = (t.kf.box[0] + t.kf.box[2]) / 2.0
            if not (0.3 * self.frame_w <= cx <= 0.7 * self.frame_w):
                continue
            if best is None or t.depth_score > best.depth_score:
                best = t
        if best is not None and best.depth_score is not None:
            self.calibrator.observe(best.depth_score, dist)

    def _estimate(self, track: _Track) -> tuple[float | None, float | None]:
        """(distance_m, sigma_m) for one track.

        Metric mode: the depth sample is already metres, so return it with a
        fixed relative sigma (no fit needed). Relative mode: calibrated fit
        first, ground-plane fallback second.
        """
        if self.metric and track.depth_score is not None:
            dist = float(track.depth_score)
            if 0.05 < dist < 60.0:
                return dist, max(0.1, 0.15 * dist)
        if track.depth_score is not None:
            dist, sigma = self.calibrator.predict(track.depth_score)
            if dist is not None:
                return dist, sigma
        if self.ground_height_m > 0:
            gp = ground_distance_m(
                track.kf.box[3],
                height_m=self.ground_height_m,
                focal_px=self.ground_focal_px,
                pitch_deg=self.ground_pitch_deg,
                frame_h=self.frame_h,
            )
            if gp is not None and gp < 12.0:
                return gp, max(0.15 * gp, 0.1)
        return None, None

    def _summarise(self, now: float, depth_map) -> list[dict]:
        entries: list[dict] = []
        for track in list(self._tracks.values()):
            box = track.kf.box
            cx = (box[0] + box[2]) / 2.0
            dist, sigma = self._estimate(track)
            lo = hi = None
            if dist is not None and sigma is not None:
                lo = max(0.0, dist - self.k_sigma * sigma)
                hi = dist + self.k_sigma * sigma
            rate = track.kf.size_rate
            motion = "still"
            if rate >= SIZE_RATE_APPROACH:
                motion = "approaching"
            elif rate <= SIZE_RATE_RECEDE:
                motion = "receding"
            elif track.depth_score is not None and track.prev_depth_score is not None:
                delta = track.depth_score - track.prev_depth_score
                cut = METRIC_MOTION_DELTA_M if self.metric else MOTION_DELTA
                if delta > cut:
                    motion = "approaching"
                elif delta < -cut:
                    motion = "receding"
            if track.depth_score is None:
                band = None
            elif self.metric:
                band = band_of_metric(track.depth_score)
            else:
                band = band_of(track.depth_score)
            entry = {
                "label": track.label,
                "side": side_of(cx, self.frame_w),
                "depth_score": track.depth_score,
                "band": band,
                "motion": motion,
                "conf": round(track.conf, 2),
                "dist_m": round(dist, 2) if dist is not None else None,
                "dist_lo_m": round(lo, 2) if lo is not None else None,
                "dist_hi_m": round(hi, 2) if hi is not None else None,
                "sigma_m": round(sigma, 2) if sigma is not None else None,
                "pos_sigma_px": round(track.kf.pos_sigma_px, 1),
            }
            if track.on:
                entry["on"] = track.on
            entries.append(entry)
        entries = self._relations(entries)
        entries.sort(key=lambda e: e["conf"], reverse=True)
        return entries

    def _relations(self, entries: list[dict]) -> list[dict]:
        for track in self._tracks.values():
            inner_box = track.kf.box
            for other in self._tracks.values():
                if other is track:
                    continue
                outer_box = other.kf.box
                if _area(inner_box) >= _area(outer_box) * 0.8:
                    continue
                if not _contains(outer_box, inner_box):
                    continue
                di, si = self._estimate(track)
                do, so = self._estimate(other)
                if (
                    di is not None
                    and do is not None
                    and abs(di - do) > max(0.3, 2 * (si or 0) + 2 * (so or 0))
                ):
                    continue
                if (
                    track.depth_score is not None
                    and other.depth_score is not None
                    and abs(track.depth_score - other.depth_score) > DEPTH_TOL
                    and di is None
                ):
                    continue
                track.on = other.label
        for e in entries:
            for t in self._tracks.values():
                if t.label == e["label"] and t.on:
                    e["on"] = t.on
                    break
        return entries

    def _fact(self, e: dict) -> str:
        parts = [e["label"], e["side"]]
        if e.get("dist_m") is not None and e.get("sigma_m") is not None:
            parts.append(f"d={e['dist_m']:.1f}±{e['sigma_m']:.1f}m")
        elif e["band"]:
            parts.append(e["band"])
        if e.get("on"):
            parts.append(f"on {e['on']}")
        if e["motion"] != "still":
            parts.append(e["motion"])
        parts.append(f"conf={e['conf']:.2f}")
        return " ".join(parts)

    def _path(self, entries: list[dict]) -> tuple[str, str | None]:
        """Three-state verdict from interval arithmetic vs the clear margin."""
        m = self.clear_margin_m
        uncertain: list[dict] = []
        blocked: list[dict] = []
        for e in entries:
            lo, hi = e.get("dist_lo_m"), e.get("dist_hi_m")
            if lo is not None and hi is not None:
                if hi < m:
                    blocked.append(e)
                elif lo < m:
                    uncertain.append(e)
            elif e["side"] == "center" and e.get("band") == "near":
                # uncalibrated near-centre object: at least UNCERTAIN
                uncertain.append(e)
        if blocked:
            e = blocked[0]
            return "blocked", f"{e['label']} {e['side']} hi={e['dist_hi_m']}m < {m}m"
        if uncertain:
            e = uncertain[0]
            lo = e.get("dist_lo_m")
            hi = e.get("dist_hi_m")
            span = f" [{lo}-{hi}m]" if lo is not None else ""
            return "uncertain", f"{e['label']} {e['side']}{span} straddles {m}m"
        return "clear", None

    def _spec_rho(self, now: float, entries: list[dict] | None = None) -> float | None:
        """STL robustness of `always (ultrasonic > clear_margin)` over the
        last spec_window_s. Falls back to the nearest metric interval's
        lower bound when the ultrasonic signal is silent."""
        t0 = now - self.spec_window_s
        if self.ultrasonic.window(t0, now):
            return evaluate(
                Always(
                    0.0, self.spec_window_s, Pred("ultrasonic_m", self.clear_margin_m)
                ),
                {"ultrasonic_m": self.ultrasonic},
                t=now,
            )
        if entries is None:
            entries = self.last.get("objects", [])
        lows = [e["dist_lo_m"] for e in entries if e.get("dist_lo_m") is not None]
        if lows:
            return float(min(lows) - self.clear_margin_m)
        return None

    # ------------------------------------------------------------ watchdog
    def status(self, now: float | None = None) -> dict[str, Any]:
        """Age + degraded verdict — refreshed at read time, not update time."""
        now = time.time() if now is None else now
        d = dict(self.last)
        if self._last_update is None:
            d["age_s"] = None
            d["degraded"] = True
            return d
        age = now - self._last_update
        d["age_s"] = round(age, 2)
        d["degraded"] = age > self.deadline_s
        return d
