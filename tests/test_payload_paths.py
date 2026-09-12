"""Hardware-free tests: ESPHome/MQTT payloads -> GridData -> fake D-Bus writes."""

import json
import sys
import types
from typing import Any

import pytest


# --- vedbus stub -------------------------------------------------------------
# vedbus is Victron-only (no PyPI). Stub VeDbusService so the module imports
# on a dev box and we can capture add_path / __setitem__ calls.
class _StubVeDbusService:
    def __init__(self, service_name: str, register: bool = True) -> None:
        self.service_name = service_name
        assert register is False
        self.registered = False
        self.paths: dict[str, Any] = {}

    def register(self) -> None:
        assert "/DeviceInstance" in self.paths
        assert "/Ac/Power" in self.paths
        self.registered = True

    def add_path(self, path: str, value: Any, writeable: bool = False) -> None:
        self.paths[path] = value

    def __setitem__(self, path: str, value: Any) -> None:
        self.paths[path] = value

    def __getitem__(self, path: str) -> Any:
        return self.paths[path]


vedbus_mod = types.ModuleType("vedbus")
vedbus_mod.VeDbusService = _StubVeDbusService
sys.modules["vedbus"] = vedbus_mod

# gi.repository.GLib + dbus.mainloop.glib stubs (also unavailable on dev box).
glib_mod = types.ModuleType("gi.repository.GLib")


def _noop(*_a: Any, **_kw: Any) -> bool:
    return True


class _MainLoop:
    def run(self) -> None:
        pass

    def quit(self) -> None:
        pass


glib_mod.idle_add = lambda callback, *args: callback(*args)
glib_mod.timeout_add_seconds = _noop
glib_mod.timeout_add = _noop
glib_mod.MainLoop = _MainLoop
sys.modules.setdefault("gi", types.ModuleType("gi"))
sys.modules.setdefault("gi.repository", types.ModuleType("gi.repository"))
sys.modules["gi.repository.GLib"] = glib_mod


dbus_mainloop = types.ModuleType("dbus.mainloop.glib")


def _dbus_set_default(_arg: bool = False, set_as_default: bool = False) -> None:
    pass


dbus_mainloop.DBusGMainLoop = _dbus_set_default
sys.modules.setdefault("dbus", types.ModuleType("dbus"))
sys.modules.setdefault("dbus.mainloop", types.ModuleType("dbus.mainloop"))
sys.modules["dbus.mainloop.glib"] = dbus_mainloop

# Import the service under test after the stubs land.
# Import the service under test after the stubs land.
import dbus_grid_service as svc  # noqa: E402

# --- GridData assertions -----------------------------------------------------


def test_griddata_defaults():
    g = svc.GridData()
    assert g.power == 0.0
    assert g.voltage == 230.0
    assert g.connected is False
    assert g.status == 0


# --- DBusGridService.update_from_mqtt → path mapping -------------------------


@pytest.fixture
def dgs():
    dgs = svc.DBusGridService("com.victronenergy.grid.test", 42, "ESPHome CT")
    dgs.setup_dbus()
    return dgs


def test_power_payload_sets_ac_power(dgs):
    dgs.update_from_mqtt("grid-sensor/power", {"value": 1234.5})
    # JSON-wrapped payloads are common; the topic sends raw floats via plain
    # {"value":...} in ESPHome; both shapes must coerce. We accept both shapes.
    assert dgs.data.power == 1234.5
    assert dgs.dbus_service.paths["/Ac/Power"] == 1234.5


def test_full_payload_round_trip(dgs):
    payload = {
        "power": 1500.0,
        "voltage": 230.5,
        "current": 6.5,
        "energy_forward": 12.34,
        "energy_reverse": 0.5,
        "frequency": 50.01,
        "status": "online",
    }
    dgs.update_from_mqtt("grid-sensor/state", payload)

    assert dgs.data.power == 1500.0
    assert dgs.data.voltage == 230.5
    assert dgs.data.current == 6.5
    assert dgs.data.energy_forward == 12.34
    assert dgs.data.energy_reverse == 0.5
    assert dgs.data.frequency == 50.01
    assert dgs.data.connected is True
    assert dgs.data.status == 0

    # D-Bus writes the canonical grid paths (com.victronenergy.grid)
    paths = dgs.dbus_service.paths
    assert paths["/Ac/Power"] == 1500.0
    assert paths["/Ac/L1/Power"] == 1500.0
    assert paths["/Ac/L1/Voltage"] == 230.5
    assert paths["/Ac/L1/Current"] == 6.5
    assert paths["/Ac/Energy/Forward"] == 12.34
    assert paths["/Ac/Energy/Reverse"] == 0.5
    assert paths["/Ac/Frequency"] == 50.01
    assert paths["/Connected"] == 1
    assert paths["/Status"] == 0
    assert paths["/ErrorCode"] == 0


