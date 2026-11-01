"""Exercise the image's dependency installer without downloading packages."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def installer(tmp_path: Path, **changes: str) -> tuple[subprocess.CompletedProcess[str], list]:
    """Run the real shell with isolated files and observable package commands."""
    system = tmp_path / "system"
    system.mkdir()
    (system / "os-release").write_text(
        changes.pop("os_release", "ID=ubuntu\nVERSION_CODENAME=noble\n")
    )
    keyring = system / "archive-keyring.gpg"
    if changes.pop("keyring", "yes") == "yes":
        keyring.write_text("existing trust anchor")
    (system / "sources.list").write_text("original source list")
    (system / "sources.list.d").mkdir()
    (system / "sources.list.d/ubuntu.sources").write_text("signed ports configuration")
    original = {p: p.read_bytes() for p in system.rglob("*") if p.is_file()}
    binary = tmp_path / "bin"
    binary.mkdir()
    (binary / "dpkg").write_text('#!/bin/sh\nprintf "%s\\n" "$TEST_ARCH"\n')
    (binary / "dpkg").chmod(0o755)
    (binary / "apt-get").write_text(
        f"#!{sys.executable}\n"
        "import json,os,pathlib,sys,time\n"
        "args=sys.argv[1:]; op='update' if 'update' in args else 'install'\n"
        "options={a.split('=',1)[0]:a.split('=',1)[1] for a in args if '=' in a and not a.startswith('--')}\n"
        "source=pathlib.Path(options['Dir::Etc::sourcelist'])\n"
        "row={'args':args,'options':options,'source':source.read_text()}\n"
        "if 'mirror+file:' in row['source']:\n"
        " root=source.parent; row['mirrors']=(root/'mirrors.txt').read_text()\n"
        " row['modes']={p.name:oct(p.stat().st_mode&0o777) for p in [root,source,root/'mirrors.txt',root/'lists']}\n"
        "with open(os.environ['TEST_LOG'],'a') as f:f.write(json.dumps(row)+'\\n')\n"
        "time.sleep(float(os.getenv('TEST_SLEEP_'+op.upper(),'0')))\n"
        "sys.exit(int(os.getenv('TEST_EXIT_'+op.upper(),'0')))\n"
    )
    (binary / "apt-get").chmod(0o755)
    timeout = shutil.which("gtimeout") or shutil.which("timeout")
    assert timeout, "GNU timeout is required by the production container"
    (binary / "timeout").symlink_to(timeout)
    text = (ROOT / "scripts/install-container-deps.sh").read_text()
    for before, after in (
        ("/etc/os-release", str(system / "os-release")),
        ("/usr/share/keyrings/ubuntu-archive-keyring.gpg", str(keyring)),
        ("/etc/apt/sources.list", str(system / "sources.list")),
    ):
        text = text.replace(before, after)
    if changes.pop("short_timeout", "no") == "yes":
        text = text.replace("180s", "0.2s").replace("--kill-after=15s", "--kill-after=0.2s")
    script = tmp_path / "installer.sh"
    script.write_text(text)
    log = tmp_path / "calls.jsonl"
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    env = dict(
        os.environ,
        PATH=f"{binary}:{os.environ['PATH']}",
        TMPDIR=str(scratch),
        TEST_LOG=str(log),
        TEST_ARCH=changes.pop("arch", "amd64"),
    )
    env.update(changes)
    packages = [] if env.pop("no_packages", "no") == "yes" else ["python3", "python3-dbus"]
    result = subprocess.run(
        ["/bin/sh", "-c", 'umask 077; exec /bin/sh "$@"', "sh", str(script), *packages],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert all(p.read_bytes() == b for p, b in original.items())
    assert list(scratch.iterdir()) == []
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return result, calls


def test_amd64_strict_signed_sources_and_identical_options(tmp_path: Path) -> None:
    """Update and installation share readable temporary signed mirror inputs."""
    result, calls = installer(tmp_path)
    assert result.returncode == 0, result.stderr
    assert len(calls) == 2
    assert calls[0]["options"] == calls[1]["options"]
    assert calls[0]["args"][-2:] == ["update", "--error-on=any"]
    assert calls[1]["args"][-5:] == [
        "install",
        "--yes",
        "--no-install-recommends",
        "python3",
        "python3-dbus",
    ]
    assert calls[0]["mirrors"] == (
        "http://security.ubuntu.com/ubuntu/\tpriority:1\n"
        "http://archive.ubuntu.com/ubuntu/\tpriority:2\n"
    )
    assert "Signed-By:" in calls[0]["source"]
    assert "Suites: noble noble-updates noble-backports noble-security" in calls[0]["source"]
    assert calls[0]["options"]["Dir::Etc::sourceparts"] == "-"
    assert set(calls[0]["modes"].values()) == {"0o755", "0o644"}
    assert calls[0]["options"]["Acquire::Retries"] == "2"
    assert calls[0]["options"]["Acquire::http::Timeout"] == "20"
    assert calls[0]["options"]["DPkg::Lock::Timeout"] == "60"


@pytest.mark.parametrize("arch", ["arm64", "armhf"])
def test_other_architectures_keep_image_sources(tmp_path: Path, arch: str) -> None:
    """ARM images continue to use their original ports and trust configuration."""
    result, calls = installer(tmp_path, arch=arch)
    assert result.returncode == 0, result.stderr
    assert calls[0]["source"] == "original source list"
    assert calls[0]["options"]["Dir::Etc::sourceparts"].endswith("system/sources.list.d")
    assert "mirrors" not in calls[0]


def test_failed_update_prevents_installation(tmp_path: Path) -> None:
    """An incomplete index acquisition fails before any package installation."""
    result, calls = installer(tmp_path, TEST_EXIT_UPDATE="100")
    assert result.returncode == 100
    assert len(calls) == 1


def test_failed_installation_is_not_masked(tmp_path: Path) -> None:
    """Installer errors remain errors after cleaning temporary list files."""
    result, calls = installer(tmp_path, TEST_EXIT_INSTALL="100")
    assert result.returncode == 100
    assert len(calls) == 2


def test_slow_update_has_finite_timeout(tmp_path: Path) -> None:
    """The actual GNU timeout terminates a slow updater before installation."""
    result, calls = installer(tmp_path, TEST_SLEEP_UPDATE="5", short_timeout="yes")
    assert result.returncode == 124
    assert len(calls) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"os_release": "ID=ubuntu\nVERSION_CODENAME=resolute\n"},
        {"keyring": "no"},
        {"no_packages": "yes"},
    ],
)
def test_invalid_prerequisites_stop_before_apt(tmp_path: Path, changes: dict[str, str]) -> None:
    """Unsupported suites, absent trust anchors and empty requests fail closed."""
    result, calls = installer(tmp_path, **changes)
    assert result.returncode != 0
    assert calls == []


def test_container_preserves_packages_and_native_import_contract() -> None:
    """Both stages reuse one pinned base while preserving production imports."""
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert (
        dockerfile.count(
            "ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac"
        )
        == 1
    )
    assert "FROM apt-base AS builder" in dockerfile
    assert "FROM apt-base\n" in dockerfile
    assert "RUN install-container-deps ca-certificates python3 python3-venv" in dockerfile
    assert (
        "RUN install-container-deps gir1.2-glib-2.0 python3 python3-dbus python3-gi" in dockerfile
    )
    assert (
        "RUN python -c 'import dbus_grid_service; from vedbus import VeDbusService'" in dockerfile
    )
    assert "USER appuser" in dockerfile
