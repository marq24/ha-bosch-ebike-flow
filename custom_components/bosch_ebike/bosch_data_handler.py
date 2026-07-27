import logging
from datetime import datetime, timezone
from typing import Any, Final

_LOGGER = logging.getLogger(__name__)

KEY_TOTAL_DISTANCE: Final = "total_distance"
KEY_SOC: Final = "soc"
KEY_PROFILE: Final = "profile"
KEY_ACTIVITY: Final = "last_activity"
KEY_LOCATION: Final = "location"

# Assist mode code to display name mapping
ASSIST_MODE_NAMES: dict[str, str] = {
    # G-series drive units
    "A100G0AUTO": "AUTO",
    "A100GAAAA0": "TURBO",
    "A100GAAAB0": "eMTB",
    "A100GAAAC0": "TOUR",
    "A100GAAAD0": "ECO",
    "A100GAAAF0": "TOUR+",
    "A100ECOP38": "ECO+",
    # M-series drive units
    "A100M00040": "ECO",
    "A100ECOP37": "ECO+",
    "A100M00030": "TOUR",
    "A100MAAAA0": "TOUR+",
    "A100M00020": "SPORT",
    "A100M00010": "TURBO",
    "A100M0AUTO": "AUTO",
    "A100EAAAB0": "eMTB",
    "A100MSPIC7": "eMTB+",
    "A100MSPIC8": "eMTB+",
    # E-series Performance Line SX
    "A100E10040": "ECO",
    "A100E1AAA0": "TOUR+",
    "A100ESPNT0": "SPRINT",
    "A100E10010": "TURBO",
    # M3-series drive units
    "A100M3AUTO": "AUTO",
    "A100M30020": "TURBO",
    "A100M3AAB0": "eMTB",
    "A100M40010": "TURBO",
    "A100M30040": "ECO",
    "A100M3AAA0": "TOUR+",
    "A100M40040": "ECO",
}


def build_bike_name_from_api_profile_v1_endpoint(bike: dict[str, Any]) -> str:
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


def _get_drive_unit(data: dict[str, Any]) -> dict[str, Any]:
    """Extract drive unit data from bike data."""
    return data.get(KEY_PROFILE, {}).get("driveUnit") or {}


def _get_first_battery(data: dict[str, Any]) -> dict[str, Any]:
    """Extract first battery data from bike data."""
    batteries = data.get(KEY_PROFILE, {}).get("batteries", [])
    return batteries[0] if batteries else {}


def get_battery_reachable_min_range(data: dict[str, Any]):
    soc_data = data.get(KEY_SOC)
    if soc_data:
        reachable_range_raw = soc_data.get("reachableRange")
        if isinstance(reachable_range_raw, list) and len(reachable_range_raw) > 0:
            for x in reversed(reachable_range_raw):
                if x != 0:
                    return x
            return 0
        elif isinstance(reachable_range_raw, (int, float)):
            return reachable_range_raw
    else:
        ranges = sorted(
            [
                int(item["reachableRange"])
                for item in _get_drive_unit(data).get("driveUnitAssistModes", {})
            ],
            reverse=True,
        )
        if ranges:
            for x in reversed(ranges):
                if x != 0:
                    return x
            return 0
    return None


def get_battery_reachable_max_range(data: dict[str, Any]):
    soc_data = data.get(KEY_SOC)
    if soc_data:
        reachable_range_raw = soc_data.get("reachableRange")
        if isinstance(reachable_range_raw, list) and len(reachable_range_raw) > 0:
            return reachable_range_raw[0]
        elif isinstance(reachable_range_raw, (int, float)):
            return reachable_range_raw
    else:
        ranges = sorted(
            [
                int(item["reachableRange"])
                for item in _get_drive_unit(data).get("driveUnitAssistModes", {})
            ],
            reverse=True,
        )
        if ranges:
            return ranges[0]
    return None


def get_battery_charging(data: dict[str, Any]) -> bool:
    soc_data = data.get(KEY_SOC)
    if soc_data and soc_data.get("chargingActive") is not None:
        return bool(soc_data.get("chargingActive"))

    return bool(_get_first_battery(data).get("isCharging", False))


def get_charger_connected(data: dict[str, Any]) -> bool:
    soc_data = data.get(KEY_SOC)
    if soc_data and soc_data.get("chargerConnected") is not None:
        return bool(soc_data.get("chargerConnected"))

    return bool(_get_first_battery(data).get("isChargerConnected", False))


def get_lock_enabled(data: dict[str, Any]):
    lock = _get_drive_unit(data).get("lock") or {}
    is_locked = lock.get("isLocked")
    if is_locked is not None:
        return is_locked
    return lock.get("isEnabled")