def test_offline_payload_marks_disconnected(dgs):
    dgs.update_from_mqtt("grid-sensor/status", {"status": "offline"})
    assert dgs.data.connected is False
    assert dgs.data.status == 2
    assert dgs.dbus_service.paths["/Connected"] == 0
    assert dgs.dbus_service.paths["/Status"] == 2
    assert dgs.dbus_service.paths["/ErrorCode"] == 1


def test_negative_power_for_export(dgs):
    """Negative W = export. Victron grid path /Ac/Power accepts negatives."""
    dgs.update_from_mqtt("grid-sensor/power", {"power": -800.0})
    assert dgs.data.power == -800.0
    assert dgs.dbus_service.paths["/Ac/Power"] == -800.0
    assert dgs.dbus_service.paths["/Ac/L1/Power"] == -800.0


def test_partial_payload_only_updates_known_keys(dgs):
    """An MQTT update with only 'voltage' must NOT clobber the other paths."""
    dgs.update_from_mqtt(
        "grid-sensor/state",
        {"power": 1000.0, "voltage": 230.0, "current": 4.0, "frequency": 50.0},
    )
    dgs.update_from_mqtt("grid-sensor/voltage", {"voltage": 240.0})
    assert dgs.data.voltage == 240.0
    assert dgs.data.power == 1000.0  # untouched
    assert dgs.data.current == 4.0  # untouched


def test_unknown_keys_are_ignored(dgs):
    """Forward-compat: ESPHome may send new fields; we ignore unknowns."""
    dgs.update_from_mqtt(
        "grid-sensor/state",
        {"power": 100.0, "phase_angle": 12.3, "future_field": "abc"},
    )
    assert dgs.data.power == 100.0


def test_setup_registers_mandatory_victron_paths(dgs):
    """com.victronenergy.grid requires these management + device paths."""
    paths = dgs.dbus_service.paths
    assert paths["/Mgmt/ProcessName"] == "dbus-grid-service"
    assert paths["/Mgmt/Connection"] == "MQTT"
    assert paths["/DeviceInstance"] == 42
    assert paths["/ProductId"] == 0xFFFF
    assert paths["/ProductName"] == "ESPHome CT"
    assert paths["/HardwareVersion"] == "ESP32-SCT013"
    assert "/Ac/Power" in paths
    assert "/Ac/Energy/Forward" in paths


def test_check_connection_timeout_marks_stale(dgs, monkeypatch):
    import time as _time

    dgs.update_from_mqtt("grid-sensor/state", {"power": 10, "status": "online"})
    assert dgs.data.connected is True

    # Move last_update into the past (>30s)
    dgs.data.last_update = _time.monotonic() - 60
    dgs.check_connection_timeout()
    assert dgs.data.connected is False
    assert dgs.data.status == 2


# --- MQTTHandler._on_message → payload → DBusGridService -------------------


class _StubReasonCode:
    """Stub for paho.mqtt.reasoncodes.ReasonCode — compares as an int via ==."""

    def __init__(self, value: int) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.value == other
        if isinstance(other, _StubReasonCode):
            return self.value == other.value
        return NotImplemented

    def __repr__(self) -> str:
        return f"ReasonCode({self.value})"


class _StubProperties:
    """Stub for paho.mqtt.properties.Properties (paho-mqtt v2 requires packetType)."""


def _mqtt_message(topic: str, payload: dict[str, Any]):
    msg = types.SimpleNamespace(topic=topic, payload=json.dumps(payload).encode())
    return msg


