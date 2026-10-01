/*
 * AI Visual Smart Rover — Arduino UNO controller
 * Hardware: UNO + L298N + HC-SR04 (+ optional SG90)
 *
 * Protocol (see docs/hardware_protocol.md):
 *   RX: 'F' forward, 'B' back, 'L' left, 'R' right, 'S' stop, each with an
 *       OPTIONAL PWM suffix 0..255 (e.g. 'L120'); bare char = active speed
 *       (DEFAULT_SPEED at boot). Newline optional; a chunk must hold ONE
 *       distinct command (plus digits) or it is malformed.
 *   TX: 'DIST:<cm>' every 200ms, 'STATUS:OK|STOP|ERROR',
 *       'TICKS:<left>,<right>' (wheel encoder counts, pins D2/D3)
 *
 * Safety: local emergency stop + communication timeout stop.
 * An invalid/no-echo ultrasonic reading (dist <= 0) blocks translation
 * (red-team C1: never drive on a dead sensor).
 */

// L298N pins
const int ENA = 5;
const int IN1 = 6;
const int IN2 = 7;
const int IN3 = 8;
const int IN4 = 9;
const int ENB = 10;

// HC-SR04 pins
const int TRIG_PIN = 11;
const int ECHO_PIN = 12;

// Config (tune to match config/thresholds.yaml)
const float EMERGENCY_STOP_CM = 15.0;
const unsigned long COMM_TIMEOUT_MS = 3000;
const unsigned long TELEMETRY_MS = 200;
const int DEFAULT_SPEED = 200;
// Bound on STATUS:ERROR replies per malformed chunk (TX at 9600 baud must
// never stall the control loop for long).
const int MAX_ERROR_REPLIES = 4;

unsigned long lastCmdTime = 0;
unsigned long lastTelemetry = 0;
char currentCmd = 'S';

// Wheel encoders (Phase 9+, docs/future-work/30): D2/D3 = INT0/INT1.
// Inert until encoders are fitted; counts reported as TICKS:<l>,<r>.
const int ENC_L_PIN = 2;
const int ENC_R_PIN = 3;
volatile unsigned long encTicksL = 0;
volatile unsigned long encTicksR = 0;

void encISR_L() { encTicksL++; }
void encISR_R() { encTicksR++; }

// --- Protocol v2 speed channel + Phase 9+ P velocity loop -----------------
// Optional per-command PWM suffix (0..255); digits NEVER refresh the
// watchdog. Velocity loop (docs/future-work/30 §2): per-wheel P correction
// toward VEL_TARGET_TPS while driving F/B with encoders enabled; silent
// encoders fall back to open-loop activeSpeed (fail-safe, never latches).
// Gains/setpoint synced to config/config.yaml control: by contract test.
bool encodersEnabled = false;
const float VEL_KP = 1.2;
const int VEL_TARGET_TPS = 50;
const int VEL_PWM_FF = 150;
const int VEL_PERIOD_MS = 50;
const int VEL_DEAD_PERIODS = 6;

int activeSpeed = DEFAULT_SPEED;  // sticky PWM for motion commands
int pwmCmdL = DEFAULT_SPEED;      // per-wheel PWM applied by drive()
int pwmCmdR = DEFAULT_SPEED;
unsigned long lastVelCtl = 0;
unsigned long prevEncL = 0;
unsigned long prevEncR = 0;
int velDead = 0;
long speedAccum = -1;  // digits accumulated for the next command (-1 = none)

void setup() {
  Serial.begin(9600);
  pinMode(ENA, OUTPUT); pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT); pinMode(ENB, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT); pinMode(ECHO_PIN, INPUT);
  stopMotors();
  pinMode(ENC_L_PIN, INPUT_PULLUP);
  pinMode(ENC_R_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(ENC_L_PIN), encISR_L, FALLING);
  attachInterrupt(digitalPinToInterrupt(ENC_R_PIN), encISR_R, FALLING);
  lastCmdTime = millis();
}

float readDistance() {
  digitalWrite(TRIG_PIN, LOW); delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long dur = pulseIn(ECHO_PIN, HIGH, 30000); // 30ms timeout
  if (dur == 0) return -1.0;
  return (dur * 0.0343) / 2.0;
}

void stopMotors() {
  digitalWrite(IN1, LOW); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, LOW);
  analogWrite(ENA, 0); analogWrite(ENB, 0);
}

void drive(char cmd) {
  analogWrite(ENA, pwmCmdL);
  analogWrite(ENB, pwmCmdR);
  switch (cmd) {
    case 'F': digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
              digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW); break;
    case 'B': digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
              digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH); break;
    case 'L': digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
              digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW); break;
    case 'R': digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
              digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH); break;
    default: stopMotors(); break;
  }
}

bool validCmd(char c) {
  c = toupper(c);
  return c=='F'||c=='B'||c=='L'||c=='R'||c=='S';
}

