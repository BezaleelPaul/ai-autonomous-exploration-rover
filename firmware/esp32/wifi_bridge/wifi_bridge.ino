/*
 * AI-Assisted Autonomous Exploration Rover - ESP32 DevKit V1 gateway
 * ------------------------------------------------------------------
 * Responsibilities
 *   1. Standalone 2.4 GHz Soft-AP "AI_Rover_Control" (192.168.4.1).
 *   2. Serve the mobile drive pad from flash (no internet, no cloud).
 *   3. Whitelist + rate-limit every /cmd request, add a CRC-8 and relay it
 *      to the Uno over UART2.
 *   4. Persist the phone camera URL in NVS and expose /status as JSON.
 *   5. Monitor the Uno's 1 kHz heartbeat and FAULT line, and parse its
 *      compact telemetry, so /status reflects what the rover is really doing.
 *
 * Motor logic stays on the Uno: if this board hangs, the Uno stops itself.
 *
 * Target: ESP32 DevKit V1 (esp32:esp32:esp32doit-devkit-v1)
 */
#include "config.h"

#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <ESPmDNS.h>
#if ENABLE_OTA
#include <ArduinoOTA.h>
#endif
#if ENABLE_CAPTIVE_PORTAL
#include <DNSServer.h>
#endif

#include <protocol.h>
#include "web_ui.h"

WebServer server(80);
HardwareSerial unoLink(2);  // not "link": that collides with POSIX link()
Preferences prefs;
#if ENABLE_CAPTIVE_PORTAL
DNSServer dns;
#endif

// ---------------------------------------------------------------------------
// Gateway state
// ---------------------------------------------------------------------------
uint32_t forwarded = 0;
uint32_t rejected = 0;
uint32_t lastCmdAt = 0;
uint32_t lastForwardMs = 0;
char lastCmdText[10] = "--";
String cameraUrl;

// ---------------------------------------------------------------------------
// Uno health + telemetry
// ---------------------------------------------------------------------------
struct UnoTlm {
  bool valid = false;
  uint32_t at = 0;
  int state = 0;       // 0 stop, 1 go, 2 blocked, 3 timeout, 4 fault
  char cmd = 'S';
  int pwm = 0;
  int distCm = -1;
  int batteryMv = 0;
  int fault = 0;       // 0 none, 1 estop, 2 battlow, 3 stall
  int speedL = 0;      // mm/s
  int speedR = 0;
  int xMm = 0;
  int yMm = 0;
  int thetaDeg = 0;
  int odoMm = 0;
};

UnoTlm tlm;
volatile uint32_t aliveEdges = 0;
uint32_t healthWindowStart = 0;
float heartbeatHz = 0.0f;
bool unoAlive = false;
bool unoWired = false;
bool unoFaultPin = false;
uint32_t tlmCrcFailures = 0;
uint32_t tlmOverflows = 0;

static char tlmBuf[80];
static uint8_t tlmLen = 0;

static const char* STATE_LABELS[] = {"STOP", "GO", "BLOCKED", "TIMEOUT", "FAULT"};
static const char* FAULT_LABELS[] = {"NONE", "ESTOP", "BATTLOW", "STALL"};

static const char* stateLabel(int code) {
  return (code >= 0 && code <= 4) ? STATE_LABELS[code] : "?";
}
static const char* faultLabel(int code) {
  return (code >= 0 && code <= 3) ? FAULT_LABELS[code] : "?";
}

#if ENABLE_UNO_HEALTH
void IRAM_ATTR onAliveEdge() { aliveEdges++; }
#endif

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
static void cors() {
  server.sendHeader("Access-Control-Allow-Origin", CORS_ORIGIN);
  server.sendHeader("Cache-Control", "no-store");
}

static void sendJson(int code, const String& body) {
  cors();
  server.send(code, "application/json", body);
}

// Escapes a string for JSON. Control characters MUST be escaped: a raw '\n'
// inside a JSON string makes /status unparseable by the drive pad.
static String jsonEscape(const String& in) {
  String out;
  out.reserve(in.length() + 8);
  for (size_t i = 0; i < in.length(); ++i) {
    const char c = in[i];
    switch (c) {
      case '"':  out += "\\\""; break;
      case '\\': out += "\\\\"; break;
      case '\n': out += "\\n"; break;
      case '\r': out += "\\r"; break;
      case '\t': out += "\\t"; break;
      default:
        if (static_cast<unsigned char>(c) < 0x20) {
          char esc[8];
          snprintf(esc, sizeof(esc), "\\u%04x", static_cast<unsigned>(c) & 0xFF);
          out += esc;
        } else {
          out += c;
        }
    }
  }
  return out;
}

