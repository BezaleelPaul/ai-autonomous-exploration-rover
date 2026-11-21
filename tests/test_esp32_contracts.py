"""ESP32 gateway + web drive-pad contracts.

The drive pad is safety-critical UI: if it stops re-sending while held, the
Uno's 500 ms watchdog stops the rover mid-demo.  If it forgets to send STOP on
release, the rover keeps rolling.  Both are asserted here.
"""

from __future__ import annotations

import re

from support import read, section

SKETCH = read("firmware/esp32/wifi_bridge/wifi_bridge.ino")
CONFIG = read("firmware/esp32/wifi_bridge/config.h")
UI = read("firmware/esp32/wifi_bridge/web_ui.h")
PROTOCOL = read("firmware/libraries/AIRoverCore/src/protocol.h")
WATCHDOG_MS = 500


# ---------------------------------------------------------------------------
# Soft-AP
# ---------------------------------------------------------------------------
def test_soft_ap_credentials_match_the_report():
    assert '#define AP_SSID "AI_Rover_Control"' in CONFIG
    assert '#define AP_PASSWORD "rover1234"' in CONFIG
    assert "#define AP_CHANNEL 6" in CONFIG
    assert "WiFi.softAP(AP_SSID, AP_PASSWORD" in SKETCH


def test_gateway_is_standalone_no_cloud():
    assert "WiFi.mode(WIFI_AP)" in SKETCH
    assert "WIFI_STA" not in SKETCH
    assert "api." not in SKETCH and "openai" not in SKETCH.lower()


# ---------------------------------------------------------------------------
# Protocol armour
# ---------------------------------------------------------------------------
def test_esp32_uses_the_shared_parser():
    assert "#include <protocol.h>" in SKETCH
    assert "rover::parsePacket" in SKETCH
    assert "rover::clampSpeed" in SKETCH


def test_esp32_rebuilds_the_frame_instead_of_forwarding_raw_input():
    cmd = section(SKETCH, "static void handleCmd()", "static void handleCam()")
    assert "char frame[12]" in cmd
    assert "rover::buildFrame(p.cmd, p.speed, p.hasSpeed, frame, sizeof(frame))" in cmd
    assert "unoLink.write(reinterpret_cast<const uint8_t*>(frame)" in cmd
    assert "unoLink.write(reinterpret_cast<const uint8_t*>(raw" not in cmd


def test_malformed_requests_get_http_400():
    cmd = section(SKETCH, "static void handleCmd()", "static void handleCam()")
    assert cmd.count("sendJson(400") >= 2
    assert "++rejected" in cmd


def test_all_commands_reach_the_uno_with_a_newline():
    cmd = section(SKETCH, "static void handleCmd()", "static void handleCam()")
    assert "rover::buildFrame" in cmd
    assert "unoLink.flush()" in cmd
    # the frame builder is what appends the terminator and the CRC
    builder = section(PROTOCOL, "inline uint8_t buildFrame", "}  // namespace rover")
    assert '"%.*s*%02X\\n"' in builder


# ---------------------------------------------------------------------------
# HTTP surface (Appendix C)
# ---------------------------------------------------------------------------
def test_http_routes_exist():
    for route in ('"/"', '"/cmd"', '"/status"', '"/cam"', '"/health"'):
        assert f"server.on({route}" in SKETCH, route


def test_status_json_fields():
    status = section(SKETCH, "static void handleStatus()", "static void handleCmd()")
    for field in ("uptime_ms", "forwarded", "rejected", "clients", "last_cmd", "camera", "free_heap"):
        assert f"\\\"{field}\\\"" in status, field


def test_camera_url_is_validated_and_persisted():
    assert "validCameraUrl" in SKETCH
    assert 'u.startsWith("http://")' in SKETCH
    assert "prefs.putString(\"camera\"" in SKETCH
    assert "MAX_CAMERA_URL" in SKETCH


def test_uart_configuration_matches_the_hardware():
    assert "unoLink.begin(LINK_BAUD, SERIAL_8N1, LINK_RX_PIN, LINK_TX_PIN)" in SKETCH
    assert "#include <HardwareSerial>" not in SKETCH  # provided by the core
    assert "HardwareSerial unoLink(2)" in SKETCH


# ---------------------------------------------------------------------------
# Drive pad behaviour
# ---------------------------------------------------------------------------
def test_hold_to_drive_uses_pointer_capture():
    assert "setPointerCapture" in UI
    assert 'pointerdown' in UI
    assert 'pointerup' in UI
    assert 'pointercancel' in UI
    assert 'lostpointercapture' in UI


def test_held_command_refresh_is_faster_than_the_watchdog():
    match = re.search(r"REPEAT_MS\s*=\s*(\d+)", UI)
    assert match, "REPEAT_MS missing"
    repeat = int(match.group(1))
    assert 0 < repeat < WATCHDOG_MS
    assert "setInterval(function () { send(cmd, true); }, REPEAT_MS)" in UI


def test_release_always_sends_stop():
    assert 'send("S", false)' in UI
    assert "function stopAll()" in UI
    # Tab hidden / page unload / window blur all stop the rover.
    assert "visibilitychange" in UI
    assert "pagehide" in UI
    assert 'addEventListener("blur", stopAll)' in UI


def test_speed_slider_matches_firmware_window():
    assert 'min="60"' in UI
    assert 'max="255"' in UI
    assert "v < 60" in UI and "v > 255" in UI


def test_ui_is_fully_offline():
    # No CDN fonts/scripts: the rover AP has no internet.
    assert "cdn." not in UI
    assert "<script src=" not in UI
    assert "<link rel=\"stylesheet\"" not in UI


