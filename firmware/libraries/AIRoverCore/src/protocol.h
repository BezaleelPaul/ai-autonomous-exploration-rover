/*
 * protocol.h - wire protocol + safety constants shared by BOTH boards.
 *
 * Included by:
 *   firmware/libraries/AIRoverCore/src/safety_core.h   (Uno reflex core)
 *   firmware/esp32/wifi_bridge/wifi_bridge.ino         (ESP32 gateway)
 *
 * No Arduino headers here: the file also compiles on a host for unit tests.
 * The Python mirror lives in software/ai_rover/protocol.py; the test suite
 * asserts that the two never drift apart.
 *
 * Frame on the wire:
 *     <CMD>[<SPEED>][*<CRC>]\n
 *       CMD   : F B L R S (lowercase accepted, normalised to uppercase)
 *       SPEED : optional integer 0..255; motion commands are clamped to
 *               [60, 255] because 60 PWM is the TT gearmotor stiction floor
 *       CRC   : optional CRC-8/SMBUS (poly 0x07, init 0x00) over the body,
 *               two uppercase hex digits. REQUIRED on the ESP32->Uno link;
 *               optional on the USB bench port and on HTTP (TCP already
 *               protects the HTTP hop; the UART is the exposed segment).
 *
 *   e.g.  "F200*6B\n"  (link)     "F200\n"  (typed on the serial monitor)
 *
 * A flipped bit that still parses as a command is the one corruption the
 * whitelist cannot catch, which is why the link checks the CRC.
 */
#ifndef ROVER_PROTOCOL_H
#define ROVER_PROTOCOL_H

#include <stdint.h>
#include <stdio.h>

namespace rover {

constexpr int kForwardGateCm = 15;         // hard forward-obstacle floor
constexpr int kGateSpeedCm = 20;           // extra cm demanded at full speed
constexpr int kRearGateCm = 15;            // reverse-obstacle gate
constexpr uint32_t kLinkWatchdogMs = 500;  // command loss -> motors stop
constexpr uint32_t kSonarPeriodMs = 60;    // HC-SR04 ping cadence
constexpr uint32_t kCommandGapUs = 15000;  // 15 ms inter-byte gap framing
constexpr int kSpeedMin = 60;              // overcomes TT gearmotor stiction
constexpr int kSpeedMax = 255;
constexpr int kDefaultSpeed = 180;
constexpr uint8_t kMaxFrameLen = 16;       // body + "*HH" + NUL
constexpr uint8_t kMaxBodyLen = 8;
constexpr uint32_t kSonarMaxCm = 400;      // HC-SR04 usable range

// Stall detection: target speed above kStallMinSpeedMmS with no encoder
// progress for kStallMs latches a fault.
constexpr uint32_t kStallMs = 1000;
constexpr int kStallMinSpeedMmS = 60;
constexpr int kStallRatioPct = 15;  // measured < 15 % of target = no progress

// 2S Li-ion pack protection (3.2 V/cell cutoff, 3.4 V recovery).
constexpr int kBatteryLowMv = 6400;
constexpr int kBatteryRecoverMv = 6800;

// Uno -> ESP32 health telemetry
constexpr uint32_t kTelemetryPeriodMs = 200;
constexpr uint32_t kTelemetryQuietMs = 120;  // never talk over a command
constexpr uint32_t kHeartbeatHalfPeriodUs = 500;  // 1 kHz square wave

inline bool isMotionCommand(char c) {
  return c == 'F' || c == 'B' || c == 'L' || c == 'R';
}

inline bool isCommand(char c) {
  return isMotionCommand(c) || c == 'S';
}

inline char canonicalCommand(char c) {
  if (c >= 'a' && c <= 'z') c = static_cast<char>(c - 'a' + 'A');
  return isCommand(c) ? c : '\0';
}

inline int clampSpeed(int speed) {
  if (speed < kSpeedMin) return kSpeedMin;
  if (speed > kSpeedMax) return kSpeedMax;
  return speed;
}

/*
 * Forward gate that grows with commanded speed. 15 cm is the floor; at full
 * PWM the rover needs ~35 cm because stopping distance scales with v^2.
 */
inline int requiredGateCm(int speed) {
  const int s = clampSpeed(speed);
  return kForwardGateCm + ((s - kSpeedMin) * kGateSpeedCm) / (kSpeedMax - kSpeedMin);
}

// CRC-8/SMBUS: poly 0x07, init 0x00.  Check value for "123456789" is 0xF4.
inline uint8_t crc8(const char* data, uint8_t len, uint8_t crc = 0) {
  for (uint8_t i = 0; i < len; ++i) {
    crc ^= static_cast<uint8_t>(data[i]);
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x80) ? static_cast<uint8_t>((crc << 1) ^ 0x07)
                         : static_cast<uint8_t>(crc << 1);
    }
  }
  return crc;
}

