"""Command routing and safety validation."""

from typing import Optional, Tuple
from commands.base import Command
from commands.registry import CommandRegistry, COMMAND_REGISTRY
from core.context import CommandContext
from storage.logger import logger


class CommandRouter:
    """Routes transcribed text to the appropriate command handler with safety checks."""

    def __init__(self, registry: CommandRegistry | None = None):
        self.registry = registry or COMMAND_REGISTRY
        self.pending_confirmation: Optional[Tuple[Command, CommandContext]] = None

    def route(self, text: str) -> str:
        """
        Processes transcribed user text, identifies intent, enforces safety,
        and returns verbal response string.
        """
        cleaned = text.strip()
        if not cleaned:
            logger.info("Empty speech input received.")
            return "I didn't hear a command."

        logger.info("Routing command: \"%s\"", cleaned)
        lower_cleaned = cleaned.lower()

        # Check for confirmation responses
        if self.pending_confirmation is not None:
            cmd, ctx = self.pending_confirmation
            if lower_cleaned in ["yes", "yeah", "yep", "sure", "please do", "confirm", "do it"]:
                self.pending_confirmation = None
                ctx.confirmed = True
                logger.info("Confirmed Level 2 command execution: %s", cmd.name)
                return cmd.execute(ctx)
            elif lower_cleaned in ["no", "nope", "cancel", "dont", "do not", "nevermind", "stop"]:
                self.pending_confirmation = None
                logger.info("Canceled Level 2 command execution: %s", cmd.name)
                return "Action canceled."

        command = self.registry.find_command(cleaned)

        if not command:
            logger.info("No matching command handler found for: \"%s\"", cleaned)
            return "I didn't understand that."

        logger.info("Matched command handler: %s (Risk Level %d)", command.name, command.risk_level)

        # Enforce safety rules
        if command.risk_level >= 3:
            logger.warning("Blocked dangerous command: %s", command.name)
            return "I don't have permission to perform that action."

        context = CommandContext(
            raw_text=text,
            cleaned_text=cleaned,
        )

        # Handle Level 2: Potentially disruptive commands requiring confirmation
        if command.risk_level == 2:
            self.pending_confirmation = (command, context)
            prompt = command.execute(context)
            logger.info("Prompting for confirmation: %s", prompt)
            return prompt

        # Level 1: Safe commands execute directly
        self.pending_confirmation = None
        try:
            response = command.execute(context)
            logger.info("Command %s response: \"%s\"", command.name, response)
            return response
        except Exception as e:
            logger.error("Error executing command %s: %s", command.name, e)
            return "An error occurred while executing that command."
