/*
 * AI-Assisted Autonomous Exploration Rover - Arduino Uno R3 reflex core
 * ---------------------------------------------------------------------
 * Owner of every physical actuation pin.  Safety rules, in order of authority:
 *
 *   1. Boot stopped.  PWM is 0 before setup() returns.
 *   2. Hardware watchdog (250 ms).  A firmware hang resets the MCU, which
 *      stops the 1 kHz heartbeat -> the 555 missing-pulse detector drops STBY
 *      -> the TB6612 outputs are disabled in hardware.
 *   3. Fault latch: E-stop engaged (A1) or pack < 3.2 V/cell -> no motion.
 *   4. Forward gate: 15 cm floor, ramped to 35 cm at full PWM.
 *   5. 500 ms link watchdog.
 *   6. CRC-8 required on the ESP32 link; a corrupted command is discarded.
 *
 * Logic lives in safety_core.h / protocol.h (portable, host-tested).  This
 * sketch only does I/O: serial, HC-SR04 timing, ADC, PWM.
 *
 * Target: Arduino Uno R3 (arduino:avr:uno)
 * Link  : ESP32 GPIO17 TX2 -> D4, 9600 8N1, CRC-protected
 * USB   : 115200 8N1 telemetry, plus command input for bench bring-up
 */
#include <SoftwareSerial.h>
#include <avr/io.h>
#include <avr/wdt.h>
#include <stdlib.h>

#include <pins.h>
#include <safety_core.h>

// ---------------------------------------------------------------------------
// Build options.  `make compile-prod` turns the safety inputs on.
// ---------------------------------------------------------------------------
#ifndef ACCEPT_USB_COMMANDS
#define ACCEPT_USB_COMMANDS 1  // bench-test the Uno without the ESP32
#endif
#ifndef REQUIRE_ESTOP
#define REQUIRE_ESTOP 0  // 1 = A1 NC contact must read GND to allow motion
#endif
#ifndef BATTERY_SENSE
#define BATTERY_SENSE 0  // 1 = A0 divider installed (3.2 V/cell cutoff)
#endif
#ifndef REAR_SONAR
#define REAR_SONAR 0  // 1 = second HC-SR04 on A2/A3
#endif
#ifndef ENCODERS
#define ENCODERS 0  // 1 = closed-loop speed + odometry on A2/A3
#endif
#if ENCODERS && REAR_SONAR
#error "ENCODERS and REAR_SONAR both need A2/A3: enable only one"
#endif
#ifndef ENABLE_UART_TELEMETRY
#define ENABLE_UART_TELEMETRY 1  // Uno -> ESP32 health/state frames on D3
#endif
#ifndef SONAR_MEDIAN_FILTER
#define SONAR_MEDIAN_FILTER 1
#endif
#ifndef STATUS_LED_ENABLED
#define STATUS_LED_ENABLED 1
#endif
#define WDT_TIMEOUT WDTO_250MS

using rover::State;
using rover::Status;

SoftwareSerial link(rover::pins::kLinkRx, rover::pins::kLinkTx);
rover::SafetyCore core;
rover::GapFramer linkFramer;
rover::GapFramer usbFramer;
rover::MedianFilter3 sonarFilter;

// ---------------------------------------------------------------------------
// HC-SR04 non-blocking ping (one instance per sensor)
// ---------------------------------------------------------------------------
struct PingSensor {
  uint8_t trig = 0;
  uint8_t echo = 0;
  uint8_t phase = 0;  // 0 idle, 1 trig high, 2 wait rise, 3 wait fall
  uint32_t phaseUs = 0;
  uint32_t riseUs = 0;
  uint32_t lastMs = 0;
  bool enabled = false;

  void begin(uint8_t trigPin, uint8_t echoPin, uint16_t offsetMs) {
    trig = trigPin;
    echo = echoPin;
    enabled = true;
    pinMode(trig, OUTPUT);
    pinMode(echo, INPUT);
    digitalWrite(trig, LOW);
    lastMs = millis() - rover::kSonarPeriodMs + offsetMs;
  }

