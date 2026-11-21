/*
 * pins.h - Arduino Uno R3 pin map (single source of truth).
 *
 * Verified against the production TB6612FNG module silkscreen:
 *   bottom row, left to right = PWMA, AIN2, AIN1, STBY, BIN1, BIN2, PWMB
 * i.e. AIN2 sits LEFT of AIN1 and PWMB is at the far right end of the row.
 * Do not "fix" the order to match the datasheet drawing.
 *
 * Analog-capable pins are written as their digital numbers (A0=14 ... A5=19)
 * because this header also compiles on a host PC without Arduino.h.
 *
 *   D2  encoder L / rear TRIG   (INT0; depends on the build, see below)
 *   D3  encoder R / rear ECHO   (INT1; depends on the build, see below)
 *   D4  link RX      <- ESP32 GPIO17 TX2 (9600 8N1)
 *   D5  PWMA         left PWM
 *   D6  AIN1         left direction A
 *   D7  AIN2         left direction B   (left of AIN1 on the module)
 *   D8  BIN1         right direction A
 *   D9  PWMB         right PWM          (far right of the module)
 *   D10 BIN2         right direction B
 *   D11 TRIG         front HC-SR04
 *   D12 ECHO         front HC-SR04
 *   D13 status LED
 *   A0  battery sense divider (100k / 47k)
 *   A1  E-stop sense (NC contact to GND, INPUT_PULLUP)
 *   A2  link TX      -> ESP32 GPIO16 RX2 (5V->3.3V divider)
 *   A3  spare
 *   A4  FAULT output, active LOW -> ESP32 GPIO14
 *   A5  heartbeat    1 kHz square wave -> 555 missing-pulse detector + GPIO13
 */
#ifndef ROVER_PINS_H
#define ROVER_PINS_H

#include <stdint.h>

namespace rover {
namespace pins {

// TB6612FNG - left channel
constexpr uint8_t kPwma = 5;   // D5  ~976 Hz Timer0
constexpr uint8_t kAin1 = 6;   // D6
constexpr uint8_t kAin2 = 7;   // D7
// TB6612FNG - right channel
constexpr uint8_t kBin1 = 8;   // D8
constexpr uint8_t kBin2 = 10;  // D10
constexpr uint8_t kPwmb = 9;   // D9  ~490 Hz Timer1
// STBY is driven by the heartbeat interlock (or tied to +5V for bench).
constexpr uint8_t kStby = 0;   // not a GPIO

// HC-SR04 ultrasonic, front
constexpr uint8_t kTrig = 11;  // D11
constexpr uint8_t kEcho = 12;  // D12

// HC-SR04 ultrasonic, rear (optional; enable with -DREAR_SONAR=1)
// NOTE: D2/D3 are shared with the encoders. Enable one, not both.
constexpr uint8_t kRearTrig = 2;   // D2
constexpr uint8_t kRearEcho = 3;   // D3

// Single-channel encoders (optional; enable with -DENCODERS=1).
// D2/D3 are the Uno's only external-interrupt pins; SoftwareSerial already
// owns the pin-change vectors, so INT0/INT1 are the only clean option.
constexpr uint8_t kEncoderLeft = 2;   // D2, INT0
constexpr uint8_t kEncoderRight = 3;  // D3, INT1

// ESP32 link (SoftwareSerial)
constexpr uint8_t kLinkRx = 4;   // D4 <- ESP32 GPIO17 TX2
constexpr uint8_t kLinkTx = 16;  // A2 -> ESP32 GPIO16 RX2 (UART telemetry)

// Status / hardware interlock
constexpr uint8_t kStatusLed = 13;    // onboard LED
constexpr uint8_t kPinHeartbeat = 19;  // A5, 1 kHz -> 555 missing-pulse -> STBY
constexpr uint8_t kPinFaultOut = 18;  // A4, active LOW, mirrored to the ESP32

// Safety inputs
constexpr uint8_t kPinEstop = 15;    // A1, NC contact to GND, INPUT_PULLUP
constexpr uint8_t kPinBattery = 14;  // A0, 100k / 47k divider from the pack

// ---------------------------------------------------------------------------
// Battery divider: Vbat = ADC * 5.0/1024 * (100k + 47k)/47k
// 8.4 V -> 2.686 V at the pin (safe), 6.4 V -> 2.046 V.
// ---------------------------------------------------------------------------
constexpr float kAdcRefV = 5.0f;
constexpr int kAdcMax = 1023;
constexpr float kBatteryDividerRatio = 147.0f / 47.0f;  // 3.1277

// ---------------------------------------------------------------------------
// Drive calibration (encoders). Measure, do not trust the datasheet:
//   * counts/rev  : push the rover exactly one wheel revolution, read ODO
//   * wheel circ  : measure the wheel diameter, or roll 1 m and compare ODO
//   * track       : centre-to-centre distance between the wheels
// Typical yellow TT motor with a 20-slot magnetic encoder and 1:48 gearbox
// = 960 counts per output revolution.
// ---------------------------------------------------------------------------
constexpr float kEncoderCpr = 960.0f;
constexpr float kWheelCircumferenceMm = 204.0f;  // 65 mm wheel
constexpr float kTrackMm = 150.0f;
constexpr float kMaxSpeedMmS = 350.0f;           // at PWM 255
constexpr float kSpeedKp = 0.5f;
constexpr float kSpeedKi = 0.6f;
constexpr uint16_t kControlPeriodMs = 50;

// USB telemetry baud (human log).  UART link stays at 9600 8N1.
constexpr uint32_t kTelemetryBaud = 115200;
constexpr uint32_t kLinkBaud = 9600;

}  // namespace pins
}  // namespace rover

#endif  // ROVER_PINS_H
