"""DualShock 4 HID input handler with gyroscope support."""

import asyncio
import struct
from typing import Any

from events import EventBus, Event, EventType


# DualShock 4 vendor/product IDs
DS4_VENDOR_ID = 0x054C  # Sony
DS4_PRODUCT_IDS = [0x05C4, 0x09CC]  # DS4 v1, DS4 v2


class DS4Button:
    """DualShock 4 button bit positions."""
    SQUARE = 4
    CROSS = 5
    CIRCLE = 6
    TRIANGLE = 7
    L1 = 8
    R1 = 9
    L2 = 10
    R2 = 11
    SHARE = 12
    OPTIONS = 13
    L3 = 14
    R3 = 15
    PS = 16
    TOUCHPAD = 17


class DS4HIDController:
    """DualShock 4 controller using raw HID for gyro access."""

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self._device: Any = None
        self._running = False
        self._was_used = False  # Track if we successfully used HID

        # State tracking
        self._button_state: dict[int, bool] = {}
        self._axis_state: dict[int, float] = {}
        self._dpad_state = (0, 0)

        # Calibration for gyro (raw values are quite sensitive)
        self.gyro_scale = 1.0 / 1024.0  # Scale to roughly -1 to 1 range
        self.accel_scale = 1.0 / 8192.0

        # Deadzone for analog sticks
        self.deadzone = 0.15

    def _find_device(self) -> Any:
        """Find and open DS4 controller."""
        try:
            import hid
            for product_id in DS4_PRODUCT_IDS:
                try:
                    device = hid.device()
                    device.open(DS4_VENDOR_ID, product_id)
                    device.set_nonblocking(True)
                    print(f"DS4 connected via HID: {device.get_product_string()}")
                    return device
                except OSError:
                    continue
            return None
        except ImportError:
            print("Warning: hidapi not installed. DS4 HID input disabled.")
            return None

    def _parse_report(self, data: bytes) -> dict[str, Any] | None:
        """Parse DS4 HID report."""
        if not data:
            return None

        # USB reports start with 0x01, Bluetooth with 0x11
        # USB report is 64 bytes, Bluetooth is 78 bytes
        offset = 0
        if data[0] == 0x11:  # Bluetooth
            offset = 2
        elif data[0] != 0x01:  # Not a standard input report
            return None

        if len(data) < offset + 10:
            return None

        # Parse analog sticks (bytes 1-4 from offset)
        lx = (data[offset + 1] - 128) / 128.0
        ly = (data[offset + 2] - 128) / 128.0
        rx = (data[offset + 3] - 128) / 128.0
        ry = (data[offset + 4] - 128) / 128.0

        # Parse buttons (bytes 5-7 from offset)
        buttons_raw = data[offset + 5] | (data[offset + 6] << 8) | (data[offset + 7] << 16)

        # D-pad is in lower 4 bits of byte 5
        dpad = data[offset + 5] & 0x0F
        dpad_map = {
            0: (0, 1),    # Up
            1: (1, 1),    # Up-Right
            2: (1, 0),    # Right
            3: (1, -1),   # Down-Right
            4: (0, -1),   # Down
            5: (-1, -1),  # Down-Left
            6: (-1, 0),   # Left
            7: (-1, 1),   # Up-Left
            8: (0, 0),    # Neutral
        }
        dpad_xy = dpad_map.get(dpad, (0, 0))

        # Parse face buttons (byte 5, upper nibble + byte 6)
        buttons = {
            'square': bool(buttons_raw & (1 << 4)),
            'cross': bool(buttons_raw & (1 << 5)),
            'circle': bool(buttons_raw & (1 << 6)),
            'triangle': bool(buttons_raw & (1 << 7)),
            'l1': bool(buttons_raw & (1 << 8)),
            'r1': bool(buttons_raw & (1 << 9)),
            'l2': bool(buttons_raw & (1 << 10)),
            'r2': bool(buttons_raw & (1 << 11)),
            'share': bool(buttons_raw & (1 << 12)),
            'options': bool(buttons_raw & (1 << 13)),
            'l3': bool(buttons_raw & (1 << 14)),
            'r3': bool(buttons_raw & (1 << 15)),
            'ps': bool(buttons_raw & (1 << 16)),
            'touchpad': bool(buttons_raw & (1 << 17)),
        }

        result = {
            'lx': lx, 'ly': ly, 'rx': rx, 'ry': ry,
            'dpad': dpad_xy,
            'buttons': buttons,
        }

        # Parse gyro and accelerometer (bytes 13-24 from offset for USB)
        # These are signed 16-bit little-endian values
        gyro_offset = offset + 13
        if len(data) >= gyro_offset + 12:
            try:
                gyro_x, gyro_y, gyro_z = struct.unpack('<hhh', data[gyro_offset:gyro_offset + 6])
                accel_x, accel_y, accel_z = struct.unpack('<hhh', data[gyro_offset + 6:gyro_offset + 12])

                result['gyro'] = {
                    'x': gyro_x * self.gyro_scale,
                    'y': gyro_y * self.gyro_scale,
                    'z': gyro_z * self.gyro_scale,
                }
                result['accel'] = {
                    'x': accel_x * self.accel_scale,
                    'y': accel_y * self.accel_scale,
                    'z': accel_z * self.accel_scale,
                }
            except struct.error:
                pass

        return result

    def _apply_deadzone(self, value: float) -> float:
        """Apply deadzone to axis value."""
        if abs(value) < self.deadzone:
            return 0.0
        sign = 1 if value > 0 else -1
        return sign * (abs(value) - self.deadzone) / (1 - self.deadzone)

    async def run(self) -> None:
        """Run the HID input loop."""
        self._device = self._find_device()
        if not self._device:
            return

        self._was_used = True
        self._running = True
        while self._running:
            try:
                # Read HID report (non-blocking)
                data = self._device.read(78)  # Max report size
                if data:
                    report = self._parse_report(bytes(data))
                    if report:
                        await self._process_report(report)
            except Exception as e:
                print(f"DS4 HID error: {e}")
                break

            await asyncio.sleep(0.008)  # ~120 Hz

        if self._device:
            self._device.close()
            self._device = None

    async def _process_report(self, report: dict[str, Any]) -> None:
        """Process parsed report and emit events."""
        # Analog sticks
        for i, axis_name in enumerate(['lx', 'ly', 'rx', 'ry']):
            value = self._apply_deadzone(report[axis_name])
            if self._axis_state.get(i) != value:
                self._axis_state[i] = value
                await self.event_bus.publish(
                    Event(
                        type=EventType.CONTROLLER_AXIS,
                        data={'axis': i, 'value': value}
                    )
                )

        # D-pad
        if report['dpad'] != self._dpad_state:
            self._dpad_state = report['dpad']
            if report['dpad'] != (0, 0):
                await self.event_bus.publish(
                    Event(
                        type=EventType.CONTROLLER_BUTTON,
                        data={'dpad': report['dpad']}
                    )
                )

        # Buttons
        button_map = {
            'cross': 0, 'circle': 1, 'square': 2, 'triangle': 3,
            'l1': 4, 'r1': 5, 'l2': 6, 'r2': 7,
            'share': 8, 'options': 9, 'l3': 10, 'r3': 11,
            'ps': 12, 'touchpad': 13,
        }
        for name, button_id in button_map.items():
            pressed = report['buttons'].get(name, False)
            if self._button_state.get(button_id) != pressed:
                self._button_state[button_id] = pressed
                await self.event_bus.publish(
                    Event(
                        type=EventType.CONTROLLER_BUTTON,
                        data={'button': button_id, 'pressed': pressed}
                    )
                )

        # Gyroscope
        if 'gyro' in report:
            gyro = report['gyro']
            # Only emit if there's significant movement
            if abs(gyro['x']) > 0.01 or abs(gyro['y']) > 0.01 or abs(gyro['z']) > 0.01:
                await self.event_bus.publish(
                    Event(
                        type=EventType.CONTROLLER_GYRO,
                        data=gyro
                    )
                )

        # Accelerometer
        if 'accel' in report:
            await self.event_bus.publish(
                Event(
                    type=EventType.CONTROLLER_ACCEL,
                    data=report['accel']
                )
            )

    def stop(self) -> None:
        """Stop the controller handler."""
        self._running = False
        if self._device:
            self._device.close()
            self._device = None
