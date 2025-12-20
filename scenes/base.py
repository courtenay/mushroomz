"""Base scene class."""

from abc import ABC, abstractmethod

from events import Event
from fixtures.mushroom import Mushroom


class Scene(ABC):
    """Base class for lighting scenes."""

    name: str = "Base Scene"

    def __init__(self) -> None:
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def activate(self) -> None:
        """Called when scene becomes active."""
        self._active = True

    def deactivate(self) -> None:
        """Called when scene becomes inactive."""
        self._active = False

    @abstractmethod
    def update(self, mushroom: Mushroom, dt: float) -> None:
        """Update the mushroom's lighting state.

        Args:
            mushroom: The mushroom to update
            dt: Time since last update in seconds
        """
        pass

    def handle_event(self, event: Event, mushroom: Mushroom) -> None:
        """Handle an event for a specific mushroom.

        Override to respond to events like audio beats, bio sensors, etc.
        """
        pass
