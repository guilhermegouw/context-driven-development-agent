"""Initialize CDD project structure command.

Handler for the /init slash command.
"""

from ..mechanical.init import InitializationError, initialize_project
from .base import BaseSlashCommand, CommandError


class InitCommand(BaseSlashCommand):
    """Initialize CDD project structure.

    Creates:
    - CDD.md (project constitution)
    - specs/tickets/ directory
    - docs/features/ and docs/guides/ directories
    - .cdd/templates/ with all templates
    - .cdd/config.yaml

    Usage:
        /init           # Initialize in current directory
        /init --force   # Force re-initialization
    """

    def __init__(self):
        """Initialize command metadata."""
        super().__init__()
        self.name = "init"
        self.description = "Initialize CDD project structure"
        self.usage = "[--force]"
        self.examples = [
            "/init",
            "/init --force",
        ]

    def validate_args(self, args: str) -> bool:
        """Validate arguments (only --force allowed).

        Args:
            args: Command arguments

        Returns:
            True if valid (empty or "--force")
        """
        if not args:
            return True
        return args.strip() == "--force"

    async def execute(self, args: str) -> str:
        """Execute project initialization.

        Args:
            args: Command arguments (empty or "--force")

        Returns:
            Formatted success message

        Raises:
            CommandError: If initialization fails
        """
        import logging

        logger = logging.getLogger("cdd_agent.slash_commands.init")
        logger.info(f"InitCommand.execute called with args: '{args}'")

        # Always use force=True in TUI mode to avoid interactive prompts
        force = True
        logger.debug(f"Force flag: {force} (always True in TUI)")

        try:
            # Execute initialization
            logger.info("Calling initialize_project...")
            result = initialize_project(".", force)
            logger.info(f"initialize_project returned: {result}")

            # Format success message
            formatted = self.format_success(result)
            logger.info(f"Formatted success message (length: {len(formatted)})")
            return formatted

        except InitializationError as e:
            logger.error(f"InitializationError: {e}")
            raise CommandError(str(e))
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            raise

    def format_success(self, result: dict) -> str:
        """Format initialization success message.

        Args:
            result: Dictionary from initialize_project()

        Returns:
            Rich markdown-formatted message
        """
        path = result["path"]
        created_dirs = result["created_dirs"]
        installed_templates = result["installed_templates"]
        cdd_md_created = result["cdd_md_created"]
        cdd_md_migrated = result["cdd_md_migrated"]
        existing_structure = result["existing_structure"]

        # Build message
        lines = ["# ✅ CDD Project Initialized\n"]

        if existing_structure:
            lines.append(
                "⚠️  *Partial structure detected. Created missing items only.*\n"
            )

        lines.append(f"**Location:** `{path}`\n")

        # Created items
        if created_dirs:
            lines.append("**Created directories:**")
            for dir_name in created_dirs:
                lines.append(f"  - 📁 {dir_name}")
            lines.append("")

        # CDD.md status
        if cdd_md_migrated:
            lines.append("**CDD.md:** ✅ Migrated from CLAUDE.md")
            lines.append("💡 *You can now delete CLAUDE.md if desired*\n")
        elif cdd_md_created:
            lines.append("**CDD.md:** ✅ Created from template\n")
        else:
            lines.append("**CDD.md:** ✅ Already exists\n")

        # Templates
        if installed_templates:
            lines.append(
                f"**Templates:** ✅ Installed {len(installed_templates)} templates"
            )
            lines.append("  - Location: `.cdd/templates/`\n")

        # Next steps
        lines.append("**Next steps:**")
        lines.append("  1. Edit `CDD.md` with your project context")
        lines.append("  2. Create your first ticket: `/new ticket feature <name>`")
        lines.append("  3. Start building with CDD workflow!")

        return "\n".join(lines)
