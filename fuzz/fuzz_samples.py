import json
import math
import sys
import types
from pathlib import Path

import atheris

ROOT = Path(__file__).resolve().parents[1]


def forbidden(*args, **kwargs):
    raise AssertionError("Grid parser fuzzing cannot call device APIs")


for name in ("dbus", "dbus.mainloop", "dbus.mainloop.glib", "gi", "gi.repository", "vedbus"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["dbus.mainloop.glib"].DBusGMainLoop = forbidden
sys.modules["gi.repository"].GLib = types.SimpleNamespace(timeout_add=forbidden)
sys.modules["vedbus"].VeDbusService = forbidden
sys.path.insert(0, str(ROOT / "src"))

with atheris.instrument_imports():
    from dbus_grid_service import normalize_payload


def test_one_input(data: bytes) -> None:
    try:
        value = json.loads(data)
    except (ValueError, RecursionError):
        return
    try:
        sample = normalize_payload("grid-sensor/power", value)
    except (ValueError, TypeError, OverflowError):
        return
    assert set(sample) <= {
        "power",
        "voltage",
        "current",
        "energy_forward",
        "energy_reverse",
        "frequency",
        "status",
    }  # nosec B101 - intentional test oracle
    assert all(name == "status" or math.isfinite(item) for name, item in sample.items())  # nosec B101 - intentional test oracle


if __name__ == "__main__":
    atheris.Setup(sys.argv, atheris.instrument_func(test_one_input))
    atheris.Fuzz()
