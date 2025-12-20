"""OSC server for receiving audio and bio sensor data."""

import asyncio
import sys
import time
from typing import Any

from events import EventBus, Event, EventType


class OSCServer:
    """OSC server for audio and bio sensor input."""

    def __init__(self, event_bus: EventBus, port: int = 8000) -> None:
        self.event_bus = event_bus
        self.port = port
        self._server: Any = None
        self._transport: Any = None

        # Audio state for display
        self._level = 0.0
        self._bass = 0.0
        self._mid = 0.0
        self._high = 0.0
        self._beat = False
        self._beat_time = 0.0
        self._last_display = 0.0

    def _update_display(self) -> None:
        """Update the terminal status line."""
        now = time.time()
        if now - self._last_display < 0.05:  # 20fps max
            return
        self._last_display = now

        # Beat indicator fades after 100ms
        beat_char = "●" if (now - self._beat_time) < 0.1 else "○"

        # Create level bars
        bar_len = 15
        level_bar = "█" * int(self._level * bar_len)
        bass_bar = "█" * int(self._bass * bar_len)

        # Color codes
        reset = "\033[0m"
        purple = "\033[35m"
        cyan = "\033[36m"
        yellow = "\033[33m"

        status = (
            f"\r{purple}♪{reset} "
            f"Level [{level_bar:<{bar_len}}] "
            f"Bass [{cyan}{bass_bar:<{bar_len}}{reset}] "
            f"{yellow}{beat_char}{reset}  "
        )
        sys.stdout.write(status)
        sys.stdout.flush()

    def _handle_audio_beat(self, address: str, *args: Any) -> None:
        """Handle beat detection messages."""
        intensity = args[0] if args else 1.0
        if intensity > 0:
            self._beat = True
            self._beat_time = time.time()
            self.event_bus.publish_sync(
                Event(
                    type=EventType.OSC_AUDIO_BEAT,
                    data={"intensity": float(intensity)}
                )
            )
        self._update_display()

    def _handle_audio_level(self, address: str, *args: Any) -> None:
        """Handle audio level messages."""
        self._level = float(args[0]) if args else 0.0
        self.event_bus.publish_sync(
            Event(
                type=EventType.OSC_AUDIO_LEVEL,
                data={
                    "level": self._level,
                    "low": self._bass,
                    "mid": self._mid,
                    "high": self._high,
                }
            )
        )
        self._update_display()

    def _handle_audio_bass(self, address: str, *args: Any) -> None:
        """Handle bass level messages."""
        self._bass = float(args[0]) if args else 0.0
        self._update_display()

    def _handle_audio_mid(self, address: str, *args: Any) -> None:
        """Handle mid level messages."""
        self._mid = float(args[0]) if args else 0.0

    def _handle_audio_high(self, address: str, *args: Any) -> None:
        """Handle high level messages."""
        self._high = float(args[0]) if args else 0.0

    def _handle_bio(self, address: str, *args: Any) -> None:
        """Handle bio sensor messages."""
        # Extract plant ID from address like /bio/plant1
        parts = address.split("/")
        plant_id = parts[-1] if parts else "unknown"

        # Try to map to mushroom ID
        mushroom_id = None
        if plant_id.startswith("plant"):
            try:
                mushroom_id = int(plant_id[5:]) - 1  # plant1 -> mushroom 0
            except ValueError:
                pass

        self.event_bus.publish_sync(
            Event(
                type=EventType.OSC_BIO,
                data={
                    "plant_id": plant_id,
                    "resistance": args[0] if args else 0.0,
                },
                mushroom_id=mushroom_id,
            )
        )

    def _default_handler(self, address: str, *args: Any) -> None:
        """Handle unknown OSC messages - silently ignore most."""
        # Only log truly unknown messages, not the common ones we don't need
        if not address.startswith(("/qlc/", "/live/")):
            pass  # Silently ignore

    async def start(self) -> None:
        """Start the OSC server."""
        try:
            from pythonosc.dispatcher import Dispatcher
            from pythonosc.osc_server import AsyncIOOSCUDPServer

            dispatcher = Dispatcher()
            dispatcher.map("/audio/beat", self._handle_audio_beat)
            dispatcher.map("/audio/level", self._handle_audio_level)
            dispatcher.map("/audio/bass", self._handle_audio_bass)
            dispatcher.map("/audio/mid", self._handle_audio_mid)
            dispatcher.map("/audio/high", self._handle_audio_high)
            dispatcher.map("/bio/*", self._handle_bio)
            dispatcher.set_default_handler(self._default_handler)

            self._server = AsyncIOOSCUDPServer(
                ("0.0.0.0", self.port),
                dispatcher,
                asyncio.get_event_loop()
            )
            self._transport, _ = await self._server.create_serve_endpoint()
            print(f"OSC server started on port {self.port}")
        except ImportError:
            print("Warning: python-osc not installed. OSC input disabled.")

    def stop(self) -> None:
        """Stop the OSC server."""
        if self._transport:
            self._transport.close()
            self._transport = None
        # Clear the status line
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()
