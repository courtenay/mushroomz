"""Art-Net DMX output."""

import socket
import struct

from .base import DMXOutput


class ArtNetOutput(DMXOutput):
    """Art-Net DMX output handler.

    Simple implementation that handles network errors gracefully.
    """

    # Art-Net constants
    ARTNET_PORT = 6454
    ARTNET_HEADER = b'Art-Net\x00'  # Art-Net magic
    ARTNET_OPCODE_DMX = 0x5000

    def __init__(self, ip: str = "255.255.255.255", universe: int = 0) -> None:
        super().__init__()
        self.ip = ip
        self.universe = universe
        self._socket: socket.socket | None = None
        self._sequence = 0

    def _build_packet(self) -> bytes:
        """Build an Art-Net DMX packet."""
        # Art-Net DMX packet structure:
        # - 8 bytes: "Art-Net\0"
        # - 2 bytes: OpCode (0x5000 for DMX, little-endian)
        # - 2 bytes: Protocol version (14, big-endian)
        # - 1 byte: Sequence (0-255)
        # - 1 byte: Physical port (0)
        # - 2 bytes: Universe (little-endian)
        # - 2 bytes: Length (big-endian, must be even, 2-512)
        # - n bytes: DMX data

        length = len(self._dmx_data)

        packet = (
            self.ARTNET_HEADER +
            struct.pack('<H', self.ARTNET_OPCODE_DMX) +  # OpCode (little-endian)
            struct.pack('>H', 14) +  # Protocol version (big-endian)
            struct.pack('B', self._sequence) +  # Sequence
            struct.pack('B', 0) +  # Physical
            struct.pack('<H', self.universe) +  # Universe (little-endian)
            struct.pack('>H', length) +  # Length (big-endian)
            bytes(self._dmx_data)
        )

        self._sequence = (self._sequence + 1) % 256
        return packet

    def start(self) -> None:
        """Start the Art-Net output."""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            print(f"Art-Net started: {self.ip} universe {self.universe}")
        except OSError as e:
            print(f"Warning: Could not create Art-Net socket: {e}")
            self._socket = None

    def stop(self) -> None:
        """Stop the Art-Net output."""
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

    def send(self) -> None:
        """Send the DMX data."""
        if not self._socket:
            return

        try:
            packet = self._build_packet()
            self._socket.sendto(packet, (self.ip, self.ARTNET_PORT))
        except OSError:
            # Network error (disconnected, host down, etc.) - silently ignore
            pass
