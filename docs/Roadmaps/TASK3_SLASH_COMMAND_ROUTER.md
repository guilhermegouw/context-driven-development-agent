# Task 3: Implement Slash Command Router

**Status:** 🔜 Planning Complete, Ready to Implement
**Estimated Time:** 3-4 hours
**Dependencies:** Task 1 ✅, Task 2 ✅
**Date:** 2025-11-09

---

## Objective

Implement a slash command router system that enables users to execute CDD commands (mechanical layer) from within `cdd-agent chat` sessions. This eliminates the need to switch between terminal and chat, providing a unified UX.

---

## Background

### Current State (After Task 1 & 2)
- ✅ `initialize_project()` - Creates CDD structure
- ✅ `create_new_ticket()` - Creates ticket specifications
- ✅ `create_new_documentation()` - Creates documentation files

### Problem
These functions are currently isolated Python functions with no way for users to invoke them during a chat session.

### Solution
Create a slash command router that:
1. Detects slash commands in user messages
2. Parses command arguments
3. Routes to appropriate handler
4. Executes mechanical layer functions
5. Returns formatted results to chat

---

## Architecture Design

### Component Structure

```
src/cdd_agent/
├── slash_commands/
│   ├── __init__.py          # Module exports
│   ├── router.py            # Main router and detection logic
│   ├── base.py              # BaseSlashCommand abstract class
│   ├── init_command.py      # /init handler
│   ├── new_command.py       # /new handler
│   └── help_command.py      # /help handler (list commands)
└── agent.py                 # [MODIFIED] Integrate router into chat loop
```

### Command Hierarchy

```
/init [--force]
    └─> InitCommand.execute()
        └─> initialize_project()

/new ticket <type> <name>
    └─> NewCommand.execute()
        └─> create_new_ticket(type, name)

/new documentation <type> <name>
    └─> NewCommand.execute()
        └─> create_new_documentation(type, name)

/help [command]
    └─> HelpCommand.execute()
        └─> Display available commands
```

---

## Detailed Implementation Plan

### Step 1: Create Base Command Class (30 min)

**File:** `src/cdd_agent/slash_commands/base.py`

**Purpose:** Abstract base class that all slash commands inherit from.

**Interface:**
```python
from abc import ABC, abstractmethod
from typing import Optional

class BaseSlashCommand(ABC):
    """Base class for all slash commands."""

    def __init__(self):
        self.name: str = ""           # Command name (e.g., "init")
        self.description: str = ""     # Short description
        self.usage: str = ""           # Usage pattern
        self.examples: list[str] = []  # Example invocations

    @abstractmethod
    async def execute(self, args: str) -> str:
        """Execute the command with given arguments.

        Args:
            args: Raw argument string (everything after command name)

        Returns:
            Formatted result message to display in chat

        Raises:
            CommandError: If command execution fails
        """
        pass

    def validate_args(self, args: str) -> bool:
        """Validate command arguments (optional override)."""
        return True

    def format_success(self, result: dict) -> str:
        """Format successful result (optional override)."""
        return "Command executed successfully"

    def format_error(self, error: Exception) -> str:
        """Format error message (optional override)."""
        return f"Error: {error}"


class CommandError(Exception):
    """Raised when command execution fails."""
    pass
```

**Key Design Decisions:**
- Async interface for future compatibility with async operations
- Returns string (formatted for chat display)
- Validation and formatting methods are optional overrides
- Each command is responsible for its own formatting

---

### Step 2: Create Slash Command Router (45 min)

**File:** `src/cdd_agent/slash_commands/router.py`

**Purpose:** Detect, parse, and route slash commands to handlers.

