"""Property-based / randomized tests (MASTER_TEST_PROMPT section 23).

Every property uses a fixed seed so failures are reproducible.
"""

from __future__ import annotations

import itertools
import math
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from software.control.steering import AntiOscillation, command_for_position
from software.hardware.arduino_serial import ArduinoSerial
from software.perception.position_estimator import classify_position, is_centered
from software.safety.safety_manager import SafetyManager

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260925
VALID_CMDS = {"F", "B", "L", "R", "S"}
RANK = {"LEFT": 0, "CENTER": 1, "RIGHT": 2}


# ---------------------------------------------------- target classification --
def test_random_target_positions_always_classify():
    rng = random.Random(SEED)
    for _ in range(4000):
        x = rng.uniform(-0.5, 1.5)
        pos = classify_position(x)
        assert pos in ("LEFT", "CENTER", "RIGHT"), f"{x!r} -> {pos!r}"


def test_classification_is_monotonic_in_x():
    rng = random.Random(SEED + 1)
    xs = sorted(rng.uniform(-0.2, 1.2) for _ in range(2000))
    ranks = [RANK[classify_position(x)] for x in xs]
    assert all(a <= b for a, b in itertools.pairwise(ranks)), (
        "a target cannot move RIGHT -> LEFT while its x coordinate increases"
    )


def test_classification_respects_configured_boundaries():
    rng = random.Random(SEED + 2)
    left, center = 0.33, 0.66
    for _ in range(2000):
        x = rng.random()
        pos = classify_position(x, left, center)
        expected = "LEFT" if x < left else ("CENTER" if x < center else "RIGHT")
        assert pos == expected, f"x={x:.4f} -> {pos} (expected {expected})"


def test_centered_predicate_is_symmetric_and_bounded():
    rng = random.Random(SEED + 3)
    for _ in range(2000):
        x = rng.uniform(-1.0, 2.0)
        assert is_centered(x) == is_centered(1.0 - x), "is_centered is not symmetric"
        if is_centered(x):
            assert abs(x - 0.5) <= 0.06


# ------------------------------------------------------- obstacle distances --
def test_random_distances_never_authorise_unsafe_translation():
    rng = random.Random(SEED + 4)
    sm = SafetyManager(emergency_cm=15.0, slow_cm=30.0)
    for _ in range(4000):
        sm.reset_latch()
        d = rng.uniform(-50.0, 600.0)
        healthy = rng.random() < 0.8
        cam = rng.random() < 0.9
        conf = rng.random()
        proposed = rng.choice(sorted(VALID_CMDS))
        v = sm.check(proposed, d, healthy, cam, conf, 0.5, allow_without_camera=True)
        assert v.command in VALID_CMDS, v
        if not healthy:
            assert v.command == "S", f"unhealthy link allowed {v}"
        if d < 15.0 and proposed in ("F", "B"):
            assert v.command == "S", f"d={d} allowed translation {v}"
        if d > 400.0:
            assert v.command == "S", f"out-of-range d={d} allowed {v}"
        if d < 0.0 and proposed in ("F", "B"):
            # negative reading = no echo: turns may escape, translation may not
            assert v.command == "S", f"negative d={d} allowed translation {v}"
        if d < 0.0 and proposed in ("L", "R", "S") and healthy and cam:
            assert v.command == proposed, (
                f"negative d={d} suppressed an escape turn ({v})"
            )
        if math.isnan(d) and proposed in ("F", "B"):
            assert v.command == "S"


def test_ai_confidence_gate_is_applied_in_every_distance_zone():
    """docs/06 priority list: (5) AI confidence comes before (6) navigation."""
    sm = SafetyManager(emergency_cm=15.0, slow_cm=30.0)
    for d in (5.0, 10.0, 20.0, 25.0, 50.0, 200.0, 399.0):
        sm.reset_latch()
        v = sm.check("F", d, True, True, 0.1, 0.5, allow_without_camera=True)
        assert v.command == "S", f"low-confidence forward allowed at {d} cm: {v.reason}"


def test_random_invalid_distances_never_crash_and_never_translate():
    rng = random.Random(SEED + 5)
    bad_values = [
        None,
        float("nan"),
        float("inf"),
        -float("inf"),
        -1.0,
        "25",
        b"25",
        [25],
        {"d": 25},
    ]
    for _ in range(500):
        sm = SafetyManager()
        d = rng.choice(bad_values)
        proposed = rng.choice(sorted(VALID_CMDS))
        v = sm.check(proposed, d, True, True, 1.0, 0.5, allow_without_camera=True)
        assert v.command in VALID_CMDS
        if proposed in ("F", "B"):
            assert v.command == "S", f"{d!r} allowed translation {v}"


