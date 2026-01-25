"""Sensor platform for Bosch eBike integration."""
import logging
from typing import Any

from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from . import BoschEBikeDataUpdateCoordinator, KEY_COORDINATOR
from .bosch_data_handler import KEY_TOTAL_DISTANCE
from .const import DOMAIN, CONF_LAST_BIKE_ACTIVITY
from .entities import SENSORS, BoschEBikeEntity, BoschEBikeSensorEntityDescription

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Bosch eBike sensors from a config entry."""
    coordinator: BoschEBikeDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    entities = [
        BoschEBikeSensor(coordinator, description, config_entry)
        for description in SENSORS
    ]

    async_add_entities(entities)


class BoschEBikeSensor(BoschEBikeEntity, SensorEntity):

    def __init__(self, coordinator: BoschEBikeDataUpdateCoordinator, description: BoschEBikeSensorEntityDescription, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, description=description)
        self._config_entry = config_entry

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # we want to try to import the historic states for the 'total_distance' based on the available activities
        if self.entity_description.key == KEY_TOTAL_DISTANCE:
            await self._import_historical_total_distance_statistics()

    async def _import_historical_total_distance_statistics(self) -> None:
        """Import historical statistics from an activity list."""
        if not hasattr(self.coordinator, "activity_list") or not self.coordinator.activity_list or len(self.coordinator.activity_list) == 0:
            _LOGGER.debug(f"_import_historical_total_distance_statistics(): No NEW activities that must be imported into stats found for: {self.entity_id}")
            return

        _LOGGER.info(f"_import_historical_total_distance_statistics(): Starting historical statistics import of {len(self.coordinator.activity_list)} entries for: {self.entity_id}")
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
                has_sum=True,
                name=self.name,
                source="recorder",
                statistic_id=self.entity_id,
                unit_of_measurement=self.native_unit_of_measurement,
            )
            # Check for unit_class (modern HA) vs. older versions
            from homeassistant.components.recorder import models
            if hasattr(models, "StatisticMeanType"):
                metadata["mean_type"] = models.StatisticMeanType.NONE
                metadata["unit_class"] = None
            else:
                # old HA Versions...
                metadata["has_mean"] = False

            async_import_statistics(self.hass, metadata, statistics)

            # update the config entry to indicate that we have imported the statistics up to the
            # most recent activity id that is present @ bosch backends...
            self.hass.config_entries.async_update_entry(self._config_entry, data={
                **self._config_entry.data,
                CONF_LAST_BIKE_ACTIVITY: self.coordinator.activity_list[0].get("id", None)
            })

    @property
    def extra_state_attributes(self):
        if self.coordinator.data is None:
            return None

        if hasattr(self.entity_description, "attr_fn") and self.entity_description.attr_fn is not None:
            return self.entity_description.attr_fn(self.coordinator.data)


    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        if hasattr(self.entity_description, "value_fn") and self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(self.coordinator.data)

        return None
