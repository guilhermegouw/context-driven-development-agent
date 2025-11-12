"""CLI entry point for CDD Agent.

This module provides the command-line interface for:
- Authentication management
- Provider configuration
- Chat and agent interactions
"""

import os
from typing import TYPE_CHECKING

import click

# Safe version import with fallback for development mode
try:
    from . import __version__
except ImportError:
    # Fallback for development mode when package is not installed
    __version__ = "0.0.3-dev"

# Ultra-lazy imports for maximum startup performance
# This minimizes the import chain to essential components only
if TYPE_CHECKING:
    from .agent import Agent
    from .ui import StreamingUI

# Lazy console initialization - only create when first used
_console = None


def _get_console():
    """Lazy console initialization to avoid Rich import-time cost."""
    global _console
    if _console is None:
        from rich.console import Console

        _console = Console()
    return _console


def _get_logger():
    """Lazy logger initialization to avoid import-time performance hit."""
    from .logging import get_logger

    return get_logger("cli")


@click.group()
@click.version_option(version=__version__, prog_name="cdd-agent")
def cli():
    """CDD Agent - AI coding assistant with structured workflows.

    An LLM-agnostic terminal agent that helps you build software with
    structured specifications, plans, and implementations.
    """
    pass


@cli.command()
@click.argument("prompt", required=False)
@click.option(
    "--provider",
    default=None,
    help="Provider to use (defaults to default provider)",
)
@click.option(
    "--model",
    default="mid",
    help="Model tier to use (small/mid/big)",
    type=click.Choice(["small", "mid", "big"]),
)
@click.option(
    "--system",
    default=None,
    help="System prompt for context",
)
@click.option(
    "--no-stream",
    is_flag=True,
    help="Disable streaming (single-shot mode)",
)
@click.option(
    "--simple",
    is_flag=True,
    help="Use simple streaming UI instead of full TUI",
)
@click.option(
    "--approval",
    default=None,
    help="Tool approval mode (paranoid/balanced/trusting)",
    type=click.Choice(["paranoid", "balanced", "trusting"]),
)
@click.option(
    "--no-context",
    is_flag=True,
    help="Disable hierarchical context loading (CLAUDE.md, CDD.md)",
)
@click.option(
    "--plan",
    is_flag=True,
    help="Start in Plan Mode (read-only exploration mode)",
)
def chat(
    prompt: str,
    provider: str,
    model: str,
    system: str,
    no_stream: bool,
    simple: bool,
    approval: str,
    no_context: bool,
    plan: bool,
):
    """Interactive chat with AI agent.

    The agent can use tools to read files, write files, and execute commands.

    By default, opens a beautiful split-pane TUI interface with automatic context
    loading from CLAUDE.md/CDD.md files. Use --simple for a simpler streaming
    interface, or --no-stream for single-shot mode.

    Examples:
        cdd-agent chat                      # Full TUI mode (default)
        cdd-agent chat --simple             # Simple streaming UI
        cdd-agent chat "Quick question"     # Single message in TUI
        cdd-agent chat --model small        # Use smaller model
        cdd-agent chat --approval paranoid  # Ask for all tool approvals
        cdd-agent chat --no-context         # Disable context loading
        cdd-agent chat --no-stream          # Disable streaming
    """
    # Lazy imports - only load when chat command is used
    from .config import ConfigManager
    from .tools import create_default_registry

    config = ConfigManager()

    # Check if configured
    if not config.exists():
        from rich.panel import Panel

        _get_console().print(
            Panel.fit(
                "[bold red]No configuration found![/bold red]\n\n"
                "Please run [cyan]cdd-agent auth setup[/cyan] first to "
                "configure your LLM provider.",
                border_style="red",
                title="❌ Error",
            )
        )
        return

    try:
        # Lazy imports - only load when chat command is actually executed
        from .agent import Agent
        from .utils.execution_state import ExecutionMode

        # Load provider config
        provider_config = config.get_effective_config(provider)

        # Get effective approval mode (CLI flag > env var > settings > default)
        approval_mode = config.get_effective_approval_mode(approval)
        # TODO: Pass approval_mode to ApprovalManager when integrating Phase 2
        _ = approval_mode  # noqa: F841 - Will be used in Phase 2 integration

        # Get effective execution mode (CLI flag > env var > settings > default)
        execution_mode_str = config.get_effective_execution_mode(plan_flag=plan)
        execution_mode = ExecutionMode.PLAN if execution_mode_str == "plan" else ExecutionMode.NORMAL

        # Create tool registry with default tools
        tool_registry = create_default_registry()

        # Create agent
        agent = Agent(
            provider_config=provider_config,
            tool_registry=tool_registry,
            model_tier=model,
            max_iterations=100,  # Increased to 100 for complex tasks
            enable_context=not no_context,  # Invert flag (--no-context disables)
            execution_mode=execution_mode,
        )

        # Decide which UI to use
        if simple or no_stream:
            # Lazy import - only load StreamingUI when simple mode is used
            from .ui import StreamingUI

            # Use simple streaming UI
            ui = StreamingUI(_get_console())

            # If approval mode is set, create ApprovalManager for simple mode
            if approval_mode:
                from .approval import ApprovalManager

                agent.approval_manager = ApprovalManager(
                    mode=approval_mode, ui_callback=ui.request_approval
                )

            # Show welcome screen
            ui.show_welcome(
                provider=provider or "default",
                model=provider_config.get_model(model),
                cwd=os.getcwd(),
            )

            # If prompt provided, run single message and exit
            if prompt:
                _run_single_message(agent, ui, prompt, system, no_stream)
                return

            # Interactive mode
            _run_interactive_chat(agent, ui, system, no_stream)

        else:
            # Lazy import - only load TUI when actually needed
            from .tui import run_tui

            # Use full TUI (default)
            run_tui(
                agent=agent,
                provider=provider or "default",
                model=provider_config.get_model(model),
                system_prompt=system,
                approval_mode=approval_mode,
                execution_mode=execution_mode,
            )

    except KeyboardInterrupt:
        _get_logger().info("Chat session interrupted by user (Ctrl+C)")
        _get_console().print("\n[dim]Goodbye![/dim]")
    except Exception as e:
        _get_logger().error(f"Chat command failed: {e}", exc_info=True)
        from rich.panel import Panel

        _get_console().print(
            Panel.fit(
                f"[bold red]Error:[/bold red]\n\n{str(e)}",
                border_style="red",
                title="❌ Error",
            )
        )
        import traceback

        _get_console().print(f"\n[dim]{traceback.format_exc()}[/dim]")
        _get_console().print("\n[dim]💡 Check logs: cdd-agent logs show[/dim]")


