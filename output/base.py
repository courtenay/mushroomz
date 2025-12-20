"""Base DMX output interface."""

from abc import ABC, abstractmethod


class DMXOutput(ABC):
    """Abstract base class for DMX output handlers."""

    def __init__(self) -> None:
        self._dmx_data = bytearray(512)

    @abstractmethod
    def start(self) -> None:
        """Start the DMX output."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the DMX output."""
        pass

    @abstractmethod
    def send(self) -> None:
        """Send the DMX data."""
        pass

    def set_channel(self, address: int, value: int) -> None:
        """Set a single DMX channel (1-indexed address)."""
        if 1 <= address <= 512:
            self._dmx_data[address - 1] = max(0, min(255, value))

    def set_channels(self, address: int, values: list[int]) -> None:
        """Set multiple consecutive DMX channels (1-indexed address)."""
        for i, value in enumerate(values):
            self.set_channel(address + i, value)

    def blackout(self) -> None:
        """Set all channels to zero."""
        self._dmx_data = bytearray(512)
        self.send()

    def get_channel(self, address: int) -> int:
        """Get current value of a DMX channel (for debugging)."""
        if 1 <= address <= 512:
            return self._dmx_data[address - 1]
        return 0

    @property
    def dmx_data(self) -> bytearray:
        """Get the current DMX data buffer."""
        return self._dmx_data
