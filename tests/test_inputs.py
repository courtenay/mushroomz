"""Tests for the input handler plugin system."""

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from events import EventBus, EventType
from inputs.base import InputHandler, InputConfig
from inputs.registry import register, get_handler, list_handlers, unregister, clear_registry
from inputs.manager import InputManager


# --- Test Fixtures ---


@pytest.fixture
def event_bus() -> EventBus:
    """Create a fresh EventBus for testing."""
    return EventBus()


@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure registry is in known state before/after each test.

    Saves existing handlers, clears registry, runs test, then restores them.
    This allows tests to register custom handlers without interference.
    """
    # Save existing handlers
    original_handlers = list_handlers()

    # Clear registry for isolated test
    clear_registry()

    yield

    # Restore original handlers
    clear_registry()
    for name, handler_cls in original_handlers.items():
        try:
            register(handler_cls)
        except ValueError:
            pass  # Already registered


# --- InputConfig Tests ---


class TestInputConfig:
    """Tests for InputConfig base class."""

    def test_default_enabled(self):
        """Test that config is enabled by default."""
        config = InputConfig()
        assert config.enabled is True

    def test_disable_via_constructor(self):
        """Test disabling via constructor."""
        config = InputConfig(enabled=False)
        assert config.enabled is False

    def test_subclass_inherits_enabled(self):
        """Test that subclasses inherit the enabled field."""
        @dataclass
        class CustomConfig(InputConfig):
            port: int = 8000

        config = CustomConfig()
        assert config.enabled is True
        assert config.port == 8000

        config2 = CustomConfig(enabled=False, port=9000)
        assert config2.enabled is False
        assert config2.port == 9000


# --- InputHandler Tests ---


class TestInputHandler:
    """Tests for InputHandler base class."""

    def test_abstract_cannot_instantiate(self, event_bus: EventBus):
        """Test that InputHandler cannot be instantiated directly."""
        with pytest.raises(TypeError):
            InputHandler(event_bus)

    def test_concrete_handler_init(self, event_bus: EventBus):
        """Test initializing a concrete handler."""
        class ConcreteHandler(InputHandler):
            name = "concrete"
            async def run(self) -> None:
                pass

        handler = ConcreteHandler(event_bus)
        assert handler.event_bus is event_bus
        assert handler._running is False
        assert isinstance(handler.config, InputConfig)

    def test_handler_with_custom_config(self, event_bus: EventBus):
        """Test handler with custom config class."""
        @dataclass
        class MyConfig(InputConfig):
            value: int = 42

        class MyHandler(InputHandler):
            name = "my_handler"
            config_class = MyConfig
            async def run(self) -> None:
                pass

        # Default config
        handler1 = MyHandler(event_bus)
        assert isinstance(handler1.config, MyConfig)
        assert handler1.config.value == 42

        # Custom config
        custom = MyConfig(value=100)
        handler2 = MyHandler(event_bus, custom)
        assert handler2.config.value == 100

    def test_handler_metadata(self, event_bus: EventBus):
        """Test class-level metadata."""
        class MetadataHandler(InputHandler):
            name = "metadata_test"
            description = "Test description"
            produces_events = [EventType.CONTROLLER_BUTTON]
            resets_idle = False

            async def run(self) -> None:
                pass

        assert MetadataHandler.name == "metadata_test"
        assert MetadataHandler.description == "Test description"
        assert MetadataHandler.produces_events == [EventType.CONTROLLER_BUTTON]
        assert MetadataHandler.resets_idle is False

    def test_stop_sets_running_false(self, event_bus: EventBus):
        """Test that stop() sets _running to False."""
        class TestHandler(InputHandler):
            name = "test"
            async def run(self) -> None:
                self._running = True
                while self._running:
                    await asyncio.sleep(0.01)

        handler = TestHandler(event_bus)
        handler._running = True
        handler.stop()
        assert handler._running is False

    def test_connected_default_true(self, event_bus: EventBus):
        """Test that connected property defaults to True."""
        class TestHandler(InputHandler):
            name = "test"
            async def run(self) -> None:
                pass

        handler = TestHandler(event_bus)
        assert handler.connected is True

    def test_repr(self, event_bus: EventBus):
        """Test handler repr."""
        class TestHandler(InputHandler):
            name = "test_repr"
            async def run(self) -> None:
                pass

        handler = TestHandler(event_bus)
        assert "TestHandler" in repr(handler)
        assert "test_repr" in repr(handler)


# --- Registry Tests ---


class TestRegistry:
    """Tests for handler registration system."""

    def test_register_decorator(self):
        """Test @register decorator."""
        @register
        class NewHandler(InputHandler):
            name = "new_handler"
            async def run(self) -> None:
                pass

        assert get_handler("new_handler") is NewHandler

    def test_register_case_insensitive(self):
        """Test that handler lookup is case-insensitive."""
        @register
        class CaseHandler(InputHandler):
            name = "Case_Handler"
            async def run(self) -> None:
                pass

        assert get_handler("case_handler") is CaseHandler
        assert get_handler("CASE_HANDLER") is CaseHandler
        assert get_handler("Case_Handler") is CaseHandler

    def test_register_duplicate_raises(self):
        """Test that registering same name twice raises error."""
        @register
        class FirstHandler(InputHandler):
            name = "duplicate"
            async def run(self) -> None:
                pass

        with pytest.raises(ValueError, match="already registered"):
            @register
            class SecondHandler(InputHandler):
                name = "duplicate"
                async def run(self) -> None:
                    pass

    def test_get_handler_not_found(self):
        """Test get_handler returns None for unknown name."""
        assert get_handler("nonexistent") is None

    def test_list_handlers(self):
        """Test list_handlers returns copy of registry."""
        @register
        class ListHandler1(InputHandler):
            name = "list1"
            async def run(self) -> None:
                pass

        @register
        class ListHandler2(InputHandler):
            name = "list2"
            async def run(self) -> None:
                pass

        handlers = list_handlers()
        assert "list1" in handlers
        assert "list2" in handlers

        # Verify it's a copy (modifying doesn't affect registry)
        handlers.clear()
        assert get_handler("list1") is ListHandler1

    def test_unregister(self):
        """Test unregister removes handler."""
        @register
        class UnregHandler(InputHandler):
            name = "unreg_test"
            async def run(self) -> None:
                pass

        assert get_handler("unreg_test") is UnregHandler
        result = unregister("unreg_test")
        assert result is True
        assert get_handler("unreg_test") is None

    def test_unregister_not_found(self):
        """Test unregister returns False for unknown handler."""
        result = unregister("nonexistent_handler")
        assert result is False

    def test_clear_registry(self):
        """Test clear_registry removes all handlers."""
        @register
        class ClearHandler(InputHandler):
            name = "clear_test"
            async def run(self) -> None:
                pass

        assert len(list_handlers()) > 0
        clear_registry()
        assert len(list_handlers()) == 0


# --- InputManager Tests ---


class TestInputManager:
    """Tests for InputManager lifecycle management."""

    def test_init(self, event_bus: EventBus):
        """Test InputManager initialization."""
        config = {"osc": {"port": 9000}}
        manager = InputManager(event_bus, config)

        assert manager.event_bus is event_bus
        assert manager._inputs_config == config
        assert manager._handlers == {}
        assert manager._tasks == {}

    def test_init_no_config(self, event_bus: EventBus):
        """Test InputManager with no config defaults to empty dict."""
        manager = InputManager(event_bus)
        assert manager._inputs_config == {}

    def test_load_enabled_handlers(self, event_bus: EventBus):
        """Test loading handlers that are enabled."""
        @dataclass
        class TestConfig(InputConfig):
            value: int = 10

        @register
        class TestLoadHandler(InputHandler):
            name = "test_load"
            config_class = TestConfig
            async def run(self) -> None:
                pass

        manager = InputManager(event_bus, {"test_load": {"value": 20}})
        loaded = manager.load_enabled_handlers()

        assert "test_load" in loaded
        handler = manager.get_handler("test_load")
        assert handler is not None
        assert handler.config.value == 20

    def test_load_handler_disabled(self, event_bus: EventBus):
        """Test that disabled handlers are not loaded."""
        @register
        class DisabledHandler(InputHandler):
            name = "disabled_test"
            async def run(self) -> None:
                pass

        manager = InputManager(event_bus, {"disabled_test": {"enabled": False}})
        loaded = manager.load_enabled_handlers()

        assert "disabled_test" not in loaded
        assert manager.get_handler("disabled_test") is None

    def test_load_handler_default_enabled(self, event_bus: EventBus):
        """Test that handlers without config are enabled by default."""
        @register
        class DefaultHandler(InputHandler):
            name = "default_enabled"
            async def run(self) -> None:
                pass

        manager = InputManager(event_bus)  # No config
        loaded = manager.load_enabled_handlers()

        assert "default_enabled" in loaded

    @pytest.mark.asyncio
    async def test_start_all(self, event_bus: EventBus):
        """Test starting all handlers."""
        run_count = 0

        @register
        class StartHandler(InputHandler):
            name = "start_test"
            async def run(self) -> None:
                nonlocal run_count
                self._running = True
                run_count += 1
                while self._running:
                    await asyncio.sleep(0.01)

        manager = InputManager(event_bus)
        manager.load_enabled_handlers()

        tasks = await manager.start_all()
        await asyncio.sleep(0.05)  # Let handler start

        assert len(tasks) >= 1
        assert run_count == 1

        # Cleanup
        manager.stop_all()
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def test_stop_all(self, event_bus: EventBus):
        """Test stopping all handlers."""
        @register
        class StopHandler(InputHandler):
            name = "stop_test"
            stopped = False

            async def run(self) -> None:
                pass

            def stop(self) -> None:
                super().stop()
                StopHandler.stopped = True

        manager = InputManager(event_bus)
        manager.load_enabled_handlers()
        manager.stop_all()

        assert StopHandler.stopped is True

    def test_get_handler(self, event_bus: EventBus):
        """Test get_handler returns loaded handler instance."""
        @register
        class GetHandler(InputHandler):
            name = "get_test"
            async def run(self) -> None:
                pass

        manager = InputManager(event_bus)
        manager.load_enabled_handlers()

        handler = manager.get_handler("get_test")
        assert handler is not None
        assert isinstance(handler, GetHandler)

        # Case insensitive
        assert manager.get_handler("GET_TEST") is handler

    def test_get_handler_not_loaded(self, event_bus: EventBus):
        """Test get_handler returns None for unloaded handler."""
        manager = InputManager(event_bus)
        assert manager.get_handler("nonexistent") is None

    def test_get_idle_event_types(self, event_bus: EventBus):
        """Test collecting event types that reset idle."""
        @register
        class IdleResetHandler(InputHandler):
            name = "idle_reset"
            produces_events = [EventType.CONTROLLER_BUTTON, EventType.CONTROLLER_AXIS]
            resets_idle = True
            async def run(self) -> None:
                pass

        @register
        class NoIdleResetHandler(InputHandler):
            name = "no_idle_reset"
            produces_events = [EventType.OSC_AUDIO_BEAT]
            resets_idle = False
            async def run(self) -> None:
                pass

        manager = InputManager(event_bus)
        manager.load_enabled_handlers()

        types = manager.get_idle_event_types()

        assert EventType.CONTROLLER_BUTTON in types
        assert EventType.CONTROLLER_AXIS in types
        assert EventType.OSC_AUDIO_BEAT not in types

    def test_get_status(self, event_bus: EventBus):
        """Test get_status returns handler info."""
        @register
        class StatusHandler(InputHandler):
            name = "status_test"
            description = "Status test handler"
            produces_events = [EventType.CONTROLLER_BUTTON]
            resets_idle = True

            async def run(self) -> None:
                pass

        manager = InputManager(event_bus)
        manager.load_enabled_handlers()

        status = manager.get_status()

        assert "status_test" in status
        info = status["status_test"]
        assert info["name"] == "status_test"
        assert info["description"] == "Status test handler"
        assert info["running"] is False
        assert info["connected"] is True
        assert "CONTROLLER_BUTTON" in info["produces_events"]
        assert info["resets_idle"] is True

    def test_handlers_property(self, event_bus: EventBus):
        """Test handlers property returns copy."""
        @register
        class PropHandler(InputHandler):
            name = "prop_test"
            async def run(self) -> None:
                pass

        manager = InputManager(event_bus)
        manager.load_enabled_handlers()

        handlers = manager.handlers
        assert "prop_test" in handlers

        # Verify it's a copy
        handlers.clear()
        assert manager.get_handler("prop_test") is not None


# --- Integration Tests ---


class TestIntegration:
    """Integration tests for the plugin system."""

    @pytest.mark.asyncio
    async def test_full_handler_lifecycle(self, event_bus: EventBus):
        """Test complete handler lifecycle: register -> load -> start -> stop."""
        events_received: list[Any] = []

        @dataclass
        class LifecycleConfig(InputConfig):
            message: str = "hello"

        @register
        class LifecycleHandler(InputHandler):
            name = "lifecycle"
            config_class = LifecycleConfig
            produces_events = [EventType.CONTROLLER_BUTTON]

            async def run(self) -> None:
                self._running = True
                await self.event_bus.publish(
                    type("Event", (), {
                        "type": EventType.CONTROLLER_BUTTON,
                        "data": {"message": self.config.message}
                    })()
                )
                while self._running:
                    await asyncio.sleep(0.01)

        # Subscribe to events
        def handler(event: Any) -> None:
            events_received.append(event)
        event_bus.subscribe(EventType.CONTROLLER_BUTTON, handler)

        # Create manager with custom config
        manager = InputManager(event_bus, {"lifecycle": {"message": "world"}})
        loaded = manager.load_enabled_handlers()

        assert "lifecycle" in loaded

        # Start event processing
        event_task = asyncio.create_task(event_bus.process())

        # Start handlers
        tasks = await manager.start_all()
        await asyncio.sleep(0.1)  # Let events process

        # Stop everything
        manager.stop_all()
        for task in tasks:
            task.cancel()
        event_task.cancel()

        try:
            await asyncio.gather(event_task, *tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass

        # Verify event was received with custom config
        assert len(events_received) >= 1
        assert events_received[0].data["message"] == "world"
