// Native host tests for the AI Rover reflex core.
//
// Build (from the repo root):
//   g++ -std=c++17 -Wall -Wextra -I firmware/arduino/motion_safety
//       tests/native/test_safety_core.cpp -o /tmp/test_safety_core
//
// No Arduino, no hardware: the same header that ships to the Uno runs here.

#include <cmath>
#include <cstdio>
#include <cstring>

#include "safety_core.h"

using namespace rover;

static int g_checks = 0;
static int g_failures = 0;

#define CHECK(cond)                                                              \
  do {                                                                           \
    ++g_checks;                                                                  \
    if (!(cond)) {                                                               \
      ++g_failures;                                                              \
      std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond);                \
    }                                                                            \
  } while (0)

#define CHECK_EQ(a, b)                                                           \
  do {                                                                           \
    ++g_checks;                                                                  \
    const auto _va = (a);                                                        \
    const auto _vb = (b);                                                        \
    if (!(_va == _vb)) {                                                         \
      ++g_failures;                                                              \
      std::printf("FAIL %s:%d  %s == %s (%ld vs %ld)\n", __FILE__, __LINE__, #a, \
                  #b, static_cast<long>(_va), static_cast<long>(_vb));           \
    }                                                                            \
  } while (0)

// ---------------------------------------------------------------------------
static void test_boot_is_stopped() {
  SafetyCore core;
  core.begin(1000);
  CHECK(core.state() == State::Stop);
  CHECK(core.status() == Status::Ok);
  CHECK_EQ(core.outputs().pwmL, 0);
  CHECK_EQ(core.outputs().pwmR, 0);
  CHECK_EQ(core.outputs().dirL, 0);
  CHECK_EQ(core.outputs().dirR, 0);
  CHECK_EQ(core.command(), 'S');
  CHECK(core.forwardBlocked());  // no sonar reading yet -> forward refused
  CHECK_EQ(core.distanceCm(), -1);
}

static void test_forward_gate() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(40, true, 5);  // gate @200 PWM is 29 cm
  core.acceptCommand('F', 200, 10);
  CHECK(core.state() == State::Go);
  CHECK_EQ(core.outputs().pwmL, 200);
  CHECK_EQ(core.outputs().dirL, 1);
  CHECK_EQ(core.outputs().dirR, 1);

  // 14 cm: refused, motors to zero, intent remembered
  core.updateSonar(14, true, 20);
  CHECK(core.state() == State::Blocked);
  CHECK(core.status() == Status::Blocked);
  CHECK(core.obstacleLatched());
  CHECK_EQ(core.outputs().pwmL, 0);
  CHECK_EQ(core.outputs().pwmR, 0);
}

static void test_gate_boundary_is_inclusive_at_min_speed() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(kForwardGateCm, true, 1);  // 15 cm, 60 PWM -> 15 cm gate
  core.acceptCommand('F', kSpeedMin, 2);
  CHECK(core.state() == State::Go);

  SafetyCore low;
  low.begin(0);
  low.updateSonar(kForwardGateCm - 1, true, 1);
  low.acceptCommand('F', kSpeedMin, 2);
  CHECK(low.state() == State::Blocked);
}

static void test_gate_scales_with_speed() {
  CHECK_EQ(requiredGateCm(kSpeedMin), kForwardGateCm);
  CHECK_EQ(requiredGateCm(kSpeedMax), kForwardGateCm + kGateSpeedCm);
  CHECK_EQ(requiredGateCm(180), 27);
  CHECK_EQ(requiredGateCm(200), 29);

  SafetyCore slow;
  slow.begin(0);
  slow.updateSonar(16, true, 1);
  slow.acceptCommand('F', kSpeedMin, 2);
  CHECK(slow.state() == State::Go);

  SafetyCore fast;
  fast.begin(0);
  fast.updateSonar(30, true, 1);  // fine at 60 PWM, not at 255
  fast.acceptCommand('F', kSpeedMax, 2);
  CHECK(fast.state() == State::Blocked);

  SafetyCore fastOk;
  fastOk.begin(0);
  fastOk.updateSonar(35, true, 1);
  fastOk.acceptCommand('F', kSpeedMax, 2);
  CHECK(fastOk.state() == State::Go);
}

