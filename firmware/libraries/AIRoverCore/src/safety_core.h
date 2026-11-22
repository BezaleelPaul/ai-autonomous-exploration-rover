/*
 * safety_core.h - Portable reflex-core logic for the AI Rover.
 *
 * NO Arduino-specific code: the same header is compiled by avr-gcc (target
 * hardware) and by host g++ (tests/native/test_safety_core.cpp, CI).
 *
 * Safety rules enforced here:
 *   1. Boot stopped.
 *   2. Forward gate: 15 cm floor, scaled up to 35 cm at full PWM.
 *   3. Reverse gate (optional rear sensor): 15 cm.
 *   4. 500 ms link watchdog.
 *   5. Fault latch: E-stop engaged or pack below 3.2 V/cell -> no motion.
 *   6. CRC-checked link frames (the caller passes requireCrc on the UART).
 */
#ifndef ROVER_SAFETY_CORE_H
#define ROVER_SAFETY_CORE_H

#include <stdint.h>
#include <math.h>
#include <string.h>

#include "protocol.h"

namespace rover {

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------
enum class State : uint8_t { Stop = 0, Go, Blocked, Timeout, Fault };
enum class Status : uint8_t { Ok = 0, Error, Blocked };
enum class Fault : uint8_t { None = 0, Estop, BatteryLow, Stall };

inline const char* stateName(State s) {
  switch (s) {
    case State::Go:      return "GO";
    case State::Blocked: return "BLOCKED";
    case State::Timeout: return "TIMEOUT";
    case State::Fault:   return "FAULT";
    case State::Stop:
    default:             return "STOP";
  }
}

inline const char* statusName(Status s) {
  switch (s) {
    case Status::Error:   return "ERROR";
    case Status::Blocked: return "BLOCKED";
    case Status::Ok:
    default:              return "OK";
  }
}

inline const char* faultName(Fault f) {
  switch (f) {
    case Fault::Estop:      return "ESTOP";
    case Fault::BatteryLow: return "BATTLOW";
    case Fault::Stall:      return "STALL";
    case Fault::None:
    default:                return "NONE";
  }
}

// Compact numeric codes for the Uno -> ESP32 telemetry frame.
inline uint8_t stateCode(State s) { return static_cast<uint8_t>(s); }
inline uint8_t faultCode(Fault f) { return static_cast<uint8_t>(f); }

// ---------------------------------------------------------------------------
// Motor outputs
// ---------------------------------------------------------------------------
struct Outputs {
  uint8_t pwmL;
  uint8_t pwmR;
  int8_t dirL;  // +1 forward, -1 reverse, 0 coast
  int8_t dirR;
};

struct PinLevels {
  uint8_t ain1;
  uint8_t ain2;
  uint8_t bin1;
  uint8_t bin2;
};

inline PinLevels pinLevels(const Outputs& o) {
  PinLevels p;
  p.ain1 = o.dirL > 0 ? 1 : 0;
  p.ain2 = o.dirL < 0 ? 1 : 0;
  p.bin1 = o.dirR > 0 ? 1 : 0;
  p.bin2 = o.dirR < 0 ? 1 : 0;
  return p;
}

// ---------------------------------------------------------------------------
// Median-of-3 filter: kills single-sample ultrasonic spikes.
// Invalid samples bypass the window so a dead sensor is never masked.
// ---------------------------------------------------------------------------
class MedianFilter3 {
 public:
  void reset() { count_ = 0; }
  int push(int cm) {
    if (cm < 0) return -1;
    buf_[count_ % 3] = cm;
    if (count_ < 3) ++count_;
    if (count_ == 1) return buf_[0];
    if (count_ == 2) return (buf_[0] + buf_[1]) / 2;
    int a = buf_[0], b = buf_[1], c = buf_[2];
    if (a > b) { int t = a; a = b; b = t; }
    if (b > c) { int t = b; b = c; c = t; }
    if (a > b) { int t = a; a = b; b = t; }
    return b;
  }
  uint8_t count() const { return count_; }

