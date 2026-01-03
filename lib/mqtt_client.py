"""
MQTT Client module for Home Assistant integration.
Handles MQTT connection and publishing.
"""

import time
import decky

# Import paho-mqtt
import os
import sys
sys.path.insert(0, os.path.join(decky.DECKY_PLUGIN_DIR, "py_modules"))
import paho.mqtt.client as mqtt

from .constants import STATE_TOPIC_PREFIX
from .utils import sanitize_identifier


class MQTTClient:
    """Handles MQTT connection and publishing."""

    def __init__(self):
        self.client = None
        self.connected = False
        self.host = ""
        self.port = 1883
        self.username = ""
        self.password = ""
        self.hostname = ""
        self.status_topic = ""

    def configure(self, host: str, port: int, username: str, password: str, hostname: str = ""):
        """Configure MQTT connection parameters."""
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.hostname = sanitize_identifier(hostname) if hostname else ""
        if self.hostname:
            self.status_topic = f"{STATE_TOPIC_PREFIX}/{self.hostname}/status"

    def connect(self) -> bool:
        """Connect to the MQTT broker."""
        try:
            if self.client:
                self.disconnect()

            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)

            # Set Last Will message - published when client disconnects unexpectedly
            if self.status_topic:
                self.client.will_set(
                    topic=self.status_topic,
                    payload="offline",
                    qos=1,
                    retain=True
                )
                decky.logger.info(f"Last Will message set for topic: {self.status_topic}")

            def on_connect(client, userdata, flags, reason_code, properties):
                if reason_code == 0:
                    self.connected = True
                    decky.logger.info(f"Connected to MQTT broker at {self.host}:{self.port}")
                    # Publish initial online status with QoS 1 for reliability
                    if self.status_topic:
                        result = self.publish(self.status_topic, "online", retain=True, qos=1)
                        if result:
                            decky.logger.info(f"Published initial online status to {self.status_topic}")
                        else:
                            decky.logger.warning(f"Failed to publish initial online status to {self.status_topic}")
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
                # Publish offline status before clean disconnect with QoS 1 for reliability
                if self.connected and self.status_topic:
                    result = self.publish(self.status_topic, "offline", retain=True, qos=1)
                    if result:
                        decky.logger.info(f"Published offline status to {self.status_topic}")
                        # Brief wait to ensure message is sent before disconnecting
                        time.sleep(0.1)
                    else:
                        decky.logger.warning(f"Failed to publish offline status to {self.status_topic}")
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
            self.client = None
        self.connected = False

    def publish(self, topic: str, payload: str, retain: bool = False, qos: int = 0) -> bool:
        """Publish a message to an MQTT topic."""
        if not self.client or not self.connected:
            return False
        try:
            result = self.client.publish(topic, payload, qos=qos, retain=retain)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            decky.logger.error(f"Error publishing to {topic}: {e}")
            return False

    def publish_heartbeat(self) -> bool:
        """Publish a heartbeat message to keep the status online."""
        if self.status_topic and self.connected:
            # Use QoS 1 for heartbeat to ensure delivery of status updates
            return self.publish(self.status_topic, "online", retain=True, qos=1)
        return False