**Implementation:**
```python
import re
from typing import Optional, Type
from rich.console import Console

from .base import BaseSlashCommand, CommandError

console = Console()


class SlashCommandRouter:
    """Routes slash commands to appropriate handlers."""

    def __init__(self):
        self._commands: dict[str, BaseSlashCommand] = {}

    def register(self, command: BaseSlashCommand) -> None:
        """Register a slash command handler.

        Args:
            command: Command instance to register
        """
        self._commands[command.name] = command
        console.print(f"[dim]Registered command: /{command.name}[/dim]", style="dim")

    def is_slash_command(self, message: str) -> bool:
        """Check if message starts with a slash command.

        Args:
            message: User input message

        Returns:
            True if message is a slash command
        """
        return message.strip().startswith("/")

    def parse_command(self, message: str) -> tuple[str, str]:
        """Parse slash command into name and arguments.

        Args:
            message: User input (e.g., "/init --force")

        Returns:
            Tuple of (command_name, args_string)

        Examples:
            "/init" -> ("init", "")
            "/init --force" -> ("init", "--force")
            "/new ticket feature Auth" -> ("new", "ticket feature Auth")
        """
        message = message.strip()

        if not message.startswith("/"):
            raise CommandError("Not a slash command")

        # Remove leading slash
        message = message[1:]

        # Split on first whitespace
        parts = message.split(maxsplit=1)

        command_name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        return command_name, args

    async def execute(self, message: str) -> str:
        """Execute a slash command.

        Args:
            message: Full user message (e.g., "/init --force")

        Returns:
            Formatted result string

        Raises:
            CommandError: If command not found or execution fails
        """
        try:
            command_name, args = self.parse_command(message)

            if command_name not in self._commands:
                return self._format_unknown_command(command_name)

            command = self._commands[command_name]

            # Validate arguments
            if not command.validate_args(args):
                return self._format_invalid_args(command)

            # Execute command
            result = await command.execute(args)
            return result

        except CommandError as e:
            return f"❌ Command error: {e}"
        except Exception as e:
            console.print_exception()
            return f"❌ Unexpected error: {e}"

    def _format_unknown_command(self, command_name: str) -> str:
        """Format error message for unknown command."""
        available = ", ".join(f"/{name}" for name in self._commands.keys())
        return (
            f"❌ Unknown command: /{command_name}\n\n"
            f"Available commands: {available}\n"
            f"Type /help for more information"
        )

    def _format_invalid_args(self, command: BaseSlashCommand) -> str:
        """Format error message for invalid arguments."""
        return (
            f"❌ Invalid arguments\n\n"
            f"Usage: /{command.name} {command.usage}\n\n"
            f"Examples:\n" + "\n".join(f"  {ex}" for ex in command.examples)
        )

    def get_all_commands(self) -> list[BaseSlashCommand]:
        """Get list of all registered commands."""
        return list(self._commands.values())


# Global router instance
_router: Optional[SlashCommandRouter] = None


def get_router() -> SlashCommandRouter:
    """Get the global slash command router instance."""
    global _router
    if _router is None:
        _router = SlashCommandRouter()
    return _router
```

**Key Features:**
- Command registration system
- Parsing with validation
- Error handling with helpful messages
- Global singleton pattern for easy access
- Rich console integration for debug output

---

### Step 3: Implement /init Command (30 min)

**File:** `src/cdd_agent/slash_commands/init_command.py`

**Purpose:** Handler for `/init` command.

**Implementation:**
```python
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from .base import BaseSlashCommand, CommandError
from ..mechanical.init import initialize_project, InitializationError

console = Console()


class InitCommand(BaseSlashCommand):
    """Initialize CDD project structure."""

    def __init__(self):
        super().__init__()
        self.name = "init"
        self.description = "Initialize CDD project structure"
        self.usage = "[--force]"
        self.examples = [
            "/init",
            "/init --force",
        ]

    def validate_args(self, args: str) -> bool:
        """Validate arguments (only --force allowed)."""
        if not args:
            return True
        return args.strip() == "--force"

    async def execute(self, args: str) -> str:
        """Execute project initialization.

        Args:
            args: Command arguments (empty or "--force")

        Returns:
            Formatted success message
        """
        force = "--force" in args

        try:
            # Execute initialization
            result = initialize_project(".", force)

            # Format success message
            return self.format_success(result)

        except InitializationError as e:
            raise CommandError(str(e))

    def format_success(self, result: dict) -> str:
        """Format initialization success message.

        Args:
            result: Dictionary from initialize_project()

        Returns:
            Rich-formatted message
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
            lines.append("⚠️  *Partial structure detected. Created missing items only.*\n")

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
            lines.append(f"**Templates:** ✅ Installed {len(installed_templates)} templates")
            lines.append(f"  - Location: `.cdd/templates/`\n")

        # Next steps
        lines.append("**Next steps:**")
        lines.append("  1. Edit `CDD.md` with your project context")
        lines.append("  2. Create your first ticket: `/new ticket feature <name>`")
        lines.append("  3. Start building with CDD workflow!")

        return "\n".join(lines)
```

