"""Novation Launchpad Mini input handler with LED feedback."""

import asyncio
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable

from events import EventBus, Event, EventType
from .base import InputHandler, InputConfig
from .registry import register


# Launchpad Mini note mapping (8x8 grid + top row)
# Bottom-left is note 11, grid goes up and right
# Top row (scene launch) is CC 104-111

class LaunchpadColor(IntEnum):
    """Launchpad Mini color palette (velocity values)."""
    OFF = 0
    RED_LOW = 1
    RED = 2
    RED_FULL = 3
    AMBER_LOW = 17
    AMBER = 18
    AMBER_FULL = 19
    YELLOW = 34
    YELLOW_FULL = 35
    GREEN_LOW = 16
    GREEN = 32
    GREEN_FULL = 48
    # Additional colors (Mini MK3)
    ORANGE = 9
    LIME = 40
    CYAN = 44
    BLUE = 45
    PURPLE = 53
    PINK = 57
    WHITE = 3


@dataclass
class PadEvent:
    """Represents a pad press/release event."""
    x: int  # 0-7, left to right
    y: int  # 0-7, bottom to top (0 = bottom row)
    pressed: bool
    velocity: int  # 0-127


@dataclass
class LaunchpadConfig(InputConfig):
    """Configuration for Launchpad Mini."""
    device_names: list[str] | None = None  # Custom device names to search for

    def __post_init__(self) -> None:
        if self.device_names is None:
            self.device_names = ["Launchpad Mini", "Launchpad Mini MK3"]