def _run_single_message(
    agent, ui: "StreamingUI", prompt: str, system: str, no_stream: bool
):
    """Run a single message (non-interactive).

    Args:
        agent: Agent instance
        ui: UI instance
        prompt: User message
        system: System prompt
        no_stream: Whether to disable streaming
    """
    _get_console().print(f"[bold]>[/bold] {prompt}\n")

    if no_stream:
        # Non-streaming mode (original behavior)
        from rich.markdown import Markdown

        response = agent.run(prompt, system_prompt=system)
        _get_console().print(Markdown(response))
    else:
        # Streaming mode
        event_stream = agent.stream(prompt, system_prompt=system)
        ui.stream_response(event_stream)

    _get_console().print("\n[green]✓ Done![/green]")


def _run_interactive_chat(agent, ui: "StreamingUI", system: str, no_stream: bool):
    """Run interactive chat loop with session management.

    Args:
        agent: Agent instance
        ui: UI instance
        system: System prompt
        no_stream: Whether to disable streaming
    """
    import asyncio

    from rich.markdown import Markdown

    from .session import ChatSession

    # Create chat session
    session = ChatSession(
        agent=agent,
        provider_config=agent.provider_config,
        tool_registry=agent.tool_registry,
    )

    _get_console().print(
        "[dim]Type /help for commands, 'exit' to leave agent mode, "
        "Ctrl+D to quit[/dim]\n"
    )

    while True:
        try:
            # Show prompt (indicate agent mode if active)
            if session.is_in_agent_mode():
                agent_name = session.get_current_agent_name()
                ui.show_prompt(f"[{agent_name}]>")
            else:
                ui.show_prompt(">")

            # Get user input
            user_input = input()

            # Handle empty input
            if not user_input.strip():
                continue

            # Process through session
            response, should_exit = asyncio.run(session.process_input(user_input))

            # Handle session-level exit (not used yet)
            if should_exit:
                break

            # If response is None, it's general chat - use existing agent
            if response is None:
                _get_console().print()  # Blank line before response

                if no_stream:
                    response = agent.run(user_input, system_prompt=system)
                    _get_console().print(Markdown(response))
                else:
                    event_stream = agent.stream(user_input, system_prompt=system)
                    ui.stream_response(event_stream)

                _get_console().print()  # Blank line after response
            else:
                # Slash command or agent response
                _get_console().print()
                _get_console().print(Markdown(response))
                _get_console().print()

        except KeyboardInterrupt:
            if session.is_in_agent_mode():
                _get_console().print(
                    "\n[dim]Use 'exit' to leave agent mode or Ctrl+D to quit[/dim]"
                )
            else:
                _get_console().print("\n[dim]Use /quit to exit or Ctrl+D[/dim]")
            continue
        except EOFError:
            break


