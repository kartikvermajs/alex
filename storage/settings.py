"""Persistent configuration and settings storage for Alex."""

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from storage.logger import logger

SETTINGS_FILE = Path(__file__).resolve().parent / "settings.json"


@dataclass
class UserSettings:
    # General
    start_with_windows: bool = False
    speak_startup_greeting: bool = False
    startup_greeting_phrase: str = "Alex is ready."
    minimize_to_tray: bool = True
    tts_engine: str = "kokoro"  # "kokoro" or "sapi"
    kokoro_voice: str = "af_bella"  # e.g. af_bella, af_sarah, am_michael
    voice_speed: int = 190
    voice_volume: float = 1.0
    voice_id: Optional[str] = None

    # Microphone
    input_device: Optional[int] = None
    mic_sensitivity: float = 0.015

    # Wake Word
    wake_word_enabled: bool = True
    wake_phrase: str = "hey alex"
    wake_sensitivity: float = 0.5
    acknowledgement_phrase: str = "Yes?"

    # Custom Applications
    custom_apps: List[Dict[str, Any]] = field(default_factory=list)


class SettingsStore:
    """Handles loading and saving of user settings to JSON."""

    def __init__(self, filepath: Path | None = None):
        self.filepath = filepath or SETTINGS_FILE
        self._settings = self._load()

    def _load(self) -> UserSettings:
        if not self.filepath.exists():
            return UserSettings()
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Filter unknown fields for backwards compatibility
            valid_fields = UserSettings.__dataclass_fields__.keys()
            filtered = {k: v for k, v in data.items() if k in valid_fields}
            return UserSettings(**filtered)
        except Exception as e:
            logger.error("Failed to load settings file: %s. Using defaults.", e)
            return UserSettings()

    def get(self) -> UserSettings:
        """Returns the current settings."""
        return self._settings

    def save(self, settings: UserSettings | None = None) -> bool:
        """Persists the settings to disk."""
        if settings is not None:
            self._settings = settings
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(asdict(self._settings), f, indent=2)
            logger.info("Settings saved successfully to %s", self.filepath)
            return True
        except Exception as e:
            logger.error("Failed to save settings: %s", e)
            return False

    def update(self, **kwargs: Any) -> bool:
        """Updates specific settings fields and saves."""
        for k, v in kwargs.items():
            if hasattr(self._settings, k):
                setattr(self._settings, k, v)
        return self.save()


SETTINGS_STORE = SettingsStore()