static void test_dead_sensor_blocks_forward() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(30, true, 1);
  core.acceptCommand('F', 120, 2);
  CHECK(core.state() == State::Go);

  core.updateSonar(-1, false, 50);
  CHECK(core.state() == State::Blocked);
  CHECK_EQ(core.distanceCm(), -1);
  CHECK(core.forwardBlocked());
}

static void test_dead_sensor_blocks_before_moving() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(-1, false, 1);
  core.acceptCommand('F', 120, 2);
  CHECK(core.state() == State::Blocked);
  CHECK_EQ(core.outputs().pwmL, 0);
}

static void test_escape_commands_while_blocked() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(10, true, 1);
  core.acceptCommand('F', 120, 2);
  CHECK(core.state() == State::Blocked);

  core.acceptCommand('B', 120, 3);
  CHECK(core.state() == State::Go);
  CHECK_EQ(core.outputs().dirL, -1);
  CHECK_EQ(core.outputs().dirR, -1);

  core.updateSonar(9, true, 4);
  core.acceptCommand('L', 120, 5);
  CHECK(core.state() == State::Go);
  CHECK_EQ(core.outputs().dirL, -1);
  CHECK_EQ(core.outputs().dirR, 1);

  core.acceptCommand('R', 120, 6);
  CHECK_EQ(core.outputs().dirL, 1);
  CHECK_EQ(core.outputs().dirR, -1);
}

static void test_obstacle_clear_requires_new_command() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(10, true, 1);
  core.acceptCommand('F', 120, 2);
  CHECK(core.state() == State::Blocked);
  core.updateSonar(80, true, 3);
  CHECK(core.state() == State::Blocked);  // never resumes on its own
  core.acceptCommand('F', 120, 4);
  CHECK(core.state() == State::Go);
}

static void test_pivot_directions() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(100, true, 1);
  core.acceptCommand('L', 100, 2);
  PinLevels l = pinLevels(core.outputs());
  CHECK_EQ(l.ain1, 0);
  CHECK_EQ(l.ain2, 1);
  CHECK_EQ(l.bin1, 1);
  CHECK_EQ(l.bin2, 0);

  core.acceptCommand('R', 100, 3);
  PinLevels r = pinLevels(core.outputs());
  CHECK_EQ(r.ain1, 1);
  CHECK_EQ(r.ain2, 0);
  CHECK_EQ(r.bin1, 0);
  CHECK_EQ(r.bin2, 1);
}

static void test_watchdog() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(50, true, 0);
  core.acceptCommand('F', 180, 100);
  core.tick(600);  // 500 ms after the command
  CHECK(core.state() == State::Go);
  core.tick(601);
  CHECK(core.state() == State::Timeout);
  CHECK_EQ(core.outputs().pwmL, 0);
  CHECK_EQ(core.outputs().pwmR, 0);
  CHECK_EQ(core.watchdogTrips(), 1);

  // A fresh command recovers.
  core.acceptCommand('F', 180, 700);
  CHECK(core.state() == State::Go);
}

static void test_watchdog_refresh_and_boot_exemption() {
  SafetyCore core;
  core.begin(0);
  core.tick(100000);  // no command ever -> stays stopped, no trip
  CHECK(core.state() == State::Stop);
  CHECK_EQ(core.watchdogTrips(), 0);

  core.updateSonar(50, true, 100000);
  core.acceptCommand('F', 200, 100000);
  core.acceptCommand('F', 200, 100300);  // refreshed
  core.tick(100700);
  CHECK(core.state() == State::Go);
  core.tick(100801);
  CHECK(core.state() == State::Timeout);
}

static void test_watchdog_does_not_fire_when_stopped() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(50, true, 0);
  core.acceptCommand('S', 0, 10);
  core.tick(5000);
  CHECK(core.state() == State::Stop);
  CHECK_EQ(core.watchdogTrips(), 0);
}

static void test_explicit_stop() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(50, true, 0);
  core.acceptCommand('F', 200, 1);
  core.acceptCommand('S', 0, 2);
  CHECK(core.state() == State::Stop);
  CHECK_EQ(core.command(), 'S');
  CHECK_EQ(core.outputs().pwmL, 0);
  CHECK_EQ(core.outputs().dirL, 0);
}

