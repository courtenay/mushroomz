"""Art-Net DMX output."""

from typing import TYPE_CHECKING, Any

from .base import DMXOutput

if TYPE_CHECKING:
    from stupidArtnet import StupidArtnet


class ArtNetOutput(DMXOutput):
    """Art-Net DMX output handler."""

    def __init__(self, ip: str = "255.255.255.255", universe: int = 0) -> None:
        super().__init__()
        self.ip = ip
        self.universe = universe
        self._artnet: Any = None

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

    def send(self) -> None:
        """Send the DMX data."""
        if self._artnet:
            self._artnet.set(self._dmx_data)
