# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.4] - Development line

### Release overview

Publishes ESPHome current-transformer measurements as a Victron D-Bus grid meter. The existing README documents configuration and external interfaces for this development line.

### Maintenance

- Preserve exception tracebacks for D-Bus writes and MQTT connection/message failures, and send installer errors to stderr.
- Publish reviewed release notes from the exact source commit used to build each candidate, preserving build provenance.
- Document contribution checks, confidential security reporting and the project-specific trust boundaries.

### Upgrade

These maintenance changes do not introduce a configuration or data migration. Retain local configuration and credentials when using the documented update procedure. Validate the candidate on an isolated system before production use; automated checks do not establish hardware acceptance.

### Security

Private vulnerability reporting and response policy are documented in SECURITY.md. This maintenance update strengthens release evidence and review instructions; it does not replace deployment authentication, network isolation or independent equipment safeguards. No new project CVE is announced by these changes.

## [1.0.2] - 2026-09-12

### Fixed
- Register complete D-Bus services with valid names and apply MQTT updates on the GLib thread.
- Reject malformed and non-finite telemetry, use monotonic freshness, and publish invalid readings after data loss.
- Load literal persisted configuration without requiring python-dotenv on Venus OS.
- Preserve existing configuration and supervisor directory inodes during native installation, with persistent boot restoration and bounded multilog output.

## [1.0.1] - 2026-09-12

### Fixed
- Accept standard ESPHome scalar state topics while preserving keyed JSON telemetry.
- Reject invalid samples without partially updating readings or their freshness.
- Include the executable service modules in Python distributions and the native D-Bus/GI runtime in Docker.
- Use the official Victron library API and persistent native service paths.
- Preserve spaces, quotes and literal special characters in native `.env` configuration.

The ESPHome firmware is unchanged. Native installations still require platform
D-Bus/GI bindings and official `velib_python` on `PYTHONPATH`; the Docker image
includes those runtime dependencies. Wheel and source distribution assets include
SHA256 checksums.

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
