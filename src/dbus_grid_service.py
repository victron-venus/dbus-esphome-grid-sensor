#!/usr/bin/env python3
"""
D-Bus Grid Sensor Service for Victron Venus OS

Subscribes to MQTT topics from ESPHome CT grid sensor and registers
as com.victronenergy.grid on D-Bus, exposing grid metrics.

D-Bus Paths (com.victronenergy.grid):
- /Ac/Power                - Total AC power (W, positive = import, negative = export)
- /Ac/L1/Power             - L1 AC power (W)
- /Ac/L1/Voltage           - L1 voltage (V)
- /Ac/L1/Current           - L1 current (A)
- /Ac/Energy/Forward       - Total energy imported (kWh)
- /Ac/Energy/Reverse       - Total energy exported (kWh)
- /Ac/Frequency            - Grid frequency (Hz)
- /Status                  - 0=OK, 1=Warning, 2=Error
- /CustomName              - User-defined name
- /DeviceInstance          - Device instance number
- /Connected               - 1=connected, 0=disconnected
- /ErrorCode               - Error code (0=none)
"""

import os
import sys
import json
import time
import signal
import logging
import threading
from typing import Optional
from dataclasses import dataclass, field

import paho.mqtt.client as mqtt
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

# Victron D-Bus
try:
    from vedbus import VeDBusService
except ImportError:
    print("Error: vedbus not installed. Install with: pip install vedbus")
    sys.exit(1)


# Configuration from environment
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "grid-sensor")

DBUS_SERVICE_NAME = f"com.victronenergy.grid.{os.getenv('DBUS_INSTANCE', '42')}"
DEVICE_INSTANCE = int(os.getenv("DEVICE_INSTANCE", "42"))
CUSTOM_NAME = os.getenv("CUSTOM_NAME", "ESPHome CT Grid Sensor")
RECONNECT_DELAY = int(os.getenv("RECONNECT_DELAY", "5"))
MQTT_KEEPALIVE = int(os.getenv("MQTT_KEEPALIVE", "60"))

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("dbus-grid-service")


@dataclass
class GridData:
    """Container for grid sensor data"""
    power: float = 0.0           # W
    voltage: float = 230.0       # V
    current: float = 0.0         # A
    energy_forward: float = 0.0  # kWh
    energy_reverse: float = 0.0  # kWh
    frequency: float = 50.0      # Hz
    status: int = 0              # 0=OK, 1=Warning, 2=Error
    last_update: float = field(default_factory=time.time)
    connected: bool = False


class DBusGridService:
    """D-Bus service registrating as Victron grid meter"""

    def __init__(self, service_name: str, device_instance: int, custom_name: str):
        self.service_name = service_name
        self.device_instance = device_instance
        self.custom_name = custom_name
        self.data = GridData()
        self.dbus_service: Optional[VeDBusService] = None
        self.running = False
        self._lock = threading.Lock()

    def setup_dbus(self) -> None:
        """Initialize D-Bus service with all required paths"""
        DBusGMainLoop(set_as_default=True)

        self.dbus_service = VeDBusService(self.service_name)

        # Management paths
        self.dbus_service.add_path("/Mgmt/ProcessName", "dbus-grid-service")
        self.dbus_service.add_path("/Mgmt/ProcessVersion", "1.0.0")
        self.dbus_service.add_path("/Mgmt/Connection", "MQTT")

        # Device info
        self.dbus_service.add_path("/DeviceInstance", self.device_instance)
        self.dbus_service.add_path("/ProductId", 0xFFFF)
        self.dbus_service.add_path("/ProductName", self.custom_name)
        self.dbus_service.add_path("/CustomName", self.custom_name)
        self.dbus_service.add_path("/FirmwareVersion", "1.0")
        self.dbus_service.add_path("/HardwareVersion", "ESP32-SCT013")
        self.dbus_service.add_path("/Connected", 0)

        # Grid AC paths (com.victronenergy.grid standard)
        self.dbus_service.add_path("/Ac/Power", 0.0, writeable=True)
        self.dbus_service.add_path("/Ac/L1/Power", 0.0, writeable=True)
        self.dbus_service.add_path("/Ac/L1/Voltage", 230.0, writeable=True)
        self.dbus_service.add_path("/Ac/L1/Current", 0.0, writeable=True)
        self.dbus_service.add_path("/Ac/Energy/Forward", 0.0, writeable=True)
        self.dbus_service.add_path("/Ac/Energy/Reverse", 0.0, writeable=True)
        self.dbus_service.add_path("/Ac/Frequency", 50.0, writeable=True)

        # Status paths
        self.dbus_service.add_path("/Status", 0, writeable=True)
        self.dbus_service.add_path("/ErrorCode", 0, writeable=True)

        logger.info(f"D-Bus service registered: {self.service_name}")

    def update_from_mqtt(self, topic: str, payload: dict) -> None:
        """Update internal state from MQTT message"""
        with self._lock:
            updated = False

            # Power (W)
            if "power" in payload:
                self.data.power = float(payload["power"])
                updated = True

            # Voltage (V)
            if "voltage" in payload:
                self.data.voltage = float(payload["voltage"])
                updated = True

            # Current (A)
            if "current" in payload:
                self.data.current = float(payload["current"])
                updated = True

            # Energy forward (kWh)
            if "energy_forward" in payload:
                self.data.energy_forward = float(payload["energy_forward"])
                updated = True

            # Energy reverse (kWh)
            if "energy_reverse" in payload:
                self.data.energy_reverse = float(payload["energy_reverse"])
                updated = True

            # Frequency (Hz)
            if "frequency" in payload:
                self.data.frequency = float(payload["frequency"])
                updated = True

            # Connection status
            if "status" in payload:
                self.data.connected = payload["status"] == "online"
                self.data.status = 0 if self.data.connected else 2
                updated = True

            if updated:
                self.data.last_update = time.time()
                self._push_to_dbus()

    def _push_to_dbus(self) -> None:
        """Push current data to D-Bus"""
        if not self.dbus_service:
            return

        try:
            # Power values (positive = import, negative = export)
            self.dbus_service["/Ac/Power"] = self.data.power
            self.dbus_service["/Ac/L1/Power"] = self.data.power
            self.dbus_service["/Ac/L1/Voltage"] = self.data.voltage
            self.dbus_service["/Ac/L1/Current"] = self.data.current
            self.dbus_service["/Ac/Energy/Forward"] = self.data.energy_forward
            self.dbus_service["/Ac/Energy/Reverse"] = self.data.energy_reverse
            self.dbus_service["/Ac/Frequency"] = self.data.frequency

            # Connection status: 1 on D-Bus = connected
            self.dbus_service["/Connected"] = 1 if self.data.connected else 0
            self.dbus_service["/Status"] = self.data.status
            self.dbus_service["/ErrorCode"] = 0 if self.data.connected else 1

        except Exception as e:
            logger.error(f"Failed to update D-Bus: {e}")

    def check_connection_timeout(self) -> None:
        """Check if MQTT data is stale and mark disconnected"""
        with self._lock:
            if time.time() - self.data.last_update > 30:
                if self.data.connected:
                    logger.warning("MQTT data stale, marking disconnected")
                    self.data.connected = False
                    self.data.status = 2
                    self._push_to_dbus()


