# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-10

### Added
- Initial release of ESP32 CT Grid Sensor for Victron Venus OS
- ESPHome firmware for ESP32 with CT sensor (SCT-013-000) monitoring
- Support for ADS1115 16-bit ADC for higher precision readings
- MQTT discovery integration with Home Assistant
- Python D-Bus bridge service publishing to `com.victronenergy.grid`
- Device instance 42 for grid meter registration
- Power calculation: P = V × I × PF
- Energy tracking (import/export) via integration sensors
- Docker Compose deployment ready
- Installation script for Venus OS (Cerbo GX)

### Hardware
- SCT-013-000 CT Sensor (0-100A, 0-50mA)
- ESP32 DevKit V1 (ADC1_CH6 / GPIO34)
- Optional ADS1115 16-bit ADC (I2C)
- 33Ω Burden Resistor (1.65V @ 100A)
- 3.5mm Stereo Jack (Panel Mount)

### Infrastructure
- Python 3.11+ support
- Poetry-ready pyproject.toml
- Ruff for linting/formatting
- MyPy strict type checking
- Pytest with asyncio support