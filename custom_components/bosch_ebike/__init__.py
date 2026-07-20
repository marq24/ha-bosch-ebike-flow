"""The Bosch eBike integration."""
import asyncio
import logging
import time
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any, Final

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform, CONF_ACCESS_TOKEN, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session, LocalOAuth2Implementation
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from polyline import polyline

from . import bosch_data_handler
from .api import BoschEBikeOAuthAPI, BoschEBikeAPIError, BoschEBikeAuthError
from .bosch_data_handler import KEY_PROFILE, KEY_SOC, KEY_ACTIVITY, KEY_LOCATION
from .const import (
    DOMAIN,
    CLIENT_ID,
    AUTH_URL,
    TOKEN_URL,
    OAUTH_TOKEN_KEY,
    CONF_BIKE_ID,
    CONF_BIKE_NAME,
    CONF_REFRESH_TOKEN,
    CONFIG_VERSION,
    CONFIG_MINOR_VERSION,
    CONF_EXPIRES_AT,
    CONF_BIKE_PASS,
    CONF_LAST_BIKE_ACTIVITY,
    CONF_LOG_TO_FILESYSTEM,
    LOCATION_SCAN_INTERVAL_MINUTES,
)
from .entity import CustomFriendlyNameEntity

_LOGGER = logging.getLogger(__name__)

KEY_COORDINATOR: Final  = "coordinator"

# Platforms to set up
PLATFORMS: Final = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    if config_entry.minor_version < CONFIG_MINOR_VERSION:
        if config_entry.data is not None and len(config_entry.data) > 0:

            # do we need to convert the config_entry?!
            if CONF_ACCESS_TOKEN in config_entry.data:
                # converting the origin 'access_token' and 'refresh_token' storage to the 'token' format...
                access_token = config_entry.data[CONF_ACCESS_TOKEN]
                refresh_token = config_entry.data.get(CONF_REFRESH_TOKEN)
                new_config_entry_data = {**config_entry.data, **{OAUTH_TOKEN_KEY: {
                    CONF_ACCESS_TOKEN: access_token,
                    CONF_REFRESH_TOKEN: refresh_token,
                    CONF_EXPIRES_AT: time.time()
                }}}
                new_config_entry_data.pop(CONF_ACCESS_TOKEN)
                new_config_entry_data.pop(CONF_REFRESH_TOKEN)

                hass.config_entries.async_update_entry(config_entry, data=new_config_entry_data, options=config_entry.options, version=CONFIG_VERSION, minor_version=CONFIG_MINOR_VERSION)
                _LOGGER.debug(f"async_migrate_entry(): Migration to configuration version {config_entry.version}.{config_entry.minor_version} successful")
            else:
                _LOGGER.warning(f"async_migrate_entry(): Incompatible config_entry found - this configuration should be removed from your HA - will not migrate {config_entry}")
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    if hass.is_stopping:
        _LOGGER.info("async_setup_entry(): Bosch eBike integration setup aborted due to Home Assistant shutdown")
        return False

    _LOGGER.debug("async_setup_entry(): Setting up Bosch eBike integration")

    # Create update coordinator
    coordinator = BoschEBikeDataUpdateCoordinator(hass=hass, config_entry=config_entry)
    _LOGGER.info(f"async_setup_entry(): Created coordinator for {coordinator} with update interval: {coordinator.update_interval}")

    # we need to check some configuration stuff after start...
    await coordinator.int_after_start()

    # Fetch initial data
    _LOGGER.info(f"Performing initial data refresh for {coordinator.bin}")
    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    _LOGGER.info(f"async_setup_entry(): Initial data refresh complete for {coordinator.bin}")

    # Store coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {KEY_COORDINATOR: coordinator}

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # at least we want to log if somebody updated the config entry...
    config_entry.async_on_unload(config_entry.add_update_listener(entry_update_listener))

    _LOGGER.info(f"async_setup_entry(): Bosch eBike integration setup complete for {coordinator.bin}")
    return True


