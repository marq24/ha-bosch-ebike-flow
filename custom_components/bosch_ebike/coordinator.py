"""DataUpdateCoordinator for Bosch eBike integration."""
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.device_tracker import config_entry
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BoschEBikeOAuthAPI, BoschEBikeAPIError
from .const import DOMAIN, CONF_BIKE_PASS, CONF_LAST_BIKE_ACTIVITY

_LOGGER = logging.getLogger(__name__)

# Poll every 5 minutes (300 seconds)
UPDATE_INTERVAL = timedelta(minutes=5)


class BoschEBikeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Bosch eBike data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: BoschEBikeOAuthAPI,
        config_entry: ConfigEntry,
        bike_id: str,
        bike_name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{bike_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self.config_entry = config_entry
        self.bike_id = bike_id
        self.bike_name = bike_name

        self.has_flow_subscription = False
        self.activity_list = None

    async def int_after_start(self) -> None:
        """We are initializing our data coordinator after Home Assistant startup."""
        self.has_flow_subscription = await self.api.get_subscription_status()
        if self.config_entry.data.get(CONF_BIKE_PASS, None) is None:
            _LOGGER.info("int_after_start(): need to fetch bike pass...")
            pass_data_src = await self.api.get_bike_pass(bike_id=self.bike_id)
            if pass_data_src is not None and pass_data_src.get("frameNumber") is not None:
                pass_data = {CONF_BIKE_PASS: {
                        "frame": pass_data_src.get("frameNumber"),
                        "created_at": pass_data_src.get("createdAt"),
                    }}
                self.hass.config_entries.async_update_entry(self.config_entry, data={**self.config_entry.data, **pass_data})

        # do we need to import activities? [including the past statistics?]
        last_processed_activity = self.config_entry.data.get(CONF_LAST_BIKE_ACTIVITY, None)
        must_import_all = False
        if last_processed_activity is None:
            must_import_all = True
        else:
            recent_activities = await self.api.get_activity_list_recent(bike_id=self.bike_id)
            _LOGGER.debug(f"int_after_start(): Fetched RECENT activity list with {len(recent_activities)} entries")

            if recent_activities is not None and len(recent_activities) > 0:
                idx = 0
                for activity in recent_activities:
                    if activity.get("id") == last_processed_activity:
                        break
                    idx += 1

                if idx == 0:
                    _LOGGER.debug(f"int_after_start(): Last processed activity {last_processed_activity} is still the most recent one.")
                elif idx < len(recent_activities):
                    self.activity_list = recent_activities[:idx]
                    _LOGGER.debug(f"int_after_start(): Processing new activity list with {len(self.activity_list)} entries")
                else:
                    must_import_all = True
                    _LOGGER.debug(f"int_after_start(): Last processed activity {last_processed_activity} not found in the activity list - must process all")

        if must_import_all:
            # looks like we have never imported the activity list into the odometer sensor statistics... so we do it now
            self.activity_list = await self.api.get_activity_list_complete(bike_id=self.bike_id)
            _LOGGER.debug(f"int_after_start(): Fetched ALL activity list with {len(self.activity_list)} entries")

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Bosch eBike API."""
        try:
            _LOGGER.info(
                "=== COORDINATOR UPDATE TRIGGERED for bike %s ===", self.bike_id)

            # Fetch bike profile (static info + last known battery state)
            profile_data = await self.api.get_bike_profile(self.bike_id)

            # Try to fetch live state of charge (only works when bike is online/charging)
            soc_data = None
            if self.has_flow_subscription:
                try:
                    soc_data = await self.api.get_state_of_charge(self.bike_id)
                    _LOGGER.debug("_async_update_data(): Got live state-of-charge data")
                except BaseException as err:
                    # This is expected when bike is offline - not an error
                    _LOGGER.debug(f"_async_update_data(): get_state_of_charge caused {type(err).__name__} - {err}")
            else:
                _LOGGER.debug("_async_update_data(): No 'Bosch-Flow'-Subscription - skipping fetching of live state-of-charge data")

            # Combine the data
            combined_data = self._combine_bike_data(profile_data, soc_data)

            _LOGGER.info(
                "=== COORDINATOR UPDATE COMPLETE: battery = %s %%, charging = %s, charger_connected = %s ===",
                combined_data.get("battery", {}).get("level_percent", "unknown"),
                combined_data.get("battery", {}).get("is_charging"),
                combined_data.get("battery", {}).get("is_charger_connected"),
            )

            # Log lock/alarm status for debugging
            _LOGGER.info(
                "Lock status: is_locked=%s, lock_enabled=%s, alarm_enabled=%s",
                combined_data.get("bike", {}).get("is_locked"),
                combined_data.get("bike", {}).get("lock_enabled"),
                combined_data.get("bike", {}).get("alarm_enabled"),
            )

            return combined_data

        except BoschEBikeAPIError as err:
            _LOGGER.error("Error fetching bike data: %s", err)
            raise UpdateFailed(
                f"Error communicating with Bosch API: {err}") from err

    def _combine_bike_data(
        self,
        profile_data: dict[str, Any],
        soc_data: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Combine bike profile and state-of-charge data."""
        try:
            # Extract from profile
            batteries_list = profile_data.get("batteries") or []
            battery = batteries_list[0] if batteries_list else {}
            # Use 'or {}' to handle None values (API may return null for optional fields)
            drive_unit = profile_data.get("driveUnit") or {}
            connected_module = profile_data.get("connectedModule") or {}
            remote_control = profile_data.get("remoteControl") or {}

            # Start with profile data
            combined = {
                "battery": {
                    "level_percent": battery.get("batteryLevel"),
                    "remaining_wh": battery.get("remainingEnergy"),
                    "total_capacity_wh": battery.get("totalEnergy"),
                    "is_charging": battery.get("isCharging"),
                    "is_charger_connected": battery.get("isChargerConnected"),
                    "charge_cycles_total": (battery.get("numberOfFullChargeCycles") or {}).get("total"),
                    "delivered_lifetime_wh": battery.get("deliveredWhOverLifetime"),
                    "product_name": battery.get("productName"),
                    "software_version": battery.get("softwareVersion"),
                    # take the max 'reachableRange' from the driveUnit:driveUnitAssistModes...
                    "reachable_range_km": sorted(
                        [int(item["reachableRange"]) for item in drive_unit.get("driveUnitAssistModes",{})],
                        reverse=True)
            },
                "bike": {
                    "total_distance_m": drive_unit.get("totalDistanceTraveled"),
                    "is_locked": (drive_unit.get("lock") or {}).get("isLocked"),
                    "lock_enabled": (drive_unit.get("lock") or {}).get("isEnabled"),
                    "alarm_enabled": connected_module.get("isAlarmFeatureEnabled"),
                },
                "components": {
                    "drive_unit": {
                        "product_name": drive_unit.get("productName"),
                        "software_version": drive_unit.get("softwareVersion"),
                        "serial_number": drive_unit.get("serialNumber"),
                    },
                    "battery": {
                        "product_name": battery.get("productName"),
                        "software_version": battery.get("softwareVersion"),
                        "serial_number": battery.get("serialNumber"),
                    },
                    "connected_module": {
                        "product_name": connected_module.get("productName"),
                        "software_version": connected_module.get("softwareVersion"),
                        "serial_number": connected_module.get("serialNumber"),
                    },
                    "remote_control": {
                        "product_name": remote_control.get("productName"),
                        "software_version": remote_control.get("softwareVersion"),
                        "serial_number": remote_control.get("serialNumber"),
                    },
                },
                "last_update": None,
                "live_data_available": False,
            }


        # If we have live state-of-charge data, use it to fill in/override nulls
            if soc_data:
                combined["live_data_available"] = True
                combined["last_update"] = soc_data.get(
                    "stateOfChargeLatestUpdate")

                # Use live data to fill in null values from profile
                if combined["battery"]["level_percent"] is None:
                    combined["battery"]["level_percent"] = soc_data.get(
                        "stateOfCharge")

                if combined["battery"]["is_charging"] is None:
                    combined["battery"]["is_charging"] = soc_data.get(
                        "chargingActive")

                if combined["battery"]["is_charger_connected"] is None:
                    combined["battery"]["is_charger_connected"] = soc_data.get(
                        "chargerConnected")

                # Add live-only data
                reachable_range_raw = soc_data.get("reachableRange")
                _LOGGER.debug("Reachable range raw data: %s (type: %s)",
                              reachable_range_raw, type(reachable_range_raw))
                combined["battery"]["reachable_range_km"] = reachable_range_raw
                combined["battery"]["remaining_energy_rider_wh"] = soc_data.get(
                    "remainingEnergyForRider")

                # Update odometer from live data if available
                if soc_data.get("odometer") is not None:
                    combined["bike"]["total_distance_m"] = soc_data.get(
                        "odometer")
            return combined

        except (KeyError, IndexError, TypeError) as err:
            _LOGGER.error("Error combining bike data: %s", err)
            raise UpdateFailed(f"Error parsing bike data: {err}") from err