def _handle_slash_command(command: str, agent: "Agent", ui: "StreamingUI") -> bool:
    """Handle slash commands.

    Integrates both built-in commands (quit, clear, etc.) and CDD commands
    (init, new) via the slash command router.

    Args:
        command: Command string (e.g., "/help", "/init", "/new ticket feature Auth")
        agent: Agent instance
        ui: UI instance

    Returns:
        True if should exit, False otherwise
    """
    import asyncio

    from rich.markdown import Markdown

    from .slash_commands import get_router, setup_commands

    cmd = command.strip().lower()

    # Built-in session commands (have priority over CDD commands)
    if cmd == "/quit" or cmd == "/exit":
        _get_console().print("[dim]Goodbye![/dim]")
        return True

    elif cmd == "/clear":
        agent.clear_history()
        _get_console().print("[green]✓ Conversation history cleared[/green]")
        return False

    elif cmd == "/compact":
        # Compact conversation history (like Claude Code)
        if agent.compact():
            _get_console().print("[green]✓ Conversation compacted[/green]")
        return False

    elif cmd.startswith("/save"):
        # Save conversation to file with timestamp
        import datetime

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conversation_{timestamp}.md"

        # Simple conversation export (basic implementation)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# CDD Agent Conversation - {datetime.datetime.now()}\n\n")
            f.write("## History\n")
            f.write("(Full conversation history export coming soon)\n")

        _get_console().print(f"[green]✓ Conversation saved to {filename}[/green]")
        return False

    elif cmd == "/new" and " " not in cmd:
        # /new without arguments = start new conversation
        agent.clear_history()
        _get_console().print("[green]✓ Starting new conversation[/green]")
        return False

    # Try CDD slash command router
    else:
        # Initialize router on first use
        router = get_router()
        if not router._commands:
            setup_commands(router)

        # Check if it's a CDD command
        if router.is_slash_command(command):
            try:
                # Execute command (async)
                result = asyncio.run(router.execute(command))

                # Display result with markdown formatting
                _get_console().print()
                _get_console().print(Markdown(result))
                _get_console().print()

                return False

            except Exception as e:
                _get_console().print(f"[red]Error executing command: {e}[/red]")
                return False
        else:
            # Unknown command
            _get_console().print(f"[red]Unknown command: {command}[/red]")
            _get_console().print("[dim]Type /help for available commands[/dim]")
            return False


@cli.group()
def auth():
    """Manage authentication and provider configuration."""
    pass


@auth.command(name="setup")
def auth_setup():
    """Interactive authentication setup.

    Guides you through configuring your LLM provider (Anthropic, OpenAI, or custom).
    Creates ~/.cdd-agent/settings.json with your credentials.

    Example:
        cdd-agent auth setup
    """
    # Lazy imports - only load when auth setup is used
    from .auth import AuthManager
    from .config import ConfigManager

    config = ConfigManager()
    auth_manager = AuthManager(config)
    auth_manager.interactive_setup()