inline int hexDigit(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return -1;
}

struct Packet {
  char cmd;
  int speed;
  bool hasSpeed;
  bool hasCrc;
  bool crcOk;
};

/*
 * Strict whitelist parser.
 * Rejects: empty / too long, unknown command, non-digit speed, >3 digits,
 * speed > 255, trailing garbage, malformed or mismatched CRC.
 * Accepts one space between command and speed ("F 200").
 */
inline bool parsePacket(const char* buf, uint8_t len, Packet& out) {
  out.cmd = '\0';
  out.speed = 0;
  out.hasSpeed = false;
  out.hasCrc = false;
  out.crcOk = false;

  if (buf == nullptr || len == 0 || len > kMaxFrameLen - 1) return false;

  // Split an optional "*HH" checksum suffix.
  uint8_t bodyLen = len;
  bool crcPresent = false;
  uint8_t crcExpected = 0;
  for (uint8_t i = 0; i < len; ++i) {
    if (buf[i] != '*') continue;
    if (i + 3 != len) return false;  // CRC must be the last 3 characters
    const int hi = hexDigit(buf[i + 1]);
    const int lo = hexDigit(buf[i + 2]);
    if (hi < 0 || lo < 0) return false;
    crcExpected = static_cast<uint8_t>((hi << 4) | lo);
    bodyLen = i;
    crcPresent = true;
    break;
  }

  if (bodyLen == 0 || bodyLen > kMaxBodyLen) return false;

  if (crcPresent) {
    out.hasCrc = true;
    out.crcOk = (crc8(buf, bodyLen) == crcExpected);
    if (!out.crcOk) return false;
  }

  const char cmd = canonicalCommand(buf[0]);
  if (cmd == '\0') return false;
  out.cmd = cmd;

  uint8_t i = 1;
  if (i < bodyLen && buf[i] == ' ') ++i;
  if (i == bodyLen) return true;  // bare command

  int value = 0;
  uint8_t digits = 0;
  for (; i < bodyLen; ++i) {
    const char c = buf[i];
    if (c < '0' || c > '9') return false;
    value = value * 10 + (c - '0');
    if (++digits > 3) return false;
  }
  if (digits == 0 || value > 255) return false;

  out.speed = value;
  out.hasSpeed = true;
  return true;
}

/*
 * Builds the exact bytes to put on the UART, CRC included.
 * Returns the frame length (with the trailing '\n') or 0 on error.
 */
inline uint8_t buildFrame(char cmd, int speed, bool hasSpeed, char* out, uint8_t cap) {
  char body[kMaxBodyLen + 1];
  uint8_t n = 0;
  const char c = canonicalCommand(cmd);
  if (c == '\0' || cap < 8) return 0;

  body[n++] = c;
  if (c != 'S' && hasSpeed) {
    const int v = clampSpeed(speed);
    if (v >= 100) body[n++] = static_cast<char>('0' + v / 100);
    if (v >= 10) body[n++] = static_cast<char>('0' + (v / 10) % 10);
    body[n++] = static_cast<char>('0' + v % 10);
  }

  const uint8_t crc = crc8(body, n);
  const int written = snprintf(out, cap, "%.*s*%02X\n", static_cast<int>(n), body, crc);
  if (written <= 0 || written >= cap) return 0;
  return static_cast<uint8_t>(written);
}

}  // namespace rover

#endif  // ROVER_PROTOCOL_H
