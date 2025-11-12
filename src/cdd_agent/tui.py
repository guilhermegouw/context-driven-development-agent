"""Textual TUI for CDD Agent - Beautiful split-pane chat interface."""

import os
import threading
import time
from typing import Dict, Optional

from rich.panel import Panel
from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static, TextArea

from . import __version__
from .agent import Agent
from .background_executor import get_background_executor
from .session import ChatSession
from .tools import RiskLevel
from .utils.custom_markdown import LeftAlignedMarkdown
from .utils.markdown_normalizer import normalize_markdown

# Gold/yellow color scheme
BRAND_COLOR = "#d4a574"  # Warm gold/tan color for consistency
USER_COLOR = "#d4a574"  # Same as brand color
ASSISTANT_COLOR = "white"
TOOL_COLOR = "magenta"
ERROR_COLOR = "red"
DIM_COLOR = "dim"

ASCII_LOGO = """██████╗██████╗ ██████╗
██╔════╝██╔══██╗██╔══██╗
██║     ██║  ██║██║  ██║
██║     ██║  ██║██║  ██║
╚██████╗██████╔╝██████╔╝
 ╚═════╝╚═════╝ ╚═════╝"""

TAGLINE = "Context captured once. AI understands forever."
SUBTITLE = "Context-Driven Development"


def create_welcome_message(provider: str, model: str, cwd: str, width: int = 80, execution_mode=None) -> str:
    """Create centered welcome message text.

    Args:
        provider: Provider name
        model: Model name
        cwd: Current working directory
        width: Terminal width for centering
        execution_mode: Optional ExecutionMode to display

    Returns:
        Formatted welcome message
    """
    from .utils.execution_state import ExecutionMode

    # Center each line of ASCII logo
    lines = [
        "",
        "██████╗██████╗ ██████╗",
        "██╔════╝██╔══██╗██╔══██╗",
        "██║     ██║  ██║██║  ██║",
        "██║     ██║  ██║██║  ██║",
        "╚██████╗██████╔╝██████╔╝",
        " ╚═════╝╚═════╝ ╚═════╝",
        "",
        f"v{__version__}",
        "",
        "Context-Driven Development",
        "Context captured once. AI understands forever.",
        "",
        f"Provider: {provider} • Model: {model}",
        f"Folder: {cwd}",
    ]

    # Add mode indicator if in Plan Mode
    if execution_mode == ExecutionMode.PLAN:
        mode_icon = execution_mode.get_icon()
        mode_name = execution_mode.get_display_name()
        lines.append(f"Mode: {mode_icon} {mode_name} (read-only) • Shift+Tab to toggle")

    lines.append("")

    # Center align all lines based on terminal width
    return "\n".join(line.center(width) for line in lines)


class MessageWidget(Static):
    """A single message in the chat."""

    # Use reactive property for selection state
    is_selected = reactive(False)

    class Selected(Message):
        """Message sent when a message is selected/deselected."""

        def __init__(self, message_widget: "MessageWidget") -> None:
            """Initialize selected message.

            Args:
                message_widget: The message widget that was selected
            """
            self.message_widget = message_widget
            super().__init__()

    def __init__(
        self,
        content: str,
        role: str = "user",
        is_markdown: bool = True,
        **kwargs,
    ):
        """Initialize message widget.

        Args:
            content: Message content
            role: Message role (user/assistant/tool/system)
            is_markdown: Whether to render as markdown
        """
        self.content = content
        self.role = role
        self.is_markdown = is_markdown
        super().__init__(**kwargs)

    def watch_is_selected(self, new_value: bool) -> None:
        """Watch for changes to is_selected and update display."""
        # Update CSS class for background styling
        if new_value:
            self.add_class("selected")
        else:
            self.remove_class("selected")

        # Re-render the content with new border style
        # Only do this if the widget is mounted (has children)
        if self.children:
            try:
                self.remove_children()
                self.mount(*self.compose())
            except Exception:
                # If we can't re-render (e.g., no app context), just skip
                pass

    def on_click(self) -> None:
        """Handle click on message - toggle selection."""
        # Toggle selection state (this will trigger watch_is_selected)
        self.is_selected = not self.is_selected

        # Post selection event for app-level handling if needed
        try:
            self.post_message(self.Selected(self))
        except Exception:
            # If post_message fails (e.g., in tests without app context), just skip
            pass

    def compose(self) -> ComposeResult:
        """Compose the message."""
        # Choose style and format based on role
        if self.role == "system" and not self.is_markdown:
            # Simple system messages (like welcome) - no border, just yellow text
            text = Text(self.content, style=BRAND_COLOR)
            yield Static(text)
        else:
            # Regular messages with panels
            if self.role == "user":
                # Use brighter gold for selected state
                border_style = "#ffd700" if self.is_selected else USER_COLOR
                title = "Human"
                title_align = "right"
            elif self.role == "assistant":
                # Use brand color (gold) for selected state
                border_style = BRAND_COLOR if self.is_selected else ASSISTANT_COLOR
                title = "Robot"
                title_align = "left"
            elif self.role == "tool":
                # Use brighter magenta for selected state
                border_style = "#ff00ff" if self.is_selected else TOOL_COLOR
                title = "🔧 Tool"
                title_align = "left"
            elif self.role == "error":
                # Use brighter red for selected state
                border_style = "#ff0000" if self.is_selected else ERROR_COLOR
                title = "⚠ Error"
                title_align = "left"
            else:
                # Use brand color for selected state
                border_style = BRAND_COLOR if self.is_selected else DIM_COLOR
                title = "System"
                title_align = "left"

            # Render content
            if self.is_markdown:
                # Normalize markdown for consistent rendering
                normalized_content = normalize_markdown(self.content)

                # Use Catppuccin syntax highlighting for code blocks
                try:
                    from catppuccin.extras.pygments import FrappeStyle

                    content_widget = LeftAlignedMarkdown(
                        normalized_content,
                        code_theme=FrappeStyle,
                        inline_code_lexer="python",
                        inline_code_theme=FrappeStyle,
                    )
                except ImportError:
                    # Fallback to default if catppuccin not available
                    content_widget = LeftAlignedMarkdown(normalized_content)

                # Note: TUI uses Textual's Markdown widget which has its own styling
                # Heading underlines are controlled by Textual's CSS, not Rich's Theme
            else:
                content_widget = Text(self.content)

            # Create panel
            panel = Panel(
                content_widget,
                title=title,
                title_align=title_align,
                border_style=border_style,
            )

            yield Static(panel)

    def update_content(self, new_content: str):
        """Update message content (for streaming).

        Args:
            new_content: New content to display
        """
        # Normalize markdown before storing
        if self.is_markdown and self.role == "assistant":
            self.content = normalize_markdown(new_content)
        else:
            self.content = new_content
        # Re-render the widget
        self.remove_children()
        self.mount(*self.compose())