@register
class LaunchpadMini(InputHandler):
    """Novation Launchpad Mini handler with bidirectional MIDI.

    Supports pad input and LED feedback for scene selection interface.
    """

    name = "launchpad"
    description = "Novation Launchpad Mini MIDI controller"
    config_class = LaunchpadConfig
    produces_events = [EventType.CONTROLLER_BUTTON]

    DEVICE_NAMES = ["Launchpad Mini", "Launchpad Mini MK3"]

    def __init__(self, event_bus: EventBus, config: LaunchpadConfig | None = None) -> None:
        super().__init__(event_bus, config)
        self._inport: Any = None
        self._outport: Any = None
        self._connected = False
        self._mido_available = False

        # Use custom device names if provided
        if isinstance(self.config, LaunchpadConfig) and self.config.device_names:
            self.DEVICE_NAMES = self.config.device_names

        # Pad state tracking (for toggle modes etc)
        self._pad_state: dict[tuple[int, int], bool] = {}

        # Callback for custom pad handling
        self._pad_callback: Callable[[PadEvent], None] | None = None

    def _init_mido(self) -> bool:
        """Initialize mido library."""
        if self._mido_available:
            return True
        try:
            import mido
            self._mido_available = True
            return True
        except ImportError:
            print("Warning: mido not installed. Launchpad input disabled.")
            print("  Install with: pip install mido python-rtmidi")
            return False

    def _find_launchpad(self) -> tuple[str | None, str | None]:
        """Find Launchpad MIDI ports. Returns (input_name, output_name)."""
        if not self._mido_available:
            return None, None

        import mido

        input_name = None
        output_name = None

        for name in mido.get_input_names():
            for device in self.DEVICE_NAMES:
                if device.lower() in name.lower():
                    input_name = name
                    break

        for name in mido.get_output_names():
            for device in self.DEVICE_NAMES:
                if device.lower() in name.lower():
                    output_name = name
                    break

        return input_name, output_name

    def _try_connect(self) -> bool:
        """Attempt to connect to Launchpad. Returns True if connected."""
        if not self._mido_available:
            return False

        import mido

        input_name, output_name = self._find_launchpad()

        if not input_name:
            return False

        try:
            self._inport = mido.open_input(input_name)
            if output_name:
                self._outport = mido.open_output(output_name)
            self._connected = True
            print(f"Launchpad connected: {input_name}")
            if output_name:
                self.clear_all()
            return True
        except Exception as e:
            print(f"Failed to connect to Launchpad: {e}")
            return False

    def _handle_disconnect(self) -> None:
        """Handle Launchpad disconnection."""
        if self._connected:
            print("Launchpad disconnected. Waiting for reconnection...")
            self._connected = False
            if self._inport:
                try:
                    self._inport.close()
                except Exception:
                    pass
                self._inport = None
            if self._outport:
                try:
                    self._outport.close()
                except Exception:
                    pass
                self._outport = None
            self._pad_state.clear()

    def _note_to_xy(self, note: int) -> tuple[int, int] | None:
        """Convert MIDI note to (x, y) grid position.

        Launchpad Mini MK3 uses: note = row * 16 + col
        where row 0 is TOP of grid, row 7 is BOTTOM.
        We use y=0 as bottom, so y = 7 - row.
        """
        if note < 0 or note > 127:
            return None
        row = note // 16  # 0-7 (0=top, 7=bottom)
        col = note % 16   # 0-7 for grid, 8 for side buttons
        if col > 7 or row > 7:
            return None  # Side button or out of range
        y = 7 - row  # Convert to y=0 at bottom
        return (col, y)

    def _note_to_side(self, note: int) -> int | None:
        """Convert MIDI note to side button index (A-H = 0-7).

        Side buttons are at column 8: notes 8, 24, 40, 56, 72, 88, 104, 120
        A (bottom) = 120, H (top) = 8
        """
        if note % 16 == 8:
            row = note // 16  # 0=top, 7=bottom
            return 7 - row  # A=0 (bottom), H=7 (top)
        return None

    def _xy_to_note(self, x: int, y: int) -> int:
        """Convert (x, y) grid position to MIDI note.

        y=0 is bottom row, x=0 is left column.
        Note = (7 - y) * 16 + x
        """
        row = 7 - y  # Convert y=0 (bottom) to row 7
        return row * 16 + x

    async def run(self) -> None:
        """Run the Launchpad input loop with hot-connect support."""
        if not self._init_mido():
            return

        self._running = True
        reconnect_interval = 2.0
        last_connect_attempt = 0.0

        while self._running:
            # If not connected, poll for Launchpad
            if not self._connected:
                import time
                now = time.monotonic()
                if now - last_connect_attempt >= reconnect_interval:
                    last_connect_attempt = now
                    if self._try_connect():
                        await self.event_bus.publish(
                            Event(
                                type=EventType.CONTROLLER_BUTTON,
                                data={"launchpad_connected": True}
                            )
                        )
                await asyncio.sleep(0.1)
                continue

            # Process MIDI messages
            try:
                for msg in self._inport.iter_pending():
                    await self._process_message(msg)
            except Exception:
                self._handle_disconnect()
                await self.event_bus.publish(
                    Event(
                        type=EventType.CONTROLLER_BUTTON,
                        data={"launchpad_connected": False}
                    )
                )
                continue

            await asyncio.sleep(0.008)  # ~120 Hz

    async def _process_message(self, msg: Any) -> None:
        """Process a MIDI message from the Launchpad."""
        if msg.type == 'note_on':
            # Check for side button first
            side_idx = self._note_to_side(msg.note)
            if side_idx is not None:
                pressed = msg.velocity > 0
                await self.event_bus.publish(
                    Event(
                        type=EventType.CONTROLLER_BUTTON,
                        data={
                            "launchpad_side": side_idx,
                            "pressed": pressed,
                        }
                    )
                )
                return

            # Main grid pad
            pos = self._note_to_xy(msg.note)
            if pos:
                x, y = pos
                pressed = msg.velocity > 0
                self._pad_state[(x, y)] = pressed

                pad_event = PadEvent(x=x, y=y, pressed=pressed, velocity=msg.velocity)

                if self._pad_callback:
                    self._pad_callback(pad_event)

                await self.event_bus.publish(
                    Event(
                        type=EventType.CONTROLLER_BUTTON,
                        data={
                            "launchpad_pad": (x, y),
                            "pressed": pressed,
                            "velocity": msg.velocity,
                        }
                    )
                )

        elif msg.type == 'note_off':
            # Check for side button first
            side_idx = self._note_to_side(msg.note)
            if side_idx is not None:
                await self.event_bus.publish(
                    Event(
                        type=EventType.CONTROLLER_BUTTON,
                        data={
                            "launchpad_side": side_idx,
                            "pressed": False,
                        }
                    )
                )
                return

            # Main grid pad
            pos = self._note_to_xy(msg.note)
            if pos:
                x, y = pos
                self._pad_state[(x, y)] = False

                pad_event = PadEvent(x=x, y=y, pressed=False, velocity=0)

                if self._pad_callback:
                    self._pad_callback(pad_event)

                await self.event_bus.publish(
                    Event(
                        type=EventType.CONTROLLER_BUTTON,
                        data={
                            "launchpad_pad": (x, y),
                            "pressed": False,
                            "velocity": 0,
                        }
                    )
                )

        elif msg.type == 'control_change':
            # Top row buttons (CC 104-111)
            if 104 <= msg.control <= 111:
                button_index = msg.control - 104
                pressed = msg.value > 0
                await self.event_bus.publish(
                    Event(
                        type=EventType.CONTROLLER_BUTTON,
                        data={
                            "launchpad_top": button_index,
                            "pressed": pressed,
                        }
                    )
                )

    # --- LED Control Methods ---

    def set_pad(self, x: int, y: int, color: int | LaunchpadColor) -> None:
        """Set a pad's LED color."""
        if not self._outport or not self._connected:
            return
        import mido
        note = self._xy_to_note(x, y)
        msg = mido.Message('note_on', note=note, velocity=int(color))
        try:
            self._outport.send(msg)
        except Exception:
            pass

    def set_top_button(self, index: int, color: int | LaunchpadColor) -> None:
        """Set a top row button's LED color (index 0-7)."""
        if not self._outport or not self._connected:
            return
        import mido
        msg = mido.Message('control_change', control=104 + index, value=int(color))
        try:
            self._outport.send(msg)
        except Exception:
            pass

    def set_side_button(self, index: int, color: int | LaunchpadColor) -> None:
        """Set a side column button's LED color (A-H = index 0-7).

        A (index 0, bottom) = note 120, H (index 7, top) = note 8
        Formula: note = (7 - index) * 16 + 8
        """
        if not self._outport or not self._connected:
            return
        import mido
        note = (7 - index) * 16 + 8
        msg = mido.Message('note_on', note=note, velocity=int(color))
        try:
            self._outport.send(msg)
        except Exception:
            pass

    def clear_all(self) -> None:
        """Turn off all LEDs."""
        if not self._outport or not self._connected:
            return
        for y in range(8):
            for x in range(8):
                self.set_pad(x, y, LaunchpadColor.OFF)
        for i in range(8):
            self.set_top_button(i, LaunchpadColor.OFF)
            self.set_side_button(i, LaunchpadColor.OFF)

    def set_row(self, y: int, color: int | LaunchpadColor) -> None:
        """Set all pads in a row to the same color."""
        for x in range(8):
            self.set_pad(x, y, color)

    def set_column(self, x: int, color: int | LaunchpadColor) -> None:
        """Set all pads in a column to the same color."""
        for y in range(8):
            self.set_pad(x, y, color)

    def set_grid(self, colors: list[list[int | LaunchpadColor]]) -> None:
        """Set entire grid from 2D array [y][x]."""
        for y, row in enumerate(colors):
            for x, color in enumerate(row):
                if x < 8 and y < 8:
                    self.set_pad(x, y, color)

    # --- Utility Methods ---

    def stop(self) -> None:
        """Stop the Launchpad handler."""
        super().stop()
        if self._connected:
            self.clear_all()
        if self._inport:
            try:
                self._inport.close()
            except Exception:
                pass
        if self._outport:
            try:
                self._outport.close()
            except Exception:
                pass

    @property
    def connected(self) -> bool:
        """Check if Launchpad is currently connected."""
        return self._connected

    def is_pad_pressed(self, x: int, y: int) -> bool:
        """Check if a pad is currently pressed."""
        return self._pad_state.get((x, y), False)

    def set_pad_callback(self, callback: Callable[[PadEvent], None] | None) -> None:
        """Set a callback for pad events (for direct handling without EventBus)."""
        self._pad_callback = callback
