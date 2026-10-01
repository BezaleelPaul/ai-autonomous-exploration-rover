"""Run the Wokwi firmware simulation headlessly (one command).

Pipeline: build the UNO firmware -> optionally lint diagram.json -> drive
wokwi-cli against the Wokwi simulator and assert the telemetry text the
firmware must emit. Nothing here is pretend: the simulated binary is the
shipping rover_controller.ino build (tools/build_wokwi_firmware.py).

Requirements (all free, none committed to the repo):
    arduino-cli  - compiles the firmware
    wokwi-cli    - iwr https://wokwi.com/ci/install.ps1 -useb | iex
    WOKWI_CLI_TOKEN - https://wokwi.com/dashboard/ci (starts with 'wok_')
    Override the CLI path with WOKWI_CLI_PATH if it is not on PATH.

Usage:
    python tools/run_wokwi_sim.py                # build + lint + simulate
    python tools/run_wokwi_sim.py --scenario scenarios/safety.yaml
    python tools/run_wokwi_sim.py --no-build     # reuse build/ artifacts
    python tools/run_wokwi_sim.py --no-lint      # skip the registry lint

Exit codes: 0 pass, 1 firmware build failed, 2 wokwi-cli not found,
3 WOKWI_CLI_TOKEN not set, 4 simulation failed, 5 usage error.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WOKWI_DIR = ROOT / "diagrams" / "wokwi"
LOG_PATH = ROOT / "logs" / "wokwi_serial.log"
DEFAULT_TIMEOUT_MS = 10000
DEFAULT_EXPECT = "DIST:"


def find_cli() -> str | None:
    override = os.environ.get("WOKWI_CLI_PATH")
    if override:
        return override if Path(override).exists() else None
    return shutil.which("wokwi-cli") or shutil.which("wokwi-cli.exe")


def build_firmware() -> int:
    sys.path.insert(0, str(ROOT / "tools"))
    import build_wokwi_firmware

    return build_wokwi_firmware.main()


def lint_diagram(cli: str) -> bool:
    result = subprocess.run(
        [cli, "lint", str(WOKWI_DIR)],
        capture_output=True,
        text=True,
        check=False,
    )
    out = (result.stdout or "") + (result.stderr or "")
    print(out.strip())
    return result.returncode == 0


def simulate(
    cli: str, timeout_ms: int, expect: str, scenario: str | None = None
) -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        cli,
        str(WOKWI_DIR),
        "--timeout",
        str(timeout_ms),
        "--serial-log-file",
        str(LOG_PATH),
        "--expect-text",
        expect,
    ]
    if scenario:
        cmd += ["--scenario", scenario]
    print("running:", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        print(f"[OK] simulation emitted {expect!r}; serial log: {LOG_PATH}")
    else:
        print(
            f"[FAIL] wokwi-cli exited {result.returncode}; serial log: {LOG_PATH}",
            file=sys.stderr,
        )
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Wokwi firmware simulation headlessly"
    )
    parser.add_argument(
        "--no-build", action="store_true", help="skip arduino-cli build"
    )
    parser.add_argument("--no-lint", action="store_true", help="skip wokwi-cli lint")
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT_MS, help="sim ms"
    )
    parser.add_argument(
        "--expect-text", default=DEFAULT_EXPECT, help="required serial text"
    )
    parser.add_argument(
        "--scenario",
        default=None,
        help="automation scenario YAML relative to diagrams/wokwi/ "
        "(e.g. scenarios/safety.yaml)",
    )
    args = parser.parse_args(argv)

    if not args.no_build:
        code = build_firmware()
        if code != 0:
            print("[FAIL] firmware build", file=sys.stderr)
            return 1

    cli = find_cli()
    if cli is None:
        print(
            "error: wokwi-cli not found. Install it with:\n"
            "  iwr https://wokwi.com/ci/install.ps1 -useb | iex\n"
            "or set WOKWI_CLI_PATH to the executable.",
            file=sys.stderr,
        )
        return 2

    if not os.environ.get("WOKWI_CLI_TOKEN"):
        print(
            "error: WOKWI_CLI_TOKEN is not set. Get a free token at "
            "https://wokwi.com/dashboard/ci (starts with 'wok_') and set it:\n"
            "  $env:WOKWI_CLI_TOKEN = 'wok_...'",
            file=sys.stderr,
        )
        return 3

    if not args.no_lint and not lint_diagram(cli):
        print("[FAIL] diagram lint", file=sys.stderr)
        return 4

    timeout = args.timeout
    if args.scenario and timeout == DEFAULT_TIMEOUT_MS:
        timeout = 30000  # scenario steps run in simulated time
    code = simulate(cli, timeout, args.expect_text, args.scenario)
    return 0 if code == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
