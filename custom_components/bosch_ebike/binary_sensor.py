"""Binary sensor platform for Bosch eBike integration."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .coordinator import BoschEBikeDataUpdateCoordinator
from .entities import BINARY_SENSORS, BoschEBikeEntity, BoschEBikeBinarySensorEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bosch eBike binary sensors from a config entry."""
    coordinator: BoschEBikeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = [
        BoschEBikeBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    ]

    async_add_entities(entities)


class BoschEBikeBinarySensor(BoschEBikeEntity, BinarySensorEntity):
    """Representation of a Bosch eBike binary sensor."""
    def __init__(
        self,
        coordinator: BoschEBikeDataUpdateCoordinator,
        description: BoschEBikeBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator=coordinator, description=description)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if self.coordinator.data is None:
            return None

        if self.entity_description.value_fn is not None:
            value = self.entity_description.value_fn(self.coordinator.data)

            # Log state changes for critical sensors
            if self.entity_description.key in ("charger_connected", "battery_charging"):
                if not hasattr(self, "_last_logged_state") or self._last_logged_state != value:
                    _LOGGER.info(
                        "Binary sensor %s state: %s (previous: %s)",
                        self.entity_description.key,
                        value,
                        getattr(self, "_last_logged_state", "unknown"),
                    )
                    self._last_logged_state = value

            return value

        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Entity is available if coordinator succeeded
        # Even if individual values are None, we want to show the entity
        # (it will just show as Off/Unknown)
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
        )
