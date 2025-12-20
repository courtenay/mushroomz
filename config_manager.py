"""Configuration manager for JSON persistence and live updates."""

import json
from pathlib import Path
from typing import Callable

from config import Config, DEFAULT_CONFIG


class ConfigManager:
    """Manages configuration loading, saving, and live updates."""

    def __init__(self, config_path: str | Path = "config.json") -> None:
        self.config_path = Path(config_path)
        self._config: Config | None = None
        self._change_callbacks: list[Callable[[Config], None]] = []

    @property
    def config(self) -> Config:
        if self._config is None:
            self._config = self.load()
        return self._config

    def load(self) -> Config:
        """Load config from JSON file, or return default if not found."""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                self._config = Config.from_dict(data)
                print(f"Loaded config from {self.config_path}")
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error loading config: {e}, using defaults")
                self._config = DEFAULT_CONFIG
        else:
            print(f"No config file found, using defaults")
            self._config = DEFAULT_CONFIG
        return self._config

    def save(self) -> None:
        """Save current config to JSON file."""
        if self._config is None:
            return
        with open(self.config_path, "w") as f:
            json.dump(self._config.to_dict(), f, indent=2)
        print(f"Saved config to {self.config_path}")

    def reload(self) -> Config:
        """Reload config from file."""
        self._config = None
        config = self.load()
        self._notify_change()
        return config

    def update(self, new_config: Config) -> None:
        """Update config and notify listeners."""
        self._config = new_config
        self._notify_change()

    def update_from_dict(self, data: dict) -> None:
        """Update config from dictionary."""
        self._config = Config.from_dict(data)
        self._notify_change()

    def on_change(self, callback: Callable[[Config], None]) -> None:
        """Register a callback for config changes."""
        self._change_callbacks.append(callback)

    def _notify_change(self) -> None:
        """Notify all listeners of config change."""
        if self._config is None:
            return
        for callback in self._change_callbacks:
            try:
                callback(self._config)
            except Exception as e:
                print(f"Error in config change callback: {e}")
