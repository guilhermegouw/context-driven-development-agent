"""Test agent for integration testing.

This agent is used to validate the session management system
without needing to implement the full Socrates/Planner/Executor agents.
"""

from pathlib import Path

from ..session.base_agent import BaseAgent


class TestAgent(BaseAgent):
    """Simple test agent for validating session integration.

    Behavior:
    - Greets user on initialization
    - Echoes user messages with a counter
    - Auto-exits after 3 messages
    - Can be manually exited with 'exit' command
    """

    def __init__(
        self,
        target_path: Path,
        session,
        provider_config,
        tool_registry,
    ):
        """Initialize test agent."""
        super().__init__(target_path, session, provider_config, tool_registry)
        self.name = "TestAgent"
        self.description = "Simple test agent for session validation"
        self.message_count = 0

    def initialize(self) -> str:
        """Return greeting message.

        Returns:
            Initial greeting with instructions
        """
        return (
            f"Hello! I'm **{self.name}**.\n\n"
            f"I'm working on: `{self.target_path}`\n\n"
            f"**Instructions:**\n"
            f"- Send me 3 messages, then I'll automatically exit\n"
            f"- Or type 'exit' to leave early\n\n"
            f"Let's test the session management!"
        )

    async def process(self, user_input: str) -> str:
        """Process user message and track count.

        Args:
            user_input: User's message

        Returns:
            Echo response with message counter
        """
        self.message_count += 1
        self.conversation_history.append(user_input)

        response = f"**[Message {self.message_count}/3]** You said: *{user_input}*"

        # Auto-complete after 3 messages
        if self.message_count >= 3:
            self.mark_complete()
            response += (
                "\n\n✅ **Mission accomplished!** "
                "I've received 3 messages. Exiting..."
            )

        return response

    def finalize(self) -> str:
        """Return completion summary.

        Returns:
            Summary of test session
        """
        return (
            f"✅ **{self.name} completed**\n\n"
            f"- Processed {self.message_count} message(s)\n"
            f"- Target file: `{self.target_path}`\n"
            f"- Conversation history: {len(self.conversation_history)} entries"
        )
