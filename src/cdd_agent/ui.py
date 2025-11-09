"""Rich terminal UI components for streaming conversations."""

from typing import Generator, Optional

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text

from . import __version__
from .tools import RiskLevel

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

    def request_approval(
        self, tool_name: str, args: dict, risk_level: RiskLevel
    ) -> bool:
        """Request approval for tool execution (simple mode).

        Args:
            tool_name: Name of tool requesting approval
            args: Tool arguments
            risk_level: Risk classification

        Returns:
            True if approved, False if denied
        """
        # Determine risk color
        risk_colors = {
            RiskLevel.SAFE: "green",
            RiskLevel.MEDIUM: "yellow",
            RiskLevel.HIGH: "red",
        }
        risk_color = risk_colors[risk_level]

        # Format arguments for display
        args_text = ", ".join(f"{key}={str(value)[:40]}" for key, value in args.items())
        if not args_text:
            args_text = "(no arguments)"

        # Check for dangerous patterns
        warning = None
        if tool_name == "run_bash" and "command" in args:
            from .approval import ApprovalManager

            manager = ApprovalManager(mode=None, ui_callback=None)  # type: ignore
            is_dangerous, warn_msg = manager.is_dangerous_command(args["command"])
            if is_dangerous:
                warning = warn_msg

        # Show approval request
        self.console.print()
        self.console.print("[bold]🔐 Tool Approval Required[/bold]", style=risk_color)
        self.console.print(f"  Tool: [bold {risk_color}]{tool_name}[/]")
        self.console.print(f"  Risk: [{risk_color}]{risk_level.value.upper()}[/]")
        self.console.print(f"  Args: {args_text}")

        if warning:
            self.console.print(f"  [bold red]⚠️  WARNING: {warning}[/]")

        # Ask for confirmation
        approved = Confirm.ask("[bold]Allow this tool to execute?[/]", default=False)

        if approved:
            self.console.print("[green]✓ Tool approved[/]")
        else:
            self.console.print("[yellow]✗ Tool denied[/]")

        self.console.print()
        return approved

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
        instructions = (
            f"[{DIM_COLOR}]ENTER to send • \\ + ENTER for a new line • "
            f"@ to mention files[/{DIM_COLOR}]\n"
        )
        self.console.print(instructions)

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

        Hybrid approach:
        1. Stream raw text in real-time for responsiveness
        2. After streaming completes, re-render as beautiful markdown

        Args:
            event_stream: Generator yielding event dicts from agent.stream()
        """
        import time
        from threading import Event, Thread

        accumulated_text = ""
        status_active = False
        stop_animation = Event()
        status_events = []  # Keep last 3 events
        raw_text_lines = 0  # Track how many lines of raw text we printed

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

                # Accumulate text
                chunk = event.get("content")
                if chunk is not None:  # Only process if chunk is not None
                    accumulated_text += chunk

                    # Print chunks as they arrive (raw text for speed)
                    self.console.print(chunk, end="", markup=False, highlight=False)

                    # Track lines for clearing later
                    raw_text_lines += chunk.count("\n")

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

        # Hybrid approach: Now re-render as beautiful markdown
        if accumulated_text.strip():
            # Clear the raw text output
            # Move cursor up and clear lines
            if raw_text_lines > 0:
                # ANSI escape codes: Move up N lines and clear from cursor to end
                clear_sequence = f"\033[{raw_text_lines + 2}A\033[J"
                self.console.file.write(clear_sequence)
                self.console.file.flush()

            # Render as beautiful markdown with Catppuccin theme
            self._render_markdown(accumulated_text)

        # Final newline after response
        self.console.print()

    def _convert_underline_headings(self, text: str) -> str:
        """Convert underline-style headings to # syntax.

        Converts:
            Heading
            =======
        To:
            # Heading

        And:
            Subheading
            ----------
        To:
            ## Subheading

        Args:
            text: Markdown text potentially containing underline-style headings

        Returns:
            Converted markdown text with # syntax headings
        """
        import re

        # Convert H1 style (text followed by ===)
        text = re.sub(
            r"^(.+)\n=+\s*$",
            r"# \1",
            text,
            flags=re.MULTILINE,
        )

        # Convert H2 style (text followed by ---)
        text = re.sub(
            r"^(.+)\n-+\s*$",
            r"## \1",
            text,
            flags=re.MULTILINE,
        )

        return text

    def _render_markdown(self, text: str):
        """Render text as beautiful markdown with syntax highlighting.

        Uses Catppuccin Frappé for code syntax highlighting while keeping
        the original gold/tan color scheme for other elements.

        Args:
            text: Markdown text to render
        """
        from rich.theme import Theme

        # Convert underline-style headings to # syntax
        text = self._convert_underline_headings(text)

        try:
            from catppuccin.extras.pygments import FrappeStyle

            # Use Catppuccin only for code syntax highlighting
            md = Markdown(
                text,
                code_theme=FrappeStyle,
                inline_code_lexer="python",
                inline_code_theme=FrappeStyle,
            )
        except ImportError:
            # Fallback to default theme if catppuccin not available
            md = Markdown(text)

        # Create a custom theme that removes underlines from headings
        custom_theme = Theme(
            {
                "markdown.h1": "bold",
                "markdown.h2": "bold",
                "markdown.h3": "bold",
                "markdown.h4": "bold",
                "markdown.h5": "bold",
                "markdown.h6": "bold",
            }
        )

        # Create a temporary console with custom theme (no underlines on headings)
        from rich.console import Console

        temp_console = Console(theme=custom_theme, file=self.console.file)
        temp_console.print(md)

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
  /compact     Compact conversation (summarize old messages)
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
  • Use /compact if conversation gets too long
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
        response = self.console.input(
            f"[{BRAND_COLOR}]{message} [Y/n]:[/{BRAND_COLOR}] "
        )
        return response.lower() in ("", "y", "yes")

    def show_separator(self):
        """Show a separator line."""
        self.console.print(f"[{DIM_COLOR}]{'─' * self.console.width}[/{DIM_COLOR}]")