// Optional bearer token for state-changing endpoints. The drive pad gets the
// token from flash; /status and /health stay open for dashboards and scripts.
static bool authorized() {
  if (strlen(API_TOKEN) == 0) return true;
  String supplied;
  if (server.hasHeader("X-Rover-Token")) {
    supplied = server.header("X-Rover-Token");
  } else if (server.hasArg("k")) {
    supplied = server.arg("k");
  }
  return supplied == API_TOKEN;
}

static void deny() {
  ++rejected;
  sendJson(401, "{\"ok\":false,\"error\":\"token required\"}");
}

static bool validCameraUrl(const String& u) {
  if (u.length() < 8 || u.length() > MAX_CAMERA_URL) return false;
  if (!u.startsWith("http://") && !u.startsWith("https://")) return false;
  for (size_t i = 0; i < u.length(); ++i) {
    const char c = u[i];
    if (c == '"' || c == '\\' || c == '<' || c == '>' || c == ' ' || c < 0x20) return false;
  }
  return true;
}

static void loadCamera() {
  prefs.begin("rover", true);
  cameraUrl = prefs.getString("camera", "");
  prefs.end();
}

static void saveCamera(const String& u) {
  prefs.begin("rover", false);
  prefs.putString("camera", u);
  prefs.end();
  cameraUrl = u;
}

// ---------------------------------------------------------------------------
// Uno telemetry: "T,<state>,<cmd>,<pwm>,<dist>,<mv>,<fault>*HH"
// ---------------------------------------------------------------------------
static void parseTelemetryLine(char* line) {
  if (line[0] != 'T') return;
  char* star = strchr(line, '*');
  if (star == nullptr || star[0] == '\0') return;
  if (star[1] == '\0' || star[2] == '\0' || star[3] != '\0') return;

  const int hi = rover::hexDigit(star[1]);
  const int lo = rover::hexDigit(star[2]);
  if (hi < 0 || lo < 0) return;
  const uint8_t expected = static_cast<uint8_t>((hi << 4) | lo);
  const uint8_t bodyLen = static_cast<uint8_t>(star - line);
  if (rover::crc8(line, bodyLen) != expected) {
    ++tlmCrcFailures;
    return;
  }
  *star = '\0';

  int state = 0, pwm = 0, dist = -1, mv = 0, fault = 0;
  int vL = 0, vR = 0, xMm = 0, yMm = 0, theta = 0, odoMm = 0;
  char cmd = 'S';
  const int fields = sscanf(line, "T,%d,%c,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d",
                            &state, &cmd, &pwm, &dist, &mv, &fault,
                            &vL, &vR, &xMm, &yMm, &theta, &odoMm);
  if (fields != 12) return;
  if (state < 0 || state > 4 || fault < 0 || fault > 3) return;
  if (cmd != 'F' && cmd != 'B' && cmd != 'L' && cmd != 'R' && cmd != 'S') cmd = '?';

  tlm.valid = true;
  tlm.at = millis();
  tlm.state = state;
  tlm.cmd = cmd;
  tlm.pwm = pwm;
  tlm.distCm = dist;
  tlm.batteryMv = mv;
  tlm.fault = fault;
  tlm.speedL = vL;
  tlm.speedR = vR;
  tlm.xMm = xMm;
  tlm.yMm = yMm;
  tlm.thetaDeg = theta;
  tlm.odoMm = odoMm;
}

static void serviceUnoSerial() {
  while (unoLink.available() > 0) {
    const int b = unoLink.read();
    if (b < 0) break;
    const char c = static_cast<char>(b);
    if (c == '\n' || c == '\r') {
      if (tlmLen > 0) {
        tlmBuf[tlmLen] = '\0';
        parseTelemetryLine(tlmBuf);
        tlmLen = 0;
      }
    } else if (tlmLen < sizeof(tlmBuf) - 1) {
      tlmBuf[tlmLen++] = c;
    } else {
      tlmLen = 0;
      ++tlmOverflows;
    }
  }
}

static void serviceUnoHealth() {
#if ENABLE_UNO_HEALTH
  unoFaultPin = (digitalRead(UNO_FAULT_PIN) == LOW);
  if ((millis() - healthWindowStart) < 1000) return;
  const uint32_t edges = aliveEdges;
  aliveEdges = 0;
  healthWindowStart = millis();
  heartbeatHz = edges / 2.0f;  // square wave: two edges per period
  unoAlive = heartbeatHz > 50.0f;
  if (unoAlive) unoWired = true;
#endif
}

