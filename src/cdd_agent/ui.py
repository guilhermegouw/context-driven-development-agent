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
        import time
        from threading import Thread, Event

        accumulated_text = ""
        status_active = False
        stop_animation = Event()
        status_events = []  # Keep last 3 events

        def format_status():
            """Format status events as 3-line display."""
            if not status_events:
                return ""
            lines = []
            for event_text in status_events[-3:]:  # Last 3 events
                lines.append(event_text)
            return "\n".join(lines)

        def animate_status(live: Live):
            """Animate thinking dots in status area."""
            dots = 0
            while not stop_animation.is_set():
                dots = (dots % 3) + 1
                dot_str = "." * dots
                # Update the first line with animated dots
                if status_events:
                    # Keep all events but animate the first one
                    animated_events = status_events.copy()
                    if animated_events:
                        animated_events[0] = f"💭 Thinking{dot_str}"
                    lines = animated_events[-3:]  # Last 3
                    live.update("\n".join(lines))
                time.sleep(1.0)  # Slower animation (1 second per dot)

        animation_thread = None
        status_live = None

        for event in event_stream:
            event_type = event.get("type")

            if event_type == "thinking":
                thinking_msg = event.get("content", "Thinking")
                status_events.append(f"💭 {thinking_msg}.")

                # Start status area if not active
                if not status_active:
                    stop_animation.clear()
                    status_live = Live(
                        format_status(),
                        console=self.console,
                        refresh_per_second=2,
                    )
                    status_live.start()
                    animation_thread = Thread(
                        target=animate_status,
                        args=(status_live,),
                        daemon=True,
                    )
                    animation_thread.start()
                    status_active = True

            elif event_type == "tool_use":
                tool_name = event.get("name", "unknown")
                status_events.append(f"🔧 Using tool: {tool_name}")
                if status_live:
                    status_live.update(format_status())

            elif event_type == "tool_result":
                tool_name = event.get("name", "unknown")
                is_error = event.get("is_error", False)

                if is_error:
                    msg = f"✗ Error in {tool_name}"
                else:
                    msg = f"✓ {tool_name} completed"

                status_events.append(msg)
                if status_live:
                    status_live.update(format_status())

            elif event_type == "text":
                # Stop status area and start text output
                if status_active:
                    stop_animation.set()
                    if animation_thread:
                        animation_thread.join(timeout=1.0)
                    if status_live:
                        status_live.stop()
                    status_active = False
                    status_events.clear()
                    self.console.print()  # New line after status

                # Accumulate and render text
                chunk = event.get("content", "")
                accumulated_text += chunk

                # Print chunks as they arrive
                self.console.print(chunk, end="", markup=False, highlight=False)

            elif event_type == "error":
                # Stop status area
                if status_active:
                    stop_animation.set()
                    if animation_thread:
                        animation_thread.join(timeout=1.0)
                    if status_live:
                        status_live.stop()
                    status_active = False
                    status_events.clear()
                    self.console.print()  # New line after status

                # Error message
                error_msg = event.get("content", "Unknown error")
                self.console.print(f"[{ERROR_COLOR}]⚠ {error_msg}[/{ERROR_COLOR}]")

        # Stop status area if still running
        if status_active:
            stop_animation.set()
            if animation_thread:
                animation_thread.join(timeout=1.0)
            if status_live:
                status_live.stop()
            self.console.print()  # New line after status

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
