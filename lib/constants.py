"""
Constants used throughout the Home Assistant MQTT plugin.
"""

# Settings
SETTINGS_FILE = "settings.json"

# MQTT Configuration
MQTT_DISCOVERY_PREFIX = "homeassistant"
STATE_TOPIC_PREFIX = "steamdeck"

# Telemetry constants
MIN_SD_CARD_SIZE_BYTES = 1024 ** 3  # 1 GB minimum to be considered an SD card
DOWNLOAD_COMPLETION_DELAY_SECONDS = 1  # Brief delay before clearing completed download state