class StatusWidget(Static):
    """Fixed 3-line status area that shows recent events."""

    def __init__(self, **kwargs):
        """Initialize status widget."""
        super().__init__("", **kwargs)
        self.events = []  # Keep last 3 events

    def add_event(self, text: str):
        """Add an event to the status display.

        Args:
            text: Event text to display
        """
        self.events.append(text)
        # Keep only last 3 events
        if len(self.events) > 3:
            self.events.pop(0)
        self.update_display()

    def update_display(self):
        """Update the displayed content."""
        # Render as Text with proper styling
        content = "\n".join(self.events) if self.events else ""
        # Use from_markup to parse Rich markup tags like [bold]
        self.update(Text.from_markup(content))

    def clear_events(self):
        """Clear all events."""
        self.events = []
        self.update_display()


class ChatHistory(VerticalScroll):
    """Scrollable chat history container."""

    def __init__(self, **kwargs):
        """Initialize chat history."""
        super().__init__(**kwargs)
        self.can_focus = False

    def add_message(
        self,
        content: str,
        role: str = "user",
        is_markdown: bool = True,
    ):
        """Add a message to the chat history.

        Args:
            content: Message content
            role: Message role
            is_markdown: Whether to render as markdown
        """
        message = MessageWidget(content, role, is_markdown)
        self.mount(message)
        # Auto-scroll to bottom
        self.scroll_end(animate=False)


class CustomTextArea(TextArea):
    """Custom TextArea that handles Enter for submission and allows multiline input."""

    class Submitted(Message):
        """Message sent when the text area is submitted with Enter."""

        def __init__(self, text_area: "CustomTextArea") -> None:
            """Initialize submitted message.

            Args:
                text_area: The text area that was submitted
            """
            self.text_area = text_area
            super().__init__()

    # Override bindings to remove default Enter behavior
    BINDINGS = []

    def action_submit(self) -> None:
        """Submit the text area content."""
        self.post_message(self.Submitted(self))

    def _on_key(self, event: events.Key) -> None:
        """Internal key handler - intercepts before default TextArea processing."""
        # Check if we're in approval mode - if so, handle approval keys directly
        app = self.app
        if isinstance(app, CDDAgentTUI) and app._approval_pending:
            # When approval is pending, intercept keys and call app actions directly
            event.prevent_default()
            event.stop()

            if event.key == "enter":
                app.action_approval_confirm()
                return
            elif event.key in ("1", "a"):
                app.action_approve_allow()
                return
            elif event.key in ("2", "d"):
                app.action_approve_deny()
                return
            elif event.key in ("3", "s"):
                app.action_approve_session()
                return
            elif event.key == "left" or event.key == "shift+tab":
                app.action_approval_navigate_left()
                return
            elif event.key == "right" or event.key == "tab":
                app.action_approval_navigate_right()
                return

        # Debug: Log key presses that contain 'enter' to help diagnose Shift+Enter
        if "enter" in event.key or "return" in event.key:
            self.log(f"Key received: {event.key!r}, aliases: {event.aliases}")

        # Check for Enter key (without modifiers)
        if event.key == "enter":
            # Plain Enter - submit the message
            event.prevent_default()
            event.stop()
            self.action_submit()
            return

        # Ctrl+J or Shift+Enter - insert newline
        if event.key in ("ctrl+j", "shift+enter"):
            event.prevent_default()
            event.stop()
            # Insert newline using TextArea's replace method
            self.replace("\n", self.selection.end, self.selection.end)
            return

        # Shift+Tab - Toggle execution mode (Claude Code style)
        if event.key == "shift+tab":
            event.prevent_default()
            event.stop()
            app.action_toggle_execution_mode()
            return

        # Background process shortcuts (only when not in approval mode)
        if not (isinstance(app, CDDAgentTUI) and app._approval_pending):
            # Ctrl+B - Show background processes
            if event.key == "ctrl+b":
                event.prevent_default()
                event.stop()
                app.action_show_background_processes()
                return
            
            # Ctrl+I - Interrupt background processes
            if event.key == "ctrl+i":
                event.prevent_default()
                event.stop()
                app.action_interrupt_background_processes()
                return
            
            # Ctrl+O - Show output of last background process
            if event.key == "ctrl+o":
                event.prevent_default()
                event.stop()
                # Find the most recent background process and show its output
                processes = app.background_executor.list_all_processes()
                if processes:
                    # Get the most recent process (sorted by start time)
                    latest_process = max(processes, key=lambda p: p.start_time or 0)
                    from .tools import get_background_output
                    output = get_background_output(latest_process.process_id, lines=20)
                    
                    chat_history = app.query_one("#chat-history", ChatHistory)
                    chat_history.add_message(
                        f"📄 **Output from {latest_process.process_id[:12]}...**\n\n{output}",
                        role="assistant",
                        is_markdown=True,
                    )
                    chat_history.scroll_end(animate=False)
                else:
                    app._add_background_status_message("ℹ No background processes found")
                return

        # For all other keys, let TextArea handle them normally
        super()._on_key(event)


