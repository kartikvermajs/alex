"""Unit tests for CommandRouter and safety enforcement."""

import pytest
from commands.base import Command
from commands.registry import CommandRegistry
from core.command_router import CommandRouter
from core.context import CommandContext


class DummyDangerousCommand(Command):
    name = "dangerous_action"
    description = "Dangerous operation"
    examples = ["format drive"]
    risk_level = 3  # Level 3: Dangerous

    def matches(self, text: str) -> bool:
        return "format drive" in text.lower()

    def execute(self, context: CommandContext) -> str:
        return "Drive formatted."


def test_command_router_empty_input():
    router = CommandRouter()
    assert router.route("") == "I didn't hear a command."
    assert router.route("   ") == "I didn't hear a command."


def test_command_router_unknown_command():
    router = CommandRouter()
    assert router.route("perform an unknown unknown task xyz") == "I didn't understand that."


def test_command_router_date_routing():
    router = CommandRouter()
    response = router.route("What is the date today?")
    assert response.startswith("Today is ")


def test_command_router_time_routing():
    router = CommandRouter()
    response = router.route("What time is it?")
    assert response.startswith("It's ")


def test_command_router_blocks_dangerous_level_3():
    registry = CommandRegistry()
    registry.register(DummyDangerousCommand())
    router = CommandRouter(registry)

    response = router.route("format drive")
    assert response == "I don't have permission to perform that action."