static void test_speed_clamping_and_default() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(50, true, 0);
  core.acceptCommand('F', 10, 1);
  CHECK_EQ(core.speed(), kSpeedMin);
  CHECK_EQ(core.outputs().pwmL, kSpeedMin);

  core.acceptCommand('F', 300, 2);
  CHECK_EQ(core.speed(), kSpeedMax);

  SafetyCore bare;
  bare.begin(0);
  bare.updateSonar(50, true, 0);
  bare.acceptFrame("F", 1, 1);  // no speed -> default
  CHECK_EQ(bare.speed(), kDefaultSpeed);
  CHECK_EQ(bare.outputs().pwmL, kDefaultSpeed);
}

static void test_packet_parser() {
  Packet p;
  CHECK(parsePacket("F200", 4, p) && p.cmd == 'F' && p.speed == 200 && p.hasSpeed);
  CHECK(parsePacket("f", 1, p) && p.cmd == 'F' && !p.hasSpeed);
  CHECK(parsePacket("S", 1, p) && p.cmd == 'S');
  CHECK(parsePacket("L 90", 4, p) && p.cmd == 'L' && p.speed == 90);
  CHECK(parsePacket("R000", 4, p) && p.speed == 0);

  CHECK(!parsePacket("", 0, p));
  CHECK(!parsePacket("Z", 1, p));
  CHECK(!parsePacket("F999", 4, p));
  CHECK(!parsePacket("F1234", 5, p));
  CHECK(!parsePacket("F20x", 4, p));
  CHECK(!parsePacket("F  200", 6, p));
  CHECK(!parsePacket("FF", 2, p));
  CHECK(!parsePacket("F256", 4, p));
  CHECK(!parsePacket("999999999", 9, p));
}

static void test_bad_packet_is_discarded_but_motion_continues() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(50, true, 0);
  core.acceptFrame("F200", 4, 10);
  CHECK(core.state() == State::Go);
  CHECK(!core.acceptFrame("F999", 4, 20));
  CHECK(core.status() == Status::Error);
  CHECK(core.state() == State::Go);  // discarded, still driving
  CHECK_EQ(core.rejected(), 1);
  core.tick(520);  // watchdog then stops it
  CHECK(core.state() == State::Timeout);
}

static void test_accept_frame_updates_watchdog() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(60, true, 0);
  core.acceptFrame("F200", 4, 10);
  core.acceptFrame("F210", 4, 400);
  core.tick(899);
  CHECK(core.state() == State::Go);
  core.tick(901);
  CHECK(core.state() == State::Timeout);
}

// ---------------------------------------------------------------------------
static void test_gap_framer_reassembles_split_packets() {
  GapFramer f;
  const char* part1 = "F20";
  const char* part2 = "0";
  uint32_t t = 1000;
  for (const char* c = part1; *c; ++c) f.push(static_cast<uint8_t>(*c), t += 100);
  CHECK(!f.ready());
  for (const char* c = part2; *c; ++c) f.push(static_cast<uint8_t>(*c), t += 100);
  CHECK(!f.ready());
  f.poll(t + kCommandGapUs);  // exactly the gap: not yet
  CHECK(!f.ready());
  f.poll(t + kCommandGapUs + 1);
  CHECK(f.ready());
  CHECK_EQ(std::strcmp(f.frame(), "F200"), 0);
  CHECK_EQ(f.length(), 4);
}

static void test_gap_framer_separates_back_to_back_packets() {
  GapFramer f;
  uint32_t t = 0;
  for (const char* c = "F200\n"; *c; ++c) f.push(static_cast<uint8_t>(*c), t += 50);
  CHECK(f.ready());
  CHECK_EQ(std::strcmp(f.frame(), "F200"), 0);
  f.consume();
  CHECK(!f.ready());

  for (const char* c = "S\n"; *c; ++c) f.push(static_cast<uint8_t>(*c), t += 50);
  CHECK(f.ready());
  CHECK_EQ(std::strcmp(f.frame(), "S"), 0);  // never merged with the previous
}

static void test_gap_framer_newline_terminates() {
  GapFramer f;
  uint32_t t = 0;
  for (const char* c = "F200"; *c; ++c) f.push(static_cast<uint8_t>(*c), t += 50);
  f.push('\r', t += 50);
  f.push('\n', t += 50);
  CHECK(f.ready());
  CHECK_EQ(std::strcmp(f.frame(), "F200"), 0);
  CHECK_EQ(f.length(), 4);
}

static void test_gap_framer_overflow() {
  GapFramer f;
  uint32_t t = 0;
  for (int i = 0; i < 30; ++i) f.push('A', t += 10);
  f.poll(t + kCommandGapUs + 1);
  CHECK(f.ready());
  CHECK(f.overflowed());
}

