/*
 * AI Rover - Arduino UNO R3 motion & safety executive (TB6612FNG build)
 *
 * Input : SoftwareSerial D4 (RX) <- ESP32 TX2 GPIO17, 9600 8N1, F/B/L/R/S
 *         with optional PWM speed suffix (e.g. "F200", the Wi-Fi pad's
 *         slider). Chunks are framed by a 15 ms inter-byte silence gap, so a
 *         multi-byte command split across buffer drains can never be
 *         misparsed (e.g. "F2"/"00" driving at PWM 2). Same chars over the
 *         USB Serial work as a bench bring-up fallback.
 *         SoftwareSerial D12 (TX) unused - this link is one-way
 * Output: TB6612FNG dual MOSFET H-bridge, STBY -> 5V, + USB Serial telemetry
 * Sensor: HC-SR04  VCC->5V, GND->GND, TRIG->D2, ECHO->D3
 *
 * Pin map (production blueprint, TB6612FNG replaces the L298N):
 *   D5 PWMA (left PWM)   D6 AIN1  D7 AIN2   (left direction)
 *   D9 PWMB (right PWM)  D8 BIN1  D10 BIN2  (right direction)
 *
 * Safety rule (hard override): a forward command 'F' is refused and movement is
 * cut whenever the ultrasonic reading is below OBSTACLE_STOP_CM, and also when
 * the echo is invalid (never drive on a dead sensor). 'B', 'L', 'R' and 'S'
 * always execute as received, so the rover can reverse or turn out of a front
 * obstacle. A 500 ms communication watchdog also stops the motors, so a dead
 * Wi-Fi/Bluetooth bridge can never leave the rover driving (production
 * blueprint: the wireless pad re-sends the held command every 200 ms; the
 * laptop tiers send their own heartbeats and keep the 3 s config gate).
 *
 * Telemetry (USB Serial Monitor, 9600 baud): DIST:<cm>, CMD:<c> STATE:<...>,
 * STATUS:OK|STOP|ERROR and ALERT:OBSTACLE lines on every safety override.
 * The ultrasonic service is a micros()/millis() state machine: the loop never
 * blocks waiting for an echo (there is no pulseIn anywhere in this sketch).
 */

#include <SoftwareSerial.h>

const int SS_RX_PIN = 4;   // <- ESP32 TX2 GPIO17 (moved off D2: D2/D3 are the HC-SR04 now)
const int SS_TX_PIN = 12;  // unused - this link is one-way
const long LINK_BAUD = 9600;

const int TRIG_PIN = 2;
const int ECHO_PIN = 3;

// TB6612FNG control pins (blueprint map)
const int PWMA = 5;   // left motor speed (PWM)
const int AIN1 = 6;   // left motor direction 1
const int AIN2 = 7;   // left motor direction 2
const int PWMB = 9;   // right motor speed (PWM)
const int BIN1 = 8;   // right motor direction 1
const int BIN2 = 10;  // right motor direction 2
const int DEFAULT_SPEED = 200;

const float OBSTACLE_STOP_CM = 15.0;
const bool BLOCK_ON_INVALID_ECHO = true;
const unsigned long COMM_TIMEOUT_MS = 500;
const unsigned long TELEMETRY_MS = 200;
const unsigned long DISTANCE_PERIOD_MS = 60;
const unsigned long ECHO_TIMEOUT_US = 30000;
const unsigned long ERROR_REPLY_MS = 100;
const unsigned long ALERT_INTERVAL_MS = 500;
const unsigned long CHUNK_GAP_MS = 15;
const int RX_BUF_MAX = 16;

enum PingState { PING_IDLE, PING_WAIT_RISE, PING_WAIT_FALL };
enum ExecState { STATE_GO, STATE_STOP, STATE_BLOCKED, STATE_TIMEOUT };

const char *stateName(ExecState s) {
  switch (s) {
    case STATE_GO: return "GO";
    case STATE_BLOCKED: return "BLOCKED";
    case STATE_TIMEOUT: return "TIMEOUT";
    default: return "STOP";
  }
}

SoftwareSerial link(SS_RX_PIN, SS_TX_PIN);

