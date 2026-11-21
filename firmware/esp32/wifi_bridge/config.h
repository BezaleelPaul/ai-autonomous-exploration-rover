/*
 * config.h - ESP32 gateway build configuration.
 * Change the credentials here, re-flash, done.  Nothing else hard-codes them.
 */
#ifndef ROVER_ESP32_CONFIG_H
#define ROVER_ESP32_CONFIG_H

#define FW_VERSION "1.3.0"

// ---- Soft-AP -------------------------------------------------------------
#define AP_SSID "AI_Rover_Control"
#define AP_PASSWORD "rover1234"  // >= 8 chars (WPA2)
#define AP_CHANNEL 6
#define AP_MAX_CLIENTS 4

// Captive portal: phones pop the drive pad automatically when joining.
// Off by default because it hijacks DNS for every client on the AP.
#define ENABLE_CAPTIVE_PORTAL 0
#define ENABLE_MDNS 1  // http://rover.local

// ---- Uno health monitor --------------------------------------------------
// D2 heartbeat -> GPIO13 (5V->3.3V divider), A4 fault -> GPIO14 (divider).
// Leave the pins unwired and /status reports "not wired" instead of lying.
#define ENABLE_UNO_HEALTH 1
#define UNO_ALIVE_PIN 13
#define UNO_FAULT_PIN 14

// The AVR link is half-duplex software serial: cap the command rate so a
// client cannot starve the Uno's receive path or its telemetry window.
#define CMD_MIN_INTERVAL_MS 60

// ---- UART link to the Uno ------------------------------------------------
// ESP32 GPIO17 (TX2) -> Uno D4.  GPIO16 is configured but not wired
// (the link is intentionally unidirectional; see docs/WIRING.md).
#define LINK_TX_PIN 17
#define LINK_RX_PIN 16
#define LINK_BAUD 9600

// ---- OTA (field updates without a USB cable) -----------------------------
// Flash with:  make ota-esp32 OTA_HOST=192.168.4.1 OTA_PASS=roverota
// The rover must be stationary: an OTA reboot stops the command stream and
// the Uno's 500 ms watchdog stops the motors.
#define ENABLE_OTA 1
#define OTA_HOSTNAME "rover"
#define OTA_PASSWORD "roverota"

// ---- API hardening -------------------------------------------------------
// Empty = open (bench/demo). Set a token for any shared/exhibition network:
//   export ROVER_TOKEN=...        (the laptop scripts pick this up)
// The drive pad receives the token from flash, state-changing endpoints
// require it, /status and /health stay readable.
#define API_TOKEN ""
// Pin this to your dashboard origin in production, e.g. "http://localhost:8080".
#define CORS_ORIGIN "*"

// ---- Housekeeping --------------------------------------------------------
#define STATUS_LED_PIN 2
#define MAX_CAMERA_URL 192
#define SERIAL_BAUD 115200

#endif  // ROVER_ESP32_CONFIG_H