**Key Features:**
- Validates `--force` flag
- Calls `initialize_project()` from mechanical layer
- Rich markdown formatting for output
- Helpful next steps for users

---

### Step 4: Implement /new Command (45 min)

**File:** `src/cdd_agent/slash_commands/new_command.py`

**Purpose:** Handler for `/new` command (tickets and documentation).

**Implementation:**
```python
import re
from rich.console import Console

from .base import BaseSlashCommand, CommandError
from ..mechanical.new_ticket import (
    create_new_ticket,
    create_new_documentation,
    TicketCreationError,
)

console = Console()


class NewCommand(BaseSlashCommand):
    """Create new tickets or documentation."""

    def __init__(self):
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
        """Format ticket creation success message."""
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
            "  2. Use `/plan` to generate implementation plan (coming soon)",
            "  3. Use `/exec` to execute the plan (coming soon)",
        ]

        return "\n".join(lines)

    def _format_doc_success(self, result: dict) -> str:
        """Format documentation creation success message."""
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
            "  2. Use this documentation as context for AI assistance",
        ]

        return "\n".join(lines)

    def _format_usage_error(self) -> str:
        """Format usage error message."""
        lines = [
            "# ❌ Invalid Usage\n",
            "**Ticket creation:**",
            f"  `/new ticket <type> <name>`",
            f"  Valid types: {', '.join(self.ticket_types)}\n",
            "**Documentation creation:**",
            f"  `/new documentation <type> <name>`",
            f"  Valid types: {', '.join(self.doc_types)}\n",
            "**Examples:**",
        ] + [f"  {ex}" for ex in self.examples]

        return "\n".join(lines)
```

**Key Features:**
- Handles both tickets and documentation
- Validates category and type
- Calls appropriate mechanical layer function
- Rich formatting with next steps
- Helpful error messages

---

### Step 5: Implement /help Command (20 min)

**File:** `src/cdd_agent/slash_commands/help_command.py`

**Purpose:** Display available commands and usage.

**Implementation:**
```python
from .base import BaseSlashCommand
from .router import get_router


class HelpCommand(BaseSlashCommand):
    """Display available slash commands."""

    def __init__(self):
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
        """Format general help (list all commands)."""
        commands = router.get_all_commands()

        lines = [
            "# 📚 CDD Agent Slash Commands\n",
            "**Available commands:**\n",
        ]

        for cmd in commands:
            lines.append(f"**`/{cmd.name}`** - {cmd.description}")
            lines.append(f"  Usage: `/{cmd.name} {cmd.usage}`")
            lines.append("")

        lines.append("**Get detailed help:**")
        lines.append("  `/help <command>` - Show examples and details\n")

        lines.append("**Examples:**")
        lines.append("  `/help init`")
        lines.append("  `/help new`")

        return "\n".join(lines)

    def _format_command_help(self, command_name: str, router) -> str:
        """Format help for specific command."""
        commands = {cmd.name: cmd for cmd in router.get_all_commands()}

        if command_name not in commands:
            return f"❌ Unknown command: /{command_name}\n\nUse `/help` to see all commands"

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
```

**Key Features:**
- Lists all available commands
- Shows detailed help for specific command
- Markdown formatting

---

### Step 6: Create Module Initialization (15 min)