 private:
  int buf_[3] = {0, 0, 0};
  uint8_t count_ = 0;
};

// ---------------------------------------------------------------------------
// The reflex core
// ---------------------------------------------------------------------------
class SafetyCore {
 public:
  void begin(uint32_t nowMs) {
    state_ = State::Stop;
    status_ = Status::Ok;
    cmd_ = 'S';
    speed_ = kDefaultSpeed;
    outputs_ = Outputs{0, 0, 0, 0};
    lastCmdMs_ = nowMs;
    hasCmd_ = false;
    distCm_ = -1;
    distValid_ = false;
    sonarSeen_ = false;
    lastSonarMs_ = nowMs;
    obstacleLatched_ = false;
    rearCm_ = -1;
    rearValid_ = false;
    rearSeen_ = false;
    rearLatched_ = false;
    batteryMv_ = 0;
    batteryLow_ = false;
    estop_ = false;
    stall_ = false;
    accepted_ = 0;
    rejected_ = 0;
    watchdogTrips_ = 0;
    crcFailures_ = 0;
  }

  // -------------------------------------------------------------------------
  // Commands
  // -------------------------------------------------------------------------
  // Returns true when the frame was syntactically valid and accepted.
  bool acceptFrame(const char* frame, uint8_t len, uint32_t nowMs, bool requireCrc = false) {
    Packet p;
    if (!parsePacket(frame, len, p)) {
      ++rejected_;
      if (frame != nullptr) {
        // A well-formed body with a bad checksum is reported separately.
        for (uint8_t i = 0; i < len; ++i) {
          if (frame[i] == '*') { ++crcFailures_; break; }
        }
      }
      status_ = Status::Error;
      return false;
    }
    if (requireCrc && !p.hasCrc) {
      ++rejected_;
      status_ = Status::Error;
      return false;
    }
    acceptCommand(p.cmd, p.hasSpeed ? p.speed : speed_, nowMs);
    return true;
  }

  void acceptCommand(char cmd, int speed, uint32_t nowMs) {
    cmd = canonicalCommand(cmd);
    if (cmd == '\0') {
      ++rejected_;
      status_ = Status::Error;
      return;
    }
    ++accepted_;
    hasCmd_ = true;
    lastCmdMs_ = nowMs;

    if (cmd == 'S') {
      stall_ = false;  // an explicit stop acknowledges a stall; E-stop/battery stay latched
      stop(faultActive() ? State::Fault : State::Stop, Status::Ok);
      return;
    }

    if (faultActive()) {
      stop(State::Fault, Status::Ok);
      return;
    }

    speed_ = clampSpeed(speed);
    cmd_ = cmd;

    if (cmd == 'F' && forwardBlocked()) {
      stop(State::Blocked, Status::Blocked);
      cmd_ = 'F';  // remember the refused intent for telemetry
      obstacleLatched_ = true;
      return;
    }
    if (cmd == 'B' && rearBlocked()) {
      stop(State::Blocked, Status::Blocked);
      cmd_ = 'B';
      rearLatched_ = true;
      return;
    }

    applyMotion(cmd, speed_);
    status_ = Status::Ok;
    state_ = State::Go;
    obstacleLatched_ = false;
    rearLatched_ = false;
  }

  // -------------------------------------------------------------------------
  // Sensors and inputs
  // -------------------------------------------------------------------------
  void updateSonar(int cm, bool valid, uint32_t nowMs) {
    lastSonarMs_ = nowMs;
    sonarSeen_ = true;
    distValid_ = valid && cm >= 0;
    if (!distValid_) {
      distCm_ = -1;
      if (requireSonar_ && cmd_ == 'F') {
        stop(State::Blocked, Status::Blocked);
        obstacleLatched_ = true;
      }
      return;
    }
    if (cm > static_cast<int>(kSonarMaxCm)) cm = static_cast<int>(kSonarMaxCm);
    distCm_ = cm;

    if (cmd_ == 'F' && state_ == State::Go && cm < requiredGateCm(speed_)) {
      stop(State::Blocked, Status::Blocked);
      obstacleLatched_ = true;
    }
  }

  // Only enforced once a rear sensor has produced at least one reading, so a
  // board without the optional second HC-SR04 still allows reverse.
  void updateRearSonar(int cm, bool valid, uint32_t nowMs) {
    lastRearMs_ = nowMs;
    rearSeen_ = true;
    rearValid_ = valid && cm >= 0;
    rearCm_ = rearValid_ ? cm : -1;
    if (rearValid_ && rearCm_ > static_cast<int>(kSonarMaxCm)) {
      rearCm_ = static_cast<int>(kSonarMaxCm);
    }
    if (cmd_ == 'B' && state_ == State::Go && rearBlocked()) {
      stop(State::Blocked, Status::Blocked);
      rearLatched_ = true;
    }
  }

