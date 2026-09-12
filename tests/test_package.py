"""Build the actual wheel and verify its executable module is distributed."""

import ast
import shutil
import tarfile
import tomllib
import zipfile
from pathlib import Path

from build import ProjectBuilder


def test_wheel_contains_runtime_module(tmp_path: Path) -> None:
    """Package discovery must include the single module used by the entrypoint."""
    root = Path(__file__).resolve().parents[1]
    staging = tmp_path / "source"
    staging.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy2(root / name, staging / name)
    shutil.copytree(
        root / "src", staging / "src", ignore=shutil.ignore_patterns("*.egg-info", "__pycache__")
    )
    builder = ProjectBuilder(str(staging))
    wheel = builder.build("wheel", str(tmp_path / "dist"))
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    declarations = ast.parse((root / "src/dbus_grid_service.py").read_text()).body
    runtime_version = next(
        node.value.value
        for node in declarations
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets)
    )
    assert runtime_version == version
    with zipfile.ZipFile(wheel) as archive:
        for name in ("dbus_grid_service.py", "service_launcher.py"):
            source = archive.read(name)
            assert source == (root / "src" / name).read_bytes()
            compile(source, name, "exec")

    sdist = builder.build("sdist", str(tmp_path / "dist"))
    with tarfile.open(sdist) as archive:
        prefix = f"dbus_esphome_grid_sensor-{version}"
        for name in ("dbus_grid_service.py", "service_launcher.py"):
            member = archive.extractfile(f"{prefix}/src/{name}")
            assert member is not None
            assert member.read() == (root / "src" / name).read_bytes()
