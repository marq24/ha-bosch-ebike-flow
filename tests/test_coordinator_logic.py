"""Test coordinator data combination logic without Home Assistant dependencies."""
# This test file tests the core logic directly without importing Home Assistant modules
import importlib.util
from pathlib import Path
from typing import Optional, Dict, Any

# Loaded from its path rather than imported as `custom_components.bosch_ebike.
# bosch_data_handler`, because that pulls in the package __init__ and with it
# Home Assistant. The module itself only needs the standard library.
_HANDLER = Path(__file__).resolve().parent.parent / "custom_components" / "bosch_ebike" / "bosch_data_handler.py"
_spec = importlib.util.spec_from_file_location("bosch_data_handler", _HANDLER)
bosch_data_handler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bosch_data_handler)
get_battery_reachable_min_max_range_attr = bosch_data_handler.get_battery_reachable_min_max_range_attr


def combine_bike_data_logic(profile_data: Dict[str, Any], soc_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Test version of _combine_bike_data method logic.

    This replicates the logic from coordinator.py to test it independently.
    """
    # Extract from profile
    bike_attrs = profile_data.get("data", {}).get("attributes", {})
    batteries_list = bike_attrs.get("batteries") or []
    battery = batteries_list[0] if batteries_list else {}
    # Use 'or {}' to handle None values (API may return null for optional fields)
    drive_unit = bike_attrs.get("driveUnit") or {}
    connected_module = bike_attrs.get("connectedModule") or {}
    remote_control = bike_attrs.get("remoteControl") or {}

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
            combined["battery"]["level_percent"] = soc_data.get(
                "stateOfCharge")

        if combined["battery"]["is_charging"] is None:
            combined["battery"]["is_charging"] = soc_data.get("chargingActive")

        if combined["battery"]["is_charger_connected"] is None:
            combined["battery"]["is_charger_connected"] = soc_data.get(
                "chargerConnected")

        # Add live-only data
        combined["battery"]["reachable_range_km"] = soc_data.get(
            "reachableRange")
        combined["battery"]["remaining_energy_rider_wh"] = soc_data.get(
            "remainingEnergyForRider")

        # Update odometer from live data if available
        if soc_data.get("odometer") is not None:
            combined["bike"]["total_distance_m"] = soc_data.get("odometer")

    return combined


def test_combine_bike_data_with_none_connected_module():
    """Test that coordinator handles None connectedModule gracefully.

    This simulates the scenario where users have ConnectModule but not Flow+
    subscription, causing the API to return null for connectedModule.
    """
    # Simulate API response with connectedModule: null (becomes None in Python)
    profile_data = {
        "data": {
            "attributes": {
                "batteries": [{
                    "batteryLevel": 75,
                    "remainingEnergy": 500,
                    "totalEnergy": 625,
                    "isCharging": False,
                    "isChargerConnected": False,
                    "numberOfFullChargeCycles": {"total": 42},
                }],
                "driveUnit": {
                    "totalDistanceTraveled": 12345,
                    "lock": {
                        "isLocked": False,
                        "isEnabled": True,
                    },
                },
                # This is the key issue: API returns null for users without Flow+
                "connectedModule": None,
                "remoteControl": None,
            }
        }
    }

    # This should not raise an AttributeError
    result = combine_bike_data_logic(profile_data, None)

    # Verify the structure is correct
    assert result is not None
    assert "battery" in result
    assert "bike" in result
    assert "components" in result

    # Verify alarm_enabled is None (not causing an error)
    assert result["bike"]["alarm_enabled"] is None

    # Verify connected_module components are all None
    assert result["components"]["connected_module"]["product_name"] is None
    assert result["components"]["connected_module"]["software_version"] is None
    assert result["components"]["connected_module"]["serial_number"] is None

    # Verify other data is still processed correctly
    assert result["battery"]["level_percent"] == 75
    assert result["bike"]["total_distance_m"] == 12345


def test_combine_bike_data_with_missing_fields():
    """Test handling of various missing/null fields."""
    # Simulate minimal API response
    profile_data = {
        "data": {
            "attributes": {
                "batteries": [{
                    "batteryLevel": 50,
                }],
                "driveUnit": {},
                "connectedModule": None,
                "remoteControl": None,
            }
        }
    }

    # Should not raise any errors
    result = combine_bike_data_logic(profile_data, None)

    assert result is not None
    assert result["battery"]["level_percent"] == 50


def test_combine_bike_data_with_empty_batteries():
    """Test handling of empty batteries array."""
    profile_data = {
        "data": {
            "attributes": {
                "batteries": [],
                "driveUnit": {},
                "connectedModule": None,
                "remoteControl": None,
            }
        }
    }

    # Should not raise IndexError
    result = combine_bike_data_logic(profile_data, None)

    assert result is not None


def test_combine_bike_data_with_none_lock():
    """Test handling of None lock field."""
    profile_data = {
        "data": {
            "attributes": {
                "batteries": [{
                    "batteryLevel": 80,
                }],
                "driveUnit": {
                    "totalDistanceTraveled": 5000,
                    "lock": None,  # lock field is None
                },
                "connectedModule": None,
                "remoteControl": None,
            }
        }
    }

    # Should not raise AttributeError when accessing lock.get()
    result = combine_bike_data_logic(profile_data, None)

    assert result is not None
    assert result["bike"]["is_locked"] is None
    assert result["bike"]["lock_enabled"] is None


def test_combine_bike_data_with_none_number_of_charge_cycles():
    """Test handling of None numberOfFullChargeCycles field."""
    profile_data = {
        "data": {
            "attributes": {
                "batteries": [{
                    "batteryLevel": 80,
                    "numberOfFullChargeCycles": None,  # This field can be None
                }],
                "driveUnit": {},
                "connectedModule": None,
                "remoteControl": None,
            }
        }
    }

    # Should not raise AttributeError when accessing numberOfFullChargeCycles.get()
    result = combine_bike_data_logic(profile_data, None)

    assert result is not None
    assert result["battery"]["charge_cycles_total"] is None


# A Performance Line PX drive unit: an OFF mode that is skipped, two mapped
# assist modes and two the name table does not know.
BIKE_DATA_FOUR_MODES = {
    "profile": {
        "driveUnit": {
            "driveUnitAssistModes": [
                {"id": "0"},
                {"id": "A100M40040"},
                {"id": "A100E34AA0"},
                {"id": "A100M40020"},
                {"id": "A100M40010"},
            ]
        }
    },
    "soc": {"reachableRange": [80, 61, 40, 38]},
}


def test_reachable_range_attr_keys_are_strings():
    """Attribute keys must be strings.

    Home Assistant exporters iterate the attributes and sort the keys, so int
    keys mixed in among the string ones raise
    `TypeError: '<' not supported between instances of 'int' and 'str'`.
    """
    attrs = get_battery_reachable_min_max_range_attr(BIKE_DATA_FOUR_MODES)

    assert attrs
    non_string = [key for key in attrs if not isinstance(key, str)]
    assert not non_string, f"non-string attribute keys: {non_string}"
    sorted(attrs)


def test_reachable_range_attr_preserves_modes_and_order():
    """Only the key type changes: same modes, same order, same values."""
    attrs = get_battery_reachable_min_max_range_attr(BIKE_DATA_FOUR_MODES)

    assert list(attrs) == ["0", "1", "2", "3"]
    assert [entry["id"] for entry in attrs.values()] == [
        "A100M40040",
        "A100E34AA0",
        "A100M40020",
        "A100M40010",
    ]
    assert [entry["rangeInKm"] for entry in attrs.values()] == [80.0, 61.0, 40.0, 38.0]
    assert attrs["0"]["name"] == "ECO"
    assert attrs["3"]["name"] == "TURBO"
    # Codes the table does not know fall back to the code itself.
    assert attrs["1"]["name"] == "A100E34AA0"