PingState pingState = PING_IDLE;
ExecState execState = STATE_STOP;
float distanceCm = -1.0;
bool distanceValid = false;
unsigned long triggerMicros = 0;
unsigned long riseMicros = 0;
unsigned long lastPingMs = 0;
unsigned long lastCmdMs = 0;
unsigned long lastTelemetryMs = 0;
unsigned long lastErrorMs = 0;
unsigned long lastAlertMs = 0;
char currentCmd = 'S';
int activeSpeed = DEFAULT_SPEED;
char rxBuf[RX_BUF_MAX];
int rxLen = 0;
unsigned long lastByteMs = 0;
long speedAccum = -1;  // digits accumulated for the next command (-1 = none)

void stopMotors() {
  digitalWrite(AIN1, LOW);
  digitalWrite(AIN2, LOW);
  digitalWrite(BIN1, LOW);
  digitalWrite(BIN2, LOW);
  analogWrite(PWMA, 0);
  analogWrite(PWMB, 0);
}

void drive(char cmd) {
  analogWrite(PWMA, activeSpeed);
  analogWrite(PWMB, activeSpeed);
  switch (cmd) {
    case 'F':
      digitalWrite(AIN1, HIGH);
      digitalWrite(AIN2, LOW);
      digitalWrite(BIN1, HIGH);
      digitalWrite(BIN2, LOW);
      break;
    case 'B':
      digitalWrite(AIN1, LOW);
      digitalWrite(AIN2, HIGH);
      digitalWrite(BIN1, LOW);
      digitalWrite(BIN2, HIGH);
      break;
    case 'L':
      digitalWrite(AIN1, LOW);
      digitalWrite(AIN2, HIGH);
      digitalWrite(BIN1, HIGH);
      digitalWrite(BIN2, LOW);
      break;
    case 'R':
      digitalWrite(AIN1, HIGH);
      digitalWrite(AIN2, LOW);
      digitalWrite(BIN1, LOW);
      digitalWrite(BIN2, HIGH);
      break;
    default:
      stopMotors();
      break;
  }
}

bool validCmd(char c) {
  return c == 'F' || c == 'B' || c == 'L' || c == 'R' || c == 'S';
}

void drainSource(Stream &src, unsigned long &lastByteMs) {
  while (src.available() > 0) {
    int raw = src.read();
    if (raw < 0) break;
    if (rxLen < RX_BUF_MAX - 1) rxBuf[rxLen++] = (char)raw;
    lastByteMs = millis();
  }
}

void handleLink() {
  unsigned long now = millis();
  drainSource(link, lastByteMs);
  drainSource(Serial, lastByteMs);
  if (rxLen == 0) return;
  if (now - lastByteMs < CHUNK_GAP_MS) return;  // chunk still arriving

  // Parse the completed chunk as ONE unit: a single distinct command
  // (plus optional speed digits 0..255). Mixed commands, unknown bytes or
  // overspeed are malformed: STOP + STATUS:ERROR (red-team H3).
  int cmds = 0;
  int others = 0;
  char first = 0;
  bool mixed = false;
  for (int i = 0; i < rxLen; i++) {
    char c = rxBuf[i];
    if (c == '\n' || c == '\r' || c == '\t' || c == ' ') continue;
    if (c >= '0' && c <= '9') {
      if (speedAccum < 0) speedAccum = c - '0';
      else if (speedAccum <= 255) speedAccum = speedAccum * 10 + (c - '0');
      if (speedAccum > 255) speedAccum = 9999;  // bounded sentinel
      continue;
    }
    if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A');
    if (validCmd(c)) {
      if (cmds == 0) first = c;
      else if (first != c) mixed = true;
      cmds++;
    } else {
      others++;
    }
  }
  rxLen = 0;

  if (others > 0 || (cmds > 1 && mixed) || speedAccum > 255) {
    currentCmd = 'S';
    stopMotors();
    speedAccum = -1;
    if (now - lastErrorMs >= ERROR_REPLY_MS) {
      lastErrorMs = now;
      Serial.println("STATUS:ERROR");
    }
    return;
  }
  if (cmds >= 1) {
    currentCmd = first;
    if (speedAccum >= 0) activeSpeed = (int)speedAccum;
    speedAccum = -1;
    lastCmdMs = millis();
  } else if (speedAccum >= 0) {
    // speed-only chunk: retune the PWM but never refresh the watchdog
    activeSpeed = (int)speedAccum;
    speedAccum = -1;
  }
}

