# Firmware and service assurance

The maintained source includes the Python D-Bus service, ESPHome YAML with four
C++ lambdas, installer/release helpers and host tests. ESPHome/framework/library
code is reused third-party source, with versions described in
[the firmware guide](../esphome/README.md). A successful firmware build alone is
not a C++ security review or physical meter calibration.

`tests/test_firmware_lambdas.py` extracts all four actual YAML lambda bodies and
runs the Clang static analyzer, strict compiler warnings and an executable with
AddressSanitizer/UndefinedBehaviorSanitizer. It checks signed nominal power,
unknown values, feed-in threshold behavior and bounded diagnostic formatting.
Adding another lambda fails the inventory until the harness is reviewed. Python
lint/type checks, Bandit and CodeQL cover the maintained host code separately.
The full pinned ESPHome compile remains required; the host model does not replace
ESP-IDF or board integration and does not cover every third-party code path.

## Transport and credential profile

Native API and OTA require the same device-specific 32-byte random Noise key.
The pinned ESPHome profile uses Curve25519, ChaCha20-Poly1305 and SHA-256 and
rejects plaintext API/OTA build flags. The firmware guide documents OS-generated
keys, ESP32 hardware RNG dependencies and two-stage legacy migration limits.
Use unique strong Wi-Fi/AP credentials; never deploy the synthetic CI secrets.

MQTT remains plaintext, independently of API/OTA encryption. Run it only on a
trusted isolated segment and block internet access to its broker/device ports.
Give the sensor its own broker identity restricted to publishing its configured
telemetry/status/discovery topics. Give the D-Bus subscriber an independent
identity limited to reading the configured `MQTT_TOPIC_PREFIX` subtree; do not
grant it broker administration or unrelated control topics. Set broker policy
from the actual deployed topic prefix rather than copying a wildcard administrator
account. Keep configuration files private and exclude real secrets from logs and
support bundles. This profile does not claim encrypted MQTT or deployment audit.

The application does not implement a human-password verifier database. Wi-Fi,
broker and device credentials are consumed by the documented external services.
Hardware key entropy, reference-meter calibration, polarity and physical safety
remain operator acceptance requirements. Neither the native harness nor the
synthetic firmware compile attests them.

## Remaining evidence limits

Python coverage is measured over `src`, not every firmware/deployment helper.
No whole-source Silver coverage claim is made. Source builds use pinned/locked
inputs but have not been independently shown bit-for-bit reproducible. The
single-maintainer continuity limitation is recorded in [governance](../GOVERNANCE.md).
