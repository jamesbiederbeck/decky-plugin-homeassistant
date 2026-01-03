"""
Telemetry Collection module.
Collects system telemetry data from the Steam Deck.
"""

import os
import json
import subprocess
from pathlib import Path
import decky

from .constants import MIN_SD_CARD_SIZE_BYTES


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

        # Internal storage - prefer /home for Steam Deck user storage
        # On Steam Deck, /home is typically more representative of user-available space
        # Fall back to / if /home is not accessible
        internal_path = "/home"
        try:
            # Check if /home exists and is accessible
            stat = os.statvfs(internal_path)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            result["internal_free_gb"] = round(free / (1024 ** 3), 2)
            result["internal_total_gb"] = round(total / (1024 ** 3), 2)
            result["internal_percent_used"] = round((used / total) * 100, 1) if total > 0 else 0
        except Exception as e:
            decky.logger.debug(f"Error getting disk info from {internal_path}, falling back to /: {e}")
            # Fall back to root filesystem
            try:
                stat = os.statvfs("/")
                total = stat.f_blocks * stat.f_frsize
                free = stat.f_bavail * stat.f_frsize
                used = total - free
                result["internal_free_gb"] = round(free / (1024 ** 3), 2)
                result["internal_total_gb"] = round(total / (1024 ** 3), 2)
                result["internal_percent_used"] = round((used / total) * 100, 1) if total > 0 else 0
            except Exception as e2:
                decky.logger.error(f"Error getting internal disk info: {e2}")

        # SD card (usually mounted under /run/media/)
        # Explicitly detect SD card mount state
        sd_mount_base = Path("/run/media")
        if sd_mount_base.exists():
            try:
                for user_dir in sd_mount_base.iterdir():
                    if not user_dir.is_dir():
                        continue
                    for mount_point in user_dir.iterdir():
                        if not mount_point.is_dir():
                            continue
                        # Check if it's a valid mount point
                        try:
                            stat = os.statvfs(str(mount_point))
                            total = stat.f_blocks * stat.f_frsize
                            # Only consider it an SD card if it has reasonable size
                            if total > MIN_SD_CARD_SIZE_BYTES:
                                free = stat.f_bavail * stat.f_frsize
                                used = total - free
                                result["sd_free_gb"] = round(free / (1024 ** 3), 2)
                                result["sd_total_gb"] = round(total / (1024 ** 3), 2)
                                result["sd_percent_used"] = round((used / total) * 100, 1)
                                result["sd_mounted"] = True
                                decky.logger.debug(f"SD card detected at {mount_point}")
                                break
                        except Exception as e:
                            decky.logger.debug(f"Error checking mount point {mount_point}: {e}")
                    if result["sd_mounted"]:
                        break
            except Exception as e:
                decky.logger.debug(f"Error scanning SD card mounts: {e}")

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
