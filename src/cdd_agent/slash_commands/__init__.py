"""Slash command system for CDD Agent.

This module provides slash command functionality for the chat interface,
allowing users to execute CDD commands without leaving the chat session.

Architecture:
- BaseSlashCommand: Abstract base class for all commands
- SlashCommandRouter: Detects, parses, and routes commands
- Command implementations: InitCommand, NewCommand, HelpCommand

Usage:
    from cdd_agent.slash_commands import get_router, setup_commands

    # Initialize router with all commands
    router = get_router()
    setup_commands(router)

    # In chat loop
    if router.is_slash_command(user_message):
        result = await router.execute(user_message)
        print(result)

Available Commands:
    /init [--force]
        Initialize CDD project structure

    /new ticket <type> <name>
        Create a new ticket (feature, bug, spike, enhancement)

    /new documentation <type> <name>
        Create documentation (guide, feature)

    /help [command]
        Display available commands and usage
"""

from .base import BaseSlashCommand, CommandError
from .exec_command import ExecCommand
from .help_command import HelpCommand
from .init_command import InitCommand
from .new_command import NewCommand
from .plan_command import PlanCommand
from .router import SlashCommandRouter, get_router
from .socrates_command import SocratesCommand


def setup_commands(router: SlashCommandRouter, session=None) -> None:
    """Register all available slash commands.

    This function registers all built-in commands with the router.
    Call this once during application initialization.

    Args:
        router: Router instance to register commands with
        session: Optional ChatSession instance (required for agent commands)
    """
    # Register mechanical layer commands
    router.register(InitCommand())
    router.register(NewCommand())

    # Register agent commands (require session)
    socrates_cmd = SocratesCommand()
    if session:
        socrates_cmd.session = session
    router.register(socrates_cmd)

    plan_cmd = PlanCommand()
    if session:
        plan_cmd.session = session
    router.register(plan_cmd)

    exec_cmd = ExecCommand()
    if session:
        exec_cmd.session = session
    router.register(exec_cmd)

    # Register meta commands
    router.register(HelpCommand())


__all__ = [
    # Core classes
    "BaseSlashCommand",
    "SlashCommandRouter",
    "CommandError",
    # Router access
    "get_router",
    "setup_commands",
    # Command implementations
    "InitCommand",
    "NewCommand",
    "HelpCommand",
    "SocratesCommand",
    "PlanCommand",
    "ExecCommand",
]
