"""Guards: the Wokwi simulation project must match the firmware pin map.

diagrams/wokwi/sketch.ino is a verbatim copy of the Arduino firmware;
diagrams/wokwi/diagram.json wires the simulated UNO to the L298N chip and
HC-SR04; diagrams/wokwi/wokwi.toml points Wokwi at the compiled firmware.
All three drift out of sync with docs/PINOUT.md the moment a pin changes.
"""

import importlib.util
import json
import re
from pathlib import Path

import pytest
import tomllib

ROOT = Path(__file__).resolve().parents[1]
SKETCH = ROOT / "diagrams" / "wokwi" / "sketch.ino"
DIAGRAM = ROOT / "diagrams" / "wokwi" / "diagram.json"
WOKWI_TOML = ROOT / "diagrams" / "wokwi" / "wokwi.toml"
BUILD_SCRIPT = ROOT / "tools" / "build_wokwi_firmware.py"
FIRMWARE = ROOT / "arduino" / "rover_controller" / "rover_controller.ino"

EXPECTED_PINS = {
    "ENA": 5,
    "IN1": 6,
    "IN2": 7,
    "IN3": 8,
    "IN4": 9,
    "ENB": 10,
    "TRIG_PIN": 11,
    "ECHO_PIN": 12,
}

_CONST_RE = re.compile(r"const\s+int\s+(\w+)\s*=\s*(\d+)\s*;")


