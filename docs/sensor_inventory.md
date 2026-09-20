# Sensor Inventory & Hardware Specification

## Hardware Overview
- **Device Model**: Apollo Automation AIR-1 (ESP32-C3)
- **Microcontroller**: ESP32-C3-Mini (4MB Flash, Wi-Fi 4 + BLE 5.0)
- **Power supply**: USB-C or Battery
- **Network**: eduroam (WPA2-Enterprise, EAP-TTLS + MSCHAPv2) with mDNS / static fallback AP.

---

## Discovered Sensors Inventory (9 Nodes)

| Sensor ID | Friendly Name | Authoritative hostname | ESPHome Version |
|---|---|---|---|
| `air-sensor-01` | Apollo AIR-1 01 | `air-sensor-01-2b8844.dyn.uncc.edu` | 26.3.2.1 |
| `air-sensor-02` | Apollo AIR-1 02 | `air-sensor-02-2c59a8.dyn.uncc.edu` | 26.3.2.1 |
| `air-sensor-03` | Apollo AIR-1 03 | `air-sensor-03-3ec4c4.dyn.uncc.edu` | 26.3.2.1 |
| `air-sensor-04` | Apollo AIR-1 04 | `air-sensor-04-420748.dyn.uncc.edu` | 26.3.2.1 |
| `air-sensor-05` | Apollo AIR-1 05 | `air-sensor-05-3e4ca4.dyn.uncc.edu` | 26.3.2.1 |
| `air-sensor-06` | Apollo AIR-1 06 | `air-sensor-06-2b991c.dyn.uncc.edu` | 26.3.2.1 |
| `air-sensor-07` | Apollo AIR-1 07 | `air-sensor-07-3e2468.dyn.uncc.edu` | 26.3.2.1 |
| `air-sensor-08` | Apollo AIR-1 08 | `air-sensor-08-411de4.dyn.uncc.edu` | 26.3.2.1 |
| `air-sensor-09` | Apollo AIR-1 09 | `air-sensor-09-3f2018.dyn.uncc.edu` | 26.3.2.1 |

---

## Service & Network Configuration

- **Collector interface**: Embedded web server on port `80`, using REST and `/events` SSE.
- **OTA Updates**:
  - Platform `esphome` (credentials are managed outside this repository)
  - Platform `http_request` (HTTPS manifest auto-update)
- **Deep Sleep Configuration**: Default 5 min sleep, 2 min run duration (configurable via slider).

---

## Exposed Entities & Sensors Specification

### 1. Environmental Sensors (`sensor`)
| Entity ID | Entity Name | Sensor Module | Unit | Update Interval | Range / Thresholds |
|---|---|---|---|---|---|
| `co2` | CO2 | Sensirion SCD40 | ppm | 60s | 400 - 5000 ppm (Green: <800, Yellow: 800-1000, Orange: 1000-1500, Red: >1500) |
| `pm_1_0` | PM <1µm Weight conc. | Sensirion SEN55 | µg/m³ | 10s | 0 - 1000 µg/m³ |
| `pm_2_5` | PM <2.5µm Weight conc. | Sensirion SEN55 | µg/m³ | 10s | 0 - 1000 µg/m³ (Green: <12, Yellow: 12-35, Orange: 35-55, Red: >55) |
| `pm_4_0` | PM <4µm Weight conc. | Sensirion SEN55 | µg/m³ | 10s | 0 - 1000 µg/m³ |
| `pm_10_0` | PM <10µm Weight conc. | Sensirion SEN55 | µg/m³ | 10s | 0 - 1000 µg/m³ |
| `sen55_voc` | SEN55 VOC Index | Sensirion SEN55 | Index | 10s | 1 - 500 Index (Green: <100, Yellow: 100-200, Orange: 200-300, Red: >300) |
| `sen55_nox` | SEN55 NOX Index | Sensirion SEN55 | Index | 10s | 1 - 500 Index (Green: <1, Yellow: 1-10, Orange: 10-20, Red: >20) |
| `sen55_temperature` | SEN55 Temperature | Sensirion SEN55 | °C / °F | 10s | -10 to 60 °C (converted to °F by the API collector) |
| `sen55_humidity` | SEN55 Humidity | Sensirion SEN55 | % | 10s | 0 - 100 % |
| `dps310pressure` | DPS310 Pressure | Infineon DPS310 | hPa | 30s | 300 - 1200 hPa |
| `sys_esp_temperature` | ESP Temperature | ESP32-C3 | °C | 60s | Internal die temp |
| `sys_uptime` | System Uptime | System | seconds | 60s | Continuous uptime |
| `wifi_signal_db` | Wi-Fi RSSI | Wi-Fi | dBm | 60s | Signal strength (-90 to -30 dBm) |

### 2. Controls & Configuration (`number`, `switch`, `binary_sensor`)
- `air_quality_led_brightness`: RGB LED brightness control (5% - 100%).
- `sen55_temperature_offset`: Temperature calibration offset (-70.0 to +70.0 °C).
- `sen55_humidity_offset`: Humidity calibration offset (-70.0 to +70.0 %).
- `dps310_pressure_offset`: Pressure calibration offset (-100.0 to +100.0 hPa).
- `deep_sleep_sleep_duration`: Deep sleep duration in minutes (0 - 800 min).
- `ink_ha_connected`: Binary sensor for connection state.
- `ota_mode`: Binary sensor for OTA lock state.
