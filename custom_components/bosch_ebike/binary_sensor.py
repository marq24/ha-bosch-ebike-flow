"""Binary sensor platform for Bosch eBike integration."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import BoschEBikeDataUpdateCoordinator, KEY_COORDINATOR
from .const import DOMAIN
from .entities import BINARY_SENSORS, BoschEBikeEntity, BoschEBikeBinarySensorEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Bosch eBike binary sensors from a config entry."""
    coordinator: BoschEBikeDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]
    entities = [
        BoschEBikeBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    ]
    async_add_entities(entities)


class BoschEBikeBinarySensor(BoschEBikeEntity, BinarySensorEntity):
    """Representation of a Bosch eBike binary sensor."""
    def __init__(self, coordinator: BoschEBikeDataUpdateCoordinator, description: BoschEBikeBinarySensorEntityDescription) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator=coordinator, description=description)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if self.coordinator.data is None:
            return None

        if hasattr(self.entity_description, "value_fn") and self.entity_description.value_fn is not None:
            value = self.entity_description.value_fn(self.coordinator.data)

            # Log state changes for critical sensors
            if self.entity_description.key in ("charger_connected", "battery_charging"):
                if not hasattr(self, "_last_logged_state") or self._last_logged_state != value:
                    _LOGGER.debug(f"Binary sensor {self.entity_description.key} state: {value} (previous: {getattr(self, "_last_logged_state", "unknown")})")
                    self._last_logged_state = value

            return value

        return None