#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <Matter.h>
#include <MatterAirQuality.h>

#include "config.h"

#if defined(SENSOR_SCD40)
  #include <SensirionI2cScd4x.h>
  SensirionI2cScd4x scd4x;
#elif defined(SENSOR_MHZ19B)
  #include <MHZ19.h>
  #include <HardwareSerial.h>
  MHZ19 mhz19;
  HardwareSerial mhzSerial(1);  // UART1
#else
  #error "Define either SENSOR_SCD40 or SENSOR_MHZ19B in config.h"
#endif

MatterAirQuality matterAirQuality;

// ── Forward declarations ──────────────────────────────────────────────────────
static void     connectWiFi();
static void     initSensor();
static bool     readSensor(float &co2, float &tempC, float &humidity);
static MatterAirQuality::AirQualityType co2ToAirQuality(float co2ppm);
static void     checkDecommissionButton();
static void     blinkLed(int times, int onMs = 100, int offMs = 100);

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(500);  // allow USB-CDC to enumerate

    pinMode(STATUS_LED_PIN, OUTPUT);
    pinMode(DECOMMISSION_BTN_PIN, INPUT_PULLUP);

    Serial.printf("\n=== %s ===\n", MATTER_DEVICE_NAME);

    initSensor();

    // Matter.begin() must be called before WiFi so the stack can set its
    // vendor/product IDs before commissioning.
    matterAirQuality.begin();
    Matter.begin();

    connectWiFi();

    if (!Matter.isDeviceCommissioned()) {
        Serial.println("Not commissioned yet. Scan the QR code below to add to TAPO/Home app:");
        Matter.printOnboardingCodes();
    } else {
        Serial.println("Device is already commissioned.");
    }

    blinkLed(3, 200, 200);
    Serial.printf("Sampling every %d s.\n\n", MEASUREMENT_INTERVAL_SEC);
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
    static unsigned long lastMeasure = 0;

    checkDecommissionButton();

    unsigned long now = millis();
    if (now - lastMeasure >= (unsigned long)MEASUREMENT_INTERVAL_SEC * 1000UL) {
        lastMeasure = now;

        float co2 = 0, tempC = 0, humidity = 0;
        if (readSensor(co2, tempC, humidity)) {
            MatterAirQuality::AirQualityType aq = co2ToAirQuality(co2);
            matterAirQuality.setAirQuality(aq);

            // Matter carbon-dioxide concentration cluster (ppm)
            matterAirQuality.setCarbonDioxideConcentration(co2);

            // Temperature and humidity clusters (if supported by build)
            matterAirQuality.setTemperature(tempC);
            matterAirQuality.setHumidity(humidity);

            Serial.printf("[CO2] %.0f ppm  Temp %.1f°C  Hum %.0f%%  AQ=%d\n",
                          co2, tempC, humidity, (int)aq);

            // Single blink = successful reading
            blinkLed(1, 50);
        } else {
            Serial.println("[CO2] Sensor read failed – retrying next cycle.");
            blinkLed(5, 50, 50);
        }
    }
}

// ── WiFi ──────────────────────────────────────────────────────────────────────
static void connectWiFi() {
    Serial.printf("Connecting to WiFi: %s", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.printf("\nIP: %s\n", WiFi.localIP().toString().c_str());
}

// ── Sensor init ───────────────────────────────────────────────────────────────
static void initSensor() {
#if defined(SENSOR_SCD40)
    Wire.begin(SCD40_SDA_PIN, SCD40_SCL_PIN);
    scd4x.begin(Wire);

    // Stop any previous measurement before reconfiguring
    scd4x.stopPeriodicMeasurement();
    delay(500);

    uint16_t err = scd4x.startPeriodicMeasurement();
    if (err) {
        Serial.printf("SCD40 startPeriodicMeasurement error: %u\n", err);
    } else {
        Serial.println("SCD40 initialised (periodic measurement started).");
    }

#elif defined(SENSOR_MHZ19B)
    mhzSerial.begin(MHZ19_BAUD, SERIAL_8N1, MHZ19_RX_PIN, MHZ19_TX_PIN);
    mhz19.begin(mhzSerial);
    mhz19.autoCalibration(false);  // disable ABC for indoor use
    Serial.println("MH-Z19B initialised.");
#endif
}

// ── Sensor read ───────────────────────────────────────────────────────────────
static bool readSensor(float &co2, float &tempC, float &humidity) {
#if defined(SENSOR_SCD40)
    bool dataReady = false;
    uint16_t err = scd4x.getDataReadyFlag(dataReady);
    if (err || !dataReady) {
        // Data not ready yet; not an error – caller will retry next cycle
        return false;
    }

    uint16_t rawCo2 = 0;
    float    rawTemp = 0, rawHum = 0;
    err = scd4x.readMeasurement(rawCo2, rawTemp, rawHum);
    if (err || rawCo2 == 0) {
        return false;
    }
    co2      = (float)rawCo2;
    tempC    = rawTemp;
    humidity = rawHum;
    return true;

#elif defined(SENSOR_MHZ19B)
    int rawCo2 = mhz19.getCO2();
    if (rawCo2 <= 0) {
        return false;
    }
    co2      = (float)rawCo2;
    tempC    = (float)mhz19.getTemperature();
    humidity = 0.0f;  // MH-Z19B does not measure humidity
    return true;
#endif
}

// ── CO2 → Air Quality mapping ─────────────────────────────────────────────────
static MatterAirQuality::AirQualityType co2ToAirQuality(float co2ppm) {
    if (co2ppm < CO2_GOOD_MAX)         return MatterAirQuality::AirQualityType::Good;
    if (co2ppm < CO2_FAIR_MAX)         return MatterAirQuality::AirQualityType::Fair;
    if (co2ppm < CO2_MODERATE_MAX)     return MatterAirQuality::AirQualityType::Moderate;
    return                                    MatterAirQuality::AirQualityType::Poor;
}

// ── Decommission button ───────────────────────────────────────────────────────
// Hold the BOOT button (GPIO9) for DECOMMISSION_HOLD_MS to factory-reset Matter.
static void checkDecommissionButton() {
    if (digitalRead(DECOMMISSION_BTN_PIN) != LOW) return;

    unsigned long pressStart = millis();
    while (digitalRead(DECOMMISSION_BTN_PIN) == LOW) {
        if (millis() - pressStart >= DECOMMISSION_HOLD_MS) {
            Serial.println("Decommissioning Matter device – resetting NVS…");
            blinkLed(10, 50, 50);
            Matter.decommission();
            // Matter.decommission() triggers a reboot; code below is a fallback.
            ESP.restart();
        }
        delay(50);
    }
}

// ── LED helper ────────────────────────────────────────────────────────────────
static void blinkLed(int times, int onMs, int offMs) {
    for (int i = 0; i < times; i++) {
        digitalWrite(STATUS_LED_PIN, HIGH);
        delay(onMs);
        digitalWrite(STATUS_LED_PIN, LOW);
        if (i < times - 1) delay(offMs);
    }
}