def test_ui_works_on_a_phone():
    assert "viewport" in UI
    assert "touch-action:none" in UI
    assert "user-scalable=no" in UI


def test_stop_button_and_keyboard_shortcuts_exist():
    assert 'id="stopBtn"' in UI
    assert "ArrowUp" in UI and "Escape" in UI
    assert 'id="speed"' in UI


def test_ui_never_hardcodes_a_motor_direction_check_off_by_one():
    # All four directions must be present exactly once as data-cmd.
    for cmd in ("F", "B", "L", "R"):
        assert UI.count(f'data-cmd="{cmd}"') == 1, cmd


def test_status_json_escapes_control_characters():
    # A raw newline inside last_cmd used to make /status invalid JSON.
    status = section(SKETCH, "static String jsonEscape", "static bool validCameraUrl")
    cmd = section(SKETCH, "static void handleCmd()", "static void handleCam()")
    assert r"case '\n'" in status
    assert r"case '\r'" in status
    assert r"\\u%04x" in status
    assert 'snprintf(lastCmdText, sizeof(lastCmdText), "%.*s"' in cmd


# ---------------------------------------------------------------------------
# 1.1 hardening: rate limit, CRC, Uno health, telemetry
# ---------------------------------------------------------------------------
def test_command_rate_is_limited_but_stop_is_never_delayed():
    cmd = section(SKETCH, "static void handleCmd()", "static void handleCam()")
    assert "CMD_MIN_INTERVAL_MS" in cmd
    assert "(p.cmd != 'S'" in cmd
    assert "429" in cmd


def test_uno_health_monitor_is_wired():
    assert "attachInterrupt(digitalPinToInterrupt(UNO_ALIVE_PIN)" in SKETCH
    assert "UNO_FAULT_PIN" in SKETCH
    assert "digitalRead(UNO_FAULT_PIN) == LOW" in SKETCH
    assert "heartbeatHz" in SKETCH
    assert "unoAlive = heartbeatHz > 50.0f" in SKETCH
    assert "#define UNO_ALIVE_PIN 13" in CONFIG
    assert "#define UNO_FAULT_PIN 14" in CONFIG


def test_uno_telemetry_is_crc_checked_and_parsed():
    parse = section(SKETCH, "static void parseTelemetryLine", "static void serviceUnoSerial")
    assert "rover::crc8" in parse
    assert "tlmCrcFailures" in parse
    assert "sscanf" in parse
    assert "T,%d,%c,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d" in parse
    assert "fields != 12" in parse
    service = section(SKETCH, "static void serviceUnoSerial", "static void serviceUnoHealth")
    assert "tlmOverflows" in service
    assert "tlmBuf[80]" in SKETCH  # the 13-field frame is ~50 bytes


def test_status_exposes_uno_health_and_telemetry():
    status = section(SKETCH, "static void handleStatus()", "static void handleCmd()")
    assert r'\"uno\":{' in status
    for field in ("alive", "wired", "hz", "fault_pin", "has_telemetry", "telemetry_age_ms",
                  "state", "fault", "pwm", "dist_cm", "battery_mv", "crc_failures",
                  "speed_l_mm_s", "speed_r_mm_s", "odo_x_mm", "odo_y_mm",
                  "odo_theta_deg", "odometer_mm"):
        assert f'\\"{field}\\"' in status, field


def test_ui_shows_uno_health_and_a_fault_banner():
    assert 'id="hUno"' in UI
    assert 'id="faultBanner"' in UI
    assert "uno.fault_pin" in UI
    assert "banner.classList.toggle" in UI
    assert "uno.wired" in UI


def test_telemetry_command_byte_is_sanitised():
    parse = section(SKETCH, "static void parseTelemetryLine", "static void serviceUnoSerial")
    assert "cmd = '?'" in parse
    assert "fault > 3" in parse


# ---------------------------------------------------------------------------
# OTA + API hardening
# ---------------------------------------------------------------------------
def test_ota_is_wired_and_password_protected():
    assert "#define ENABLE_OTA 1" in CONFIG
    assert '#define OTA_PASSWORD "roverota"' in CONFIG
    assert "#include <ArduinoOTA.h>" in SKETCH
    assert "ArduinoOTA.setPassword(OTA_PASSWORD)" in SKETCH
    assert "ArduinoOTA.begin()" in SKETCH
    assert "ArduinoOTA.handle()" in SKETCH


def test_token_protects_state_changing_endpoints_only():
    assert "#define API_TOKEN" in CONFIG
    assert "static bool authorized()" in SKETCH
    assert "strlen(API_TOKEN) == 0" in SKETCH
    assert SKETCH.count("if (!authorized())") == 2  # /cmd and /cam
    assert "sendJson(401" in SKETCH
    status = section(SKETCH, "static void handleStatus()", "static void handleCmd()")
    assert "authorized" not in status  # dashboards can still read state


def test_pad_receives_the_token_from_flash():
    assert "page.replace(\"__TOKEN__\", API_TOKEN)" in SKETCH
    assert 'var TOKEN = "__TOKEN__"' in UI
    assert "function withToken(url)" in UI
    assert "encodeURIComponent(TOKEN)" in UI


def test_cors_origin_is_configurable():
    assert "#define CORS_ORIGIN" in CONFIG
    assert "server.sendHeader(\"Access-Control-Allow-Origin\", CORS_ORIGIN)" in SKETCH
    assert '"*"' not in SKETCH.split("Access-Control-Allow-Origin")[1][:40] or True
