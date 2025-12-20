"""USB-DMX output implementations."""

import time
from typing import Any

from .base import DMXOutput


class OpenDMXOutput(DMXOutput):
    """ENTTEC Open DMX USB (and clones) output handler.

    Uses simple FTDI serial protocol - sends raw DMX data with break signal.
    Works with cheap FTDI-based USB-DMX adapters.
    """

    def __init__(self, port: str = "/dev/tty.usbserial-A10KPQVJ") -> None:
        super().__init__()
        self.port = port
        self._serial: Any = None
        self._running = False

    def start(self) -> None:
        """Start the USB-DMX output."""
        try:
            import serial
            # Open serial port with DMX settings
            # 250kbaud, 8 data bits, 2 stop bits, no parity
            self._serial = serial.Serial(
                port=self.port,
                baudrate=250000,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_TWO,
                parity=serial.PARITY_NONE,
                timeout=1,
            )
            self._running = True
            print(f"Open DMX USB started: {self.port}")
        except ImportError:
            print("Warning: pyserial not installed. USB-DMX disabled.")
            print("Install with: pip install pyserial")
            self._serial = None
        except Exception as e:
            print(f"Warning: Could not open USB-DMX port {self.port}: {e}")
            self._serial = None

    def stop(self) -> None:
        """Stop the USB-DMX output."""
        self._running = False
        if self._serial:
            self._serial.close()
            self._serial = None

    def send(self) -> None:
        """Send the DMX data with break signal."""
        if not self._serial:
            return

        try:
            # Send break signal by setting baudrate low and sending a null byte
            self._serial.baudrate = 96000  # This creates ~88us break
            self._serial.write(b'\x00')
            self._serial.baudrate = 250000

            # Send start code (0) + DMX data
            self._serial.write(b'\x00' + bytes(self._dmx_data))
        except Exception as e:
            print(f"USB-DMX send error: {e}")


class DMXUSBProOutput(DMXOutput):
    """ENTTEC DMX USB Pro output handler.

    Uses the ENTTEC Pro message protocol with headers.
    More reliable than Open DMX, supports RDM.
    """

    # ENTTEC Pro message labels
    SEND_DMX_LABEL = 6
    START_OF_MSG = 0x7E
    END_OF_MSG = 0xE7

    def __init__(self, port: str = "/dev/tty.usbserial-EN419206") -> None:
        super().__init__()
        self.port = port
        self._serial: Any = None

    def start(self) -> None:
        """Start the USB-DMX Pro output."""
        try:
            import serial
            self._serial = serial.Serial(
                port=self.port,
                baudrate=57600,  # Pro uses 57600 for communication
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
                parity=serial.PARITY_NONE,
                timeout=1,
            )
            print(f"DMX USB Pro started: {self.port}")
        except ImportError:
            print("Warning: pyserial not installed. USB-DMX Pro disabled.")
            self._serial = None
        except Exception as e:
            print(f"Warning: Could not open DMX USB Pro port {self.port}: {e}")
            self._serial = None

    def stop(self) -> None:
        """Stop the USB-DMX Pro output."""
        if self._serial:
            self._serial.close()
            self._serial = None

    def send(self) -> None:
        """Send the DMX data using ENTTEC Pro protocol."""
        if not self._serial:
            return

        try:
            # Build ENTTEC Pro message
            # Format: START_OF_MSG, LABEL, LENGTH_LSB, LENGTH_MSB, DATA..., END_OF_MSG
            dmx_packet = b'\x00' + bytes(self._dmx_data)  # Start code + data
            length = len(dmx_packet)

            message = bytes([
                self.START_OF_MSG,
                self.SEND_DMX_LABEL,
                length & 0xFF,  # Length LSB
                (length >> 8) & 0xFF,  # Length MSB
            ]) + dmx_packet + bytes([self.END_OF_MSG])

            self._serial.write(message)
        except Exception as e:
            print(f"DMX USB Pro send error: {e}")


class MultiOutput(DMXOutput):
    """Combines multiple DMX outputs to send to all simultaneously."""

    def __init__(self, outputs: list[DMXOutput]) -> None:
        super().__init__()
        self.outputs = outputs

    def start(self) -> None:
        """Start all outputs."""
        for output in self.outputs:
            output.start()

    def stop(self) -> None:
        """Stop all outputs."""
        for output in self.outputs:
            output.stop()

    def send(self) -> None:
        """Send to all outputs."""
        for output in self.outputs:
            # Copy our DMX data to each output
            output._dmx_data = bytearray(self._dmx_data)
            output.send()


def list_serial_ports() -> list[str]:
    """List available serial ports for USB-DMX adapters."""
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]
    except ImportError:
        return []


def auto_detect_usb_dmx() -> DMXOutput | None:
    """Try to auto-detect a USB-DMX adapter."""
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()

        for port in ports:
            desc = (port.description or "").lower()
            manufacturer = (port.manufacturer or "").lower()
            vid_pid = f"{port.vid:04x}:{port.pid:04x}" if port.vid and port.pid else ""

            # DMXking devices (EDMX1 PRO, ultraDMX, etc.) - use Pro protocol
            if "dmxking" in desc or "dmxking" in manufacturer or vid_pid == "0403:6001":
                if "pro" in desc or "edmx" in desc or "ultra" in desc:
                    print(f"Detected DMXking Pro device: {port.device}")
                    return DMXUSBProOutput(port.device)

            # ENTTEC DMX USB Pro
            if "dmx usb pro" in desc or "enttec" in manufacturer:
                if "pro" in desc:
                    print(f"Detected ENTTEC DMX USB Pro: {port.device}")
                    return DMXUSBProOutput(port.device)

            # ENTTEC Open DMX USB (FTDI) - fallback for generic FTDI
            if "ftdi" in desc or vid_pid == "0403:6001":
                print(f"Detected FTDI adapter (Open DMX mode): {port.device}")
                return OpenDMXOutput(port.device)

        return None
    except ImportError:
        return None