  // 0 = not fitted / not sampled yet.
  void updateBatteryMv(int mv) {
    if (mv <= 0) return;
    batteryMv_ = mv;
    if (mv < kBatteryLowMv && !batteryLow_) {
      batteryLow_ = true;
      refreshFaultState();
    } else if (mv > kBatteryRecoverMv && batteryLow_) {
      batteryLow_ = false;
      refreshFaultState();
    }
  }

  // A normally-closed E-stop contact: armed = pin LOW, pressed/disconnected =
  // HIGH -> fail-safe fault.
  void setEstop(bool engaged) {
    if (engaged == estop_) return;
    estop_ = engaged;
    refreshFaultState();
  }

  // Latched by the speed loop when the wheels make no progress. Cleared by an
  // explicit S (operator acknowledgement), never automatically.
  void setStall(bool stalled) {
    if (stalled == stall_) return;
    stall_ = stalled;
    refreshFaultState();
  }

  void tick(uint32_t nowMs) {
    if (!hasCmd_) return;
    if (state_ == State::Stop || state_ == State::Timeout || state_ == State::Fault) return;
    if (nowMs - lastCmdMs_ <= kLinkWatchdogMs) return;
    stop(State::Timeout, Status::Ok);
    watchdogTrips_++;
  }

  // -------------------------------------------------------------------------
  // Queries
  // -------------------------------------------------------------------------
  bool sonarDue(uint32_t nowMs) const {
    return (nowMs - lastSonarMs_) >= kSonarPeriodMs;
  }

  bool forwardBlocked() const {
    if (!requireSonar_) {
      return distValid_ && distCm_ < requiredGateCm(speed_);
    }
    return !distValid_ || distCm_ < requiredGateCm(speed_);
  }

  void setRequireSonar(bool req) { requireSonar_ = req; }
  bool requireSonar() const { return requireSonar_; }

  bool rearBlocked() const {
    return rearSeen_ && (!rearValid_ || rearCm_ < kRearGateCm);
  }

  bool faultActive() const { return estop_ || batteryLow_ || stall_; }
  Fault faultReason() const {
    if (estop_) return Fault::Estop;
    if (batteryLow_) return Fault::BatteryLow;
    if (stall_) return Fault::Stall;
    return Fault::None;
  }

  int gateCm() const { return requiredGateCm(speed_); }
  const Outputs& outputs() const { return outputs_; }
  State state() const { return state_; }
  Status status() const { return status_; }
  char command() const { return cmd_; }
  int speed() const { return speed_; }
  int distanceCm() const { return distCm_; }
  bool distanceValid() const { return distValid_; }
  bool sonarSeen() const { return sonarSeen_; }
  int rearDistanceCm() const { return rearCm_; }
  bool rearSeen() const { return rearSeen_; }
  int batteryMv() const { return batteryMv_; }
  bool batteryLow() const { return batteryLow_; }
  bool estopEngaged() const { return estop_; }
  bool stalled() const { return stall_; }
  bool moving() const { return state_ == State::Go; }
  bool obstacleLatched() const { return obstacleLatched_; }
  bool rearLatched() const { return rearLatched_; }
  uint32_t lastCommandAgeMs(uint32_t nowMs) const {
    return hasCmd_ ? (nowMs - lastCmdMs_) : 0;
  }
  uint32_t accepted() const { return accepted_; }
  uint32_t rejected() const { return rejected_; }
  uint32_t watchdogTrips() const { return watchdogTrips_; }
  uint32_t crcFailures() const { return crcFailures_; }

 private:
  void stop(State s, Status st) {
    outputs_ = Outputs{0, 0, 0, 0};
    state_ = s;
    status_ = st;
    cmd_ = 'S';
  }

  void refreshFaultState() {
    if (faultActive()) {
      if (state_ != State::Fault) stop(State::Fault, Status::Ok);
    } else if (state_ == State::Fault) {
      stop(State::Stop, Status::Ok);  // requires a fresh command to move again
    }
  }

  void applyMotion(char cmd, int speed) {
    outputs_.pwmL = static_cast<uint8_t>(speed);
    outputs_.pwmR = static_cast<uint8_t>(speed);
    switch (cmd) {
      case 'F': outputs_.dirL = 1;  outputs_.dirR = 1;  break;
      case 'B': outputs_.dirL = -1; outputs_.dirR = -1; break;
      case 'L': outputs_.dirL = -1; outputs_.dirR = 1;  break;  // pivot left
      case 'R': outputs_.dirL = 1;  outputs_.dirR = -1; break;  // pivot right
      default:  outputs_ = Outputs{0, 0, 0, 0};         break;
    }
  }

