"""Leap Motion hand tracking input handler.

Supports both modern Ultraleap Gemini SDK (leapc-python-api) and
legacy Leap Motion SDK. Falls back gracefully if not available.

Hand position is normalized to:
- X: -1 (left) to +1 (right)
- Y: 0 (bottom) to 1 (top)
- Z: -1 (near/towards user) to +1 (far/away from user)

Gesture Recognition:
- Swipe: Fast directional hand movement (left/right/up/down)
- Push/Pull: Z-axis movement towards/away from sensor
- Grab: Closing hand into fist (grab_strength transition)
- Release: Opening hand from fist
- Tap: Quick downward motion followed by stop
- Circle: Circular motion detected via velocity direction changes
"""

import asyncio
import math
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any
from collections import deque

from events import EventBus, Event, EventType
from .base import InputHandler, InputConfig
from .registry import register


class GestureType(Enum):
    """Recognized gesture types."""
    SWIPE_LEFT = auto()
    SWIPE_RIGHT = auto()
    SWIPE_UP = auto()
    SWIPE_DOWN = auto()
    PUSH = auto()  # Hand moving away from user
    PULL = auto()  # Hand moving towards user
    GRAB = auto()  # Hand closing into fist
    RELEASE = auto()  # Hand opening from fist
    TAP = auto()  # Quick downward motion
    CIRCLE_CW = auto()  # Clockwise circle
    CIRCLE_CCW = auto()  # Counter-clockwise circle


@dataclass
class Gesture:
    """A detected gesture."""
    type: GestureType
    hand: str  # "left" or "right"
    strength: float  # 0-1, how confident/strong the gesture was
    timestamp: float = field(default_factory=time.time)


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
    # Gesture detection thresholds (tuned for reliability over sensitivity)
    swipe_velocity_threshold: float = 0.7  # Minimum velocity for swipe detection
    swipe_min_distance: float = 0.35  # Minimum travel distance for swipe
    push_pull_threshold: float = 0.5  # Z velocity threshold for push/pull
    push_pull_sustain: float = 0.15  # Seconds of sustained movement for push/pull
    grab_threshold: float = 0.75  # Grab strength to trigger grab gesture
    release_threshold: float = 0.25  # Grab strength to trigger release gesture
    tap_velocity_threshold: float = 0.6  # Downward velocity for tap
    tap_stop_threshold: float = 0.15  # Velocity must drop below this after tap
    circle_min_rotations: float = 0.85  # Minimum rotations to detect circle
    gesture_cooldown: float = 0.5  # Seconds between same gesture type (increased)


