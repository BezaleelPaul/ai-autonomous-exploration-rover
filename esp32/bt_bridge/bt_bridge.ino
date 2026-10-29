/*
 * AI Rover - ESP32 DevKit V1 (30-pin) wireless bridge
 *
 * Link: laptop Bluetooth Classic SPP  ->  ESP32 UART2 (GPIO17 TX)  ->  Arduino UNO D4
 *       device name "AI_Rover_Control", 9600 baud, 8N1, one-way (no return channel).
 *
 * Wiring:  ESP32 GPIO17 (TX2) -> Arduino UNO D4 (SoftwareSerial RX)
 *          ESP32 GND          -> Arduino UNO GND   (common ground is mandatory)
 *
 * Behaviour:
 *   - drains the Bluetooth RX buffer every pass (bounded, never blocks)
 *   - relays only validated motion characters F/B/L/R/S (case-insensitive),
 *     latest-wins per pass so a burst can never queue stale motion
 *   - counts and discards noise / framing bytes instead of forwarding them
 *   - no local queue to overflow: the Arduino's communication watchdog
 *     (motion_safety.ino, COMM_TIMEOUT_MS) produces the stop when this link dies
 *
 * The USB serial port (115200) is debug telemetry only - it is not wired.
 */

#include "BluetoothSerial.h"

#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error "Bluetooth Classic is disabled: select an ESP32 Dev Module board and a BLE-off config"
#endif

static const char BT_DEVICE_NAME[] = "AI_Rover_Control";

const long LINK_BAUD = 9600;
const int UART2_TX_PIN = 17;
const int UART2_RX_PIN = -1;
const long DEBUG_BAUD = 115200;
const int RX_DRAIN_LIMIT = 64;
const unsigned long HEALTH_MS = 2000;

BluetoothSerial SerialBT;

unsigned long gForwarded = 0;
unsigned long gDropped = 0;
unsigned long gLastHealth = 0;
unsigned long gLastRelay = 0;
bool gHadClient = false;
char gLastCommand = 0;

bool isValidMotion(char c) {
  return c == 'F' || c == 'B' || c == 'L' || c == 'R' || c == 'S';
}

void relayFromBluetooth() {
  int drained = 0;
  int dropped = 0;
  char lastValid = 0;
  while (SerialBT.available() > 0 && drained < RX_DRAIN_LIMIT) {
    int raw = SerialBT.read();
    if (raw < 0) break;
    drained++;
    char c = (char)raw;
    if (c == '\n' || c == '\r' || c == '\t' || c == ' ') continue;
    if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A');
    if (isValidMotion(c)) {
      lastValid = c;
    } else {
      dropped++;
    }
  }
  if (dropped > 0) {
    gDropped += (unsigned long)dropped;
    Serial.print("DROP:");
    Serial.println(dropped);
  }
  if (lastValid != 0) {
    Serial2.write((uint8_t)lastValid);
    gForwarded++;
    gLastCommand = lastValid;
    gLastRelay = millis();
    Serial.print("RELAY:");
    Serial.println(lastValid);
  }
}

void reportHealth() {
  bool client = SerialBT.hasClient();
  if (client != gHadClient) {
    gHadClient = client;
    Serial.print("BT:");
    Serial.println(client ? "CONNECTED" : "IDLE");
  }
  if (millis() - gLastHealth < HEALTH_MS) return;
  gLastHealth = millis();
  Serial.print("STAT fwd=");
  Serial.print(gForwarded);
  Serial.print(" drop=");
  Serial.print(gDropped);
  Serial.print(" last=");
  Serial.print(gLastCommand);
  Serial.print(" client=");
  Serial.println(client ? 1 : 0);
}

void setup() {
  Serial.begin(DEBUG_BAUD);
  Serial2.begin(LINK_BAUD, SERIAL_8N1, UART2_RX_PIN, UART2_TX_PIN);
  if (!SerialBT.begin(BT_DEVICE_NAME)) {
    Serial.println("BT:FAIL");
    while (true) {
      delay(1000);
    }
  }  Serial.print("BT:READY ");
  Serial.println(BT_DEVICE_NAME);
}

void loop() {
  relayFromBluetooth();
  reportHealth();
}
