"""Base class for specialized CDD agents.

This module provides the abstract base class that all CDD agents
(Socrates, Planner, Executor) inherit from.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .chat_session import ChatSession


class AgentError(Exception):
    """Raised when agent operations fail."""

    pass


class BaseAgent(ABC):
    """Base class for all CDD agents (Socrates, Planner, Executor).

    Lifecycle:
    1. __init__() - Create agent instance
    2. initialize() - Called when agent activates (returns greeting)
    3. process() - Called for each user message while agent is active
    4. is_done() - Check if agent has completed its task
    5. finalize() - Called when agent deactivates (returns summary)

    Example:
        class MyAgent(BaseAgent):
            def initialize(self) -> str:
                return "Hello! I'm MyAgent."

            async def process(self, user_input: str) -> str:
                # Process user message
                return "Response"

            def finalize(self) -> str:
                return "✅ Completed"
    """

    def __init__(
        self,
        target_path: Path,
        session: "ChatSession",
        provider_config: Any,
        tool_registry: Any,
    ):
        """Initialize agent.

        Args:
            target_path: Path to ticket/doc being worked on
            session: Parent ChatSession instance
            provider_config: LLM provider configuration
            tool_registry: Available tools for agent
        """
        self.target_path = target_path
        self.session = session
        self.provider_config = provider_config
        self.tool_registry = tool_registry

        # Agent state
        self.conversation_history = []
        self._is_complete = False

        # Agent metadata (set by subclasses)
        self.name: str = ""  # e.g., "Socrates", "Planner"
        self.description: str = ""  # e.g., "Refine ticket requirements"
        self.prompt_template: str = ""  # System prompt for agent

    @abstractmethod
    def initialize(self) -> str:
        """Called when agent is activated.

        Returns:
            Initial greeting message to display

        Example:
            "Hello! I'm Socrates. Let's refine your ticket requirements."
        """
        pass

    @abstractmethod
    async def process(self, user_input: str) -> str:
        """Process user message while agent is active.

        Args:
            user_input: User's message

        Returns:
            Agent's response
        """
        pass

    def is_done(self) -> bool:
        """Check if agent has completed its task.

        Returns:
            True if agent should exit automatically
        """
        return self._is_complete

    def finalize(self) -> str:
        """Called when agent is deactivated.

        Returns:
            Completion summary message

        Example:
            "✅ Specification updated: specs/tickets/feature-auth/spec.yaml"
        """
        return f"✅ {self.name} completed"

    def mark_complete(self):
        """Mark agent as complete (will exit automatically)."""
        self._is_complete = True

    def load_target(self) -> dict:
        """Load target file (ticket spec, doc, etc.).

        Returns:
            Parsed content (YAML or markdown)

        Raises:
            AgentError: If target file not found or invalid
        """
        if not self.target_path.exists():
            raise AgentError(f"Target not found: {self.target_path}")

        # For now, just read as text
        # Future: Parse YAML for tickets, markdown for docs
        return {"content": self.target_path.read_text()}

    def save_target(self, content: str):
        """Save changes to target file.

        Args:
            content: Updated content to write
        """
        self.target_path.write_text(content)
