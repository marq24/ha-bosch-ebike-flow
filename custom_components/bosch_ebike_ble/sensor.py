"""Support for Bosch eBike BLE sensors."""

from __future__ import annotations

from sensor_state_data import SensorUpdate

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfPower,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from . import BoschEBikeBLEConfigEntry
from .device import device_key_to_bluetooth_entity_key
from .parser import BoschEBikeSensor

SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    BoschEBikeSensor.BATTERY: SensorEntityDescription(
        key=BoschEBikeSensor.BATTERY,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BoschEBikeSensor.SPEED: SensorEntityDescription(
        key=BoschEBikeSensor.SPEED,
        translation_key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BoschEBikeSensor.CADENCE: SensorEntityDescription(
        key=BoschEBikeSensor.CADENCE,
        translation_key="cadence",
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:rotate-right",
    ),
    BoschEBikeSensor.HUMAN_POWER: SensorEntityDescription(
        key=BoschEBikeSensor.HUMAN_POWER,
        translation_key="human_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BoschEBikeSensor.MOTOR_POWER: SensorEntityDescription(
        key=BoschEBikeSensor.MOTOR_POWER,
        translation_key="motor_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BoschEBikeSensor.ASSIST_MODE: SensorEntityDescription(
        key=BoschEBikeSensor.ASSIST_MODE,
        translation_key="assist_mode",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "eco", "tour", "sport", "turbo"],
    ),
    BoschEBikeSensor.TORQUE: SensorEntityDescription(
        key=BoschEBikeSensor.TORQUE,
        translation_key="torque",
        native_unit_of_measurement="Nm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:car-turbocharger",
        entity_registry_enabled_default=False,
    ),
    BoschEBikeSensor.SIGNAL_STRENGTH: SensorEntityDescription(
        key=BoschEBikeSensor.SIGNAL_STRENGTH,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
}


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a Bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            device_key_to_bluetooth_entity_key(device_key): SENSOR_DESCRIPTIONS[
                device_key.key
            ]
            for device_key in sensor_update.entity_descriptions
            if device_key.key in SENSOR_DESCRIPTIONS
        },
        entity_data={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
        entity_names={},
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschEBikeBLEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bosch eBike BLE sensors."""
    coordinator = entry.runtime_data
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            BoschEBikeBLESensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(
        coordinator.async_register_processor(processor, SensorEntityDescription)
    )


class BoschEBikeBLESensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[str | int | float | None, SensorUpdate]
    ],
    SensorEntity,
):
    """Representation of a Bosch eBike BLE sensor."""

    @property
    def native_value(self) -> str | int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        The sensor is only created when the device is seen.
        Since eBikes only broadcast when powered on, we return True
        once the device has been seen.
        """
        return True

    @property
    def assumed_state(self) -> bool:
        """Return True if the device is no longer broadcasting."""
        return not self.processor.available

