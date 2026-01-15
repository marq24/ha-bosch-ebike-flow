"""Config flow for Bosch eBike integration."""
import logging
import time
from typing import Any, Final
from urllib.parse import urlparse, parse_qs

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BoschEBikeAIOAPI, BoschEBikeAuthError, BoschEBikeAPIError
from .const import (
    DOMAIN,
    CONFIG_VERSION,
    CONFIG_MINOR_VERSION,
    CONF_BIKE_ID,
    CONF_BIKE_NAME,
    OAUTH_TOKEN_KEY,
    CONF_EXPIRES_AT,
    CONF_EXPIRES_IN,
    CONF_REFRESH_EXPIRES_IN,
    CONF_REFRESH_EXPIRES_AT
)

_LOGGER = logging.getLogger(__name__)

CONF_CODE: Final = "code"

def _build_bike_name_from_v1(bike: dict[str, Any]) -> str:
    """Build a descriptive bike name from bike data."""
    attrs = bike.get("attributes", {})
    brand_name = attrs.get("brandName", "eBike")
    drive_unit = attrs.get("driveUnit", {})
    drive_unit_name = drive_unit.get("productName")

    # Try to get frame number for uniqueness
    frame_number = attrs.get("frameNumber")

    if drive_unit_name:
        # e.g., "Cube (Performance CX)"
        return f"{brand_name} ({drive_unit_name})"
    elif frame_number and len(frame_number) >= 4:
        # e.g., "Cube (...1234)" - last 4 digits of frame number
        return f"{brand_name} (...{frame_number[-4:]})"
    else:
        # Just the brand name
        return brand_name


class BoschEBikeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bosch eBike."""

    VERSION = CONFIG_VERSION
    MINOR_VERSION = CONFIG_MINOR_VERSION

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._code_verifier: str | None = None
        self._code_challenge: str | None = None
        self._bikes: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # Generate PKCE parameters
        self._code_verifier, self._code_challenge = BoschEBikeAIOAPI.generate_pkce_pair()

        # Build authorization URL
        auth_url = BoschEBikeAIOAPI.build_auth_url(self._code_challenge)

        # Store for next step
        self.context["code_verifier"] = self._code_verifier

        # Show auth URL and ask for code manually
        return self.async_show_form(
            step_id="auth",
            description_placeholders={"auth_url": auth_url},
            data_schema=vol.Schema({
                vol.Required(CONF_CODE): str,
            }),
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual authorization code entry."""
        if user_input is None:
            return self.async_abort(reason="missing_code")

        # Extract authorization code from user input
        authorization_code = user_input[CONF_CODE].strip()

        # The user might have pasted the complete URL... so we try to parse it
        if "code=" in authorization_code:
            query_params = parse_qs(urlparse(authorization_code).query)
            if "code" not in query_params:
                return self.async_abort(reason="missing_code")
            else:
                authorization_code = query_params["code"][0]

        # Get code_verifier from context
        code_verifier = self.context.get("code_verifier")
        if not code_verifier:
            return self.async_abort(reason="missing_verifier")

        errors = {}

        try:
            # Exchange code for tokens
            api = BoschEBikeAIOAPI(session=async_get_clientsession(self.hass))

            token_data = await api.exchange_code_for_token(
                authorization_code,
                code_verifier,
            )

            # we must ensure that 'expires_at' is present...
            try:
                token_data[CONF_EXPIRES_IN] = int(token_data[CONF_EXPIRES_IN])
            except ValueError as err:
                _LOGGER.warning(f"Error converting {CONF_EXPIRES_IN} to int: {err}")
                return self.async_abort(reason="oauth_error")
            token_data[CONF_EXPIRES_AT] = time.time() + token_data[CONF_EXPIRES_IN]

            if CONF_REFRESH_EXPIRES_IN in token_data:
                try:
                    token_data[CONF_REFRESH_EXPIRES_IN] = int(token_data[CONF_REFRESH_EXPIRES_IN])
                    if token_data[CONF_REFRESH_EXPIRES_IN] > 0:
                        token_data[CONF_REFRESH_EXPIRES_AT] = time.time() + token_data[CONF_REFRESH_EXPIRES_IN]
                    else:
                        _LOGGER.info(f"Received an ENDLESS valid refresh token! - *sigh* this is security design of 1986")
                except ValueError as err:
                    _LOGGER.warning(f"Error converting {CONF_REFRESH_EXPIRES_IN} to int: {err}")

            # Fetch bikes
            self._bikes = await api.get_bikes()

            if not self._bikes:
                _LOGGER.error("No bikes found for this account")
                errors["base"] = "no_bikes"

            if not errors:
                # Store tokens for next step
                self.context[OAUTH_TOKEN_KEY] = token_data.copy()

                # If only one bike, auto-select it
                if len(self._bikes) == 1:
                    bike = self._bikes[0]
                    bike_id = bike["id"]
                    bike_name = _build_bike_name_from_v1(bike)

                    return self.async_create_entry(
                        title=bike_name,
                        data={
                            CONF_BIKE_ID: bike_id,
                            CONF_BIKE_NAME: bike_name,
                            OAUTH_TOKEN_KEY: self.context[OAUTH_TOKEN_KEY]
                        },
                    )
                else:
                    # Multiple bikes - let user choose
                    return await self.async_step_select_bike()

        except BoschEBikeAuthError as err:
            _LOGGER.error("Authentication failed: %s", err)
            errors["base"] = "auth_error"
        except BoschEBikeAPIError as err:
            _LOGGER.error("API error: %s", err)
            errors["base"] = "api_error"
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error: %s", err)
            errors["base"] = "unknown"

        # Show form again with errors or regenerate auth URL
        auth_url = BoschEBikeAIOAPI.build_auth_url(self._code_challenge)
        return self.async_show_form(
            step_id="auth",
            description_placeholders={"auth_url": auth_url},
            data_schema=vol.Schema({
                vol.Required(CONF_CODE): str,
            }),
            errors=errors,
        )

    async def async_step_select_bike(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle bike selection when multiple bikes exist."""
        if user_input is not None:
            # Get selected bike
            bike_id = user_input[CONF_BIKE_ID]

            # Find bike details
            bike = next((b for b in self._bikes if b["id"] == bike_id), None)
            if not bike:
                return self.async_abort(reason="bike_not_found")

            bike_name = _build_bike_name_from_v1(bike)

            return self.async_create_entry(
                title=bike_name,
                data={
                    CONF_BIKE_ID: bike_id,
                    CONF_BIKE_NAME: bike_name,
                    OAUTH_TOKEN_KEY: self.context.get(OAUTH_TOKEN_KEY)
                },
            )

        # Build bike selection options
        bike_options = {
            bike["id"]: _build_bike_name_from_v1(bike)
            for bike in self._bikes
        }

        return self.async_show_form(
            step_id="select_bike",
            data_schema=vol.Schema({
                vol.Required(CONF_BIKE_ID): vol.In(bike_options),
            }),
        )