// Drain every byte currently in the RX buffer and judge it as ONE chunk.
// Executes a command only when the chunk holds a single distinct command
// character (plus optional digits/newline). Anything else is malformed:
// clear command, stop motors, reply STATUS:ERROR. This makes "FORWARD"
// or noise ending in 'F' unable to actuate the motors (red-team H3).
// Digits form an optional PWM suffix (0..255); >255 is malformed as well.
void handleSerial() {
  if (Serial.available() <= 0) return;
  int cmds = 0, others = 0;
  char first = 0;
  bool mixed = false;
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') continue;
    if (c >= '0' && c <= '9') {
      if (speedAccum < 0) speedAccum = c - '0';
      else if (speedAccum <= 255) speedAccum = speedAccum * 10 + (c - '0');
      if (speedAccum > 255) speedAccum = 9999;  // bounded sentinel: malformed
      continue;
    }
    c = toupper(c);
    if (validCmd(c)) {
      if (cmds == 0) first = c;
      else if (first != c) mixed = true;
      cmds++;
    } else {
      others++;
    }
  }
  if (others > 0 || (cmds > 1 && mixed) || speedAccum > 255) {
    // MASTER PROMPT §2 / red-team H3: invalid input => STOP
    currentCmd = 'S';
    stopMotors();
    speedAccum = -1;
    int n = others + cmds + 1;
    if (n > MAX_ERROR_REPLIES) n = MAX_ERROR_REPLIES;
    for (int i = 0; i < n; i++) Serial.println("STATUS:ERROR");
    return;
  }
  if (cmds >= 1) {
    currentCmd = first;          // single distinct command (1..N repeats)
    if (speedAccum >= 0) activeSpeed = (int)speedAccum;
    speedAccum = -1;
    pwmCmdL = activeSpeed;
    pwmCmdR = activeSpeed;
    lastCmdTime = millis();
  } else if (speedAccum >= 0) {
    // speed-only chunk: retune now, but NEVER refresh the watchdog
    activeSpeed = (int)speedAccum;
    speedAccum = -1;
    if (currentCmd == 'F' || currentCmd == 'B' || currentCmd == 'L' ||
        currentCmd == 'R') {
      pwmCmdL = activeSpeed;
      pwmCmdR = activeSpeed;
    }
  }
  // pure line endings: ignored, never refresh the watchdog
}

// Phase 9+: per-wheel P velocity correction while driving forward/back.
// Runs only when encoders are enabled; silent encoders fall back to the
// open-loop activeSpeed so a dead sensor can never pin PWM at the limit.
void velocityControl(unsigned long now) {
  if (!encodersEnabled) return;
  if (now - lastVelCtl < (unsigned long)VEL_PERIOD_MS) return;
  lastVelCtl = now;
  unsigned long tl, tr;
  noInterrupts();
  tl = encTicksL;
  tr = encTicksR;
  interrupts();
  long dL = (long)(tl - prevEncL);
  long dR = (long)(tr - prevEncR);
  prevEncL = tl;
  prevEncR = tr;
  if (dL == 0 && dR == 0) velDead++;
  else velDead = 0;
  if (velDead >= VEL_DEAD_PERIODS) {
    pwmCmdL = activeSpeed;
    pwmCmdR = activeSpeed;
    velDead = 0;
    return;
  }
  long measL = dL * 1000L / (long)VEL_PERIOD_MS;
  long measR = dR * 1000L / (long)VEL_PERIOD_MS;
  float rawL = VEL_KP * (float)(VEL_TARGET_TPS - measL);
  float rawR = VEL_KP * (float)(VEL_TARGET_TPS - measR);
  long uL = (long)(rawL >= 0 ? rawL + 0.5f : rawL - 0.5f) + (long)VEL_PWM_FF;
  long uR = (long)(rawR >= 0 ? rawR + 0.5f : rawR - 0.5f) + (long)VEL_PWM_FF;
  if (uL < 0) uL = 0;
  if (uL > 255) uL = 255;
  if (uR < 0) uR = 0;
  if (uR > 255) uR = 255;
  pwmCmdL = (int)uL;
  pwmCmdR = (int)uR;
}

void loop() {
  handleSerial();

  float dist = readDistance();
  unsigned long now = millis();

  // Safety layer 1: comm timeout
  bool commLost = (now - lastCmdTime) > COMM_TIMEOUT_MS;
  // Safety layer 0: ultrasonic must produce a valid echo (red-team C1)
  bool sensorBad = (dist <= 0);
  // Safety layer 2: emergency obstacle (or dead sensor) blocks translation
bool blocked = (currentCmd == 'F' || currentCmd == 'B') && (sensorBad || dist < EMERGENCY_STOP_CM);

  if (commLost) {
    stopMotors();
    currentCmd = 'S';
  } else if (blocked) {
    stopMotors();
  } else if (currentCmd == 'S') {
    stopMotors();
  } else {
    drive(currentCmd);
    velocityControl(now);
  }

  if (now - lastTelemetry > TELEMETRY_MS) {
    lastTelemetry = now;
    if (dist < 0) Serial.println("DIST:-1");
    else { Serial.print("DIST:"); Serial.println(dist, 1); }
    if (commLost || blocked || sensorBad) Serial.println("STATUS:STOP");
    else Serial.println("STATUS:OK");
    unsigned long tl, tr;
    noInterrupts();
    tl = encTicksL;
    tr = encTicksR;
    interrupts();
    Serial.print("TICKS:");
    Serial.print(tl);
    Serial.print(",");
    Serial.println(tr);
  }
}
