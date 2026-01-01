# Home Assistant MQTT Plugin for Steam Deck

[![Chat](https://img.shields.io/badge/chat-on%20discord-7289da.svg)](https://deckbrew.xyz/discord)

A [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin that publishes Steam Deck telemetry to [Home Assistant](https://www.home-assistant.io/) via MQTT Discovery.

## Features

- **Battery Monitoring**: Battery percentage, charging status, and time remaining
- **Disk Usage**: Internal storage and SD card space monitoring
- **Network Information**: WiFi and Ethernet IP addresses
- **Game Detection**: Current running game/app information
- **Download Status**: Steam download progress and rate
- **MQTT Discovery**: Automatic device and sensor registration in Home Assistant
- **Configurable**: Enable/disable individual sensors, customize hostname, adjust publish interval

## Sensors

The plugin creates the following entities in Home Assistant:

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.steamdeck_<hostname>_battery_percent` | sensor | Battery percentage (0-100%) |
| `binary_sensor.steamdeck_<hostname>_charging` | binary_sensor | Charging status |
| `sensor.steamdeck_<hostname>_battery_time_remaining` | sensor | Estimated time remaining (minutes) |
| `sensor.steamdeck_<hostname>_disk_free_internal` | sensor | Internal storage free space (GB) |
| `sensor.steamdeck_<hostname>_disk_used_internal` | sensor | Internal storage usage (%) |
| `sensor.steamdeck_<hostname>_disk_free_sd` | sensor | SD card free space (GB) |
| `binary_sensor.steamdeck_<hostname>_sd_mounted` | binary_sensor | SD card mounted status |
| `sensor.steamdeck_<hostname>_ip_primary` | sensor | Primary IP address |
| `sensor.steamdeck_<hostname>_ip_wifi` | sensor | WiFi IP address |
| `sensor.steamdeck_<hostname>_ip_ethernet` | sensor | Ethernet IP address |
| `sensor.steamdeck_<hostname>_current_game` | sensor | Current game name |
| `sensor.steamdeck_<hostname>_current_appid` | sensor | Current Steam App ID |
| `binary_sensor.steamdeck_<hostname>_game_running` | binary_sensor | Game running status |
| `binary_sensor.steamdeck_<hostname>_downloading` | binary_sensor | Download in progress |
| `sensor.steamdeck_<hostname>_download_progress` | sensor | Download progress (%) |
| `sensor.steamdeck_<hostname>_download_rate` | sensor | Download speed (Mbps) |

All sensors are grouped under a single "Steam Deck" device in Home Assistant.

## Prerequisites

### Home Assistant MQTT Setup

1. **Install an MQTT Broker** (if you don't have one)

   The easiest option is to install the [Mosquitto broker add-on](https://github.com/home-assistant/addons/tree/master/mosquitto):
   
   - Go to **Settings** → **Add-ons** → **Add-on Store**
   - Search for "Mosquitto broker"
   - Click **Install**
   - After installation, go to the add-on's **Configuration** tab
   - Create a user/password or configure anonymous access
   - Start the add-on

2. **Enable MQTT Integration**

   - Go to **Settings** → **Devices & Services** → **Integrations**
   - Click **+ Add Integration**
   - Search for "MQTT"
   - Select **MQTT**
   - If using the Mosquitto add-on, Home Assistant should auto-discover it
   - Otherwise, enter your broker's host, port, and credentials

3. **Enable MQTT Discovery** (usually enabled by default)

   In your Home Assistant `configuration.yaml`, ensure MQTT discovery is enabled:
   
   ```yaml
   mqtt:
     discovery: true
     discovery_prefix: homeassistant
   ```
   
   Restart Home Assistant if you made changes.

### Steam Deck Setup

1. **Install Decky Loader**
   
   Follow the instructions at [decky-loader](https://github.com/SteamDeckHomebrew/decky-loader) to install Decky Loader on your Steam Deck.

2. **Install this Plugin**
   
   - Open the Decky menu (press the **...** button on your Steam Deck)
   - Go to the **Plugin Store**
   - Search for "Home Assistant MQTT"
   - Click **Install**

## Configuration

1. Open the Decky menu on your Steam Deck
2. Click on **Home Assistant MQTT**
3. Configure the following settings:

### MQTT Broker Settings

| Setting | Description | Example |
|---------|-------------|---------|
| **Host** | MQTT broker hostname or IP | `192.168.1.100` or `homeassistant.local` |
| **Port** | MQTT broker port (default: 1883) | `1883` |
| **Username** | MQTT username (if required) | `mqtt_user` |
| **Password** | MQTT password (if required) | `your_password` |

### Device Settings

| Setting | Description | Default |
|---------|-------------|---------|
| **Hostname** | Device identifier used in Home Assistant entity names | Steam Deck's hostname |

### Sensor Toggles

Enable or disable individual sensor categories:
- **Battery**: Battery percentage, charging status, time remaining
- **Disk**: Internal and SD card storage usage
- **Network**: IP addresses
- **Game**: Current game/app information
- **Downloads**: Steam download progress

### Advanced Settings

| Setting | Description | Default |
|---------|-------------|---------|
| **Publish Interval** | How often to send telemetry (seconds) | 30 |

## Usage

1. **Save Settings**: After configuring, click **Save** to persist your settings
2. **Test Connection**: Click **Test** to verify MQTT broker connectivity
3. **Connect**: Click **Connect** to establish the MQTT connection
4. **Publish Now**: Manually trigger a telemetry publish
5. **View Current Telemetry**: See the current sensor values

The plugin will automatically:
- Connect to MQTT on startup (if configured)
- Register sensors with Home Assistant via MQTT Discovery
- Publish telemetry at the configured interval

## MQTT Topics

The plugin uses the following topic structure:

### Discovery Topics (retained)
```
homeassistant/<component>/<hostname>_<sensor>/config
```

### State Topics
```
steamdeck/<hostname>/telemetry/battery
steamdeck/<hostname>/telemetry/disk
steamdeck/<hostname>/telemetry/network
steamdeck/<hostname>/telemetry/game
steamdeck/<hostname>/telemetry/download
```

### Example Payloads

**Battery State:**
```json
{
  "percent": 73,
  "charging": true,
  "time_remaining_min": 95
}
```

**Disk State:**
```json
{
  "internal_free_gb": 45.2,
  "internal_total_gb": 64.0,
  "internal_percent_used": 29.4,
  "sd_free_gb": 128.5,
  "sd_total_gb": 256.0,
  "sd_percent_used": 49.8,
  "sd_mounted": true
}
```

## Home Assistant Automations

Example automation to notify when battery is low:

```yaml
automation:
  - alias: "Steam Deck Low Battery Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.steamdeck_steamdeck_battery_percent
        below: 20
    condition:
      - condition: state
        entity_id: binary_sensor.steamdeck_steamdeck_charging
        state: "off"
    action:
      - service: notify.mobile_app
        data:
          title: "Steam Deck Battery Low"
          message: "Battery at {{ states('sensor.steamdeck_steamdeck_battery_percent') }}%"
```

Example to turn on a smart plug when Steam Deck is charging:

```yaml
automation:
  - alias: "Steam Deck Charging Indicator"
    trigger:
      - platform: state
        entity_id: binary_sensor.steamdeck_steamdeck_charging
        to: "on"
    action:
      - service: light.turn_on
        target:
          entity_id: light.charging_indicator
```

## Troubleshooting

### Plugin won't connect to MQTT
- Verify your MQTT broker is running and accessible
- Check the host/port settings
- Ensure username/password are correct
- Check your network connection

### Sensors not appearing in Home Assistant
- Verify MQTT Discovery is enabled in Home Assistant
- Check that the MQTT integration is properly configured
- Try disconnecting and reconnecting from the plugin
- Check Home Assistant logs for MQTT-related errors

### Battery time remaining shows "unavailable"
- This sensor depends on power draw data which may not always be available
- It's normal for this to be unavailable when plugged in or when the system can't calculate the estimate

### SD card not detected
- The SD card must be mounted at `/run/media/...`
- Try removing and reinserting the SD card

## Development

### Dependencies

- Node.js v16.14+
- pnpm v9

### Building

```bash
# Install dependencies
pnpm i

# Build the frontend
pnpm run build
```

### Python Backend

The plugin uses the [paho-mqtt](https://pypi.org/project/paho-mqtt/) library for MQTT communication. The library is included in `py_modules/`.

## License

BSD-3-Clause - See [LICENSE](LICENSE) for details.

## Credits

- [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) - Plugin framework
- [Home Assistant](https://www.home-assistant.io/) - Home automation platform
- [paho-mqtt](https://pypi.org/project/paho-mqtt/) - MQTT client library
