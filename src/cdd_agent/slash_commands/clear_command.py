"""Clear slash command - Reset chat history while preserving system context."""

import logging

from .base import BaseSlashCommand


logger = logging.getLogger(__name__)


class ClearCommand(BaseSlashCommand):
    """Clear the conversation history in the current chat session.

    This command removes only the conversation messages between the user and AI,
    while preserving system context, loaded files, and other session data.

    Usage:
        /clear

    The command:
    1. Clears the conversation history from the chat session
    2. Preserves system context and loaded files
    3. Shows a confirmation message
    """

    def __init__(self):
        """Initialize command metadata."""
        super().__init__()
        self.name = "clear"
        self.description = "Clear chat history while preserving system context"
        self.usage = ""
        self.examples = [
            "/clear",
        ]

    async def execute(self, args: str) -> str:
        """Execute the /clear command.

        Args:
            args: No arguments expected for this command

        Returns:
            Success message confirming chat history was cleared
        """
        logger.info("Executing /clear command")

        # This command doesn't take any arguments
        if args.strip():
            return (
                "**Usage:** `/clear`\n\n"
                "The clear command does not take any arguments. "
                "It clears the conversation history while preserving system context."
            )

        # Check if we have access to session
        if not hasattr(self, "session") or not self.session:
            return "**Error:** No active session. This command requires a chat session."

        # Check if we have access to the agent through the session
        if not hasattr(self.session, "general_agent") or not self.session.general_agent:
            return (
                "**Error:** No agent available. This command requires an active agent."
            )

        try:
            # Clear the conversation history using the session method
            # This preserves system context while clearing only conversation messages
            logger.info("Clearing conversation history from session")
            self.session.clear_history()

            return "✅ **Chat history cleared.**"

        except Exception as e:
            logger.error(f"Error clearing chat history: {e}", exc_info=True)
            return (
                f"**Error clearing chat history:**\n\n"
                f"```\n{str(e)}\n```\n\n"
                f"Please try again or restart the session."
            )
