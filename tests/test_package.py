"""Build the actual wheel and verify its executable module is distributed."""

import shutil
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
    wheel = ProjectBuilder(str(staging)).build("wheel", str(tmp_path / "dist"))
    with zipfile.ZipFile(wheel) as archive:
        source = archive.read("dbus_grid_service.py")
        assert source == (root / "src/dbus_grid_service.py").read_bytes()
        compile(source, "dbus_grid_service.py", "exec")
