"""Application control commands: Open, Close, Restart."""

import re
from typing import Optional
from commands.base import Command
from core.context import CommandContext
from storage.logger import logger
from system.application_manager import ApplicationManager, GLOBAL_APP_MANAGER

SYSTEM_EXCLUDED_KEYWORDS = {"pc", "computer", "my pc", "my computer", "windows", "system", "laptop"}


def clean_app_command_text(text: str) -> str:
    """Removes punctuation and normalizes extra spaces."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(cleaned.split())


class OpenApplicationCommand(Command):
    """Opens a desktop application."""

    name = "open_application"
    description = "Opens a desktop application by name."
    examples = [
        "open spotify",
        "launch spotify",
        "start spotify",
        "open the spotify app",
        "can you open spotify",
        "please open chrome",
    ]
    risk_level = 1

    def __init__(self, app_manager: ApplicationManager | None = None):
        self.app_manager = app_manager or GLOBAL_APP_MANAGER

    _PATTERNS = [
        r"^(?:can you\s+)?(?:please\s+)?(?:open|launch|start)\s+(?:the\s+)?(.+?)(?:\s+app|\s+application)?$",
    ]

    def _extract_app_name(self, text: str) -> Optional[str]:
        cleaned = clean_app_command_text(text)
        if "date" in cleaned or "time" in cleaned:
            return None
        for pattern in self._PATTERNS:
            match = re.match(pattern, cleaned)
            if match:
                app_target = match.group(1).strip()
                app_target = re.sub(r"\b(?:for me|please)\b", "", app_target).strip()
                if app_target in SYSTEM_EXCLUDED_KEYWORDS:
                    return None
                return app_target
        return None

    def matches(self, text: str) -> bool:
        return self._extract_app_name(text) is not None

    def execute(self, context: CommandContext) -> str:
        app_name = self._extract_app_name(context.raw_text)
        if not app_name:
            return "Which application would you like me to open?"

        success, message = self.app_manager.open_app(app_name)
        return message


class CloseApplicationCommand(Command):
    """Closes or terminates a running desktop application."""

    name = "close_application"
    description = "Closes a running desktop application by name."
    examples = [
        "close spotify",
        "quit spotify",
        "exit spotify",
        "stop spotify",
        "close the spotify app",
        "can you close spotify",
        "please close chrome",
    ]
    risk_level = 1

    def __init__(self, app_manager: ApplicationManager | None = None):
        self.app_manager = app_manager or GLOBAL_APP_MANAGER

    _PATTERNS = [
        r"^(?:can you\s+)?(?:please\s+)?(?:close|quit|exit|stop|terminate|kill)\s+(?:the\s+)?(.+?)(?:\s+app|\s+application)?$",
    ]

    def _extract_app_name(self, text: str) -> Optional[str]:
        cleaned = clean_app_command_text(text)
        if "close" in cleaned and "open" in cleaned:
            return None
        for pattern in self._PATTERNS:
            match = re.match(pattern, cleaned)
            if match:
                app_target = match.group(1).strip()
                app_target = re.sub(r"\b(?:for me|please)\b", "", app_target).strip()
                if app_target in SYSTEM_EXCLUDED_KEYWORDS:
                    return None
                return app_target
        return None

    def matches(self, text: str) -> bool:
        return self._extract_app_name(text) is not None

    def execute(self, context: CommandContext) -> str:
        app_name = self._extract_app_name(context.raw_text)
        if not app_name:
            return "Which application would you like me to close?"

        success, message = self.app_manager.close_app(app_name)
        return message


class RestartApplicationCommand(Command):
    """Restarts a desktop application with full verification."""

    name = "restart_application"
    description = "Restarts a desktop application."
    examples = [
        "restart spotify",
        "restart the spotify app",
        "can you restart spotify",
        "please restart spotify",
        "close spotify and open it again",
        "relaunch spotify",
    ]
    risk_level = 1

    def __init__(self, app_manager: ApplicationManager | None = None):
        self.app_manager = app_manager or GLOBAL_APP_MANAGER

    _PATTERNS = [
        r"^(?:can you\s+)?(?:please\s+)?(?:restart|relaunch|reboot)\s+(?:the\s+)?(.+?)(?:\s+app|\s+application)?$",
        r"^(?:can you\s+)?(?:please\s+)?close\s+(?:the\s+)?(.+?)(?:\s+app|\s+application)?\s+and\s+(?:open|start|launch)\s+it\s+again$",
    ]

    def _extract_app_name(self, text: str) -> Optional[str]:
        cleaned = clean_app_command_text(text)
        for pattern in self._PATTERNS:
            match = re.match(pattern, cleaned)
            if match:
                app_target = match.group(1).strip()
                app_target = re.sub(r"\b(?:for me|please)\b", "", app_target).strip()
                if app_target in SYSTEM_EXCLUDED_KEYWORDS:
                    return None
                return app_target
        return None

    def matches(self, text: str) -> bool:
        return self._extract_app_name(text) is not None

    def execute(self, context: CommandContext) -> str:
        app_name = self._extract_app_name(context.raw_text)
        if not app_name:
            return "Which application would you like me to restart?"

        success, message = self.app_manager.restart_app(app_name)
        return message