class GestureDetector:
    """Detects gestures from hand tracking data over time."""

    def __init__(self, config: LeapMotionConfig) -> None:
        self.config = config
        # History of hand positions for pattern detection
        self._history: dict[str, deque[tuple[float, HandData]]] = {
            "left": deque(maxlen=30),  # ~0.5 seconds at 60fps
            "right": deque(maxlen=30),
        }
        # Track grab state for edge detection
        self._grab_state: dict[str, bool] = {"left": False, "right": False}
        # Track velocity direction for circle detection
        self._velocity_angles: dict[str, deque[float]] = {
            "left": deque(maxlen=60),
            "right": deque(maxlen=60),
        }
        # Cooldown tracking
        self._last_gesture_time: dict[str, dict[GestureType, float]] = {
            "left": {},
            "right": {},
        }
        # Swipe tracking
        self._swipe_start: dict[str, tuple[float, float, float, float] | None] = {
            "left": None,
            "right": None,
        }
        # Push/pull tracking (sustained movement)
        self._push_pull_start: dict[str, tuple[float, float] | None] = {
            "left": None,  # (start_time, direction)
            "right": None,
        }

    def update(self, hand_data: HandData) -> list[Gesture]:
        """Process new hand data and return any detected gestures."""
        now = time.time()
        hand = hand_data.hand_type
        gestures: list[Gesture] = []

        # Add to history
        self._history[hand].append((now, hand_data))

        # Detect grab/release (state transitions)
        grab_gesture = self._detect_grab_release(hand_data, now)
        if grab_gesture:
            gestures.append(grab_gesture)

        # Detect swipes (fast directional movement)
        swipe_gesture = self._detect_swipe(hand_data, now)
        if swipe_gesture:
            gestures.append(swipe_gesture)

        # Detect push/pull (Z-axis movement)
        push_pull = self._detect_push_pull(hand_data, now)
        if push_pull:
            gestures.append(push_pull)

        # Detect tap (quick downward motion)
        tap_gesture = self._detect_tap(hand_data, now)
        if tap_gesture:
            gestures.append(tap_gesture)

        # Detect circle (rotational velocity pattern)
        circle_gesture = self._detect_circle(hand_data, now)
        if circle_gesture:
            gestures.append(circle_gesture)

        return gestures

    def _is_on_cooldown(self, hand: str, gesture_type: GestureType, now: float) -> bool:
        """Check if gesture is on cooldown."""
        last_time = self._last_gesture_time[hand].get(gesture_type, 0)
        return (now - last_time) < self.config.gesture_cooldown

    def _record_gesture(self, hand: str, gesture_type: GestureType, now: float) -> None:
        """Record gesture time for cooldown."""
        self._last_gesture_time[hand][gesture_type] = now

    def _detect_grab_release(self, hand_data: HandData, now: float) -> Gesture | None:
        """Detect grab (closing fist) and release (opening hand) gestures."""
        hand = hand_data.hand_type
        grab = hand_data.grab_strength
        was_grabbed = self._grab_state[hand]

        # Detect grab transition
        if not was_grabbed and grab >= self.config.grab_threshold:
            self._grab_state[hand] = True
            if not self._is_on_cooldown(hand, GestureType.GRAB, now):
                self._record_gesture(hand, GestureType.GRAB, now)
                return Gesture(GestureType.GRAB, hand, grab)

        # Detect release transition
        elif was_grabbed and grab <= self.config.release_threshold:
            self._grab_state[hand] = False
            if not self._is_on_cooldown(hand, GestureType.RELEASE, now):
                self._record_gesture(hand, GestureType.RELEASE, now)
                return Gesture(GestureType.RELEASE, hand, 1.0 - grab)

        return None

    def _detect_swipe(self, hand_data: HandData, now: float) -> Gesture | None:
        """Detect swipe gestures (fast directional movement)."""
        hand = hand_data.hand_type
        vx, vy = hand_data.velocity_x, hand_data.velocity_y
        speed = math.sqrt(vx * vx + vy * vy)

        # Start tracking when velocity exceeds threshold
        if speed >= self.config.swipe_velocity_threshold:
            if self._swipe_start[hand] is None:
                self._swipe_start[hand] = (now, hand_data.palm_x, hand_data.palm_y, speed)
        else:
            # Check if we had a swipe in progress
            start = self._swipe_start[hand]
            if start is not None:
                start_time, start_x, start_y, _ = start
                dx = hand_data.palm_x - start_x
                dy = hand_data.palm_y - start_y
                distance = math.sqrt(dx * dx + dy * dy)

                self._swipe_start[hand] = None

                if distance >= self.config.swipe_min_distance:
                    # Determine direction
                    if abs(dx) > abs(dy):
                        gesture_type = GestureType.SWIPE_RIGHT if dx > 0 else GestureType.SWIPE_LEFT
                    else:
                        gesture_type = GestureType.SWIPE_UP if dy > 0 else GestureType.SWIPE_DOWN

                    if not self._is_on_cooldown(hand, gesture_type, now):
                        self._record_gesture(hand, gesture_type, now)
                        return Gesture(gesture_type, hand, min(1.0, distance / 0.5))

        return None

    def _detect_push_pull(self, hand_data: HandData, now: float) -> Gesture | None:
        """Detect push (away) and pull (towards) gestures with sustained movement."""
        hand = hand_data.hand_type
        vz = hand_data.velocity_z
        threshold = self.config.push_pull_threshold
        sustain = self.config.push_pull_sustain

        # Check if we have sustained movement in one direction
        if abs(vz) >= threshold:
            direction = 1.0 if vz > 0 else -1.0
            start = self._push_pull_start[hand]

            if start is None:
                # Start tracking
                self._push_pull_start[hand] = (now, direction)
            elif start[1] == direction:
                # Same direction - check duration
                duration = now - start[0]
                if duration >= sustain:
                    self._push_pull_start[hand] = None
                    gesture_type = GestureType.PUSH if direction > 0 else GestureType.PULL
                    if not self._is_on_cooldown(hand, gesture_type, now):
                        self._record_gesture(hand, gesture_type, now)
                        return Gesture(gesture_type, hand, min(1.0, abs(vz)))
            else:
                # Direction changed - reset
                self._push_pull_start[hand] = (now, direction)
        else:
            # Velocity dropped - reset tracking
            self._push_pull_start[hand] = None

        return None

    def _detect_tap(self, hand_data: HandData, now: float) -> Gesture | None:
        """Detect tap gesture (quick downward motion that stops)."""
        hand = hand_data.hand_type
        history = self._history[hand]

        if len(history) < 5:
            return None

        # Look for pattern: fast downward -> slow/stop
        recent = list(history)[-5:]
        velocities = [h[1].velocity_y for h in recent]

        # Check if we had fast downward motion followed by stop
        had_fast_down = any(v < -self.config.tap_velocity_threshold for v in velocities[:-2])
        now_stopped = abs(velocities[-1]) < self.config.tap_stop_threshold

        if had_fast_down and now_stopped:
            if not self._is_on_cooldown(hand, GestureType.TAP, now):
                self._record_gesture(hand, GestureType.TAP, now)
                return Gesture(GestureType.TAP, hand, 1.0)

        return None

    def _detect_circle(self, hand_data: HandData, now: float) -> Gesture | None:
        """Detect circular motion via velocity direction tracking."""
        hand = hand_data.hand_type
        vx, vy = hand_data.velocity_x, hand_data.velocity_y
        speed = math.sqrt(vx * vx + vy * vy)

        # Only track when moving
        if speed > 0.1:
            angle = math.atan2(vy, vx)
            self._velocity_angles[hand].append(angle)

        angles = list(self._velocity_angles[hand])
        if len(angles) < 20:
            return None

        # Calculate cumulative angle change
        total_rotation = 0.0
        for i in range(1, len(angles)):
            diff = angles[i] - angles[i - 1]
            # Normalize to -pi to pi
            while diff > math.pi:
                diff -= 2 * math.pi
            while diff < -math.pi:
                diff += 2 * math.pi
            total_rotation += diff

        rotations = abs(total_rotation) / (2 * math.pi)

        if rotations >= self.config.circle_min_rotations:
            self._velocity_angles[hand].clear()
            gesture_type = GestureType.CIRCLE_CW if total_rotation > 0 else GestureType.CIRCLE_CCW
            if not self._is_on_cooldown(hand, gesture_type, now):
                self._record_gesture(hand, gesture_type, now)
                return Gesture(gesture_type, hand, min(1.0, rotations))

        return None

    def clear(self, hand: str | None = None) -> None:
        """Clear gesture detection state."""
        hands = [hand] if hand else ["left", "right"]
        for h in hands:
            self._history[h].clear()
            self._velocity_angles[h].clear()
            self._swipe_start[h] = None
            self._push_pull_start[h] = None


