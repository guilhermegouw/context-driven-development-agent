"""Display available slash commands.

Handler for the /help slash command.
"""

from .base import BaseSlashCommand
from .router import get_router


class HelpCommand(BaseSlashCommand):
    """Display available slash commands and their usage.

    Usage:
        /help           # Show all commands
        /help <command> # Show detailed help for specific command
    """

    def __init__(self):
        """Initialize command metadata."""
        super().__init__()
        self.name = "help"
        self.description = "Display available commands"
        self.usage = "[command]"
        self.examples = [
            "/help",
            "/help init",
            "/help new",
        ]

    async def execute(self, args: str) -> str:
        """Display help information.

        Args:
            args: Optional command name to get specific help

        Returns:
            Formatted help message
        """
        router = get_router()

        # Specific command help
        if args.strip():
            command_name = args.strip()
            return self._format_command_help(command_name, router)

        # General help (all commands)
        return self._format_general_help(router)

    def _format_general_help(self, router) -> str:
        """Format general help (list all commands).

        Args:
            router: Router instance to get commands from

        Returns:
            Markdown-formatted help message
        """
        commands = router.get_all_commands()

        lines = [
            "# 📚 CDD Agent Slash Commands\n",
            "Slash commands allow you to execute CDD operations without "
            "leaving chat.\n",
            "**Available commands:**\n",
        ]

        for cmd in commands:
            lines.append(f"**`/{cmd.name}`** - {cmd.description}")
            lines.append(f"  Usage: `/{cmd.name} {cmd.usage}`")
            lines.append("")

        lines.append("**Get detailed help:**")
        lines.append("  `/help <command>` - Show examples and details\n")

        lines.append("**Examples:**")
        lines.append("  `/help init` - Show /init command details")
        lines.append("  `/help new` - Show /new command details")

        return "\n".join(lines)

    def _format_command_help(self, command_name: str, router) -> str:
        """Format help for specific command.

        Args:
            command_name: Name of command to show help for
            router: Router instance to get commands from

        Returns:
            Markdown-formatted help message
        """
        commands = {cmd.name: cmd for cmd in router.get_all_commands()}

        if command_name not in commands:
            available = ", ".join(f"/{name}" for name in sorted(commands.keys()))
            return (
                f"❌ Unknown command: /{command_name}\n\n"
                f"Available commands: {available}\n\n"
                f"Use `/help` to see all commands"
            )

        cmd = commands[command_name]

        lines = [
            f"# 📚 Help: `/{cmd.name}`\n",
            f"**Description:** {cmd.description}\n",
            f"**Usage:** `/{cmd.name} {cmd.usage}`\n",
            "**Examples:**",
        ]

        for example in cmd.examples:
            lines.append(f"  `{example}`")

        return "\n".join(lines)