  State state_ = State::Stop;
  Status status_ = Status::Ok;
  char cmd_ = 'S';
  int speed_ = kDefaultSpeed;
  Outputs outputs_ = {0, 0, 0, 0};
  uint32_t lastCmdMs_ = 0;
  bool hasCmd_ = false;
  int distCm_ = -1;
  bool distValid_ = false;
  bool requireSonar_ = false;
  bool sonarSeen_ = false;
  uint32_t lastSonarMs_ = 0;
  int rearCm_ = -1;
  bool rearValid_ = false;
  bool rearSeen_ = false;
  uint32_t lastRearMs_ = 0;
  int batteryMv_ = 0;
  bool batteryLow_ = false;
  bool estop_ = false;
  bool stall_ = false;
  bool obstacleLatched_ = false;
  bool rearLatched_ = false;
  uint32_t accepted_ = 0;
  uint32_t rejected_ = 0;
  uint32_t watchdogTrips_ = 0;
  uint32_t crcFailures_ = 0;
};


// ---------------------------------------------------------------------------
// Closed-loop wheel speed (PI + feed-forward).
//
// The commanded PWM is treated as a *speed request* (60..255 -> 0..maxSpeed),
// so the rover holds the same speed as the pack drains instead of slowing
// down.  Single-channel encoders are enough: direction comes from the driver.
// ---------------------------------------------------------------------------
class WheelSpeedLoop {
 public:
  void configure(float countsPerRev, float wheelCircumferenceMm, float maxSpeedMmS,
                 float kp, float ki) {
    cpr_ = countsPerRev > 1.0f ? countsPerRev : 960.0f;
    circ_ = wheelCircumferenceMm > 1.0f ? wheelCircumferenceMm : 204.0f;
    maxSpeed_ = maxSpeedMmS > 1.0f ? maxSpeedMmS : 350.0f;
    kp_ = kp;
    ki_ = ki;
    reset();
  }

  void reset() {
    integral_ = 0.0f;
    speed_ = 0.0f;
    target_ = 0.0f;
    pwm_ = 0;
    stallMs_ = 0;
    stalled_ = false;
  }

  // counts = pulses since the previous call, throttle = commanded PWM (0..255)
  int update(uint32_t counts, uint16_t dtMs, int throttle) {
    if (throttle <= 0 || dtMs == 0) {
      reset();
      return 0;
    }
    const int thr = clampSpeed(throttle);
    target_ = maxSpeed_ * static_cast<float>(thr - kSpeedMin) /
              static_cast<float>(kSpeedMax - kSpeedMin);

    speed_ = (static_cast<float>(counts) / cpr_) * circ_ * 1000.0f /
             static_cast<float>(dtMs);

    const float err = target_ - speed_;
    integral_ += ki_ * err * (static_cast<float>(dtMs) / 1000.0f);
    if (integral_ > 80.0f) integral_ = 80.0f;
    if (integral_ < -80.0f) integral_ = -80.0f;

    float out = static_cast<float>(thr) + kp_ * err + integral_;
    if (out < 0.0f) out = 0.0f;
    if (out > 255.0f) out = 255.0f;
    pwm_ = static_cast<int>(out + 0.5f);

    if (target_ >= static_cast<float>(kStallMinSpeedMmS) &&
        speed_ < target_ * (static_cast<float>(kStallRatioPct) / 100.0f)) {
      stallMs_ += dtMs;
    } else {
      stallMs_ = 0;
    }
    stalled_ = stallMs_ >= kStallMs;
    return pwm_;
  }

  float speedMmS() const { return speed_; }
  float targetMmS() const { return target_; }
  int pwm() const { return pwm_; }
  bool stalled() const { return stalled_; }

 private:
  float cpr_ = 960.0f;
  float circ_ = 204.0f;
  float maxSpeed_ = 350.0f;
  float kp_ = 0.5f;
  float ki_ = 0.6f;
  float integral_ = 0.0f;
  float speed_ = 0.0f;
  float target_ = 0.0f;
  int pwm_ = 0;
  uint32_t stallMs_ = 0;
  bool stalled_ = false;
};

// ---------------------------------------------------------------------------
// Differential-drive odometry (single-channel encoders, command-signed).
// ---------------------------------------------------------------------------
class DifferentialOdometry {
 public:
  void configure(float wheelCircumferenceMm, float trackMm, float countsPerRev) {
    circ_ = wheelCircumferenceMm > 1.0f ? wheelCircumferenceMm : 204.0f;
    track_ = trackMm > 1.0f ? trackMm : 150.0f;
    cpr_ = countsPerRev > 1.0f ? countsPerRev : 960.0f;
    reset();
  }

