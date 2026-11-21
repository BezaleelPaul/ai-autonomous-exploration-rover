/*
 * AI Rover - TB6612FNG isolated diagnostic wheel test.
 *
 * Tests both motor channels with auto-stopping timeout to ensure safety
 * during bench bringup. Chassis should be propped up with wheels free.
 */

const int PWMA = 5;
const int AIN1 = 6;
const int AIN2 = 7;
const int PWMB = 9;
const int BIN1 = 8;
const int BIN2 = 10;
const int LED_PIN = 13;

constexpr unsigned long kAutoStopMs = 3000;
unsigned long startTime = 0;
bool running = false;

void stopAll() {
  digitalWrite(AIN1, LOW);
  digitalWrite(AIN2, LOW);
  digitalWrite(BIN1, LOW);
  digitalWrite(BIN2, LOW);
  analogWrite(PWMA, 0);
  analogWrite(PWMB, 0);
  digitalWrite(LED_PIN, LOW);
  running = false;
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

  // Safety: never boot driving
  stopAll();

  Serial.println("=== ISOLATED DRIVE TEST: TB6612FNG auto-stopping ===");
  Serial.println("Motors will spin for 3000 ms then stop automatically.");

  // Command forward motion
  digitalWrite(AIN1, HIGH);
  digitalWrite(AIN2, LOW);
  digitalWrite(BIN1, HIGH);
  digitalWrite(BIN2, LOW);
  analogWrite(PWMA, 255);
  analogWrite(PWMB, 255);
  digitalWrite(LED_PIN, HIGH);
  running = true;
  startTime = millis();
}

void loop() {
  if (running && (millis() - startTime >= kAutoStopMs)) {
    stopAll();
    Serial.println("Test complete: auto-stopped.");
  }
}