  // -2 = no sample yet, -1 = invalid/timeout, >= 0 = centimetres
  int poll(uint32_t nowUs, uint32_t nowMs) {
    if (!enabled) return -2;
    switch (phase) {
      case 0:
        if ((nowMs - lastMs) >= rover::kSonarPeriodMs) {
          lastMs = nowMs;
          digitalWrite(trig, HIGH);
          phaseUs = nowUs;
          phase = 1;
        }
        return -2;
      case 1:
        if ((nowUs - phaseUs) >= 10) {
          digitalWrite(trig, LOW);
          phaseUs = nowUs;
          phase = 2;
        }
        return -2;
      case 2:
        if (digitalRead(echo) == HIGH) {
          riseUs = nowUs;
          phase = 3;
        } else if ((nowUs - phaseUs) > 5000) {
          phase = 0;
          return -1;
        }
        return -2;
      case 3:
        if (digitalRead(echo) == LOW) {
          const uint32_t width = nowUs - riseUs;
          phase = 0;
          if (width < 100) return -1;  // electrical noise, not an echo
          int cm = static_cast<int>(width / 58UL);
          if (cm < 2) cm = 2;
          if (cm > static_cast<int>(rover::kSonarMaxCm)) {
            cm = static_cast<int>(rover::kSonarMaxCm);
          }
          return cm;
        }
        if ((nowUs - riseUs) > 25000) {  // no return within ~4.3 m
          phase = 0;
          return -1;
        }
        return -2;
    }
    return -2;
  }
};

PingSensor frontSonar;
#if REAR_SONAR
PingSensor rearSonar;
#endif

// ---------------------------------------------------------------------------
// Encoders / closed loop
// ---------------------------------------------------------------------------
#if ENCODERS
volatile uint32_t encCountL = 0;
volatile uint32_t encCountR = 0;
uint8_t encPrev = 0;
rover::WheelSpeedLoop speedL;
rover::WheelSpeedLoop speedR;
rover::DifferentialOdometry odom;
uint32_t lastCtrlMs = 0;
int8_t lastDirL = 0;
int8_t lastDirR = 0;

// Single-channel encoders: count rising edges. Direction comes from the
// commanded direction, which is exact for a differential drive.
void encoderLeftIsr() { ++encCountL; }
void encoderRightIsr() { ++encCountR; }
#endif

// ---------------------------------------------------------------------------
// Timing / state
// ---------------------------------------------------------------------------
uint32_t lastTlmMs = 0;
uint32_t lastLinkByteMs = 0;
uint32_t lastBatteryMs = 0;
uint32_t lastHeartbeatUs = 0;
bool heartbeatLevel = false;
bool wdtReboot = false;

State lastState = State::Stop;
Status lastStatus = Status::Ok;
char lastCmd = 'S';
int lastSpeed = -1;
rover::Outputs lastOut = {0, 0, 0, 0};
uint8_t appliedPwmL = 0;
uint8_t appliedPwmR = 0;
uint8_t writtenPwmL = 0;
uint8_t writtenPwmR = 0;
int8_t writtenDirL = 0;
int8_t writtenDirR = 0;
uint8_t lastFaultOut = 0xFF;
bool lastEstop = false;
int lastBatteryMv = -1;
rover::Fault lastFault = rover::Fault::None;

// ---------------------------------------------------------------------------
// Output stage
// ---------------------------------------------------------------------------
static void applyOutputs() {
  const rover::Outputs& o = core.outputs();

  // Safety: when the core is not driving, the driver sees 0 immediately,
  // regardless of where the 50 ms control loop is.
  uint8_t pwmL = o.pwmL;
  uint8_t pwmR = o.pwmR;
#if ENCODERS
  if (core.moving()) {
    pwmL = appliedPwmL;
    pwmR = appliedPwmR;
  } else {
    pwmL = 0;
    pwmR = 0;
  }
#endif

  if (pwmL == writtenPwmL && pwmR == writtenPwmR && o.dirL == writtenDirL &&
      o.dirR == writtenDirR) {
    return;
  }
  const rover::PinLevels p = rover::pinLevels(o);
  digitalWrite(rover::pins::kAin1, p.ain1);
  digitalWrite(rover::pins::kAin2, p.ain2);
  digitalWrite(rover::pins::kBin1, p.bin1);
  digitalWrite(rover::pins::kBin2, p.bin2);
  analogWrite(rover::pins::kPwma, pwmL);
  analogWrite(rover::pins::kPwmb, pwmR);
  writtenPwmL = pwmL;
  writtenPwmR = pwmR;
  writtenDirL = o.dirL;
  writtenDirR = o.dirR;
  lastOut = o;
}

