#!/usr/bin/env python3
"""Mushroom Lighting Controller - Main entry point."""

import asyncio
import signal
import time

from config import Config
from config_manager import ConfigManager
from events import EventBus, EventType
from fixtures.mushroom import Mushroom
from inputs.ps4 import PS4Controller
from inputs.ds4_hid import DS4HIDController
from inputs.osc_server import OSCServer
from inputs.idle import IdleHandler
from output.artnet import ArtNetOutput
from scene_manager import SceneManager


class LightingController:
    """Main lighting controller orchestrating all components."""

    def __init__(self, config_path: str = "config.json") -> None:
        # Load configuration
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.config
        self._running = False

        # Create event bus
        self.event_bus = EventBus()

        # Create mushrooms from config
        self.mushrooms = [
            Mushroom(mc, i) for i, mc in enumerate(self.config.mushrooms)
        ]

        # Create components
        self.artnet = ArtNetOutput(
            ip=self.config.artnet_ip,
            universe=self.config.artnet_universe
        )
        # Try DS4 HID first (has gyro support), fall back to pygame
        self.ds4_hid = DS4HIDController(self.event_bus)
        self.ps4 = PS4Controller(self.event_bus)
        self.osc = OSCServer(self.event_bus, self.config.osc_port)
        self.idle = IdleHandler(self.event_bus, self.config.idle_timeout)
        self.scene_manager = SceneManager(self.mushrooms, self.event_bus)

        # Track activity for idle handler - subscribe to input events
        activity_handler = lambda e: self.idle.activity()
        for event_type in [
            EventType.CONTROLLER_BUTTON,
            EventType.CONTROLLER_AXIS,
            EventType.CONTROLLER_GYRO,
            EventType.CONTROLLER_ACCEL,
            EventType.OSC_AUDIO_BEAT,
            EventType.OSC_AUDIO_LEVEL,
            EventType.OSC_BIO,
        ]:
            self.event_bus.subscribe(event_type, activity_handler)

        # Web server reference (set during run)
        self._web_server = None

        # Flash queue for fixture identification
        # Each entry: (address, channels, color, end_time)
        self._flash_queue: list[tuple[int, int, list[int], float]] = []

    def add_flash(self, address: int, channels: int, color: list[int], duration: float) -> None:
        """Add a flash request to identify a fixture."""
        end_time = time.time() + duration
        # Remove any existing flash for same address
        self._flash_queue = [f for f in self._flash_queue if f[0] != address]
        self._flash_queue.append((address, channels, color, end_time))

    async def _render_loop(self) -> None:
        """Main render loop - updates scenes and sends DMX."""
        target_fps = self.config.dmx_fps
        frame_time = 1.0 / target_fps
        last_time = time.time()

        while self._running:
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time

            # Update scene manager (updates all mushrooms)
            self.scene_manager.update(dt)

            # Collect DMX data from all mushrooms
            for mushroom in self.mushrooms:
                dmx_data = mushroom.get_dmx_data()
                for address, values in dmx_data.items():
                    self.artnet.set_channels(address, values)

            # Apply flash overrides for fixture identification
            now = current_time
            active_flashes = []
            for flash in self._flash_queue:
                address, channels, color, end_time = flash
                if now < end_time:
                    # Flash is active - override DMX values
                    self.artnet.set_channels(address, color[:channels])
                    active_flashes.append(flash)
            self._flash_queue = active_flashes

            # Send DMX
            self.artnet.send()

            # Sleep to maintain frame rate
            elapsed = time.time() - current_time
            sleep_time = max(0, frame_time - elapsed)
            await asyncio.sleep(sleep_time)

    async def _run_web_server(self) -> None:
        """Run the FastAPI web server."""
        try:
            import uvicorn
            from web import create_app

            app = create_app(self)
            config = uvicorn.Config(
                app,
                host="0.0.0.0",
                port=self.config.web_port,
                log_level="warning",
            )
            self._web_server = uvicorn.Server(config)
            await self._web_server.serve()
        except ImportError:
            print("Warning: FastAPI/uvicorn not installed. Web interface disabled.")
            print("Install with: pip install fastapi uvicorn")

    async def run(self) -> None:
        """Run the lighting controller."""
        print("=" * 50)
        print("Mushroom Lighting Controller")
        print("=" * 50)
        print(f"Mushrooms: {len(self.mushrooms)}")
        print(f"Art-Net: {self.config.artnet_ip} universe {self.config.artnet_universe}")
        print(f"OSC port: {self.config.osc_port}")
        print(f"Web UI: http://localhost:{self.config.web_port}")
        print(f"DMX FPS: {self.config.dmx_fps}")
        print("=" * 50)
        print("\nPS4 Controls:")
        print("  D-pad Up: Select all mushrooms")
        print("  D-pad Left/Down/Right: Select individual mushroom")
        print("  Triangle: Pastel Fade scene")
        print("  Circle: Audio Pulse scene")
        print("  Square: Bio Glow scene")
        print("  X: Manual control scene")
        print("  Options: Blackout toggle")
        print("  Left stick: Hue/Saturation (manual mode)")
        print("  Right stick: Brightness")
        print("  Gyro tilt: Hue control (manual mode)")
        print("=" * 50)

        self._running = True

        # Start Art-Net
        self.artnet.start()

        # Start OSC server
        await self.osc.start()

        # Create tasks for all components
        tasks = [
            asyncio.create_task(self.event_bus.process(), name="event_bus"),
            asyncio.create_task(self.ds4_hid.run(), name="ds4_hid"),
            asyncio.create_task(self.ps4.run(), name="ps4"),
            asyncio.create_task(self.idle.run(), name="idle"),
            asyncio.create_task(self._render_loop(), name="render"),
            asyncio.create_task(self._run_web_server(), name="web"),
        ]

        print("\nRunning... Press Ctrl+C to exit\n")

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass

    def stop(self) -> None:
        """Stop the controller."""
        print("\nShutting down...")
        self._running = False
        self.ds4_hid.stop()
        self.ps4.stop()
        self.osc.stop()
        self.idle.stop()
        self.artnet.blackout()
        self.artnet.stop()
        if self._web_server:
            self._web_server.should_exit = True


async def main() -> None:
    """Main entry point."""
    controller = LightingController()

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def shutdown() -> None:
        controller.stop()
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    await controller.run()


if __name__ == "__main__":
    asyncio.run(main())
