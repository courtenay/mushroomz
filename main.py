#!/usr/bin/env python3
"""Mushroom Lighting Controller - Main entry point."""

import asyncio
import signal
import time

from config import Config, DMXOutputConfig
from config_manager import ConfigManager
from events import EventBus, EventType
from fixtures.mushroom import Mushroom
from inputs import InputManager, list_handlers
from inputs.launchpad import LaunchpadMini
from inputs.idle import IdleHandler
from output import DMXOutput, ArtNetOutput, OpenDMXOutput, DMXUSBProOutput, MultiOutput, auto_detect_usb_dmx
from scene_manager import SceneManager


def create_dmx_output(config: DMXOutputConfig) -> DMXOutput:
    """Factory function to create DMX output based on config."""
    output_type = config.output_type.lower()

    if output_type == "artnet":
        return ArtNetOutput(ip=config.artnet_ip, universe=config.artnet_universe)

    elif output_type == "opendmx":
        if config.usb_port:
            return OpenDMXOutput(port=config.usb_port)
        else:
            # Try auto-detect
            output = auto_detect_usb_dmx()
            if output:
                return output
            print("Warning: No USB-DMX adapter found, falling back to Art-Net")
            return ArtNetOutput(ip=config.artnet_ip, universe=config.artnet_universe)

    elif output_type == "dmxpro":
        if config.usb_port:
            return DMXUSBProOutput(port=config.usb_port)
        else:
            print("Warning: USB port not specified for DMX USB Pro")
            return ArtNetOutput(ip=config.artnet_ip, universe=config.artnet_universe)

    elif output_type == "multi":
        # Send to both Art-Net and USB-DMX
        outputs: list[DMXOutput] = [
            ArtNetOutput(ip=config.artnet_ip, universe=config.artnet_universe)
        ]
        if config.usb_port:
            outputs.append(OpenDMXOutput(port=config.usb_port))
        else:
            usb_output = auto_detect_usb_dmx()
            if usb_output:
                outputs.append(usb_output)
        return MultiOutput(outputs)

    else:
        print(f"Warning: Unknown output type '{output_type}', using Art-Net")
        return ArtNetOutput(ip=config.artnet_ip, universe=config.artnet_universe)


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

        # Create DMX output based on config
        self.dmx_output = create_dmx_output(self.config.dmx_output)

        # Create input manager with config
        # Convert InputsConfig to dict for InputManager
        inputs_config = self.config.inputs.to_dict()
        # Migrate legacy osc_port and idle_timeout if not in inputs config
        if "port" not in inputs_config.get("osc", {}):
            inputs_config.setdefault("osc", {})["port"] = self.config.osc_port
        if "timeout" not in inputs_config.get("idle", {}):
            inputs_config.setdefault("idle", {})["timeout"] = self.config.idle_timeout

        self.input_manager = InputManager(self.event_bus, inputs_config)
        loaded = self.input_manager.load_enabled_handlers()
        print(f"Loaded input handlers: {', '.join(loaded)}")

        # Get special handlers for wiring
        self.launchpad = self.input_manager.get_handler("launchpad")
        self.idle = self.input_manager.get_handler("idle")
        self.ds4_hid = self.input_manager.get_handler("ds4_hid")
        self.ps4 = self.input_manager.get_handler("ps4")

        # Create scene manager (needs launchpad for LED feedback)
        self.scene_manager = SceneManager(
            self.mushrooms, self.event_bus, self.launchpad, self.config.scene_params
        )

        # Wire idle handler to reset on input events
        if self.idle and isinstance(self.idle, IdleHandler):
            activity_handler = lambda e: self.idle.activity()
            for event_type in self.input_manager.get_idle_event_types():
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
                    self.dmx_output.set_channels(address, values)

            # Apply flash overrides for fixture identification
            now = current_time
            active_flashes = []
            for flash in self._flash_queue:
                address, channels, color, end_time = flash
                if now < end_time:
                    # Flash is active - override DMX values
                    self.dmx_output.set_channels(address, color[:channels])
                    active_flashes.append(flash)
            self._flash_queue = active_flashes

            # Send DMX
            self.dmx_output.send()

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
        print(f"DMX Output: {self.config.dmx_output.output_type}")
        if self.config.dmx_output.output_type == "artnet":
            print(f"  Art-Net: {self.config.dmx_output.artnet_ip} universe {self.config.dmx_output.artnet_universe}")
        elif self.config.dmx_output.usb_port:
            print(f"  USB Port: {self.config.dmx_output.usb_port}")
        print(f"OSC port: {self.config.osc_port}")
        print(f"Web UI: http://localhost:{self.config.web_port}")
        print(f"DMX FPS: {self.config.dmx_fps}")
        print("=" * 50)
        print("\nAvailable Input Handlers:")
        for name, handler_cls in list_handlers().items():
            status = "enabled" if self.input_manager.get_handler(name) else "disabled"
            print(f"  {name}: {handler_cls.description} [{status}]")
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
        print("\nLaunchpad Mini Controls:")
        print("  Top row (1-8): Apply scene to selected | [8]=Blackout")
        print("  Side col (A-H): Select mushroom | [A]=All [H]=Blackout")
        print("  Row 0 (bottom): [All] [M1] [M2] [M3] [M4] ... [Blackout]")
        print("  Rows 1-4: Per-mushroom scene grid")
        print("    Col 0: Pastel Fade (green)")
        print("    Col 1: Audio Pulse (red)")
        print("    Col 2: Bio Glow (purple)")
        print("    Col 3: Manual (yellow)")
        print("=" * 50)
        print("\nLeap Motion Controls:")
        print("  Palm X: Hue control (left to right)")
        print("  Palm Y: Brightness (bottom to top)")
        print("  Palm Z: Saturation (near to far)")
        print("  Grab: Intensity modifier")
        print("  Pinch: Fine control")
        print("=" * 50)

        self._running = True

        # Start DMX output
        self.dmx_output.start()

        # Start all input handlers
        input_tasks = await self.input_manager.start_all()

        # Create tasks for all components
        tasks = [
            asyncio.create_task(self.event_bus.process(), name="event_bus"),
            asyncio.create_task(self._render_loop(), name="render"),
            asyncio.create_task(self._run_web_server(), name="web"),
            *input_tasks,
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
        self.input_manager.stop_all()
        self.dmx_output.blackout()
        self.dmx_output.stop()
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