def test_on_message_full_payload_reaches_dbus(monkeypatch):
    dgs = svc.DBusGridService("com.victronenergy.grid.test", 42, "ESPHome CT")
    dgs.setup_dbus()
    handler = svc.MQTTHandler(dgs)

    handler._on_message(  # type: ignore[attr-defined]
        handler.client, None, _mqtt_message("grid-sensor/state", {"power": 500.0, "voltage": 231.0})
    )
    assert dgs.data.power == 500.0
    assert dgs.data.voltage == 231.0
    assert dgs.dbus_service.paths["/Ac/Power"] == 500.0


def test_on_message_invalid_json_is_logged_not_raised(monkeypatch, caplog):
    dgs = svc.DBusGridService("com.victronenergy.grid.test", 42, "ESPHome CT")
    dgs.setup_dbus()
    handler = svc.MQTTHandler(dgs)

    bad = types.SimpleNamespace(topic="grid-sensor/power", payload=b"not-json{")
    with caplog.at_level("WARNING", logger="dbus-grid-service"):
        handler._on_message(handler.client, None, bad)  # type: ignore[attr-defined]

    assert any("Invalid JSON" in r.message for r in caplog.records)


def test_on_connect_subscribes_to_all_grid_topics():
    dgs = svc.DBusGridService("com.victronenergy.grid.test", 42, "ESPHome CT")
    dgs.setup_dbus()
    handler = svc.MQTTHandler(dgs)

    fake_client = types.SimpleNamespace(subscribe=lambda topics: None)

    handler._on_connect(  # type: ignore[attr-defined]
        fake_client,
        None,
        types.SimpleNamespace(),
        # paho-mqtt ReasonCode/Properties constructors differ between v1 and
        # v2. The handler only checks `reason_code == 0`, so a stub with the
        # right __eq__ semantics is enough and keeps the test version-agnostic.
        _StubReasonCode(0),
        _StubProperties(),
    )
    # If subscribe() raised we'd see it; subscribe callable with any args is
    # the contract. Verify the stub was invoked by swapping it for a recorder.
    recorder = types.SimpleNamespace(
        subscribed=[], subscribe=lambda topics: recorder.subscribed.append(topics)
    )
    handler._on_connect(  # type: ignore[attr-defined]
        recorder,
        None,
        types.SimpleNamespace(),
        _StubReasonCode(0),
        _StubProperties(),
    )
    flat = [t for sub in recorder.subscribed for (t, _qos) in sub]
    assert flat == ["grid-sensor/#"]


def test_on_connect_failure_does_not_subscribe():
    dgs = svc.DBusGridService("com.victronenergy.grid.test", 42, "ESPHome CT")
    dgs.setup_dbus()
    handler = svc.MQTTHandler(dgs)

    called = {"subscribe": 0}

    def _track(_t: Any) -> None:
        called["subscribe"] += 1

    recorder = types.SimpleNamespace(subscribe=_track)

    handler._on_connect(  # type: ignore[attr-defined]
        recorder,
        None,
        types.SimpleNamespace(),
        # Non-zero reason_code → failure branch (no subscribe call).
        _StubReasonCode(5),
        _StubProperties(),
    )
    assert called["subscribe"] == 0


@pytest.mark.parametrize("payload", [123.5, {"value": 123.5}, {"power": 123.5}])
def test_topic_payload_variants(dgs, payload):
    dgs.update_from_mqtt("grid-sensor/power", payload)
    assert dgs.dbus_service.paths["/Ac/Power"] == 123.5
    assert dgs.dbus_service.paths["/Connected"] == 1


def test_esphome_native_sensor_topic(dgs):
    dgs.update_from_mqtt("grid-sensor/sensor/grid_power/state", 42.0)
    assert dgs.dbus_service.paths["/Ac/Power"] == 42.0


def test_online_and_energy_do_not_refresh_stale_power(dgs):
    dgs.update_from_mqtt("grid-sensor/power", 42.0)
    dgs.data.last_update -= 60
    dgs.update_from_mqtt("grid-sensor/status", "online")
    dgs.update_from_mqtt("grid-sensor/energy_forward", 100.0)
    dgs.check_connection_timeout()
    assert dgs.dbus_service.paths["/Connected"] == 0
    assert dgs.dbus_service.paths["/Ac/Power"] is None
    dgs.update_from_mqtt("grid-sensor/power", 43.0)
    assert dgs.dbus_service.paths["/Connected"] == 1
    assert dgs.dbus_service.paths["/Ac/Power"] == 43.0


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "unknown", None])
def test_invalid_measurements_do_not_mutate_data(dgs, value):
    before = dgs.data.last_update
    with pytest.raises((ValueError, TypeError)):
        dgs.update_from_mqtt("grid-sensor/state", {"power": 123, "voltage": value})
    assert dgs.data.power == 0.0
    assert dgs.data.last_update == before


