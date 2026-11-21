#!/usr/bin/env python3
"""End-to-end bench smoke test for the ESP32 gateway (and optionally the motors).

Run this the moment the rover is powered and the phone is on the Soft-AP:

    python scripts/bench_smoke_test.py                 # gateway only
    python scripts/bench_smoke_test.py --drive --yes   # spins the wheels

Exit code 0 = every check passed.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import _bootstrap  # noqa: F401

from ai_rover import RoverClient, parse_command

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


TOKEN = os.environ.get("ROVER_TOKEN", "")


def raw_get(base: str, path: str, timeout: float = 0.6) -> tuple[int, bytes]:
    if TOKEN:
        path += ("&" if "?" in path else "?") + "k=" + urllib.parse.quote(TOKEN)
    req = urllib.request.Request(base.rstrip("/") + path, headers={"Cache-Control": "no-store"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc).encode()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Rover bench smoke test")
    parser.add_argument("--gateway", default="http://192.168.4.1")
    parser.add_argument("--drive", action="store_true", help="also spin the wheels (lift the rover!)")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    parser.add_argument("--speed", type=int, default=110)
    args = parser.parse_args(argv)

    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        print(f"  [{PASS if ok else FAIL}] {name}" + (f" - {detail}" if detail else ""))

    print(f"\nAI Rover bench smoke test -> {args.gateway}\n")

    print("1. Gateway HTTP")
    status, body = raw_get(args.gateway, "/health")
    check("GET /health == ok", status == 200 and body.strip() == b"ok", f"http {status}")

    status, body = raw_get(args.gateway, "/")
    check("GET / serves the drive pad", status == 200 and b"AI ROVER" in body, f"{len(body)} bytes")

    status, body = raw_get(args.gateway, "/status")
    check("GET /status is JSON", status == 200 and body.startswith(b"{"), f"http {status}")

    client = RoverClient(args.gateway, timeout=0.6)
    before = client.status()
    check("gateway reachable by RoverClient", before is not None)

    print("\n2. Protocol armour (must be rejected)")
    for payload in ("Z", "F999", "F1234", "", "FF", "F20x"):
        status, _ = raw_get(args.gateway, f"/cmd?c={payload}")
        check(f"/cmd?c={payload!r} -> 400", status == 400, f"http {status}")
    status, _ = raw_get(args.gateway, "/cmd")
    check("/cmd without c -> 400", status == 400, f"http {status}")

    after = client.status()
    if before and after:
        check("rejected counter increased", after.rejected > before.rejected, f"{before.rejected} -> {after.rejected}")
        check("forwarded counter unchanged by rejects", after.forwarded == before.forwarded)

    print("\n3. Whitelisted commands (STOP only - pass --drive to spin the wheels)")
    for _ in range(6):
        ok = client.send("S")
        check("/cmd 'S' accepted", ok)
        time.sleep(0.12)

    status_after = client.status()
    if before and status_after:
        check("forwarded counter advanced by 6", status_after.forwarded >= before.forwarded + 6,
              f"{before.forwarded} -> {status_after.forwarded}")

    print("\n4. Parser parity (laptop vs firmware)")
    samples = ["F200", "s", "R60", "L 90", "B255"]
    for sample in samples:
        try:
            packet = parse_command(sample)
            check(f"parse {sample!r} -> {packet.cmd}{packet.speed or ''}", True)
        except ValueError as exc:
            check(f"parse {sample!r}", False, str(exc))

    uno = (status_after.uno if status_after else {}) or {}
    if uno.get("wired"):
        check("Uno heartbeat is alive", bool(uno.get("alive")), f"{uno.get('hz', 0)} Hz")
        check("Uno fault line clear", not uno.get("fault_pin"), uno.get("fault", "?"))
        check("Uno telemetry frame is fresh", int(uno.get("telemetry_age_ms", -1)) >= 0
              and int(uno.get("telemetry_age_ms", 1 << 30)) < 2000,
              f"{uno.get('telemetry_age_ms')} ms")
    else:
        print("  [SKIP] Uno health harness not wired (D2/D3/A4 dividers) - bench mode")

    if args.drive:
        print("\n5. Wheels (lift the rover off the table!)")
        if not args.yes:
            input("   Press Enter when both wheels are off the ground, Ctrl+C to abort... ")
        for cmd, label in (("L", "left pivot"), ("R", "right pivot"), ("F", "both forward"), ("B", "both reverse")):
            print(f"   {label}: {cmd}{args.speed} for 1.2 s")
            client.send(cmd, args.speed)
            time.sleep(1.2)
            client.send("S")
            time.sleep(0.3)

    client.stop(attempts=3)
    status_after = client.status()
    if status_after:
        print(f"\n[gateway] fw={status_after.fw} uptime={status_after.uptime_ms / 1000:.0f}s "
              f"forwarded={status_after.forwarded} rejected={status_after.rejected} "
              f"clients={status_after.clients} camera={status_after.camera or '(unset)'}")

    failures = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failures)}/{len(results)} checks passed")
    if failures:
        print("Failed:")
        for name, _, detail in failures:
            print(f"  - {name} {detail}")
        return 1
    print("Rover gateway is good to go.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