@auth.command(name="oauth")
@click.option(
    "--provider",
    default="anthropic",
    help="Provider to configure (default: anthropic)",
)
def auth_oauth(provider: str):
    """Set up OAuth authentication for Claude Pro/Max plans.

    Authenticate with your Claude Pro or Max subscription for zero-cost API access.
    This opens a browser for OAuth authorization and stores refresh tokens that
    automatically renew.

    Two modes available:
    - "max": OAuth tokens (auto-refresh, zero-cost for Pro/Max subscribers)
    - "api-key": Create permanent API key via OAuth

    Example:
        cdd-agent auth oauth
        cdd-agent auth oauth --provider anthropic
    """
    # Lazy imports - only load when OAuth setup is used
    from .auth import AuthManager
    from .config import ConfigManager

    config = ConfigManager()
    auth_manager = AuthManager(config)
    auth_manager.setup_oauth_interactive(provider)


@auth.command(name="status")
def auth_status():
    """Show current authentication status.

    Displays configured providers, API key status, and model mappings.

    Example:
        cdd-agent auth status
    """
    # Lazy imports - only load when auth status is used
    from .auth import AuthManager
    from .config import ConfigManager

    config = ConfigManager()
    auth_manager = AuthManager(config)
    auth_manager.display_current_config()


@auth.command(name="set-default")
@click.argument("provider")
def set_default(provider: str):
    """Set default provider.

    Args:
        provider: Provider name (anthropic, openai, custom)

    Example:
        cdd-agent auth set-default openai
    """
    # Lazy imports - only load when set-default is used
    from .config import ConfigManager

    config = ConfigManager()

    if not config.exists():
        _get_console().print(
            "[red]No configuration found. Run 'cdd-agent auth setup' first.[/red]"
        )
        return

    settings = config.load()

    if provider not in settings.providers:
        _get_console().print(f"[red]Provider '{provider}' not found.[/red]")
        available = ", ".join(settings.providers.keys())
        _get_console().print(f"[yellow]Available providers: {available}[/yellow]")
        return

    settings.default_provider = provider
    config.save(settings)
    _get_console().print(f"[green]✓ Default provider set to: {provider}[/green]")


@auth.command(name="test")
@click.option(
    "--provider", default=None, help="Provider to test (defaults to default provider)"
)
def test_auth(provider: str):
    """Test authentication for a provider.

    Makes a minimal API call to validate credentials.

    Args:
        provider: Provider name (defaults to default provider)

    Example:
        cdd-agent auth test --provider anthropic
    """
    # Lazy imports - only load when auth test is used
    from .config import ConfigManager

    config = ConfigManager()

    if not config.exists():
        _get_console().print(
            "[red]No configuration found. Run 'cdd-agent auth setup' first.[/red]"
        )
        return

    try:
        provider_config = config.get_effective_config(provider)
        _get_console().print(
            f"[cyan]Testing {provider or 'default'} provider...[/cyan]"
        )

        # Try to import and test based on provider type
        api_key = provider_config.get_api_key()
        if not api_key:
            _get_console().print("[red]✗ No API key configured[/red]")
            return

        # Detect provider type
        if (
            "anthropic" in provider_config.base_url
            or provider_config.provider_type == "anthropic"
        ):
            success = _test_anthropic(provider_config)
        elif (
            "openai" in provider_config.base_url
            or provider_config.provider_type == "openai"
        ):
            success = _test_openai(provider_config)
        else:
            _get_console().print(
                "[yellow]⚠ Unknown provider type, cannot test automatically[/yellow]"
            )
            return

        if success:
            _get_console().print("[green]✓ Authentication successful![/green]")
        else:
            _get_console().print("[red]✗ Authentication failed[/red]")

    except Exception as e:
        _get_console().print(f"[red]✗ Error: {e}[/red]")


