"""Mission report: turn a recorded run + live world facts into rover-log prose.

Mars-rover-style summary generated from what already exists — no new sensors,
no LLM. Inputs are the RunRecorder's in-memory counters/events and the last
WorldModel snapshot; output is a markdown document the deck serves at
GET /api/report and the recorder writes as ``report.md`` on stop.

Everything is derived defensively: a run with no frames, no world model or no
ultrasonic still yields a coherent (if sparse) report.
"""

from __future__ import annotations

import time
from typing import Any

REPORT_FIELDS = (
    "duration_s",
    "decisions",
    "images",
    "commands",
    "events",
    "world",
    "mode_mix",
)


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _command_line(commands: dict[str, int]) -> str:
    total = sum(int(v) for v in commands.values()) or 0
    if not total:
        return "no commands sent"
    parts = [
        f"{cmd} {_pct(int(n), total)}% ({n})"
        for cmd, n in sorted(commands.items(), key=lambda kv: -kv[1])
    ]
    return ", ".join(parts)


def _world_lines(world: dict[str, Any] | None) -> list[str]:
    if not world or world.get("degraded") or not world.get("objects"):
        return ["- nothing recognised (world model empty or degraded)"]
    lines: list[str] = []
    scene = str(world.get("scene", ""))
    if scene:
        lines.append(f"Scene: {scene}")
    for fact in world.get("facts", [])[:8]:
        lines.append(f"- {fact}")
    path_state = str(world.get("path_state", "unknown"))
    reason = world.get("block_reason")
    lines.append(f"Path verdict: {path_state}" + (f" ({reason})" if reason else ""))
    rho = world.get("spec_rho_m")
    if rho is not None:
        lines.append(
            f"STL clear-path margin: rho={float(rho):+.2f} m "
            f"[{world.get('spec_verdict', 'unknown')}]"
        )
    return lines


def _event_lines(events: list[str], limit: int = 8) -> list[str]:
    if not events:
        return ["- no events"]
    return [f"- {e}" for e in list(events)[-limit:]]


def build_report(
    *,
    duration_s: float = 0.0,
    decisions: int = 0,
    images: int = 0,
    commands: dict[str, int] | None = None,
    events: list[str] | None = None,
    world: dict[str, Any] | None = None,
    mode_mix: dict[str, int] | None = None,
    path: str | None = None,
    now: float | None = None,
) -> str:
    """Render one mission's worth of facts as a markdown rover-log report."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now or time.time()))
    minutes, seconds = divmod(int(max(0.0, duration_s)), 60)
    lines = [
        "# MISSION REPORT",
        "",
        f"Generated: {stamp}",
    ]
    if path:
        lines.append(f"Run: {path}")
    lines += [
        "",
        "## Summary",
        f"- Duration: {minutes}m {seconds:02d}s",
        f"- Decision ticks: {decisions}",
        f"- Annotated frames: {images}",
        f"- Commands sent: {_command_line(commands or {})}",
    ]
    if mode_mix:
        mix = ", ".join(f"{k}={v}" for k, v in sorted(mode_mix.items()))
        lines.append(f"- Mode mix: {mix}")
    lines += ["", "## What the rover saw", *_world_lines(world)]
    lines += ["", "## Notable events", *_event_lines(list(events or []))]
    lines += [
        "",
        "## Notes",
        "- Distances are monocular estimates (± sigma) unless the ultrasonic",
        "  calibrator or metric depth checkpoint is active.",
        "- The world model is advisory; the ultrasonic safety chain is tier-1.",
    ]
    return "\n".join(lines) + "\n"
