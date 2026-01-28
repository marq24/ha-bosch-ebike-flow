"""Constants for the Bosch eBike integration."""
from dataclasses import dataclass, replace
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
from homeassistant.helpers.entity import EntityCategory, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import BoschEBikeDataUpdateCoordinator
from .bosch_data_handler import KEY_TOTAL_DISTANCE
from .const import DOMAIN


@dataclass(frozen=True)
class BoschEBikeSensorEntityDescription(SensorEntityDescription):
    """Describes Bosch eBike sensor entity."""
    value_fn: Callable[[dict[str, Any]], Any] | None = None
    attr_fn: Callable[[dict[str, Any]], Any] | None = None


@dataclass(frozen=True)
class BoschEBikeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Bosch eBike binary sensor entity."""
    value_fn: Callable[[dict[str, Any]], bool | None] | None = None


class BoschEBikeEntity(CoordinatorEntity[BoschEBikeDataUpdateCoordinator]):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: BoschEBikeDataUpdateCoordinator, description: EntityDescription) -> None:
        super().__init__(coordinator)
        # make sure we have a valid translation_key...
        if description.translation_key is None:
            description = replace(
                description,
                translation_key = f"{description.key}"
            )
        self.coordinator = coordinator
        self.entity_description = description

        # Set unique ID
        self._attr_unique_id = f"{coordinator.bike_id}_{description.key}"

        # we need also a 'shorter' entity-id
        self.entity_id = f"{DOMAIN}.bfe_{coordinator.bin.lower()}_{description.key}"

        # Build enhanced device info from component data
        device_info = {
            "identifiers": {(DOMAIN, coordinator.bike_id)},
            "name": coordinator.bike_name,
            "manufacturer": "Bosch",
        }

        # Add component details if available
        if coordinator.data and "components" in coordinator.data:
            components = coordinator.data["components"]

            # Set model from drive unit
            drive_unit = components.get("drive_unit", {})
            if drive_unit.get("product_name"):
                device_info["model"] = drive_unit["product_name"]

            # Add software version
            if drive_unit.get("software_version"):
                device_info["sw_version"] = f"DU: {drive_unit['software_version']}"

            # Add serial number
            if drive_unit.get("serial_number"):
                device_info["serial_number"] = drive_unit["serial_number"]

        if not device_info.get("model"):
            device_info["model"] = "eBike with ConnectModule"

        self._attr_device_info = device_info

    async def async_update(self):
        """Update entity."""
        await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def should_poll(self) -> bool:
        """Entities do not individually poll."""
        return False


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