void startPing(unsigned long nowMs) {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  lastPingMs = nowMs;
  triggerMicros = micros();
  pingState = PING_WAIT_RISE;
}

void serviceUltrasonic(unsigned long nowMs) {
  switch (pingState) {
    case PING_IDLE:
      if (nowMs - lastPingMs >= DISTANCE_PERIOD_MS) startPing(nowMs);
      break;
    case PING_WAIT_RISE:
      if (digitalRead(ECHO_PIN) == HIGH) {
        riseMicros = micros();
        pingState = PING_WAIT_FALL;
      } else if (micros() - triggerMicros > ECHO_TIMEOUT_US) {
        distanceValid = false;
        distanceCm = -1.0;
        pingState = PING_IDLE;
      }
      break;
    case PING_WAIT_FALL:
      if (digitalRead(ECHO_PIN) == LOW) {
        unsigned long duration = micros() - riseMicros;
        if (duration > ECHO_TIMEOUT_US || duration == 0) {
          distanceValid = false;
          distanceCm = -1.0;
        } else {
          distanceCm = (float)duration * 0.0343f / 2.0f;
          distanceValid = true;
        }
        pingState = PING_IDLE;
      } else if (micros() - riseMicros > ECHO_TIMEOUT_US) {
        distanceValid = false;
        distanceCm = -1.0;
        pingState = PING_IDLE;
      }
      break;
  }
}

void emitAlert(unsigned long nowMs) {
  if (nowMs - lastAlertMs < ALERT_INTERVAL_MS) return;
  lastAlertMs = nowMs;
  Serial.print("ALERT:OBSTACLE dist=");
  if (distanceValid) Serial.print(distanceCm, 1);
  else Serial.print(-1);
  Serial.print("cm cmd=");
  Serial.println(currentCmd);
}

void evaluateSafety(unsigned long nowMs) {
  bool commLost = (nowMs - lastCmdMs) > COMM_TIMEOUT_MS;
  bool sensorBlocked;
  if (distanceValid) sensorBlocked = distanceCm < OBSTACLE_STOP_CM;
  else sensorBlocked = BLOCK_ON_INVALID_ECHO;
  bool blocked = (currentCmd == 'F') && sensorBlocked;

  if (commLost) {
    currentCmd = 'S';
    stopMotors();
    execState = STATE_TIMEOUT;
  } else if (blocked) {
    stopMotors();
    execState = STATE_BLOCKED;
    emitAlert(nowMs);
  } else if (currentCmd == 'S') {
    stopMotors();
    execState = STATE_STOP;
  } else {
    drive(currentCmd);
    execState = STATE_GO;
  }
}

void emitTelemetry(unsigned long nowMs) {
  if (nowMs - lastTelemetryMs < TELEMETRY_MS) return;
  lastTelemetryMs = nowMs;
  Serial.print("DIST:");
  if (distanceValid) Serial.println(distanceCm, 1);
  else Serial.println(-1);
  Serial.print("CMD:");
  Serial.print(currentCmd);
  Serial.print(" STATE:");
  Serial.println(stateName(execState));
  if (execState == STATE_GO) Serial.println("STATUS:OK");
  else Serial.println("STATUS:STOP");
}

void setup() {
  Serial.begin(9600);
  link.begin(LINK_BAUD);
  pinMode(PWMA, OUTPUT);
  pinMode(AIN1, OUTPUT);
  pinMode(AIN2, OUTPUT);
  pinMode(PWMB, OUTPUT);
  pinMode(BIN1, OUTPUT);
  pinMode(BIN2, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  stopMotors();
  lastCmdMs = millis();
  Serial.println("BOOT:STOP");
}

void loop() {
  unsigned long now = millis();
  handleLink();
  serviceUltrasonic(now);
  evaluateSafety(now);
  emitTelemetry(now);
}
