// Red-team host harness: compiles and executes the REAL
// arduino/rover_controller/rover_controller.ino against stubbed Arduino APIs,
// then replays adversarial serial/ultrasonic/clock inputs and prints a trace.
//
// Usage:  firmware_host <scenario>
// Output: one line per loop() iteration:  iter=<n> cmd=<currentCmd> motors=<state>
//         plus any TX text emitted by the sketch (STATUS:/DIST: lines).
//
// SIMULATED: no MCU, no real UART, no real timing. Logic under test is the
// actual firmware source; the electrical/timing behaviour is NOT proven.

#include "arduino_stubs.h"

// The Arduino builder auto-generates function prototypes for .ino files;
// g++ does not, so declare them here (this is what arduino-cli does).
void stopMotors();
float readDistance();
void drive(char cmd);
void setup();
void loop();

#include "../../arduino/rover_controller/rover_controller.ino"

#include <iostream>
#include <string>
#include <vector>

// Pin numbers come from the sketch itself.
static std::string motor_state() {
  // GPIO that have never been configured as outputs are high-Z (input) at
  // reset; a real L298N then sees floating ENA/ENB/INx lines.
  if (!g_pin_mode[ENA] || !g_pin_mode[ENB]) return "HIGH-Z";
  bool ena = g_pwm[ENA] > 0;
  bool enb = g_pwm[ENB] > 0;
  int i1 = g_pin_val[IN1], i2 = g_pin_val[IN2];
  int i3 = g_pin_val[IN3], i4 = g_pin_val[IN4];
  if (!ena && !enb) return "STOP";
  if (i1 == 1 && i2 == 0 && i3 == 1 && i4 == 0) return "F";
  if (i1 == 0 && i2 == 1 && i3 == 0 && i4 == 1) return "B";
  if (i1 == 0 && i2 == 1 && i3 == 1 && i4 == 0) return "L";
  if (i1 == 1 && i2 == 0 && i3 == 0 && i4 == 1) return "R";
  if (i1 == 0 && i2 == 0 && i3 == 0 && i4 == 0) return "STOP";
  return "MIXED";
}

static int g_iter = 0;

static void step(bool trace) {
  Serial.tx.clear();
  loop();
  if (trace) {
    std::cout << "iter=" << g_iter << " cmd=" << currentCmd
              << " motors=" << motor_state() << " tx=" << Serial.tx << "\n";
  }
  ++g_iter;
}

static void steps(int n, bool trace = true) {
  for (int i = 0; i < n; ++i) step(trace);
}

static void feed(const std::string &s) { Serial.feed(s); }

static void finish() {
  std::cout << "FINAL cmd=" << currentCmd << " motors=" << motor_state()
            << " lastCmdTime=" << lastCmdTime << " millis=" << g_millis
            << "\n";
}

