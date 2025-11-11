"""Session management for CDD Agent.

This module provides conversation state management and agent switching:
- ChatSession: Manages conversation and agent transitions
- BaseAgent: Abstract base for specialized agents (Socrates, Planner, Executor)

Usage:
    from cdd_agent.session import ChatSession, BaseAgent

    # Create session
    session = ChatSession(agent, provider_config, tool_registry)

    # In chat loop
    response, should_exit = await session.process_input(user_input)
    if response:
        console.print(response)

    # Check agent mode
    if session.is_in_agent_mode():
        agent_name = session.get_current_agent_name()
        print(f"Currently in {agent_name} mode")
"""

from .base_agent import AgentError, BaseAgent
from .chat_session import ChatSession

__all__ = [
    "ChatSession",
    "BaseAgent",
    "AgentError",
]