static void test_gap_framer_ignores_empty_gap() {
  GapFramer f;
  f.poll(100000);
  CHECK(!f.ready());
  f.push('\n', 100001);
  CHECK(!f.ready());
}

// ---------------------------------------------------------------------------
static void test_median_filter() {
  MedianFilter3 m;
  m.push(10);
  m.push(10);
  CHECK_EQ(m.push(10), 10);
  CHECK_EQ(m.push(200), 10);  // single spike rejected
  CHECK_EQ(m.push(10), 10);
  CHECK_EQ(m.push(-1), -1);   // invalid bypasses the window
  m.reset();
  CHECK_EQ(m.push(50), 50);
}


// ---------------------------------------------------------------------------
static void test_crc8_and_frame_builder() {
  CHECK_EQ(crc8("123456789", 9), 0xF4);  // CRC-8/SMBUS check vector

  char buf[16];
  uint8_t n = buildFrame('F', 200, true, buf, sizeof(buf));
  CHECK_EQ(n, 8);
  CHECK_EQ(std::strcmp(buf, "F200*B1\n"), 0);

  n = buildFrame('f', 0, true, buf, sizeof(buf));
  CHECK_EQ(std::strcmp(buf, "F60*EC\n"), 0);  // clamped + uppercase

  n = buildFrame('S', 180, true, buf, sizeof(buf));
  CHECK(buf[0] == 'S' && buf[1] == '*' && buf[n - 1] == '\n');

  Packet p;
  CHECK(parsePacket("F200*B1", 7, p));
  CHECK(p.cmd == 'F' && p.speed == 200 && p.hasCrc && p.crcOk);
  CHECK(parsePacket("F200*b1", 7, p) && p.crcOk);  // lowercase hex
  CHECK(!parsePacket("F200*B2", 7, p));            // wrong CRC
  CHECK(!parsePacket("F200*B", 6, p));             // too short
  CHECK(!parsePacket("F200*B11", 8, p));           // too long
  CHECK(!parsePacket("F200*GG", 7, p));            // not hex
  CHECK(parsePacket("F200", 4, p) && !p.hasCrc);   // legacy form
}

static void test_crc_required_on_the_link() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(100, true, 0);

  CHECK(!core.acceptFrame("F200", 4, 10, true));  // missing CRC -> rejected
  CHECK(core.state() == State::Stop);
  CHECK_EQ(core.rejected(), 1);

  CHECK(core.acceptFrame("F200*B1", 7, 20, true));
  CHECK(core.state() == State::Go);

  CHECK(!core.acceptFrame("F200*00", 7, 30, true));  // corrupt -> rejected
  CHECK_EQ(core.crcFailures(), 1);
  CHECK(core.state() == State::Go);  // discarded, current motion continues

  // The USB bench port accepts both forms.
  SafetyCore usb;
  usb.begin(0);
  usb.updateSonar(100, true, 0);
  CHECK(usb.acceptFrame("F200", 4, 10, false));
  CHECK(usb.acceptFrame("F180*A4", 7, 20, false));
  CHECK_EQ(usb.state(), State::Go);
}

static void test_estop_latches_a_fault() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(100, true, 0);
  core.acceptCommand('F', 120, 1);
  CHECK(core.state() == State::Go);

  core.setEstop(true);
  CHECK(core.state() == State::Fault);
  CHECK(core.faultActive());
  CHECK(core.faultReason() == Fault::Estop);
  CHECK_EQ(core.outputs().pwmL, 0);

  core.acceptCommand('F', 120, 2);
  CHECK(core.state() == State::Fault);  // motion refused while engaged
  core.acceptCommand('B', 120, 3);
  CHECK(core.state() == State::Fault);
  core.acceptCommand('S', 0, 4);
  CHECK(core.state() == State::Fault);  // stop reports the fault, not "OK"

  // The link watchdog must never overwrite a fault.
  core.acceptCommand('F', 120, 5);
  core.tick(100000);
  CHECK(core.state() == State::Fault);

  core.setEstop(false);
  CHECK(core.state() == State::Stop);
  CHECK(!core.faultActive());
  core.acceptCommand('F', 120, 6);
  CHECK(core.state() == State::Go);  // a fresh command is required
}

