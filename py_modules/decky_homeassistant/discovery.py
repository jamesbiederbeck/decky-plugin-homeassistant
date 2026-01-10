"""
Home Assistant MQTT Discovery module.
Handles MQTT Discovery for Home Assistant sensor registration.
"""

import json
import decky

from .constants import MQTT_DISCOVERY_PREFIX, STATE_TOPIC_PREFIX
from .utils import sanitize_identifier


class HomeAssistantDiscovery:
    """Handles MQTT Discovery for Home Assistant."""

    def __init__(self, mqtt_client, hostname: str):
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
        
        # Add availability topic - sensors are available when plugin is connected
        status_topic = self.mqtt_client.status_topic
        if status_topic:
            config["availability_topic"] = status_topic
            config["payload_available"] = "online"
            config["payload_not_available"] = "offline"
        
        payload = json.dumps(config)
        self.mqtt_client.publish(topic, payload, retain=True)

    def publish_state(self, sensor_type: str, payload: dict, retain: bool = False):
        """
        Publish state data to a topic.
        
        Args:
            sensor_type: Type of sensor (battery, disk, network, game, download)
            payload: State data as dictionary
            retain: Whether to retain the message (use True for persistent state like battery/disk)
        """
        topic = f"{STATE_TOPIC_PREFIX}/{self.hostname}/telemetry/{sensor_type}"
        self.mqtt_client.publish(topic, json.dumps(payload), retain=retain)

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

    def register_status_sensor(self):
        """Register connection status sensor with Home Assistant."""
        # Use the status topic from mqtt_client to maintain consistency
        status_topic = self.mqtt_client.status_topic
        if not status_topic:
            decky.logger.warning("Status topic not configured, skipping status sensor registration")
            return

        # Connection status
        self.publish_discovery_config("binary_sensor", "status", {
            "name": f"{self.device_name} Status",
            "state_topic": status_topic,
            "payload_on": "online",
            "payload_off": "offline",
            "device_class": "connectivity",
            "icon": "mdi:steam"
        })
