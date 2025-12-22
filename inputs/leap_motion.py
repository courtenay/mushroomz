"""Leap Motion hand tracking input handler.

Supports both modern Ultraleap Gemini SDK (leapc-python-api) and
legacy Leap Motion SDK. Falls back gracefully if not available.

Hand position is normalized to:
- X: -1 (left) to +1 (right)
- Y: 0 (bottom) to 1 (top)
- Z: -1 (near/towards user) to +1 (far/away from user)
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from events import EventBus, Event, EventType
from .base import InputHandler, InputConfig
from .registry import register


@dataclass
class HandData:
    """Normalized hand tracking data."""
    hand_type: str  # "left" or "right"
    palm_x: float  # -1 to 1 (left to right)
    palm_y: float  # 0 to 1 (bottom to top)
    palm_z: float  # -1 to 1 (near to far)
    grab_strength: float  # 0 to 1 (open to closed fist)
    pinch_strength: float  # 0 to 1 (not pinching to pinching)
    fingers_extended: int  # 0 to 5
    velocity_x: float  # Normalized velocity
    velocity_y: float
    velocity_z: float


@dataclass
class LeapMotionConfig(InputConfig):
    """Configuration for Leap Motion controller."""
    interaction_box_width: float = 250.0  # X range: -125 to +125 mm
    interaction_box_height: float = 250.0  # Y range: 0 to 250 mm above sensor
    interaction_box_depth: float = 200.0  # Z range: -100 to +100 mm


@register
class LeapMotionController(InputHandler):
    """Leap Motion hand tracking input handler.

    Publishes LEAP_HAND events with normalized hand position and gesture data.
    Supports hot-connect (waits for Leap service to become available).
    """

    name = "leap_motion"
    description = "Leap Motion hand tracking sensor"
    config_class = LeapMotionConfig
    produces_events = [EventType.LEAP_HAND]

    def __init__(self, event_bus: EventBus, config: LeapMotionConfig | None = None) -> None:
        super().__init__(event_bus, config)
        self._connected = False
        self._connection: Any = None  # Gemini SDK connection
        self._connection_context: Any = None  # Gemini SDK context manager
        self._controller: Any = None  # Legacy SDK controller
        self._listener: Any = None
        self._sdk_type: str | None = None  # "gemini" or "legacy"

        # Interaction box normalization (from config)
        cfg = self.config if isinstance(self.config, LeapMotionConfig) else LeapMotionConfig()
        self.INTERACTION_BOX_WIDTH = cfg.interaction_box_width
        self.INTERACTION_BOX_HEIGHT = cfg.interaction_box_height
        self.INTERACTION_BOX_DEPTH = cfg.interaction_box_depth

        # Track last hand state for gesture detection
        self._last_hands: dict[str, HandData] = {}

    def _try_init_gemini(self) -> bool:
        """Try to initialize modern Ultraleap Gemini SDK."""
        try:
            import leap

            class GeminiListener(leap.Listener):
                def __init__(self, handler: "LeapMotionController"):
                    self.handler = handler

                def on_connection_event(self, event: Any) -> None:
                    print("Leap Motion: Connected to service")

                def on_tracking_event(self, event: Any) -> None:
                    self.handler._process_gemini_frame(event)

            self._connection = leap.Connection()
            self._listener = GeminiListener(self)
            self._connection.add_listener(self._listener)
            self._connection_context = self._connection.open()
            self._connection_context.__enter__()
            self._connection.set_tracking_mode(leap.TrackingMode.Desktop)
            self._sdk_type = "gemini"
            print("Leap Motion initialized (Gemini SDK)")
            return True
        except ImportError:
            return False
        except Exception as e:
            print(f"Gemini SDK error: {e}")
            return False

    def _try_init_legacy(self) -> bool:
        """Try to initialize legacy Leap Motion SDK (v2/v3)."""
        try:
            import Leap

            class LegacyListener(Leap.Listener):
                def __init__(self, handler: "LeapMotionController"):
                    super().__init__()
                    self.handler = handler

                def on_frame(self, controller: Any) -> None:
                    frame = controller.frame()
                    self.handler._process_legacy_frame(frame)

            self._controller = Leap.Controller()
            self._listener = LegacyListener(self)
            self._controller.add_listener(self._listener)
            self._sdk_type = "legacy"
            print("Leap Motion initialized (Legacy SDK)")
            return True
        except ImportError:
            return False
        except Exception as e:
            print(f"Legacy SDK error: {e}")
            return False

    def _normalize_position(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        """Normalize position from mm to -1/+1 range."""
        norm_x = max(-1, min(1, x / (self.INTERACTION_BOX_WIDTH / 2)))
        norm_y = max(0, min(1, y / self.INTERACTION_BOX_HEIGHT))
        norm_z = max(-1, min(1, z / (self.INTERACTION_BOX_DEPTH / 2)))
        return norm_x, norm_y, norm_z

    def _normalize_velocity(self, vx: float, vy: float, vz: float) -> tuple[float, float, float]:
        """Normalize velocity (mm/s) to useful range."""
        # Scale down - 500mm/s is considered "fast"
        scale = 500.0
        return vx / scale, vy / scale, vz / scale

    def _process_gemini_frame(self, event: Any) -> None:
        """Process a frame from Gemini SDK."""
        if not hasattr(event, 'hands') or not event.hands:
            return

        for hand in event.hands:
            try:
                palm = hand.palm
                pos = palm.position
                vel = palm.velocity

                norm_x, norm_y, norm_z = self._normalize_position(
                    pos.x, pos.y, -pos.z  # Z is inverted in Leap coordinate system
                )
                vel_x, vel_y, vel_z = self._normalize_velocity(vel.x, vel.y, vel.z)

                hand_data = HandData(
                    hand_type="left" if hand.type == 0 else "right",
                    palm_x=norm_x,
                    palm_y=norm_y,
                    palm_z=norm_z,
                    grab_strength=hand.grab_strength,
                    pinch_strength=hand.pinch_strength,
                    fingers_extended=sum(1 for f in hand.digits if f.is_extended),
                    velocity_x=vel_x,
                    velocity_y=vel_y,
                    velocity_z=vel_z,
                )

                self._publish_hand_event(hand_data)
            except Exception as e:
                print(f"Error processing Gemini hand: {e}")

    def _process_legacy_frame(self, frame: Any) -> None:
        """Process a frame from legacy SDK."""
        if not frame.hands:
            return

        for hand in frame.hands:
            try:
                palm = hand.palm_position
                vel = hand.palm_velocity

                norm_x, norm_y, norm_z = self._normalize_position(
                    palm.x, palm.y, -palm.z
                )
                vel_x, vel_y, vel_z = self._normalize_velocity(vel.x, vel.y, vel.z)

                # Count extended fingers
                extended = sum(1 for f in hand.fingers if f.is_extended)

                hand_data = HandData(
                    hand_type="left" if hand.is_left else "right",
                    palm_x=norm_x,
                    palm_y=norm_y,
                    palm_z=norm_z,
                    grab_strength=hand.grab_strength,
                    pinch_strength=hand.pinch_strength,
                    fingers_extended=extended,
                    velocity_x=vel_x,
                    velocity_y=vel_y,
                    velocity_z=vel_z,
                )

                self._publish_hand_event(hand_data)
            except Exception as e:
                print(f"Error processing legacy hand: {e}")

    def _publish_hand_event(self, hand_data: HandData) -> None:
        """Publish hand tracking event."""
        self._last_hands[hand_data.hand_type] = hand_data

        self.event_bus.publish_sync(
            Event(
                type=EventType.LEAP_HAND,
                data={
                    "hand_type": hand_data.hand_type,
                    "palm_x": hand_data.palm_x,
                    "palm_y": hand_data.palm_y,
                    "palm_z": hand_data.palm_z,
                    "grab_strength": hand_data.grab_strength,
                    "pinch_strength": hand_data.pinch_strength,
                    "fingers_extended": hand_data.fingers_extended,
                    "velocity_x": hand_data.velocity_x,
                    "velocity_y": hand_data.velocity_y,
                    "velocity_z": hand_data.velocity_z,
                }
            )
        )

    async def run(self) -> None:
        """Run the Leap Motion input loop with hot-connect support."""
        self._running = True
        reconnect_interval = 3.0

        print("Leap Motion: Searching for device...")

        while self._running:
            if not self._connected:
                # Try to connect
                if self._try_init_gemini() or self._try_init_legacy():
                    self._connected = True
                else:
                    await asyncio.sleep(reconnect_interval)
                    continue

            # The SDK callbacks handle frame processing
            # Just keep the loop alive and check connection (legacy only)
            await asyncio.sleep(0.1)

            # Check if still connected (legacy SDK only - Gemini uses callbacks)
            if self._sdk_type == "legacy":
                try:
                    if not self._controller.is_connected:
                        self._handle_disconnect()
                except Exception:
                    self._handle_disconnect()

    def _handle_disconnect(self) -> None:
        """Handle Leap Motion disconnection."""
        if self._connected:
            print("Leap Motion disconnected. Waiting for reconnection...")
            self._connected = False
            self._last_hands.clear()

            # Cleanup Gemini connection
            if self._connection_context:
                try:
                    self._connection_context.__exit__(None, None, None)
                except Exception:
                    pass
            self._connection = None
            self._connection_context = None

            # Cleanup legacy controller
            if self._controller and self._listener:
                try:
                    self._controller.remove_listener(self._listener)
                except Exception:
                    pass
            self._controller = None
            self._listener = None
            self._sdk_type = None

    def stop(self) -> None:
        """Stop the Leap Motion handler."""
        super().stop()
        # Cleanup Gemini connection
        if self._connection_context:
            try:
                self._connection_context.__exit__(None, None, None)
            except Exception:
                pass
        # Cleanup legacy controller
        if self._controller and self._listener:
            try:
                self._controller.remove_listener(self._listener)
            except Exception:
                pass

    @property
    def connected(self) -> bool:
        """Check if Leap Motion is currently connected."""
        return self._connected

    def get_hand(self, hand_type: str = "right") -> HandData | None:
        """Get the last known state of a hand."""
        return self._last_hands.get(hand_type)
