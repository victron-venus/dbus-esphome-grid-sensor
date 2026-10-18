# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.8] - 2026-10-18

### Changed

- Route Dependabot metadata approval through the trusted default branch while preserving the existing author and review policy.
- Prepare the metadata automation maintenance release.

### Upgrade

Use the existing upgrade procedure and preserve configuration and data. No data migration is required.

### Security

This release preserves the existing security and release-validation policy. Publication does not deploy the service or establish physical-device acceptance.

## [1.0.7] - 2026-10-17

### Changed

- Modernize PEP 639 license metadata and Ruff configuration while retaining lint coverage.
- Analyze and execute maintained ESPHome firmware lambdas with native memory instrumentation.
- Document firmware and broker trust boundaries, project governance and source-bound RC fuzzing evidence.

### Upgrade

Use the existing installation procedure and preserve local configuration. The
runtime configuration format is unchanged. Package builders should use the
committed locked toolchain; live sensor, firmware and D-Bus acceptance remain
separate from these software checks.

### Security

Native tests extend verification of the maintained firmware lambdas. No new
application vulnerability fix or hardware acceptance is claimed. Existing TLS,
OTA and broker trust requirements remain in force.

## [1.0.6] - 2026-10-14

### Changed

- Modernize PEP 639 license metadata and Ruff configuration without dropping lint rules.
- Analyze and execute all maintained firmware lambdas with native memory instrumentation.
- Document governance, continuity limits and firmware/broker trust boundaries.

- Validate each public release candidate with bounded, network-isolated fuzz campaigns against its exact source revision.
- Require positive engine execution counts, instrumented production code and validated seed corpora; retain source-bound reports and diagnostic evidence.
- Run deterministic seed and configuration checks in ordinary CI without starting mutation campaigns on betas.

### Upgrade

Use the existing installation procedure, preserve local configuration and keep the previous accepted package for rollback. This maintenance release updates release validation and does not change the application configuration format. Deployment and applicable device or integration acceptance remain separate from publication.

### Security

RC publication rejects absent or invalid source-bound fuzz reports. The fuzz runner bounds corpus paths, file types and size. No application vulnerability or new target-device acceptance is claimed by these tooling changes.

## [1.0.5] - Development line

### Release candidate validation

- Require bounded fuzzing on public release candidates, with source-bound reports and retained diagnostics; beta and ordinary CI do not run mutation campaigns.

### Changed

- Require encrypted OTA in the pinned ESPHome firmware profile and validate the example using synthetic secrets and an explicit calibration table.
- Preserve D-Bus and MQTT failure tracebacks, validate configuration and package paths, and use hash-locked build and security dependencies.
- Interpret GitHub response status from authoritative HTTP headers during release publication.

### Upgrade

Retain existing API credentials and calibration data. Password-OTA devices require the documented two-stage migration or serial provisioning before adopting the encrypted profile; see `esphome/README.md`. Firmware compilation and offline tests do not replace hardware validation. This cycle uses a new base version rather than the existing 1.0.4 release tag.

### Security

Use deployment-specific encrypted OTA and API keys; the checked-in examples and CI validation use synthetic values only. Keep existing credentials out of committed configuration and preserve the encrypted transport requirements during migration.

## [1.0.4] - Development line

### Release overview

Publishes ESPHome current-transformer measurements as a Victron D-Bus grid meter. The existing README documents configuration and external interfaces for this development line.

### Maintenance

- Validate and compile the ESPHome 2026.9.1 firmware with synthetic secrets; require an operator calibration table, express kWh conversion explicitly and use the supported initial switch state.

- Verify hashes for locked CI, security-tool, release-build and container Python dependencies; build local packages without resolving an isolated backend.
- Preserve exception tracebacks for D-Bus writes and MQTT connection/message failures, and send installer errors to stderr.
- Publish reviewed release notes from the exact source commit used to build each candidate, preserving build provenance.
- Document contribution checks, confidential security reporting and the project-specific trust boundaries.

### Upgrade

Contributors should recreate their check environment with `bash scripts/ci.sh --install` after updating the lock and exported requirements together. Container builders require supported prebuilt dependency wheels. The firmware configuration now requires `ct_calibration_points` in local secrets and encrypted OTA. Existing password-OTA devices need the documented two-stage migration or serial provisioning; preserve their existing API key. See `esphome/README.md` before any update. Retain local configuration and credentials when using the documented update procedure. Validate the candidate on an isolated system before production use; automated checks do not establish hardware acceptance.

### Security

New firmware builds require authenticated encrypted OTA, with no plaintext fallback in the final profile. The transitional first migration upload can still expose embedded secrets; prefer serial or a controlled trusted network. MQTT remains a separate local-network boundary. Private vulnerability reporting and response policy are documented in SECURITY.md. This maintenance update strengthens release evidence and review instructions; it does not replace deployment authentication, network isolation or independent equipment safeguards. No new project CVE is announced by these changes.

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