int main(int argc, char **argv) {
  std::string sc = argc > 1 ? argv[1] : "help";
  g_millis = 1000;  // arbitrary post-boot time

  if (sc == "startup") {
    setup();
    std::cout << "after setup motors=" << motor_state() << "\n";
    finish();
    return 0;
  }

  if (sc == "valid") {
    setup();
    for (std::string c : {"F", "B", "L", "R", "S"}) {
      feed(c + "\n");
      steps(2);  // one byte consumed per loop(): cmd byte then newline
    }
    finish();
    return 0;
  }

  if (sc == "invalid_char") {
    setup();
    feed("F\n");
    steps(2);
    feed("X");
    steps(1);
    finish();
    return 0;
  }

  if (sc == "binary") {
    setup();
    feed("F\n");
    steps(2);
    std::string bin;
    bin.push_back((char)0x00);
    bin.push_back((char)0x80);
    bin.push_back((char)0xFF);
    bin.push_back((char)0x7F);
    feed(bin);
    steps(4);
    finish();
    return 0;
  }

  if (sc == "malformed_word") {
    // Corrupted multi-char command: firmware reads ONE byte per loop().
    setup();
    feed("FORWARD");
    steps(8);
    finish();
    return 0;
  }

  if (sc == "corrupt_ends_F") {
    // Noise that happens to end with a motion byte -> motors keep running.
    setup();
    feed("abcF");
    steps(5);
    finish();
    return 0;
  }

  if (sc == "watchdog") {
    setup();
    feed("F\n");
    steps(1);
    std::cout << "driving, advancing clock 3001ms\n";
    g_millis += 3001;
    steps(2);
    finish();
    return 0;
  }

  if (sc == "watchdog_newline_only") {
    // Newlines must NOT refresh the comm watchdog.
    setup();
    feed("F\n");
    steps(1);
    g_millis += 3001;
    feed("\n\n\n\n\n");
    steps(5);
    finish();
    return 0;
  }

  if (sc == "watchdog_exact") {
    // Boundary: exactly COMM_TIMEOUT_MS must not trip (strict >).
    setup();
    feed("F\n");
    steps(1);
    g_millis += 3000;
    steps(1);
    std::cout << "at +3000 motors=" << motor_state() << "\n";
    g_millis += 1;
    steps(1);
    std::cout << "at +3001 motors=" << motor_state() << "\n";
    finish();
    return 0;
  }

  if (sc == "obstacle") {
    setup();
    // ~10 cm  => dur = 10 / 0.0343 * 2 = 583
    g_pulse_dur = 583;
    feed("F\n");
    steps(2);
    feed("L\n");
    steps(2);
    feed("B\n");
    steps(2);
    finish();
    return 0;
  }

  if (sc == "sensor_dead") {
    // HC-SR04 unplugged / no echo => pulseIn returns 0 => distance -1.
    setup();
    feed("F\n");
    steps(1);
    g_pulse_dur = 0;  // sensor dies mid-run
    steps(3);
    finish();
    return 0;
  }

  if (sc == "sensor_dead_from_boot") {
    setup();
    g_pulse_dur = 0;
    feed("F\n");
    steps(3);
    finish();
    return 0;
  }

  if (sc == "reboot") {
    setup();
    feed("F\n");
    steps(1);
    std::cout << "motors before reboot=" << motor_state() << "\n";
    // Emulate an MCU reset. On AVR the CRT re-runs static initialisers
    // (currentCmd='S', lastCmdTime=0) and all GPIO return to INPUT/high-Z
    // before setup() executes.
    for (int p = 0; p < MAXPINS; ++p) {
      g_pin_val[p] = 0;
      g_pwm[p] = 0;
      g_pin_mode[p] = 0;
    }
    g_millis = 0;
    currentCmd = 'S';  // static initialiser value restored by the CRT
    lastCmdTime = 0;
    lastTelemetry = 0;
    std::cout << "immediately after reset, before setup(): motors="
              << motor_state() << "\n";
    setup();
    steps(1);
    finish();
    return 0;
  }

  if (sc == "flood_valid") {
    setup();
    std::string flood(500, 'F');
    feed(flood);
    steps(520, false);
    std::cout << "after 500xF: cmd=" << currentCmd
              << " motors=" << motor_state() << "\n";
    finish();
    return 0;
  }

  if (sc == "flood_invalid") {
    setup();
    feed("F\n");
    steps(1);
    std::string flood(500, 'Z');
    feed(flood);
    steps(520, false);
    std::cout << "after 500xZ: cmd=" << currentCmd
              << " motors=" << motor_state() << "\n";
    finish();
    return 0;
  }

  if (sc == "flood_then_silence") {
    setup();
    std::string flood(100, 'F');
    feed(flood);
    steps(100, false);
    std::cout << "during flood motors=" << motor_state() << "\n";
    g_millis += 3001;
    steps(2);
    finish();
    return 0;
  }

  if (sc == "partial_then_valid") {
    setup();
    feed("O");
    steps(1);
    feed("F");
    steps(1);
    finish();
    return 0;
  }

  if (sc == "case_insensitive") {
    setup();
    feed("f\n");
    steps(1);
    std::cout << "lowercase f -> cmd=" << currentCmd
              << " motors=" << motor_state() << "\n";
    finish();
    return 0;
  }

  if (sc == "telemetry") {
    setup();
    g_pulse_dur = 583;  // ~10cm
    steps(3);
    finish();
    return 0;
  }

  if (sc == "encoders") {
    // Phase 9+: wheel-encoder ticks counted by ISR, reported as TICKS:<l>,<r>.
    setup();
    feed("F\n");
    steps(1);
    for (int i = 0; i < 5; ++i) encISR_L();
    for (int i = 0; i < 2; ++i) encISR_R();
    g_millis += 250;  // past TELEMETRY_MS (200), well under watchdog (3000)
    steps(2);
    std::cout << "ticks L=" << encTicksL << " R=" << encTicksR << "\n";
    finish();
    return 0;
  }

  if (sc == "speed_suffix") {
    // Protocol v2: optional PWM suffix; overspeed (>255) must fail safe.
    setup();
    feed("F180\n");
    steps(1);
    std::cout << "after F180 pwm L=" << pwmCmdL << " R=" << pwmCmdR << "\n";
    feed("L77\n");
    steps(1);
    std::cout << "after L77 pwm L=" << pwmCmdL << " R=" << pwmCmdR
              << " cmd=" << currentCmd << "\n";
    feed("B\n");  // bare command keeps the sticky speed (never resets)
    steps(1);
    std::cout << "after bare B pwm L=" << pwmCmdL << " R=" << pwmCmdR
              << " cmd=" << currentCmd << "\n";
    feed("R999\n");  // 999 > 255 => malformed => STOP
    steps(1);
    std::cout << "after overspeed: cmd=" << currentCmd
              << " motors=" << motor_state() << "\n";
    finish();
    return 0;
  }

  if (sc == "velocity") {
    // Phase 9+ P velocity loop: under-speed boosts PWM, over-speed trims it,
    // silent encoders fall back to open-loop activeSpeed (fail-safe).
    encodersEnabled = true;
    setup();
    feed("F\n");
    steps(1);  // first period: 0 ticks -> 150 + 1.2*(50-0) = 210
    std::cout << "pwm L=" << pwmCmdL << " R=" << pwmCmdR << "\n";
    for (int i = 0; i < 4; ++i) {
      for (int k = 0; k < 3; ++k) {
        encISR_L();
        encISR_R();
      }  // 3 ticks / 50ms = 60 tps > 50 target -> 150 + 1.2*(-10) = 138
      g_millis += 50;
      steps(1);
      std::cout << "pwm L=" << pwmCmdL << " R=" << pwmCmdR << "\n";
    }
    for (int i = 0; i < VEL_DEAD_PERIODS; ++i) {
      g_millis += 50;
      steps(1);  // silent encoders: dead counter climbs to fallback
    }
    std::cout << "fallback pwm L=" << pwmCmdL << " R=" << pwmCmdR << "\n";
    std::cout << "ticks L=" << encTicksL << " R=" << encTicksR << "\n";
    finish();
    return 0;
  }

  std::cout << "unknown scenario\n";
  return 2;
}
