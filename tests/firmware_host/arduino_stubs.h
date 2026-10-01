// Host-side stub of the Arduino API so that the *real* rover_controller.ino
// can be compiled and executed off-target for red-team testing.
// Everything here is a simulation of the MCU environment (no hardware timing,
// no real PWM, no real UART). Results are SIMULATED.

#pragma once

#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <string>

// ---- controllable clock -------------------------------------------------
inline unsigned long g_millis = 0;
inline unsigned long millis() { return g_millis; }
inline void delay(unsigned long) {}
inline void delayMicroseconds(unsigned int) {}

// ---- pins ---------------------------------------------------------------
#ifndef HIGH
#define HIGH 1
#endif
#ifndef LOW
#define LOW 0
#endif
#ifndef INPUT
#define INPUT 0
#endif
#ifndef OUTPUT
#define OUTPUT 1
#endif
#ifndef INPUT_PULLUP
#define INPUT_PULLUP 2
#endif
#ifndef FALLING
#define FALLING 2
#endif

const int MAXPINS = 64;
inline int g_pin_mode[MAXPINS];
inline int g_pin_val[MAXPINS];
inline int g_pwm[MAXPINS];

inline void pinMode(int pin, int) {
  if (pin >= 0 && pin < MAXPINS) g_pin_mode[pin] = 1;
}
inline void digitalWrite(int pin, int v) {
  if (pin >= 0 && pin < MAXPINS) g_pin_val[pin] = (v ? 1 : 0);
}
inline void analogWrite(int pin, int v) {
  if (pin >= 0 && pin < MAXPINS) g_pwm[pin] = v;
}

// ---- interrupts (wheel encoders, Phase 9+) ------------------------------
// Host harness invokes the ISRs directly; attach/detach are recorded only.
inline int digitalPinToInterrupt(int pin) { return pin; }
inline void attachInterrupt(int, void (*)(), int) {}
inline void noInterrupts() {}
inline void interrupts() {}

// ---- HC-SR04 ------------------------------------------------------------
// g_pulse_dur == 0 models "no echo" (pulseIn timeout), which the firmware
// converts to distance -1.0.
inline long g_pulse_dur = 1750;  // ~30 cm default: (dur * 0.0343)/2
inline unsigned long pulseIn(int, int, unsigned long) {
  return (unsigned long)g_pulse_dur;
}

// ---- Serial -------------------------------------------------------------
struct FakeSerial {
  std::deque<char> rx;
  std::string tx;
  void begin(long) {}
  int available() { return (int)rx.size(); }
  int read() {
    if (rx.empty()) return -1;
    char c = rx.front();
    rx.pop_front();
    return (unsigned char)c;
  }
  void feed(const std::string &s) {
    for (char c : s) rx.push_back(c);
  }
  void feed(const char *s) { feed(std::string(s)); }
  void print(const char *s) { tx += s; }
  void println(const char *s) { tx += std::string(s) + "\n"; }
  void println(double v, int digits = 2) {
    char b[64];
    snprintf(b, sizeof b, "%.*f", digits, v);
    tx += b;
    tx += "\n";
  }
  void println(int v) { tx += std::to_string(v) + "\n"; }
  void print(unsigned long v) { tx += std::to_string(v); }
  void println(unsigned long v) { tx += std::to_string(v) + "\n"; }
};
inline FakeSerial Serial;
