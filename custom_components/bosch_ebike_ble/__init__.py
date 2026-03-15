"""The Bosch eBike BLE integration."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.components.bluetooth.active_update_processor import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from sensor_state_data import SensorUpdate

from .parser import BoschEBikeBluetoothDeviceData

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


type BoschEBikeBLEConfigEntry = ConfigEntry[ActiveBluetoothProcessorCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BoschEBikeBLEConfigEntry) -> bool:
    """Set up Bosch eBike BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    data = BoschEBikeBluetoothDeviceData()

    def _needs_poll(
        service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        # Bosch eBike requires active connection to read data
        # Only poll if hass is running and we have a connectable device

        _LOGGER.debug("_needs_poll called: hass.state=%s, last_poll=%s", hass.state, last_poll)

        # if hass.state is not CoreState.running:
        #     _LOGGER.debug("_needs_poll: hass IS NOT running (yet)")
        #     return False

        poll_needed = data.poll_needed(service_info, last_poll)
        _LOGGER.debug("_needs_poll: poll_needed=%s", poll_needed)

        if not poll_needed:
            return False

        # Check if we have a connectable device
        device = async_ble_device_from_address(
            hass, service_info.device.address, connectable=True
        )
        _LOGGER.debug("_needs_poll: device=%s, connectable=%s", device, service_info.connectable)

        result = bool(device) or service_info.connectable
        _LOGGER.debug("_needs_poll returning: %s", result)
        return result

    async def _async_poll(service_info: BluetoothServiceInfoBleak) -> SensorUpdate:
        _LOGGER.debug("_async_poll called for %s", service_info.device.address)

        # Make sure the device we have is one that we can connect with
        # in case its coming from a passive scanner
        if service_info.connectable:
            connectable_device = service_info.device
            _LOGGER.debug("Using connectable device from service_info")
        elif device := async_ble_device_from_address(
                hass, service_info.device.address, True
        ):
            connectable_device = device
            _LOGGER.debug("Got connectable device from async_ble_device_from_address")
        else:
            _LOGGER.error("No connectable device found for %s", service_info.device.address)
            raise RuntimeError(
                f"No connectable device found for {service_info.device.address}"
            )

        _LOGGER.debug("Calling data.async_poll with device: %s", connectable_device)
        return await data.async_poll(connectable_device)

    coordinator = entry.runtime_data = ActiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.ACTIVE,
        update_method=data.update,
        needs_poll_method=_needs_poll,
        poll_method=_async_poll,
        connectable=True,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Wait 10 seconds before starting polling to give device time after pairing
    async def delayed_start():
        _LOGGER.info("Waiting 10 seconds before starting Bosch eBike polling...")
        await asyncio.sleep(10)
        _LOGGER.info("Starting Bosch eBike coordinator")
        entry.async_on_unload(coordinator.async_start())

    # Start the delayed task
    hass.async_create_task(delayed_start())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BoschEBikeBLEConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

