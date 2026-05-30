#pragma once

// IMPORTANT: Set WIFI_SSID and WIFI_PASSWORD before flashing

// ── WiFi credentials ──────────────────────────────────────────────────────────
#define WIFI_SSID     "YOUR_SSID"
#define WIFI_PASSWORD "YOUR_PASSWORD"

// ── Sensor selection ──────────────────────────────────────────────────────────
// Use the Sensirion SCD40 (I2C) by default.
// Comment out SENSOR_SCD40 and uncomment SENSOR_MHZ19B to use the MH-Z19B instead.
#define SENSOR_SCD40
// #define SENSOR_MHZ19B

// ── SCD40 I2C pins (ESP32-C3) ─────────────────────────────────────────────────
#define SCD40_SDA_PIN 8
#define SCD40_SCL_PIN 9

// ── MH-Z19B UART pins (ESP32-C3) ─────────────────────────────────────────────
// Wired: sensor TX → ESP GPIO4 (RX), sensor RX → ESP GPIO5 (TX)
#define MHZ19_RX_PIN  4   // ESP RX ← sensor TX
#define MHZ19_TX_PIN  5   // ESP TX → sensor RX
#define MHZ19_BAUD    9600

// ── Measurement ───────────────────────────────────────────────────────────────
#define MEASUREMENT_INTERVAL_SEC 10

// ── Matter device identity ────────────────────────────────────────────────────
#define MATTER_DEVICE_NAME "CO2 Sensor"

// ── Status LED ────────────────────────────────────────────────────────────────
// GPIO2 is the onboard LED on ESP32-C3-DevKitM-1
#define STATUS_LED_PIN 2

// ── Decommission button ───────────────────────────────────────────────────────
// Hold GPIO9 (BOOT button on DevKitM-1) for 5 s to factory-reset Matter
#define DECOMMISSION_BTN_PIN  9
#define DECOMMISSION_HOLD_MS  5000

// ── CO2 → Air Quality thresholds (ppm) ───────────────────────────────────────
#define CO2_GOOD_MAX     800
#define CO2_FAIR_MAX    1200
#define CO2_MODERATE_MAX 1500
// > CO2_MODERATE_MAX is considered Poor
