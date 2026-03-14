"""Constants for the Bosch eBike BLE integration."""

DOMAIN = "bosch_ebike_ble"

# Bosch eBike BLE Service UUIDs
BOSCH_STATUS_SERVICE_UUID = "00000010-eaa2-11e9-81b4-2a2ae2dbcce4"
BOSCH_STATUS_CHAR_UUID = "00000011-eaa2-11e9-81b4-2a2ae2dbcce4"

# Update intervals
CONNECTED_UPDATE_INTERVAL_SECONDS = 30  # Erhöht von 10 auf 30
DISCONNECTED_UPDATE_INTERVAL_SECONDS = 120  # Erhöht von 60 auf 120
MIN_TIME_BETWEEN_POLLS_SECONDS = 5  # Mindestens 5 Sekunden zwischen Polls


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

