# Wiring Guide

## SCD40 ↔ ESP32-C3-DevKitM-1

| SCD40 Pin | ESP32-C3 Pin | Notes                              |
|-----------|--------------|------------------------------------|
| VCC       | 3.3 V        | Do **not** connect to 5 V          |
| GND       | GND          |                                    |
| SDA       | GPIO 8       | Configured in `config.h`           |
| SCL       | GPIO 9       | Configured in `config.h`           |

**Power note:** The SCD40 runs on 3.3 V and draws up to ~205 mA during measurement.
Make sure your 3.3 V rail can supply at least 300 mA. The on-board LDO on the
DevKitM-1 is rated for 500 mA, which is sufficient.

Add 4.7 kΩ pull-up resistors on SDA and SCL if using long wires (> ~20 cm) or
sharing the I2C bus with other devices.

---

## MH-Z19B ↔ ESP32-C3-DevKitM-1 (alternative sensor)

| MH-Z19B Pin | ESP32-C3 Pin | Notes                                      |
|-------------|------------- |--------------------------------------------|
| VCC (Vin)   | 5 V (Vin)    | Requires **5 V** – do not use 3.3 V        |
| GND         | GND          |                                            |
| TX          | GPIO 4       | Sensor TX → ESP RX (UART1 RX)              |
| RX          | GPIO 5       | Sensor RX → ESP TX (UART1 TX)              |

**Power note:** The MH-Z19B requires 5 V at up to 150 mA peak (during the
infrared lamp pulse). Connect to the Vin/5 V pin on the DevKitM-1, which passes
through from the USB supply. Do **not** power it from the 3.3 V rail.

The UART logic on the MH-Z19B is 3.3 V tolerant, so no level-shifter is needed
on the TX/RX lines.

---

## Status LED

GPIO 2 is the onboard blue LED on the ESP32-C3-DevKitM-1. No external wiring
required.

## Decommission / BOOT button

GPIO 9 is the onboard BOOT button. Hold it for 5 s to factory-reset the Matter
pairing (clears NVS and reboots).
