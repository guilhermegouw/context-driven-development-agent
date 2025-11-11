"""Exec slash command - Activate Executor agent for autonomous implementation."""

import logging
from pathlib import Path

from .base import BaseSlashCommand

logger = logging.getLogger(__name__)


class ExecCommand(BaseSlashCommand):
    """Activate Executor agent to implement a plan autonomously.

    Usage:
        /exec <ticket-slug>
        /exec feature-user-auth
        /exec bug-login-error

    The command:
    1. Resolves ticket slug to spec.yaml path
    2. Verifies implementation plan exists
    3. Switches to Executor agent
    4. Agent executes plan step-by-step
    5. Generates code via LLM
    6. Auto-exits when complete
    """

    def __init__(self):
        """Initialize command metadata."""
        super().__init__()
        self.name = "exec"
        self.description = "Execute implementation plan autonomously"
        self.usage = "<ticket-slug>"
        self.examples = [
            "/exec feature-user-auth",
            "/exec bug-login-error",
        ]

    async def execute(self, args: str) -> str:
        """Execute the /exec command.

        Args:
            args: Ticket slug (e.g., "feature-user-auth")

        Returns:
            Error message or None (session handles agent activation)
        """
        logger.info(f"Executing /exec command with args: {args}")

        # Validate arguments
        if not args.strip():
            return (
                "**Usage:** `/exec <ticket-slug>`\n\n"
                "**Examples:**\n"
                "- `/exec feature-user-auth`\n"
                "- `/exec bug-login-error`\n\n"
                "Executes the implementation plan autonomously, generating code "
                "for each step."
            )

        ticket_slug = args.strip()

        # Resolve ticket path
        try:
            spec_path = self._resolve_ticket_spec(ticket_slug)
            logger.info(f"Resolved ticket to: {spec_path}")
        except FileNotFoundError as e:
            logger.warning(f"Ticket not found: {ticket_slug}")
            return (
                f"**Error:** {str(e)}\n\n"
                f"Make sure the ticket exists. Use `/new ticket` to create one."
            )

        # Check if plan exists
        plan_path = spec_path.parent / "plan.md"
        logger.debug(f"Checking for plan at: {plan_path}")

        if not plan_path.exists():
            logger.warning(f"No plan found at {plan_path}")
            return (
                f"**Error:** No implementation plan found.\n\n"
                f"Run `/plan {ticket_slug}` to generate a plan first."
            )

        # Check if we have access to session (for agent switching)
        if not hasattr(self, "session") or not self.session:
            return "**Error:** No active session. This command requires a chat session."

        # Check if already in agent mode
        if self.session.is_in_agent_mode():
            current = self.session.get_current_agent_name()
            return (
                f"**Error:** Already in {current} mode.\n\n"
                f"Type 'exit' to leave {current} before starting Executor."
            )

        # Import here to avoid circular dependency
        from ..agents import ExecutorAgent

        # Switch to Executor agent
        try:
            logger.info("Activating Executor agent")
            greeting = self.session.switch_to_agent(ExecutorAgent, spec_path)
            logger.info("Successfully activated Executor agent")
            return greeting
        except Exception as e:
            logger.error(f"Error activating Executor: {e}", exc_info=True)
            return (
                f"**Error activating Executor:**\n\n"
                f"```\n{str(e)}\n```\n\n"
                f"Please check the ticket and plan, then try again."
            )

    def _resolve_ticket_spec(self, ticket_slug: str) -> Path:
        """Resolve ticket slug to spec.yaml path.

        Args:
            ticket_slug: Ticket slug (e.g., "feature-user-auth")

        Returns:
            Path to spec.yaml file

        Raises:
            FileNotFoundError: If ticket not found
        """
        # CDD structure: specs/tickets/<type>-<slug>/spec.yaml
        # Try common locations
        base_path = Path.cwd()

        # Try specs/tickets/<slug>/spec.yaml (most common)
        ticket_dir = base_path / "specs" / "tickets" / ticket_slug
        if ticket_dir.exists() and ticket_dir.is_dir():
            spec_path = ticket_dir / "spec.yaml"
            if spec_path.exists():
                return spec_path

        # Try direct path if user provided full path
        if ticket_slug.endswith(".yaml"):
            direct_path = base_path / ticket_slug
            if direct_path.exists():
                return direct_path

        # Search in specs/tickets directory
        tickets_dir = base_path / "specs" / "tickets"
        if tickets_dir.exists():
            # List all ticket directories
            ticket_dirs = [d for d in tickets_dir.iterdir() if d.is_dir()]

            # Find matching ticket (case-insensitive partial match)
            matches = [d for d in ticket_dirs if ticket_slug.lower() in d.name.lower()]

            if len(matches) == 1:
                spec_path = matches[0] / "spec.yaml"
                if spec_path.exists():
                    return spec_path
            elif len(matches) > 1:
                match_names = ", ".join(d.name for d in matches)
                raise FileNotFoundError(
                    f"Multiple tickets match '{ticket_slug}': {match_names}\n"
                    f"Please be more specific."
                )

        # Not found
        search_location = (
            str(tickets_dir) if tickets_dir.exists() else "specs/tickets (not found)"
        )
        raise FileNotFoundError(
            f"Ticket not found: {ticket_slug}\n\n" f"Searched in: {search_location}"
        )
