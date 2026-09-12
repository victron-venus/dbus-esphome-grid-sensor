"""Read literal service settings using only the Venus OS standard library."""

import os
import re
import sys
from pathlib import Path


def read_settings(path: Path) -> dict[str, str]:
    """Read installer KEY=VALUE settings, including existing quoted dotenv files.

    Values are data: there is no shell evaluation or variable interpolation.
    Single-quoted values retain escapes other than a quote/backslash; double
    quotes also support the JSON escapes written by the installer.
    """
    if not path.exists():
        return {}
    settings = {}
    lines = iter(path.read_text(encoding="utf-8").splitlines(keepends=True))
    escapes = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "a": "\a", "v": "\v"}
    for line in lines:
        line = line.rstrip("\r\n").lstrip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.removeprefix("export ").partition("=")
        if not separator:
            continue
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"Invalid configuration key: {key}")
        value = value.lstrip()
        if value.startswith(("'", '"')):
            quote = value[0]
            pattern = re.compile(
                re.escape(quote)
                + r"((?:\\.|[^\\"
                + re.escape(quote)
                + r"])*)"
                + re.escape(quote)
                + r"[ \t]*(?:#.*)?",
                re.DOTALL,
            )
            match = pattern.fullmatch(value)
            while match is None:
                continuation = next(lines, None)
                if continuation is None:
                    raise ValueError(f"Unterminated quoted value for {key}")
                value += "\n" + continuation.rstrip("\r\n")
                match = pattern.fullmatch(value)
            value = match.group(1)
            if quote == "'":
                value = re.sub(r"\\(['\\])", lambda item: item.group(1), value)
            else:
                value = re.sub(
                    r"\\([\\\"'abfnrtv])",
                    lambda item: escapes.get(item.group(1), item.group(1)),
                    value,
                )
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        settings[key] = value
    return settings


def service_environment(path: Path) -> dict[str, str]:
    """Read literal configuration while preserving explicit process overrides."""
    return {**read_settings(path), **os.environ}


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
