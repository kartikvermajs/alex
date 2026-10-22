"""Base class for all commands."""

from abc import ABC, abstractmethod
from typing import List
from core.context import CommandContext


class Command(ABC):
    """Abstract base class representing an executable voice command."""

    name: str = "base_command"
    description: str = ""
    examples: List[str] = []
    risk_level: int = 1  # 1: Safe, 2: Potentially disruptive (requires confirmation), 3: Dangerous

    @abstractmethod
    def matches(self, text: str) -> bool:
        """Determines if the user speech matches this command."""
        pass

    @abstractmethod
    def execute(self, context: CommandContext) -> str:
        """Executes the command and returns the verbal response message."""
        pass
