import logging
from typing import Any, Final

_LOGGER = logging.getLogger(__name__)

KEY_TOTAL_DISTANCE: Final = "total_distance"

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
def combine_bike_data(profile_data: dict[str, Any], soc_data: dict[str, Any] | None) -> dict[str, Any]:
    """Combine bike profile and state-of-charge data."""

    # Extract from profile
    batteries_list = profile_data.get("batteries", [])
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
            "charge_cycles_total": battery.get("numberOfFullChargeCycles", {}).get("total"),
            "charge_cycles_on_bike": battery.get("numberOfFullChargeCycles", {}).get("onBike"),
            "charge_cycles_off_bike": battery.get("numberOfFullChargeCycles", {}).get("offBike"),
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
        combined["last_update"] = soc_data.get("stateOfChargeLatestUpdate")

        # Use live data to fill in null values from profile
        if combined["battery"]["level_percent"] is None:
            combined["battery"]["level_percent"] = soc_data.get("stateOfCharge")

        if combined["battery"]["is_charging"] is None:
            combined["battery"]["is_charging"] = soc_data.get("chargingActive")

        if combined["battery"]["is_charger_connected"] is None:
            combined["battery"]["is_charger_connected"] = soc_data.get("chargerConnected")

        # Add live-only data
        reachable_range_raw = soc_data.get("reachableRange")
        _LOGGER.debug(f"Reachable range raw data: {reachable_range_raw} (type: {type(reachable_range_raw)})")
        combined["battery"]["reachable_range_km"] = reachable_range_raw
        combined["battery"]["remaining_energy_rider_wh"] = soc_data.get("remainingEnergyForRider")

        # Update odometer from live data if available
        if soc_data.get("odometer") is not None:
            combined["bike"]["total_distance_m"] = soc_data.get("odometer")
    return combined

@staticmethod
def get_battery_reachable_min_range(data: dict[str, Any]):
    ranges = data.get("battery", {}).get("reachable_range_km", [])
    #_LOGGER.warning(f"MIN Reachable range: {ranges}")
    if isinstance(ranges, list) and len(ranges) > 0:
        for x in reversed(ranges):
            if x != 0:
                return x
        return 0
    return None

@staticmethod
def get_battery_reachable_max_range(data: dict[str, Any]):
    ranges = data.get("battery", {}).get("reachable_range_km", [])
    #_LOGGER.warning(f"MAX Reachable range: {ranges}")
    if isinstance(ranges, list) and len(ranges) > 0:
        return ranges[0]
    return None

@staticmethod
def get_battery_charging(data: dict[str, Any]) -> bool:
    return bool(data.get("battery", {}).get("is_charging", False))

@staticmethod
def get_charger_connected(data: dict[str, Any]) -> bool:
    return bool(data.get("battery", {}).get("is_charger_connected", False))

@staticmethod
def get_lock_enabled(data: dict[str, Any]):
    is_locked = data.get("bike", {}).get("is_locked", None)
    if is_locked is not None:
        return is_locked
    else:
        return data.get("bike", {}).get("lock_enabled", None)

@staticmethod
def get_alarm_enabled(data: dict[str, Any]):
    return data.get("bike", {}).get("alarm_enabled", None)

@staticmethod
def get_battery_level(data: dict[str, Any]):
    return data.get("battery", {}).get("level_percent", None)

@staticmethod
def get_battery_remaining_energy(data: dict[str, Any]):
    return data.get("battery", {}).get("remaining_wh", None)

@staticmethod
def get_battery_capacity(data: dict[str, Any]):
    return data.get("battery", {}).get("total_capacity_wh", None)

@staticmethod
def get_total_distance(data: dict[str, Any]):
    a_val = data.get("bike", {}).get("total_distance_m", None)
    if a_val is not None:
        return round(a_val / 1000, 2)
    return None

@staticmethod
def get_charge_cycles(data: dict[str, Any]):
    return data.get("battery", {}).get("charge_cycles_total", None)

@staticmethod
def get_charge_cycles_attr(data: dict[str, Any]):
    attrs = {}
    val_on_bike = data.get("battery", {}).get("charge_cycles_on_bike", None)
    val_off_bike = data.get("battery", {}).get("charge_cycles_off_bike", None)

    if val_on_bike is not None:
        attrs["onBike"] = val_on_bike
    if val_off_bike is not None:
        attrs["offBike"] = val_off_bike

    return attrs if len(attrs) > 0 else None

@staticmethod
def get_lifetime_energy_delivered(data: dict[str, Any]):
    a_val = data.get("battery", {}).get("delivered_lifetime_wh", None)
    if a_val is not None:
        return round(a_val / 1000, 2)
    return None

@staticmethod
def get_drive_unit_software_version(data: dict[str, Any]):
    return data.get("components", {}).get("drive_unit", {}).get("software_version", None)

@staticmethod
def get_battery_software_version(data: dict[str, Any]):
    return data.get("components", {}).get("battery", {}).get("software_version", None)

@staticmethod
def get_connected_module_software_version(data: dict[str, Any]):
    return data.get("components", {}).get("connected_module", {}).get("software_version", None)

@staticmethod
def get_remote_control_software_version(data: dict[str, Any]):
    return data.get("components", {}).get("remote_control", {}).get("software_version", None)