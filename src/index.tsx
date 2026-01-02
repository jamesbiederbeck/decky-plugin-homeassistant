import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  ToggleField,
  staticClasses,
  Focusable,
  DialogButton,
  showModal
} from "@decky/ui";
import {
  callable,
  definePlugin,
  toaster
} from "@decky/api"
import { useState, useEffect, FC } from "react";
import { FaHome } from "react-icons/fa";
import TextInputModal from "./components/TextInputModal";

// Backend API calls
const getSettings = callable<[], Settings>("get_settings");
const saveSettings = callable<[settings: Settings], boolean>("save_settings");
const connectMqtt = callable<[], ConnectionResult>("connect_mqtt");
const disconnectMqtt = callable<[], ConnectionResult>("disconnect_mqtt");
const testConnection = callable<[], ConnectionResult>("test_connection");
const getConnectionStatus = callable<[], ConnectionStatus>("get_connection_status");
const publishNow = callable<[], PublishResult>("publish_now");
const getTelemetry = callable<[], TelemetryData>("get_telemetry");

// Types
interface EnabledSensors {
  battery: boolean;
  disk: boolean;
  network: boolean;
  game: boolean;
  download: boolean;
}

interface Settings {
  mqtt_host: string;
  mqtt_port: number;
  mqtt_username: string;
  mqtt_password: string;
  hostname: string;
  publish_interval: number;
  enabled_sensors: EnabledSensors;
  connected?: boolean;
}

interface ConnectionResult {
  success: boolean;
  connected?: boolean;
  error?: string;
}

interface ConnectionStatus {
  connected: boolean;
}

interface PublishResult {
  success: boolean;
  error?: string;
}

interface BatteryInfo {
  percent: number | null;
  charging: boolean;
  time_remaining_min: number | null;
}

interface DiskInfo {
  internal_free_gb: number | null;
  internal_total_gb: number | null;
  internal_percent_used: number | null;
  sd_free_gb: number | null;
  sd_total_gb: number | null;
  sd_percent_used: number | null;
  sd_mounted: boolean;
}

interface NetworkInfo {
  ip_wifi: string | null;
  ip_ethernet: string | null;
  ip_primary: string | null;
}

interface GameInfo {
  game_name: string | null;
  app_id: number | null;
  is_running: boolean;
}

interface DownloadInfo {
  downloading: boolean;
  download_progress: number | null;
  download_rate_mbps: number | null;
  download_app_name: string | null;
}

interface TelemetryData {
  battery: BatteryInfo;
  disk: DiskInfo;
  network: NetworkInfo;
  game: GameInfo;
  download: DownloadInfo;
}

const defaultSettings: Settings = {
  mqtt_host: "",
  mqtt_port: 1883,
  mqtt_username: "",
  mqtt_password: "",
  hostname: "steamdeck",
  publish_interval: 30,
  enabled_sensors: {
    battery: true,
    disk: true,
    network: true,
    game: true,
    download: true
  }
};

// Connection Status Component
const ConnectionStatusBadge: FC<{ connected: boolean }> = ({ connected }) => {
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: "8px",
      padding: "8px 12px",
      backgroundColor: connected ? "#1a472a" : "#4a1a1a",
      borderRadius: "4px",
      marginBottom: "12px"
    }}>
      <div style={{
        width: "10px",
        height: "10px",
        borderRadius: "50%",
        backgroundColor: connected ? "#4caf50" : "#f44336"
      }} />
      <span style={{ color: connected ? "#81c784" : "#ef9a9a" }}>
        {connected ? "Connected to MQTT" : "Disconnected"}
      </span>
    </div>
  );
};

// Telemetry Display Component
const TelemetryDisplay: FC<{ telemetry: TelemetryData | null }> = ({ telemetry }) => {
  if (!telemetry) return null;

  return (
    <PanelSection title="Current Telemetry">
      <PanelSectionRow>
        <div style={{ fontSize: "12px", color: "#b0b0b0" }}>
          <div><strong>Battery:</strong> {telemetry.battery.percent ?? "N/A"}% {telemetry.battery.charging ? "(Charging)" : ""}</div>
          <div><strong>Internal:</strong> {telemetry.disk.internal_free_gb ?? "N/A"} GB free</div>
          <div><strong>SD Card:</strong> {telemetry.disk.sd_mounted ? `${telemetry.disk.sd_free_gb ?? "N/A"} GB free` : "Not mounted"}</div>
          <div><strong>IP:</strong> {telemetry.network.ip_primary ?? "N/A"}</div>
          <div><strong>Game:</strong> {telemetry.game.is_running ? `App ${telemetry.game.app_id}` : "Not playing"}</div>
        </div>
      </PanelSectionRow>
    </PanelSection>
  );
};

