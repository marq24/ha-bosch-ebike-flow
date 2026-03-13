"""Constants for the Bosch eBike BLE integration."""

DOMAIN = "bosch_ebike_ble"

# Bosch eBike BLE Service UUIDs
# From: https://github.com/RobbyPee/Bosch-Smart-System-Ebike-Garmin-Android
BOSCH_STATUS_SERVICE_UUID = "00000010-eaa2-11e9-81b4-2a2ae2dbcce4"
BOSCH_STATUS_CHAR_UUID = "00000011-eaa2-11e9-81b4-2a2ae2dbcce4"

# Update intervals
CONNECTED_UPDATE_INTERVAL_SECONDS = 10
DISCONNECTED_UPDATE_INTERVAL_SECONDS = 60


# Assist modes
ASSIST_MODES = {
    0: "off",
    1: "eco",
    2: "tour",
    3: "sport",
    4: "turbo",
}

# Device name patterns for discovery
DEVICE_NAME_PATTERNS = [
    "SMART SYSTEM EBIKE",
    "smart system eBike",
    "Bosch eBike",
]

