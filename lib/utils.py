"""
Utility functions for the Home Assistant MQTT plugin.
"""

import socket


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
