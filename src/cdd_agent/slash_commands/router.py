"""Slash command router.

This module provides command detection, parsing, and routing functionality.
"""

import logging
from typing import Optional

from rich.console import Console

from .base import BaseSlashCommand, CommandError

console = Console()
logger = logging.getLogger(__name__)


class SlashCommandRouter:
    """Routes slash commands to appropriate handlers.

    The router maintains a registry of commands and handles:
    - Command detection (is message a slash command?)
    - Command parsing (extract command name and arguments)
    - Command routing (find and execute handler)
    - Error handling (unknown commands, invalid arguments)
    """

    def __init__(self):
        """Initialize router with empty command registry."""
        self._commands: dict[str, BaseSlashCommand] = {}

    def register(self, command: BaseSlashCommand) -> None:
        """Register a slash command handler.

        Args:
            command: Command instance to register
        """
        self._commands[command.name] = command

    def is_slash_command(self, message: str) -> bool:
        """Check if message starts with a slash command.

        Args:
            message: User input message

        Returns:
            True if message is a slash command (starts with /)
        """
        return message.strip().startswith("/")

    def parse_command(self, message: str) -> tuple[str, str]:
        """Parse slash command into name and arguments.

        Args:
            message: User input (e.g., "/init --force")

        Returns:
            Tuple of (command_name, args_string)

        Examples:
            "/init" -> ("init", "")
            "/init --force" -> ("init", "--force")
            "/new ticket feature Auth" -> ("new", "ticket feature Auth")

        Raises:
            CommandError: If message is not a slash command
        """
        message = message.strip()

        if not message.startswith("/"):
            raise CommandError("Not a slash command")

        # Remove leading slash
        message = message[1:]

        # Split on first whitespace
        parts = message.split(maxsplit=1)

        command_name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        return command_name, args

    async def execute(self, message: str) -> str:
        """Execute a slash command.

        Args:
            message: Full user message (e.g., "/init --force")

        Returns:
            Formatted result string (markdown supported)

        Raises:
            CommandError: If command not found or execution fails
        """
        logger.info(f"Executing slash command: {message}")
        try:
            command_name, args = self.parse_command(message)
            logger.debug(f"Parsed command: name={command_name}, args={args}")

            if command_name not in self._commands:
                logger.warning(f"Unknown command: {command_name}")
                return self._format_unknown_command(command_name)

            command = self._commands[command_name]
            logger.debug(f"Found command handler: {command.__class__.__name__}")

            # Validate arguments
            if not command.validate_args(args):
                logger.warning(f"Invalid args for /{command_name}: {args}")
                return self._format_invalid_args(command)

            # Execute command
            logger.info(f"Executing /{command_name} with args: {args}")
            result = await command.execute(args)
            logger.info(f"Command /{command_name} completed successfully")
            return result

        except CommandError as e:
            logger.error(f"Command error: {e}")
            return f"❌ Command error: {e}"
        except Exception as e:
            logger.error(f"Unexpected error executing command: {e}", exc_info=True)
            console.print_exception()
            return f"❌ Unexpected error: {e}"

    def _format_unknown_command(self, command_name: str) -> str:
        """Format error message for unknown command.

        Args:
            command_name: Name of unknown command

        Returns:
            Formatted error message
        """
        available = ", ".join(f"/{name}" for name in sorted(self._commands.keys()))
        return (
            f"❌ Unknown command: /{command_name}\n\n"
            f"Available commands: {available}\n"
            f"Type /help for more information"
        )

    def _format_invalid_args(self, command: BaseSlashCommand) -> str:
        """Format error message for invalid arguments.

        Args:
            command: Command that received invalid arguments

        Returns:
            Formatted error message
        """
        lines = [
            "❌ Invalid arguments\n",
            f"**Usage:** `/{command.name} {command.usage}`\n",
            "**Examples:**",
        ]

        for example in command.examples:
            lines.append(f"  `{example}`")

        return "\n".join(lines)

    def get_all_commands(self) -> list[BaseSlashCommand]:
        """Get list of all registered commands.

        Returns:
            List of command instances, sorted by name
        """
        return [self._commands[name] for name in sorted(self._commands.keys())]


# Global router instance
_router: Optional[SlashCommandRouter] = None


def get_router() -> SlashCommandRouter:
    """Get the global slash command router instance.

    Creates the router on first call (singleton pattern).

    Returns:
        Global router instance
    """
    global _router
    if _router is None:
        _router = SlashCommandRouter()
    return _router
