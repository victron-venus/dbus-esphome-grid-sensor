"""Exercise native configuration parsing without D-Bus, MQTT or a service manager."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values, set_key

import service_launcher


def test_literal_environment_and_process_overrides(tmp_path, monkeypatch):
    """Spaces and shell-looking input remain data; explicit process values win."""
    path = tmp_path / ".env"
    values = {
        "CUSTOM_NAME": "Kitchen 'grid' sensor #1",
        "MQTT_PASSWORD": "a # b $HOME ${USER} `touch marker` $(touch marker)",
        "MQTT_BROKER": "file-broker",
        "PYTHONPATH": "/path with spaces/velib:/other",
        "MQTT_USERNAME": "",
    }
    for key, value in values.items():
        monkeypatch.delenv(key, raising=False)
        set_key(path, key, value, quote_mode="always")
    monkeypatch.setenv("MQTT_BROKER", "process-broker")
    environment = service_launcher.service_environment(path)
    assert environment == {**values, **os.environ}
    assert environment["MQTT_PASSWORD"] == values["MQTT_PASSWORD"]
    assert not (tmp_path / "marker").exists()


def test_launcher_executes_real_entrypoint_with_configured_search_path(tmp_path, monkeypatch):
    """Only the exec boundary is replaced; configuration is read from disk."""
    monkeypatch.setattr(service_launcher, "__file__", str(tmp_path / "service_launcher.py"))
    monkeypatch.delenv("PYTHONPATH", raising=False)
    (tmp_path / ".env").write_text("PYTHONPATH='/official/velib_python'\nCUSTOM_NAME='Grid Room'\n")
    calls = []
    monkeypatch.setattr(service_launcher.os, "execve", lambda *args: calls.append(args))
    service_launcher.main()
    executable, arguments, environment = calls[0]
    assert executable == sys.executable
    assert arguments == [sys.executable, str(tmp_path / "dbus_grid_service.py")]
    assert environment["PYTHONPATH"] == "/official/velib_python"
    assert environment["CUSTOM_NAME"] == "Grid Room"


def test_installer_copies_launcher_and_round_trips_literal_values(tmp_path):
    """Run only the actual copy/config writer inside a temporary install directory."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "install.sh").read_text()
    function = (
        "copy_files() {"
        + source.split("copy_files() {", 1)[1].split("\ncreate_daemontools_service()", 1)[0]
    )
    values = {
        "MQTT_BROKER": "localhost",
        "MQTT_PORT": "1883",
        "MQTT_USERNAME": "",
        "MQTT_PASSWORD": "quote' slash\\ # dollar${HOME}",
        "MQTT_TOPIC_PREFIX": "grid-sensor",
        "DBUS_INSTANCE": "42",
        "DEVICE_INSTANCE": "42",
        "CUSTOM_NAME": "Grid room #1",
        "PYTHONPATH": "/library path",
        "RECONNECT_DELAY": "5",
    }
    environment = dict(
        os.environ,
        **values,
        INSTALL_DIR=str(tmp_path),
        PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
    )
    subprocess.run(
        [
            "bash",
            "-c",
            "set -eu\nlog_info() { :; }\nlog_success() { :; }\n" + function + "\ncopy_files\n",
            str(root / "install.sh"),
        ],
        env=environment,
        check=True,
    )
    assert dotenv_values(tmp_path / ".env", interpolate=False) == values
    for name in ("dbus_grid_service.py", "service_launcher.py"):
        assert (tmp_path / name).read_bytes() == (root / "src" / name).read_bytes()
