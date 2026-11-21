#!/usr/bin/env python3
"""Soak / latency test for the rover link.

Two modes:
  * default (safe): hammer the STOP path and poll /status. No motion.
  * --move: cycle F / L / B / R with stops between. LIFT THE ROVER or give it
    room; this makes the wheels turn.

    python scripts/soak_test.py --seconds 30
    python scripts/soak_test.py --seconds 60 --move --hz 8
    python scripts/soak_test.py --gateway http://127.0.0.1:8090 --seconds 10

Reports command success rate, HTTP codes, latency percentiles, the worst
`last_cmd_age_ms` (must stay below the 500 ms watchdog), and any Uno fault.
Exit code 0 = pass.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import _bootstrap  # noqa: F401

from ai_rover import RoverClient

DRIVE_CYCLE = ("F", "S", "L", "S", "B", "S", "R", "S")


def run(
    gateway: str = "http://192.168.4.1",
    seconds: float = 30.0,
    hz: float = 8.0,
    move: bool = False,
    speed: int = 120,
    log=print,
) -> dict:
    client = RoverClient(gateway, timeout=0.5)
    if not client.health():
        raise RuntimeError(f"gateway {gateway} unreachable")

    started = time.monotonic()
    attempts = 0
    ok = 0
    codes: Counter = Counter()
    latencies: list[float] = []
    max_age = 0
    max_age_at = 0.0
    faults: set[str] = set()
    states: set[str] = set()
    uno_wired = False
    next_status = 0.0

    log(f"[SOAK] {gateway} for {seconds:.0f}s at {hz:.0f} Hz ({'drive' if move else 'stop'} pattern)")

    while (elapsed := time.monotonic() - started) < seconds:
        cmd = DRIVE_CYCLE[int(elapsed) % len(DRIVE_CYCLE)] if move else "S"
        good = client.send(cmd, speed)
        attempts += 1
        ok += int(good)
        codes[client.stats.last_code] += 1
        latencies.append(client.stats.last_latency_ms)

        if elapsed >= next_status:
            next_status = elapsed + 1.0
            status = client.status()
            if status is not None:
                max_age = max(max_age, status.last_cmd_age_ms)
                if status.last_cmd_age_ms == max_age:
                    max_age_at = elapsed
                uno = status.uno
                uno_wired = uno_wired or bool(uno.get("wired"))
                if uno.get("fault") and uno.get("fault") != "NONE":
                    faults.add(str(uno["fault"]))
                if uno.get("state"):
                    states.add(str(uno["state"]))

        time.sleep(max(0.0, 1.0 / hz))

    client.stop(attempts=3)
    final = client.status()

    ordered = sorted(latencies) or [0.0]
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    report = {
        "gateway": gateway,
        "seconds": round(seconds, 1),
        "hz": hz,
        "move": move,
        "attempts": attempts,
        "ok": ok,
        "success_rate": round(ok / max(1, attempts), 4),
        "http_codes": {str(k): v for k, v in sorted(codes.items(), key=lambda kv: str(kv[0]))},
        "latency_ms": {
            "mean": round(statistics.mean(ordered), 1),
            "p95": round(p95, 1),
            "max": round(max(ordered), 1),
        },
        "max_last_cmd_age_ms": max_age,
        "max_age_at_s": round(max_age_at, 1),
        "uno_wired": uno_wired,
        "faults": sorted(faults),
        "states": sorted(states),
        "final_forwarded": final.forwarded if final else None,
        "final_rejected": final.rejected if final else None,
    }
    report["passed"] = (
        report["success_rate"] >= 0.99
        and not any(str(code).startswith("5") for code in codes)
        and not faults
        and max_age < 600
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Rover soak / latency test")
    parser.add_argument("--gateway", default="http://192.168.4.1")
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--hz", type=float, default=8.0)
    parser.add_argument("--move", action="store_true", help="cycle the drive commands (wheels turn)")
    parser.add_argument("--speed", type=int, default=120)
    parser.add_argument("--out", default="logs", help="where to write the JSON report")
    args = parser.parse_args(argv)

    try:
        report = run(args.gateway, args.seconds, args.hz, args.move, args.speed)
    except RuntimeError as exc:
        print(f"[SOAK] {exc}")
        return 2

    print(json.dumps(report, indent=2))
    Path(args.out).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = Path(args.out) / f"soak-{stamp}.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"[SOAK] report: {path}")
    print("[SOAK] PASS" if report["passed"] else "[SOAK] FAIL")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
