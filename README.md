# Arduino CO2 Sensor with Matter (TAPO / Home App)

An ESP32-C3 firmware that reads CO2 (and optionally temperature + humidity) and
exposes the data as a **Matter Air Quality Sensor** device. Once commissioned,
it appears natively in the **TAPO app**, Apple Home, Google Home, or any other
Matter-compatible controller.

---

## Overview

| Item         | Detail                                    |
|--------------|-------------------------------------------|
| MCU          | ESP32-C3 (ESP32-C3-DevKitM-1)            |
| Framework    | Arduino ESP32 3.x (built-in Matter stack) |
| Protocol     | Matter over Wi-Fi                         |
| Sensor (A)   | Sensirion SCD40 – CO2 + temp + humidity   |
| Sensor (B)   | Winsen MH-Z19B – CO2 + temp (alternative) |
| Controller   | TAPO app / Apple Home / Google Home       |

---

## Hardware Requirements

- ESP32-C3-DevKitM-1 (or compatible ESP32-C3 board)
- **One** of the following sensors:
  - Sensirion SCD40 (I2C, 3.3 V) — recommended; provides CO2, temperature, and humidity
  - Winsen MH-Z19B (UART, 5 V) — alternative; provides CO2 and temperature only
- USB-C cable for programming
- Wi-Fi 2.4 GHz network (Matter requires 2.4 GHz)

See `hardware/wiring.md` for pin connections.

---

## Software Requirements

- [PlatformIO](https://platformio.org/) (VS Code extension or CLI)
- Arduino ESP32 core ≥ 3.0 (installed automatically by PlatformIO via `platformio.ini`)

---

## Quick Start

### 1. Clone the repository

```bash
git clone <repo-url>
cd masahiro
```

### 2. Set your Wi-Fi credentials

Open `src/config.h` and replace the placeholders:

```cpp
#define WIFI_SSID     "YOUR_SSID"
#define WIFI_PASSWORD "YOUR_PASSWORD"
```

> **Warning:** Never commit real credentials. Add `src/config.h` to `.gitignore`
> or use a `secrets.h` approach for production use.

### 3. (Optional) Select sensor

The SCD40 is selected by default. To use the MH-Z19B instead, edit `src/config.h`:

```cpp
// #define SENSOR_SCD40      ← comment this out
#define SENSOR_MHZ19B        // ← uncomment this
```

### 4. Wire the sensor

Follow `hardware/wiring.md`.

### 5. Build and flash

```bash
# Build only
pio run

# Build and upload
pio run -t upload

# Open serial monitor
pio device monitor
```

---

## Commissioning with the TAPO App

1. Flash the firmware and open the serial monitor (`pio device monitor`).
2. On first boot the device prints a **QR code URL** and a **manual pairing code**:

   ```
   Not commissioned yet. Scan the QR code below to add to TAPO/Home app:
   QR Code URL: MT:...
   Manual pairing code: XXXX-XXX-XXXX
   ```

3. Open the **TAPO app** → **Add Device** → **Matter** → scan the QR code
   (or enter the manual code).
4. Follow the in-app steps to join the device to your home.

After commissioning, CO2, temperature, and humidity readings update every
10 seconds (configurable via `MEASUREMENT_INTERVAL_SEC` in `config.h`).

### Decommissioning

To remove the device from the Matter fabric and re-pair it:
Hold the **BOOT button (GPIO9)** for **5 seconds**. The LED blinks rapidly,
the NVS is wiped, and the device reboots to the unconfigured state.

---

## Sensor Accuracy Notes

| Sensor   | CO2 range  | CO2 accuracy           | Temp accuracy | Hum accuracy |
|----------|-----------|------------------------|---------------|--------------|
| SCD40    | 400–2000 ppm | ±(50 ppm + 5 % of reading) | ±0.8 °C  | ±6 % RH     |
| MH-Z19B  | 400–5000 ppm | ±(50 ppm + 5 % of reading) | ±0.5 °C  | —            |

The MH-Z19B has Automatic Baseline Correction (ABC) disabled in this firmware
to avoid drift in continuously occupied indoor spaces. Recalibrate manually
every few months by placing the sensor outdoors for 20 minutes and calling
`mhz19.calibrate()` once.

The SCD40 should be calibrated after assembly; the Sensirion SCD4x library
provides a `performForcedRecalibration()` method.

---

## CO2 Air Quality Levels

| CO2 (ppm) | Matter Air Quality | Typical context         |
|-----------|--------------------|-------------------------|
| < 800     | Good               | Fresh outdoor air       |
| 800–1200  | Fair               | Acceptable indoor level |
| 1200–1500 | Moderate           | Stuffy; ventilate soon  |
| > 1500    | Poor               | Open windows now        |

---

## Folder Structure

```
masahiro/
├── platformio.ini        # PlatformIO project config
├── src/
│   ├── config.h          # WiFi credentials & pin/sensor settings
│   └── main.cpp          # Main Arduino sketch
├── hardware/
│   └── wiring.md         # Pin wiring diagrams
└── README.md
```

---

## License

MIT License. See individual library licenses (SensirionI2cScd4x, MH-Z19, Arduino ESP32 core).
