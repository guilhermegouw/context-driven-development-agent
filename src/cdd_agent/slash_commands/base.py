"""Base class for slash commands.

This module provides the abstract base class that all slash commands inherit from.
"""

from abc import ABC, abstractmethod


class CommandError(Exception):
    """Raised when command execution fails."""

    pass


class BaseSlashCommand(ABC):
    """Base class for all slash commands.

    All slash commands must inherit from this class and implement the execute() method.
    Optional methods can be overridden for custom validation and formatting.
    """

    def __init__(self):
        """Initialize command with metadata."""
        self.name: str = ""  # Command name (e.g., "init")
        self.description: str = ""  # Short description
        self.usage: str = ""  # Usage pattern (e.g., "[--force]")
        self.examples: list[str] = []  # Example invocations

    @abstractmethod
    async def execute(self, args: str) -> str:
        """Execute the command with given arguments.

        This method must be implemented by all subclasses.

        Args:
            args: Raw argument string (everything after command name)

        Returns:
            Formatted result message to display in chat (markdown supported)

        Raises:
            CommandError: If command execution fails
        """
        pass

    def validate_args(self, args: str) -> bool:
        """Validate command arguments.

        Override this method to provide custom validation logic.
        Default implementation accepts any arguments.

        Args:
            args: Raw argument string

        Returns:
            True if arguments are valid, False otherwise
        """
        return True

    def format_success(self, result: dict) -> str:
        """Format successful result.

        Override this method to provide custom success formatting.
        Default implementation returns a generic message.

        Args:
            result: Result dictionary from command execution

        Returns:
            Formatted success message
        """
        return "✅ Command executed successfully"

    def format_error(self, error: Exception) -> str:
        """Format error message.

        Override this method to provide custom error formatting.
        Default implementation returns the exception message.

        Args:
            error: Exception that occurred during execution

        Returns:
            Formatted error message
        """
        return f"❌ Error: {error}"
