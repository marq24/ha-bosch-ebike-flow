"""API client for Bosch eBike Flow."""
import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, time
from typing import Any
from urllib.parse import urlencode

import aiohttp
import async_timeout

from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from .const import (
    AUTH_URL,
    TOKEN_URL,
    REDIRECT_URI,
    CLIENT_ID,
    SCOPE,

    PROFILE_API_BASE_URL,
    PROFILE_ENDPOINT_BIKE_PROFILE,
    PROFILE_ENDPOINT_STATE_OF_CHARGE,
    PROFILE_ENDPOINT_BIKE_PROFILE_V2,

    IN_APP_PURCHASE_API_BASE_URL,
    IN_APP_PURCHASE_ENDPOINT_STATE,

    ACTIVITY_API_BASE_URL,
    ACTIVITIES_ENDPOINT, BIKEPASS_ENDPOINT_PASSES, BIKEPASS_API_BASE_URL,
)

_LOGGER = logging.getLogger(__name__)


class BoschEBikeAPIError(Exception):
    """Base exception for Bosch eBike API errors."""
    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize the exception with an optional status code."""
        super().__init__(message)
        self.status_code = status_code

class BoschEBikeAuthError(BoschEBikeAPIError):
    """Authentication error."""


class BoschEBikeAIOAPI:
    """API client for Bosch eBike Flow."""

    def __init__(
        self,
        session: aiohttp.ClientSession
    ) -> None:
        """Initialize the API client."""
        self._aoi_session = session
        self._access_token = None
        self._refresh_token = None
        self._token_expires_at: datetime | None = None

    @staticmethod
    def generate_pkce_pair() -> tuple[str, str]:
        """Generate PKCE code verifier and challenge."""
        # Generate code verifier (43-128 characters)
        code_verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode('utf-8').rstrip('=')

        # Generate code challenge
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')

        return code_verifier, code_challenge

    @staticmethod
    def build_auth_url(code_challenge: str) -> str:
        """Build the OAuth authorization URL."""
        # Generate random nonce and state for security
        nonce = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        state = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPE,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "kc_idp_hint": "skid",
            "prompt": "login",
            "nonce": nonce,
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def exchange_code_for_token(
            self,
            authorization_code: str,
            code_verifier: str,
    ) -> dict[str, Any]:
        """Exchange authorization code for access token."""
        data = {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": authorization_code,
            "code_verifier": code_verifier,
            "redirect_uri": REDIRECT_URI,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }

        try:
            async with async_timeout.timeout(10):
                async with self._aoi_session.post(
                        TOKEN_URL,
                        data=data,
                        headers=headers,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        _LOGGER.error("Token exchange failed: %s - %s", response.status, error_text)
                        raise BoschEBikeAuthError(f"Token exchange failed ({response.status}): {error_text}")

                    token_data = await response.json()

                    self._access_token = token_data["access_token"]
                    self._refresh_token = token_data["refresh_token"]

                    # Calculate expiration time
                    expires_in = token_data.get("expires_in", 7200)  # Default 2 hours
                    self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

                    _LOGGER.debug("Successfully exchanged code for tokens")
                    return token_data

        except aiohttp.ClientError as err:
            _LOGGER.error("Error exchanging code for token: %s", err)
            raise BoschEBikeAuthError(f"Failed to exchange code: {err}") from err

    async def _aio_api_request(
            self,
            method: str,
            endpoint: str,
            base: str = PROFILE_API_BASE_URL,
            **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an API request."""
        if not self._access_token:
            raise BoschEBikeAuthError("No access token available")

        headers = kwargs.pop("headers", {})
        headers.update({
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        })

        url = f"{base}{endpoint}"

        try:
            async with async_timeout.timeout(10):
                async with self._aoi_session.request(
                        method,
                        url,
                        headers=headers,
                        **kwargs,
                ) as response:
                    if response.status == 401:
                        # Try to refresh token and retry once
                        _LOGGER.debug("Got 401, attempting token refresh")
                        await self.refresh_access_token()

                        headers["Authorization"] = f"Bearer {self._access_token}"
                        async with self._aoi_session.request(
                                method,
                                url,
                                headers=headers,
                                **kwargs,
                        ) as retry_response:
                            retry_response.raise_for_status()
                            return await retry_response.json()

                    response.raise_for_status()
                    return await response.json()

        except aiohttp.ClientResponseError as err:
            if err.status == 404:
                _LOGGER.debug("Resource not found (404): %s", endpoint)
                return None
            _LOGGER.error("API request error: %s", err)
            raise BoschEBikeAPIError(f"API request failed: {err}", err.status) from err
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error: %s", err)
            raise BoschEBikeAPIError(f"Connection failed: {err}") from err

    async def get_bikes(self) -> list[dict[str, Any]]:
        """Get all bikes for the authenticated user."""
        _LOGGER.debug(f"get_bikes(): Fetching bike list")
        response = await self._aio_api_request("GET", PROFILE_ENDPOINT_BIKE_PROFILE)

        if not response:
            return []

        bikes = response.get("data", [])
        _LOGGER.debug(f"get_bikes(): Found{len(bikes)} bike(s)")
        return bikes

    async def get_bike_pass(self, bike_id:str):
        """Get all bikes for the authenticated user."""
        _LOGGER.debug(f"get_bike_pass(): Fetching bike list")
        response = await self._aio_api_request("GET", BIKEPASS_ENDPOINT_PASSES, BIKEPASS_API_BASE_URL)
        pass_items = response.get("bikePasses", [])
        for item in pass_items:
            a_bike_id = item.get("bikeId")
            if a_bike_id == bike_id:
                return item
        return None

    @property
    def access_token(self) -> str | None:
        """Get the current access token."""
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        """Get the current refresh token."""
        return self._refresh_token


