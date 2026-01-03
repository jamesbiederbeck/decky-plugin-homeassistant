"""
Home Assistant MQTT Publisher for Steam Deck
Publishes telemetry data (battery, disk, game, network) to Home Assistant via MQTT Discovery.

Features:
- MQTT Last Will message to automatically mark Steam Deck as offline when disconnected
- Heartbeat mechanism to keep status as online during normal operation
- Automatic sensor registration with Home Assistant Discovery
- Event-driven telemetry for game and download state
"""

import json
import asyncio
from pathlib import Path

import decky

# Import local lib modules
from lib import (
    SETTINGS_FILE,
    DOWNLOAD_COMPLETION_DELAY_SECONDS,
    get_default_hostname,
    MQTTClient,
    TelemetryCollector,
    HomeAssistantDiscovery,
)


class Plugin:
    """Main plugin class for Home Assistant MQTT integration."""

    def __init__(self):
        self.loop = None
        self.mqtt_client = MQTTClient()
        self.discovery = None
        self.telemetry_task = None
        self.settings = self._get_default_settings()
        self.running = False
        
        # Event-driven state
        self.game_state = {
            "is_running": False,
            "app_id": None,
            "app_name": None
        }
        self.download_state = {
            "downloading": False,
            "progress": None,
            "rate_mbps": None,
            "app_id": None
        }

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
            hostname = self.settings.get("hostname", get_default_hostname())
            self.mqtt_client.configure(
                self.settings.get("mqtt_host", ""),
                self.settings.get("mqtt_port", 1883),
                self.settings.get("mqtt_username", ""),
                self.settings.get("mqtt_password", ""),
                hostname
            )

            success = self.mqtt_client.connect()

            if success:
                # Initialize discovery and register sensors
                self.discovery = HomeAssistantDiscovery(
                    self.mqtt_client,
                    hostname
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
            hostname = self.settings.get("hostname", get_default_hostname())
            test_client.configure(
                self.settings.get("mqtt_host", ""),
                self.settings.get("mqtt_port", 1883),
                self.settings.get("mqtt_username", ""),
                self.settings.get("mqtt_password", ""),
                hostname
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

        # Always register status sensor
        self.discovery.register_status_sensor()

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

        # Publish heartbeat to keep status online
        self.mqtt_client.publish_heartbeat()

        enabled = self.settings.get("enabled_sensors", {})

        # Battery, disk, and network are still polled (hardware telemetry)
        # Use retain=True for these persistent hardware states
        if enabled.get("battery", True):
            battery_info = TelemetryCollector.get_battery_info()
            self.discovery.publish_state("battery", battery_info, retain=True)

        if enabled.get("disk", True):
            disk_info = TelemetryCollector.get_disk_info()
            self.discovery.publish_state("disk", disk_info, retain=True)

        if enabled.get("network", True):
            network_info = TelemetryCollector.get_network_info()
            self.discovery.publish_state("network", network_info, retain=True)

        # Game and download state are now event-driven, not polled
        # They are published via _publish_game_state() and _publish_download_state()
        # when events are received from the frontend

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
            "game": self._get_game_state(),
            "download": self._get_download_state()
        }

    async def ingest_event(self, event: dict):
        """
        Ingest a system event from the frontend (callable from frontend).
        
        This is the main entry point for event-driven telemetry.
        Events are routed to appropriate handlers based on type.
        """
        try:
            event_type = event.get("type")
            timestamp = event.get("timestamp")
            
            decky.logger.debug(f"Received event: {event_type} at {timestamp}")
            
            # Route event to appropriate handler
            if event_type == "game_started":
                await self._handle_game_started(event)
            elif event_type == "game_stopped":
                await self._handle_game_stopped(event)
            elif event_type == "download_started":
                await self._handle_download_started(event)
            elif event_type == "download_progress":
                await self._handle_download_progress(event)
            elif event_type == "download_completed":
                await self._handle_download_completed(event)
            elif event_type == "download_stopped":
                await self._handle_download_stopped(event)
            elif event_type == "system_suspending":
                await self._handle_system_suspending(event)
            elif event_type == "system_resuming":
                await self._handle_system_resuming(event)
            elif event_type == "system_shutting_down":
                await self._handle_system_shutting_down(event)
            else:
                decky.logger.warning(f"Unknown event type: {event_type}")
                
        except Exception as e:
            decky.logger.error(f"Error processing event: {e}")

    def _get_game_state(self) -> dict:
        """Get current game state from event-driven data."""
        return {
            "game_name": self.game_state.get("app_name"),
            "app_id": self.game_state.get("app_id"),
            "is_running": self.game_state.get("is_running", False)
        }

    def _get_download_state(self) -> dict:
        """Get current download state from event-driven data."""
        return {
            "downloading": self.download_state.get("downloading", False),
            "download_progress": self.download_state.get("progress"),
            "download_rate_mbps": self.download_state.get("rate_mbps"),
            "download_app_name": None  # App name lookup could be added later
        }

    async def _handle_game_started(self, event: dict):
        """Handle game started event."""
        app_id = event.get("app_id")
        
        # Detect unexpected event sequence
        if self.game_state.get("is_running"):
            decky.logger.warning(f"Received game_started for app_id={app_id} but game is already running (current={self.game_state.get('app_id')})")
        
        decky.logger.info(f"Game started: app_id={app_id}")
        
        # Update state
        self.game_state["is_running"] = True
        self.game_state["app_id"] = app_id
        self.game_state["app_name"] = None  # Could lookup app name from Steam API
        
        # Publish to MQTT
        await self._publish_game_state()

    async def _handle_game_stopped(self, event: dict):
        """Handle game stopped event."""
        app_id = event.get("app_id")
        
        # Detect unexpected event sequence
        if not self.game_state.get("is_running"):
            decky.logger.warning(f"Received game_stopped for app_id={app_id} but no game is running")
        
        decky.logger.info(f"Game stopped: app_id={app_id}")
        
        # Update state
        self.game_state["is_running"] = False
        self.game_state["app_id"] = None
        self.game_state["app_name"] = None
        
        # Publish to MQTT
        await self._publish_game_state()

    async def _handle_download_started(self, event: dict):
        """Handle download started event."""
        app_id = event.get("app_id")
        
        # Detect unexpected event sequence
        if self.download_state.get("downloading"):
            decky.logger.warning(f"Received download_started for app_id={app_id} but download is already active")
        
        decky.logger.info(f"Download started: app_id={app_id}")
        
        # Update state
        self.download_state["downloading"] = True
        self.download_state["app_id"] = app_id
        self.download_state["progress"] = 0
        self.download_state["rate_mbps"] = 0
        
        # Publish to MQTT
        await self._publish_download_state()

    async def _handle_download_progress(self, event: dict):
        """Handle download progress event."""
        progress = event.get("progress")
        rate = event.get("rate")
        
        # Update state
        self.download_state["downloading"] = True
        self.download_state["progress"] = progress
        self.download_state["rate_mbps"] = rate
        
        # Publish to MQTT
        await self._publish_download_state()

    async def _handle_download_completed(self, event: dict):
        """Handle download completed event."""
        app_id = event.get("app_id")
        decky.logger.info(f"Download completed: app_id={app_id}")
        
        # Update state
        self.download_state["downloading"] = False
        self.download_state["progress"] = 100
        self.download_state["rate_mbps"] = 0
        
        # Publish to MQTT
        await self._publish_download_state()
        
        # Clear state after a brief moment (allow cancellation)
        try:
            await asyncio.sleep(DOWNLOAD_COMPLETION_DELAY_SECONDS)
            self.download_state["progress"] = None
            self.download_state["rate_mbps"] = None
            self.download_state["app_id"] = None
        except asyncio.CancelledError:
            # Allow graceful cancellation during shutdown
            pass

    async def _handle_download_stopped(self, event: dict):
        """Handle download stopped event."""
        decky.logger.info("Download stopped")
        
        # Update state
        self.download_state["downloading"] = False
        self.download_state["progress"] = None
        self.download_state["rate_mbps"] = None
        self.download_state["app_id"] = None
        
        # Publish to MQTT
        await self._publish_download_state()

    async def _handle_system_suspending(self, event: dict):
        """Handle system suspending event."""
        decky.logger.info("System suspending - finalizing state")
        
        # Finalize any active game or download state
        if self.game_state.get("is_running"):
            self.game_state["is_running"] = False
            await self._publish_game_state()
        
        if self.download_state.get("downloading"):
            self.download_state["downloading"] = False
            await self._publish_download_state()

    async def _handle_system_resuming(self, event: dict):
        """Handle system resuming event."""
        decky.logger.info("System resuming - resetting transient state")
        
        # Reset transient state (game and download state will be re-established by events)
        # Just ensure we're in a clean state
        pass

    async def _handle_system_shutting_down(self, event: dict):
        """Handle system shutting down event."""
        decky.logger.info("System shutting down - flushing state")
        
        # Flush state and mark sensors unavailable
        self.game_state["is_running"] = False
        self.game_state["app_id"] = None
        self.download_state["downloading"] = False
        
        await self._publish_game_state()
        await self._publish_download_state()

    async def _publish_game_state(self):
        """Publish game state to MQTT."""
        if not self.mqtt_client.connected or not self.discovery:
            return
            
        if not self.settings.get("enabled_sensors", {}).get("game", True):
            return
            
        game_info = self._get_game_state()
        # Don't retain game state - it's transient and event-driven
        self.discovery.publish_state("game", game_info, retain=False)
        decky.logger.debug(f"Published game state: {game_info}")

    async def _publish_download_state(self):
        """Publish download state to MQTT."""
        if not self.mqtt_client.connected or not self.discovery:
            return
            
        if not self.settings.get("enabled_sensors", {}).get("download", True):
            return
            
        download_info = self._get_download_state()
        # Don't retain download state - it's transient and event-driven
        self.discovery.publish_state("download", download_info, retain=False)
        decky.logger.debug(f"Published download state: {download_info}")

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