static void test_battery_cutoff_and_recovery() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(100, true, 0);
  core.updateBatteryMv(7400);
  CHECK(!core.batteryLow());
  core.acceptCommand('F', 120, 1);
  CHECK(core.state() == State::Go);

  core.updateBatteryMv(kBatteryLowMv - 1);
  CHECK(core.batteryLow());
  CHECK(core.faultReason() == Fault::BatteryLow);
  CHECK(core.state() == State::Fault);
  CHECK_EQ(core.outputs().pwmL, 0);

  core.acceptCommand('F', 120, 2);
  CHECK(core.state() == State::Fault);

  // Hysteresis: must climb above the recovery threshold to clear.
  core.updateBatteryMv(kBatteryLowMv + 100);
  CHECK(core.state() == State::Fault);
  core.updateBatteryMv(kBatteryRecoverMv + 100);
  CHECK(core.state() == State::Stop);
  CHECK(!core.batteryLow());
}

static void test_estop_has_priority_over_battery() {
  SafetyCore core;
  core.begin(0);
  core.updateBatteryMv(kBatteryLowMv - 100);
  core.setEstop(true);
  CHECK(core.faultReason() == Fault::Estop);
  core.setEstop(false);
  CHECK(core.faultReason() == Fault::BatteryLow);
  CHECK(core.state() == State::Fault);
}

static void test_rear_gate_only_when_a_rear_sensor_is_present() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(100, true, 0);
  core.acceptCommand('B', 120, 1);
  CHECK(core.state() == State::Go);  // no rear sensor fitted -> reverse allowed

  SafetyCore rear;
  rear.begin(0);
  rear.updateSonar(100, true, 0);
  rear.updateRearSonar(10, true, 1);
  rear.acceptCommand('B', 120, 2);
  CHECK(rear.state() == State::Blocked);

  rear.acceptCommand('L', 120, 3);
  CHECK(rear.state() == State::Go);

  // A dead rear sensor after it has been seen is fail-safe.
  rear.updateRearSonar(-1, false, 4);
  rear.acceptCommand('B', 120, 5);
  CHECK(rear.state() == State::Blocked);
}

static void test_rear_obstacle_stops_a_reversing_rover() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(100, true, 0);
  core.updateRearSonar(60, true, 1);
  core.acceptCommand('B', 120, 2);
  CHECK(core.state() == State::Go);

  core.updateRearSonar(9, true, 3);
  CHECK(core.state() == State::Blocked);
  CHECK_EQ(core.outputs().pwmL, 0);
}


// ---------------------------------------------------------------------------
static void test_speed_loop_tracks_the_requested_speed() {
  WheelSpeedLoop loop;
  loop.configure(960.0f, 204.0f, 350.0f, 0.5f, 0.6f);

  CHECK_EQ(loop.update(0, 50, 0), 0);  // throttle 0 -> no drive

  // 255 PWM asks for 350 mm/s. 82 counts in 50 ms = 348.5 mm/s.
  const int full = loop.update(82, 50, 255);
  CHECK(full >= 240 && full <= 255);
  CHECK(loop.speedMmS() > 340.0f && loop.speedMmS() < 360.0f);

  // 180 PWM asks for ~215 mm/s. 51 counts = 216.75 mm/s -> near feed-forward.
  loop.reset();
  const int trimmed = loop.update(51, 50, 180);
  CHECK(trimmed >= 176 && trimmed <= 183);

  // Wheels faster than requested -> back off.
  loop.reset();
  CHECK(loop.update(200, 50, 180) < 180);

  // Wheels stalled but not long enough -> add power, still bounded.
  loop.reset();
  const int boosting = loop.update(0, 50, 180);
  CHECK(boosting >= 180 && boosting <= 255);
}

static void test_speed_loop_stall_window() {
  WheelSpeedLoop loop;
  loop.configure(960.0f, 204.0f, 350.0f, 0.5f, 0.6f);
  for (int i = 0; i < 19; ++i) {  // 950 ms of no progress
    loop.update(0, 50, 200);
    CHECK(!loop.stalled());
  }
  loop.update(0, 50, 200);
  CHECK(loop.stalled());  // 1000 ms

  loop.update(100, 50, 200);  // movement clears the window
  CHECK(!loop.stalled());
  loop.update(0, 50, 0);  // stop resets everything
  CHECK(!loop.stalled());
  CHECK_EQ(loop.pwm(), 0);
}