def _pins(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return {m.group(1): int(m.group(2)) for m in _CONST_RE.finditer(text)}


def _diagram() -> dict:
    return json.loads(DIAGRAM.read_text(encoding="utf-8"))


def test_sketch_and_firmware_pin_map_agree():
    sketch = _pins(SKETCH)
    firmware = _pins(FIRMWARE)
    for name, value in EXPECTED_PINS.items():
        assert sketch.get(name) == value, f"sketch.ino {name} != {value}"
        assert firmware.get(name) == value, f"firmware {name} != {value}"


def test_diagram_signal_wires_match_pin_map():
    diagram = _diagram()
    wires = {(c[0], c[1]) for c in diagram["connections"]}
    expected = {
        (f"uno:{EXPECTED_PINS['ENA']}", "driver:EN A"),
        (f"uno:{EXPECTED_PINS['IN1']}", "driver:IN1"),
        (f"uno:{EXPECTED_PINS['IN2']}", "driver:IN2"),
        (f"uno:{EXPECTED_PINS['IN3']}", "driver:IN3"),
        (f"uno:{EXPECTED_PINS['IN4']}", "driver:IN4"),
        (f"uno:{EXPECTED_PINS['ENB']}", "driver:EN B"),
        (f"uno:{EXPECTED_PINS['TRIG_PIN']}", "sonar:TRIG"),
        (f"uno:{EXPECTED_PINS['ECHO_PIN']}", "sonar:ECHO"),
    }
    assert expected <= wires, f"missing wires: {expected - wires}"

    endpoints = {ep for wire in diagram["connections"] for ep in wire[:2]}
    uno_pins = {ep.split(":", 1)[1] for ep in endpoints if ep.startswith("uno:")}
    assert not {"0", "1"} & uno_pins, "D0/D1 are USB serial and must stay unwired"


def test_diagram_parts_and_l298n_dependency():
    diagram = _diagram()
    types = {p["type"] for p in diagram["parts"]}
    assert {"wokwi-arduino-uno", "wokwi-hc-sr04", "chip-l298n"} <= types
    dep = diagram.get("dependencies", {}).get("chip-l298n", "")
    assert dep.endswith("@1.0.5"), f"chip-l298n must pin @1.0.5, got {dep!r}"
    sonar = next(p for p in diagram["parts"] if p["type"] == "wokwi-hc-sr04")
    assert "distance" in sonar.get("attrs", {}), "distance slider attr required"


def _wokwi_config() -> dict:
    return tomllib.loads(WOKWI_TOML.read_text(encoding="utf-8"))["wokwi"]


def test_wokwi_toml_declares_build_artifacts():
    cfg = _wokwi_config()
    assert cfg.get("version") == 1, "wokwi.toml must declare version = 1"
    firmware, elf = cfg.get("firmware", ""), cfg.get("elf", "")
    assert firmware.endswith(".hex"), "UNO firmware must be an Intel HEX file"
    assert elf.endswith(".elf"), "ELF path required for Wokwi"
    for rel in (firmware, elf):
        path = Path(rel)
        assert not path.is_absolute(), f"wokwi.toml paths must be relative: {rel}"
        assert path.parts[0] == "build", f"artifacts live in build/: {rel}"
    assert Path(firmware).stem == Path(elf).stem, (
        "firmware and elf must come from one build"
    )


def test_build_script_feeds_the_declared_artifacts():
    assert BUILD_SCRIPT.exists(), "missing tools/build_wokwi_firmware.py"
    script = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "wokwi.toml" in script, "build must read wokwi.toml, not hardcode names"
    assert "--output-dir" in script and "arduino-cli" in script, (
        "must drive arduino-cli"
    )
    assert "rover_controller" in script, "must build the shipping firmware"


def test_built_firmware_is_intel_hex_when_present():
    rel = _wokwi_config()["firmware"]
    artifact = WOKWI_TOML.parent / rel
    if not artifact.exists():
        pytest.skip("firmware not built; run: python tools/build_wokwi_firmware.py")
    head = artifact.read_text(encoding="ascii", errors="replace")[:1]
    assert head == ":", "not an Intel HEX file"
    assert artifact.stat().st_size > 1024, "suspiciously small firmware image"


# ------------------------------------------------- tools/run_wokwi_sim.py ----
def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_wokwi_sim", ROOT / "tools" / "run_wokwi_sim.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_reports_a_failed_build_before_touching_the_network(monkeypatch):
    runner = _load_runner()
    monkeypatch.setattr(runner, "build_firmware", lambda: 2)
    assert runner.main(["--no-lint"]) == 1


def test_runner_stops_with_a_clear_error_when_wokwi_cli_is_absent(monkeypatch):
    runner = _load_runner()
    monkeypatch.setattr(runner.shutil, "which", lambda *_a, **_k: None)
    monkeypatch.setenv("WOKWI_CLI_PATH", str(ROOT / "no-such-wokwi-cli"))
    monkeypatch.delenv("WOKWI_CLI_TOKEN", raising=False)
    assert runner.main(["--no-build", "--no-lint"]) == 2


def test_runner_stops_with_a_clear_error_when_the_token_is_missing(monkeypatch):
    runner = _load_runner()
    monkeypatch.setenv("WOKWI_CLI_PATH", str(SKETCH))  # any existing path
    monkeypatch.delenv("WOKWI_CLI_TOKEN", raising=False)
    assert runner.main(["--no-build", "--no-lint"]) == 3


# ------------------------------------------------- automation scenarios -----
SCENARIOS_DIR = WOKWI_TOML.parent / "scenarios"


def _scenario_docs() -> dict:
    yaml = pytest.importorskip("yaml", reason="pyyaml required")
    files = sorted(SCENARIOS_DIR.glob("*.yaml"))
    assert files, "no automation scenarios in diagrams/wokwi/scenarios/"
    docs = {}
    for path in files:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(doc, dict), f"{path.name} is not a YAML mapping"
        docs[path.name] = doc
    return docs


def test_scenarios_are_well_formed_and_reference_real_parts():
    part_ids = {p["id"] for p in _diagram()["parts"]}
    for name, doc in _scenario_docs().items():
        assert doc.get("version") == 1, f"{name}: scenario version must be 1"
        assert doc.get("name"), f"{name}: missing name"
        steps = doc.get("steps")
        assert isinstance(steps, list) and steps, f"{name}: no steps"
        for step in steps:
            assert isinstance(step, dict) and len(step) == 1, f"{name}: malformed step"
            kind, payload = next(iter(step.items()))
            if kind in {"expect-pin", "set-control"}:
                assert isinstance(payload, dict), (
                    f"{name}:{kind} payload must be a mapping"
                )
                assert payload.get("part-id") in part_ids, (
                    f"{name}:{kind} targets unknown part {payload.get('part-id')!r}"
                )
            else:
                # delay / wait-serial / write-serial take a scalar
                assert not isinstance(payload, dict), f"{name}:{kind} takes a scalar"
            if kind == "expect-pin":
                # the alpha API reads `value`; `expected` silently compares
                # against `undefined` and the step then fails for the wrong reason
                assert "value" in payload, f"{name}: expect-pin needs `value:`"
                assert "expected" not in payload, (
                    f"{name}: use `value:`, not `expected:`"
                )


def test_scenarios_cover_startup_protocol_watchdog_and_the_obstacle_gate():
    docs = _scenario_docs()
    safety = docs.get("safety.yaml")
    assert safety is not None, "missing scenarios/safety.yaml"
    blob = json.dumps(safety)
    for needle in ("IN1", "STATUS:ERROR", "STATUS:STOP", "3600ms"):
        assert needle in blob, f"safety.yaml does not exercise {needle}"
    gate = docs.get("obstacle_gate.yaml")
    assert gate is not None, "missing scenarios/obstacle_gate.yaml"
    gate_blob = json.dumps(gate)
    # distance must go below EMERGENCY_STOP_CM (15 cm) before the F command
    assert "set-control" in gate_blob and "DIST:10" in gate_blob, (
        "obstacle_gate.yaml must move the sonar inside the emergency stop distance"
    )
    assert "STATUS:STOP" in gate_blob, "the gate must be asserted via STATUS:STOP"