static void printActuation() {
  const rover::Outputs& o = core.outputs();
  const rover::PinLevels p = rover::pinLevels(o);
  Serial.print(F("[UNO] ACT: PWMA="));
  Serial.print(writtenPwmL);
  Serial.print(F(" PWMB="));
  Serial.print(writtenPwmR);
  Serial.print(F(" AIN1="));
  Serial.print(p.ain1 ? F("H") : F("L"));
  Serial.print(F(" AIN2="));
  Serial.print(p.ain2 ? F("H") : F("L"));
  Serial.print(F(" BIN1="));
  Serial.print(p.bin1 ? F("H") : F("L"));
  Serial.print(F(" BIN2="));
  Serial.println(p.bin2 ? F("H") : F("L"));
}

static void printState(bool force) {
  if (!force && core.state() == lastState && core.status() == lastStatus &&
      core.command() == lastCmd && core.speed() == lastSpeed) {
    return;
  }
  lastState = core.state();
  lastStatus = core.status();
  lastCmd = core.command();
  lastSpeed = core.speed();

  Serial.print(F("[UNO] CMD: "));
  Serial.print(core.command());
  Serial.print(F(" | Speed: "));
  Serial.print(core.speed());
  Serial.print(F("/255 | STATE: "));
  Serial.print(rover::stateName(core.state()));
  Serial.print(F(" | STATUS: "));
  Serial.println(rover::statusName(core.status()));
  printActuation();
}

static void printSafety(bool force) {
  const int battBucket = core.batteryMv() / 100;  // 0.1 V granularity
  const rover::Fault fault = core.faultReason();
  if (!force && core.estopEngaged() == lastEstop && battBucket == lastBatteryMv &&
      fault == lastFault) {
    return;
  }
  lastEstop = core.estopEngaged();
  lastBatteryMv = battBucket;
  lastFault = fault;

  Serial.print(F("[UNO] SAFETY: estop="));
#if REQUIRE_ESTOP
  Serial.print(core.estopEngaged() ? F("ENGAGED") : F("ARMED"));
#else
  Serial.print(F("off"));
#endif
  Serial.print(F(" | batt="));
  if (core.batteryMv() > 0) {
    Serial.print(core.batteryMv() / 1000);
    Serial.print('.');
    const int frac = (core.batteryMv() % 1000) / 10;
    if (frac < 10) Serial.print('0');
    Serial.print(frac);
    Serial.print(F("V"));
  } else {
    Serial.print(F("--"));
  }
  Serial.print(F(" | fault="));
  Serial.print(rover::faultName(fault));
  Serial.print(F(" | gate<="));
  Serial.print(core.gateCm());
  Serial.println(F("cm"));
}

// Emit exactly one alert per blocked transition, not on every retry.
static void announceBlockIfNew(State before, char intent) {
  if (core.state() != State::Blocked || before == State::Blocked) return;
  Serial.print(F("[UNO] ALERT:OBSTACLE dist="));
  Serial.print(core.distanceCm());
  Serial.print(F("cm cmd="));
  Serial.print(intent);
  Serial.println(F(" --> Immediate Motor STOP (PWM=0)"));
}

// ---------------------------------------------------------------------------
// Serial / framing
// ---------------------------------------------------------------------------
static void feed(Stream& port, rover::GapFramer& framer, bool isLink) {
  while (port.available() > 0) {
    const int b = port.read();
    if (b < 0) break;
    framer.push(static_cast<uint8_t>(b), micros());
    if (isLink) lastLinkByteMs = millis();
  }
}