def test_mqtt_defers_dbus_writes_until_glib_callback(dgs, monkeypatch):
    pending = []
    monkeypatch.setattr(
        svc.GLib, "idle_add", lambda callback, *args: pending.append((callback, args))
    )
    handler = svc.MQTTHandler(dgs)
    handler._on_message(None, None, _mqtt_message("grid-sensor/power", 42.0))
    assert dgs.data.power == 0.0
    callback, args = pending.pop()
    assert callback(*args) is False
    assert dgs.dbus_service.paths["/Ac/Power"] == 42.0


def test_startup_registers_invalid_measurements_until_power_arrives(dgs):
    assert dgs.dbus_service.registered
    assert dgs.dbus_service.paths["/Ac/Power"] is None
    dgs.update_from_mqtt("grid-sensor/status", "online")
    assert dgs.dbus_service.paths["/Connected"] == 0
    assert svc.DBUS_SERVICE_NAME == "com.victronenergy.grid.esphome_42"


@pytest.mark.parametrize(
    "suffix,field,path,value",
    [
        ("power", "power", "/Ac/Power", -1250.5),
        ("sensor/grid_power/state", "power", "/Ac/Power", 1234.5),
        ("sensor/grid_current/state", "current", "/Ac/L1/Current", 5.4),
        ("sensor/grid_energy_forward/state", "energy_forward", "/Ac/Energy/Forward", 45.2),
        ("sensor/grid_energy_reverse/state", "energy_reverse", "/Ac/Energy/Reverse", 12.1),
    ],
)
def test_real_esphome_scalar_message_reaches_dbus(dgs, suffix, field, path, value):
    """Feed actual Paho messages through the production callback without a broker."""
    dgs.update_from_mqtt("grid-sensor/power", 1.0)
    handler = svc.MQTTHandler(dgs)
    message = svc.mqtt.MQTTMessage(topic=f"grid-sensor/{suffix}".encode())
    message.payload = str(value).encode()
    handler._on_message(handler.client, None, message)
    assert getattr(dgs.data, field) == value
    assert dgs.dbus_service.paths[path] == value


@pytest.mark.parametrize(
    "payload",
    [b"nan", b"NaN", b"Infinity", b"true", b"null", b"[1]", b'{"power": 12, "voltage": "bad"}'],
)
def test_invalid_sample_preserves_all_readings(dgs, payload):
    """Malformed samples must neither partially write D-Bus nor refresh timeout."""
    handler = svc.MQTTHandler(dgs)
    before = vars(dgs.data).copy()
    paths = dgs.dbus_service.paths.copy()
    message = svc.mqtt.MQTTMessage(topic=b"grid-sensor/power")
    message.payload = payload
    handler._on_message(handler.client, None, message)
    assert vars(dgs.data) == before
    assert dgs.dbus_service.paths == paths


def test_custom_prefix_and_plain_availability(dgs, monkeypatch):
    """A configured prefix scopes updates and accepts ESPHome's default will."""
    monkeypatch.setattr(svc, "MQTT_TOPIC_PREFIX", "home/grid")
    handler = svc.MQTTHandler(dgs)
    for topic, payload in [
        ("home/grid/status", b"online"),
        ("grid-sensor/power", b"999"),
        ("home/grid/sensor/grid_power/state", b"42"),
    ]:
        message = svc.mqtt.MQTTMessage(topic=topic.encode())
        message.payload = payload
        handler._on_message(handler.client, None, message)
    assert dgs.data.connected
    assert dgs.data.power == 42
    message = svc.mqtt.MQTTMessage(topic=b"home/grid/status")
    message.payload = b"offline"
    handler._on_message(handler.client, None, message)
    assert not dgs.data.connected
