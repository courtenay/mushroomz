"""Scene manager - handles per-mushroom scene assignment and updates."""

from typing import Type, Any

from events import EventBus, Event, EventType
from fixtures.mushroom import Mushroom
from scenes.base import Scene
from scenes.pastel_fade import PastelFadeScene
from scenes.audio_pulse import AudioPulseScene
from scenes.bio_glow import BioGlowScene
from scenes.manual import ManualScene
from inputs.ps4 import PS4Button
from inputs.launchpad import LaunchpadColor


class SceneManager:
    """Manages scene assignment and updates for all mushrooms."""

    # Available scenes mapped to controller buttons
    SCENE_BUTTONS: dict[int, Type[Scene]] = {
        PS4Button.TRIANGLE: PastelFadeScene,
        PS4Button.CIRCLE: AudioPulseScene,
        PS4Button.SQUARE: BioGlowScene,
        PS4Button.CROSS: ManualScene,
    }

    # Launchpad grid mapping (row 0 = bottom)
    # Each row is a mushroom, columns are scenes
    # Row 7: Selection row (All, M1, M2, M3, M4, ...)
    # Rows 0-3: Mushroom 1-4 scene selection
    LAUNCHPAD_SCENES: list[Type[Scene]] = [
        PastelFadeScene,  # Column 0 - Green
        AudioPulseScene,  # Column 1 - Red
        BioGlowScene,     # Column 2 - Purple
        ManualScene,      # Column 3 - Yellow
    ]

    LAUNCHPAD_SCENE_COLORS: list[LaunchpadColor] = [
        LaunchpadColor.GREEN,
        LaunchpadColor.RED,
        LaunchpadColor.PURPLE,
        LaunchpadColor.YELLOW,
    ]

    def __init__(
        self,
        mushrooms: list[Mushroom],
        event_bus: EventBus,
        launchpad: Any | None = None,
    ) -> None:
        self.mushrooms = mushrooms
        self.event_bus = event_bus
        self.launchpad = launchpad

        # Per-mushroom scene instances
        self._scenes: dict[int, Scene] = {}

        # Selection state
        self._selected: set[int] = set(m.id for m in mushrooms)  # All selected initially
        self._blackout = False

        # Initialize all mushrooms to pastel fade
        for mushroom in mushrooms:
            scene = PastelFadeScene()
            scene.activate()
            self._scenes[mushroom.id] = scene

        # Subscribe to events
        event_bus.subscribe(EventType.CONTROLLER_BUTTON, self._handle_button)
        event_bus.subscribe(EventType.CONTROLLER_AXIS, self._handle_axis)
        event_bus.subscribe(EventType.CONTROLLER_GYRO, self._handle_gyro)
        event_bus.subscribe(EventType.OSC_AUDIO_BEAT, self._handle_audio)
        event_bus.subscribe(EventType.OSC_AUDIO_LEVEL, self._handle_audio)
        event_bus.subscribe(EventType.OSC_BIO, self._handle_bio)
        event_bus.subscribe(EventType.IDLE_TIMEOUT, self._handle_idle)

        # Initial launchpad LED update
        self._update_launchpad_leds()

    def _handle_button(self, event: Event) -> None:
        """Handle controller button events."""
        data = event.data

        # Handle Launchpad connection
        if "launchpad_connected" in data:
            if data["launchpad_connected"]:
                self._update_launchpad_leds()
            return

        # Handle Launchpad pad press
        if "launchpad_pad" in data:
            if data.get("pressed"):
                self._handle_launchpad_pad(data["launchpad_pad"])
            return

        # Handle Launchpad top button press
        if "launchpad_top" in data:
            if data.get("pressed"):
                self._handle_launchpad_top(data["launchpad_top"])
            return

        # Handle Launchpad side button press (A-H for mushroom selection)
        if "launchpad_side" in data:
            if data.get("pressed"):
                self._handle_launchpad_side(data["launchpad_side"])
            return

        # Handle D-pad for selection
        if "dpad" in data:
            x, y = data["dpad"]
            if y == 1:  # Up - select all
                self._selected = set(m.id for m in self.mushrooms)
                print("Selected: All mushrooms")
            elif y == -1:  # Down - mushroom 2
                self._selected = {1}
                print("Selected: Mushroom 2")
            elif x == -1:  # Left - mushroom 1
                self._selected = {0}
                print("Selected: Mushroom 1")
            elif x == 1:  # Right - mushroom 3
                self._selected = {2}
                print("Selected: Mushroom 3")
            return

        button = data.get("button")
        pressed = data.get("pressed", False)

        if not pressed:
            return

        # Handle scene switching
        if button in self.SCENE_BUTTONS:
            scene_class = self.SCENE_BUTTONS[button]
            for mushroom_id in self._selected:
                old_scene = self._scenes.get(mushroom_id)
                if old_scene:
                    old_scene.deactivate()
                new_scene = scene_class()
                new_scene.activate()
                self._scenes[mushroom_id] = new_scene
                print(f"Mushroom {mushroom_id + 1}: {new_scene.name}")
            return

        # L1/R1 for individual mushroom toggle
        if button == PS4Button.L1:
            # Cycle to previous mushroom in selection
            if len(self._selected) == len(self.mushrooms):
                self._selected = {0}
            else:
                min_id = min(self._selected)
                new_id = (min_id - 1) % len(self.mushrooms)
                self._selected = {new_id}
        elif button == PS4Button.R1:
            # Cycle to next mushroom in selection
            if len(self._selected) == len(self.mushrooms):
                self._selected = {0}
            else:
                max_id = max(self._selected)
                new_id = (max_id + 1) % len(self.mushrooms)
                self._selected = {new_id}

        # Options for blackout
        if button == PS4Button.OPTIONS:
            self._blackout = not self._blackout
            print(f"Blackout: {'ON' if self._blackout else 'OFF'}")

    def _handle_axis(self, event: Event) -> None:
        """Forward axis events to active scenes."""
        for mushroom in self.mushrooms:
            if mushroom.id in self._selected:
                scene = self._scenes.get(mushroom.id)
                if scene:
                    scene.handle_event(event, mushroom)

    def _handle_gyro(self, event: Event) -> None:
        """Forward gyro events to active scenes."""
        for mushroom in self.mushrooms:
            if mushroom.id in self._selected:
                scene = self._scenes.get(mushroom.id)
                if scene:
                    scene.handle_event(event, mushroom)

    def _handle_audio(self, event: Event) -> None:
        """Forward audio events to all mushrooms."""
        for mushroom in self.mushrooms:
            scene = self._scenes.get(mushroom.id)
            if scene:
                scene.handle_event(event, mushroom)

    def _handle_bio(self, event: Event) -> None:
        """Forward bio events to targeted mushroom."""
        target_id = event.mushroom_id
        for mushroom in self.mushrooms:
            if target_id is None or mushroom.id == target_id:
                scene = self._scenes.get(mushroom.id)
                if scene:
                    scene.handle_event(event, mushroom)

    def _handle_idle(self, event: Event) -> None:
        """Switch all mushrooms to pastel fade on idle."""
        print("Idle timeout - switching to pastel fade")
        for mushroom in self.mushrooms:
            old_scene = self._scenes.get(mushroom.id)
            if old_scene:
                old_scene.deactivate()
            new_scene = PastelFadeScene()
            new_scene.activate()
            self._scenes[mushroom.id] = new_scene

    def update(self, dt: float) -> None:
        """Update all mushrooms."""
        if self._blackout:
            for mushroom in self.mushrooms:
                mushroom.set_intensity(0.0)
            return

        for mushroom in self.mushrooms:
            mushroom.set_intensity(1.0)
            scene = self._scenes.get(mushroom.id)
            if scene:
                scene.update(mushroom, dt)

    def get_selected_names(self) -> str:
        """Get names of selected mushrooms for display."""
        if len(self._selected) == len(self.mushrooms):
            return "All"
        return ", ".join(
            f"M{i+1}" for i in sorted(self._selected)
        )

    # --- Launchpad Methods ---

    def _handle_launchpad_pad(self, pos: tuple[int, int]) -> None:
        """Handle Launchpad pad press.

        Grid layout:
        - Row 0 (bottom): Global actions (col 0=All, col 7=Blackout)
        - Rows 1-4: Per-mushroom scene selection (M1-M4, cols 0-3 = scenes)
        """
        x, y = pos

        # Row 0: Global controls
        if y == 0:
            if x == 0:
                self._selected = set(m.id for m in self.mushrooms)
                print("Selected: All mushrooms")
            elif x == 7:
                self._blackout = not self._blackout
                print(f"Blackout: {'ON' if self._blackout else 'OFF'}")
            elif 1 <= x <= len(self.mushrooms):
                self._selected = {x - 1}
                print(f"Selected: Mushroom {x}")
            self._update_launchpad_leds()
            return

        # Rows 1-4: Per-mushroom scene selection (row 1 = M1, row 2 = M2, etc.)
        mushroom_id = y - 1  # Row 1 = mushroom 0, Row 2 = mushroom 1, etc.
        scene_col = x

        if 0 <= mushroom_id < len(self.mushrooms) and scene_col < len(self.LAUNCHPAD_SCENES):
            scene_class = self.LAUNCHPAD_SCENES[scene_col]
            old_scene = self._scenes.get(mushroom_id)
            if old_scene:
                old_scene.deactivate()
            new_scene = scene_class()
            new_scene.activate()
            self._scenes[mushroom_id] = new_scene
            print(f"Mushroom {mushroom_id + 1}: {new_scene.name}")
            self._update_launchpad_leds()

    def _handle_launchpad_top(self, index: int) -> None:
        """Handle Launchpad top row button press.

        Top row buttons (index 0-7):
        - 0-3: Apply scene to all selected mushrooms
        - 7: Toggle blackout
        """
        if index < len(self.LAUNCHPAD_SCENES):
            # Apply scene to all selected mushrooms
            scene_class = self.LAUNCHPAD_SCENES[index]
            for mushroom_id in self._selected:
                old_scene = self._scenes.get(mushroom_id)
                if old_scene:
                    old_scene.deactivate()
                new_scene = scene_class()
                new_scene.activate()
                self._scenes[mushroom_id] = new_scene
                print(f"Mushroom {mushroom_id + 1}: {new_scene.name}")
            self._update_launchpad_leds()
        elif index == 7:
            self._blackout = not self._blackout
            print(f"Blackout: {'ON' if self._blackout else 'OFF'}")
            self._update_launchpad_leds()

    def _handle_launchpad_side(self, index: int) -> None:
        """Handle Launchpad side column button press (A-H).

        Side buttons align with rows:
        - A (index 0): Select All (aligns with row 0 global)
        - B-E (index 1-4): Select mushroom for that row
        - H (index 7): Toggle blackout
        """
        if index == 0:
            # A = Select all
            self._selected = set(m.id for m in self.mushrooms)
            print("Selected: All mushrooms")
        elif index == 7:
            # H = Blackout
            self._blackout = not self._blackout
            print(f"Blackout: {'ON' if self._blackout else 'OFF'}")
        elif 1 <= index <= len(self.mushrooms):
            # B-E = Select mushroom for that row
            mushroom_id = index - 1
            if mushroom_id in self._selected:
                # Toggle off if already selected (but keep at least one)
                if len(self._selected) > 1:
                    self._selected.discard(mushroom_id)
                    print(f"Deselected: Mushroom {mushroom_id + 1}")
            else:
                self._selected.add(mushroom_id)
                print(f"Selected: Mushroom {mushroom_id + 1}")
        self._update_launchpad_leds()

    def _update_launchpad_leds(self) -> None:
        """Update Launchpad LEDs to reflect current state.

        Layout:
        - Row 0: Global controls (col 0=All, cols 1-4=M select, col 7=Blackout)
        - Rows 1-4: Per-mushroom scene grid
        - Side column: Selection for each row
        - Top row: Scene shortcuts
        """
        if not self.launchpad or not self.launchpad.connected:
            return

        # Clear grid first
        self.launchpad.clear_all()

        # --- Row 0: Global controls ---
        # Pad (0,0) = All (bright if all selected)
        if len(self._selected) == len(self.mushrooms):
            self.launchpad.set_pad(0, 0, LaunchpadColor.WHITE)
        else:
            self.launchpad.set_pad(0, 0, LaunchpadColor.AMBER_LOW)

        # Pads (1-4, 0): Individual mushroom quick-select
        for i, mushroom in enumerate(self.mushrooms):
            if i >= 4:
                break
            if mushroom.id in self._selected:
                self.launchpad.set_pad(i + 1, 0, LaunchpadColor.CYAN)
            else:
                self.launchpad.set_pad(i + 1, 0, LaunchpadColor.AMBER_LOW)

        # Pad (7,0): Blackout indicator
        if self._blackout:
            self.launchpad.set_pad(7, 0, LaunchpadColor.RED_FULL)
        else:
            self.launchpad.set_pad(7, 0, LaunchpadColor.RED_LOW)

        # --- Rows 1-4: Per-mushroom scene indicators ---
        for mushroom in self.mushrooms:
            row = mushroom.id + 1  # Mushroom 0 -> row 1, etc.
            if row > 4:
                break

            # Show scene buttons for this mushroom
            scene = self._scenes.get(mushroom.id)
            for col, scene_class in enumerate(self.LAUNCHPAD_SCENES):
                if isinstance(scene, scene_class):
                    # Active scene - full brightness
                    self.launchpad.set_pad(col, row, self.LAUNCHPAD_SCENE_COLORS[col])
                else:
                    # Inactive scene - dim
                    self.launchpad.set_pad(col, row, LaunchpadColor.AMBER_LOW)

        # --- Side column: Selection indicators ---
        # A (index 0): All select
        if len(self._selected) == len(self.mushrooms):
            self.launchpad.set_side_button(0, LaunchpadColor.WHITE)
        else:
            self.launchpad.set_side_button(0, LaunchpadColor.AMBER_LOW)

        # B-E (index 1-4): Mushroom selection for rows
        for i, mushroom in enumerate(self.mushrooms):
            if i >= 4:
                break
            if mushroom.id in self._selected:
                self.launchpad.set_side_button(i + 1, LaunchpadColor.CYAN)
            else:
                self.launchpad.set_side_button(i + 1, LaunchpadColor.AMBER_LOW)

        # H (index 7): Blackout
        if self._blackout:
            self.launchpad.set_side_button(7, LaunchpadColor.RED_FULL)
        else:
            self.launchpad.set_side_button(7, LaunchpadColor.RED_LOW)

        # --- Top row buttons: Scene shortcuts ---
        for i, color in enumerate(self.LAUNCHPAD_SCENE_COLORS):
            self.launchpad.set_top_button(i, color)

        # Top button 7: Blackout shortcut
        if self._blackout:
            self.launchpad.set_top_button(7, LaunchpadColor.RED_FULL)
        else:
            self.launchpad.set_top_button(7, LaunchpadColor.RED_LOW)
