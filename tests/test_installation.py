"""Run the real POSIX installer in a disposable mapped Venus filesystem."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def test_install_preserves_literal_configuration_and_boot_order(tmp_path):
    repo = Path(__file__).parents[1]
    install_script = (repo / "install.sh").read_text()
    # Map absolute device paths; keep every installer branch and generated script.
    install_script = re.sub(
        r"(?<![\w/}])(/data|/service|/var/log|/var/run|/etc/systemd|/run/systemd)",
        lambda match: str(tmp_path) + match.group(),
        install_script,
    )
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    shutil.copy(repo / "src/dbus_grid_service.py", source / "src")
    shutil.copy(repo / "src/service_launcher.py", source / "src")
    installer = source / "install.sh"
    installer.write_text(install_script)
    (tmp_path / "data").mkdir()
    (tmp_path / "service").mkdir()
    rc = tmp_path / "data/rc.local"
    rc.write_text("#!/bin/sh\necho existing-boot-task\nexit 0\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").symlink_to(sys.executable)
    for name, output in (
        ("id", "echo 0"),
        ("svc", "exit 0"),
        ("multilog", "exit 0"),
        ("sleep", "exit 0"),
    ):
        command = bin_dir / name
        command.write_text("#!/bin/sh\n" + output + "\n")
        command.chmod(0o755)
    stubs = tmp_path / "stubs"
    (stubs / "gi").mkdir(parents=True)
    (stubs / "dbus/mainloop").mkdir(parents=True)
    (stubs / "dbus/__init__.py").write_text("")
    (stubs / "dbus/mainloop/__init__.py").write_text("")
    (stubs / "dbus/mainloop/glib.py").write_text("DBusGMainLoop = object()\n")
    (stubs / "vedbus.py").write_text("class VeDbusService: pass\n")
    (stubs / "gi/__init__.py").write_text("")
    (stubs / "gi/repository.py").write_text("GLib = object()\n")
    install_script = installer.read_text().replace("if [[ $EUID -ne 0 ]]; then", "if false; then")
    installer.write_text(install_script)
    environment = dict(
        os.environ,
        PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
        PYTHONPATH=str(stubs),
        CUSTOM_NAME="Grid sensor with spaces",
        MQTT_PASSWORD="literal $value `text` # spaces",
    )
    result = subprocess.run(
        ["bash", str(installer), "--skip-start"], env=environment, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    installed = tmp_path / "data/dbus-grid-service"
    from dotenv import dotenv_values

    config = (installed / ".env").read_text()
    parsed = dotenv_values(installed / ".env", interpolate=False)
    assert parsed["CUSTOM_NAME"] == "Grid sensor with spaces"
    assert parsed["MQTT_PASSWORD"] == "literal $value `text` # spaces"
    assert (installed / ".env").stat().st_mode & 0o777 == 0o600
    boot = str(installed / "boot.sh")
    assert rc.read_text().index(boot) < rc.read_text().index("exit 0")
    assert "echo existing-boot-task" in rc.read_text()
    service = tmp_path / "service/dbus-grid-service"
    assert service.is_symlink()
    assert (service / "down").exists()
    assert "exec 2>&1" in (service / "run").read_text()
    assert "s25000 n4" in (service / "log/run").read_text()
    environment["MQTT_PASSWORD"] = "replacement-must-not-overwrite"
    result = subprocess.run(
        ["bash", str(installer), "--skip-start"], env=environment, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert (installed / ".env").read_text() == config
    assert rc.read_text().splitlines().count(boot) == 1
    assert not list((tmp_path / "service").glob("*.old*"))