static void handleFrames(rover::GapFramer& framer, bool requireCrc, const char* source) {
  framer.poll(micros());
  if (!framer.ready()) return;

  if (framer.overflowed()) {
    Serial.print(F("[UNO] STATUS: ERROR | frame overflow ("));
    Serial.print(source);
    Serial.println(F(") -> discarded"));
    framer.consume();
    framer.reset();
    return;
  }

  const State before = core.state();
  const char intent = framer.frame()[0];
  const uint32_t crcBefore = core.crcFailures();
  const bool ok = core.acceptFrame(framer.frame(), framer.length(), millis(), requireCrc);

  if (!ok) {
    Serial.print(F("[UNO] STATUS: ERROR | rejected=\""));
    for (uint8_t i = 0; i < framer.length(); ++i) Serial.print(framer.frame()[i]);
    Serial.print(F("\" src="));
    Serial.print(source);
    if (core.crcFailures() > crcBefore) {
      Serial.print(F(" | CRC:FAIL"));
    } else if (requireCrc && intent != '\0') {
      Serial.print(F(" | CRC:MISSING"));
    }
    Serial.print(F(" | total="));
    Serial.println(core.rejected());
  } else {
    announceBlockIfNew(before, intent);
  }
  framer.consume();
}

// ---------------------------------------------------------------------------
// Numeric helpers for the compact telemetry frame (no printf on AVR)
// ---------------------------------------------------------------------------
static uint8_t appendInt(char* out, uint8_t n, int value) {
  char tmp[8];
  itoa(value, tmp, 10);
  for (const char* p = tmp; *p != '\0' && n < 76; ++p) out[n++] = *p;
  return n;
}

static uint8_t appendHex8(char* out, uint8_t n, uint8_t value) {
  static const char* digits = "0123456789ABCDEF";
  out[n++] = digits[(value >> 4) & 0x0F];
  out[n++] = digits[value & 0x0F];
  return n;
}

// ---------------------------------------------------------------------------
// Uno -> ESP32 telemetry: "T,<state>,<cmd>,<pwm>,<dist>,<mv>,<fault>*HH\n"
// Sent only inside a safe window so it never collides with a command.
// ---------------------------------------------------------------------------
static void sendTelemetryIfDue() {
  const uint32_t sinceRx = millis() - lastLinkByteMs;
  const bool inRxWindow = sinceRx <= 45;       // just after a command
  const bool linkIdle = sinceRx >= 1000;       // nobody is commanding
  const bool due = (millis() - lastTlmMs) >= rover::kTelemetryPeriodMs;
  if (!due || !(inRxWindow || linkIdle)) return;

  char buf[80];
  uint8_t n = 0;
  buf[n++] = 'T';
  buf[n++] = ',';
  n = appendInt(buf, n, rover::stateCode(core.state()));
  buf[n++] = ',';
  buf[n++] = core.command();
  buf[n++] = ',';
  n = appendInt(buf, n, core.outputs().pwmL);
  buf[n++] = ',';
  n = appendInt(buf, n, core.distanceCm());
  buf[n++] = ',';
  n = appendInt(buf, n, core.batteryMv());
  buf[n++] = ',';
  n = appendInt(buf, n, rover::faultCode(core.faultReason()));

  int vL = 0, vR = 0, ox = 0, oy = 0, th = 0;
#if ENCODERS
  vL = static_cast<int>(speedL.speedMmS());
  vR = static_cast<int>(speedR.speedMmS());
  ox = static_cast<int>(odom.xMm());
  oy = static_cast<int>(odom.yMm());
  th = static_cast<int>(odom.thetaDeg());
#endif
  buf[n++] = ',';
  n = appendInt(buf, n, vL);
  buf[n++] = ',';
  n = appendInt(buf, n, vR);
  buf[n++] = ',';
  n = appendInt(buf, n, ox);
  buf[n++] = ',';
  n = appendInt(buf, n, oy);
  buf[n++] = ',';
  n = appendInt(buf, n, th);

  const uint8_t crc = rover::crc8(buf, n);
  buf[n++] = '*';
  n = appendHex8(buf, n, crc);
  buf[n++] = '\n';

  link.write(reinterpret_cast<const uint8_t*>(buf), n);
  lastTlmMs = millis();
}

