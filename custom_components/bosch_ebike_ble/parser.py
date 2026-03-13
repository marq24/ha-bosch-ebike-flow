"""Parser for Bosch eBike BLE data.

"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from bleak import BleakClient, BleakError, BLEDevice
from bleak_retry_connector import establish_connection
from bluetooth_data_tools import short_address
from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfo
from sensor_state_data import SensorDeviceClass, SensorUpdate, Units
from sensor_state_data.enum import StrEnum

from .const import (
    ASSIST_MODES,
    BOSCH_STATUS_CHAR_UUID,
    BOSCH_STATUS_SERVICE_UUID,
    CONNECTED_UPDATE_INTERVAL_SECONDS,
    DEVICE_NAME_PATTERNS,
    DISCONNECTED_UPDATE_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class BoschEBikeSensor(StrEnum):
    """Sensor types for Bosch eBike."""

    BATTERY = "battery"
    SPEED = "speed"
    CADENCE = "cadence"
    HUMAN_POWER = "human_power"
    MOTOR_POWER = "motor_power"
    ASSIST_MODE = "assist_mode"
    TORQUE = "torque"
    SIGNAL_STRENGTH = "signal_strength"
    TOTAL_DISTANCE = "total_distance"
    WHEEL_CIRCUMFERENCE = "wheel_circumference"
    TOTAL_ENERGY = "total_energy"
    BATTERY_CAPACITY = "battery_capacity"
    ENERGY_DELIVERED = "energy_delivered"
    CHARGE_CYCLES = "charge_cycles"
    MAX_ASSIST_SPEED = "max_assist_speed"


@dataclass
class BoschMessage:
    """Parsed Bosch BLE message."""

    message_id: int
    message_type: int
    value: int
    raw_bytes: list[int]


@dataclass
class BikeStatus:
    """Current bike status data."""

    cadence: int = 0
    human_power: int = 0
    motor_power: int = 0
    speed: float = 0.0
    battery: int = 0
    assist_mode: int = 0
    torque: float = 0.0
    total_distance: int = 0  # meters
    wheel_circumference: float = 0.0  # mm
    total_energy: int = 0  # Wh
    battery_capacity: int = 0  # Wh
    energy_delivered: int = 0  # Wh
    charge_cycles: float = 0.0
    max_assist_speed: float = 0.0  # km/h


def decode_varint(data: list[int], start_index: int = 0) -> tuple[int, int]:
    """Decode a varint from bytes.

    Returns tuple of (decoded value, number of bytes consumed).
    Varints use MSB to indicate continuation.
    """
    if start_index >= len(data):
        return (0, 0)

    result = 0
    shift = 0
    current_index = start_index
    bytes_consumed = 0

    try:
        while current_index < len(data) and bytes_consumed < 5:
            byte = data[current_index]
            result = result | ((byte & 0x7F) << shift)
            bytes_consumed += 1
            current_index += 1

            # If MSB is 0, this is the last byte
            if (byte & 0x80) == 0:
                break
            shift += 7
    except Exception as e:
        _LOGGER.debug("Error decoding varint: %s", e)
        return (0, 1)

    return (result, bytes_consumed)


def parse_bosch_packet(data: bytes | list[int]) -> list[BoschMessage]:
    """Parse a Bosch BLE packet containing potentially multiple messages.

    Message format:
    - 0x30: Start of message
    - Length byte: Payload size (not including start and length bytes)
    - Message ID: 2 bytes
    - Data type: 1 byte (0x08 = varint)
    - Data: Variable length varint or raw bytes
    """
    if isinstance(data, bytes):
        data = list(data)

    messages: list[BoschMessage] = []
    index = 0

    _LOGGER.debug("Parsing packet: %s", "-".join(f"{b:02X}" for b in data))

    try:
        while index < len(data):
            # Look for message start (0x30)
            if data[index] != 0x30:
                index += 1
                continue

            # Check if we have enough bytes for a basic message header
            if index + 2 >= len(data):
                break

            message_length = data[index + 1]
            _LOGGER.debug("Found message start at index %d, length: %d", index, message_length)

            # Message length is payload size, not including start byte and length byte
            total_message_size = message_length + 2

            if message_length < 2 or message_length > 50:
                _LOGGER.debug("Invalid message length: %d", message_length)
                index += 1
                continue

            if index + total_message_size > len(data):
                _LOGGER.debug("Not enough bytes for complete message")
                break

            if index + 4 > len(data):
                break

            # Extract the message ID (2 bytes after start and length)
            message_id = (data[index + 2] << 8) | data[index + 3]
            _LOGGER.debug("Message ID: 0x%04X", message_id)

            # Get all message bytes
            message_bytes = data[index:min(index + total_message_size, len(data))]
            _LOGGER.debug("Message bytes: %s", "-".join(f"{b:02X}" for b in message_bytes))

            # Determine if there's a data type byte and data
            data_value = 0
            data_type = 0

            # If message length is <= 2, the data_value = 0
            if message_length > 2:
                data_type_index = 4  # Position after start(1) + length(1) + messageId(2)
                data_start_index = 5  # Position after data type byte

                if data_type_index < len(message_bytes):
                    data_type = message_bytes[data_type_index]
                    if data_type == 0x08:
                        # Varint encoded data
                        if data_start_index < len(message_bytes):
                            data_bytes = message_bytes[data_start_index:]
                            value, consumed = decode_varint(data_bytes, 0)
                            data_value = value
                            _LOGGER.debug("Decoded varint value: %d (consumed %d bytes)", data_value, consumed)
                    elif data_type == 0x0A:
                        # Different encoding type - try as raw bytes
                        if data_start_index < len(message_bytes):
                            data_value = message_bytes[data_start_index]
                            _LOGGER.debug("Using first data byte for 0x0A: %d", data_value)
                    else:
                        # Unknown data type
                        data_value = 0
                        _LOGGER.debug("Unknown data type 0x%02X - setting value to 0", data_type)

            message = BoschMessage(
                message_id=message_id,
                message_type=data_type,
                value=data_value,
                raw_bytes=message_bytes,
            )

            messages.append(message)
            _LOGGER.debug("Created message: ID=0x%04X, value=%d", message_id, data_value)

            index += total_message_size  # Move to the next message

    except Exception as e:
        _LOGGER.error("Error parsing packet: %s", e)
        return messages

    _LOGGER.debug("Parsed %d messages", len(messages))
    return messages


def process_messages(messages: list[BoschMessage]) -> BikeStatus:
    """Process parsed messages and return bike status."""
    status = BikeStatus()

    for message in messages:
        _LOGGER.debug(
            "Processing message ID: 0x%04X, value: %d",
            message.message_id,
            message.value,
        )

        match message.message_id:
            # Core sensor data
            case 0x985A:  # Cadence - divide by 2
                status.cadence = max(0, message.value // 2)
            case 0x985B:  # Human Power
                status.human_power = max(0, message.value)
            case 0x985D:  # Motor Power
                status.motor_power = max(0, message.value)
            case 0x982D:  # Speed - divide by 100 for km/h
                status.speed = max(0.0, message.value / 100.0)
            case 0x8088:  # Battery percentage
                status.battery = min(100, max(0, message.value))
            case 0x9809:  # Assist Mode
                status.assist_mode = min(10, max(0, message.value))
            case 0x9815:  # Torque - divide by 200
                status.torque = max(0.0, message.value / 200.0)

            # Distance and wheel
            case 0x9818:  # Total distance in meters (odometer)
                status.total_distance = max(0, message.value)
            case 0x9829:  # Wheel circumference - divide by 10 for mm
                status.wheel_circumference = max(0.0, message.value / 10.0)

            # Battery and energy
            case 0x80B4:  # Total energy - divide by 10 for Wh
                status.total_energy = max(0, message.value // 10)
            case 0x9874:  # Battery capacity in Wh
                status.battery_capacity = max(0, message.value)
            case 0x809C:  # Total energy delivered in Wh
                status.energy_delivered = max(0, message.value)
            case 0x8096:  # Battery charge cycles - divide by 10
                status.charge_cycles = max(0.0, message.value / 10.0)

            # Speed limits
            case 0x9842:  # Maximum assistance speed - divide by 100 for km/h
                status.max_assist_speed = max(0.0, message.value / 100.0)

            # System signals (ping/alive)
            case 0x2002:  # Ping/alive signal - sent during startup and shutdown
                if message.value > 0:
                    _LOGGER.debug("eBike ping signal, value: %d", message.value)

            # Button events
            case 0xA0AA:  # Long-press OK button (reset)
                if message.value == 0:
                    _LOGGER.debug("eBike OK button long-press detected")
                else:
                    _LOGGER.debug("eBike reset signal, value: %d", message.value)

            # Display refresh
            case 0x2112:  # Display refresh after mode change
                _LOGGER.debug("eBike display refresh signal, value: %d", message.value)

            # Known startup sequence IDs (typically 0 during startup)
            case (
                0x0D27 | 0x0D2C | 0x108B | 0x108C | 0x1818 | 0x181A |
                0x1090 | 0x1091 | 0x1092 | 0x2010 | 0x2030 | 0x20C7 |
                0x208E | 0x210B | 0x216A | 0x2150 | 0xA183
            ):
                if message.value > 0:
                    _LOGGER.debug(
                        "eBike startup sequence ID 0x%04X with non-zero value: %d",
                        message.message_id,
                        message.value,
                    )

            # Other typically-zero values
            case (
                0x808A | 0x80C4 | 0x9811 | 0x9834 | 0x9835 |
                0x984E | 0x9857 | 0x986A | 0x988B
            ):
                if message.value > 0:
                    _LOGGER.debug(
                        "eBike ID 0x%04X expected 0, got: %d",
                        message.message_id,
                        message.value,
                    )

            # Typically-one values
            case (
                0x981A | 0x981C | 0x9820 | 0x9821 | 0x9826 | 0x9865 |
                0xA081 | 0xA083 | 0xA085 | 0xA10F | 0x8D1B
            ):
                if message.value != 1:
                    _LOGGER.debug(
                        "eBike ID 0x%04X expected 1, got: %d",
                        message.message_id,
                        message.value,
                    )

            # Known but unprocessed values
            case (
                0x9819 |  # = 162
                0x986D |  # = 88
                0xA011 |  # = 40
                0xA0E2 |  # = 1 and 4
                0xA165 |  # = 65
                0xA250 |  # = 2
                0x808B |  # = 458
                0x808E |  # = 2
                0x8091 |  # = 5430
                0x8092 |  # = 5650
                0x80B0 |  # = 99
                0x80B1 |  # batteries:numberOfFullChargeCycles OFF-Bike, divided by 10
                0x80BC |  # batteries:numberOfFullChargeCycles ON-Bike, divided by 10
                0x80C5 |  # = 5430
                0x80CA    # = 98
            ):
                pass  # Known but not currently processed

            case _:
                if message.value > 1:
                    _LOGGER.debug(
                        "Unknown message ID: 0x%04X, value: %d",
                        message.message_id,
                        message.value,
                    )

    return status


class BoschEBikeBluetoothDeviceData(BluetoothData):
    """Data for Bosch eBike BLE sensors."""

    def __init__(self) -> None:
        super().__init__()
        self._connected = False
        self._last_update = 0.0
        self._bike_status = BikeStatus()

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        _LOGGER.debug("Parsing Bosch eBike BLE advertisement data: %s", service_info)

        address = service_info.address
        name = service_info.name or "Bosch eBike"

        self.set_device_manufacturer("Bosch")
        self.set_device_type("Smart System eBike")
        self.set_device_name(f"Bosch eBike {short_address(address)}")
        self.set_title(name)

        # Update signal strength from advertisement
        if service_info.rssi is not None:
            self.update_sensor(
                str(BoschEBikeSensor.SIGNAL_STRENGTH),
                Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                service_info.rssi,
                SensorDeviceClass.SIGNAL_STRENGTH,
                "Signal Strength",
            )

    def poll_needed(
        self, service_info: BluetoothServiceInfo, last_poll: float | None
    ) -> bool:
        """Determine if we need to poll the device.

        Bosch eBike requires active connection to read sensor data.
        """
        if last_poll is None:
            return True

        update_interval = (
            CONNECTED_UPDATE_INTERVAL_SECONDS
            if self._connected
            else DISCONNECTED_UPDATE_INTERVAL_SECONDS
        )
        return last_poll > update_interval

    def supported(self, service_info: BluetoothServiceInfo) -> bool:
        """Check if this device is a supported Bosch eBike."""
        name = service_info.name or ""

        # Check by name pattern
        name_lower = name.lower()
        for pattern in DEVICE_NAME_PATTERNS:
            if pattern.lower() in name_lower:
                return True

        # Check if the Bosch service UUID is advertised
        for uuid in service_info.service_uuids:
            if uuid.lower() == BOSCH_STATUS_SERVICE_UUID.lower():
                return True

        return False

    def get_device_name(self) -> str | None:
        """Return the device name."""
        return self.title

    def _update_sensors_from_status(self, status: BikeStatus) -> None:
        """Update Home Assistant sensors from bike status."""
        self.update_sensor(
            str(BoschEBikeSensor.BATTERY),
            Units.PERCENTAGE,
            status.battery,
            SensorDeviceClass.BATTERY,
            "Battery",
        )
        self.update_sensor(
            str(BoschEBikeSensor.SPEED),
            Units.SPEED_KILOMETERS_PER_HOUR,
            round(status.speed, 1),
            SensorDeviceClass.SPEED,
            "Speed",
        )
        self.update_sensor(
            str(BoschEBikeSensor.CADENCE),
            None,  # RPM - no standard unit
            status.cadence,
            None,
            "Cadence",
        )
        self.update_sensor(
            str(BoschEBikeSensor.HUMAN_POWER),
            Units.POWER_WATT,
            status.human_power,
            SensorDeviceClass.POWER,
            "Human Power",
        )
        self.update_sensor(
            str(BoschEBikeSensor.MOTOR_POWER),
            Units.POWER_WATT,
            status.motor_power,
            SensorDeviceClass.POWER,
            "Motor Power",
        )
        self.update_sensor(
            str(BoschEBikeSensor.ASSIST_MODE),
            None,
            ASSIST_MODES.get(status.assist_mode, f"Mode {status.assist_mode}"),
            None,
            "Assist Mode",
        )
        if status.torque > 0:
            self.update_sensor(
                str(BoschEBikeSensor.TORQUE),
                None,  # Nm - no standard unit available
                round(status.torque, 2),
                None,
                "Torque",
            )

        # Distance and odometer
        if status.total_distance > 0:
            self.update_sensor(
                str(BoschEBikeSensor.TOTAL_DISTANCE),
                Units.LENGTH_METERS,
                status.total_distance,
                SensorDeviceClass.DISTANCE,
                "Total Distance",
            )

        # Wheel circumference
        if status.wheel_circumference > 0:
            self.update_sensor(
                str(BoschEBikeSensor.WHEEL_CIRCUMFERENCE),
                None,  # mm
                round(status.wheel_circumference, 1),
                None,
                "Wheel Circumference",
            )

        # Battery and energy sensors
        if status.total_energy > 0:
            self.update_sensor(
                str(BoschEBikeSensor.TOTAL_ENERGY),
                Units.ENERGY_WATT_HOUR,
                status.total_energy,
                SensorDeviceClass.ENERGY,
                "Total Energy",
            )

        if status.battery_capacity > 0:
            self.update_sensor(
                str(BoschEBikeSensor.BATTERY_CAPACITY),
                Units.ENERGY_WATT_HOUR,
                status.battery_capacity,
                SensorDeviceClass.ENERGY,
                "Battery Capacity",
            )

        if status.energy_delivered > 0:
            self.update_sensor(
                str(BoschEBikeSensor.ENERGY_DELIVERED),
                Units.ENERGY_WATT_HOUR,
                status.energy_delivered,
                SensorDeviceClass.ENERGY,
                "Energy Delivered",
            )

        if status.charge_cycles > 0:
            self.update_sensor(
                str(BoschEBikeSensor.CHARGE_CYCLES),
                None,
                round(status.charge_cycles, 1),
                None,
                "Charge Cycles",
            )

        # Speed limits
        if status.max_assist_speed > 0:
            self.update_sensor(
                str(BoschEBikeSensor.MAX_ASSIST_SPEED),
                Units.SPEED_KILOMETERS_PER_HOUR,
                round(status.max_assist_speed, 1),
                SensorDeviceClass.SPEED,
                "Max Assist Speed",
            )

        self._bike_status = status

    async def async_poll(self, ble_device: BLEDevice) -> SensorUpdate:
        """Poll the device to retrieve values via GATT connection.

        Bosch eBike sends data via notifications on the status characteristic.
        """
        _LOGGER.debug("Polling Bosch eBike device: %s", ble_device.address)

        collected_data: list[bytes] = []

        def notification_handler(sender: Any, data: bytes) -> None:
            """Handle incoming notification data."""
            _LOGGER.debug(
                "Received notification from %s: %s",
                sender,
                "-".join(f"{b:02X}" for b in data),
            )
            collected_data.append(data)

        try:
            client = await establish_connection(
                BleakClient, ble_device, ble_device.address
            )

            try:
                self._connected = True

                # Get the status service and characteristic
                service = client.services.get_service(BOSCH_STATUS_SERVICE_UUID)
                if service is None:
                    _LOGGER.warning("Bosch status service not found")
                    return self._finish_update()

                char = service.get_characteristic(BOSCH_STATUS_CHAR_UUID)
                if char is None:
                    _LOGGER.warning("Bosch status characteristic not found")
                    return self._finish_update()

                # Enable notifications
                await client.start_notify(char, notification_handler)

                # Wait for data (Bosch sends data continuously when bike is on)
                import asyncio
                await asyncio.sleep(2.0)  # Wait 2 seconds for notifications

                # Stop notifications
                await client.stop_notify(char)

                # Process collected data
                if collected_data:
                    all_messages: list[BoschMessage] = []
                    for data in collected_data:
                        messages = parse_bosch_packet(data)
                        all_messages.extend(messages)

                    if all_messages:
                        status = process_messages(all_messages)
                        self._update_sensors_from_status(status)
                        _LOGGER.debug("Successfully processed %d messages", len(all_messages))
                else:
                    _LOGGER.debug("No notification data received (bike may be off)")

                self._last_update = time.monotonic()

            finally:
                await client.disconnect()
                _LOGGER.debug("Disconnected from Bosch eBike")

        except BleakError as err:
            _LOGGER.warning("Error connecting to Bosch eBike: %s", err)
            self._connected = False
        except Exception as err:
            _LOGGER.error("Unexpected error polling Bosch eBike: %s", err)
            self._connected = False

        return self._finish_update()