static void test_stall_fault_requires_acknowledgement() {
  SafetyCore core;
  core.begin(0);
  core.updateSonar(100, true, 0);
  core.acceptCommand('F', 180, 1);
  CHECK(core.state() == State::Go);

  core.setStall(true);
  CHECK(core.state() == State::Fault);
  CHECK(core.faultReason() == Fault::Stall);
  CHECK_EQ(core.outputs().pwmL, 0);

  core.acceptCommand('F', 180, 2);
  CHECK(core.state() == State::Fault);  // still latched

  core.acceptCommand('S', 0, 3);  // operator acknowledges
  CHECK(!core.stalled());
  CHECK(core.state() == State::Stop);
  core.acceptCommand('F', 180, 4);
  CHECK(core.state() == State::Go);

  // E-stop has priority over the stall latch.
  core.setStall(true);
  core.setEstop(true);
  CHECK(core.faultReason() == Fault::Estop);
  core.setEstop(false);
  CHECK(core.faultReason() == Fault::Stall);
}

static void test_odometry_straight() {
  DifferentialOdometry odo;
  odo.configure(204.0f, 150.0f, 960.0f);
  odo.update(960, 960, 1000);  // one wheel revolution each in 1 s
  CHECK(std::fabs(odo.xMm() - 204.0f) < 0.5f);
  CHECK(std::fabs(odo.yMm()) < 0.5f);
  CHECK(std::fabs(odo.thetaDeg()) < 0.01f);
  CHECK(std::fabs(odo.distanceMm() - 204.0f) < 0.5f);
  CHECK(std::fabs(odo.speedMmS() - 204.0f) < 1.0f);
}

static void test_odometry_pivot_and_quarter_turn() {
  DifferentialOdometry odo;
  odo.configure(204.0f, 150.0f, 960.0f);
  odo.update(960, -960, 1000);  // pivot in place
  CHECK(std::fabs(odo.xMm()) < 0.1f);
  CHECK(std::fabs(odo.yMm()) < 0.1f);
  CHECK(std::fabs(odo.thetaRad() + 2.72f) < 0.05f);
  CHECK(std::fabs(odo.speedMmS()) < 0.1f);

  odo.reset();
  odo.update(-554, 555, 500);  // ~90 degrees
  CHECK(std::fabs(odo.thetaDeg() - 90.0f) < 1.0f);
}

static void test_odometry_wraps_heading() {
  DifferentialOdometry odo;
  odo.configure(204.0f, 150.0f, 960.0f);
  for (int i = 0; i < 10; ++i) odo.update(-960, 960, 100);
  CHECK(odo.thetaRad() >= -3.1416f && odo.thetaRad() <= 3.1416f);
}

int main() {
  test_boot_is_stopped();
  test_forward_gate();
  test_gate_boundary_is_inclusive_at_min_speed();
  test_gate_scales_with_speed();
  test_dead_sensor_blocks_forward();
  test_dead_sensor_blocks_before_moving();
  test_escape_commands_while_blocked();
  test_obstacle_clear_requires_new_command();
  test_pivot_directions();
  test_watchdog();
  test_watchdog_refresh_and_boot_exemption();
  test_watchdog_does_not_fire_when_stopped();
  test_explicit_stop();
  test_speed_clamping_and_default();
  test_packet_parser();
  test_bad_packet_is_discarded_but_motion_continues();
  test_accept_frame_updates_watchdog();
  test_gap_framer_reassembles_split_packets();
  test_gap_framer_separates_back_to_back_packets();
  test_gap_framer_newline_terminates();
  test_gap_framer_overflow();
  test_gap_framer_ignores_empty_gap();
  test_median_filter();
  test_crc8_and_frame_builder();
  test_crc_required_on_the_link();
  test_estop_latches_a_fault();
  test_battery_cutoff_and_recovery();
  test_estop_has_priority_over_battery();
  test_rear_gate_only_when_a_rear_sensor_is_present();
  test_rear_obstacle_stops_a_reversing_rover();
  test_speed_loop_tracks_the_requested_speed();
  test_speed_loop_stall_window();
  test_stall_fault_requires_acknowledgement();
  test_odometry_straight();
  test_odometry_pivot_and_quarter_turn();
  test_odometry_wraps_heading();

  std::printf("%d assertions, %d failures\n", g_checks, g_failures);
  return g_failures == 0 ? 0 : 1;
}
