/*
 * AI Rover - TB6612FNG wheel bring-up test v2 (standalone, no Wi-Fi, no link)
 *
 * Purpose: prove the wheels, wiring and PWM channels BEFORE first drive.
 * Flash THIS sketch (arduino/wheel_test), prop the chassis up, wheels free.
 *
 * HOW YOU KNOW IT IS RUNNING: the onboard LED (D13) blinks 3x at boot, then
 * stays ON whenever a motor is commanded and OFF during pauses. No Serial
 * Monitor needed to see life. With the monitor open (9600 baud) every step
 * is announced before it runs.
 *
 * Cycle (repeats forever):
 *   LEFT forward -> LEFT reverse -> RIGHT forward -> RIGHT reverse
 *   -> BOTH forward -> BOTH reverse -> rest 3 s -> repeat
 *
 * Expected: the named wheel(s) spin at FULL torque (PWM 255).
 *
 * IF NOTHING SPINS AT ALL (both channels dead), check in this order:
 *  1. STBY -> 5V jumper on the driver (driver is asleep without it).
 *  2. TWO separate power pins on the driver: VM -> battery + (motor power)
 *     AND VCC -> Arduino 5V (logic power). VM alone or VCC alone = no motion.
 *  3. COMMON GROUND: battery -, driver GND and Arduino GND all tied together.
 *  4. Battery: measure/swap it; check its switch and connector.
 *  5. The motor wires actually grip the motor's tabs (TT tabs pull loose).
 *  6. Serial shows "=== WHEEL TEST ===" at boot - if not, the wrong sketch
 *     is flashed (the rover firmware boots STOPPED and never self-drives).
 *
 * IF ONE WHEEL IS WRONG:
 *   Spins the wrong way -> swap that motor's two tabs (AO1/AO2 or BO1/BO2).
 *   Dead while other works -> that motor's tab wire or AO/BO output.
 *   Hums/twitches -> weak battery (voltage sag under load).
 */

// TB6612FNG pins (production blueprint map)
const int PWMA = 5;   // left speed
const int AIN1 = 6;   // left direction 1
const int AIN2 = 7;   // left direction 2
const int PWMB = 9;   // right speed
const int BIN1 = 8;   // right direction 1
const int BIN2 = 10;  // right direction 2

const int LED_PIN = 13;
const int TEST_SPEED = 255;                // full torque: rules out weak PWM
const unsigned long SPIN_MS = 3000;        // each step spins 3 s
const unsigned long GAP_MS = 1000;         // pause between steps
const unsigned long ROUND_REST_MS = 3000;  // pause between rounds

void ledOn()  { digitalWrite(LED_PIN, HIGH); }
void ledOff() { digitalWrite(LED_PIN, LOW); }

void stopAll() {
  digitalWrite(AIN1, LOW);
  digitalWrite(AIN2, LOW);
  digitalWrite(BIN1, LOW);
  digitalWrite(BIN2, LOW);
  analogWrite(PWMA, 0);
  analogWrite(PWMB, 0);
  ledOff();
}

// leftOn/rightOn select the channel, leftFwd/rightFwd pick direction.
void spin(bool leftOn, bool leftFwd, bool rightOn, bool rightFwd) {
  if (leftOn) {
    analogWrite(PWMA, TEST_SPEED);
    digitalWrite(AIN1, leftFwd ? HIGH : LOW);
    digitalWrite(AIN2, leftFwd ? LOW : HIGH);
  } else {
    analogWrite(PWMA, 0);
    digitalWrite(AIN1, LOW);
    digitalWrite(AIN2, LOW);
  }
  if (rightOn) {
    analogWrite(PWMB, TEST_SPEED);
    digitalWrite(BIN1, rightFwd ? HIGH : LOW);
    digitalWrite(BIN2, rightFwd ? LOW : HIGH);
  } else {
    analogWrite(PWMB, 0);
    digitalWrite(BIN1, LOW);
    digitalWrite(BIN2, LOW);
  }
  ledOn();
}

void step(const char *label, bool lOn, bool lF, bool rOn, bool rF) {
  Serial.print("-> ");
  Serial.println(label);
  spin(lOn, lF, rOn, rF);
  delay(SPIN_MS);
  stopAll();
  delay(GAP_MS);
}

void setup() {
  Serial.begin(9600);
  pinMode(LED_PIN, OUTPUT);
  pinMode(PWMA, OUTPUT);
  pinMode(AIN1, OUTPUT);
  pinMode(AIN2, OUTPUT);
  pinMode(PWMB, OUTPUT);
  pinMode(BIN1, OUTPUT);
  pinMode(BIN2, OUTPUT);
  stopAll();
  // Visible boot signature: 3 quick blinks = wheel test is running.
  for (int i = 0; i < 3; i++) {
    ledOn();
    delay(120);
    ledOff();
    delay(120);
  }
  Serial.println("=== WHEEL TEST v2 (TB6612FNG, full torque) ===");
  Serial.println("Chassis propped up, wheels free. L fwd, L rev, R fwd,");
  Serial.println("R rev, BOTH fwd, BOTH rev - repeating forever.");
  Serial.println("Nothing spins? 1) STBY->5V  2) VM->battery+ AND VCC->5V");
  Serial.println("3) common GND 4) battery 5) motor tab wires.");
  delay(1500);
}

void loop() {
  Serial.println("== ROUND ==");
  step("LEFT FORWARD  (left wheel only)", true, true, false, false);
  step("LEFT REVERSE  (left wheel only)", true, false, false, false);
  step("RIGHT FORWARD (right wheel only)", false, false, true, true);
  step("RIGHT REVERSE (right wheel only)", false, false, true, false);
  step("BOTH FORWARD", true, true, true, true);
  step("BOTH REVERSE", true, false, true, false);
  Serial.println("rest 3 s, then repeating...");
  delay(ROUND_REST_MS);
}
