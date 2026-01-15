"""Sensor platform for Bosch eBike integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.util import dt as dt_util

from .const import DOMAIN, CONF_LAST_BIKE_ACTIVITY
from .coordinator import BoschEBikeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BoschEBikeSensorEntityDescription(SensorEntityDescription):
    """Describes Bosch eBike sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any] | None = None


SENSORS: tuple[BoschEBikeSensorEntityDescription, ...] = (
    BoschEBikeSensorEntityDescription(
        key="battery_level",
        translation_key="battery_level",
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("battery", {}).get("level_percent"),
    ),
    BoschEBikeSensorEntityDescription(
        key="battery_remaining_energy",
        translation_key="battery_remaining_energy",
        name="Battery Remaining Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("battery", {}).get("remaining_wh"),
    ),
    BoschEBikeSensorEntityDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        name="Battery Capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("battery", {}).get("total_capacity_wh"),
    ),
    BoschEBikeSensorEntityDescription(
        key="battery_reachable_range",
        translation_key="battery_reachable_range",
        name="Reachable Range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            # reachableRange is an array with values for each riding mode
            # Take the first value (most economical mode)
            data.get("battery", {}).get("reachable_range_km")[0]
            if isinstance(data.get("battery", {}).get("reachable_range_km"), list)
            and len(data.get("battery", {}).get("reachable_range_km", [])) > 0
            else None
        ),
        entity_registry_enabled_default=False,  # Only available when bike is online
    ),
    BoschEBikeSensorEntityDescription(
        key="total_distance",
        translation_key="total_distance",
        name="Total Distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            round(data.get("bike", {}).get("total_distance_m", 0) / 1000, 2)
            if data.get("bike", {}).get("total_distance_m") is not None
            else None
        ),
    ),
    BoschEBikeSensorEntityDescription(
        key="charge_cycles",
        translation_key="charge_cycles",
        name="Charge Cycles",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.get(
            "battery", {}).get("charge_cycles_total"),
    ),
    BoschEBikeSensorEntityDescription(
        key="lifetime_energy_delivered",
        translation_key="lifetime_energy_delivered",
        name="Lifetime Energy Delivered",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            round(data.get("battery", {}).get(
                "delivered_lifetime_wh", 0) / 1000, 2)
            if data.get("battery", {}).get("delivered_lifetime_wh") is not None
            else None
        ),
    ),
    # Diagnostic sensors (disabled by default)
    BoschEBikeSensorEntityDescription(
        key="drive_unit_software_version",
        translation_key="drive_unit_software_version",
        name="Drive Unit Software",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("components", {}).get(
            "drive_unit", {}).get("software_version"),
    ),
    BoschEBikeSensorEntityDescription(
        key="battery_software_version",
        translation_key="battery_software_version",
        name="Battery Software",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("components", {}).get(
            "battery", {}).get("software_version"),
    ),
    BoschEBikeSensorEntityDescription(
        key="connected_module_software_version",
        translation_key="connected_module_software_version",
        name="ConnectModule Software",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("components", {}).get(
            "connected_module", {}).get("software_version"),
    ),
    BoschEBikeSensorEntityDescription(
        key="remote_control_software_version",
        translation_key="remote_control_software_version",
        name="Remote Control Software",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get("components", {}).get(
            "remote_control", {}).get("software_version"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bosch eBike sensors from a config entry."""
    coordinator: BoschEBikeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = [
        BoschEBikeSensor(coordinator, description, entry)
        for description in SENSORS
    ]

    async_add_entities(entities)


class BoschEBikeSensor(CoordinatorEntity[BoschEBikeDataUpdateCoordinator], SensorEntity):
    """Representation of a Bosch eBike sensor."""

    entity_description: BoschEBikeSensorEntityDescription
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = None  # Will be computed dynamically

    def __init__(
        self,
        coordinator: BoschEBikeDataUpdateCoordinator,
        description: BoschEBikeSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry

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

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # we want to try to import the historic states for the 'total_distance' based in the available activities
        if self.entity_description.key == "total_distance":
            await self._import_historical_total_distance_statistics()

    async def _import_historical_total_distance_statistics(self) -> None:
        """Import historical statistics from activity list."""
        if not hasattr(self.coordinator, "activity_list") or not self.coordinator.activity_list or len(self.coordinator.activity_list) == 0:
            _LOGGER.debug(f"_import_historical_total_distance_statistics(): No NEW activities that must be imported into stats found for sensor: {self.entity_id}")
            return

        _LOGGER.info(f"_import_historical_total_distance_statistics(): Starting historical statistics import of {len(self.coordinator.activity_list)} entries for sensor: {self.entity_id}")

        statistics = []
        for activity in self.coordinator.activity_list:
            # ok go though our activities and just get the end date...
            attributes = activity.get("attributes", {})
            end_timestamp = attributes.get("endTime")
            start_odometer = attributes.get("startOdometer")
            distance = attributes.get("distance")

            if end_timestamp and start_odometer is not None and distance is not None:
                # Calculate odometer at the end of the activity
                total_dist_km = round((start_odometer + distance) / 1000, 2)
                # Round down to the start of the hour for HA long-term statistics
                end_time = dt_util.utc_from_timestamp(end_timestamp).replace(minute=0, second=0, microsecond=0)
                _LOGGER.debug(f"_import_historical_total_distance_statistics(): Queueing statistic for {total_dist_km} at {end_time.isoformat()}",)
                statistics.append(StatisticData(start=end_time, state=total_dist_km, sum=total_dist_km))

        if statistics:
            # Sort by time to ensure the recorder processes them in order
            statistics.sort(key=lambda x: x["start"])

            _LOGGER.info(f"_import_historical_total_distance_statistics(): Importing {len(statistics)} historical data points - range: {statistics[0]["start"].isoformat()} to {statistics[-1]["start"].isoformat()}")
            metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=self.name,
                source="recorder",  # Change from DOMAIN to "recorder"
                statistic_id=self.entity_id,
                unit_of_measurement=self.native_unit_of_measurement,
            )
            async_import_statistics(self.hass, metadata, statistics)

            # update the config entry to indicate that we have imported the statistics up to the
            # most recent activity id that is present @ bosch backends...
            self.hass.config_entries.async_update_entry(self._entry, data={
                **self._entry.data,
                CONF_LAST_BIKE_ACTIVITY: self.coordinator.activity_list[0].get("id", None)
            })

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(self.coordinator.data)

        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Entity is available if coordinator succeeded
        # Even if individual values are None, we want to show the entity
        # (it will just show as Unknown)
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
        )
