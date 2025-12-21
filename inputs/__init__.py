"""Input handlers for the lighting system.

This module provides a plugin architecture for input handlers:
- InputHandler: Abstract base class for creating handlers
- InputConfig: Base configuration class
- InputManager: Lifecycle manager for loading and running handlers
- register: Decorator to register handler classes
- list_handlers/get_handler: Query registered handlers

Example creating a new handler:
    from dataclasses import dataclass
    from inputs import InputHandler, InputConfig, register
    from events import EventBus, EventType

    @dataclass
    class MyConfig(InputConfig):
        port: int = 9000

    @register
    class MyHandler(InputHandler):
        name = "my_handler"
        description = "My custom input handler"
        config_class = MyConfig
        produces_events = [EventType.CONTROLLER_BUTTON]

        async def run(self) -> None:
            self._running = True
            while self._running:
                # Handle input...
                await asyncio.sleep(0.1)
"""

# Plugin infrastructure
from .base import InputHandler, InputConfig
from .registry import register, list_handlers, get_handler, unregister, clear_registry
from .manager import InputManager

# Import all handlers to trigger @register decorators
from .ps4 import PS4Controller, PS4Button, PS4Axis, PS4Config
from .ds4_hid import DS4HIDController, DS4Button, DS4HIDConfig
from .osc_server import OSCServer, OSCConfig
from .idle import IdleHandler, IdleConfig
from .launchpad import LaunchpadMini, LaunchpadColor, PadEvent, LaunchpadConfig
from .leap_motion import LeapMotionController, HandData, LeapMotionConfig

__all__ = [
    # Plugin infrastructure
    "InputHandler",
    "InputConfig",
    "InputManager",
    "register",
    "list_handlers",
    "get_handler",
    "unregister",
    "clear_registry",
    # Handler classes (for direct use / backward compatibility)
    "PS4Controller",
    "PS4Button",
    "PS4Axis",
    "PS4Config",
    "DS4HIDController",
    "DS4Button",
    "DS4HIDConfig",
    "OSCServer",
    "OSCConfig",
    "IdleHandler",
    "IdleConfig",
    "LaunchpadMini",
    "LaunchpadColor",
    "PadEvent",
    "LaunchpadConfig",
    "LeapMotionController",
    "HandData",
    "LeapMotionConfig",
]
