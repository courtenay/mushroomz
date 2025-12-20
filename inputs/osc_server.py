"""OSC server for receiving audio and bio sensor data."""

import asyncio
from typing import Any

from events import EventBus, Event, EventType


class OSCServer:
    """OSC server for audio and bio sensor input."""

    def __init__(self, event_bus: EventBus, port: int = 8000) -> None:
        self.event_bus = event_bus
        self.port = port
        self._server: Any = None
        self._transport: Any = None

    def _handle_audio_beat(self, address: str, *args: Any) -> None:
        """Handle beat detection messages."""
        self.event_bus.publish_sync(
            Event(
                type=EventType.OSC_AUDIO_BEAT,
                data={"intensity": args[0] if args else 1.0}
            )
        )

    def _handle_audio_level(self, address: str, *args: Any) -> None:
        """Handle audio level messages."""
        self.event_bus.publish_sync(
            Event(
                type=EventType.OSC_AUDIO_LEVEL,
                data={
                    "level": args[0] if args else 0.0,
                    "low": args[1] if len(args) > 1 else 0.0,
                    "mid": args[2] if len(args) > 2 else 0.0,
                    "high": args[3] if len(args) > 3 else 0.0,
                }
            )
        )

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
        """Handle unknown OSC messages."""
        print(f"OSC: {address} {args}")

    async def start(self) -> None:
        """Start the OSC server."""
        try:
            from pythonosc.dispatcher import Dispatcher
            from pythonosc.osc_server import AsyncIOOSCUDPServer

            dispatcher = Dispatcher()
            dispatcher.map("/audio/beat", self._handle_audio_beat)
            dispatcher.map("/audio/level", self._handle_audio_level)
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
