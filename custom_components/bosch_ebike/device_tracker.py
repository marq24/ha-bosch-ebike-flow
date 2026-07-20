"""Device tracker platform for Bosch eBike integration."""
import logging

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BoschEBikeDataUpdateCoordinator, BoschEBikeEntity, KEY_COORDINATOR, bosch_data_handler
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

LOCATION_DESCRIPTION = EntityDescription(
    key="location",
    icon="mdi:map-marker",
)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Bosch eBike device trackers from a config entry."""
    coordinator: BoschEBikeDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    # only bikes with a registered ConnectModule (BCM) can report their location
    if not coordinator.has_bcm:
        _LOGGER.debug("async_setup_entry(): No BCM registration found - using last location from activity polyline")

    async_add_entities([BoschEBikeDeviceTracker(coordinator, LOCATION_DESCRIPTION)])


class BoschEBikeDeviceTracker(BoschEBikeEntity, TrackerEntity):
    """Representation of a Bosch eBike device tracker (last known GPS location)."""
    def __init__(self, coordinator: BoschEBikeDataUpdateCoordinator, description: EntityDescription) -> None:
        """Initialize the device tracker."""
        self.is_polyline_location = not coordinator.has_bcm
        super().__init__(entity_type=Platform.DEVICE_TRACKER, coordinator=coordinator, description=description)

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device tracker."""
        if self.is_polyline_location:
            #return SourceType.ROUTER
            # YES marq24 is aware, that "Polyline"`is not part of the SourceType ENUM
            # but ROUTER is IMHO also totally wrong as source - we can argue that
            # the last point of the polyline is mobile-phone (Flow App) GPS
            # generated... but still I am not a fan of declaring this as SourceType.GPS
            return "Polyline"
        else:
            return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return the latitude of the last known location."""
        if self.coordinator.data is None:
            return None
        return bosch_data_handler.get_location_latitude(self.coordinator.data)

    @property
    def longitude(self) -> float | None:
        """Return the longitude of the last known location."""
        if self.coordinator.data is None:
            return None
        return bosch_data_handler.get_location_longitude(self.coordinator.data)

    @property
    def location_accuracy(self) -> float|int:
        """Return the horizontal accuracy of the last known location (in meters)."""
        if self.is_polyline_location:
            return 10
        else:
            if self.coordinator.data is None:
                return 0
            accuracy = bosch_data_handler.get_location_accuracy(self.coordinator.data)
            return int(accuracy) if accuracy is not None else 0

    @property
    def extra_state_attributes(self):
        """Return additional attributes of the last known location."""
        if self.is_polyline_location:
            return None
        else:
            if self.coordinator.data is None:
                return None
            return bosch_data_handler.get_location_attr(self.coordinator.data)
