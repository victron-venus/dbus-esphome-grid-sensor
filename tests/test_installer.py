"""Render the real systemd generator with filesystem and service-manager adapters."""

import os
import subprocess
from pathlib import Path


def test_systemd_generator_uses_persistent_install_directory(tmp_path: Path) -> None:
    """The installer must not generate a unit pointing at its old /opt location."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "install.sh").read_text()
    function = source.split("create_systemd_service() {", 1)[1].split("\nverify_installation()", 1)[
        0
    ]
    # Redirect only the host output directory; execute the actual generator body.
    function = "create_systemd_service() {" + function.replace(
        '"/etc/systemd/system/$SERVICE_NAME.service"', '"$TEST_OUTPUT/$SERVICE_NAME.service"'
    )
    script = (
        "set -eu\nlog_info() { :; }\nlog_success() { :; }\n"
        'systemctl() { printf "%s\\n" "$*" >> "$TEST_OUTPUT/calls"; }\n'
        + function
        + "\ncreate_systemd_service\n"
    )
    install_dir = tmp_path / "persistent"
    environment = dict(
        os.environ,
        TEST_OUTPUT=str(tmp_path),
        INSTALL_DIR=str(install_dir),
        SERVICE_NAME="dbus-grid-service",
    )
    subprocess.run(["bash", "-c", script], env=environment, check=True)
    unit = (tmp_path / "dbus-grid-service.service").read_text()
    assert f"WorkingDirectory={install_dir}" in unit
    assert f"EnvironmentFile={install_dir}/.env" in unit
    assert "ExecStart=/usr/bin/python3 dbus_grid_service.py" in unit
    assert (tmp_path / "calls").read_text().splitlines() == [
        "daemon-reload",
        "enable dbus-grid-service",
    ]
