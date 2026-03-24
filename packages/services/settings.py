"""
SettingsService - Configuration Management

Centralized configuration using QSettings for persistent storage.
Provides default values and hierarchical key access.
"""

from PyQt5.QtCore import QSettings


def load_settings():
    """
    Load application settings with default values.
    
    Returns:
        QSettings: Configured settings object with defaults
    """
    settings = QSettings("UWB-Localization", "UnifiedDemo")
    
    # Set defaults if not already set
    _set_default(settings, "world/width_m", 4.80)
    _set_default(settings, "world/height_m", 6.00)
    
    _set_default(settings, "grid/cols", 8)
    _set_default(settings, "grid/rows", 10)
    _set_default(settings, "grid/cell_m", 0.60)
    
    _set_default(settings, "adaptive/split_y_m", 3.00)
    _set_default(settings, "adaptive/t_register_ms", 3000)
    _set_default(settings, "adaptive/t_deregister_ms", 1000)
    
    _set_default(settings, "zonedj/default_zone_radius_m", 0.25)
    _set_default(settings, "zonedj/t_register_ms", 3000)
    _set_default(settings, "zonedj/t_deregister_ms", 1000)
    
    _set_default(settings, "floorplan/default_path", "")
    
    _set_default(settings, "pgo/refresh_rate_fps", 30)
    _set_default(settings, "pgo/max_history_points", 1000)

    # MQTT broker (UnifiedDemo / server_bring_up_with_audio — use laptop IP for real anchors)
    _set_default(settings, "mqtt/broker", "localhost")
    _set_default(settings, "mqtt/port", 1884)
    _set_default(settings, "mqtt/username", "laptop")
    _set_default(settings, "mqtt/password", "laptop")

    _set_default(settings, "server/phone_node_id", 0)
    _set_default(settings, "server/poll_rate_hz", 20)
    
    return settings


def _set_default(settings: QSettings, key: str, value):
    """Helper to set default value if key doesn't exist."""
    if not settings.contains(key):
        settings.setValue(key, value)