**File:** `src/cdd_agent/slash_commands/__init__.py`

**Purpose:** Initialize and export slash command system.

**Implementation:**
```python
"""Slash command system for CDD Agent.

This module provides slash command functionality for the chat interface,
allowing users to execute CDD commands without leaving the chat session.

Usage:
    from cdd_agent.slash_commands import get_router, setup_commands

    router = get_router()
    setup_commands(router)

    # In chat loop
    if router.is_slash_command(user_message):
        result = await router.execute(user_message)
        print(result)
"""

from .router import SlashCommandRouter, get_router, CommandError
from .base import BaseSlashCommand
from .init_command import InitCommand
from .new_command import NewCommand
from .help_command import HelpCommand


def setup_commands(router: SlashCommandRouter) -> None:
    """Register all available slash commands.

    Args:
        router: Router instance to register commands with
    """
    # Register mechanical layer commands
    router.register(InitCommand())
    router.register(NewCommand())

    # Register meta commands
    router.register(HelpCommand())


__all__ = [
    "SlashCommandRouter",
    "get_router",
    "setup_commands",
    "BaseSlashCommand",
    "CommandError",
    "InitCommand",
    "NewCommand",
    "HelpCommand",
]
```

---

### Step 7: Integrate into Agent Chat Loop (45 min)

**File:** `src/cdd_agent/agent.py` (MODIFIED)

**Changes Required:**

1. **Import slash command system:**
```python
from .slash_commands import get_router, setup_commands
```

2. **Initialize router on agent startup:**
```python
class Agent:
    def __init__(self, ...):
        # ... existing code ...

        # Initialize slash command router
        self.slash_router = get_router()
        setup_commands(self.slash_router)
```

3. **Add slash command detection to chat loop:**
```python
async def chat(self, ...):
    """Main chat loop."""

    while True:
        # Get user input
        user_message = await self.get_user_input()

        # Check for slash commands
        if self.slash_router.is_slash_command(user_message):
            try:
                # Execute slash command
                result = await self.slash_router.execute(user_message)

                # Display result
                self.console.print(Markdown(result))

                # Continue to next iteration (don't send to LLM)
                continue

            except Exception as e:
                self.console.print(f"[red]Error executing command: {e}[/red]")
                continue

        # ... existing chat logic for non-slash messages ...
```

**Key Integration Points:**
- Early detection before LLM call
- Direct result display (no LLM involvement)
- Error handling with continue to next iteration
- Markdown rendering for rich output

---

## Testing Strategy

### Unit Tests

**File:** `test_slash_commands.py`

**Test Coverage:**

1. **Router Tests (10 tests)**
   - ✅ Command registration
   - ✅ Slash command detection
   - ✅ Command parsing
   - ✅ Unknown command handling
   - ✅ Invalid argument handling

2. **InitCommand Tests (5 tests)**
   - ✅ Fresh initialization
   - ✅ Initialization with --force
   - ✅ Error handling (non-git, dangerous paths)
   - ✅ Success message formatting
   - ✅ Idempotency

3. **NewCommand Tests (8 tests)**
   - ✅ Create feature ticket
   - ✅ Create bug/spike/enhancement tickets
   - ✅ Create guide documentation
   - ✅ Create feature documentation
   - ✅ Invalid type handling
   - ✅ Invalid arguments
   - ✅ Success message formatting

4. **HelpCommand Tests (3 tests)**
   - ✅ General help (all commands)
   - ✅ Specific command help
   - ✅ Unknown command help

### Integration Tests (from INTEGRATION_TEST_ROADMAP.md)

**IT-3.1:** Slash command detection in chat loop
**IT-3.2:** `/init` command execution from chat
**IT-3.3:** `/new ticket` command execution from chat
**IT-3.4:** `/new documentation` command execution from chat
**IT-3.5:** `/help` command displays all commands
**IT-3.6:** Error handling for unknown commands
**IT-3.7:** Error handling for invalid arguments

---

## Success Criteria