@register
class LeapMotionController(InputHandler):
    """Leap Motion hand tracking input handler.

    Publishes LEAP_HAND events with normalized hand position and gesture data.
    Publishes LEAP_GESTURE events when gestures are recognized.
    Supports hot-connect (waits for Leap service to become available).

    Gesture Types:
    - SWIPE_LEFT/RIGHT/UP/DOWN: Fast directional hand movement
    - PUSH/PULL: Z-axis movement towards/away from sensor
    - GRAB/RELEASE: Closing/opening fist
    - TAP: Quick downward motion
    - CIRCLE_CW/CCW: Circular motion
    """

    name = "leap_motion"
    description = "Leap Motion hand tracking sensor with gesture recognition"
    config_class = LeapMotionConfig
    produces_events = [EventType.LEAP_HAND, EventType.LEAP_GESTURE]

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

        # Gesture detection
        self._gesture_detector = GestureDetector(cfg)

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
        """Publish hand tracking event and detect gestures."""
        self._last_hands[hand_data.hand_type] = hand_data

        # Publish raw hand data
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

        # Run gesture detection
        gestures = self._gesture_detector.update(hand_data)
        for gesture in gestures:
            print(f"Gesture: {gesture.type.name} ({gesture.hand}) strength={gesture.strength:.2f}")
            self.event_bus.publish_sync(
                Event(
                    type=EventType.LEAP_GESTURE,
                    data={
                        "gesture": gesture.type.name,
                        "hand": gesture.hand,
                        "strength": gesture.strength,
                        "timestamp": gesture.timestamp,
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
            self._gesture_detector.clear()

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