// ---------------------------------------------------------------------------
// Live drive/odometry log (encoder builds only) - used for calibration.
// ---------------------------------------------------------------------------
static void printDrive(bool force) {
#if ENCODERS
  static uint32_t last = 0;
  if (!force && (millis() - last) < 500) return;
  last = millis();
  Serial.print(F("[UNO] DRIVE: vL="));
  Serial.print(static_cast<int>(speedL.speedMmS()));
  Serial.print(F(" vR="));
  Serial.print(static_cast<int>(speedR.speedMmS()));
  Serial.print(F(" mm/s | odo="));
  Serial.print(static_cast<int>(odom.distanceMm()));
  Serial.print(F("mm x="));
  Serial.print(static_cast<int>(odom.xMm()));
  Serial.print(F(" y="));
  Serial.print(static_cast<int>(odom.yMm()));
  Serial.print(F(" th="));
  Serial.print(static_cast<int>(odom.thetaDeg()));
  Serial.println(F("deg"));
#else
  (void)force;
#endif
}

// ---------------------------------------------------------------------------
// Sensors and inputs
// ---------------------------------------------------------------------------
static void reportSonar(int rawCm) {
  int cm = rawCm;
#if SONAR_MEDIAN_FILTER
  cm = sonarFilter.push(rawCm);
#endif
  const bool valid = cm >= 0;
  const State before = core.state();
  const char intent = core.command();
  core.updateSonar(cm, valid, millis());

  Serial.print(F("[UNO] DIST: "));
  Serial.print(cm);
  Serial.print(F(" cm | Gate Check: "));
  if (!valid) {
    Serial.print(F("FAILED (sensor lost, DIST:-1)"));
  } else if (cm < core.gateCm()) {
    Serial.print(F("REFUSED (< "));
    Serial.print(core.gateCm());
    Serial.print(F(" cm)"));
  } else {
    Serial.print(F("PASSED (>= "));
    Serial.print(core.gateCm());
    Serial.print(F(" cm)"));
  }
  Serial.println();
  announceBlockIfNew(before, intent);
}

static void serviceBattery() {
#if BATTERY_SENSE
  if ((millis() - lastBatteryMs) < 250) return;
  lastBatteryMs = millis();
  uint32_t sum = 0;
  for (uint8_t i = 0; i < 4; ++i) sum += analogRead(rover::pins::kPinBattery);
  const int raw = static_cast<int>(sum / 4);
  const int mv = static_cast<int>(
      (static_cast<int32_t>(raw) * 5000L * 147L) / (1023L * 47L));
  core.updateBatteryMv(mv);
#endif
}

static void serviceEstop() {
#if REQUIRE_ESTOP
  core.setEstop(digitalRead(rover::pins::kPinEstop) != LOW);
#endif
}

static void serviceFaultOut() {
  const uint8_t level = core.faultActive() ? LOW : HIGH;
  if (level == lastFaultOut) return;
  digitalWrite(rover::pins::kPinFaultOut, level);
  lastFaultOut = level;
}

// ---------------------------------------------------------------------------
// Closed-loop speed + odometry at 20 Hz
// ---------------------------------------------------------------------------
static void serviceControl(uint32_t nowMs) {
#if ENCODERS
  static State prevState = State::Stop;
  const rover::Outputs& o = core.outputs();

  // Start at the feed-forward value the moment a drive command arrives.
  if (core.moving() && prevState != State::Go) {
    appliedPwmL = o.pwmL;
    appliedPwmR = o.pwmR;
    speedL.reset();
    speedR.reset();
  }
  prevState = core.state();

  if ((nowMs - lastCtrlMs) < rover::pins::kControlPeriodMs) return;
  uint16_t dt = static_cast<uint16_t>(nowMs - lastCtrlMs);
  if (dt > 500) dt = 500;
  lastCtrlMs = nowMs;

  noInterrupts();
  const uint32_t cL = encCountL;
  const uint32_t cR = encCountR;
  encCountL = 0;
  encCountR = 0;
  interrupts();

  const int thrL = core.moving() ? o.pwmL : 0;
  const int thrR = core.moving() ? o.pwmR : 0;
  appliedPwmL = static_cast<uint8_t>(speedL.update(cL, dt, thrL));
  appliedPwmR = static_cast<uint8_t>(speedR.update(cR, dt, thrR));

  if (o.dirL != 0) lastDirL = o.dirL;
  if (o.dirR != 0) lastDirR = o.dirR;
  odom.update(static_cast<int32_t>(cL) * (lastDirL < 0 ? -1 : 1),
              static_cast<int32_t>(cR) * (lastDirR < 0 ? -1 : 1), dt);

  if (speedL.stalled() || speedR.stalled()) {
    core.setStall(true);
    appliedPwmL = 0;
    appliedPwmR = 0;
  }
#endif
}

