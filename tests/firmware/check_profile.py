"""Validate/build a synthetic firmware profile; never upload or open a device."""

import argparse
import base64
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

COMPILER_VERSION = "2026.9.1"
ROOT = Path(__file__).resolve().parents[2]


def synthetic_secrets() -> dict[str, object]:
    """Public, deliberately synthetic inputs; never use this profile on hardware."""
    return {
        "wifi_ssid": "offline-fixture-network",
        "wifi_password": "offline-fixture-password",
        "grid_sensor_ip": "192.0.2.23",
        "wifi_gateway": "192.0.2.1",
        "ap_password": "offline-fixture-ap",
        "api_encryption_key": base64.b64encode(bytes(range(32))).decode(),
        "mqtt_broker": "127.0.0.1",
        "mqtt_port": 1883,
        "mqtt_username": "offline-fixture",
        "mqtt_password": "offline-fixture-mqtt",
        "ct_calibration_points": ["0.0 -> 0.0", "1.0 -> 1.0"],
    }


def write_case(directory: Path, source: str, secrets: dict[str, object]) -> Path:
    directory.mkdir()
    config = directory / "grid-sensor.yaml"
    config.write_text(source)
    secret_file = directory / "secrets.yaml"
    secret_file.write_text(json.dumps(secrets))  # JSON is also valid YAML.
    secret_file.chmod(0o600)
    return config


def run_compiler(config: Path, command: str, *options: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "esphome", command, *options, str(config)],
        capture_output=True,
        text=True,
        timeout=1800 if command == "compile" else 60,
        check=False,
    )


def require_success(result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)


def require_rejection(config: Path, reason: str) -> None:
    result = run_compiler(config, "config")
    output = result.stdout + result.stderr
    if result.returncode == 0 or reason not in output:
        raise AssertionError(f"Expected rejection containing {reason!r}:\n{output}")


def check_negative_configs(directory: Path, source: str) -> None:
    missing = synthetic_secrets()
    del missing["ct_calibration_points"]
    require_rejection(
        write_case(directory / "missing-table", source, missing),
        "Secret 'ct_calibration_points' not defined",
    )
    for name, points in (("empty-table", []), ("one-point", ["0.0 -> 0.0"])):
        secrets = synthetic_secrets()
        secrets["ct_calibration_points"] = points
        require_rejection(
            write_case(directory / name, source, secrets), "length of value must be at least 2"
        )
    short_key = synthetic_secrets()
    short_key["api_encryption_key"] = base64.b64encode(b"short fixture").decode()
    require_rejection(write_case(directory / "short-key", source, short_key), "32 bytes")
    ota = "ota:\n  platform: esphome\n  encryption:"
    assert source.count(ota) == 1, "Update this fixture if the OTA configuration layout changes"
    mixed = source.replace(ota, ota + "\n  password: offline-fixture-ota")
    require_rejection(
        write_case(directory / "mixed-auth", mixed, synthetic_secrets()),
        "'password' cannot be combined with 'encryption'",
    )
    mismatched = source.replace(
        ota, ota + "\n    key: " + base64.b64encode(bytes(range(1, 33))).decode()
    )
    require_rejection(
        write_case(directory / "mismatched-key", mismatched, synthetic_secrets()),
        "encryption key must match",
    )


def check_generated_profile(config: Path) -> None:
    generated = config.parent / ".esphome/build/grid-sensor/src"
    defines = (generated / "esphome/core/defines.h").read_text().splitlines()
    for name in ("USE_API_NOISE", "USE_OTA_ENCRYPTION", "USE_OTA_ENCRYPTION_REQUIRED"):
        assert f"#define {name}" in defines, name
    for name in ("USE_OTA_PASSWORD", "USE_API_PLAINTEXT"):
        assert not any(line.startswith(f"#define {name}") for line in defines)
    main = (generated / "main.cpp").read_text()
    assert "mqtt_publishing->set_restore_mode(switch_::SWITCH_ALWAYS_ON)" in main
    assert main.count("sensor::MultiplyFilter([]() -> float {") == 2
    for variable in ("sensor_multiplyfilter_id", "sensor_multiplyfilter_id_2"):
        expected = (
            f"new({variable}) sensor::MultiplyFilter([]() -> float {{\n      return 0.001f;\n  }});"
        )
        assert expected in main, "Generated Wh-to-kWh conversion differs"
    assert "grid_energy_forward->set_filters({sensor_multiplyfilter_id});" in main
    assert (
        "grid_energy_reverse->set_filters({sensor_multiplyfilter_id_2, sensor_lambdafilter_id});"
        in main
    ), "Convert units before the existing reverse-energy filter"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compile", action="store_true", help="Also build the firmware binary")
    args = parser.parse_args()
    version = importlib.metadata.version("esphome")
    if version != COMPILER_VERSION:
        raise SystemExit(f"Expected ESPHome {COMPILER_VERSION}, found {version}")
    source = (ROOT / "esphome/grid-sensor.yaml").read_text()
    with TemporaryDirectory(prefix="synthetic-grid-firmware-") as temporary:
        directory = Path(temporary)
        config = write_case(directory / "valid", source, synthetic_secrets())
        require_success(run_compiler(config, "config"))
        check_negative_configs(directory, source)
        require_success(run_compiler(config, "compile", "--only-generate"))
        check_generated_profile(config)
        if args.compile:
            require_success(run_compiler(config, "compile"))
    print("Synthetic firmware config/security checks passed; no upload or hardware qualification.")
    if args.compile:
        print("Full firmware compilation passed; temporary synthetic firmware was removed.")


if __name__ == "__main__":
    main()
