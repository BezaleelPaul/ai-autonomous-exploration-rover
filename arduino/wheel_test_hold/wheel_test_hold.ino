/*
 * AI Rover - TB6612FNG HOLD test: both motors commanded ON at full speed
 * continuously until power is removed. For hands-on troubleshooting only
 * (probing terminals, wiggle-testing wires). Chassis propped up!
 *
 * Onboard LED: solid ON = motors are being commanded right now.
 * Serial (9600): banner + a status line every 5 s.
 *
 * While this runs, probe with a multimeter (DC 20V, black probe on driver
 * GND) or wiggle-test:
 *   VM  - GND   should read battery voltage (~7-8 V)
 *   VCC - GND   should read 5 V
 *   STBY- GND   should read 5 V
 *   PWMA- GND   ~battery voltage (PWM 255 = near full)
 *   AO1 - AO2   should read ~battery voltage while the motor is connected
 * If VM reads 0 V: the battery feed (switch, fuse, terminal) is broken.
 * If VM is good but AO1/AO2 reads 0 V: the driver input pins (AIN1/AIN2/
 * PWMA) are not being driven, or the driver is damaged.
 */

const int PWMA = 5;
const int AIN1 = 6;
const int AIN2 = 7;
const int PWMB = 9;
const int BIN1 = 8;
const int BIN2 = 10;
const int LED_PIN = 13;

unsigned long lastLog = 0;

void setup() {
  Serial.begin(9600);
  pinMode(LED_PIN, OUTPUT);
  pinMode(PWMA, OUTPUT);
  pinMode(AIN1, OUTPUT);
  pinMode(AIN2, OUTPUT);
  pinMode(PWMB, OUTPUT);
  pinMode(BIN1, OUTPUT);
  pinMode(BIN2, OUTPUT);

  // Both channels: forward at full speed, forever.
  digitalWrite(AIN1, HIGH);
  digitalWrite(AIN2, LOW);
  digitalWrite(BIN1, HIGH);
  digitalWrite(BIN2, LOW);
  analogWrite(PWMA, 255);
  analogWrite(PWMB, 255);
  digitalWrite(LED_PIN, HIGH);

  Serial.println("=== HOLD TEST: both motors ON (fwd, full speed) ===");
  Serial.println("Probe/wiggle now. Cut power to stop. LED solid = commanding.");
  lastLog = millis();
}

void loop() {
  if (millis() - lastLog >= 5000) {
    lastLog = millis();
    Serial.print("motors ON fwd 255, t=");
    Serial.println(millis() / 1000);
  }
}
