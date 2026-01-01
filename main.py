"""
Home Assistant MQTT Publisher for Steam Deck
Publishes telemetry data (battery, disk, game, network) to Home Assistant via MQTT Discovery.
"""

import os
import json
import socket
import asyncio
import subprocess
from pathlib import Path
from typing import Any

import decky

# Import paho-mqtt from py_modules
import sys
sys.path.insert(0, os.path.join(decky.DECKY_PLUGIN_DIR, "py_modules"))
import paho.mqtt.client as mqtt

# Constants
SETTINGS_FILE = "settings.json"
MQTT_DISCOVERY_PREFIX = "homeassistant"
STATE_TOPIC_PREFIX = "steamdeck"


def get_default_hostname() -> str:
    """Get the Steam Deck hostname, defaulting to 'steamdeck' if unavailable."""
    try:
        hostname = socket.gethostname()
        return hostname if hostname else "steamdeck"
    except Exception:
        return "steamdeck"


def sanitize_identifier(name: str) -> str:
    """Sanitize a string to be used as an identifier (lowercase, underscores)."""
    return name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")


class MQTTClient:
    """Handles MQTT connection and publishing."""

    def __init__(self):
        self.client = None
        self.connected = False
        self.host = ""
        self.port = 1883
        self.username = ""
        self.password = ""

    def configure(self, host: str, port: int, username: str, password: str):
        """Configure MQTT connection parameters."""
        self.host = host
        self.port = port
        self.username = username
        self.password = password

    def connect(self) -> bool:
        """Connect to the MQTT broker."""
        try:
            if self.client:
                self.disconnect()

            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)

            def on_connect(client, userdata, flags, reason_code, properties):
                if reason_code == 0:
                    self.connected = True
                    decky.logger.info(f"Connected to MQTT broker at {self.host}:{self.port}")
                else:
                    self.connected = False
                    decky.logger.error(f"Failed to connect to MQTT broker: {reason_code}")

            def on_disconnect(client, userdata, flags, reason_code, properties):
                self.connected = False
                decky.logger.info("Disconnected from MQTT broker")

            self.client.on_connect = on_connect
            self.client.on_disconnect = on_disconnect

            self.client.connect(self.host, self.port, keepalive=60)
            self.client.loop_start()

            # Wait briefly for connection
            for _ in range(10):
                if self.connected:
                    return True
                import time
                time.sleep(0.1)

            return self.connected
        except Exception as e:
            decky.logger.error(f"Error connecting to MQTT: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
            self.client = None
        self.connected = False

    def publish(self, topic: str, payload: str, retain: bool = False) -> bool:
        """Publish a message to an MQTT topic."""
        if not self.client or not self.connected:
            return False
        try:
            result = self.client.publish(topic, payload, retain=retain)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            decky.logger.error(f"Error publishing to {topic}: {e}")
            return False


class TelemetryCollector:
    """Collects telemetry data from the Steam Deck."""

    @staticmethod
    def get_battery_info() -> dict:
        """Get battery information from /sys/class/power_supply/."""
        result = {
            "percent": None,
            "charging": False,
            "time_remaining_min": None
        }

        power_supply_path = Path("/sys/class/power_supply")
        battery_path = None

        # Find battery device (usually BAT0 or BAT1)
        if power_supply_path.exists():
            for device in power_supply_path.iterdir():
                device_type_file = device / "type"
                if device_type_file.exists():
                    try:
                        device_type = device_type_file.read_text().strip()
                        if device_type == "Battery":
                            battery_path = device
                            break
                    except Exception:
                        pass

        if not battery_path:
            return result

        # Read capacity (percentage)
        try:
            capacity_file = battery_path / "capacity"
            if capacity_file.exists():
                result["percent"] = int(capacity_file.read_text().strip())
        except Exception:
            pass

        # Read charging status
        try:
            status_file = battery_path / "status"
            if status_file.exists():
                status = status_file.read_text().strip()
                result["charging"] = status in ("Charging", "Full")
        except Exception:
            pass

        # Try to calculate time remaining
        try:
            energy_now_file = battery_path / "energy_now"
            power_now_file = battery_path / "power_now"
            energy_full_file = battery_path / "energy_full"

            if energy_now_file.exists() and power_now_file.exists():
                energy_now = int(energy_now_file.read_text().strip())
                power_now = int(power_now_file.read_text().strip())

                if power_now > 0:
                    if result["charging"] and energy_full_file.exists():
                        energy_full = int(energy_full_file.read_text().strip())
                        hours = (energy_full - energy_now) / power_now
                    else:
                        hours = energy_now / power_now
                    result["time_remaining_min"] = int(hours * 60)
        except Exception:
            pass

        return result

    @staticmethod
    def get_disk_info() -> dict:
        """Get disk usage information for internal storage and SD card."""
        result = {
            "internal_free_gb": None,
            "internal_total_gb": None,
            "internal_percent_used": None,
            "sd_free_gb": None,
            "sd_total_gb": None,
            "sd_percent_used": None,
            "sd_mounted": False
        }

        # Internal storage (root filesystem)
        try:
            stat = os.statvfs("/")
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            result["internal_free_gb"] = round(free / (1024 ** 3), 2)
            result["internal_total_gb"] = round(total / (1024 ** 3), 2)
            result["internal_percent_used"] = round((used / total) * 100, 1) if total > 0 else 0
        except Exception:
            pass

        # SD card (usually mounted under /run/media/)
        sd_mount_base = Path("/run/media")
        if sd_mount_base.exists():
            try:
                for user_dir in sd_mount_base.iterdir():
                    for mount_point in user_dir.iterdir():
                        # Check if it's a different device from root
                        try:
                            stat = os.statvfs(str(mount_point))
                            total = stat.f_blocks * stat.f_frsize
                            if total > 0:
                                free = stat.f_bavail * stat.f_frsize
                                used = total - free
                                result["sd_free_gb"] = round(free / (1024 ** 3), 2)
                                result["sd_total_gb"] = round(total / (1024 ** 3), 2)
                                result["sd_percent_used"] = round((used / total) * 100, 1)
                                result["sd_mounted"] = True
                                break
                        except Exception:
                            pass
                    if result["sd_mounted"]:
                        break
            except Exception:
                pass

        return result

    @staticmethod
    def get_network_info() -> dict:
        """Get network information including IP addresses."""
        result = {
            "ip_wifi": None,
            "ip_ethernet": None,
            "ip_primary": None
        }

        try:
            # Use ip command to get addresses
            output = subprocess.check_output(
                ["ip", "-j", "addr"],
                text=True,
                timeout=5
            )
            interfaces = json.loads(output)

            for iface in interfaces:
                name = iface.get("ifname", "")
                addr_info = iface.get("addr_info", [])

                for addr in addr_info:
                    if addr.get("family") == "inet":
                        ip = addr.get("local")
                        if ip and not ip.startswith("127."):
                            if name.startswith("wl"):
                                result["ip_wifi"] = ip
                            elif name.startswith("en") or name.startswith("eth"):
                                result["ip_ethernet"] = ip

                            if not result["ip_primary"]:
                                result["ip_primary"] = ip

        except Exception as e:
            decky.logger.error(f"Error getting network info: {e}")

        return result

    @staticmethod
    def get_current_game() -> dict:
        """Get current running game information."""
        result = {
            "game_name": None,
            "app_id": None,
            "is_running": False
        }

        # Try to detect running game via Steam's local files
        try:
            # Check for running Steam apps
            steam_path = Path.home() / ".steam" / "steam"
            if not steam_path.exists():
                steam_path = Path.home() / ".local" / "share" / "Steam"

            # Try reading from steam's registry
            registry_file = steam_path / "registry.vdf"
            if registry_file.exists():
                content = registry_file.read_text()
                # Look for RunningAppID
                import re
                match = re.search(r'"RunningAppID"\s+"(\d+)"', content)
                if match:
                    app_id = int(match.group(1))
                    if app_id > 0:
                        result["app_id"] = app_id
                        result["is_running"] = True

        except Exception as e:
            decky.logger.error(f"Error getting game info: {e}")

        return result

    @staticmethod
    def get_download_info() -> dict:
        """Get Steam download progress information."""
        result = {
            "downloading": False,
            "download_progress": None,
            "download_rate_mbps": None,
            "download_app_name": None
        }

        # Download detection requires deeper Steam integration
        # This is a placeholder for when Decky APIs provide this info
        return result


class HomeAssistantDiscovery:
    """Handles MQTT Discovery for Home Assistant."""

    def __init__(self, mqtt_client: MQTTClient, hostname: str):
        self.mqtt_client = mqtt_client
        self.hostname = sanitize_identifier(hostname)
        self.device_name = f"Steam Deck ({hostname})"

    def get_device_info(self) -> dict:
        """Get the device info block for MQTT Discovery."""
        return {
            "identifiers": [f"steamdeck_{self.hostname}"],
            "name": self.device_name,
            "manufacturer": "Valve",
            "model": "Steam Deck"
        }

    def publish_discovery_config(self, component: str, object_id: str, config: dict):
        """Publish an MQTT Discovery configuration."""
        topic = f"{MQTT_DISCOVERY_PREFIX}/{component}/{self.hostname}_{object_id}/config"
        config["device"] = self.get_device_info()
        config["unique_id"] = f"steamdeck_{self.hostname}_{object_id}"
        payload = json.dumps(config)
        self.mqtt_client.publish(topic, payload, retain=True)

    def publish_state(self, sensor_type: str, payload: dict):
        """Publish state data to a topic."""
        topic = f"{STATE_TOPIC_PREFIX}/{self.hostname}/telemetry/{sensor_type}"
        self.mqtt_client.publish(topic, json.dumps(payload), retain=False)

    def register_battery_sensors(self):
        """Register battery-related sensors with Home Assistant."""
        base_topic = f"{STATE_TOPIC_PREFIX}/{self.hostname}/telemetry/battery"

        # Battery percentage
        self.publish_discovery_config("sensor", "battery_percent", {
            "name": f"{self.device_name} Battery",
            "state_topic": base_topic,
            "unit_of_measurement": "%",
            "value_template": "{{ value_json.percent }}",
            "device_class": "battery",
            "state_class": "measurement"
        })

        # Charging status
        self.publish_discovery_config("binary_sensor", "charging", {
            "name": f"{self.device_name} Charging",
            "state_topic": base_topic,
            "value_template": "{{ value_json.charging }}",
            "payload_on": "True",
            "payload_off": "False",
            "device_class": "battery_charging"
        })

        # Time remaining
        self.publish_discovery_config("sensor", "battery_time_remaining", {
            "name": f"{self.device_name} Battery Time Remaining",
            "state_topic": base_topic,
            "unit_of_measurement": "min",
            "value_template": "{{ value_json.time_remaining_min }}",
            "icon": "mdi:battery-clock"
        })

    def register_disk_sensors(self):
        """Register disk-related sensors with Home Assistant."""
        base_topic = f"{STATE_TOPIC_PREFIX}/{self.hostname}/telemetry/disk"

        # Internal disk free
        self.publish_discovery_config("sensor", "disk_free_internal", {
            "name": f"{self.device_name} Internal Storage Free",
            "state_topic": base_topic,
            "unit_of_measurement": "GB",
            "value_template": "{{ value_json.internal_free_gb }}",
            "icon": "mdi:harddisk"
        })

        # Internal disk used percentage
        self.publish_discovery_config("sensor", "disk_used_internal", {
            "name": f"{self.device_name} Internal Storage Used",
            "state_topic": base_topic,
            "unit_of_measurement": "%",
            "value_template": "{{ value_json.internal_percent_used }}",
            "icon": "mdi:harddisk"
        })

        # SD card free
        self.publish_discovery_config("sensor", "disk_free_sd", {
            "name": f"{self.device_name} SD Card Free",
            "state_topic": base_topic,
            "unit_of_measurement": "GB",
            "value_template": "{{ value_json.sd_free_gb }}",
            "icon": "mdi:sd"
        })

        # SD card mounted
        self.publish_discovery_config("binary_sensor", "sd_mounted", {
            "name": f"{self.device_name} SD Card Mounted",
            "state_topic": base_topic,
            "value_template": "{{ value_json.sd_mounted }}",
            "payload_on": "True",
            "payload_off": "False",
            "icon": "mdi:sd"
        })

    def register_network_sensors(self):
        """Register network-related sensors with Home Assistant."""
        base_topic = f"{STATE_TOPIC_PREFIX}/{self.hostname}/telemetry/network"

        # Primary IP
        self.publish_discovery_config("sensor", "ip_primary", {
            "name": f"{self.device_name} IP Address",
            "state_topic": base_topic,
            "value_template": "{{ value_json.ip_primary }}",
            "icon": "mdi:ip-network"
        })

        # WiFi IP
        self.publish_discovery_config("sensor", "ip_wifi", {
            "name": f"{self.device_name} WiFi IP",
            "state_topic": base_topic,
            "value_template": "{{ value_json.ip_wifi }}",
            "icon": "mdi:wifi"
        })

        # Ethernet IP
        self.publish_discovery_config("sensor", "ip_ethernet", {
            "name": f"{self.device_name} Ethernet IP",
            "state_topic": base_topic,
            "value_template": "{{ value_json.ip_ethernet }}",
            "icon": "mdi:ethernet"
        })

    def register_game_sensors(self):
        """Register game-related sensors with Home Assistant."""
        base_topic = f"{STATE_TOPIC_PREFIX}/{self.hostname}/telemetry/game"

        # Current game name
        self.publish_discovery_config("sensor", "current_game", {
            "name": f"{self.device_name} Current Game",
            "state_topic": base_topic,
            "value_template": "{{ value_json.game_name }}",
            "icon": "mdi:gamepad-variant"
        })

        # Current app ID
        self.publish_discovery_config("sensor", "current_appid", {
            "name": f"{self.device_name} Current App ID",
            "state_topic": base_topic,
            "value_template": "{{ value_json.app_id }}",
            "icon": "mdi:identifier"
        })

        # Game running
        self.publish_discovery_config("binary_sensor", "game_running", {
            "name": f"{self.device_name} Game Running",
            "state_topic": base_topic,
            "value_template": "{{ value_json.is_running }}",
            "payload_on": "True",
            "payload_off": "False",
            "icon": "mdi:gamepad-variant"
        })

    def register_download_sensors(self):
        """Register download-related sensors with Home Assistant."""
        base_topic = f"{STATE_TOPIC_PREFIX}/{self.hostname}/telemetry/download"

        # Downloading
        self.publish_discovery_config("binary_sensor", "downloading", {
            "name": f"{self.device_name} Downloading",
            "state_topic": base_topic,
            "value_template": "{{ value_json.downloading }}",
            "payload_on": "True",
            "payload_off": "False",
            "icon": "mdi:download"
        })

        # Download progress
        self.publish_discovery_config("sensor", "download_progress", {
            "name": f"{self.device_name} Download Progress",
            "state_topic": base_topic,
            "unit_of_measurement": "%",
            "value_template": "{{ value_json.download_progress }}",
            "icon": "mdi:download"
        })

        # Download rate
        self.publish_discovery_config("sensor", "download_rate", {
            "name": f"{self.device_name} Download Rate",
            "state_topic": base_topic,
            "unit_of_measurement": "Mbps",
            "value_template": "{{ value_json.download_rate_mbps }}",
            "icon": "mdi:speedometer"
        })


class Plugin:
    """Main plugin class for Home Assistant MQTT integration."""

    def __init__(self):
        self.loop = None
        self.mqtt_client = MQTTClient()
        self.discovery = None
        self.telemetry_task = None
        self.settings = self._get_default_settings()
        self.running = False

    def _get_default_settings(self) -> dict:
        """Get default settings."""
        return {
            "mqtt_host": "",
            "mqtt_port": 1883,
            "mqtt_username": "",
            "mqtt_password": "",
            "hostname": get_default_hostname(),
            "publish_interval": 30,
            "enabled_sensors": {
                "battery": True,
                "disk": True,
                "network": True,
                "game": True,
                "download": True
            }
        }

    def _get_settings_path(self) -> Path:
        """Get the path to the settings file."""
        return Path(decky.DECKY_PLUGIN_SETTINGS_DIR) / SETTINGS_FILE

    def _load_settings(self):
        """Load settings from file."""
        settings_path = self._get_settings_path()
        if settings_path.exists():
            try:
                with open(settings_path, "r") as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    for key, value in self._get_default_settings().items():
                        if key not in loaded:
                            loaded[key] = value
                        elif key == "enabled_sensors" and isinstance(value, dict):
                            for sensor_key, sensor_value in value.items():
                                if sensor_key not in loaded[key]:
                                    loaded[key][sensor_key] = sensor_value
                    self.settings = loaded
                    decky.logger.info("Settings loaded successfully")
            except Exception as e:
                decky.logger.error(f"Error loading settings: {e}")

    def _save_settings(self):
        """Save settings to file."""
        settings_path = self._get_settings_path()
        try:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(settings_path, "w") as f:
                json.dump(self.settings, f, indent=2)
            decky.logger.info("Settings saved successfully")
        except Exception as e:
            decky.logger.error(f"Error saving settings: {e}")

    async def get_settings(self) -> dict:
        """Get current settings (callable from frontend)."""
        # Return settings without password for security
        safe_settings = dict(self.settings)
        safe_settings["mqtt_password"] = "****" if self.settings.get("mqtt_password") else ""
        safe_settings["connected"] = self.mqtt_client.connected
        return safe_settings

    async def save_settings(self, settings: dict) -> bool:
        """Save settings (callable from frontend)."""
        try:
            # Don't overwrite password if it's masked
            if settings.get("mqtt_password") == "****":
                settings["mqtt_password"] = self.settings.get("mqtt_password", "")

            self.settings = settings
            self._save_settings()

            # Reconnect if settings changed
            if self.mqtt_client.connected:
                await self.disconnect_mqtt()
            if self.settings.get("mqtt_host"):
                await self.connect_mqtt()

            return True
        except Exception as e:
            decky.logger.error(f"Error saving settings: {e}")
            return False

    async def connect_mqtt(self) -> dict:
        """Connect to MQTT broker (callable from frontend)."""
        try:
            self.mqtt_client.configure(
                self.settings.get("mqtt_host", ""),
                self.settings.get("mqtt_port", 1883),
                self.settings.get("mqtt_username", ""),
                self.settings.get("mqtt_password", "")
            )

            success = self.mqtt_client.connect()

            if success:
                # Initialize discovery and register sensors
                self.discovery = HomeAssistantDiscovery(
                    self.mqtt_client,
                    self.settings.get("hostname", get_default_hostname())
                )
                await self._register_sensors()
                decky.logger.info("MQTT connected and sensors registered")

            return {"success": success, "connected": self.mqtt_client.connected}
        except Exception as e:
            decky.logger.error(f"Error connecting to MQTT: {e}")
            return {"success": False, "error": str(e), "connected": False}

    async def disconnect_mqtt(self) -> dict:
        """Disconnect from MQTT broker (callable from frontend)."""
        try:
            self.mqtt_client.disconnect()
            return {"success": True, "connected": False}
        except Exception as e:
            decky.logger.error(f"Error disconnecting from MQTT: {e}")
            return {"success": False, "error": str(e)}

    async def test_connection(self) -> dict:
        """Test MQTT connection (callable from frontend)."""
        try:
            test_client = MQTTClient()
            test_client.configure(
                self.settings.get("mqtt_host", ""),
                self.settings.get("mqtt_port", 1883),
                self.settings.get("mqtt_username", ""),
                self.settings.get("mqtt_password", "")
            )
            success = test_client.connect()
            test_client.disconnect()
            return {"success": success}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_connection_status(self) -> dict:
        """Get current connection status (callable from frontend)."""
        return {"connected": self.mqtt_client.connected}

    async def _register_sensors(self):
        """Register all enabled sensors with Home Assistant."""
        if not self.discovery:
            return

        enabled = self.settings.get("enabled_sensors", {})

        if enabled.get("battery", True):
            self.discovery.register_battery_sensors()

        if enabled.get("disk", True):
            self.discovery.register_disk_sensors()

        if enabled.get("network", True):
            self.discovery.register_network_sensors()

        if enabled.get("game", True):
            self.discovery.register_game_sensors()

        if enabled.get("download", True):
            self.discovery.register_download_sensors()

    async def _publish_telemetry(self):
        """Publish telemetry data to MQTT."""
        if not self.mqtt_client.connected or not self.discovery:
            return

        enabled = self.settings.get("enabled_sensors", {})

        if enabled.get("battery", True):
            battery_info = TelemetryCollector.get_battery_info()
            self.discovery.publish_state("battery", battery_info)

        if enabled.get("disk", True):
            disk_info = TelemetryCollector.get_disk_info()
            self.discovery.publish_state("disk", disk_info)

        if enabled.get("network", True):
            network_info = TelemetryCollector.get_network_info()
            self.discovery.publish_state("network", network_info)

        if enabled.get("game", True):
            game_info = TelemetryCollector.get_current_game()
            self.discovery.publish_state("game", game_info)

        if enabled.get("download", True):
            download_info = TelemetryCollector.get_download_info()
            self.discovery.publish_state("download", download_info)

    async def _telemetry_loop(self):
        """Main telemetry publishing loop."""
        while self.running:
            try:
                if self.mqtt_client.connected:
                    await self._publish_telemetry()
            except Exception as e:
                decky.logger.error(f"Error in telemetry loop: {e}")

            interval = self.settings.get("publish_interval", 30)
            await asyncio.sleep(interval)

    async def publish_now(self) -> dict:
        """Manually trigger telemetry publish (callable from frontend)."""
        try:
            if not self.mqtt_client.connected:
                return {"success": False, "error": "Not connected to MQTT"}
            await self._publish_telemetry()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_telemetry(self) -> dict:
        """Get current telemetry data (callable from frontend)."""
        return {
            "battery": TelemetryCollector.get_battery_info(),
            "disk": TelemetryCollector.get_disk_info(),
            "network": TelemetryCollector.get_network_info(),
            "game": TelemetryCollector.get_current_game(),
            "download": TelemetryCollector.get_download_info()
        }

    async def _main(self):
        """Main plugin entry point."""
        self.loop = asyncio.get_event_loop()
        self.running = True

        decky.logger.info("Home Assistant MQTT Plugin starting...")

        # Load settings
        self._load_settings()

        # Auto-connect if configured
        if self.settings.get("mqtt_host"):
            await self.connect_mqtt()

        # Start telemetry loop
        self.telemetry_task = self.loop.create_task(self._telemetry_loop())

        decky.logger.info("Home Assistant MQTT Plugin started")

    async def _unload(self):
        """Called when plugin is being unloaded."""
        decky.logger.info("Home Assistant MQTT Plugin unloading...")
        self.running = False

        if self.telemetry_task:
            self.telemetry_task.cancel()
            try:
                await self.telemetry_task
            except asyncio.CancelledError:
                pass

        self.mqtt_client.disconnect()
        decky.logger.info("Home Assistant MQTT Plugin unloaded")

    async def _uninstall(self):
        """Called when plugin is being uninstalled."""
        decky.logger.info("Home Assistant MQTT Plugin uninstalling...")
        # Clean up settings file if desired
        # settings_path = self._get_settings_path()
        # if settings_path.exists():
        #     settings_path.unlink()

    async def _migration(self):
        """Migrations that should be performed before entering `_main()`."""
        decky.logger.info("Running migrations...")
        # No migrations needed for fresh install