- ✅ `SlashCommandRouter` correctly detects and routes commands
- ✅ `/init` command creates CDD structure
- ✅ `/new ticket` creates all 4 ticket types
- ✅ `/new documentation` creates both doc types
- ✅ `/help` displays command information
- ✅ Commands integrate smoothly into chat loop
- ✅ Errors are handled gracefully with helpful messages
- ✅ Results are formatted in markdown for chat display
- ✅ All unit tests pass
- ✅ Quality checks pass (Black, Ruff, mypy)

---

## Files to Create/Modify

### New Files (7)
1. `src/cdd_agent/slash_commands/__init__.py`
2. `src/cdd_agent/slash_commands/base.py`
3. `src/cdd_agent/slash_commands/router.py`
4. `src/cdd_agent/slash_commands/init_command.py`
5. `src/cdd_agent/slash_commands/new_command.py`
6. `src/cdd_agent/slash_commands/help_command.py`
7. `test_slash_commands.py`

### Modified Files (1)
1. `src/cdd_agent/agent.py` (integrate router into chat loop)

### Documentation (1)
1. `docs/TASK3_COMPLETION_SUMMARY.md` (after implementation)

---

## Estimated Timeline

| Step | Task | Time |
|------|------|------|
| 1 | Create BaseSlashCommand | 30 min |
| 2 | Create SlashCommandRouter | 45 min |
| 3 | Implement InitCommand | 30 min |
| 4 | Implement NewCommand | 45 min |
| 5 | Implement HelpCommand | 20 min |
| 6 | Create module __init__.py | 15 min |
| 7 | Integrate into agent.py | 45 min |
| 8 | Write unit tests | 45 min |
| 9 | Run integration tests | 30 min |
| 10 | Documentation | 15 min |
| **Total** | | **~4 hours** |

---

## Risk Assessment

### Low Risk
- ✅ Base architecture is straightforward
- ✅ Clear separation of concerns
- ✅ Mechanical layer already tested and working

### Medium Risk
- ⚠️ Integration with existing agent.py chat loop
  - **Mitigation:** Test thoroughly, add fallback error handling

### Minimal Risk
- Chat loop interruption handling
  - **Mitigation:** Commands execute synchronously, no complex state

---

## Future Enhancements (Not in Scope for Task 3)

1. **Slash command auto-completion** - Tab completion for command names
2. **Command aliases** - Short forms (e.g., `/i` for `/init`)
3. **Command history** - Recall previous slash commands
4. **Interactive prompts** - Multi-step command wizards
5. **Command plugins** - User-defined custom slash commands

---

## Dependencies

### Python Packages (Already Available)
- Rich - For markdown rendering and console output
- Click - For argument parsing (already used by mechanical layer)
- Pathlib - For path operations

### Internal Dependencies
- ✅ `cdd_agent.mechanical.init` - initialize_project()
- ✅ `cdd_agent.mechanical.new_ticket` - create_new_ticket(), create_new_documentation()

---

## Notes

### Design Rationale

**Why async interface?**
- Future-proof for async mechanical operations (e.g., LLM calls in agents)
- Consistent with modern Python async patterns
- Easy to integrate with async chat loop

**Why separate command classes?**
- Single Responsibility Principle
- Easy to add new commands
- Clear ownership of formatting and validation
- Testable in isolation

**Why global router?**
- Single source of truth for registered commands
- Easy access from chat loop
- Singleton pattern prevents multiple registrations

**Why markdown output?**
- Rich rendering in terminal
- Consistent with chat interface
- Easy to read and format
- Supports code blocks, lists, emphasis

---

## Next Steps After Task 3

With slash commands complete, the foundation is ready for:

- **Task 4:** Integrate with chat session (context management)
- **Task 5:** Create BaseAgent architecture
- **Week 5:** Implement Socrates agent (`/socrates` command)
- **Week 6:** Implement Planner agent (`/plan` command)
- **Week 7:** Implement Executor agent (`/exec` command)

---

**Task 3 Status:** 🔜 **READY TO IMPLEMENT**

Plan approved and documented. Ready to begin implementation.
