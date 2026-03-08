"""Constants for the Bosch eBike integration."""
from typing import Final

DOMAIN: Final = "bosch_ebike"

# OAuth Configuration
AUTH_URL: Final = "https://p9.authz.bosch.com/auth/realms/obc/protocol/openid-connect/auth"
TOKEN_URL: Final = "https://p9.authz.bosch.com/auth/realms/obc/protocol/openid-connect/token"

CLIENT_ID: Final = "one-bike-app"
REDIRECT_URI: Final = "onebikeapp-ios://com.bosch.ebike.onebikeapp/oauth2redirect"
SCOPE: Final = "openid offline_access"

# API URLs
PROFILE_API_BASE_URL: Final = "https://obc-rider-profile.prod.connected-biking.cloud"
PROFILE_ENDPOINT_PROFILE: Final = "/v1/profile"
PROFILE_ENDPOINT_BIKE_PROFILE: Final = "/v1/bike-profile" # v1 will return ["data"]["attributes"]
PROFILE_ENDPOINT_BIKE_PROFILE_V2: Final = "/v2/bike-profile" # v2 will return a flat structure
PROFILE_ENDPOINT_STATE_OF_CHARGE: Final = "/v1/state-of-charge"

#url: 'https://obc-rider-activity.prod.connected-biking.cloud/v1/activity?page=0&size=' + this.config.maxTrips + '&sort=-startTime'
# url: 'https://obc-rider-activity.prod.connected-biking.cloud/v1/activity/' + id + '/detail',
ACTIVITY_API_BASE_URL: Final = "https://obc-rider-activity.prod.connected-biking.cloud"
ACTIVITIES_ENDPOINT:Final = "/v1/activity"

IN_APP_PURCHASE_API_BASE_URL: Final = "https://in-app-purchase.prod.connected-biking.cloud"
IN_APP_PURCHASE_ENDPOINT_STATE: Final = "/v1/subscription/status"

BIKEPASS_API_BASE_URL: Final = "https://bike-pass.prod.connected-biking.cloud"
BIKEPASS_ENDPOINT_PASSES: Final = "/v1/bike-passes"

# Update intervals
DEFAULT_SCAN_INTERVAL = 5 # 5minustes
MIN_SCAN_INTERVAL = 1

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
CONF_BIKE_PASS: Final = "bike_pass"
CONF_LAST_BIKE_ACTIVITY: Final = "last_bike_activity"
CONF_LOG_TO_FILESYSTEM: Final = "log_to_filesystem"

CONF_REFRESH_TOKEN: Final  = "refresh_token"
CONF_EXPIRES_AT: Final  = "expires_at"
CONF_EXPIRES_IN: Final  = "expires_in"
CONF_REFRESH_EXPIRES_IN: Final = "refresh_expires_in"
CONF_REFRESH_EXPIRES_AT: Final = "refresh_expires_at"

OAUTH_TOKEN_KEY:Final = "token"

CONFIG_VERSION: Final = 1
CONFIG_MINOR_VERSION: Final = 2



from dataclasses import dataclass
from typing import Callable, Any

from custom_components.bosch_ebike import bosch_data_handler
from homeassistant.components.binary_sensor import BinarySensorEntityDescription, BinarySensorDeviceClass
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
)
from homeassistant.helpers.entity import EntityCategory
from .bosch_data_handler import KEY_TOTAL_DISTANCE

@dataclass(frozen=True)
class BoschEBikeSensorEntityDescription(SensorEntityDescription):
    """Describes Bosch eBike sensor entity."""
    value_fn: Callable[[dict[str, Any]], Any] | None = None
    attr_fn: Callable[[dict[str, Any]], Any] | None = None


@dataclass(frozen=True)
class BoschEBikeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Bosch eBike binary sensor entity."""
    value_fn: Callable[[dict[str, Any]], bool | None] | None = None


BINARY_SENSORS = [
    BoschEBikeBinarySensorEntityDescription(
        key="battery_charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=bosch_data_handler.get_battery_charging,
    ),
    # Note: charger_connected is unreliable - ConnectModule stops updating when
    # bike is unplugged and powered off, so we never get the "unplugged" event
    BoschEBikeBinarySensorEntityDescription(
        key="charger_connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=bosch_data_handler.get_charger_connected,
        entity_registry_enabled_default=False,  # Disabled - unreliable due to ConnectModule behavior
    ),
    # Lock and alarm sensors are unreliable - need further API exploration
    BoschEBikeBinarySensorEntityDescription(
        key="lock_enabled",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=bosch_data_handler.get_lock_enabled,
        entity_registry_enabled_default=False,  # Disabled - unreliable, needs investigation
    ),
    BoschEBikeBinarySensorEntityDescription(
        key="alarm_enabled",
        # No device_class - just show On/Off
        value_fn=bosch_data_handler.get_alarm_enabled,
        entity_registry_enabled_default=False,  # Disabled - unreliable, needs investigation
    ),
]

SENSORS = [
    BoschEBikeSensorEntityDescription(
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=bosch_data_handler.get_battery_level,
    ),
    BoschEBikeSensorEntityDescription(
        key="battery_remaining_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=bosch_data_handler.get_battery_remaining_energy,
    ),
    BoschEBikeSensorEntityDescription(
        key="battery_capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=bosch_data_handler.get_battery_capacity,
    ),
    BoschEBikeSensorEntityDescription(
        key="battery_reachable_max_range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:arrow-collapse-right",
        value_fn=bosch_data_handler.get_battery_reachable_max_range,
        suggested_display_precision=2,
        entity_registry_enabled_default=True,
    ),
    BoschEBikeSensorEntityDescription(
        key="battery_reachable_min_range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:arrow-collapse-left",
        value_fn=bosch_data_handler.get_battery_reachable_min_range,
        suggested_display_precision=2,
        entity_registry_enabled_default=True,
    ),
    BoschEBikeSensorEntityDescription(
        key=KEY_TOTAL_DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        suggested_display_precision=2,
        value_fn=bosch_data_handler.get_total_distance,
    ),
    BoschEBikeSensorEntityDescription(
        key="charge_cycles",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:battery-sync",
        suggested_display_precision=2,
        value_fn=bosch_data_handler.get_charge_cycles,
        attr_fn=bosch_data_handler.get_charge_cycles_attr,
    ),
    BoschEBikeSensorEntityDescription(
        key="lifetime_energy_delivered",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        icon="mdi:lightning-bolt",
        value_fn=bosch_data_handler.get_lifetime_energy_delivered,
    ),
    BoschEBikeSensorEntityDescription(
        key="drive_unit_software_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
        icon="mdi:numeric",
        value_fn=bosch_data_handler.get_drive_unit_software_version,
    ),
    BoschEBikeSensorEntityDescription(
        key="battery_software_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
        icon="mdi:numeric",
        value_fn=bosch_data_handler.get_battery_software_version,
    ),
    BoschEBikeSensorEntityDescription(
        key="connected_module_software_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
        icon="mdi:numeric",
        value_fn=bosch_data_handler.get_connected_module_software_version,
    ),
    # Diagnostic sensors (disabled by default)
    BoschEBikeSensorEntityDescription(
        key="remote_control_software_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:numeric",
        value_fn=bosch_data_handler.get_remote_control_software_version,
    ),
]
