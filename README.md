# Home Assistant MQTT Plugin for Steam Deck

**Under development. Not actually in decky store, but you can download and side load it from the releases tab.**

[![Release](https://img.shields.io/github/v/release/jamesbiederbeck/decky-plugin-homeassistant?style=flat-square](

[![Chat](https://img.shields.io/badge/chat-on%20discord-7289da.svg)](https://deckbrew.xyz/discord)

A [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin that publishes Steam Deck telemetry to [Home Assistant](https://www.home-assistant.io/) via MQTT Discovery.

## Features

- **Event-Driven Telemetry**: Game and download sensors update immediately via Steam runtime events
- **Battery Monitoring**: Battery percentage, charging status, and time remaining
- **Disk Usage**: Internal storage (from /home mount) and SD card space monitoring
- **Network Information**: WiFi and Ethernet IP addresses distinguished by interface
- **Game Detection**: Real-time game start/stop detection with instant sensor updates
- **Download Status**: Real-time Steam download progress and rate tracking
- **MQTT Discovery**: Automatic device and sensor registration in Home Assistant
- **Availability Tracking**: Sensors automatically marked unavailable when plugin disconnects
- **Configurable**: Enable/disable individual sensors, customize hostname, adjust publish interval

## Architecture

The plugin now uses an **event-driven architecture** for game and download telemetry:

- **Frontend**: Subscribes to Steam runtime events (game lifecycle, downloads, system suspend/resume)
- **Backend**: Processes events and maintains authoritative state
- **MQTT**: Publishes state changes immediately when events occur

This eliminates polling delays and ensures Home Assistant sensors update instantly when:
- A game starts or stops
- A download begins, progresses, or completes
- The system suspends or resumes

Hardware telemetry (battery, disk, network) is still polled at the configured interval since it represents physical state that changes gradually.

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

Skip Steps 1-3 if you already know what you're doing with MQTT and Home Assistant, and alreay use it. 

1. **Install an MQTT Broker** (if you don't have one)
   
   This will pass messages between Steam Deck and your Home Assistant instance in a low-maintenance, future proof way. 

   The easiest option is to install the Mosquitto broker add-on, but that may not be an option if you don't have Home Assistant running in the [HA OS image](https://www.home-assistant.io/blog/2025/05/22/deprecating-core-and-supervised-installation-methods-and-32-bit-systems#how-to-migrate). [Read about the Mosquitto addon here](https://github.com/home-assistant/addons/tree/master/mosquitto) or jump to your Home Assistant instance and install it easily here: https://my.home-assistant.io/redirect/config_flow_start/?domain=mqtt
   - Go to **Settings** → **Add-ons** → **Add-on Store**
   - Search for "Mosquitto broker"
   - Click **Install**
   - After installation, go to the add-on's **Configuration** tab
   - Create a user/password or configure anonymous access
   - Start the add-on
  
   You can also do something like this if you aren't using a supervised install: https://pimylifeup.com/mosquitto-mqtt-docker/

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

4. **Make a login for your steamdeck in the Mosquitto addon**

   Configure your MQTT broker, as appropriate, and create a username and password (note them) and add them to the configuration in the plugin later. Client certs are not currently supported. If you're using the mosquitto add on from HACS, you can use this link to jump to its page in your Home Assistant instance.

   https://my.home-assistant.io/redirect/supervisor_addon/?addon=core_mosquitto

    then click over to the configuration tab.

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
4. **Publish Now**: Manually trigger a telemetry publish (hardware sensors only)
5. **View Current Telemetry**: See the current sensor values

The plugin will automatically:
- Connect to MQTT on startup (if configured)
- Register sensors with Home Assistant via MQTT Discovery
- Subscribe to Steam runtime events for instant game and download updates
- Publish hardware telemetry (battery, disk, network) at the configured interval
- Publish game and download state immediately when events occur

### Event-Driven Sensors

The following sensors update **immediately** when events occur (no polling delay):
- **Game Running**: Updates when a game starts or stops
- **Current App ID**: Updates when game changes
- **Downloading**: Updates when a download starts or stops
- **Download Progress**: Updates in real-time during downloads
- **Download Rate**: Updates with current download speed

### Polled Sensors

The following sensors update at the configured **publish interval** (default 30 seconds):
- **Battery**: Percentage, charging status, time remaining
- **Disk**: Internal and SD card storage
- **Network**: IP addresses

## MQTT Topics

The plugin uses the following topic structure:

### Discovery Topics (retained)
```
homeassistant/<component>/<hostname>_<sensor>/config
```

All sensors include an availability topic that marks them unavailable when the plugin disconnects.

### State Topics

**Hardware telemetry (retained, polled):**
```
steamdeck/<hostname>/telemetry/battery
steamdeck/<hostname>/telemetry/disk
steamdeck/<hostname>/telemetry/network
```

**Event-driven telemetry (non-retained, immediate):**
```
steamdeck/<hostname>/telemetry/game
steamdeck/<hostname>/telemetry/download
```

### Status Topic (retained)
```
steamdeck/<hostname>/status
```
Payload: `online` or `offline` (Last Will message)

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

Example automation using event-driven game sensor:

```yaml
automation:
  - alias: "Steam Deck Game Started"
    trigger:
      - platform: state
        entity_id: binary_sensor.steamdeck_steamdeck_game_running
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "Game Started"
          message: "Playing App ID {{ states('sensor.steamdeck_steamdeck_current_appid') }}"
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

### Game/Download sensors not updating
- Check browser console for event subscription errors (press F12 in Steam Deck gaming mode)
- Verify the plugin initialized successfully (check logs)
- Game and download sensors update via events, not polling - they should update instantly
- Try restarting the plugin or Steam client

### Sensors showing as "unavailable"
- Check that the plugin is connected to MQTT (status badge should show green)
- Verify the Steam Deck status sensor shows "online" in Home Assistant
- Sensors are marked unavailable when plugin disconnects

### Battery time remaining shows "unavailable"
- This sensor depends on power draw data which may not always be available
- It's normal for this to be unavailable when plugged in or when the system can't calculate the estimate

### SD card not detected
- The SD card must be mounted at `/run/media/...`
- Try removing and reinserting the SD card
- SD cards must be larger than 1GB to be detected

### Internal disk showing wrong size
- The plugin now reads from `/home` mount point for more accurate user storage
- This reflects the actual user-available space on Steam Deck

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