def get_alarm_enabled(data: dict[str, Any]):
    connected_module = data.get(KEY_PROFILE, {}).get("connectedModule") or {}
    return connected_module.get("isAlarmFeatureEnabled")


def get_battery_level(data: dict[str, Any]):
    soc_data = data.get(KEY_SOC)
    if soc_data and soc_data.get("stateOfCharge") is not None:
        return soc_data.get("stateOfCharge")

    return _get_first_battery(data).get("batteryLevel")


def get_battery_remaining_energy(data: dict[str, Any]):
    soc_data = data.get(KEY_SOC)
    if soc_data and soc_data.get("remainingEnergyForRider") is not None:
        return soc_data.get("remainingEnergyForRider")

    return _get_first_battery(data).get("remainingEnergy")


def get_battery_capacity(data: dict[str, Any]):
    return _get_first_battery(data).get("totalEnergy")


def get_total_distance(data: dict[str, Any]):
    soc_data = data.get(KEY_SOC)
    a_val = None
    if soc_data and soc_data.get("odometer", None) is not None:
        a_val = soc_data.get("odometer")
    else:
        a_val = _get_drive_unit(data).get("totalDistanceTraveled", None)

    if a_val is not None:
        return round(a_val / 1000, 2)
    return None


def get_charge_cycles(data: dict[str, Any]):
    return _get_first_battery(data).get("numberOfFullChargeCycles", {}).get("total")


def get_charge_cycles_attr(data: dict[str, Any]):
    cycles = _get_first_battery(data).get("numberOfFullChargeCycles", {})

    attrs = {}
    val_on_bike = cycles.get("onBike")
    val_off_bike = cycles.get("offBike")

    if val_on_bike:
        attrs["onBike"] = val_on_bike
    if val_off_bike:
        attrs["offBike"] = val_off_bike

    return attrs if len(attrs) > 0 else None


def get_lifetime_energy_delivered(data: dict[str, Any]):
    a_val = _get_first_battery(data).get("deliveredWhOverLifetime")
    if a_val:
        return round(a_val / 1000, 2)
    return None


def get_motor_hours(data: dict[str, Any]):
    power_on_time = _get_drive_unit(data).get("powerOnTime") or {}
    return power_on_time.get("total")


def get_motor_hours_attr(data: dict[str, Any]):
    power_on_time = _get_drive_unit(data).get("powerOnTime") or {}
    val_with_motor_support = power_on_time.get("withMotorSupport")
    return (
        {"withMotorSupport": val_with_motor_support}
        if val_with_motor_support is not None
        else None
    )


def get_drive_unit_software_version(data: dict[str, Any]):
    return _get_drive_unit(data).get("softwareVersion")


def get_battery_software_version(data: dict[str, Any]):
    return _get_first_battery(data).get("softwareVersion")


def get_connected_module_software_version(data: dict[str, Any]):
    connected_module = data.get(KEY_PROFILE, {}).get("connectedModule") or {}
    return connected_module.get("softwareVersion")


def get_remote_control_software_version(data: dict[str, Any]):
    remote_control = data.get(KEY_PROFILE, {}).get("remoteControl") or {}
    return remote_control.get("softwareVersion")


def _get_last_ride(data: dict[str, Any]) -> dict[str, Any]:
    """Extract the attributes of the most recent activity."""
    return (data.get(KEY_ACTIVITY) or {}).get("attributes") or {}


def get_last_ride_distance(data: dict[str, Any]):
    a_val = _get_last_ride(data).get("distance")
    if a_val:
        return round(a_val / 1000, 2)
    return None


last_ride_dist_attrs = [
    "timeZoneOfActivity",
    "durationWithoutStops",
    "title",
    "activityType",
    "averageSpeed",
    "maximumSpeed",
    "averageCadence",
    "maximumCadence",
    "averageRiderPower",
    "maximumRiderPower",
    "averageHeartRate",
    "maximumHeartRate",
    "elevationGain",
    "elevationLoss",
    "caloriesBurnt",
    "riderEnergyShare",
    "totalDriverConsumptionPercentage",
    "totalBatteryConsumptionPercentage",
    "co2EmissionsGrams",
    "co2EmissionsCarEquivalentGrams",
    "assistModeUsage",
    "brakeEvents",
    "trickStatistics",
]

last_ride_dist_ignore_attrs = [
    "distance",
    "startOdometer",
    "startTime",
    "endTime",
    "polyline",
    "bikeId",
]


