"""Documentation / configuration consistency checks (repository audit §2).

These tests compare what the docs and config *claim* against what the code
actually does. Failures here are documentation or configuration defects, not
necessarily runtime defects - each one is reported with its impact.
"""

from __future__ import annotations

import copy
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
SOFTWARE = ROOT / "software"
CONFIG = yaml.safe_load((ROOT / "config" / "config.yaml").read_text(encoding="utf-8"))
THRESH = yaml.safe_load(
    (ROOT / "config" / "thresholds.yaml").read_text(encoding="utf-8")
)
INO = (ROOT / "arduino" / "rover_controller" / "rover_controller.ino").read_text(
    encoding="utf-8"
)


def py_sources() -> dict[str, str]:
    return {
        str(p.relative_to(ROOT)): p.read_text(encoding="utf-8")
        for p in sorted(SOFTWARE.rglob("*.py"))
    }


def leaves(node, prefix=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from leaves(v, f"{prefix}.{k}" if prefix else str(k))
    else:
        yield prefix, node


# ------------------------------------------------- config <-> config --------
def test_thresholds_yaml_agrees_with_config_yaml():
    thr, cfg = THRESH["ultrasonic"], CONFIG["rover"]
    assert thr["emergency_stop_cm"] == cfg["emergency_stop_distance_cm"]
    assert thr["slow_cm"] == cfg["slow_down_distance_cm"]
    zones, nav = THRESH["vision_zones"], CONFIG["navigation"]
    assert zones["left_max"] == nav["left_boundary"]
    assert zones["center_max"] == nav["center_boundary"]
    assert zones["center_tolerance"] == nav["center_tolerance"]
    gap = THRESH["gap"]
    assert gap["rover_width_cm"] == cfg["width_cm"]
    assert gap["safety_margin_cm"] == cfg["safety_margin_cm"]
    assert (
        THRESH["target_approach"]["stop_width_ratio"]
        == cfg["approach_stop_width_ratio"]
    )


def test_config_validation_rejects_impossible_safety_values():
    from software.utils.config_loader import validate_config

    bad = copy.deepcopy(CONFIG)
    bad["rover"]["emergency_stop_distance_cm"] = 50.0  # >= slow zone
    bad["rover"]["slow_down_distance_cm"] = 30.0
    try:
        validate_config(bad)
    except ValueError:
        return
    raise AssertionError("validate_config accepted emergency >= slow")


def test_config_validation_rejects_missing_section():
    from software.utils.config_loader import validate_config

    try:
        validate_config({"camera": {}})
    except ValueError:
        return
    raise AssertionError("missing sections accepted")


def test_config_validation_rejects_out_of_range_confidence():
    from software.utils.config_loader import validate_config

    bad = copy.deepcopy(CONFIG)
    bad["ai"]["confidence_threshold"] = 1.5
    try:
        validate_config(bad)
    except ValueError:
        return
    raise AssertionError("confidence_threshold 1.5 accepted")


def test_config_validation_rejects_inverted_zone_boundaries():
    from software.utils.config_loader import validate_config

    bad = copy.deepcopy(CONFIG)
    bad["navigation"]["left_boundary"] = 0.9
    bad["navigation"]["center_boundary"] = 0.2
    try:
        validate_config(bad)
    except ValueError:
        return
    raise AssertionError("inverted zone boundaries accepted")


def test_config_validation_rejects_bad_control_loop_values():
    from software.utils.config_loader import validate_config

    bad = copy.deepcopy(CONFIG)
    bad["control"]["steering_kp"] = -1.0
    try:
        validate_config(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("negative steering_kp accepted")
    bad2 = copy.deepcopy(CONFIG)
    bad2["control"]["velocity_pwm_ff"] = 300  # PWM must fit 0..255
    try:
        validate_config(bad2)
    except ValueError:
        pass
    else:
        raise AssertionError("velocity_pwm_ff > 255 accepted")
    bad3 = copy.deepcopy(CONFIG)
    bad3["control"]["velocity_period_ms"] = 0
    try:
        validate_config(bad3)
    except ValueError:
        pass
    else:
        raise AssertionError("nonpositive velocity_period_ms accepted")


# ------------------------------------------------- unused config keys -------
def test_every_config_key_is_referenced_by_the_software():
    blob = "\n".join(py_sources().values())
    unused = []
    for dotted, _val in leaves(CONFIG):
        leaf = dotted.rsplit(".", 1)[-1]
        if f'"{leaf}"' not in blob and f"'{leaf}'" not in blob:
            unused.append(dotted)
    assert not unused, f"config keys never read by software/: {unused}"


def test_thresholds_yaml_is_consumed_at_runtime():
    """Tuning config/thresholds.yaml must change runtime behaviour."""
    blob = "\n".join(py_sources().values())
    assert '["thresholds"]' in blob or "['thresholds']" in blob, (
        "config/thresholds.yaml is loaded into cfg['thresholds'] but never read"
    )


def test_camera_enhance_settings_are_used_by_the_control_loop():
    main_src = (SOFTWARE / "main.py").read_text(encoding="utf-8")
    assert "enhance" in main_src, (
        "config.yaml camera.enhance_* is documented as feeding the model but "
        "software/main.py never applies it (only scripts/dashboard do)"
    )


def test_env_example_variables_are_read_somewhere():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    names = [
        line.split("=", 1)[0].strip()
        for line in env.splitlines()
        if line.strip() and not line.startswith("#") and "=" in line
    ]
    blob = "\n".join(py_sources().values())
    unread = [n for n in names if n not in blob]
    assert not unread, f".env.example keys never referenced by software/: {unread}"


# ------------------------------------------------- requirements.txt ---------
def test_requirements_has_no_unreferenced_direct_dependencies():
    reqs = []
    for raw in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        entry = raw.split("#", 1)[0].strip()
        if entry:
            reqs.append(re.split(r"[<>=!\[]", entry)[0].strip())
    blob = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in list(SOFTWARE.rglob("*.py"))
        + list((ROOT / "scripts").rglob("*.py"))
        + list((ROOT / "tools").rglob("*.py"))
        + list((ROOT / "tests").rglob("*.py"))
    )
    modules = {
        "opencv-python": "cv2",
        "pyyaml": "yaml",
        "pyserial": "serial",
        "pillow": "PIL",
        "python-docx": "docx",
        "huggingface-hub": "huggingface_hub",
        "jinja2": "jinja2",
    }
    unused = []
    for pkg in reqs:
        mod = modules.get(pkg, pkg)
        if not re.search(rf"\b{re.escape(str(mod))}\b", blob):
            unused.append(pkg)
    assert not unused, f"requirements.txt entries never imported: {unused}"


# ------------------------------------------------- doc claims ---------------
def test_test_counts_in_docs_agree_with_each_other():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    testing = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")
    m_readme = re.search(r"pytest tests -q.*?(\d+)\s+passed", readme, re.DOTALL)
    m_testing = re.search(r"\((\d+) tests", testing)
    assert m_readme and m_testing, "could not find documented test counts"
    assert m_readme.group(1) == m_testing.group(1), (
        f"README says {m_readme.group(1)} tests, docs/testing.md says "
        f"{m_testing.group(1)} tests"
    )


def test_docs_communication_protocol_names_the_correct_host():
    doc = (ROOT / "docs" / "18_COMMUNICATION_PROTOCOL.md").read_text(encoding="utf-8")
    assert "ESP32 -> Arduino" not in doc and "Arduino -> ESP32" not in doc, (
        "docs/18 claims ESP32<->Arduino commands, but the link is laptop->Arduino"
    )


def test_docs_state_machine_states_are_reachable_in_code():
    doc = (ROOT / "docs" / "19_STATE_MACHINE.md").read_text(encoding="utf-8")
    claimed = set(re.findall(r"\*\*([A-Z_]+)\*\*", doc))
    eng = (SOFTWARE / "navigation" / "decision_engine.py").read_text(encoding="utf-8")
    # drop the STATES tuple: merely *listing* a state is not reaching it
    eng_without_table = re.sub(r"STATES\s*=\s*\(.*?\)\s*\n", "", eng, flags=re.DOTALL)
    blob = eng_without_table + (SOFTWARE / "main.py").read_text(encoding="utf-8")
    unreachable = [
        s for s in sorted(claimed) if f'"{s}"' not in blob and f"'{s}'" not in blob
    ]
    assert not unreachable, (
        f"states documented in docs/19 are declared but never entered: {unreachable}"
    )


def test_decision_engine_emergency_path_is_wired_up():
    blob = "\n".join(py_sources().values())
    assert re.search(r"\.emergency\s*\(", blob), (
        "DecisionEngine.emergency() is never called (dead safety API)"
    )
    assert re.search(r"\.to_search\s*\(", blob), (
        "DecisionEngine.to_search() is never called (dead API)"
    )


def test_pinout_doc_matches_firmware_pins():
    doc = (ROOT / "docs" / "PINOUT.md").read_text(encoding="utf-8")
    pairs = dict(re.findall(r"\| D(\d+) \| L298N (ENA|IN1|IN2|IN3|IN4|ENB)", doc))
    expected = {"ENA": "5", "IN1": "6", "IN2": "7", "IN3": "8", "IN4": "9", "ENB": "10"}
    actual = {func: pin for pin, func in pairs.items()}  # doc maps pin -> function
    for func, pin in expected.items():
        assert actual.get(func) == pin, (
            f"PINOUT.md says {func}=D{actual.get(func)}, firmware says D{pin}"
        )
    for func, pin in (("TRIG", "11"), ("ECHO", "12")):
        assert f"| D{pin} | HC-SR04 {func}" in doc
    fw = dict(re.findall(r"const int (\w+) = (\d+);", INO))
    assert fw["ENA"] == "5" and fw["ENB"] == "10"
    assert fw["TRIG_PIN"] == "11" and fw["ECHO_PIN"] == "12"


def test_firmware_does_not_claim_unused_features():
    # docs list an SG90 servo as optional hardware: firmware must not silently
    # depend on it.
    assert "Servo" not in INO
    assert "EEPROM" not in INO


# ------------------------------------------------- secrets ------------------
def test_no_hardcoded_credentials():
    secret_re = re.compile(
        r"""(?i)(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*["'][^"']{6,}["']"""
    )
    offenders = []
    for rel, text in py_sources().items():
        for m in secret_re.finditer(text):
            offenders.append(f"{rel}: {m.group(0)[:60]}")
    ino = (ROOT / "esp32" / "camera_stream" / "camera_stream.ino").read_text(
        encoding="utf-8"
    )
    for ssid, pwd in re.findall(r'#define WIFI_(SSID|PASS)\s+"([^"]+)"', ino):
        if not pwd.startswith("YOUR_"):
            offenders.append(f"camera_stream.ino WIFI_{ssid} is not a placeholder")
    assert not offenders, offenders


def test_esp32_wifi_credentials_are_still_placeholders():
    ino = (ROOT / "esp32" / "camera_stream" / "camera_stream.ino").read_text(
        encoding="utf-8"
    )
    assert '#define WIFI_SSID "YOUR_WIFI_SSID"' in ino
    assert '#define WIFI_PASS "YOUR_WIFI_PASSWORD"' in ino


# ------------------------------------------------- duplicate files ----------
def test_documentation_tree_has_no_byte_identical_duplicates():
    docs = [
        p
        for p in (ROOT / "docs").rglob("*.md")
        if p.is_file() and p.stat().st_size > 500
    ]
    by_hash: dict[str, list[Path]] = {}
    for p in docs:
        h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        by_hash.setdefault(h, []).append(p)
    dupes = {
        h: [str(p.relative_to(ROOT)) for p in paths]
        for h, paths in by_hash.items()
        if len(paths) > 1
    }
    assert not dupes, f"byte-identical duplicated documentation: {dupes}"


# ------------------------------------------------- run modes (R1) -----------
def test_python_m_software_main_help_works():
    r = subprocess.run(
        [sys.executable, "-m", "software.main", "--help"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
        check=False,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert "scan360" in r.stdout


def test_python_software_main_help_works():
    r = subprocess.run(
        [sys.executable, "software/main.py", "--help"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
        check=False,
    )
    assert r.returncode == 0, r.stderr[-2000:]
