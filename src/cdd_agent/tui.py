"""Textual TUI for CDD Agent - Beautiful split-pane chat interface."""

import os
from typing import Optional

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.widgets import Input, Static, TextArea

from . import __version__
from .agent import Agent

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


def create_welcome_message(provider: str, model: str, cwd: str, width: int = 80) -> str:
    """Create centered welcome message text.

    Args:
        provider: Provider name
        model: Model name
        cwd: Current working directory
        width: Terminal width for centering

    Returns:
        Formatted welcome message
    """
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
        "",
    ]

    # Center align all lines based on terminal width
    return "\n".join(line.center(width) for line in lines)


class MessageWidget(Static):
    """A single message in the chat."""

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

    def compose(self) -> ComposeResult:
        """Compose the message."""
        # Choose style and format based on role
        if self.role == "system":
            # System messages (like welcome) - no border, just yellow text
            text = Text(self.content, style=BRAND_COLOR)
            yield Static(text)
        else:
            # Regular messages with panels
            if self.role == "user":
                border_style = USER_COLOR
                title = "Human"
                title_align = "right"
            elif self.role == "assistant":
                border_style = ASSISTANT_COLOR
                title = "Robot"
                title_align = "left"
            elif self.role == "tool":
                border_style = TOOL_COLOR
                title = "🔧 Tool"
                title_align = "left"
            elif self.role == "error":
                border_style = ERROR_COLOR
                title = "⚠ Error"
                title_align = "left"
            else:
                border_style = DIM_COLOR
                title = "System"
                title_align = "left"

            # Render content
            if self.is_markdown and self.role == "assistant":
                content_widget = Markdown(self.content)
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
        self.update(Text(content, style=BRAND_COLOR))

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
    """Custom TextArea that handles Enter for submission and Ctrl+J for newlines."""

    class Submitted(Message):
        """Message sent when the text area is submitted with Enter."""

        def __init__(self, text_area: "CustomTextArea") -> None:
            """Initialize submitted message.

            Args:
                text_area: The text area that was submitted
            """
            self.text_area = text_area
            super().__init__()

    def on_key(self, event: events.Key) -> None:
        """Handle key events before TextArea processes them.

        Args:
            event: Key event
        """
        # Intercept Ctrl+J for newline FIRST (before checking Enter)
        if event.key == "j" and event.ctrl:
            self.insert_text_at_selection("\n")
            event.prevent_default()
            event.stop()
            return

        # Intercept Enter to prevent newline and submit
        if event.key == "enter":
            # Send custom submit message to parent
            self.post_message(self.Submitted(self))
            event.prevent_default()
            event.stop()
            return

        # Let TextArea handle all other keys
        # Don't call super().on_key() - it will bubble to parent
        # TextArea handles keys internally


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
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+l", "clear", "Clear"),
        ("ctrl+n", "new", "New Chat"),
        ("f1", "help", "Help"),
    ]

    def __init__(
        self,
        agent: Agent,
        provider: str,
        model: str,
        system_prompt: Optional[str] = None,
    ):
        """Initialize TUI app.

        Args:
            agent: Agent instance
            provider: Provider name
            model: Model name
            system_prompt: Optional system prompt
        """
        self.agent = agent
        self.provider = provider
        self.model = model
        self.system_prompt = system_prompt
        self.cwd = os.getcwd()
        super().__init__(ansi_color=True)

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
            yield Static(
                "Enter Send • Ctrl+J New line • Ctrl+C Quit • Ctrl+L Clear",
                id="hint-text",
            )

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Add welcome message to chat with terminal width
        chat_history = self.query_one("#chat-history", ChatHistory)
        terminal_width = self.size.width - 4  # Account for padding
        welcome_text = create_welcome_message(
            self.provider, self.model, self.cwd, terminal_width
        )
        chat_history.add_message(welcome_text, role="system", is_markdown=False)

        # Focus the input
        self.query_one("#message-input", CustomTextArea).focus()

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
        cmd = command.strip().lower()
        chat_history = self.query_one("#chat-history", ChatHistory)

        if cmd == "/help":
            help_text = """**Available Commands:**

- `/help` - Show this help
- `/clear` - Clear conversation history
- `/new` - Start new conversation
- `/quit` - Exit (or Ctrl+C)

**Keyboard Shortcuts:**

- `Enter` - Send message
- `Ctrl+L` - Clear chat
- `Ctrl+N` - New conversation
- `Ctrl+C` - Quit
- `F1` - Help
"""
            chat_history.add_message(help_text, role="system", is_markdown=True)

        elif cmd == "/clear" or cmd == "/new":
            self.agent.clear_history()
            # Clear chat history widget
            chat_history.remove_children()
            chat_history.add_message(
                "✓ Conversation cleared. Starting fresh!",
                role="system",
                is_markdown=False,
            )

        elif cmd == "/quit":
            self.exit()

        else:
            chat_history.add_message(
                f"Unknown command: {command}\nType /help for available commands.",
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
                        status_widget.add_event,
                        f"💭 {thinking_msg}."
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
                    self.call_from_thread(
                        status_widget.add_event,
                        f"🔧 Using tool: {tool_name}"
                    )

                elif event_type == "tool_result":
                    tool_name = event.get("name", "unknown")
                    is_error = event.get("is_error", False)

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
                    chunk = event.get("content", "")
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

    def action_help(self) -> None:
        """Show help (F1)."""
        self.handle_command("/help")


def run_tui(
    agent: Agent,
    provider: str,
    model: str,
    system_prompt: Optional[str] = None,
):
    """Run the Textual TUI.

    Args:
        agent: Agent instance
        provider: Provider name
        model: Model name
        system_prompt: Optional system prompt
    """
    app = CDDAgentTUI(agent, provider, model, system_prompt)
    app.run()
