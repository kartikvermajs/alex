"""Command registry and lookup system."""

from typing import List, Optional
from commands.base import Command
from commands.date_time import DateCommand, TimeCommand
from commands.applications import (
    OpenApplicationCommand,
    CloseApplicationCommand,
    RestartApplicationCommand,
)
from commands.system import RestartComputerCommand, ShutdownComputerCommand
from commands.web_search import WebSearchCommand


class CommandRegistry:
    """Maintains registered commands and resolves text to matched commands."""

    def __init__(self):
        self._commands: List[Command] = []

    def register(self, command: Command) -> None:
        """Registers a command handler."""
        self._commands.append(command)

    def get_all(self) -> List[Command]:
        """Returns all registered commands."""
        return list(self._commands)

    def find_command(self, text: str) -> Optional[Command]:
        """Finds the first command whose matching criteria is met."""
        for cmd in self._commands:
            if cmd.matches(text):
                return cmd
        return None


def create_default_registry() -> CommandRegistry:
    """Builds the default registry with all available commands."""
    registry = CommandRegistry()
    # Date and Time
    registry.register(DateCommand())
    registry.register(TimeCommand())

    # System commands (Must be evaluated before application commands to capture PC restart/shutdown)
    registry.register(RestartComputerCommand())
    registry.register(ShutdownComputerCommand())

    # Application commands (Restart placed before Open/Close to avoid prefix collision)
    registry.register(RestartApplicationCommand())
    registry.register(CloseApplicationCommand())
    registry.register(OpenApplicationCommand())

    # Web search command (Evaluated after local app/system controls)
    registry.register(WebSearchCommand())

    return registry


COMMAND_REGISTRY = create_default_registry()