def test_random_distances_produce_consistent_classification():
    sm = SafetyManager(15.0, 30.0)
    rng = random.Random(SEED + 6)
    for _ in range(2000):
        d = rng.uniform(-10, 500)
        want = "EMERGENCY" if d < 15 else ("CAUTION" if d < 30 else "SAFE")
        assert sm.classify_distance(d) == want


# -------------------------------------------------------- serial protocol ----
def test_random_junk_on_the_wire_never_raises_and_never_forges_health():
    rng = random.Random(SEED + 7)
    alphabet = (
        "0123456789.-+eE:,\n\r\t "
        "FBLRSfblrsSTATUSOKDISTRCVD"
        "\x00\x07\x1b\x7f" + "".join(chr(c) for c in range(128, 256))
    )
    for _ in range(2000):
        ser = ArduinoSerial(mock=False)
        ser.connected = True
        ser.parse_line("DIST:120.0")
        ser.parse_line("STATUS:OK")
        good_dist, good_t = ser.telemetry.distance_cm, ser.last_telemetry_time
        line = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 48)))
        try:
            ser.parse_line(line)
        except Exception as exc:
            raise AssertionError(f"parse_line raised on {line!r}: {exc!r}") from exc
        if ser.telemetry.distance_cm != good_dist:
            d_now = ser.telemetry.distance_cm
            assert d_now is not None and 0.0 <= d_now <= 500.0, (
                f"junk {line!r} produced out-of-range distance {d_now}"
            )
        if ser.last_telemetry_time != good_t:
            assert line.startswith(("DIST:", "STATUS:")), (
                f"junk {line!r} refreshed the link heartbeat"
            )


def test_raw_binary_fuzz_never_raises():
    rng = random.Random(SEED + 8)
    for _ in range(1000):
        ser = ArduinoSerial(mock=False)
        payload = bytes(rng.randrange(256) for _ in range(rng.randint(0, 64)))
        text = payload.decode("utf-8", errors="replace")
        for line in text.splitlines() or [""]:
            try:
                ser.parse_line(line)
            except Exception as exc:
                raise AssertionError(
                    f"parse_line raised on {payload!r}: {exc!r}"
                ) from exc
        d = ser.telemetry.distance_cm
        assert d is None or (math.isfinite(d) and 0.0 <= d <= 500.0)


# ------------------------------------------------------------- decision ------
def test_random_engine_inputs_always_yield_valid_commands():
    rng = random.Random(SEED + 9)
    osc = AntiOscillation(min_command_duration_s=0.4, cooldown_s=0.2)
    now = 0.0
    for _ in range(3000):
        position = rng.choice(["LEFT", "CENTER", "RIGHT", "NONE", "JUNK"])
        very_close = rng.random() < 0.2
        target_present = rng.random() < 0.7
        command, _state = command_for_position(position, very_close, target_present)
        issued = osc.apply(command, now)
        assert issued in VALID_CMDS, issued
        now += 0.05


def test_engine_stop_decision_is_not_delayed_by_the_oscillation_hold():
    """A STOP chosen by the steering logic must be issued immediately (docs/19)."""
    osc = AntiOscillation(min_command_duration_s=0.4, cooldown_s=0.2)
    now = 0.5
    violations = []
    for i in range(200):
        drive = osc.apply(command_for_position("CENTER", False, True)[0], now)
        assert drive == "F", f"setup failed at i={i}: {drive}"
        lost = osc.apply(command_for_position("CENTER", False, False)[0], now + 0.01)
        if lost != "S":
            violations.append(("target lost", i, lost))
        now += 0.25

        drive2 = osc.apply(command_for_position("CENTER", False, True)[0], now)
        assert drive2 == "F", f"setup failed at i={i}: {drive2}"
        close = osc.apply(command_for_position("CENTER", True, True)[0], now + 0.01)
        if close != "S":
            violations.append(("approach stop", i, close))
        now += 0.25
    assert not violations, (
        f"steering re-asserted a motion command immediately after deciding to stop "
        f"in {len(violations)} of 400 cases, e.g. {violations[:3]}"
    )


# ------------------------------------------------------------ pin map --------
def test_firmware_pin_constants_are_unique_and_bounded():
    ino = (ROOT / "arduino" / "rover_controller" / "rover_controller.ino").read_text(
        encoding="utf-8"
    )
    pins = dict(re.findall(r"const int (\w+) = (\d+);", ino))
    used = {
        k: int(v)
        for k, v in pins.items()
        if k in {"ENA", "IN1", "IN2", "IN3", "IN4", "ENB", "TRIG_PIN", "ECHO_PIN"}
    }
    assert len(used) == 8, f"expected 8 pins, parsed {used}"
    values = list(used.values())
    assert len(values) == len(set(values)), f"pin collision: {used}"
    assert all(0 <= v <= 13 for v in values), used
