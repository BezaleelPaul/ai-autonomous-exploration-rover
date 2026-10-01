"""Analyze rover mission log (Layer 8 scientific analytics).

Generates:
  1. Detection statistics
  2. Tracking statistics
  3. Trajectory estimates
  4. Object observations
  5. Rover telemetry
  6. Failure & safety events
  7. Mission timeline

Usage:
  python scripts/analyze_mission.py [--csv logs/mission_log.csv] [--json]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def parse_mission_log(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        return []
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def analyze(rows: list[dict]) -> dict:
    if not rows:
        return {"status": "EMPTY_OR_NOT_FOUND", "total_frames": 0}

    total_frames = len(rows)
    class_counts = Counter()
    track_ids = set()
    track_durations = Counter()
    confs = []
    distances = []
    speeds = []
    headings = []
    tilts = []
    battery_levels = []
    safety_stops = 0
    commands = Counter()

    # Trajectory integration (dead reckoning from speed + heading)
    traj_x = [0.0]
    traj_y = [0.0]

    for r in rows:
        cls_name = r.get("class", "-")
        if cls_name != "-" and cls_name != "NONE":
            class_counts[cls_name] += 1
            try:
                confs.append(float(r["confidence"]))
            except (ValueError, KeyError):
                pass

        tid = r.get("track_id", "-")
        if tid != "-":
            track_ids.add(tid)
            track_durations[tid] += 1

        cmd = r.get("decision", "S")
        commands[cmd] += 1

        try:
            d = float(r["distance"])
            distances.append(d)
            if d < 0.25 and cmd == "S":
                safety_stops += 1
        except (ValueError, KeyError):
            pass

        try:
            s = float(r["speed"])
            h = float(r["heading"])
            speeds.append(s)
            headings.append(h)
            rad = math.radians(h)
            dt = 0.1  # approx 10 Hz step
            traj_x.append(traj_x[-1] + s * math.cos(rad) * dt)
            traj_y.append(traj_y[-1] + s * math.sin(rad) * dt)
        except (ValueError, KeyError):
            pass

        try:
            tilts.append(float(r["tilt"]))
        except (ValueError, KeyError):
            pass

        try:
            battery_levels.append(float(r["battery"]))
        except (ValueError, KeyError):
            pass

    return {
        "mission_summary": {
            "total_frames_logged": total_frames,
            "start_time": rows[0].get("timestamp"),
            "end_time": rows[-1].get("timestamp"),
        },
        "detection_statistics": {
            "detections_by_class": dict(class_counts),
            "mean_confidence": round(float(sum(confs) / max(1, len(confs))), 3),
            "max_confidence": round(float(max(confs, default=0.0)), 3),
        },
        "tracking_statistics": {
            "unique_tracks_count": len(track_ids),
            "track_identities": list(track_ids),
            "mean_track_duration_frames": round(
                float(sum(track_durations.values()) / max(1, len(track_durations))), 1
            ),
        },
        "rover_telemetry": {
            "mean_speed_m_s": round(float(sum(speeds) / max(1, len(speeds))), 3),
            "max_speed_m_s": round(float(max(speeds, default=0.0)), 3),
            "mean_tilt_deg": round(float(sum(tilts) / max(1, len(tilts))), 2),
            "max_tilt_deg": round(float(max(tilts, default=0.0)), 2),
            "battery_start_pct": battery_levels[0] if battery_levels else None,
            "battery_end_pct": battery_levels[-1] if battery_levels else None,
        },
        "safety_and_decisions": {
            "command_distribution": dict(commands),
            "safety_stop_events": safety_stops,
        },
        "estimated_trajectory": {
            "final_displacement_x_m": round(traj_x[-1], 2),
            "final_displacement_y_m": round(traj_y[-1], 2),
            "total_distance_traveled_m": round(
                sum(
                    math.hypot(traj_x[i] - traj_x[i - 1], traj_y[i] - traj_y[i - 1])
                    for i in range(1, len(traj_x))
                ),
                2,
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze mission log telemetry.")
    parser.add_argument("--csv", default=str(ROOT / "logs" / "mission_log.csv"))
    parser.add_argument("--json", action="store_true", help="Output pure JSON")
    args = parser.parse_args()

    rows = parse_mission_log(Path(args.csv))
    report = analyze(rows)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=" * 60)
        print("          AUTONOMOUS ROVER MISSION REPORT")
        print("=" * 60)
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
