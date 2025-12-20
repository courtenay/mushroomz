"""Art-Net DMX output."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stupidArtnet import StupidArtnet


class ArtNetOutput:
    """Art-Net DMX output handler."""

    def __init__(self, ip: str = "255.255.255.255", universe: int = 0) -> None:
        self.ip = ip
        self.universe = universe
        self._artnet: "StupidArtnet | None" = None
        self._dmx_data = bytearray(512)

    def start(self) -> None:
        """Start the Art-Net output."""
        try:
            from stupidArtnet import StupidArtnet
            self._artnet = StupidArtnet(self.ip, self.universe, 512, 40, True, True)
            self._artnet.start()
            print(f"Art-Net started: {self.ip} universe {self.universe}")
        except ImportError:
            print("Warning: stupidArtnet not installed. Running in simulation mode.")
            self._artnet = None

    def stop(self) -> None:
        """Stop the Art-Net output."""
        if self._artnet:
            self._artnet.stop()
            self._artnet = None

    def set_channel(self, address: int, value: int) -> None:
        """Set a single DMX channel (1-indexed address)."""
        if 1 <= address <= 512:
            self._dmx_data[address - 1] = max(0, min(255, value))

    def set_channels(self, address: int, values: list[int]) -> None:
        """Set multiple consecutive DMX channels (1-indexed address)."""
        for i, value in enumerate(values):
            self.set_channel(address + i, value)

    def send(self) -> None:
        """Send the DMX data."""
        if self._artnet:
            self._artnet.set(self._dmx_data)

    def blackout(self) -> None:
        """Set all channels to zero."""
        self._dmx_data = bytearray(512)
        self.send()

    def get_channel(self, address: int) -> int:
        """Get current value of a DMX channel (for debugging)."""
        if 1 <= address <= 512:
            return self._dmx_data[address - 1]
        return 0
