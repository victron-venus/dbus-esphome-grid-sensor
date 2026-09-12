"""Load native-service configuration as data, then replace the launcher process."""

import os
import sys
from pathlib import Path

from dotenv import dotenv_values


def service_environment(path: Path) -> dict[str, str]:
    """Read literal dotenv values while preserving explicit process overrides."""
    configured = dotenv_values(path, interpolate=False)
    return {**{key: value for key, value in configured.items() if value is not None}, **os.environ}


def main() -> None:
    """Exec the service so Python applies its configured module search path."""
    directory = Path(__file__).resolve().parent
    os.execve(
        sys.executable,
        [sys.executable, str(directory / "dbus_grid_service.py")],
        service_environment(directory / ".env"),
    )


if __name__ == "__main__":
    main()
