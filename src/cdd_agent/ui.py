"""Rich terminal UI components for streaming conversations."""

import os
from typing import Generator, Optional

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from . import __version__

# Gold/yellow color scheme inspired by Droid and Neovim
BRAND_COLOR = "#d4a574"  # Warm gold/tan color for consistency
USER_COLOR = "#d4a574"  # Same as brand color
ASSISTANT_COLOR = "white"
THINKING_COLOR = "dim cyan"
TOOL_COLOR = "cyan"
SUCCESS_COLOR = "green"
ERROR_COLOR = "red"
DIM_COLOR = "dim"

ASCII_LOGO = """
██████╗██████╗ ██████╗
██╔════╝██╔══██╗██╔══██╗
██║     ██║  ██║██║  ██║
██║     ██║  ██║██║  ██║
╚██████╗██████╔╝██████╔╝
 ╚═════╝╚═════╝ ╚═════╝
"""

TAGLINE = "Context captured once. AI understands forever."
SUBTITLE = "Context-Driven Development"


class StreamingUI:
    """Rich UI for streaming conversations."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize streaming UI.

        Args:
            console: Rich console instance (creates one if not provided)
        """
        self.console = console or Console()

    def show_welcome(self, provider: str, model: str, cwd: str):
        """Show welcome screen with branding.

        Args:
            provider: Provider name (e.g., "custom", "anthropic")
            model: Model name (e.g., "glm-4.6")
            cwd: Current working directory
        """
        # ASCII logo in gold
        logo_text = Text(ASCII_LOGO, style=BRAND_COLOR)
        self.console.print(logo_text)

        # Version centered below ASCII art
        version_text = Text(f"v{__version__}", style=BRAND_COLOR)
        self.console.print(version_text, justify="center")
        self.console.print()  # Empty line for spacing

        # Subtitle and tagline
        self.console.print(f"[{BRAND_COLOR}]{SUBTITLE}[/{BRAND_COLOR}]")
        self.console.print(f"[italic]{TAGLINE}[/italic]\n")

        # Instructions
        self.console.print(
            f"[{DIM_COLOR}]ENTER to send • \\ + ENTER for a new line • @ to mention files[/{DIM_COLOR}]\n"
        )

        # Context info
        self.console.print(f"[{DIM_COLOR}]Current folder: {cwd}[/{DIM_COLOR}]")
        self.console.print(
            f"[{DIM_COLOR}]Provider: {provider} • Model: {model}[/{DIM_COLOR}]\n"
        )

        # Separator
        self.console.print("─" * self.console.width)
        self.console.print()

    def show_prompt(self, prompt: str = ">"):
        """Show input prompt.

        Args:
            prompt: Prompt character(s)
        """
        self.console.print(f"[bold]{prompt}[/bold] ", end="")

    def stream_response(self, event_stream: Generator):
        """Stream assistant response with real-time rendering.

        Args:
            event_stream: Generator yielding event dicts from agent.stream()
        """
        accumulated_text = ""
        thinking_shown = False

        for event in event_stream:
            event_type = event.get("type")

            if event_type == "thinking":
                # Show iteration counter
                if not thinking_shown:
                    self.console.print(
                        f"[{THINKING_COLOR}]⟳ {event['content']}...[/{THINKING_COLOR}]"
                    )
                    thinking_shown = True

            elif event_type == "text":
                # Accumulate and render markdown
                chunk = event.get("content", "")
                accumulated_text += chunk

                # Use Live to update in place
                if not thinking_shown:
                    # First chunk - start live display
                    thinking_shown = True

                # For now, just print chunks (we'll add Live display later)
                self.console.print(chunk, end="", markup=False, highlight=False)

            elif event_type == "tool_use":
                # Tool being called
                tool_name = event.get("name", "unknown")
                self.console.print(
                    f"\n[{TOOL_COLOR}]🔧 Using tool: {tool_name}[/{TOOL_COLOR}]"
                )

            elif event_type == "tool_result":
                # Tool result
                tool_name = event.get("name", "unknown")
                is_error = event.get("is_error", False)

                if is_error:
                    self.console.print(
                        f"[{ERROR_COLOR}]  ✗ Error in {tool_name}[/{ERROR_COLOR}]"
                    )
                else:
                    self.console.print(
                        f"[{SUCCESS_COLOR}]  ✓ {tool_name} completed[/{SUCCESS_COLOR}]"
                    )

                # Reset accumulated text for next response
                accumulated_text = ""
                thinking_shown = False

            elif event_type == "error":
                # Error message
                error_msg = event.get("content", "Unknown error")
                self.console.print(f"\n[{ERROR_COLOR}]⚠ {error_msg}[/{ERROR_COLOR}]")

        # Final newline after response
        self.console.print()

    def show_error(self, message: str, title: str = "Error"):
        """Show error in a panel.

        Args:
            message: Error message
            title: Panel title
        """
        panel = Panel(
            message,
            title=f"[{ERROR_COLOR}]{title}[/{ERROR_COLOR}]",
            border_style=ERROR_COLOR,
        )
        self.console.print(panel)

    def show_info(self, message: str, title: str = "Info"):
        """Show info message in a panel.

        Args:
            message: Info message
            title: Panel title
        """
        panel = Panel(
            message,
            title=f"[{BRAND_COLOR}]{title}[/{BRAND_COLOR}]",
            border_style=BRAND_COLOR,
        )
        self.console.print(panel)

    def show_help(self):
        """Show help message with available commands."""
        help_text = """
[bold]Slash Commands:[/bold]

  /help        Show this help message
  /clear       Clear conversation history
  /quit        Exit the chat (Ctrl+C also works)
  /save [name] Save current conversation
  /new         Start a new conversation

[bold]Input:[/bold]

  ENTER              Send message
  \\ + ENTER          Add a new line (multi-line input)
  @ + filename       Mention a file for context

[bold]Tips:[/bold]

  • Ask the AI to read, write, or modify files
  • Use bash commands via "run this command: ..."
  • Conversations are saved automatically
        """
        self.show_info(help_text.strip(), "Help")

    def confirm(self, message: str) -> bool:
        """Ask for user confirmation.

        Args:
            message: Confirmation message

        Returns:
            True if user confirms, False otherwise
        """
        response = self.console.input(f"[{BRAND_COLOR}]{message} [Y/n]:[/{BRAND_COLOR}] ")
        return response.lower() in ("", "y", "yes")

    def show_separator(self):
        """Show a separator line."""
        self.console.print(f"[{DIM_COLOR}]{'─' * self.console.width}[/{DIM_COLOR}]")
