"""Two-tier firmware contracts: ESP32 Bluetooth bridge + Arduino safety layer.

Source-level checks that pin the spec (device name, pinout, baud, safety rule,
non-blocking timing) so a refactor cannot silently drop a safety property.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_INO = (ROOT / "esp32" / "bt_bridge" / "bt_bridge.ino").read_text(
    encoding="utf-8"
)
WIFI_INO = (ROOT / "esp32" / "wifi_bridge" / "wifi_bridge.ino").read_text(
    encoding="utf-8"
)
PAGE_H = (ROOT / "esp32" / "wifi_bridge" / "page_html.h").read_text(encoding="utf-8")
MOTION_INO = (ROOT / "arduino" / "motion_safety" / "motion_safety.ino").read_text(
    encoding="utf-8"
)
CONFIG = yaml.safe_load((ROOT / "config" / "config.yaml").read_text(encoding="utf-8"))
THRESH = yaml.safe_load(
    (ROOT / "config" / "thresholds.yaml").read_text(encoding="utf-8")
)

MOTION_PINS = (
    "SS_RX_PIN",
    "SS_TX_PIN",
    "TRIG_PIN",
    "ECHO_PIN",
    "PWMA",
    "AIN1",
    "AIN2",
    "BIN1",
    "BIN2",
    "PWMB",
)


def _const(source: str, name: str) -> str:
    match = re.search(
        rf"const\s+(?:unsigned\s+)?(?:int|long|float|bool)\s+{name}\s*=\s*([-\d.a-zA-Z]+)\s*;",
        source,
    )
    assert match, f"{name} constant missing"
    return match.group(1)


def _function_body(source: str, name: str) -> str:
    match = re.search(
        rf"(?:void|bool|int|float|char|const char\s*\*)\s+{name}\s*\([^)]*\)\s*\{{",
        source,
    )
    assert match, f"function {name} not found"
    depth = 0
    for index in range(match.end() - 1, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[match.end() : index]
    raise AssertionError(f"unbalanced braces in {name}")


# ------------------------------------------------------------ ESP32 bridge
def test_bridge_uses_the_agreed_device_name_and_baud():
    assert 'BT_DEVICE_NAME[] = "AI_Rover_Control"' in BRIDGE_INO
    assert _const(BRIDGE_INO, "LINK_BAUD") == "9600"
    assert "SERIAL_8N1" in BRIDGE_INO
    assert "BluetoothSerial" in BRIDGE_INO


def test_bridge_transmits_on_gpio17_towards_arduino_d4():
    assert _const(BRIDGE_INO, "UART2_TX_PIN") == "17"
    assert (
        "Serial2.begin(LINK_BAUD, SERIAL_8N1, UART2_RX_PIN, UART2_TX_PIN)" in BRIDGE_INO
    )
    assert "GPIO17" in BRIDGE_INO
    assert "Arduino UNO D4" in BRIDGE_INO


def test_bridge_forwards_only_valid_motion_characters():
    body = _function_body(BRIDGE_INO, "isValidMotion")
    for cmd in "FB LRS".replace(" ", ""):
        assert f"'{cmd}'" in body, f"bridge whitelist missing {cmd}"
    relay = _function_body(BRIDGE_INO, "relayFromBluetooth")
    assert "Serial2.write" in relay
    assert "lastValid" in relay


def test_bridge_drain_is_bounded_and_noise_is_counted():
    relay = _function_body(BRIDGE_INO, "relayFromBluetooth")
    assert "RX_DRAIN_LIMIT" in relay
    assert "dropped" in relay
    assert re.search(r"while\s*\(\s*SerialBT\.available\(\)", relay)


def test_bridge_loop_does_not_block():
    body = _function_body(BRIDGE_INO, "loop")
    assert "delay(" not in body
    assert "relayFromBluetooth();" in body
    assert "reportHealth();" in body
    relay = _function_body(BRIDGE_INO, "relayFromBluetooth")
    assert "SerialBT.available" in relay


def test_bridge_has_no_wifi_credentials():
    assert "WIFI_SSID" not in BRIDGE_INO
    assert "WIFI_PASSWORD" not in BRIDGE_INO


# ---------------------------------------------------- Arduino motion/safety
def test_motion_pinout_matches_the_spec():
    """TB6612FNG blueprint map: D5 PWMA / D6 AIN1 / D7 AIN2 (left),
    D9 PWMB / D8 BIN1 / D10 BIN2 (right), HC-SR04 on D2/D3, link on D4."""
    pins = {name: int(_const(MOTION_INO, name)) for name in MOTION_PINS}
    assert pins["SS_RX_PIN"] == 4
    assert pins["SS_TX_PIN"] == 12
    assert pins["TRIG_PIN"] == 2
    assert pins["ECHO_PIN"] == 3
    assert pins["PWMA"] == 5
    assert pins["AIN1"] == 6
    assert pins["AIN2"] == 7
    assert pins["BIN1"] == 8
    assert pins["PWMB"] == 9
    assert pins["BIN2"] == 10
    assert len(set(pins.values())) == len(pins), f"pin collision: {pins}"
    assert all(0 <= value <= 13 for value in pins.values())


def test_motion_obstacle_threshold_matches_config():
    stop_cm = float(_const(MOTION_INO, "OBSTACLE_STOP_CM"))
    assert stop_cm == float(CONFIG["rover"]["emergency_stop_distance_cm"])
    assert stop_cm == float(THRESH["ultrasonic"]["emergency_stop_cm"])


def test_motion_watchdog_matches_the_blueprint():
    """The wireless tier's embedded stop is deliberately tighter than the
    laptop tiers' config safety.comm_timeout_s (3 s): the production blueprint
    mandates a 500 ms stop on a dead Wi-Fi pad (pad keep-alive = 200 ms)."""
    assert int(_const(MOTION_INO, "COMM_TIMEOUT_MS")) == 500
    assert int(_const(MOTION_INO, "COMM_TIMEOUT_MS")) != int(
        float(CONFIG["safety"]["comm_timeout_s"]) * 1000
    )


def test_motion_baud_matches_the_link_config():
    assert _const(MOTION_INO, "LINK_BAUD") == str(CONFIG["serial"]["baud_rate"])
    assert _const(BRIDGE_INO, "LINK_BAUD") == str(CONFIG["serial"]["baud_rate"])


def test_motion_blocks_forward_when_obstacle_is_close():
    body = _function_body(MOTION_INO, "evaluateSafety")
    blocked_line = next(line for line in body.splitlines() if "bool blocked" in line)
    assert "'F'" in blocked_line
    assert "'B'" not in blocked_line
    assert "'L'" not in blocked_line and "'R'" not in blocked_line
    blocked_branch = re.search(r"else if \(blocked\) \{(.*?)\}", body, re.DOTALL)
    assert blocked_branch, "no blocked branch"
    assert "stopMotors()" in blocked_branch.group(1)
    assert "STATE_BLOCKED" in blocked_branch.group(1)
    assert "emitAlert" in blocked_branch.group(1)


def test_motion_all_other_directions_execute_normally():
    drive_body = _function_body(MOTION_INO, "drive")
    for cmd in ("F", "B", "L", "R"):
        assert f"case '{cmd}':" in drive_body, f"drive() has no case for {cmd}"
    safety = _function_body(MOTION_INO, "evaluateSafety")
    stop_branch = re.search(
        r"else if \(currentCmd == 'S'\) \{(.*?)\}", safety, re.DOTALL
    )
    assert stop_branch and "stopMotors()" in stop_branch.group(1)
    assert (
        "sensorBlocked" in safety
        and "'B'" not in safety.split("bool blocked")[1].splitlines()[0]
    )


def test_motion_never_drives_on_an_invalid_echo():
    assert "BLOCK_ON_INVALID_ECHO" in MOTION_INO
    assert _const(MOTION_INO, "BLOCK_ON_INVALID_ECHO") == "true"


def test_motion_ultrasonic_service_is_non_blocking():
    assert "pulseIn(" not in MOTION_INO
    body = _function_body(MOTION_INO, "serviceUltrasonic")
    assert "micros()" in body
    for state in ("PING_IDLE", "PING_WAIT_RISE", "PING_WAIT_FALL"):
        assert state in body


def test_motion_loop_uses_millis_and_never_blocks():
    body = _function_body(MOTION_INO, "loop")
    assert "millis()" in body
    assert "delay(" not in body
    assert "handleLink()" in body
    assert "serviceUltrasonic(" in body
    assert "evaluateSafety(" in body
    assert "emitTelemetry(" in body


def test_motion_boots_stopped_without_actuating():
    setup = _function_body(MOTION_INO, "setup")
    assert "stopMotors()" in setup
    assert "drive(" not in setup
    assert re.search(r"char\s+currentCmd\s*=\s*'S'", MOTION_INO)
    assert '"BOOT:STOP"' in MOTION_INO


def test_motion_treats_serial_noise_as_a_stop():
    body = _function_body(MOTION_INO, "handleLink")
    malformed = re.search(r"if \(others > 0.*?\) \{(.*?)\}", body, re.DOTALL)
    assert malformed, "no malformed-chunk branch"
    assert "currentCmd = 'S'" in malformed.group(1)
    assert "stopMotors()" in malformed.group(1)
    assert "STATUS:ERROR" in malformed.group(1)
    assert int(_const(MOTION_INO, "ERROR_REPLY_MS")) > 0


def test_motion_accepts_bench_commands_over_usb():
    body = _function_body(MOTION_INO, "handleLink")
    assert "drainSource(link" in body
    assert "drainSource(Serial" in body
    assert "bench bring-up" in MOTION_INO


def test_motion_emits_distance_and_command_state_telemetry():
    body = _function_body(MOTION_INO, "emitTelemetry")
    assert "DIST:" in body
    assert "CMD:" in body
    assert "STATE:" in body
    assert "STATUS:" in body
    assert int(_const(MOTION_INO, "TELEMETRY_MS")) > 0


def test_motion_watchdog_stops_on_a_dead_link():
    body = _function_body(MOTION_INO, "evaluateSafety")
    comm_branch = re.search(r"if \(commLost\) \{(.*?)\}", body, re.DOTALL)
    assert comm_branch, "no commLost branch"
    assert "stopMotors()" in comm_branch.group(1)
    assert "currentCmd = 'S'" in comm_branch.group(1)


@pytest.mark.parametrize("bad", ["Servo.h", "EEPROM.h", "#include <WiFi.h>"])
def test_motion_pulls_in_no_unexpected_libraries(bad: str):
    assert bad not in MOTION_INO


# ------------------------------------------------------- ESP32 WiFi web bridge
def test_wifi_bridge_pins_name_baud_and_tx_pin():
    assert 'AP_SSID = "AI_Rover_Control"' in WIFI_INO
    assert "UART2_TX_PIN = 17" in WIFI_INO
    assert _const(WIFI_INO, "LINK_BAUD") == _const(MOTION_INO, "LINK_BAUD")
    assert "SERIAL_8N1" in WIFI_INO


def test_wifi_bridge_whitelists_the_same_commands():
    body = _function_body(WIFI_INO, "validCmd")
    for cmd in "FBLRS":
        assert f"'{cmd}'" in body


def test_wifi_bridge_serves_page_cmd_and_status():
    assert 'server.on("/"' in WIFI_INO
    assert 'server.on("/cmd"' in WIFI_INO
    assert 'server.on("/status"' in WIFI_INO
    cmd_body = _function_body(WIFI_INO, "handleCmd")
    assert "BAD" in cmd_body
    assert "relay(" in cmd_body
    assert "OK " in cmd_body


def test_wifi_bridge_loop_is_non_blocking():
    body = _function_body(WIFI_INO, "loop")
    assert "handleClient()" in body
    assert "delay(" not in body
    assert "millis()" in body


def test_wifi_bridge_page_lives_outside_the_ino():
    """Regression: the sketch preprocessor reads .ino files for prototypes and
    emits `function send(c);` from JavaScript inside a raw-string page, which
    does not compile. The page therefore belongs in a header it never scans.
    """
    assert '#include "page_html.h"' in WIFI_INO
    assert 'R"rawliteral(' not in WIFI_INO
    assert re.search(r"(?m)^function\s+\w+\s*\(", WIFI_INO) is None
    assert 'R"rawliteral(' in PAGE_H


def test_wifi_bridge_page_owns_the_camera_stream_panel():
    assert 'id="cam"' in PAGE_H
    assert 'id="camu"' in PAGE_H
    assert "/cam?u=" in PAGE_H
    assert "camSync" in PAGE_H
    assert "8080/video" in PAGE_H


def test_wifi_bridge_page_recovers_when_the_phone_url_does_not_play():
    """The phone app exposes both /video and /videofeed and may be offline, so
    the page must say why a stream is blank instead of showing nothing.
    """
    assert '<img id="cam" alt="live camera">' in PAGE_H
    assert "/videofeed" in PAGE_H
    assert "camAlt" in PAGE_H
    assert "img.onerror" in PAGE_H
    assert "phone off" in PAGE_H
    assert "removeAttribute('src')" in PAGE_H


def test_wifi_bridge_camera_endpoint_persists_and_validates_the_url():
    assert 'server.on("/cam"' in WIFI_INO
    handle = _function_body(WIFI_INO, "handleCam")
    assert "http://" in handle
    assert "https://" in handle
    assert "CAM_URL_MAX" in WIFI_INO
    assert 'prefs.putString("cam"' in WIFI_INO
    assert 'prefs.getString("cam"' in WIFI_INO
    status = _function_body(WIFI_INO, "handleStatus")
    assert r"\"cam\":" in status
    assert "gCamUrl" in status


def test_wifi_bridge_station_credentials_are_still_placeholders():
    assert 'STA_SSID = "YOUR_WIFI_SSID"' in WIFI_INO
    assert 'STA_PASS = "YOUR_WIFI_PASSWORD"' in WIFI_INO