class MQTTHandler:
    """MQTT client handler for grid sensor"""

    def __init__(self, dbus_service: DBusGridService):
        self.dbus_service = dbus_service
        self.client = mqtt.Client(
            client_id=f"dbus-grid-service-{DEVICE_INSTANCE}",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_subscribe = self._on_subscribe

        if MQTT_USERNAME:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info(f"MQTT connected to {MQTT_BROKER}:{MQTT_PORT}")
            # Subscribe to all grid sensor topics
            topics = [
                (f"{MQTT_TOPIC_PREFIX}/power", 0),
                (f"{MQTT_TOPIC_PREFIX}/voltage", 0),
                (f"{MQTT_TOPIC_PREFIX}/current", 0),
                (f"{MQTT_TOPIC_PREFIX}/energy_forward", 0),
                (f"{MQTT_TOPIC_PREFIX}/energy_reverse", 0),
                (f"{MQTT_TOPIC_PREFIX}/frequency", 0),
                (f"{MQTT_TOPIC_PREFIX}/status", 0),
                (f"{MQTT_TOPIC_PREFIX}/#", 0),  # Catch-all
            ]
            client.subscribe(topics)
        else:
            logger.error(f"MQTT connection failed: {reason_code}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        logger.warning(f"MQTT disconnected: {reason_code}")
        self.dbus_service.data.connected = False
        self.dbus_service.data.status = 2
        self.dbus_service._push_to_dbus()

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties):
        logger.debug(f"MQTT subscribed: mid={mid}")

    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())

            logger.debug(f"MQTT: {topic} = {payload}")
            self.dbus_service.update_from_mqtt(topic, payload)

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON on {msg.topic}: {msg.payload}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def connect(self) -> bool:
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"MQTT connect error: {e}")
            return False

    def disconnect(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()


def create_pid_file(pid_path: str) -> None:
    """Create PID file for daemontools"""
    try:
        with open(pid_path, "w") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.warning(f"Could not write PID file: {e}")


def remove_pid_file(pid_path: str) -> None:
    """Remove PID file on exit"""
    try:
        os.remove(pid_path)
    except Exception:
        pass


def main():
    """Main entry point"""
    logger.info("Starting dbus-grid-service")

    # Setup signal handlers
    shutdown = threading.Event()

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        shutdown.set()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Create PID file
    pid_path = "/run/dbus-grid-service.pid"
    create_pid_file(pid_path)

    try:
        # Initialize D-Bus service
        dbus_service = DBusGridService(DBUS_SERVICE_NAME, DEVICE_INSTANCE, CUSTOM_NAME)
        dbus_service.setup_dbus()

        # Initialize MQTT handler
        mqtt_handler = MQTTHandler(dbus_service)

        # Connect to MQTT
        if not mqtt_handler.connect():
            logger.error("Failed to connect to MQTT, retrying...")
            time.sleep(RECONNECT_DELAY)
            if not mqtt_handler.connect():
                logger.error("MQTT connection failed permanently")
                return 1

        # Push initial values
        dbus_service._push_to_dbus()

        # Setup periodic connection check
        def periodic_check():
            dbus_service.check_connection_timeout()
            return True  # Continue timeout

        GLib.timeout_add_seconds(10, periodic_check)

        logger.info("Service running. Press Ctrl+C to stop.")

        # Run GLib main loop
        loop = GLib.MainLoop()

        def check_shutdown():
            if shutdown.is_set():
                loop.quit()
                return False
            return True

        GLib.timeout_add(100, check_shutdown)
        loop.run()

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1

    finally:
        logger.info("Shutting down...")
        remove_pid_file(pid_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())