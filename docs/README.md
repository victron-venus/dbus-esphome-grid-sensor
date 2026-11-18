# Documentation

A D-Bus service that publishes ESPHome grid-sensor readings on Venus OS, with the
firmware, container and release records around it.

## Install

- [Install the ESP32 firmware from your browser](browser-install.md) — building in Device Builder and flashing over USB.
- [Container build and trust](container-build.md) — what the Docker image builds and which base packages it includes.
- [Python dependency locks](dependency-locks.md) — what `uv.lock` selects for project, build and security tooling.

## Assurance

- [Firmware and service assurance](firmware-assurance.md) — the Python service and the ESPHome YAML actually in scope.
- [OpenSSF Best Practices evidence: dbus-esphome-grid-sensor](openssf-evidence.md) — the index behind the assessment, not an awarded badge.
- [Roadmap through October 2027](roadmap.md) — compatibility, documented interfaces and failure handling priorities.

## Releases

- [Release operations](release-packaging.md) — what `release.sh` delegates and which events validate what.
- [Release version inputs](release-versioning.md) — the `versioning` fields that identify a release.
- [Release helper TLS profile](release-tls-profile.md) — the qualified `gh` transport profile.
- [CI and release operations](release-workflow.md) — `.release-policy.json` and the required status.
- [CI orchestration](CI-ORCHESTRATION.md) — how the quality gate and release pipeline divide the events.
- [Version plans and manifest synchronization](VERSIONING.md) — the versioning opt-in.
- [Release-candidate fuzz testing](fuzzing.md) — the illustrated RC fuzzing process.
- [Fuzzing release candidates](rc-fuzzing.md) — the reusable bounded fuzz workflow.
- [Release read recovery and rerun validation](release-read-safety.md) — the two fixes carried from the shared toolkit.
- [Early final-build runner check](runner-preflight.md) — why the check runs before the final build.
