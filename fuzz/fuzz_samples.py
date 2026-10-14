import json
import math
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import atheris

# Typeshed exposes the instrumentation APIs through their implementation modules.
if TYPE_CHECKING:
    from atheris.import_hook import instrument_imports
    from atheris.instrument_bytecode import instrument_func
else:
    instrument_imports = atheris.instrument_imports
    instrument_func = atheris.instrument_func

ROOT = Path(__file__).resolve().parents[1]


def forbidden(*args: object, **kwargs: object) -> NoReturn:
    raise AssertionError("Grid parser fuzzing cannot call device APIs")


for name in ("dbus", "dbus.mainloop", "dbus.mainloop.glib", "gi", "gi.repository", "vedbus"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["dbus.mainloop.glib"].__dict__["DBusGMainLoop"] = forbidden
sys.modules["gi.repository"].__dict__["GLib"] = types.SimpleNamespace(timeout_add=forbidden)
sys.modules["vedbus"].__dict__["VeDbusService"] = forbidden
sys.path.insert(0, str(ROOT / "src"))

with instrument_imports():
    from dbus_grid_service import MQTT_TOPIC_PREFIX, normalize_payload


def test_one_input(data: bytes) -> None:
    try:
        value = json.loads(data)
    except (ValueError, RecursionError):
        return
    try:
        sample = normalize_payload(f"{MQTT_TOPIC_PREFIX.rstrip('/')}/power", value)
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
    atheris.Setup(sys.argv, instrument_func(test_one_input))
    atheris.Fuzz()
