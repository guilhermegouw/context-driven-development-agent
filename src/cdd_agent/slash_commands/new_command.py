"""Create new tickets or documentation command.

Handler for the /new slash command.
"""

from ..mechanical.new_ticket import (
    TicketCreationError,
    create_new_documentation,
    create_new_ticket,
)
from .base import BaseSlashCommand, CommandError


class NewCommand(BaseSlashCommand):
    """Create new tickets or documentation.

    Ticket types:
    - feature: New functionality or capabilities
    - bug: Defects, errors, or incorrect behavior
    - spike: Research, exploration, or proof-of-concept
    - enhancement: Improvements to existing features

    Documentation types:
    - guide: How-to guides, tutorials, getting started
    - feature: Feature specifications, technical details

    Usage:
        /new ticket <type> <name>
        /new documentation <type> <name>
    """

    def __init__(self):
        """Initialize command metadata."""
        super().__init__()
        self.name = "new"
        self.description = "Create new ticket or documentation"
        self.usage = "<ticket|documentation> <type> <name>"
        self.examples = [
            "/new ticket feature User Authentication",
            "/new ticket bug Login Error",
            "/new ticket spike Database Options",
            "/new ticket enhancement Performance Improvements",
            "/new documentation guide Getting Started",
            "/new documentation feature User Authentication",
        ]

        # Valid types
        self.ticket_types = ["feature", "bug", "spike", "enhancement"]
        self.doc_types = ["guide", "feature"]

    def validate_args(self, args: str) -> bool:
        """Validate command arguments.

        Format: <category> <type> <name>
        - category: "ticket" or "documentation"
        - type: depends on category
        - name: any string (will be normalized)

        Args:
            args: Command arguments

        Returns:
            True if valid format and types
        """
        parts = args.split(maxsplit=2)

        if len(parts) < 3:
            return False

        category = parts[0]
        item_type = parts[1]

        if category == "ticket":
            return item_type in self.ticket_types
        elif category == "documentation":
            return item_type in self.doc_types
        else:
            return False

    async def execute(self, args: str) -> str:
        """Execute ticket/documentation creation.

        Args:
            args: "ticket <type> <name>" or "documentation <type> <name>"

        Returns:
            Formatted success message

        Raises:
            CommandError: If creation fails
        """
        parts = args.split(maxsplit=2)

        if len(parts) < 3:
            return self._format_usage_error()

        category = parts[0]
        item_type = parts[1]
        name = parts[2]

        try:
            if category == "ticket":
                result = create_new_ticket(item_type, name)
                return self._format_ticket_success(result)

            elif category == "documentation":
                result = create_new_documentation(item_type, name)
                return self._format_doc_success(result)

            else:
                return self._format_usage_error()

        except TicketCreationError as e:
            raise CommandError(str(e))

    def _format_ticket_success(self, result: dict) -> str:
        """Format ticket creation success message.

        Args:
            result: Result from create_new_ticket()

        Returns:
            Markdown-formatted message
        """
        ticket_path = result["ticket_path"]
        normalized_name = result["normalized_name"]
        ticket_type = result["ticket_type"]
        overwritten = result["overwritten"]

        action = "Overwritten" if overwritten else "Created"

        lines = [
            f"# ✅ {action} {ticket_type.title()} Ticket\n",
            f"**Name:** `{normalized_name}`",
            f"**Path:** `{ticket_path}`",
            f"**Spec:** `{ticket_path}/spec.yaml`\n",
            "**Next steps:**",
            "  1. Edit `spec.yaml` to define the ticket",
            "  2. Use Socrates to refine requirements (coming soon)",
            "  3. Use Planner to generate implementation plan (coming soon)",
            "  4. Use Executor to execute the plan (coming soon)",
        ]

        return "\n".join(lines)

    def _format_doc_success(self, result: dict) -> str:
        """Format documentation creation success message.

        Args:
            result: Result from create_new_documentation()

        Returns:
            Markdown-formatted message
        """
        file_path = result["file_path"]
        normalized_name = result["normalized_name"]
        doc_type = result["doc_type"]
        overwritten = result["overwritten"]

        action = "Overwritten" if overwritten else "Created"

        lines = [
            f"# ✅ {action} {doc_type.title()} Documentation\n",
            f"**Name:** `{normalized_name}`",
            f"**Path:** `{file_path}`\n",
            "**Next steps:**",
            "  1. Edit the markdown file to document your work",
            "  2. Reference this documentation in CDD.md if needed",
            "  3. Use this documentation as context for AI assistance",
        ]

        return "\n".join(lines)

    def _format_usage_error(self) -> str:
        """Format usage error message.

        Returns:
            Markdown-formatted error message
        """
        lines = [
            "# ❌ Invalid Usage\n",
            "**Ticket creation:**",
            "  `/new ticket <type> <name>`",
            f"  Valid types: {', '.join(self.ticket_types)}\n",
            "**Documentation creation:**",
            "  `/new documentation <type> <name>`",
            f"  Valid types: {', '.join(self.doc_types)}\n",
            "**Examples:**",
        ] + [f"  {ex}" for ex in self.examples]

        return "\n".join(lines)
