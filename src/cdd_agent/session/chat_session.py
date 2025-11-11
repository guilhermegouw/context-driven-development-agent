"""Chat session management with agent switching.

This module provides the ChatSession class that manages conversation state
and enables seamless transitions between general chat and specialized agents.
"""

import logging
from pathlib import Path
from typing import Any, Optional, Type

from ..agents.writer import WriterAgent
from ..slash_commands import get_router, setup_commands
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ChatSession:
    """Manages chat conversation with agent switching.

    Modes:
    - General chat: User talks to LLM with tools (no specialized agent)
    - Agent mode: Specialized agent (Socrates/Planner/Executor) takes over

    Usage:
        session = ChatSession(agent, provider_config, tool_registry)

        # In chat loop
        result, should_exit = await session.process_input(user_input)
        if result:
            console.print(result)
    """

    def __init__(self, agent: Any, provider_config: Any, tool_registry: Any):
        """Initialize chat session.

        Args:
            agent: General-purpose Agent instance (for non-agent mode)
            provider_config: LLM provider configuration
            tool_registry: Available tools
        """
        self.general_agent = agent  # For regular chat (existing Agent class)
        self.provider_config = provider_config
        self.tool_registry = tool_registry

        # Agent management
        self.current_agent: Optional[BaseAgent] = None  # Active CDD agent
        self.slash_router = get_router()

        # Initialize slash commands if needed (pass self for agent commands)
        if not self.slash_router._commands:
            setup_commands(self.slash_router, session=self)

        # Session state
        self.context = None  # Loaded from CDD.md (future enhancement)
        self.current_ticket: Optional[Path] = None  # Track active ticket

    def is_in_agent_mode(self) -> bool:
        """Check if a specialized agent is active.

        Returns:
            True if Socrates/Planner/Executor is active, False if general chat
        """
        return self.current_agent is not None

    def get_current_agent_name(self) -> Optional[str]:
        """Get name of active agent.

        Returns:
            Agent name (e.g., "Socrates") or None if in general chat
        """
        if self.current_agent:
            return self.current_agent.name
        return None

    def switch_to_agent(
        self,
        agent_class: Type[BaseAgent],
        target_path: Path,
    ) -> str:
        """Switch from general chat to specialized agent.

        Args:
            agent_class: Agent class to instantiate (SocratesAgent, etc.)
            target_path: Path to ticket/doc to work on

        Returns:
            Agent's initial greeting message with mode indicator

        Raises:
            RuntimeError: If already in agent mode
        """
        if self.current_agent:
            raise RuntimeError(
                f"Already in {self.current_agent.name} mode. "
                f"Type 'exit' to leave agent mode first."
            )

        # Create agent instance
        self.current_agent = agent_class(
            target_path=target_path,
            session=self,
            provider_config=self.provider_config,
            tool_registry=self.tool_registry,
        )

        # Track current ticket
        self.current_ticket = target_path

        # Get agent's initial message
        greeting = self.current_agent.initialize()

        return (
            f"\n**──── Entering {self.current_agent.name} Mode ────**\n\n"
            f"{greeting}\n\n"
            f"*Type 'exit' to return to general chat.*"
        )

    def exit_agent(self) -> str:
        """Return from agent mode to general chat.

        Returns:
            Agent's completion message with mode indicator

        Raises:
            RuntimeError: If not in agent mode
        """
        if not self.current_agent:
            raise RuntimeError("Not in agent mode")

        # Get agent's final message
        completion = self.current_agent.finalize()
        agent_name = self.current_agent.name

        # Clear agent
        self.current_agent = None
        self.current_ticket = None

        return (
            f"{completion}\n\n"
            f"**──── Exiting {agent_name} Mode ────**\n\n"
            f"Back in general chat. Type `/help` to see available commands."
        )

    async def process_input(self, user_input: str) -> tuple[Optional[str], bool]:
        """Process user input (main entry point).

        Args:
            user_input: User's message

        Returns:
            Tuple of (response_message, should_exit_session)
            - response_message: String to display, or None for general chat
            - should_exit_session: True if session should end (not used yet)

        Flow:
        1. Check for exit command (if in agent mode)
        2. Check for slash command
        3. Route to active agent or general chat
        """
        user_input = user_input.strip()

        # Handle exit command (only in agent mode)
        if user_input.lower() in ["exit", "quit"] and self.current_agent:
            response = self.exit_agent()
            return response, False

        # Check for slash command
        if self.slash_router.is_slash_command(user_input):
            try:
                response = await self.slash_router.execute(user_input)

                # Check if command switched to agent mode
                # (Future: commands like /socrates will call switch_to_agent)

                return response, False

            except Exception as e:
                return f"❌ Error executing command: {e}", False

        # Route to active agent or general chat
        if self.current_agent:
            # Agent mode - send to specialized agent
            try:
                response = await self.current_agent.process(user_input)

                # Check if agent completed automatically
                if self.current_agent.is_done():
                    # Check if agent has content ready to save (Socrates → Writer handoff)
                    if (hasattr(self.current_agent, 'ready_to_save') and
                        self.current_agent.ready_to_save and
                        hasattr(self.current_agent, 'generated_content')):

                        logger.info("Agent ready to save, invoking Writer agent")

                        # Create Writer agent and save content
                        writer = WriterAgent(self.current_agent.target_path)
                        save_result = writer.save(self.current_agent.generated_content)

                        # Append Writer's result to response
                        response = f"{response}\n\n{save_result}"

                    # Exit agent mode
                    completion = self.exit_agent()
                    response = f"{response}\n\n{completion}"

                return response, False

            except Exception as e:
                logger.error(f"Agent error: {e}", exc_info=True)
                return f"❌ Agent error: {e}", False

        else:
            # General chat mode - return None to indicate caller should
            # use the general agent
            return None, False

    def get_status(self) -> dict:
        """Get current session status.

        Returns:
            Status dictionary with mode, agent, ticket info

        Example:
            {
                "mode": "agent",
                "agent_name": "Socrates",
                "current_ticket": "specs/tickets/feature-auth/spec.yaml"
            }
        """
        return {
            "mode": "agent" if self.current_agent else "general",
            "agent_name": self.get_current_agent_name(),
            "current_ticket": (
                str(self.current_ticket) if self.current_ticket else None
            ),
        }