async def entry_update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    _LOGGER.debug(f"entry_update_listener(): called for entry: {config_entry.entry_id}")

    # # Get the last known token from our data store
    # the_entry_data = hass.data[DOMAIN].get(config_entry.entry_id, {})
    # last_token = the_entry_data.get(LAST_TOKEN_KEY, None)
    #
    # # Get the current token from the config entry
    # current_access_token = config_entry.data.get(OAUTH_TOKEN_KEY, {}).get(OAUTH_ACCESS_TOKEN_KEY, None)
    #
    # # If the token has changed, update our store and skip the reload
    # if current_access_token != last_token:
    #     _LOGGER.debug(f"entry_update_listener(): only 'access token' was updated, skipping reload.")
    #     the_entry_data[LAST_TOKEN_KEY] = current_access_token
    #     return

    # only on 'none' access_token updates, reload the config_entry...
    # await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug(f"async_unload_entry(): Unloading Bosch eBike integration - {config_entry.state}")
    if config_entry.state not in [ConfigEntryState.FAILED_UNLOAD, ConfigEntryState.NOT_LOADED]:

        # Unload platforms
        unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
        if unload_ok:
            _LOGGER.debug("async_unload_entry(): async_unload_platforms returned True - removing data from hass.data")
            # Remove data
            hass.data[DOMAIN].pop(config_entry.entry_id, None)

        return unload_ok
    else:
        _LOGGER.warning(f"async_unload_entry(): Cannot unload config entry {config_entry.entry_id} because it is not in loaded state - state is {config_entry.state}" )
        return False


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.debug("async_reload_entry(): triggered")
    if await async_unload_entry(hass, entry):
        _LOGGER.debug("async_reload_entry(): call to 'async_unload_entry' returned True")
        await asyncio.sleep(1.5)
        if await async_setup_entry(hass, entry):
            _LOGGER.debug("async_reload_entry(): call to 'async_setup_entry' returned True")
    _LOGGER.debug("async_reload_entry(): finished")


class BoschEBikeDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage to fetch Bosch eBike data from the API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        # the bin is the vin of a bike ;-)
        self.config_entry = config_entry
        self.bike_id = config_entry.data[CONF_BIKE_ID]
        self.bike_name = config_entry.data.get(CONF_BIKE_NAME, "eBike")
        bike_pass_object = config_entry.data.get(CONF_BIKE_PASS, {})
        if bike_pass_object is not None:
            self._bin = bike_pass_object.get("frame", self.bike_id)
            if self._bin.startswith("NOBIKEPASS_"):
                self._bin = self.bike_id
        else:
            self._bin = self.bike_id

        # creating our OAuth2Session-session...
        implementation = LocalOAuth2Implementation(
            hass,
            DOMAIN,
            client_id=CLIENT_ID,
            client_secret="dummy_secret",
            authorize_url=AUTH_URL,
            token_url=TOKEN_URL,
        )

        if config_entry.options.get(CONF_LOG_TO_FILESYSTEM, False):
            _log_storage_path = Path(hass.config.config_dir).joinpath(STORAGE_DIR)
        else:
            _log_storage_path = None

        self.api = BoschEBikeOAuthAPI(
            bin=self._bin,
            oauth_session=OAuth2Session(hass, config_entry, implementation),
            log_storage_path=_log_storage_path
        )

        self.has_flow_subscription = False
        self.activity_list = None
        self.last_activity = None

        # bikes with a registered ConnectModule (BCM) can report their last known location
        self.has_bcm = False
        self._LAST_LOCATION_FETCH = -1

        # bikes without can still report a location based on the polyline of the last activity!
        self.location_data = None

        # tracks the single pending delayed-activity-refresh task so we can cancel superseded ones
        self._pending_activity_refresh_task: asyncio.Task | None = None

        """Initialize the coordinator."""
        scan_interval:Final = timedelta(minutes=max(config_entry.options.get(CONF_SCAN_INTERVAL, 5), 1))
        #scan_interval = timedelta(seconds=10)
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{self.bike_id}", update_interval=scan_interval)

    @property
    def bin(self) -> str | None:
        """Get the current access token."""
        return self._bin

    async def int_after_start(self) -> None:
        """We are initializing our data coordinator after Home Assistant startup."""
        if self.hass.is_stopping:
            return False

        self.has_flow_subscription = await self.api.get_subscription_status()

        # only when we have a flow subscription, we should check additionally for bmc
        if self.has_flow_subscription:
            # check if the bike has a registered ConnectModule (BCM) - only then the
            # theft-detection service can provide the last known location
            registrations = await self.api.get_bcm_registrations(bike_id=self.bike_id)
            self.has_bcm = bool(registrations and registrations.get("registrations"))
            _LOGGER.debug(f"int_after_start(): BCM registration found: {self.has_bcm}")

        # check if we already have a bike pass object (important for migrated
        # config entries)
        if self.config_entry.data.get(CONF_BIKE_PASS, None) is None:
            _LOGGER.info("int_after_start(): need to fetch bike pass...")
            pass_data_src = await self.api.get_bike_pass(bike_id=self.bike_id)
            if pass_data_src is not None and pass_data_src.get("frameNumber") is not None:
                pass_data = {CONF_BIKE_PASS: {
                    "frame": pass_data_src.get("frameNumber"),
                    "created_at": pass_data_src.get("createdAt"),
                }}
                _LOGGER.info(f"int_after_start(): fetched bike pass with frame number: {self.bin}")
            else:
                # creating a FAKE-BikePass - to avoid requests on restarts...
                from datetime import datetime, timezone
                # Generate the string and replace the +00:00 offset with Z
                pass_data = {CONF_BIKE_PASS: {
                    "frame": f"NOBIKEPASS_{self.bike_id}",
                    "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
                }}
                _LOGGER.info(f"int_after_start(): Failed to fetch bike pass for bike {self.bike_id}")

            self.hass.config_entries.async_update_entry(self.config_entry, data={**self.config_entry.data, **pass_data})
            self._bin = pass_data.get(CONF_BIKE_PASS, {}).get("frame", self.bike_id)


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
                    self.last_activity = recent_activities[0]
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

        # for our sensor's we keep track of the last activity that we have processed, so we don't process it again on next update...
        if self.activity_list is not None and len(self.activity_list) > 0:
            self.last_activity = self.activity_list[0]
            _LOGGER.debug(f"int_after_start(): set the last_activity to {self.last_activity.get('id')}")

        self.calc_bike_last_location_from_polyline()


    def calc_bike_last_location_from_polyline(self, activity=None):
        if activity is None:
            activity = self.last_activity

        if activity is not None:
            try:
                a_polyline_str = activity.get("attributes", {}).get("polyline")

                if a_polyline_str:
                    decoded_polyline = polyline.decode(a_polyline_str, precision=6)
                    last_location = decoded_polyline[-1]
                    _LOGGER.debug(f"calc_bike_last_location_from_polyline(): last location from last polyline-point: {last_location}")

                    # a simple self-created location object... as it would be returned by the Bosch API
                    self.location_data = {"locations":[{
                        "bikeId": self.bike_id,
                        "latitude": last_location[0],
                        "longitude": last_location[1]
                    }]}

            except BaseException as ex:
                _LOGGER.debug(f"calc_bike_last_location_from_polyline(): error: {type(ex).__name__} - {ex}")


    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Bosch eBike API."""
        if self.hass.is_stopping:
            raise UpdateFailed(f"HASS is stopping - cannot update data")

        try:
            _LOGGER.debug(f"_async_update_data(): === COORDINATOR UPDATE TRIGGERED for bike {self.bike_id} ===")

            # Fetch bike profile (static info + last known battery state)
            profile_data = await self.api.get_bike_profile(self.bike_id)

            if profile_data is None:
                raise UpdateFailed("get_bike_profile() returned no data")

            # Try to fetch live state of charge (only works when bike is online/charging)
            soc_data = None
            if self.has_flow_subscription:
                try:
                    soc_data = await self.api.get_state_of_charge(self.bike_id)
                    _LOGGER.debug("_async_update_data(): Got live state-of-charge data")
                except BoschEBikeAuthError:
                    raise
                except BaseException as err:
                    # This is expected when the bike is offline - not an error
                    _LOGGER.debug(f"_async_update_data(): get_state_of_charge caused {type(err).__name__} - {err}")
            else:
                pass
                # _LOGGER.debug("_async_update_data(): No 'Bosch-Flow'-Subscription - skipping fetching of live state-of-charge data")

            # we check, if the odometer has been updated, and IF this is the case, we will trigger an update of
            # the 'last-activity'
            if self.data is not None:
                last_odometer_val = bosch_data_handler.get_total_distance(self.data)
                new_odometer_val = bosch_data_handler.get_total_distance({KEY_PROFILE: profile_data, KEY_SOC: soc_data})

                if last_odometer_val is not None and new_odometer_val is not None and new_odometer_val > last_odometer_val:
                    _LOGGER.debug(f"_async_update_data(): Updated last processed activity to due to new odometer value changed from '{last_odometer_val}' to '{new_odometer_val}'")

                    # Cancel any previously pending delayed refresh so only the most recent
                    # odometer-change event triggers the final activity update.
                    if self._pending_activity_refresh_task is not None and not self._pending_activity_refresh_task.done():
                        _LOGGER.debug("_async_update_data(): Cancelling previous pending activity refresh task")
                        self._pending_activity_refresh_task.cancel()

                    _LOGGER.debug("_async_update_data(): Scheduling delayed activity refresh in 30s")
                    self._pending_activity_refresh_task = self.hass.async_create_task(
                        self._async_delayed_activity_and_location_refresh(
                            last_known_activity_id = self.last_activity.get("id", "UNKNOWN") if self.last_activity is not None else "UNKNOWN",
                            delay_in_minutes = 1)
                    )

            # check & update the location data from the Bosch API (only when a ConnectModule is registered)
            await self.check_bcm_location()

            new_data = {
                KEY_PROFILE: profile_data,
                KEY_SOC: soc_data,
                KEY_ACTIVITY: self.last_activity,
                KEY_LOCATION: self.location_data
            }

            _LOGGER.debug(f"_async_update_data(): === COORDINATOR UPDATE COMPLETE for bike {self.bike_id} ===")
            return new_data

        except BoschEBikeAuthError as err:
            _LOGGER.error(f"_async_update_data(): Authentication failed - reauthentication required: {err}")
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except BoschEBikeAPIError as err:
            _LOGGER.error(f"_async_update_data():Error fetching bike data: {err}")
            raise UpdateFailed(f"Error communicating with Bosch API: {err}") from err


    async def check_bcm_location(self):
        # Fetch the last known location (throttled - it only changes when the
        # ConnectModule reports home, so we don't need it on every cycle)
        if self.has_bcm:
            now_time = time.time()
            if (now_time - self._LAST_LOCATION_FETCH) >= LOCATION_SCAN_INTERVAL_MINUTES * 60:
                try:
                    new_location_data = await self.api.get_latest_locations(self.bike_id)
                    if new_location_data is not None:
                        self.location_data = new_location_data

                    self._LAST_LOCATION_FETCH = now_time

                except BoschEBikeAuthError:
                    raise
                except BaseException as err:
                    _LOGGER.debug(f"_async_update_data(): get_latest_locations caused {type(err).__name__} - {err}")

    async def _async_delayed_activity_and_location_refresh(self, last_known_activity_id:str, delay_in_minutes: int = 1, total_wait_time_in_minutes: int = 0, max_wait_time_in_minutes: int = 125) -> None:
        """Wait delay_in_minutes, then re-fetch the latest activity and push a coordinator update.

        If a newer call cancels this task while it is sleeping, CancelledError is caught
        and the method returns silently — only the last scheduled task proceeds.

        When the activity id has not changed yet (Bosch backend not yet updated), the task
        reschedules itself with a longer delay up to max_wait_time_in_minutes.

        The default (min) auto cancel activity in the Flow app is 2h = (120min)
        """
        try:
            await asyncio.sleep(delay_in_minutes * 60)
        except asyncio.CancelledError:
            _LOGGER.debug("_async_delayed_activity_and_location_refresh(): Task superseded by a newer one — skipping")
            return

        if self.hass.is_stopping:
            return

        try:
            _LOGGER.debug(f"_async_delayed_activity_and_location_refresh(): Fetching latest activity after delay ({total_wait_time_in_minutes}/{max_wait_time_in_minutes})")

            # now check the recent activities...
            recent_activities = await self.api.get_activity_list_recent(bike_id=self.bike_id, size=1)
            if recent_activities is not None and len(recent_activities) > 0:
                _LOGGER.debug(f"_async_delayed_activity_and_location_refresh(): Fetched RECENT activity list with {len(recent_activities)} entries")
                most_recent_activity = recent_activities[0]

                if most_recent_activity:
                    # try to update the self-created location data...
                    # when the bcm is enabled, then this 'raw' location will be overwritten by the
                    # 'real' location data from the Bosch API in the "if self.has_bcm:" block below
                    # since with the odometer update the _LAST_LOCATION_FETCH ts will be reset!
                    self.calc_bike_last_location_from_polyline(most_recent_activity)

                    if most_recent_activity.get("id") == last_known_activity_id:
                        # ok so the 'most_recent_activity' did not change (yet)...

                        if total_wait_time_in_minutes < max_wait_time_in_minutes:
                            next_delay_in_minutes = min(delay_in_minutes * 2, 15)
                            _LOGGER.debug(f"_async_delayed_activity_and_location_refresh(): Activity id unchanged ({last_known_activity_id}), retrying in {total_wait_time_in_minutes + next_delay_in_minutes} min ({total_wait_time_in_minutes}/{max_wait_time_in_minutes})")
                            self._pending_activity_refresh_task = self.hass.async_create_task(
                                self._async_delayed_activity_and_location_refresh(
                                    last_known_activity_id = last_known_activity_id,
                                    delay_in_minutes = next_delay_in_minutes,
                                    total_wait_time_in_minutes = total_wait_time_in_minutes + next_delay_in_minutes,
                                    max_wait_time_in_minutes = max_wait_time_in_minutes,
                                )
                            )

                            # we are still forcing a possible upcoming bcm-location-check (by normal update_data calls)
                            self._LAST_LOCATION_FETCH = -1
                            return
                        else:
                            _LOGGER.warning(f"_async_delayed_activity_and_location_refresh(): No new activity (id: {last_known_activity_id}) found after {max_wait_time_in_minutes} minutes — giving up")

                    # finally setting the last_activity to the new activity (even if it is the same as before)
                    self.last_activity = most_recent_activity

                    # TOxDO LATER: we might want to update the config_entry with the new last_activity id, so we don't
                    # process it again on next update...

            # when we are updating the location, then we for sure want to update the position at
            # the end of a ride... [new activity created] ?!
            self._LAST_LOCATION_FETCH = -1

            # check (if enabled) & update the location data from the Bosch API (only when a ConnectModule is registered)
            await self.check_bcm_location()

            self.async_set_updated_data({**self.data,
                                         KEY_ACTIVITY: self.last_activity,
                                         KEY_LOCATION: self.location_data})

        except BaseException as err:
            _LOGGER.warning(f"_async_delayed_activity_and_location_refresh(): Failed: {type(err).__name__} - {err}")


class BoschEBikeEntity(CustomFriendlyNameEntity):
    _attr_has_entity_name = True

    def __init__(self, entity_type:str, coordinator: BoschEBikeDataUpdateCoordinator, description: EntityDescription) -> None:
        # make sure we have a valid translation_key...
        if description.translation_key is None:
            description = replace(
                description,
                translation_key = f"{description.key}"
            )
        super().__init__(coordinator, description)
        self.coordinator = coordinator
        self.entity_description = description

        # Set unique ID
        self._attr_unique_id = f"{coordinator.bike_id}_{description.key}"

        # we need also a 'shorter' entity-id
        self.entity_id = f"{entity_type}.bfe_{coordinator.bin.lower()}_{description.key}".lower()

        # Build enhanced device info from component data
        device_info = {
            "identifiers": {(DOMAIN, coordinator.bike_id)},
            "name": coordinator.bike_name,
            "manufacturer": "Bosch",
        }

        # Add component details if available
        drive_unit = bosch_data_handler._get_drive_unit(coordinator.data)
        if len(drive_unit) > 0:
            # Set model from drive unit
            if drive_unit.get("productName"):
                device_info["model"] = drive_unit["productName"]

            # Add software version
            if drive_unit.get("softwareVersion"):
                device_info["sw_version"] = f"DU: {drive_unit['softwareVersion']}"

            # Add serial number
            if drive_unit.get("serialNumber"):
                device_info["serial_number"] = drive_unit["serialNumber"]


        if not device_info.get("model"):
            device_info["model"] = "eBike with/without ConnectModule"

        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.coordinator.data is not None

    def _friendly_name_internal(self) -> str | None:
        """Return the friendly name.
        If has_entity_name is False, this returns self.name
        If has_entity_name is True, this returns device.name + self.name
        """
        name = self.name
        if name is UNDEFINED:
            name = None

        if not self.has_entity_name or not (device_entry := self.device_entry):
            return name

        device_name = device_entry.name_by_user or device_entry.name
        if name is None and self.use_device_name:
            return device_name

        # check if there is a user specified entity name (overwritten)
        if registry_entry := self.registry_entry:
            if registry_entry.has_entity_name and registry_entry.name is not None:
                name = registry_entry.name

        # we overwrite the default impl here and just return our 'name'
        # return f"{device_name} {name}" if device_name else name
        return name