static void ledTask() {
  const bool active = (millis() - lastCmdAt) < rover::kLinkWatchdogMs;
  digitalWrite(STATUS_LED_PIN, active ? HIGH : ((millis() % 1000) < 500 ? HIGH : LOW));
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------
static void handleRoot() {
  server.sendHeader("Cache-Control", "no-store, must-revalidate");
  server.sendHeader("X-Content-Type-Options", "nosniff");
  String page(INDEX_HTML);
  page.replace("__TOKEN__", API_TOKEN);
  server.send(200, "text/html; charset=utf-8", page);
}

static void handleStatus() {
  String j = "{";
  j += "\"fw\":\"" FW_VERSION "\"";
  j += ",\"uptime_ms\":" + String(millis());
  j += ",\"ssid\":\"" AP_SSID "\"";
  j += ",\"ip\":\"" + WiFi.softAPIP().toString() + "\"";
  j += ",\"clients\":" + String(WiFi.softAPgetStationNum());
  j += ",\"forwarded\":" + String(forwarded);
  j += ",\"rejected\":" + String(rejected);
  j += ",\"last_cmd\":\"" + jsonEscape(String(lastCmdText)) + "\"";
  j += ",\"last_cmd_age_ms\":" + String((millis() - lastCmdAt));
  j += ",\"camera\":\"" + jsonEscape(cameraUrl) + "\"";
  j += ",\"free_heap\":" + String(ESP.getFreeHeap());

  j += ",\"uno\":{";
  j += "\"alive\":";
  j += unoAlive ? "true" : "false";
  j += ",\"wired\":";
  j += unoWired ? "true" : "false";
  j += ",\"hz\":" + String(heartbeatHz, 1);
  j += ",\"fault_pin\":";
  j += unoFaultPin ? "true" : "false";
  j += ",\"has_telemetry\":";
  j += tlm.valid ? "true" : "false";
  j += ",\"telemetry_age_ms\":";
  j += tlm.valid ? String(millis() - tlm.at) : String(-1);
  j += ",\"state\":\"";
  j += stateLabel(tlm.state);
  j += "\",\"fault\":\"";
  j += faultLabel(tlm.fault);
  j += "\",\"cmd\":\"";
  j += tlm.cmd;
  j += "\",\"pwm\":";
  j += String(tlm.pwm);
  j += ",\"dist_cm\":";
  j += String(tlm.distCm);
  j += ",\"battery_mv\":";
  j += String(tlm.batteryMv);
  j += ",\"speed_l_mm_s\":";
  j += String(tlm.speedL);
  j += ",\"speed_r_mm_s\":";
  j += String(tlm.speedR);
  j += ",\"odo_x_mm\":";
  j += String(tlm.xMm);
  j += ",\"odo_y_mm\":";
  j += String(tlm.yMm);
  j += ",\"odo_theta_deg\":";
  j += String(tlm.thetaDeg);
  j += ",\"odometer_mm\":";
  j += String(tlm.odoMm);
  j += ",\"crc_failures\":";
  j += String(tlmCrcFailures);
  j += ",\"overflows\":";
  j += String(tlmOverflows);
  j += "}";

  j += "}";
  sendJson(200, j);
}

static void handleCmd() {
  if (!authorized()) {
    deny();
    return;
  }
  if (!server.hasArg("c")) {
    ++rejected;
    sendJson(400, "{\"ok\":false,\"error\":\"missing c\"}");
    return;
  }

  const String raw = server.arg("c");  // no trim: the parser is strict
  rover::Packet p;
  if (raw.length() > 8 || !rover::parsePacket(raw.c_str(), (uint8_t)raw.length(), p)) {
    ++rejected;
    Serial.printf("[ESP32] REJECT \"%s\" (whitelist)\n", raw.c_str());
    sendJson(400, "{\"ok\":false,\"error\":\"invalid command\"}");
    return;
  }

  // Rate limit protects the half-duplex AVR link and the telemetry window.
  // A stop is never delayed.
  if (p.cmd != 'S' && (millis() - lastForwardMs) < CMD_MIN_INTERVAL_MS) {
    ++rejected;
    sendJson(429, "{\"ok\":false,\"error\":\"rate limited\"}");
    return;
  }

  char frame[12];
  const uint8_t n = rover::buildFrame(p.cmd, p.speed, p.hasSpeed, frame, sizeof(frame));
  if (n == 0) {
    ++rejected;
    sendJson(500, "{\"ok\":false,\"error\":\"frame build failed\"}");
    return;
  }
  unoLink.write(reinterpret_cast<const uint8_t*>(frame), n);
  unoLink.flush();

  lastForwardMs = millis();
  ++forwarded;
  lastCmdAt = millis();
  snprintf(lastCmdText, sizeof(lastCmdText), "%.*s", static_cast<int>(n > 0 ? n - 1 : 0), frame);

  Serial.printf("[ESP32] %s GET /cmd?c=%s --> OK --> UART TX2 \"%s\" (fw=%lu rej=%lu)\n",
                server.client().remoteIP().toString().c_str(), raw.c_str(), frame,
                (unsigned long)forwarded, (unsigned long)rejected);

  String body = "{\"ok\":true,\"cmd\":\"";
  body += p.cmd;
  body += "\",\"speed\":";
  body += String(p.cmd == 'S' ? 0 : (p.hasSpeed ? rover::clampSpeed(p.speed) : rover::kDefaultSpeed));
  body += ",\"frame\":\"";
  body += jsonEscape(String(lastCmdText));
  body += "\"}";
  sendJson(200, body);
}

static void handleCam() {
  if (!authorized()) {
    deny();
    return;
  }
  if (server.hasArg("u")) {
    String u = server.arg("u");
    u.trim();
    if (!validCameraUrl(u)) {
      sendJson(400, "{\"ok\":false,\"error\":\"url must be http(s) and <=192 chars\"}");
      return;
    }
    saveCamera(u);
    Serial.printf("[ESP32] CAM saved: %s\n", u.c_str());
    sendJson(200, "{\"ok\":true,\"camera\":\"" + jsonEscape(u) + "\"}");
    return;
  }
  sendJson(200, "{\"ok\":true,\"camera\":\"" + jsonEscape(cameraUrl) + "\"}");
}

static void handleHealth() {
  cors();
  server.send(200, "text/plain", "ok");
}

static void handleNotFound() {
#if ENABLE_CAPTIVE_PORTAL
  server.sendHeader("Location", String("http://") + WiFi.softAPIP().toString() + "/", true);
  server.send(302, "text/plain", "");
#else
  sendJson(404, "{\"ok\":false,\"error\":\"not found\"}");
#endif
}

// ---------------------------------------------------------------------------
// setup / loop
// ---------------------------------------------------------------------------
void setup() {
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);

#if ENABLE_UNO_HEALTH
  pinMode(UNO_ALIVE_PIN, INPUT);
  pinMode(UNO_FAULT_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(UNO_ALIVE_PIN), onAliveEdge, CHANGE);
  healthWindowStart = millis();
#endif

  Serial.begin(SERIAL_BAUD);
  delay(150);
  Serial.println();
  Serial.printf("[ESP32] BOOT fw=%s\n", FW_VERSION);

  unoLink.begin(LINK_BAUD, SERIAL_8N1, LINK_RX_PIN, LINK_TX_PIN);

  loadCamera();

  WiFi.mode(WIFI_AP);
  WiFi.setSleep(false);
  const bool apOk = WiFi.softAP(AP_SSID, AP_PASSWORD, AP_CHANNEL, 0, AP_MAX_CLIENTS);
  Serial.printf("[ESP32] SoftAP %s -> %s (%s)\n", AP_SSID,
                WiFi.softAPIP().toString().c_str(), apOk ? "up" : "FAILED");

#if ENABLE_CAPTIVE_PORTAL
  dns.start(53, "*", WiFi.softAPIP());
  Serial.println("[ESP32] captive portal enabled");
#endif

#if ENABLE_MDNS
  if (MDNS.begin("rover")) {
    MDNS.addService("http", "tcp", 80);
    Serial.println("[ESP32] mDNS http://rover.local");
  }
#endif

#if ENABLE_OTA
  ArduinoOTA.setHostname(OTA_HOSTNAME);
  if (strlen(OTA_PASSWORD) > 0) ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.onStart([]() {
    Serial.println("[ESP32] OTA start - motors will stop on command timeout");
  });
  ArduinoOTA.onEnd([]() { Serial.println("[ESP32] OTA done, rebooting"); });
  ArduinoOTA.onError([](ota_error_t error) { Serial.printf("[ESP32] OTA error %u\n", error); });
  ArduinoOTA.begin();
  Serial.printf("[ESP32] OTA ready: %s.local (password %s)\n", OTA_HOSTNAME,
                strlen(OTA_PASSWORD) ? "set" : "none");
#endif

  server.on("/", HTTP_GET, handleRoot);
  server.on("/cmd", HTTP_GET, handleCmd);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/cam", HTTP_GET, handleCam);
  server.on("/health", HTTP_GET, handleHealth);
  server.on("/favicon.ico", HTTP_GET, []() { server.send(204, "text/plain", ""); });
  server.onNotFound(handleNotFound);
  server.begin();
  Serial.println("[ESP32] HTTP :80 ready | UART2 9600 8N1 TX=GPIO17 -> Uno D4 (CRC on)");
  Serial.printf("[ESP32] camera: %s\n", cameraUrl.length() ? cameraUrl.c_str() : "(not set)");
  Serial.printf("[ESP32] uno health pins: alive=GPIO%d fault=GPIO%d\n", UNO_ALIVE_PIN, UNO_FAULT_PIN);
}

void loop() {
  server.handleClient();
#if ENABLE_CAPTIVE_PORTAL
  dns.processNextRequest();
#endif
  serviceUnoSerial();
  serviceUnoHealth();
#if ENABLE_OTA
  ArduinoOTA.handle();
#endif
  ledTask();
  delay(1);
}