// Main Content Component
function Content() {
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Load settings on mount
  useEffect(() => {
    loadSettings();
    const interval = setInterval(checkStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadSettings = async () => {
    try {
      const result = await getSettings();
      setSettings(result);
      setConnected(result.connected ?? false);
      setLoading(false);
    } catch (error) {
      console.error("Failed to load settings:", error);
      setLoading(false);
    }
  };

  const checkStatus = async () => {
    try {
      const status = await getConnectionStatus();
      setConnected(status.connected);
    } catch {
      // Silently fail for periodic status checks - this is expected when backend is loading
    }
  };

  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      const success = await saveSettings(settings);
      if (success) {
        toaster.toast({
          title: "Settings Saved",
          body: "Configuration has been saved successfully."
        });
        await loadSettings();
      } else {
        toaster.toast({
          title: "Error",
          body: "Failed to save settings."
        });
      }
    } catch (error) {
      console.error("Failed to save settings:", error);
      toaster.toast({
        title: "Error",
        body: "Failed to save settings."
      });
    }
    setSaving(false);
  };

  const handleTestConnection = async () => {
    setTesting(true);
    try {
      const result = await testConnection();
      if (result.success) {
        toaster.toast({
          title: "Connection Successful",
          body: "Successfully connected to MQTT broker!"
        });
      } else {
        toaster.toast({
          title: "Connection Failed",
          body: result.error || "Could not connect to MQTT broker."
        });
      }
    } catch (error) {
      console.error("Connection test failed:", error);
      toaster.toast({
        title: "Connection Failed",
        body: "Could not connect to MQTT broker."
      });
    }
    setTesting(false);
  };

  const handleConnect = async () => {
    try {
      const result = await connectMqtt();
      setConnected(result.connected ?? false);
      if (result.success) {
        toaster.toast({
          title: "Connected",
          body: "Successfully connected to MQTT broker!"
        });
      } else {
        toaster.toast({
          title: "Connection Failed",
          body: result.error || "Could not connect to MQTT broker."
        });
      }
    } catch (error) {
      console.error("Failed to connect:", error);
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnectMqtt();
      setConnected(false);
      toaster.toast({
        title: "Disconnected",
        body: "Disconnected from MQTT broker."
      });
    } catch (error) {
      console.error("Failed to disconnect:", error);
    }
  };

  const handlePublishNow = async () => {
    try {
      const result = await publishNow();
      if (result.success) {
        toaster.toast({
          title: "Published",
          body: "Telemetry data sent to Home Assistant."
        });
      } else {
        toaster.toast({
          title: "Publish Failed",
          body: result.error || "Failed to publish telemetry."
        });
      }
    } catch (error) {
      console.error("Failed to publish:", error);
    }
  };

  const handleRefreshTelemetry = async () => {
    try {
      const data = await getTelemetry();
      setTelemetry(data);
    } catch (error) {
      console.error("Failed to get telemetry:", error);
    }
  };

  const updateSetting = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const updateEnabledSensor = (sensor: keyof EnabledSensors, value: boolean) => {
    setSettings(prev => ({
      ...prev,
      enabled_sensors: { ...prev.enabled_sensors, [sensor]: value }
    }));
  };

  if (loading) {
    return (
      <PanelSection title="Loading...">
        <PanelSectionRow>
          <span>Loading settings...</span>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  return (
    <>
      {/* Connection Status */}
      <PanelSection>
        <ConnectionStatusBadge connected={connected} />
      </PanelSection>

      {/* MQTT Configuration */}
      <PanelSection title="MQTT Broker">
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={() => {
              showModal(
                <TextInputModal
                  title="MQTT Host"
                  description="Enter the hostname or IP address of your MQTT broker"
                  initialValue={settings.mqtt_host}
                  onConfirm={(value) => updateSetting("mqtt_host", value)}
                />
              );
            }}
          >
            Host: {settings.mqtt_host || "(not set)"}
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={() => {
              showModal(
                <TextInputModal
                  title="MQTT Port"
                  description="Enter the port number (default: 1883)"
                  initialValue={String(settings.mqtt_port)}
                  onConfirm={(value) => {
                    const parsed = parseInt(value);
                    updateSetting("mqtt_port", isNaN(parsed) ? 1883 : Math.max(1, Math.min(65535, parsed)));
                  }}
                />
              );
            }}
          >
            Port: {settings.mqtt_port}
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={() => {
              showModal(
                <TextInputModal
                  title="MQTT Username"
                  description="Enter the username for MQTT authentication (optional)"
                  initialValue={settings.mqtt_username}
                  onConfirm={(value) => updateSetting("mqtt_username", value)}
                />
              );
            }}
          >
            Username: {settings.mqtt_username || "(not set)"}
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={() => {
              showModal(
                <TextInputModal
                  title="MQTT Password"
                  description="Enter the password for MQTT authentication (optional)"
                  initialValue={settings.mqtt_password}
                  isPassword={true}
                  onConfirm={(value) => updateSetting("mqtt_password", value)}
                />
              );
            }}
          >
            Password: {settings.mqtt_password ? "****" : "(not set)"}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>

      {/* Device Configuration */}
      <PanelSection title="Device">
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={() => {
              showModal(
                <TextInputModal
                  title="Hostname"
                  description="Device identifier in Home Assistant"
                  initialValue={settings.hostname}
                  onConfirm={(value) => updateSetting("hostname", value)}
                />
              );
            }}
          >
            Hostname: {settings.hostname || "(not set)"}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>

      {/* Enabled Sensors */}
      <PanelSection title="Enabled Sensors">
        <PanelSectionRow>
          <ToggleField
            label="Battery"
            description="Battery %, charging status, time remaining"
            checked={settings.enabled_sensors.battery}
            onChange={(value) => updateEnabledSensor("battery", value)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label="Disk"
            description="Internal storage and SD card usage"
            checked={settings.enabled_sensors.disk}
            onChange={(value) => updateEnabledSensor("disk", value)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label="Network"
            description="IP addresses (WiFi, Ethernet)"
            checked={settings.enabled_sensors.network}
            onChange={(value) => updateEnabledSensor("network", value)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label="Game"
            description="Current game/app information"
            checked={settings.enabled_sensors.game}
            onChange={(value) => updateEnabledSensor("game", value)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label="Downloads"
            description="Steam download progress and status"
            checked={settings.enabled_sensors.download}
            onChange={(value) => updateEnabledSensor("download", value)}
          />
        </PanelSectionRow>
      </PanelSection>

      {/* Advanced Settings */}
      <PanelSection title="Advanced">
        <PanelSectionRow>
          <ToggleField
            label="Show Advanced"
            checked={showAdvanced}
            onChange={setShowAdvanced}
          />
        </PanelSectionRow>
        {showAdvanced && (
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={() => {
                showModal(
                  <TextInputModal
                    title="Publish Interval"
                    description="How often to publish telemetry data (in seconds, minimum 5)"
                    initialValue={String(settings.publish_interval)}
                    onConfirm={(value) => {
                      const parsed = parseInt(value);
                      updateSetting("publish_interval", isNaN(parsed) ? 30 : Math.max(5, parsed));
                    }}
                  />
                );
              }}
            >
              Publish Interval: {settings.publish_interval}s
            </ButtonItem>
          </PanelSectionRow>
        )}
      </PanelSection>

      {/* Actions */}
      <PanelSection title="Actions">
        <PanelSectionRow>
          <Focusable style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            <DialogButton
              onClick={handleSaveSettings}
              disabled={saving}
              style={{ minWidth: "80px" }}
            >
              {saving ? "Saving..." : "Save"}
            </DialogButton>
            <DialogButton
              onClick={handleTestConnection}
              disabled={testing || !settings.mqtt_host}
              style={{ minWidth: "80px" }}
            >
              {testing ? "Testing..." : "Test"}
            </DialogButton>
          </Focusable>
        </PanelSectionRow>
        <PanelSectionRow>
          <Focusable style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {connected ? (
              <DialogButton onClick={handleDisconnect} style={{ minWidth: "100px" }}>
                Disconnect
              </DialogButton>
            ) : (
              <DialogButton
                onClick={handleConnect}
                disabled={!settings.mqtt_host}
                style={{ minWidth: "100px" }}
              >
                Connect
              </DialogButton>
            )}
            <DialogButton
              onClick={handlePublishNow}
              disabled={!connected}
              style={{ minWidth: "100px" }}
            >
              Publish Now
            </DialogButton>
          </Focusable>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={handleRefreshTelemetry}
          >
            View Current Telemetry
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>

      {/* Telemetry Display */}
      <TelemetryDisplay telemetry={telemetry} />
    </>
  );
}

export default definePlugin(() => {
  console.log("Home Assistant MQTT plugin initializing");

  return {
    name: "Home Assistant MQTT",
    titleView: <div className={staticClasses.Title}>Home Assistant MQTT</div>,
    content: <Content />,
    icon: <FaHome />,
    onDismount() {
      console.log("Home Assistant MQTT plugin unloading");
    },
  };
});