// ---------------------------------------------------------------------------
// 1 kHz heartbeat: proves the MCU is executing.  The 555 missing-pulse
// detector converts it into TB6612 STBY.
// ---------------------------------------------------------------------------
static void serviceHeartbeat() {
  const uint32_t now = micros();
  if ((now - lastHeartbeatUs) < rover::kHeartbeatHalfPeriodUs) return;
  lastHeartbeatUs = now;
  heartbeatLevel = !heartbeatLevel;
  digitalWrite(rover::pins::kPinHeartbeat, heartbeatLevel);
}

// ---------------------------------------------------------------------------
// Status LED: 1 Hz stopped, solid driving, 5 Hz blocked/timeout, 2.5 Hz fault
// ---------------------------------------------------------------------------
static void serviceLed() {
#if STATUS_LED_ENABLED
  const uint32_t now = millis();
  switch (core.state()) {
    case State::Go:
      digitalWrite(rover::pins::kStatusLed, HIGH);
      break;
    case State::Stop:
      digitalWrite(rover::pins::kStatusLed, (now % 1000) < 500 ? HIGH : LOW);
      break;
    case State::Fault:
      digitalWrite(rover::pins::kStatusLed, (now % 400) < 200 ? HIGH : LOW);
      break;
    case State::Blocked:
    case State::Timeout:
    default:
      digitalWrite(rover::pins::kStatusLed, (now % 100) < 50 ? HIGH : LOW);
      break;
  }
#endif
}

