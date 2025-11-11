"""Socrates slash command - Activate Socrates agent for ticket refinement."""

import logging
from pathlib import Path

from .base import BaseSlashCommand

logger = logging.getLogger(__name__)


class SocratesCommand(BaseSlashCommand):
    """Activate Socrates agent to refine a ticket specification or CDD.md file.

    Usage:
        /socrates <ticket-slug>
        /socrates feature-user-auth
        /socrates bug-login-error
        /socrates CDD.md
        /socrates docs/my-document.md

    The command:
    1. Resolves ticket slug to spec.yaml path or finds CDD.md files
    2. Switches to Socrates agent
    3. Agent analyzes content and asks clarifying questions
    4. Auto-exits when the document is sufficiently detailed
    """

    def __init__(self):
        """Initialize command metadata."""
        super().__init__()
        self.name = "socrates"
        self.description = "Refine ticket specification through Socratic dialogue"
        self.usage = "<ticket-slug>"
        self.examples = [
            "/socrates feature-user-auth",
            "/socrates bug-login-error",
            "/socrates CDD.md",
            "/socrates docs/guide.md",
        ]

    async def execute(self, args: str) -> str:
        """Execute the /socrates command.

        Args:
            args: Ticket slug or file path (e.g., "feature-user-auth", "CDD.md")

        Returns:
            Error message or None (session handles agent activation)
        """
        logger.info(f"Executing /socrates command with args: {args}")

        # Validate arguments
        if not args.strip():
            return (
                "**Usage:** `/socrates <ticket-slug-or-file>`\n\n"
                "**Examples:**\n"
                "- `/socrates feature-user-auth` (ticket specification)\n"
                "- `/socrates CDD.md` (project documentation)\n"
                "- `/socrates docs/guide.md` (any markdown file)\n\n"
                "Activates Socrates agent to refine the document "
                "through dialogue."
            )

        ticket_slug = args.strip()

        # Resolve path (ticket spec or markdown file)
        try:
            spec_path = self._resolve_document_path(ticket_slug)
            logger.info(f"Resolved document to: {spec_path}")
        except FileNotFoundError as e:
            logger.warning(f"Document not found: {ticket_slug}")
            return (
                f"**Error:** {str(e)}\n\n"
                f"Make sure the ticket or file exists. Use `/new ticket` to create one."
            )

        # Check if we have access to session (for agent switching)
        if not hasattr(self, "session") or not self.session:
            return (
                "**Error:** No active session. " "This command requires a chat session."
            )

        # Check if already in agent mode
        if self.session.is_in_agent_mode():
            current = self.session.get_current_agent_name()
            return (
                f"**Error:** Already in {current} mode.\n\n"
                f"Type 'exit' to leave {current} before starting Socrates."
            )

        # Import here to avoid circular dependency
        from ..agents import SocratesAgent

        # Switch to Socrates agent
        try:
            logger.info("Activating Socrates agent")
            greeting = self.session.switch_to_agent(SocratesAgent, spec_path)
            logger.info("Successfully activated Socrates agent")
            return greeting
        except Exception as e:
            logger.error(f"Error activating Socrates: {e}", exc_info=True)
            return (
                f"**Error activating Socrates:**\n\n"
                f"```\n{str(e)}\n```\n\n"
                f"Please check the ticket spec and try again."
            )

    def _resolve_document_path(self, document_slug: str) -> Path:
        """Resolve ticket slug or file path to document path.

        Args:
            document_slug: Ticket slug (e.g., "feature-user-auth") or file path (e.g., "CDD.md")

        Returns:
            Path to document file (spec.yaml or .md file)

        Raises:
            FileNotFoundError: If document not found
        """
        # CDD structure: specs/tickets/<type>-<slug>/spec.yaml
        # Try common locations
        base_path = Path.cwd()

        # If it looks like a markdown file, handle it directly
        if document_slug.lower().endswith('.md') or 'CDD.md' in document_slug:
            # Try direct path first
            direct_path = base_path / document_slug
            if direct_path.exists() and direct_path.suffix == '.md':
                return direct_path
            
            # Try with .md extension if not provided
            if not document_slug.lower().endswith('.md'):
                md_path = base_path / f"{document_slug}.md"
                if md_path.exists():
                    return md_path
        
        # Try specs/tickets/<slug>/spec.yaml (most common for tickets)
        ticket_dir = base_path / "specs" / "tickets" / document_slug
        if ticket_dir.exists() and ticket_dir.is_dir():
            spec_path = ticket_dir / "spec.yaml"
            if spec_path.exists():
                return spec_path

        # Try direct path if user provided full path
        if document_slug.endswith(".yaml"):
            direct_path = base_path / document_slug
            if direct_path.exists():
                return direct_path

        # Search in specs/tickets directory for tickets
        tickets_dir = base_path / "specs" / "tickets"
        if tickets_dir.exists():
            # List all ticket directories
            ticket_dirs = [d for d in tickets_dir.iterdir() if d.is_dir()]

            # Find matching ticket (case-insensitive partial match)
            matches = [d for d in ticket_dirs if document_slug.lower() in d.name.lower()]

            if len(matches) == 1:
                spec_path = matches[0] / "spec.yaml"
                if spec_path.exists():
                    return spec_path
            elif len(matches) > 1:
                match_names = ", ".join(d.name for d in matches)
                raise FileNotFoundError(
                    f"Multiple tickets match '{document_slug}': {match_names}\n"
                    f"Please be more specific."
                )

        # Search for markdown files in the project
        if not document_slug.lower().endswith('.md'):
            # Look for any markdown files that might match
            for md_file in base_path.rglob("*.md"):
                if document_slug.lower() in md_file.name.lower():
                    return md_file

        # Not found
        search_locations = []
        if tickets_dir.exists():
            search_locations.append(str(tickets_dir))
        search_locations.append("project directory for .md files")
        
        raise FileNotFoundError(
            f"Document not found: {document_slug}\n\n" 
            f"Searched in: {', '.join(search_locations)}"
        )