def _test_anthropic(provider_config) -> bool:
    """Test Anthropic API."""
    try:
        # Lazy import anthropic - only loaded when testing auth
        import anthropic

        client = anthropic.Anthropic(
            api_key=provider_config.get_api_key(),
            base_url=provider_config.base_url,
            max_retries=5,  # Increase from default 2 to handle overloaded errors
            timeout=600.0,  # 10 minutes timeout for long-running requests
        )

        response = client.messages.create(
            model=provider_config.get_model("small"),
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}],
        )

        _get_console().print(f"[dim]Model: {provider_config.get_model('small')}[/dim]")
        _get_console().print(f"[dim]Response: {response.content[0].text}[/dim]")
        return True
    except Exception as e:
        _get_console().print(f"[dim]Error: {e}[/dim]")
        return False


def _test_openai(provider_config) -> bool:
    """Test OpenAI API."""
    try:
        # Lazy import openai - only loaded when testing auth
        import openai

        client = openai.OpenAI(
            api_key=provider_config.get_api_key(), base_url=provider_config.base_url
        )

        response = client.chat.completions.create(
            model=provider_config.get_model("small"),
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}],
        )

        _get_console().print(f"[dim]Model: {provider_config.get_model('small')}[/dim]")
        _get_console().print(
            f"[dim]Response: {response.choices[0].message.content}[/dim]"
        )
        return True
    except Exception as e:
        _get_console().print(f"[dim]Error: {e}[/dim]")
        return False


@cli.group()
def logs():
    """View and manage CDD Agent logs.

    Logs are stored in /tmp/cdd-agent/ and include detailed debug information
    to help diagnose issues. Logs rotate automatically when they reach 10MB.
    """
    pass


@logs.command(name="show")
@click.option(
    "--lines",
    "-n",
    default=50,
    type=int,
    help="Number of lines to show (default: 50)",
)
@click.option(
    "--follow",
    "-f",
    is_flag=True,
    help="Follow log output (like tail -f)",
)
def show_logs(lines: int, follow: bool):
    """Show recent log entries.

    Examples:
        cdd-agent logs show              # Last 50 lines
        cdd-agent logs show -n 100       # Last 100 lines
        cdd-agent logs show -f           # Follow logs (Ctrl+C to exit)
    """
    from .logging import get_log_file_path, read_recent_logs

    log_file = get_log_file_path()

    if follow:
        _get_console().print(f"[dim]Following {log_file}... (Ctrl+C to stop)[/dim]\n")
        try:
            import subprocess

            subprocess.run(["tail", "-f", str(log_file)])
        except KeyboardInterrupt:
            _get_console().print("\n[dim]Stopped following logs[/dim]")
        except FileNotFoundError:
            _get_console().print(
                "[yellow]tail command not available on this system[/yellow]"
            )
            _get_console().print("[dim]Showing last logs instead:[/dim]\n")
            content = read_recent_logs(lines)
            _get_console().print(content)
    else:
        _get_console().print(f"[dim]Last {lines} lines from {log_file}:[/dim]\n")
        content = read_recent_logs(lines)
        _get_console().print(content)


@logs.command(name="clear")
def clear_logs():
    """Clear all log files.

    This will delete all log files from /tmp/cdd-agent/.
    """
    from .logging import clear_logs as clear_log_files

    success, message = clear_log_files()

    if success:
        _get_console().print(f"[green]✓ {message}[/green]")
    else:
        _get_console().print(f"[red]✗ {message}[/red]")


@logs.command(name="path")
def log_path():
    """Show the path to the log file."""
    from .logging import get_log_file_path

    log_file = get_log_file_path()
    _get_console().print(f"[cyan]Log file: {log_file}[/cyan]")


@cli.command()
def hello():
    """Say hello."""
    print("Hello from CDD Agent!")


@logs.command(name="stats")
def log_stats():
    """Show statistics about log files."""
    from .logging import get_log_stats

    stats = get_log_stats()

    if stats["total_files"] == 0:
        _get_console().print("[yellow]No log files found.[/yellow]")
        _get_console().print("[dim]Logs will be created when the agent runs.[/dim]")
        return

    from rich.panel import Panel

    _get_console().print(
        Panel.fit(
            f"""[cyan]Log Statistics:[/cyan]

Total files: {stats['total_files']}
Total size: {stats['total_size_mb']:.2f} MB

Current log: {stats['current_log']}
Oldest log: {stats['oldest_log']}""",
            title="📊 Log Stats",
            border_style="cyan",
        )
    )


if __name__ == "__main__":
    cli()
