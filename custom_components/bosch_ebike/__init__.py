"""The Bosch eBike integration."""
import asyncio
import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session, LocalOAuth2Implementation

from .api import BoschEBikeAIOAPI, BoschEBikeOAuthAPI
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
    CONFIG_MINOR_VERSION, CONF_EXPIRES_AT,
)
from .coordinator import BoschEBikeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Platforms to set up
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]

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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bosch eBike from a config entry."""
    _LOGGER.debug("Setting up Bosch eBike integration")

    # creating our OAuth2Session-session...
    implementation = LocalOAuth2Implementation(
        hass,
        DOMAIN,
        client_id=CLIENT_ID,
        client_secret="dummy_secret",
        authorize_url=AUTH_URL,
        token_url=TOKEN_URL,
    )
    session = OAuth2Session(hass, entry, implementation)

    bike_id = entry.data[CONF_BIKE_ID]
    bike_name = entry.data.get(CONF_BIKE_NAME, "eBike")

    # Create API client
    api = BoschEBikeOAuthAPI(session=session)

    # Create update coordinator
    coordinator = BoschEBikeDataUpdateCoordinator(
        hass=hass,
        api=api,
        bike_id=bike_id,
        bike_name=bike_name,
    )

    _LOGGER.info(
        "Created coordinator for %s with update interval: %s",
        bike_name,
        coordinator.update_interval,
    )

    # Fetch initial data
    _LOGGER.info("Performing initial data refresh for %s", bike_name)
    await coordinator.int_after_start()
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.info("Initial data refresh complete for %s", bike_name)

    # Store coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "bike_id": bike_id,
        "bike_name": bike_name,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register options update listener
    entry.add_update_listener(async_update_options)

    _LOGGER.info(
        "Bosch eBike integration setup complete for %s (ID: %s)",
        bike_name,
        bike_id,
    )

    # at least we want to log if somebody updated the config entry...
    entry.async_on_unload(entry.add_update_listener(entry_update_listener))
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Bosch eBike integration")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Remove data
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    if await async_unload_entry(hass, entry):
        await asyncio.sleep(2)
    await async_setup_entry(hass, entry)