class BoschEBikeOAuthAPI:
    """API client for Bosch eBike Flow."""
    def __init__(
            self,
            _oauth_session: OAuth2Session
    ) -> None:
        """Initialize the API client."""
        self._oauth_session = _oauth_session
        self._last_update_time = 0

    async def _oauth_api_request(self, method: str, endpoint: str, base: str = PROFILE_API_BASE_URL, **kwargs: Any) -> dict[str, Any]:

        url = f"{base}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers.update({"Content-Type": "application/json"})
        res = await self._oauth_session.async_request(method=method, headers=headers, url=url)
        try:
            res.raise_for_status()
            response_data = await res.json()
            if response_data is not None:
                _LOGGER.debug(f"_oauth_api_request_{method}(): {len(response_data)} - {response_data.keys() if response_data is not None else 'None'}")
            else:
                _LOGGER.debug(f"_oauth_api_request_{method}(): No data received!")

            return response_data

        except aiohttp.ClientResponseError as err:
            if err.status == 429:
                _LOGGER.debug(f"_oauth_api_request_{type}():{url} caused {err.status} - rate limit exceeded - should sleeping for 15 seconds")
                self._last_update_time = time.monotonic()
                return {}
            elif err.status == 404:
                _LOGGER.debug(f"_oauth_api_request_{method}(): Resource not found (404): {endpoint}")
            else:
                _LOGGER.error(f"_oauth_api_request_{method}(): API request error: {type(err).__name__} {err}")
            raise BoschEBikeAPIError(f"API request failed: {err}", err.status) from err

        except aiohttp.ClientError as err:
            _LOGGER.error(f"_oauth_api_request_{method}(): Connection error: {type(err).__name__} {err}")
            raise BoschEBikeAPIError(f"Connection failed: {err}") from err

        except BaseException as err:
            _LOGGER.info(f"_oauth_api_request_{method}():{url} caused {type(err).__name__} {err}")


    async def get_subscription_status(self) -> dict[str, Any]:
        try:
            _LOGGER.debug(f"get_subscription_status(): Fetching subscription status")
            response = await self._oauth_api_request(
                "GET",
                endpoint = IN_APP_PURCHASE_ENDPOINT_STATE,
                base = IN_APP_PURCHASE_API_BASE_URL
            )
            return response is not None and response.get("status", False)
        except BaseException as err:
            _LOGGER.warning(f"get_subscription_status(): Fetching subscription status caused {type(err).__name__} - {err} - assuming no subscription")
            return False


    async def get_bike_profile(self, bike_id: str) -> dict[str, Any] | None:
        """Get detailed bike profile."""
        _LOGGER.debug(f"get_bike_profile(): Fetching bike profile for {bike_id}",)
        response = await self._oauth_api_request(
            "GET",
            f"{PROFILE_ENDPOINT_BIKE_PROFILE_V2}/{bike_id}"
        )
        # make sure that V1 and V2 are compatible with each other...
        if response and "data" in response and "attributes" in response["data"]:
            response["data"]["attributes"]

        return response


    async def get_state_of_charge(self, bike_id: str) -> dict[str, Any] | None:
        """Get state of charge data from ConnectModule."""
        _LOGGER.debug(f"get_state_of_charge(): Fetching state of charge for {bike_id}")
        try:
            response = await self._oauth_api_request(
                "GET",
                f"{PROFILE_ENDPOINT_STATE_OF_CHARGE}/{bike_id}"
            )
            return response
        except BoschEBikeAPIError as err:
            if err.status_code == 404:
                # 404 is expected when bike is offline
                _LOGGER.debug(f"get_state_of_charge(): Live state-of-charge not available (bike offline?)")
                return None
            else:
                raise err

    async def get_activity_list_recent(self, bike_id:str) -> list[dict[str, Any]]:
        """Get the last recent activity list for a bike."""
        _LOGGER.debug(f"get_activity_list_recent(): Fetching recent activity list for bike {bike_id}")
        activities_by_id: dict[str, dict[str, Any]] = {}
        response = await self._oauth_api_request(
            "GET",
            f"{ACTIVITIES_ENDPOINT}?page=0&size=30&sort=-startTime&include-polyline=false",
            ACTIVITY_API_BASE_URL
        )
        page_items = response.get("data", [])
        for item in page_items:
            activity_id = item.get("id")
            if activity_id:
                if activity_id not in activities_by_id:
                    if item.get("attributes", {}).get("bikeId") == bike_id:
                        activities_by_id[activity_id] = item
                else:
                    _LOGGER.warning(f"get_activity_list_recent(): Duplicate activity ID {activity_id} found, skipping it")

        return list(activities_by_id.values())


    async def get_activity_list_complete(self, bike_id:str) -> list[dict[str, Any]]:
        """Fetch all activities by iterating through all available pages."""
        activities_by_id: dict[str, dict[str, Any]] = {}
        current_page = 0
        total_pages = 1  # Start with 1 to enter the loop

        while current_page < total_pages:
            _LOGGER.debug(f"get_activity_list_complete(): Fetching activity page {current_page}")

            # Construct the endpoint with pagination parameters
            response = await self._oauth_api_request(
                "GET",
                f"{ACTIVITIES_ENDPOINT}?page={current_page}&size=30&sort=-startTime&include-polyline=false",
                base=ACTIVITY_API_BASE_URL
            )

            if not response:
                break

            # Add activities from the current page to our list
            # Assuming activities are in a 'data' or 'items' key based on standard Bosch API patterns
            page_items = response.get("data", [])
            for item in page_items:
                activity_id = item.get("id")
                if activity_id:
                    if activity_id not in activities_by_id:
                        if item.get("attributes", {}).get("bikeId") == bike_id:
                            activities_by_id[activity_id] = item
                    else:
                        _LOGGER.warning(f"get_activity_list_complete(): Duplicate activity ID {activity_id} found, skipping it")

            # Update pagination info from the meta block
            meta = response.get("meta", {})
            total_pages = meta.get("pages", 0)
            current_page += 1
            _LOGGER.debug(f"get_activity_list_complete(): Progress: {current_page}/{total_pages} pages collected")

        return list(activities_by_id.values())


    async def get_bike_pass(self, bike_id:str):
        """Get the last recent activity list for a bike."""
        _LOGGER.debug(f"get_bike_pass(): Fetching bike pass for bike {bike_id}")
        response = await self._oauth_api_request(
            "GET",
            BIKEPASS_ENDPOINT_PASSES,
            BIKEPASS_API_BASE_URL
        )
        # sample_data = {
        #     "bikePasses": [
        #         {
        #             "bikeId": "000000-000-0000-0000-000000000000",
        #             "files": [
        #                 {
        #                     "bikeId": "000000-000-0000-0000-000000000000",
        #                     "fileId": "ff0000-0f0-f00f-0ff0-0000000000ff",
        #                     "fileType": "BIKE_INVOICE",
        #                     "link": "https://bike-pass.prod.connected-biking.cloud/v1/files/{bikeId}/{fileId}",
        #                     "createdAt": "2024-12-07T12:09:45Z",
        #                     "updatedAt": "2024-12-07T12:09:46Z"
        #                 },
        #                 {
        #                     "bikeId": "000000-000-0000-0000-000000000000",
        #                     "fileId": "ff0000-0f0-f00f-0ff0-0000000000ff",
        #                     "fileType": "BIKE_INVOICE",
        #                     "link": "https://bike-pass.prod.connected-biking.cloud/v1/files/{bikeId}/{fileId}",
        #                     "createdAt": "2024-12-07T12:09:45Z",
        #                     "updatedAt": "2024-12-07T12:09:47Z"
        #                 }
        #             ],
        #             "createdAt": "2024-12-07T12:08:49Z",
        #             "updatedAt": "2024-12-07T12:09:45Z",
        #             "frameNumber": "XXXYXXYXYXXYYYYY"
        #         }
        #     ]
        # }

        pass_items = response.get("bikePasses", [])
        for item in pass_items:
            a_bike_id = item.get("bikeId")
            if a_bike_id == bike_id:
                return item

        return None


    # async def get_battery_data(self, bike_id: str) -> dict[str, Any]:
    #     """Get comprehensive battery data (tries both endpoints)."""
    #     # Try state-of-charge first (faster, from ConnectModule)
    #     soc_data = await self.get_state_of_charge(bike_id)
    #
    #     # Always get bike profile for complete data
    #     profile_data = await self.get_bike_profile(bike_id)
    #
    #     if not profile_data:
    #         raise BoschEBikeAPIError(f"get_battery_data(): Failed to fetch bike profile for {bike_id}")
    #
    #     battery = profile_data.get("batteries", [{}])[0]
    #     drive_unit = profile_data.get("driveUnit", {})
    #
    #     # Build combined data structure
    #     data = {
    #         "bike_id": bike_id,
    #         "source": "combined",
    #         "timestamp": datetime.now().isoformat(),
    #
    #         # Battery basics (prefer SoC data if available)
    #         "battery_level": battery.get("batteryLevel"),
    #         "remaining_energy": battery.get("remainingEnergy"),
    #         "total_energy": battery.get("totalEnergy"),
    #         "is_charging": battery.get("isCharging"),
    #         "is_charger_connected": battery.get("isChargerConnected"),
    #         "charge_cycles": battery.get("numberOfFullChargeCycles", {}).get("total"),
    #
    #         # Bike info
    #         "brand": profile_data.get("brandName"),
    #         "odometer": drive_unit.get("totalDistanceTraveled"),
    #         "is_locked": drive_unit.get("lock", {}).get("isLocked"),
    #
    #         # From ConnectModule (if available)
    #         "connect_module_data": None,
    #     }
    #
    #     # Override/add data from state-of-charge if available
    #     if soc_data:
    #         data["connect_module_data"] = soc_data
    #         data["battery_level"] = soc_data.get("stateOfCharge", data["battery_level"])
    #         data["is_charging"] = soc_data.get("chargingActive", data["is_charging"])
    #         data["is_charger_connected"] = soc_data.get("chargerConnected", data["is_charger_connected"])
    #         data["remaining_energy"] = soc_data.get("remainingEnergyForRider", data["remaining_energy"])
    #         data["reachable_range"] = soc_data.get("reachableRange", [])
    #         data["odometer"] = soc_data.get("odometer", data["odometer"])
    #         data["last_update"] = soc_data.get("stateOfChargeLatestUpdate")
    #
    #     return data