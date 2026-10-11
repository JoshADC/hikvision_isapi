"""Constants for the Hikvision ISAPI integration."""

DOMAIN = "hikvision_isapi"
PLATFORMS = ["switch", "number", "select"]

CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

DEFAULT_SCAN_INTERVAL = 30
CONF_NAME = "name"

# Options key: when True, select entities expose the pre-1.4.0 English words
# ("Off", "White Light") as their values instead of the camera's raw values
# ("close", "colorVuWhiteLight"). Existing cameras are migrated with this on
# so their automations keep working; new cameras start with it off.
CONF_LEGACY_SELECT_VALUES = "legacy_select_values"
