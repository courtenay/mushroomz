#!/usr/bin/env python3
"""Mushroom Lighting Controller - Main entry point."""

import asyncio
import signal
import time

from config import DEFAULT_CONFIG, Config
from events import EventBus
from fixtures.mushroom import Mushroom
from inputs.ps4 import PS4Controller
from inputs.osc_server import OSCServer
from inputs.idle import IdleHandler
from output.artnet import ArtNetOutput
from scene_manager import SceneManager


class LightingController:
    """Main lighting controller orchestrating all components."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or DEFAULT_CONFIG
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
        self.ps4 = PS4Controller(self.event_bus)
        self.osc = OSCServer(self.event_bus, self.config.osc_port)
        self.idle = IdleHandler(self.event_bus, self.config.idle_timeout)
        self.scene_manager = SceneManager(self.mushrooms, self.event_bus)

        # Track activity for idle handler - subscribe to input events
        activity_handler = lambda e: self.idle.activity()
        from events import EventType
        for event_type in [
            EventType.CONTROLLER_BUTTON,
            EventType.CONTROLLER_AXIS,
            EventType.OSC_AUDIO_BEAT,
            EventType.OSC_AUDIO_LEVEL,
            EventType.OSC_BIO,
        ]:
            self.event_bus.subscribe(event_type, activity_handler)

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

            # Send DMX
            self.artnet.send()

            # Sleep to maintain frame rate
            elapsed = time.time() - current_time
            sleep_time = max(0, frame_time - elapsed)
            await asyncio.sleep(sleep_time)

    async def run(self) -> None:
        """Run the lighting controller."""
        print("=" * 50)
        print("Mushroom Lighting Controller")
        print("=" * 50)
        print(f"Mushrooms: {len(self.mushrooms)}")
        print(f"Art-Net: {self.config.artnet_ip} universe {self.config.artnet_universe}")
        print(f"OSC port: {self.config.osc_port}")
        print(f"DMX FPS: {self.config.dmx_fps}")
        print("=" * 50)
        print("\nControls:")
        print("  D-pad Up: Select all mushrooms")
        print("  D-pad Left/Down/Right: Select individual mushroom")
        print("  Triangle: Pastel Fade scene")
        print("  Circle: Audio Pulse scene")
        print("  Square: Bio Glow scene")
        print("  X: Manual control scene")
        print("  Options: Blackout toggle")
        print("  Left stick: Hue/Saturation (manual mode)")
        print("  Right stick: Brightness")
        print("=" * 50)

        self._running = True

        # Start Art-Net
        self.artnet.start()

        # Start OSC server
        await self.osc.start()

        # Create tasks for all components
        tasks = [
            asyncio.create_task(self.event_bus.process(), name="event_bus"),
            asyncio.create_task(self.ps4.run(), name="ps4"),
            asyncio.create_task(self.idle.run(), name="idle"),
            asyncio.create_task(self._render_loop(), name="render"),
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
        self.ps4.stop()
        self.osc.stop()
        self.idle.stop()
        self.artnet.blackout()
        self.artnet.stop()


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
