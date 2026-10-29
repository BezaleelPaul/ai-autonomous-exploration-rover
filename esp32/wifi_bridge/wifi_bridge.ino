/*
 * AI Rover - ESP32 DevKit V1 WiFi web bridge (two-tier stack)
 *
 * Tier 1 reaches the rover over WiFi instead of Bluetooth:
 *   the phone joins the "AI_Rover_Control" soft-AP (WPA2) and opens
 *   http://192.168.4.1/ - the on-page F/L/R/S buttons drive the rover;
 *   GET /cmd?c=F is the machine API used by the perception node when
 *   perception.serial_mode is "http".
 * Camera: the page carries a CAMERA panel that takes the phone's IP Webcam
 *   URL (http://<PHONE_IP>:8080/video) and renders that stream beside the
 *   drive pad. GET /cam?u=<url> stores it in NVS so it survives a reboot;
 *   GET /status reports it as "cam". YOLO analysis stays on the laptop
 *   (scripts/dashboard.py --ip-webcam <url>) - the ESP32 only relays video.
 * Output: UART2 GPIO17 -> Arduino D4 (SoftwareSerial RX), 9600 8N1, one-way,
 *   same whitelist
 * and latest-wins rules as the Bluetooth bridge. Debug (HTTP requests,
 * relay counters) goes to the USB Serial port at 115200.
 */

#include <Preferences.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include "page_html.h"

/*
 * Station credentials are deliberately NOT stored in this repository: fill
 * them in locally before flashing. tests/test_redteam_docs_config.py fails
 * the build if either placeholder is replaced with a real value.
 */
const char *STA_SSID = "YOUR_WIFI_SSID";
const char *STA_PASS = "YOUR_WIFI_PASSWORD";
const char *AP_SSID = "AI_Rover_Control";
const char *AP_PASS = "rover1234";
const char *DEFAULT_CAM_URL = "http://192.168.1.10:8080/video";
const int AP_CHANNEL = 6;
const int UART2_TX_PIN = 17;
const long LINK_BAUD = 9600;
const unsigned long STATUS_LOG_MS = 2000;
const unsigned long STA_TIMEOUT_MS = 15000;
const int CAM_URL_MAX = 160;
const int LED_PIN = 2;
unsigned long gLedOffMs = 0;

WebServer server(80);
Preferences prefs;

unsigned long gForwarded = 0;
unsigned long gRejected = 0;
char gLastCommand = '-';
unsigned long gLastLogMs = 0;
bool staPending = false;
bool staUp = false;
unsigned long staStartMs = 0;
int gStaReason = 0;
String gCamUrl;

bool validCmd(char c) {
  return c == 'F' || c == 'B' || c == 'L' || c == 'R' || c == 'S';
}

char normalizeCmd(char c) {
  if (c >= 'a' && c <= 'z') return (char)(c - 'a' + 'A');
  return c;
}

void relay(const String &cmd) {
  Serial2.print(cmd);
  digitalWrite(LED_PIN, HIGH);
  gLedOffMs = millis() + 100;
  gForwarded++;
  gLastCommand = cmd.charAt(0);
}


void handlePage() { server.send_P(200, "text/html", PAGE_HTML); }

/*
 * Accepts "F" .. "S" alone or with an optional PWM speed suffix "F200"
 * (letter + digits 0..255). The suffix rides the same one-wire link; the
 * Arduino's chunk parser already understands it. Anything else is BAD.
 */
void handleCmd() {
  if (!server.hasArg("c")) {
    server.send(400, "text/plain", "BAD");
    return;
  }
  String raw = server.arg("c");
  raw.trim();
  if (raw.length() < 1 || raw.length() > 4) {
    gRejected++;
    server.send(400, "text/plain", "BAD");
    return;
  }
  char c = normalizeCmd(raw.charAt(0));
  if (!validCmd(c)) {
    gRejected++;
    server.send(400, "text/plain", "BAD");
    return;
  }
  for (unsigned int i = 1; i < raw.length(); i++) {
    if (!isDigit(raw.charAt(i))) {
      gRejected++;
      server.send(400, "text/plain", "BAD");
      return;
    }
  }
  if (raw.length() > 1 && raw.substring(1).toInt() > 255) {
    gRejected++;
    server.send(400, "text/plain", "BAD");
    return;
  }
  relay(raw);
  Serial.print("HTTP:");
  Serial.println(raw);
  String reply = "OK ";
  reply += raw;
  server.send(200, "text/plain", reply);
}

void storeCam() {
  prefs.begin("rover", false);
  prefs.putString("cam", gCamUrl);
  prefs.end();
}

void sendCamJson(bool ok, const char *why) {
  String json = "{\"ok\":";
  json += ok ? "true" : "false";
  json += ",\"cam\":\"";
  json += ok ? String(gCamUrl) : String(why);
  json += "\"}";
  server.send(ok ? 200 : 400, "application/json", json);
}

