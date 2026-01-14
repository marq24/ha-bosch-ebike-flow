"""Constants for the Bosch eBike integration."""
from typing import Final

DOMAIN: Final = "bosch_ebike"

# API URLs
AUTH_URL: Final = "https://p9.authz.bosch.com/auth/realms/obc/protocol/openid-connect/auth"
TOKEN_URL: Final = "https://p9.authz.bosch.com/auth/realms/obc/protocol/openid-connect/token"
PROFILE_API_BASE_URL: Final = "https://obc-rider-profile.prod.connected-biking.cloud"
ACTIVITY_API_BASE_URL: Final = "https://obc-rider-activity.prod.connected-biking.cloud"

# OAuth Configuration
CLIENT_ID: Final = "one-bike-app"
REDIRECT_URI: Final = "onebikeapp-ios://com.bosch.ebike.onebikeapp/oauth2redirect"
SCOPE: Final = "openid offline_access"

# Profile-API Endpoints
PROFILE_ENDPOINT_BIKE_PROFILE: Final = "/v1/bike-profile"
PROFILE_ENDPOINT_STATE_OF_CHARGE: Final = "/v1/state-of-charge"
PROFILE_ENDPOINT_PROFILE: Final = "/v1/profile"

#url: 'https://obc-rider-activity.prod.connected-biking.cloud/v1/activity?page=0&size=' + this.config.maxTrips + '&sort=-startTime'
# url: 'https://obc-rider-activity.prod.connected-biking.cloud/v1/activity/' + id + '/detail',
ACTIVITIES_ENDPOINT:Final = "/v1/activity"

# Update intervals
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes (ConnectModule updates every 5 min)
TOKEN_REFRESH_INTERVAL = 5400  # 1.5 hours (tokens expire at 2 hours)

# Entity naming
ATTR_BATTERY_LEVEL = "battery_level"
ATTR_CHARGING = "charging"
ATTR_CHARGER_CONNECTED = "charger_connected"
ATTR_REMAINING_ENERGY = "remaining_energy"
ATTR_REACHABLE_RANGE = "reachable_range"
ATTR_ODOMETER = "odometer"
ATTR_LAST_UPDATE = "last_update"
ATTR_CHARGE_CYCLES = "charge_cycles"

# Assist modes for range sensors
ASSIST_MODES = ["eco", "tour", "sport", "turbo"]

# Config flow
CONF_BIKE_ID: Final = "bike_id"
CONF_BIKE_NAME: Final = "bike_name"
CONF_REFRESH_TOKEN: Final  = "refresh_token"
CONF_EXPIRES_AT: Final  = "expires_at"
CONF_EXPIRES_IN: Final  = "expires_in"
CONF_REFRESH_EXPIRES_IN: Final = "refresh_expires_in"
CONF_REFRESH_EXPIRES_AT: Final = "refresh_expires_at"

OAUTH_TOKEN_KEY:Final = "token"

CONFIG_VERSION: Final = 1
CONFIG_MINOR_VERSION: Final = 2