// ---------------------------------------------------------------------------
// setup / loop
// ---------------------------------------------------------------------------
void setup() {
  // If the watchdog fired, clear the flag and disable it before anything else.
  const uint8_t resetFlags = MCUSR;
  MCUSR = 0;
  wdt_disable();
  wdtReboot = (resetFlags & _BV(WDRF)) != 0;

  // Drive the H-bridge inputs low before they become outputs.
  digitalWrite(rover::pins::kAin1, LOW);
  digitalWrite(rover::pins::kAin2, LOW);
  digitalWrite(rover::pins::kBin1, LOW);
  digitalWrite(rover::pins::kBin2, LOW);
  pinMode(rover::pins::kAin1, OUTPUT);
  pinMode(rover::pins::kAin2, OUTPUT);
  pinMode(rover::pins::kBin1, OUTPUT);
  pinMode(rover::pins::kBin2, OUTPUT);
  pinMode(rover::pins::kPwma, OUTPUT);
  pinMode(rover::pins::kPwmb, OUTPUT);
  analogWrite(rover::pins::kPwma, 0);
  analogWrite(rover::pins::kPwmb, 0);

  pinMode(rover::pins::kStatusLed, OUTPUT);

  // Hardware interlock / health
  pinMode(rover::pins::kPinHeartbeat, OUTPUT);
  digitalWrite(rover::pins::kPinHeartbeat, LOW);
  pinMode(rover::pins::kPinFaultOut, OUTPUT);
  digitalWrite(rover::pins::kPinFaultOut, HIGH);  // active LOW
  lastFaultOut = HIGH;

#if REQUIRE_ESTOP
  pinMode(rover::pins::kPinEstop, INPUT_PULLUP);
#endif
#if BATTERY_SENSE
  pinMode(rover::pins::kPinBattery, INPUT);
#endif

#if ENCODERS
  // A2/A3 are shared with the rear sonar; the #error above prevents both.
  pinMode(rover::pins::kEncoderLeft, INPUT_PULLUP);
  pinMode(rover::pins::kEncoderRight, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(rover::pins::kEncoderLeft), encoderLeftIsr, RISING);
  attachInterrupt(digitalPinToInterrupt(rover::pins::kEncoderRight), encoderRightIsr, RISING);
  speedL.configure(rover::pins::kEncoderCpr, rover::pins::kWheelCircumferenceMm,
                   rover::pins::kMaxSpeedMmS, rover::pins::kSpeedKp, rover::pins::kSpeedKi);
  speedR.configure(rover::pins::kEncoderCpr, rover::pins::kWheelCircumferenceMm,
                   rover::pins::kMaxSpeedMmS, rover::pins::kSpeedKp, rover::pins::kSpeedKi);
  odom.configure(rover::pins::kWheelCircumferenceMm, rover::pins::kTrackMm,
                 rover::pins::kEncoderCpr);
  lastCtrlMs = millis();
#endif

  frontSonar.begin(rover::pins::kTrig, rover::pins::kEcho, 0);
#if REAR_SONAR
  rearSonar.begin(rover::pins::kRearTrig, rover::pins::kRearEcho, rover::kSonarPeriodMs / 2);
#endif

  Serial.begin(rover::pins::kTelemetryBaud);
  link.begin(rover::pins::kLinkBaud);

  core.begin(millis());
  linkFramer.reset();
  usbFramer.reset();
  sonarFilter.reset();

  delay(50);
  Serial.println();
  if (wdtReboot) {
    Serial.println(F("[UNO] BOOT:STOP (recovered from watchdog reset)"));
  } else {
    Serial.println(F("[UNO] BOOT:STOP"));
  }
#if ACCEPT_USB_COMMANDS
  Serial.println(F("[UNO] LINK: 9600 8N1 RX=D4 (CRC required) | USB commands: on"));
#else
  Serial.println(F("[UNO] LINK: 9600 8N1 RX=D4 (CRC required) | USB commands: off"));
#endif
  Serial.print(F("[UNO] SAFETY BUILD: estop="));
  Serial.print(REQUIRE_ESTOP ? F("enforced") : F("off"));
  Serial.print(F(" battery="));
  Serial.print(BATTERY_SENSE ? F("enforced") : F("off"));
  Serial.print(F(" rear="));
  Serial.print(REAR_SONAR ? F("on") : F("off"));
  Serial.print(F(" encoders="));
  Serial.print(ENCODERS ? F("closed-loop") : F("open-loop"));
  Serial.println(F(" wdt=250ms | boot state: motors coasting"));
  Serial.print(F("[UNO] GATE: "));
  Serial.print(rover::kForwardGateCm);
  Serial.print(F(".."));
  Serial.print(rover::kForwardGateCm + rover::kGateSpeedCm);
  Serial.println(F(" cm (speed-scaled)"));
#if ENCODERS
  Serial.print(F("[UNO] ODO: cpr="));
  Serial.print(rover::pins::kEncoderCpr, 0);
  Serial.print(F(" wheel="));
  Serial.print(rover::pins::kWheelCircumferenceMm, 1);
  Serial.print(F("mm track="));
  Serial.print(rover::pins::kTrackMm, 0);
  Serial.println(F("mm (PI speed control)"));
#endif
  printState(true);
  printSafety(true);
  printDrive(true);

  wdt_enable(WDT_TIMEOUT);  // arm last: setup must never trip it
}

void loop() {
  wdt_reset();

  feed(link, linkFramer, true);
  handleFrames(linkFramer, true, "LINK");
#if ACCEPT_USB_COMMANDS
  feed(Serial, usbFramer, false);
  handleFrames(usbFramer, false, "USB");
#endif

  const uint32_t nowUs = micros();
  const uint32_t nowMs = millis();

  const int frontCm = frontSonar.poll(nowUs, nowMs);
  if (frontCm != -2) reportSonar(frontCm);

#if REAR_SONAR
  const int rearCm = rearSonar.poll(nowUs, nowMs);
  if (rearCm != -2) {
    const bool valid = rearCm >= 0;
    core.updateRearSonar(rearCm, valid, nowMs);
    Serial.print(F("[UNO] REAR: "));
    Serial.print(rearCm);
    Serial.println(F(" cm"));
  }
#endif

  serviceEstop();
  serviceBattery();
  serviceFaultOut();
  core.tick(nowMs);
  serviceControl(nowMs);
  applyOutputs();
  serviceHeartbeat();
#if ENABLE_UART_TELEMETRY
  sendTelemetryIfDue();
#endif
  serviceLed();

  printState(false);
  printSafety(false);
  printDrive(false);
}