def get_last_ride_distance_attr(data: dict[str, Any]):
    ride = _get_last_ride(data)

    attrs = {}
    start_time = ride.get("startTime")
    if start_time:
        if isinstance(start_time, (int, float)):
            # the API returns epoch seconds - guard against milliseconds just in case
            if start_time > 1e12:
                start_time = start_time / 1000
            attrs["startTime"] = datetime.fromtimestamp(start_time, tz=timezone.utc)
        elif isinstance(start_time, str):
            attrs["startTime"] = start_time

    end_time = ride.get("endTime")
    if end_time:
        if isinstance(end_time, (int, float)):
            # the API returns epoch seconds - guard against milliseconds just in case
            if end_time > 1e12:
                end_time = end_time / 1000
            attrs["endTime"] = datetime.fromtimestamp(end_time, tz=timezone.utc)
        elif isinstance(end_time, str):
            attrs["endTime"] = end_time

    # distance = ride.get("distance")
    # if distance:
    #     attrs["distance"] = round(distance / 1000, 2)

    start_odometer = ride.get("startOdometer")
    if start_odometer:
        attrs["startOdometer"] = round(start_odometer / 1000, 2)

    # we want a certain order of the attributes (YES that's quite silly - but I am human!)
    for attr in last_ride_dist_attrs:
        val = ride.get(attr)
        if val:
            attrs[attr] = val

    # getting any additional attributes (that we don't know yet)...
    for a_key in ride.keys():
        if a_key not in attrs and a_key not in last_ride_dist_ignore_attrs:
            val = ride.get(a_key)
            if val:
                attrs[a_key] = val

    return attrs if len(attrs) > 0 else None


def _get_latest_location(data: dict[str, Any]) -> dict[str, Any]:
    """Extract the most recent location entry from the theft-detection data."""
    locations = (data.get(KEY_LOCATION) or {}).get("locations")
    if isinstance(locations, list) and len(locations) > 0:
        return locations[0]
    return {}


def get_location_latitude(data: dict[str, Any]):
    return _get_latest_location(data).get("latitude")


def get_location_longitude(data: dict[str, Any]):
    return _get_latest_location(data).get("longitude")


def get_location_accuracy(data: dict[str, Any]):
    return _get_latest_location(data).get("horizontalAccuracy")


location_ignore_attrs = ["latitude", "longitude", "horizontalAccuracy", "bikeId"]


def get_location_attr(data: dict[str, Any]):
    location = _get_latest_location(data)
    attrs = {}
    for a_key in location.keys():
        if a_key not in location_ignore_attrs:
            val = location.get(a_key)
            if val:
                attrs[a_key] = val

    return attrs if len(attrs) > 0 else None


def get_reachable_ranges_per_mode(data: dict[str, Any]) -> list[dict]:
    """Extract reachable range per assist mode.

    Returns a list of dicts in order: [
        {"name": "ECO", "range_km": 86.0, "index": 0},
        {"name": "TOUR", "range_km": 67.0, "index": 1},
        ...
    ]

    Prefers reachableRange from SOC API array if available,
    otherwise uses per-mode reachableRange from profile.
    """
    modes = []
    drive_unit = _get_drive_unit(data)
    assist_modes = drive_unit.get("driveUnitAssistModes", [])

    # Get the array of reachable ranges from SOC response (preferred)
    reachable_range_array = []
    soc_data = data.get(KEY_SOC)
    if soc_data:
        reachable_range_raw = soc_data.get("reachableRange")
        if isinstance(reachable_range_raw, list):
            reachable_range_array = reachable_range_raw

    # Map modes to their ranges
    # Track output index separately from enumerate to handle skipped modes
    output_index = 0
    for mode in assist_modes:
        if not isinstance(mode, dict):
            continue

        mode_id = mode.get("id", f"Mode {output_index + 1}")

        # Skip the "0" (OFF) mode
        if mode_id == "0" or not mode_id:
            continue

        # Get range: prefer SOC array at output_index, fall back to per-mode value
        if output_index < len(reachable_range_array):
            range_km = reachable_range_array[output_index]
        else:
            range_km = mode.get("reachableRange")

        if range_km is None or (isinstance(range_km, (int, float)) and range_km == 0):
            # Skip modes with no valid range
            continue

        try:
            display_name = _assist_mode_display_name(mode_id)
            modes.append(
                {
                    "name": display_name,
                    "range_km": float(range_km),
                    "index": output_index,
                    "mode_id": mode_id,
                }
            )
            output_index += 1
        except (TypeError, ValueError):
            pass

    return modes


def _assist_mode_display_name(code: str) -> str:
    """Map internal Bosch mode code to display name.

    Falls back to the code itself if not in the mapping, or to
    heuristics for codes that contain their own name (AUTO, ECO+).
    """
    if not isinstance(code, str):
        return str(code)

    # Direct lookup
    if code in ASSIST_MODE_NAMES:
        return ASSIST_MODE_NAMES[code]

    # Heuristic for codes with embedded names
    upper_code = code.upper()
    if "AUTO" in upper_code:
        return "AUTO"
    if "ECOP" in upper_code:
        return "ECO+"

    # Return the code as-is if no mapping found
    return code
