"""Compile the real Arduino firmware into the Wokwi project directory.

Wokwi does not compile C++: `diagrams/wokwi/wokwi.toml` points at a .hex and
an .elf that this script produces with arduino-cli, from the *shipping*
firmware (arduino/rover_controller/rover_controller.ino) so the simulation
runs exactly the code the rover runs.

Usage:
    python tools/build_wokwi_firmware.py

Outputs (relative to the Wokwi project root):
    diagrams/wokwi/build/rover_controller.ino.hex
    diagrams/wokwi/build/rover_controller.ino.elf

Exit codes: 0 ok, 1 arduino-cli or the sketch is missing, 2 compile failed,
3 an output named by wokwi.toml was not produced.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
WOKWI_DIR = ROOT / "diagrams" / "wokwi"
SKETCH_DIR = ROOT / "arduino" / "rover_controller"
FQBN = "arduino:avr:uno"
BUILD_DIR = WOKWI_DIR / "build"
CLI_CANDIDATES = (
    "arduino-cli",
    str(Path.home() / "tools" / "bin" / "arduino-cli.exe"),
)


def _find_cli() -> str | None:
    for name in CLI_CANDIDATES:
        found = shutil.which(name) if "/" not in name and "\\" not in name else name
        if found and Path(found).exists():
            return found
    return None


def _declared_outputs() -> list[str]:
    """Firmware/elf paths declared by wokwi.toml (the contract this build feeds)."""
    config = WOKWI_DIR / "wokwi.toml"
    if not config.exists():
        raise FileNotFoundError(f"missing {config}")
    data = tomllib.loads(config.read_text(encoding="utf-8"))
    section = data.get("wokwi", {})
    declared = [section.get("firmware"), section.get("elf")]
    return [p for p in declared if p]


def main() -> int:
    if not (SKETCH_DIR / "rover_controller.ino").exists():
        print(f"error: sketch not found: {SKETCH_DIR}", file=sys.stderr)
        return 1
    cli = _find_cli()
    if cli is None:
        print(
            "error: arduino-cli not found (install it, or add it to PATH); "
            "Wokwi cannot compile firmware itself",
            file=sys.stderr,
        )
        return 1

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        cli,
        "compile",
        "--fqbn",
        FQBN,
        "--output-dir",
        str(BUILD_DIR),
        str(SKETCH_DIR),
    ]
    print("running:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        print("error: arduino-cli compile failed", file=sys.stderr)
        return 2

    missing = [rel for rel in _declared_outputs() if not (WOKWI_DIR / rel).exists()]
    if missing:
        print(f"error: wokwi.toml declares missing outputs: {missing}", file=sys.stderr)
        return 3

    for rel in _declared_outputs():
        path = WOKWI_DIR / rel
        print(f"  ok  {path.relative_to(ROOT)}  ({path.stat().st_size} bytes)")
    print("Wokwi firmware build complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