class ApprovalDialog(ModalScreen[bool]):
    """Modal dialog for tool execution approval.

    Shows tool name, arguments, risk level, and approval buttons.
    Returns True if approved, False if denied.
    """

    CSS = """
    ApprovalDialog {
        align: center middle;
        background: $background 60%;
    }

    #dialog-container {
        width: 70;
        height: auto;
        max-height: 25;
        border: round #d4a574;
        background: $background;
        padding: 1 2;
    }

    #dialog-title {
        text-align: left;
        text-style: bold;
        color: #d4a574;
        padding: 0 0 1 0;
    }

    #tool-info {
        height: auto;
        padding: 0 0 1 0;
        color: $text;
    }

    #warning-box {
        background: $error 20%;
        color: $error;
        padding: 0 1;
        margin: 1 0;
        border: round $error;
    }

    #button-container {
        height: auto;
        align: center middle;
        padding: 1 0 0 0;
    }

    Button {
        margin: 0 1;
        min-width: 16;
        background: transparent;
        border: round $text-muted;
        color: $text;
    }

    Button:hover {
        background: $surface;
        border: round #d4a574;
    }

    Button:focus {
        background: $surface;
        border: round #d4a574;
        text-style: bold;
    }

    .safe { color: green; }
    .medium { color: yellow; }
    .high { color: red; }
    """

    def __init__(
        self,
        tool_name: str,
        args: dict,
        risk_level: RiskLevel,
        warning: Optional[str] = None,
    ):
        """Initialize approval dialog.

        Args:
            tool_name: Name of tool requesting approval
            args: Tool arguments
            risk_level: Risk classification
            warning: Optional warning message for dangerous operations
        """
        super().__init__()
        self.tool_name = tool_name
        self.args = args
        self.risk_level = risk_level
        self.warning = warning

    def compose(self) -> ComposeResult:
        """Compose dialog layout."""
        # Determine risk color
        risk_color = {
            RiskLevel.SAFE: "safe",
            RiskLevel.MEDIUM: "medium",
            RiskLevel.HIGH: "high",
        }[self.risk_level]

        # Format arguments for display
        args_text = "\n".join(
            f"  • {key}: {str(value)[:60]}" for key, value in self.args.items()
        )
        if not args_text:
            args_text = "  (no arguments)"

        with Vertical(id="dialog-container"):
            yield Label("🔐 Tool Approval Required", id="dialog-title")

            with Vertical(id="tool-info"):
                yield Label(f"Tool: [bold {risk_color}]{self.tool_name}[/]")
                yield Label(
                    f"Risk Level: [{risk_color}]{self.risk_level.value.upper()}[/]"
                )
                yield Label(f"Arguments:\n{args_text}")

            # Show warning if dangerous
            if self.warning:
                yield Label(
                    f"⚠️  WARNING: {self.warning}",
                    id="warning-box",
                )

            with Horizontal(id="button-container"):
                yield Button("[1] Allow", id="allow")
                yield Button("[2] Deny", id="deny")
                yield Button("[3] Session", id="allow-session")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "allow":
            self.dismiss(True)
        elif event.button.id == "deny":
            self.dismiss(False)
        elif event.button.id == "allow-session":
            # For now, treat same as Allow
            # The session memory is handled by ApprovalManager
            self.dismiss(True)

    def on_key(self, event: events.Key) -> None:
        """Handle key press.

        ESC/2/d=Deny, 1/a=Allow, 3/s=Session
        """
        if event.key == "escape" or event.key == "2" or event.key == "d":
            # ESC, 2, or 'd' = Deny
            self.dismiss(False)
        elif event.key == "1" or event.key == "a":
            # 1 or 'a' = Allow
            self.dismiss(True)
        elif event.key == "3" or event.key == "s":
            # 3 or 's' = Allow for Session
            self.dismiss(True)