  void reset() {
    x_ = 0.0f;
    y_ = 0.0f;
    theta_ = 0.0f;
    dist_ = 0.0f;
    speed_ = 0.0f;
  }

  void update(int32_t dLeftCounts, int32_t dRightCounts, uint16_t dtMs) {
    const float dL = (static_cast<float>(dLeftCounts) / cpr_) * circ_;
    const float dR = (static_cast<float>(dRightCounts) / cpr_) * circ_;
    const float dC = (dL + dR) * 0.5f;
    const float dT = (dR - dL) / track_;

    const float mid = theta_ + dT * 0.5f;
    x_ += dC * cosf(mid);
    y_ += dC * sinf(mid);
    theta_ += dT;
    while (theta_ > 3.14159265f) theta_ -= 6.28318531f;
    while (theta_ < -3.14159265f) theta_ += 6.28318531f;

    const float moved = dC < 0.0f ? -dC : dC;
    dist_ += moved;
    speed_ = dtMs ? (moved * 1000.0f / static_cast<float>(dtMs)) : 0.0f;
  }

  float xMm() const { return x_; }
  float yMm() const { return y_; }
  float thetaRad() const { return theta_; }
  float thetaDeg() const { return theta_ * 57.2957795f; }
  float distanceMm() const { return dist_; }
  float speedMmS() const { return speed_; }

 private:
  float circ_ = 204.0f;
  float track_ = 150.0f;
  float cpr_ = 960.0f;
  float x_ = 0.0f;
  float y_ = 0.0f;
  float theta_ = 0.0f;
  float dist_ = 0.0f;
  float speed_ = 0.0f;
};

// ---------------------------------------------------------------------------
// Gap framer: 15 ms of silence (or CR/LF) terminates a packet.
// A packet split across serial buffers ("F20" + "0") is reassembled, and two
// packets arriving back-to-back are never merged.
// ---------------------------------------------------------------------------
class GapFramer {
 public:
  explicit GapFramer(uint32_t gapUs = kCommandGapUs) : gapUs_(gapUs) { reset(); }

  void reset() {
    len_ = 0;
    buf_[0] = '\0';
    rdyLen_ = 0;
    rdy_[0] = '\0';
    hasRdy_ = false;
    overflow_ = false;
    pending_ = false;
    lastByteUs_ = 0;
  }

  void push(uint8_t b, uint32_t nowUs) {
    if (b == '\n' || b == '\r') {
      if (pending_) finalize();
      return;
    }
    if (pending_ && (nowUs - lastByteUs_) > gapUs_) finalize();
    lastByteUs_ = nowUs;
    pending_ = true;
    if (len_ < kMaxFrameLen - 1) {
      buf_[len_++] = static_cast<char>(b);
      buf_[len_] = '\0';
    } else {
      overflow_ = true;
    }
  }

  void poll(uint32_t nowUs) {
    if (pending_ && (nowUs - lastByteUs_) > gapUs_) finalize();
  }

  bool ready() const { return hasRdy_; }
  const char* frame() const { return rdy_; }
  uint8_t length() const { return rdyLen_; }
  bool overflowed() const { return overflow_; }

  void consume() {
    hasRdy_ = false;
    rdyLen_ = 0;
    rdy_[0] = '\0';
  }

 private:
  void finalize() {
    pending_ = false;
    if (len_ > 0) {
      memcpy(rdy_, buf_, len_);
      rdyLen_ = len_;
      rdy_[rdyLen_] = '\0';
      hasRdy_ = true;
    }
    len_ = 0;
    buf_[0] = '\0';
  }

  uint32_t gapUs_;
  char buf_[kMaxFrameLen];
  char rdy_[kMaxFrameLen];
  uint8_t len_ = 0;
  uint8_t rdyLen_ = 0;
  bool hasRdy_ = false;
  bool pending_ = false;
  bool overflow_ = false;
  uint32_t lastByteUs_ = 0;
};

}  // namespace rover

#endif  // ROVER_SAFETY_CORE_H