/* /cam?u=<url> - store the phone IP Webcam URL ("" clears, NVS persists it). */
void handleCam() {
  if (!server.hasArg("u")) {
    sendCamJson(false, "missing u");
    return;
  }
  String u = server.arg("u");
  u.trim();
  if (u.length() == 0) {
    gCamUrl = "";
    storeCam();
    Serial.println("CAM:CLEAR");
    sendCamJson(true, "");
    return;
  }
  if (u.length() > CAM_URL_MAX) {
    sendCamJson(false, "url too long");
    return;
  }
  if (!u.startsWith("http://") && !u.startsWith("https://")) {
    sendCamJson(false, "url must start with http:// or https://");
    return;
  }
  for (unsigned int i = 0; i < u.length(); i++) {
    char c = u.charAt(i);
    if (c == '"' || c == '\\' || c < 32) {
      sendCamJson(false, "url contains an illegal character");
      return;
    }
  }
  gCamUrl = u;
  storeCam();
  Serial.print("CAM:SET ");
  Serial.println(gCamUrl);
  sendCamJson(true, "");
}

void handleStatus() {
  String json = "{\"uptime_ms\":";
  json += String(millis());
  json += ",\"forwarded\":";
  json += String(gForwarded);
  json += ",\"rejected\":";
  json += String(gRejected);
  json += ",\"last\":\"";
  json += gLastCommand;
  json += "\",\"sta\":\"";
  json += staUp ? WiFi.localIP().toString() : "-";
  json += "\",\"cam\":\"";
  json += gCamUrl;
  json += "\"}";
  server.send(200, "application/json", json);
}

void handleNotFound() { server.send(404, "text/plain", "NOT FOUND"); }

void onStaDisconnect(WiFiEvent_t event, WiFiEventInfo_t info) {
  gStaReason = info.wifi_sta_disconnected.reason;
  Serial.print("STA:EVT reason=");
  Serial.println(gStaReason);
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  Serial.begin(115200);
  Serial2.begin(LINK_BAUD, SERIAL_8N1, -1, UART2_TX_PIN);
  prefs.begin("rover", false);
  gCamUrl = prefs.getString("cam", DEFAULT_CAM_URL);
  prefs.end();
  WiFi.mode(WIFI_AP_STA);
  WiFi.onEvent(onStaDisconnect, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
  WiFi.setSleep(false);
  bool apOk = WiFi.softAP(AP_SSID, AP_PASS, AP_CHANNEL);
  if (strlen(STA_SSID) > 0 && strncmp(STA_SSID, "YOUR_WIFI_SSID", 14) != 0) {
    WiFi.begin(STA_SSID, STA_PASS);
    staPending = true;
    staStartMs = millis();
    Serial.print("STA:JOINING ssid=");
    Serial.println(STA_SSID);
  }
  server.on("/", HTTP_GET, handlePage);
  server.on("/cmd", HTTP_GET, handleCmd);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/cam", HTTP_GET, handleCam);
  server.onNotFound(handleNotFound);
  server.begin();
  Serial.print("AP:RESULT ");
  Serial.println(apOk ? "OK" : "FAIL");
  wifi_config_t apConf;
  if (esp_wifi_get_config(WIFI_IF_AP, &apConf) == ESP_OK) {
    Serial.print("AP:CH ");
    Serial.println(apConf.ap.channel);
  }
  Serial.print("AP:MAC ");
  Serial.println(WiFi.softAPmacAddress());
  Serial.print("AP:READY http://");
  Serial.print(WiFi.softAPIP());
  Serial.print(" ssid=");
  Serial.println(AP_SSID);
  Serial.print("CAM:LOADED ");
  Serial.println(gCamUrl);
}

void serviceSta(unsigned long now) {
  if (staUp || !staPending) return;
  if (WiFi.status() == WL_CONNECTED) {
    staUp = true;
    staPending = false;
    Serial.print("STA:OK ip=");
    Serial.println(WiFi.localIP());
  } else if (now - staStartMs >= STA_TIMEOUT_MS) {
    staPending = false;
    Serial.print("STA:FAIL status=");
    Serial.print((int)WiFi.status());
    Serial.print(" reason=");
    Serial.println(gStaReason);
  }
}

void loop() {
  server.handleClient();
  unsigned long now = millis();
  if (gLedOffMs > 0 && now >= gLedOffMs) {
    digitalWrite(LED_PIN, LOW);
    gLedOffMs = 0;
  }
  serviceSta(now);
  if (now - gLastLogMs >= STATUS_LOG_MS) {
    gLastLogMs = now;
    Serial.print("STAT fwd=");
    Serial.print(gForwarded);
    Serial.print(" rej=");
    Serial.print(gRejected);
    Serial.print(" last=");
    Serial.print(gLastCommand);
    Serial.print(" clients=");
    Serial.print(WiFi.softAPgetStationNum());
    Serial.print(" sta=");
    Serial.println(staUp ? WiFi.localIP().toString().c_str() : "-");
  }
}
