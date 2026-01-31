"""The Bosch eBike integration."""
import asyncio
import logging
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Final

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform, CONF_ACCESS_TOKEN, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session, LocalOAuth2Implementation
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import BoschEBikeAIOAPI, BoschEBikeOAuthAPI, BoschEBikeAPIError
from .bosch_data_handler import KEY_PROFILE, KEY_SOC
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
)

_LOGGER = logging.getLogger(__name__)

KEY_COORDINATOR: Final  = "coordinator"

# Platforms to set up
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

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
            hass.data[DOMAIN].pop(config_entry.entry_id)

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
        self._bin = config_entry.data.get(CONF_BIKE_PASS, {}).get("frame", self.bike_id)

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

        """Initialize the coordinator."""
        scan_interval:Final = timedelta(minutes=max(config_entry.options.get(CONF_SCAN_INTERVAL, 5), 1))
        #scan_interval = timedelta(seconds=10)
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{self.bike_id}", update_interval=scan_interval)

    @property
    def bin(self) -> str | None:
        """Get the current access token."""
        return self._bin

    async def int_after_start(self) -> None:
        if self.hass.is_stopping:
            return False

        """We are initializing our data coordinator after Home Assistant startup."""
        self.has_flow_subscription = await self.api.get_subscription_status()

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
                self.hass.config_entries.async_update_entry(self.config_entry, data={**self.config_entry.data, **pass_data})
                self._bin = pass_data.get(CONF_BIKE_PASS, {}).get("frame", self.bike_id)
                _LOGGER.info(f"int_after_start(): fetched bike pass with frame number: {self.bin}")

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
        if self.hass.is_stopping:
            raise UpdateFailed(f"HASS is stopping - cannot update data")

        """Fetch data from Bosch eBike API."""
        try:
            _LOGGER.debug(f"_async_update_data(): === COORDINATOR UPDATE TRIGGERED for bike {self.bike_id} ===")

            # Fetch bike profile (static info + last known battery state)
            profile_data = await self.api.get_bike_profile(self.bike_id)

            # Try to fetch live state of charge (only works when bike is online/charging)
            soc_data = None
            if self.has_flow_subscription:
                try:
                    soc_data = await self.api.get_state_of_charge(self.bike_id)
                    _LOGGER.debug("_async_update_data(): Got live state-of-charge data")
                except BaseException as err:
                    # This is expected when the bike is offline - not an error
                    _LOGGER.debug(f"_async_update_data(): get_state_of_charge caused {type(err).__name__} - {err}")
            else:
                pass
                # _LOGGER.debug("_async_update_data(): No 'Bosch-Flow'-Subscription - skipping fetching of live state-of-charge data")

            new_data = {
                KEY_PROFILE: profile_data,
                KEY_SOC: soc_data
            }
            _LOGGER.debug(f"_async_update_data(): === COORDINATOR UPDATE COMPLETE for bike {self.bike_id} ===")
            return new_data

        except BoschEBikeAPIError as err:
            _LOGGER.error(f"_async_update_data():Error fetching bike data: {err}")
            raise UpdateFailed(f"Error communicating with Bosch API: {err}") from err

        return None