class CDDAgentTUI(App):
    """CDD Agent Textual TUI Application."""

    CSS = """
    Screen {
        background: transparent;
    }

    ChatHistory {
        height: 1fr;
        padding: 1 2 0 2;  /* Remove bottom padding */
        scrollbar-size: 0 0;  /* Hide scrollbar */
        background: transparent;
    }

    #status-widget {
        height: auto;
        min-height: 3;
        padding: 0 2;
        background: transparent;
    }

    #input-container {
        dock: bottom;
        height: auto;
        padding: 0 1;
        margin: 0 0 0 0;
        background: transparent;
    }

    #message-input {
        margin: 0 0 0 0;
        height: auto;
        max-height: 10;
        border: round #d4a574;
        background: transparent;
        scrollbar-size: 0 0;  /* Hide scrollbar */
    }

    #message-input:focus {
        border: round #d4a574;
    }

    #message-input > .text-area--cursor-line {
        background: transparent;
    }

    TextArea > .text-area--cursor-line {
        background: transparent !important;
    }

    #hint-text {
        color: $text-muted;
        text-align: center;
        padding: 0;
        height: auto;
    }

    MessageWidget {
        margin: 0 0 0 0;
    }

    MessageWidget:hover {
        background: $surface 20%;
    }

    MessageWidget.selected {
        background: $surface 40%;
    }

    /* Remove underlines from markdown headings and left-align them */
    Markdown MarkdownH1 {
        text-style: bold;
        text-align: left;
    }

    Markdown MarkdownH2 {
        text-style: bold;
        text-align: left;
    }

    Markdown MarkdownH3 {
        text-style: bold;
        text-align: left;
    }

    Markdown MarkdownH4 {
        text-style: bold;
        text-align: left;
    }

    Markdown MarkdownH5 {
        text-style: bold;
        text-align: left;
    }

    Markdown MarkdownH6 {
        text-style: bold;
        text-align: left;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+l", "clear", "Clear"),
        ("ctrl+n", "new", "New Chat"),
        ("f1", "help", "Help"),
        ("enter", "approval_confirm", ""),
        ("1", "approve_allow", ""),
        ("2", "approve_deny", ""),
        ("3", "approve_session", ""),
        ("a", "approve_allow", ""),
        ("d", "approve_deny", ""),
        ("s", "approve_session", ""),
        ("left", "approval_navigate_left", ""),
        ("right", "approval_navigate_right", ""),
        ("tab", "approval_navigate_right", ""),
        ("shift+tab", "approval_navigate_left", ""),
    ]

    def __init__(
        self,
        agent: Agent,
        provider: str,
        model: str,
        system_prompt: Optional[str] = None,
        execution_mode=None,
    ):
        """Initialize TUI app.

        Args:
            agent: Agent instance
            provider: Provider name
            model: Model name
            system_prompt: Optional system prompt
            execution_mode: ExecutionMode (NORMAL or PLAN)
        """
        from .utils.execution_state import ExecutionMode

        self.agent = agent
        self.provider = provider
        self.model = model
        self.system_prompt = system_prompt
        self.cwd = os.getcwd()
        self.execution_mode = execution_mode or ExecutionMode.NORMAL
        self._approval_result: Optional[bool] = None
        self._approval_event = threading.Event()
        self._approval_pending = False
        self._approval_selected_option = 1  # Default to Allow (1)

        # Background process support
        self.background_executor = get_background_executor()
        self.background_processes: Dict[str, dict] = {}  # Track active processes
        self.background_monitor_active = False
        self._background_stop_event = threading.Event()

        # Initialize chat session for slash commands and agent switching
        self.chat_session = ChatSession(
            agent=agent,
            provider_config=agent.provider_config,
            tool_registry=agent.tool_registry,
        )

        super().__init__(ansi_color=True)

    def request_approval(
        self, tool_name: str, args: dict, risk_level: RiskLevel
    ) -> bool:
        """Request approval for tool execution (synchronous method for callback).

        This method can be called from worker threads. It shows the approval
        request in the status widget and waits for keyboard input.

        Args:
            tool_name: Name of tool requesting approval
            args: Tool arguments
            risk_level: Risk classification

        Returns:
            True if approved, False if denied
        """
        # Check for dangerous patterns if it's a bash command
        warning = None
        if tool_name == "run_bash" and "command" in args:
            from .approval import ApprovalManager

            manager = ApprovalManager(mode=None, ui_callback=None)  # type: ignore
            is_dangerous, warn_msg = manager.is_dangerous_command(args["command"])
            if is_dangerous:
                warning = warn_msg

        # Reset the event
        self._approval_event.clear()
        self._approval_result = None
        self._approval_pending = True
        self._approval_selected_option = 1  # Reset to default (Allow)

        # Schedule the approval UI to be shown in status widget
        self.call_from_thread(
            self._show_approval_in_status, tool_name, args, risk_level, warning
        )

        # Wait for the result (with timeout)
        self._approval_event.wait(timeout=300)  # 5 minute timeout

        # Clear pending flag
        self._approval_pending = False

        # Clear the approval message from status widget
        self.call_from_thread(self._clear_approval_status)

        # Return the result (default to False if timeout)
        return self._approval_result if self._approval_result is not None else False

    def _clear_approval_status(self) -> None:
        """Clear approval message from status widget."""
        status_widget = self.query_one("#status-widget", StatusWidget)
        status_widget.clear_events()

    def _show_approval_in_status(
        self,
        tool_name: str,
        args: dict,
        risk_level: RiskLevel,
        warning: Optional[str],
    ) -> None:
        """Show approval request in status widget (runs on main thread).

        Args:
            tool_name: Name of tool requesting approval
            args: Tool arguments
            risk_level: Risk classification
            warning: Optional warning message
        """
        status_widget = self.query_one("#status-widget", StatusWidget)

        # CLEAR all previous events - approval message should be the only focus
        status_widget.clear_events()

        # Determine risk color
        risk_colors = {
            RiskLevel.SAFE: "green",
            RiskLevel.MEDIUM: "yellow",
            RiskLevel.HIGH: "red",
        }
        risk_color = risk_colors[risk_level]

        # Format arguments
        args_text = ", ".join(f"{key}={str(value)[:30]}" for key, value in args.items())
        if not args_text:
            args_text = "(no arguments)"

        # Build approval message - make it prominent and action-oriented
        msg = "[bold #d4a574]⚠️  ACTION REQUIRED ⚠️[/bold #d4a574]"
        msg += f"\n   Tool: [bold {risk_color}]{tool_name}[/] ({args_text})"

        if warning:
            msg += f"\n   [bold red]⚠️  {warning}[/]"

        # Format options with visual selector showing current selection
        options = []
        option_data = [
            (1, "1", "Allow"),
            (2, "2", "Deny"),
            (3, "3", "Session"),
        ]

        for opt_num, key, label in option_data:
            if self._approval_selected_option == opt_num:
                # Selected option - show with arrow and bold
                options.append(f"[bold #d4a574]> [{key}] {label}[/bold #d4a574]")
            else:
                # Unselected option - dimmed
                options.append(f"  [dim][{key}] {label}[/dim]")

        msg += "\n   " + "  ".join(options)

        status_widget.add_event(msg)

    def compose(self) -> ComposeResult:
        """Compose the TUI layout."""
        # Chat history (scrollable)
        yield ChatHistory(id="chat-history")

        # Status widget (3-line scrolling event area)
        yield StatusWidget(id="status-widget")

        # Input container at bottom
        with Container(id="input-container"):
            yield CustomTextArea(
                id="message-input",
            )

            # Mode indicator bar (replaces hints)
            from .utils.execution_state import ExecutionMode

            if self.execution_mode == ExecutionMode.PLAN:
                mode_icon = self.execution_mode.get_icon()
                mode_text = f"{mode_icon} PLAN MODE (Read-Only) - Press Shift+Tab to switch to Normal Mode"
                mode_style = "#d4a574"  # Purple/gold for Plan Mode
            else:
                mode_icon = self.execution_mode.get_icon()
                mode_text = f"{mode_icon} NORMAL MODE - Press Shift+Tab to switch to Plan Mode"
                mode_style = "dim"  # Dim for Normal Mode

            yield Static(
                f"[{mode_style}]{mode_text}[/{mode_style}]",
                id="mode-indicator",
            )

    def on_mount(self) -> None:
        """Called when app is mounted."""
        from .utils.execution_state import ExecutionMode

        # Add welcome message to chat with terminal width
        chat_history = self.query_one("#chat-history", ChatHistory)
        terminal_width = self.size.width - 4  # Account for padding
        welcome_text = create_welcome_message(
            self.provider, self.model, self.cwd, terminal_width, self.execution_mode
        )
        chat_history.add_message(welcome_text, role="system", is_markdown=False)

        # Focus the input
        self.query_one("#message-input", CustomTextArea).focus()

        # Start background process monitoring
        self._start_background_monitoring()

    def _refresh_approval_display(self) -> None:
        """Refresh the approval display with current selection."""
        # This is called from main thread, so we can directly update
        # Re-call the show method with stored data would be complex,
        # so we'll just update the last event with new selector position
        status_widget = self.query_one("#status-widget", StatusWidget)
        if status_widget.events and self._approval_pending:
            # Extract the original message parts and rebuild with new selector
            # For now, just trigger a redraw by touching the events
            status_widget.update_display()

    # ============================================================================
# Background Process Management
# ============================================================================

    def _start_background_monitoring(self) -> None:
        """Start background process monitoring thread."""
        if self.background_monitor_active:
            return
        
        self.background_monitor_active = True
        self._background_stop_event.clear()
        
        # Start monitoring thread
        monitor_thread = threading.Thread(
            target=self._monitor_background_processes,
            daemon=True,
            name="BackgroundMonitor"
        )
        monitor_thread.start()
    
    def _monitor_background_processes(self) -> None:
        """Monitor background processes and update UI.
        
        This runs in a separate thread and monitors background processes
        for completion, output, and status changes.
        """
        while self.background_monitor_active and not self._background_stop_event.is_set():
            try:
                # Check all known processes
                processes_to_remove = []
                
                for process_id, process_info in self.background_processes.items():
                    process = self.background_executor.get_process(process_id)
                    
                    if process is None:
                        # Process no longer exists
                        processes_to_remove.append(process_id)
                        continue
                    
                    # Check if process status has changed
                    current_status = process.status.value
                    last_status = process_info.get('last_status')
                    
                    if current_status != last_status:
                        # Status changed, update UI
                        process_info['last_status'] = current_status
                        
                        if process.status.name == 'COMPLETED':
                            self._notify_process_completed(process_id, process)
                        elif process.status.name == 'FAILED':
                            self._notify_process_failed(process_id, process)
                        elif process.status.name == 'INTERRUPTED':
                            self._notify_process_interrupted(process_id, process)
                    
                    # Check for new output (only for running processes)
                    if process.is_running():
                        last_line_count = process_info.get('last_line_count', 0)
                        current_line_count = len(process.output_lines)
                        
                        if current_line_count > last_line_count:
                            # New output available
                            new_lines = process.output_lines[last_line_count:]
                            self._stream_process_output(process_id, process, new_lines)
                            process_info['last_line_count'] = current_line_count
                
                # Remove completed/failed processes from tracking after a delay
                for process_id in processes_to_remove:
                    del self.background_processes[process_id]
                
                # Sleep before next check
                time.sleep(0.5)  # Check every 500ms
                
            except Exception as e:
                # Log error but continue monitoring
                try:
                    self.call_from_thread(
                        self._add_background_status_message,
                        f"⚠ Background monitor error: {str(e)}"
                    )
                except:
                    pass  # Avoid crashing the monitor
                time.sleep(1.0)
    
    def _register_background_process(self, process_id: str, command: str) -> None:
        """Register a new background process for monitoring.
        
        Args:
            process_id: Background process ID
            command: Command being executed
        """
        self.background_processes[process_id] = {
            'command': command,
            'start_time': time.time(),
            'last_status': None,
            'last_line_count': 0,
            'message_widget': None  # Will store the message widget
        }
        
        # Show initial status
        self._add_background_status_message(
            f"🚀 Background process started: {process_id[:12]}..."
        )
    
    def _notify_process_completed(self, process_id: str, process) -> None:
        """Notify user that a process completed successfully."""
        runtime = process.get_runtime()
        lines = len(process.output_lines)
        
        self._add_background_status_message(
            f"✅ Background process completed: {process_id[:12]}... "
            f"(Runtime: {runtime:.1f}s, Output: {lines} lines)"
        )
    
    def _notify_process_failed(self, process_id: str, process) -> None:
        """Notify user that a process failed."""
        runtime = process.get_runtime()
        exit_code = process.exit_code or -1
        
        self._add_background_status_message(
            f"❌ Background process failed: {process_id[:12]}... "
            f"(Exit code: {exit_code}, Runtime: {runtime:.1f}s)"
        )
    
    def _notify_process_interrupted(self, process_id: str, process) -> None:
        """Notify user that a process was interrupted."""
        runtime = process.get_runtime()
        
        self._add_background_status_message(
            f"⏹ Background process interrupted: {process_id[:12]}... "
            f"(Runtime: {runtime:.1f}s)"
        )
    
    def _stream_process_output(self, process_id: str, process, new_lines: list) -> None:
        """Stream new output lines to the chat.
        
        Args:
            process_id: Background process ID
            process: BackgroundProcess instance
            new_lines: New output lines to stream
        """
        process_info = self.background_processes.get(process_id)
        if not process_info:
            return
        
        # Create or update the streaming message widget
        chat_history = self.query_one("#chat-history", ChatHistory)
        
        if process_info['message_widget'] is None:
            # Create new streaming message
            from rich.syntax import Syntax
            
            header = f"🔧 **Background Output: {process_id[:12]}...**\n"
            header += f"Command: `{process.command[:80]}{'...' if len(process.command) > 80 else ''}`\n\n"
            
            message_widget = MessageWidget(
                header,
                role="assistant",
                is_markdown=True,
            )
            process_info['message_widget'] = message_widget
            
            self.call_from_thread(chat_history.mount, message_widget)
            self.call_from_thread(chat_history.scroll_end, animate=False)
        
        # Append new output to the message
        if new_lines:
            current_content = process_info['message_widget'].content or ""
            new_output = "\n".join(new_lines)

            # Use code block formatting for output
            updated_content = current_content + f"\n```bash\n{new_output}\n```"

            self.call_from_thread(
                process_info['message_widget'].update_content,
                updated_content
            )
            self.call_from_thread(chat_history.scroll_end, animate=False)

            # Update last_line_count
            process_info['last_line_count'] = len(process.output_lines)
    
    def _add_background_status_message(self, message: str) -> None:
        """Add a background process status message to the chat.
        
        Args:
            message: Status message to display
        """
        chat_history = self.query_one("#chat-history", ChatHistory)
        self.call_from_thread(
            chat_history.add_message,
            message,
            role="system",
            is_markdown=False,
        )
    
    def _stop_background_monitoring(self) -> None:
        """Stop background process monitoring."""
        self.background_monitor_active = False
        self._background_stop_event.set()

# ============================================================================
# Approval System (Existing)
# ============================================================================

    def action_approval_navigate_left(self) -> None:
        """Navigate approval selector left."""
        if self._approval_pending:
            self._approval_selected_option -= 1
            if self._approval_selected_option < 1:
                self._approval_selected_option = 3  # Wrap to Session
            self._update_approval_selector()

    def action_approval_navigate_right(self) -> None:
        """Navigate approval selector right."""
        if self._approval_pending:
            self._approval_selected_option += 1
            if self._approval_selected_option > 3:
                self._approval_selected_option = 1  # Wrap to Allow
            self._update_approval_selector()

    def _update_approval_selector(self) -> None:
        """Update the approval display to show new selector position."""
        if not self._approval_pending:
            return

        status_widget = self.query_one("#status-widget", StatusWidget)
        if not status_widget.events:
            return

        # Rebuild the last event with new selector position
        # Get the message parts (first 2 or 3 lines are header/tool/warning)
        lines = status_widget.events[-1].split("\n") if status_widget.events else []

        if len(lines) >= 3:
            # Keep header and tool info, rebuild options line
            options = []
            option_data = [
                (1, "1", "Allow"),
                (2, "2", "Deny"),
                (3, "3", "Session"),
            ]

            for opt_num, key, label in option_data:
                if self._approval_selected_option == opt_num:
                    options.append(f"[bold #d4a574]> [{key}] {label}[/bold #d4a574]")
                else:
                    options.append(f"  [dim][{key}] {label}[/dim]")

            # Replace the last line (options) with updated version
            lines[-1] = "   " + "  ".join(options)

            # Update the event
            status_widget.events[-1] = "\n".join(lines)
            status_widget.update_display()

    def action_approval_confirm(self) -> None:
        """Action: Confirm currently selected approval option (Enter key)."""
        if self._approval_pending:
            # Confirm based on current selection
            if self._approval_selected_option == 1:  # Allow
                self._approval_result = True
            elif self._approval_selected_option == 2:  # Deny
                self._approval_result = False
            elif self._approval_selected_option == 3:  # Session
                self._approval_result = True
            self._approval_event.set()

    def action_approve_allow(self) -> None:
        """Action: Allow tool execution (directly confirm)."""
        if self._approval_pending:
            self._approval_selected_option = 1
            self._approval_result = True
            self._approval_event.set()

    def action_approve_deny(self) -> None:
        """Action: Deny tool execution (directly confirm)."""
        if self._approval_pending:
            self._approval_selected_option = 2
            self._approval_result = False
            self._approval_event.set()

    def action_approve_session(self) -> None:
        """Action: Allow tool execution for session (directly confirm)."""
        if self._approval_pending:
            self._approval_selected_option = 3
            self._approval_result = True
            self._approval_event.set()

    def on_custom_text_area_submitted(self, event: CustomTextArea.Submitted) -> None:
        """Handle when CustomTextArea submits (Enter pressed).

        Args:
            event: Submitted event from CustomTextArea
        """
        # This is triggered by CustomTextArea when Enter is pressed
        text_area = self.query_one("#message-input", CustomTextArea)
        message = text_area.text.strip()

        if not message:
            return

        # Clear input
        text_area.clear()

        # Handle slash commands
        if message.startswith("/"):
            self.handle_command(message)
            return

        # Add user message to chat
        chat_history = self.query_one("#chat-history", ChatHistory)
        chat_history.add_message(message, role="user", is_markdown=False)

        # Send to agent (in background)
        self.send_to_agent(message)

    def handle_command(self, command: str):
        """Handle slash commands.

        Args:
            command: Command string
        """
        import logging

        logger = logging.getLogger("cdd_agent.tui")
        logger.info(f"handle_command called with: {command}")

        cmd = command.strip().lower()
        chat_history = self.query_one("#chat-history", ChatHistory)

        # Check if it's a built-in TUI command
        if cmd == "/clear" or cmd == "/new":
            logger.debug("Handling built-in clear/new command")
            self.agent.clear_history()
            # Clear chat history widget
            chat_history.remove_children()
            chat_history.add_message(
                "✓ Conversation cleared. Starting fresh!",
                role="system",
                is_markdown=False,
            )

        elif cmd == "/quit":
            logger.debug("Handling quit command")
            self.exit()

        else:
            # Try to handle it with the chat session's slash command router
            # Use a worker to execute async command (Textual handles the event loop)
            logger.info(f"Routing command to slash command router: {command}")
            self.execute_slash_command_worker(command, chat_history)

    @work(exclusive=False, thread=True)
    def execute_slash_command_worker(self, command: str, chat_history):
        """Execute slash command in a worker thread.

        Args:
            command: Slash command to execute
            chat_history: Chat history widget to display result
        """
        import asyncio
        import logging

        logger = logging.getLogger("cdd_agent.tui")
        logger.info(f"Executing slash command: {command}")

        # Create async function to execute command
        async def execute_command():
            try:
                logger.debug(f"Calling router.execute for: {command}")
                # Execute the command through the router
                result = await self.chat_session.slash_router.execute(command)
                logger.debug(f"Router returned result: {result[:100] if result else None}...")
                return result, None
            except Exception as e:
                logger.error(f"Error executing command: {e}", exc_info=True)
                return None, str(e)

        # Run in new event loop (since we're in a worker thread)
        try:
            logger.debug("Creating new event loop")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result, error = loop.run_until_complete(execute_command())
            loop.close()
            logger.debug(f"Event loop completed. Result: {bool(result)}, Error: {bool(error)}")

            if error:
                logger.error(f"Command failed with error: {error}")
                # Display error on the main thread
                self.call_from_thread(
                    chat_history.add_message,
                    f"❌ Error: {error}",
                    role="error",
                    is_markdown=False,
                )
            elif result:
                logger.info(f"Command succeeded, displaying result")
                # Display the result on the main thread
                self.call_from_thread(
                    chat_history.add_message,
                    result,
                    role="system",
                    is_markdown=True,
                )
            else:
                logger.warning("Command returned no result and no error")
        except Exception as e:
            logger.error(f"Unexpected error in worker: {e}", exc_info=True)
            self.call_from_thread(
                chat_history.add_message,
                f"❌ Unexpected error: {str(e)}",
                role="error",
                is_markdown=False,
            )

    @work(exclusive=True, thread=True)
    def send_to_agent(self, message: str):
        """Send message to agent and stream response.

        Args:
            message: User message
        """
        chat_history = self.query_one("#chat-history", ChatHistory)
        status_widget = self.query_one("#status-widget", StatusWidget)

        # Start streaming
        response_text = []
        animation_active = False
        stop_animation = False
        streaming_message = None  # Track the live message widget

        def animate_status():
            """Animate thinking dots in status widget."""
            import time

            nonlocal stop_animation
            dots = 0
            while not stop_animation:
                # CRITICAL: Stop animation if approval is pending
                if self._approval_pending:
                    stop_animation = True
                    break

                dots = (dots % 3) + 1
                dot_str = "." * dots
                # Update the first line with animated dots
                if status_widget.events:
                    status_widget.events[0] = f"💭 Thinking{dot_str}"
                    self.call_from_thread(status_widget.update_display)
                time.sleep(1.0)  # Slower animation (1 second per dot)

        try:
            for event in self.agent.stream(message, system_prompt=self.system_prompt):
                event_type = event.get("type")

                if event_type == "thinking":
                    thinking_msg = event.get("content", "Thinking")
                    self.call_from_thread(
                        status_widget.add_event, f"💭 {thinking_msg}."
                    )

                    # Start animation
                    if not animation_active:
                        from threading import Thread

                        stop_animation = False
                        thread = Thread(target=animate_status, daemon=True)
                        thread.start()
                        animation_active = True

                elif event_type == "tool_use":
                    tool_name = event.get("name", "unknown")
                    
                    # Check if this is a background tool
                    if tool_name in ["run_bash_background"]:
                        tool_args = event.get("input", {})
                        command = tool_args.get("command", "unknown")
                        self.call_from_thread(
                            status_widget.add_event, 
                            f"🚀 Starting background tool: {tool_name}"
                        )
                    else:
                        self.call_from_thread(
                            status_widget.add_event, f"🔧 Using tool: {tool_name}"
                        )

                elif event_type == "tool_result":
                    tool_name = event.get("name", "unknown")
                    is_error = event.get("is_error", False)
                    
                    # Handle background tool results
                    if tool_name == "run_bash_background":
                        result = event.get("content", "")
                        
                        # Extract process ID from the result
                        import re
                        match = re.search(r'Background process started: (\w+-\w+-\w+-\w+-\w+)', result)
                        if match:
                            process_id = match.group(1)
                            tool_args = event.get("input", {})
                            command = tool_args.get("command", "unknown")
                            
                            # Register process for monitoring
                            self.call_from_thread(
                                self._register_background_process,
                                process_id,
                                command
                            )
                        else:
                            # Error starting background process
                            self.call_from_thread(
                                status_widget.add_event,
                                f"✗ Failed to start background process"
                            )
                    else:
                        # Regular tool result
                        if is_error:
                            msg = f"✗ Error in {tool_name}"
                        else:
                            msg = f"✓ {tool_name} completed"
                        
                        self.call_from_thread(status_widget.add_event, msg)

                elif event_type == "text":
                    # Stop animation and clear status widget on first text chunk
                    if not streaming_message:
                        stop_animation = True
                        animation_active = False
                        self.call_from_thread(status_widget.clear_events)

                        # Create streaming message widget
                        streaming_message = MessageWidget(
                            "",
                            role="assistant",
                            is_markdown=True,
                        )
                        self.call_from_thread(chat_history.mount, streaming_message)
                        self.call_from_thread(chat_history.scroll_end, animate=False)

                    # Accumulate text
                    chunk = event.get("content")
                    if chunk is not None:  # Only process if chunk is not None
                        response_text.append(chunk)

                        # Update the message widget with accumulated text
                        accumulated = "".join(response_text)
                        self.call_from_thread(streaming_message.update_content, accumulated)
                        self.call_from_thread(chat_history.scroll_end, animate=False)

                elif event_type == "error":
                    # Stop animation
                    stop_animation = True
                    animation_active = False
                    self.call_from_thread(status_widget.clear_events)

                    error_msg = event.get("content", "Unknown error")
                    self.call_from_thread(
                        chat_history.add_message,
                        f"⚠ {error_msg}",
                        role="error",
                        is_markdown=False,
                    )

            # Clear status widget
            stop_animation = True
            self.call_from_thread(status_widget.clear_events)

            # If no streaming message was created but we have text, add it
            if response_text and not streaming_message:
                final_response = "".join(response_text)
                self.call_from_thread(
                    chat_history.add_message,
                    final_response,
                    role="assistant",
                    is_markdown=True,
                )

        except Exception as e:
            # Stop animation and clear status
            stop_animation = True
            self.call_from_thread(status_widget.clear_events)

            self.call_from_thread(
                chat_history.add_message,
                f"Error: {str(e)}",
                role="error",
                is_markdown=False,
            )

    def action_clear(self) -> None:
        """Clear conversation (Ctrl+L)."""
        self.handle_command("/clear")

    def action_new(self) -> None:
        """New conversation (Ctrl+N)."""
        self.handle_command("/new")

    def action_toggle_execution_mode(self) -> None:
        """Toggle execution mode between NORMAL and PLAN (Ctrl+M)."""
        from .utils.execution_state import ExecutionMode
        from rich.text import Text

        # Toggle mode
        if self.execution_mode == ExecutionMode.NORMAL:
            self.execution_mode = ExecutionMode.PLAN
        else:
            self.execution_mode = ExecutionMode.NORMAL

        # Update agent's mode
        self.agent.set_execution_mode(self.execution_mode)

        # Update mode indicator bar
        mode_indicator = self.query_one("#mode-indicator", Static)
        mode_icon = self.execution_mode.get_icon()

        if self.execution_mode == ExecutionMode.PLAN:
            mode_text = f"{mode_icon} PLAN MODE (Read-Only) - Press Shift+Tab to switch to Normal Mode"
            mode_indicator.update(Text.from_markup(f"[#d4a574]{mode_text}[/#d4a574]"))
        else:
            mode_text = f"{mode_icon} NORMAL MODE - Press Shift+Tab to switch to Plan Mode"
            mode_indicator.update(Text.from_markup(f"[dim]{mode_text}[/dim]"))

        # Show brief confirmation in status widget
        status_widget = self.query_one("#status-widget", StatusWidget)
        mode_name = self.execution_mode.get_display_name()

        status_widget.add_event(
            f"[#d4a574]✓ Switched to {mode_name} Mode[/#d4a574]"
        )

    def action_show_background_processes(self) -> None:
        """Show background processes (Ctrl+B)."""
        processes = self.background_executor.list_all_processes()
        
        if not processes:
            self._add_background_status_message("📋 No background processes running")
            return
        
        # Format process list
        status_lines = [f"📋 Background Processes ({len(processes)} total):"]
        
        for process in processes:
            runtime = process.get_runtime()
            
            # Status emoji
            if process.is_running():
                status_emoji = "🟢"
            elif process.status.value == "completed":
                status_emoji = "✅"
            elif process.status.value == "failed":
                status_emoji = "❌"
            elif process.status.value == "interrupted":
                status_emoji = "⏹"
            else:
                status_emoji = "❓"
            
            status_lines.append(
                f"{status_emoji} {process.process_id[:12]}... "
                f"({process.status.value}) - {runtime:.1f}s - "
                f"{len(process.output_lines)} lines"
            )
            status_lines.append(f"   Command: {process.command[:60]}{'...' if len(process.command) > 60 else ''}")
        
        # Add management hints
        running_count = sum(1 for p in processes if p.is_running())
        if running_count > 0:
            status_lines.append(f"\n💡 {running_count} process(es) still running")
            status_lines.append("💡 Use Ctrl+I to interrupt, Ctrl+O to show output")
        
        # Display as a system message
        chat_history = self.query_one("#chat-history", ChatHistory)
        chat_history.add_message(
            "\n".join(status_lines),
            role="system",
            is_markdown=False,
        )
        chat_history.scroll_end(animate=False)
    
    def action_interrupt_background_processes(self) -> None:
        """Interrupt all running background processes (Ctrl+I)."""
        running_processes = self.background_executor.list_active_processes()
        
        if not running_processes:
            self._add_background_status_message("ℹ No running background processes to interrupt")
            return
        
        # Interrupt all running processes
        interrupted_count = 0
        for process in running_processes:
            if self.background_executor.interrupt_process(process.process_id):
                interrupted_count += 1
        
        self._add_background_status_message(
            f"⏹ Sent interrupt signal to {interrupted_count} background process(es)"
        )
    
    def action_help(self) -> None:
        """Show help (F1)."""
        self.handle_command("/help")
    
    def on_exit(self) -> None:
        """Called when the app is about to exit."""
        # Stop background monitoring
        self._stop_background_monitoring()
        
        # Interrupt all running background processes
        running_processes = self.background_executor.list_active_processes()
        if running_processes:
            for process in running_processes:
                self.background_executor.interrupt_process(process.process_id)
            
            # Give them a moment to clean up
            import time
            time.sleep(0.5)
        
        # Call parent exit method
        super().on_exit()


def run_tui(
    agent: Agent,
    provider: str,
    model: str,
    system_prompt: Optional[str] = None,
    approval_mode=None,
    execution_mode=None,
):
    """Run the Textual TUI.

    Args:
        agent: Agent instance
        provider: Provider name
        model: Model name
        system_prompt: Optional system prompt
        approval_mode: Optional approval mode (if set, creates ApprovalManager)
        execution_mode: Optional execution mode (NORMAL or PLAN)
    """
    from .utils.execution_state import ExecutionMode

    # Use agent's execution mode if not provided
    if execution_mode is None:
        execution_mode = agent.execution_mode

    app = CDDAgentTUI(agent, provider, model, system_prompt, execution_mode)

    # If approval mode is set, create ApprovalManager and wire it to agent
    if approval_mode:
        from .approval import ApprovalManager

        agent.approval_manager = ApprovalManager(
            mode=approval_mode, ui_callback=app.request_approval
        )

    app.run()
