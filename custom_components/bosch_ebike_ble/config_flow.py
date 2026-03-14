"""Config flow for Bosch eBike BLE integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.components.bluetooth.api import async_ble_device_from_address
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, BOSCH_STATUS_SERVICE_UUID, BOSCH_STATUS_CHAR_UUID
from .parser import BoschEBikeBluetoothDeviceData

_LOGGER = logging.getLogger(__name__)


class BoschEBikeBLEConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bosch eBike BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_device: BoschEBikeBluetoothDeviceData | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
            self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the Bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        device = BoschEBikeBluetoothDeviceData()
        if not device.supported(discovery_info):
            return self.async_abort(reason="not_supported")

        self._discovery_info = discovery_info
        self._discovered_device = device
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        device = self._discovered_device
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        title = device.get_device_name() or discovery_info.name or "Bosch eBike"

        if user_input is not None:
            # Try to pair with the device by establishing connection and accessing protected characteristic
            try:
                _LOGGER.info("Attempting to pair with Bosch eBike %s", discovery_info.address)

                # Get the BLE device
                ble_device = async_ble_device_from_address(
                    self.hass, discovery_info.address, connectable=True
                )

                if ble_device is None:
                    _LOGGER.error("Could not find BLE device for %s", discovery_info.address)
                    return self.async_abort(reason="cannot_connect")

                # Attempt to establish connection and trigger pairing
                from bleak import BleakClient
                from bleak_retry_connector import establish_connection

                _LOGGER.debug("Establishing connection to %s", discovery_info.address)
                client = await establish_connection(
                    BleakClient,
                    ble_device,
                    discovery_info.address,
                    max_attempts=3,
                )

                try:
                    is_connected = client.is_connected
                    _LOGGER.info("Bosch eBike connected: %s", is_connected)

                    # Get services
                    services = client.services
                    if services:
                        service_list = list(services)
                        _LOGGER.debug("Found %d services", len(service_list))

                        # Try to access the protected characteristic to trigger pairing
                        service = client.services.get_service(BOSCH_STATUS_SERVICE_UUID)
                        if service:
                            _LOGGER.debug("Found Bosch status service")
                            char = service.get_characteristic(BOSCH_STATUS_CHAR_UUID)
                            if char:
                                _LOGGER.debug("Found Bosch status characteristic")

                                # Try to enable notifications - this will trigger pairing if needed
                                try:
                                    _LOGGER.info("Attempting to enable notifications (may trigger pairing)")

                                    # Define a dummy notification handler
                                    def notification_handler(sender: Any, data: bytes) -> None:
                                        _LOGGER.debug("Pairing notification received: %s", data.hex())

                                    await client.start_notify(char, notification_handler)
                                    _LOGGER.info("Notifications enabled successfully - device is paired!")

                                    # Wait a moment for any pairing dialogs
                                    await asyncio.sleep(1.0)

                                    # Stop notifications
                                    await client.stop_notify(char)
                                    _LOGGER.debug("Stopped notifications")

                                except Exception as notify_err:
                                    _LOGGER.error("Failed to enable notifications: %s", notify_err)
                                    _LOGGER.info("Device may require manual pairing - check eBike display for PIN")
                                    # Don't abort - continue anyway, pairing might work on next connection
                            else:
                                _LOGGER.warning("Bosch status characteristic not found")
                        else:
                            _LOGGER.warning("Bosch status service not found")

                    # Give the device a moment to complete pairing
                    await asyncio.sleep(0.5)

                finally:
                    await client.disconnect()
                    _LOGGER.info("Disconnected from Bosch eBike after pairing attempt")

            except Exception as err:
                _LOGGER.exception("Error during pairing attempt")
                # Don't abort - pairing might work during normal operation
                _LOGGER.warning("Pairing failed, but will retry during normal operation")

            return self.async_create_entry(title=title, data={})

        self._set_confirm_only()
        placeholders = {"name": title}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders=placeholders
        )

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered_devices[address], data={}
            )

        current_addresses = self._async_current_ids(include_ignore=False)
        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            device = BoschEBikeBluetoothDeviceData()
            if device.supported(discovery_info):
                self._discovered_devices[address] = (
                        device.get_device_name() or discovery_info.name or "Bosch eBike"
                )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
        )

