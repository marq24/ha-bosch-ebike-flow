import logging
from typing import Any, Final

_LOGGER = logging.getLogger(__name__)

KEY_TOTAL_DISTANCE: Final = "total_distance"
KEY_SOC: Final = "soc"
KEY_PROFILE: Final = "profile"

@staticmethod
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


@staticmethod
def _get_drive_unit(data: dict[str, Any]) -> dict[str, Any]:
    """Extract drive unit data from bike data."""
    return data.get(KEY_PROFILE, {}).get("driveUnit") or {}

@staticmethod
def _get_first_battery(data: dict[str, Any]) -> dict[str, Any]:
    """Extract first battery data from bike data."""
    batteries = data.get(KEY_PROFILE, {}).get("batteries", [])
    return batteries[0] if batteries else {}

@staticmethod
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
            [int(item["reachableRange"]) for item in _get_drive_unit(data).get("driveUnitAssistModes", {})],
            reverse=True)
        if ranges:
            for x in reversed(ranges):
                if x != 0:
                    return x
            return 0
    return None

@staticmethod
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
            [int(item["reachableRange"]) for item in _get_drive_unit(data).get("driveUnitAssistModes", {})],
            reverse=True)
        if ranges:
            return ranges[0]
    return None

@staticmethod
def get_battery_charging(data: dict[str, Any]) -> bool:
    soc_data = data.get(KEY_SOC)
    if soc_data and soc_data.get("chargingActive") is not None:
        return bool(soc_data.get("chargingActive"))

    return bool(_get_first_battery(data).get("isCharging", False))

@staticmethod
def get_charger_connected(data: dict[str, Any]) -> bool:
    soc_data = data.get(KEY_SOC)
    if soc_data and soc_data.get("chargerConnected") is not None:
        return bool(soc_data.get("chargerConnected"))

    return bool(_get_first_battery(data).get("isChargerConnected", False))

@staticmethod
def get_lock_enabled(data: dict[str, Any]):
    lock = _get_drive_unit(data).get("lock") or {}
    is_locked = lock.get("isLocked")
    if is_locked is not None:
        return is_locked
    return lock.get("isEnabled")

@staticmethod
def get_alarm_enabled(data: dict[str, Any]):
    connected_module = data.get(KEY_PROFILE, {}).get("connectedModule") or {}
    return connected_module.get("isAlarmFeatureEnabled")

@staticmethod
def get_battery_level(data: dict[str, Any]):
    soc_data = data.get(KEY_SOC)
    if soc_data and soc_data.get("stateOfCharge") is not None:
        return soc_data.get("stateOfCharge")

    return _get_first_battery(data).get("batteryLevel")

@staticmethod
def get_battery_remaining_energy(data: dict[str, Any]):
    soc_data = data.get(KEY_SOC)
    if soc_data and soc_data.get("remainingEnergyForRider") is not None:
        return soc_data.get("remainingEnergyForRider")

    return _get_first_battery(data).get("remainingEnergy")

@staticmethod
def get_battery_capacity(data: dict[str, Any]):
    return _get_first_battery(data).get("totalEnergy")

@staticmethod
def get_total_distance(data: dict[str, Any]):
    soc_data = data.get(KEY_SOC)
    a_val = None
    if soc_data and soc_data.get("odometer") is not None:
        a_val = soc_data.get("odometer")
    else:
        a_val = _get_drive_unit(data).get("totalDistanceTraveled")

    if a_val is not None:
        return round(a_val / 1000, 2)
    return None

@staticmethod
def get_charge_cycles(data: dict[str, Any]):
    return _get_first_battery(data).get("numberOfFullChargeCycles", {}).get("total")

@staticmethod
def get_charge_cycles_attr(data: dict[str, Any]):
    cycles = _get_first_battery(data).get("numberOfFullChargeCycles", {})

    attrs = {}
    val_on_bike = cycles.get("onBike")
    val_off_bike = cycles.get("offBike")

    if val_on_bike is not None:
        attrs["onBike"] = val_on_bike
    if val_off_bike is not None:
        attrs["offBike"] = val_off_bike

    return attrs if len(attrs) > 0 else None

@staticmethod
def get_lifetime_energy_delivered(data: dict[str, Any]):
    a_val = _get_first_battery(data).get("deliveredWhOverLifetime")
    if a_val is not None:
        return round(a_val / 1000, 2)
    return None

@staticmethod
def get_drive_unit_software_version(data: dict[str, Any]):
    return _get_drive_unit(data).get("softwareVersion")

@staticmethod
def get_battery_software_version(data: dict[str, Any]):
    return _get_first_battery(data).get("softwareVersion")

@staticmethod
def get_connected_module_software_version(data: dict[str, Any]):
    connected_module = data.get(KEY_PROFILE, {}).get("connectedModule") or {}
    return connected_module.get("softwareVersion")

@staticmethod
def get_remote_control_software_version(data: dict[str, Any]):
    remote_control = data.get(KEY_PROFILE, {}).get("remoteControl") or {}
    return remote_control.get("softwareVersion")