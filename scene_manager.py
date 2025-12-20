"""Scene manager - handles per-mushroom scene assignment and updates."""

from typing import Type

from events import EventBus, Event, EventType
from fixtures.mushroom import Mushroom
from scenes.base import Scene
from scenes.pastel_fade import PastelFadeScene
from scenes.audio_pulse import AudioPulseScene
from scenes.bio_glow import BioGlowScene
from scenes.manual import ManualScene
from inputs.ps4 import PS4Button


class SceneManager:
    """Manages scene assignment and updates for all mushrooms."""

    # Available scenes mapped to controller buttons
    SCENE_BUTTONS: dict[int, Type[Scene]] = {
        PS4Button.TRIANGLE: PastelFadeScene,
        PS4Button.CIRCLE: AudioPulseScene,
        PS4Button.SQUARE: BioGlowScene,
        PS4Button.CROSS: ManualScene,
    }

    def __init__(self, mushrooms: list[Mushroom], event_bus: EventBus) -> None:
        self.mushrooms = mushrooms
        self.event_bus = event_bus

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
        event_bus.subscribe(EventType.OSC_AUDIO_BEAT, self._handle_audio)
        event_bus.subscribe(EventType.OSC_AUDIO_LEVEL, self._handle_audio)
        event_bus.subscribe(EventType.OSC_BIO, self._handle_bio)
        event_bus.subscribe(EventType.IDLE_TIMEOUT, self._handle_idle)

    def _handle_button(self, event: Event) -> None:
        """Handle controller button events."""
        data = event.data

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
