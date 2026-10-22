"""System-level commands with risk validation and confirmation management."""

import re
from commands.base import Command
from core.context import CommandContext


class RestartComputerCommand(Command):
    """Restarts the host computer (Level 2: Potentially disruptive)."""

    name = "restart_computer"
    description = "Restarts the Windows PC."
    examples = [
        "restart computer",
        "restart my computer",
        "restart the computer",
        "restart my pc",
        "restart pc",
    ]
    risk_level = 2  # Requires confirmation

    _PATTERNS = [
        r"\brestart\s+(?:the\s+|my\s+)?(?:computer|pc|system|windows)\b",
        r"\breboot\s+(?:the\s+|my\s+)?(?:computer|pc|system|windows)\b",
    ]

    def matches(self, text: str) -> bool:
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        for pattern in self._PATTERNS:
            if re.search(pattern, cleaned):
                return True
        return False

    def execute(self, context: CommandContext) -> str:
        if not context.confirmed:
            return "Do you want me to restart the computer?"
        return "Restarting the computer."


class ShutdownComputerCommand(Command):
    """Shuts down the host computer (Level 2: Potentially disruptive)."""

    name = "shutdown_computer"
    description = "Shuts down the Windows PC."
    examples = [
        "shut down computer",
        "shutdown my computer",
        "turn off the computer",
        "turn off my pc",
    ]
    risk_level = 2  # Requires confirmation

    _PATTERNS = [
        r"\b(?:shut\s*down|turn\s+off|power\s+off)\s+(?:the\s+|my\s+)?(?:computer|pc|system)\b",
    ]

    def matches(self, text: str) -> bool:
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        for pattern in self._PATTERNS:
            if re.search(pattern, cleaned):
                return True
        return False

    def execute(self, context: CommandContext) -> str:
        if not context.confirmed:
            return "Do you want me to shut down the computer?"
        return "Shutting down the computer."
