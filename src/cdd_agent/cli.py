"""CLI entry point for CDD Agent.

This module provides the command-line interface for:
- Authentication management
- Provider configuration
- Chat and agent interactions
"""

import os
import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from . import __version__
from .agent import Agent
from .auth import AuthManager
from .config import ConfigManager
from .tools import create_default_registry
from .tui import run_tui
from .ui import StreamingUI

console = Console()


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
def chat(prompt: str, provider: str, model: str, system: str, no_stream: bool, simple: bool):
    """Interactive chat with AI agent.

    The agent can use tools to read files, write files, and execute commands.

    By default, opens a beautiful split-pane TUI interface. Use --simple for
    a simpler streaming interface, or --no-stream for single-shot mode.

    Examples:
        cdd-agent chat                    # Full TUI mode (default)
        cdd-agent chat --simple           # Simple streaming UI
        cdd-agent chat "Quick question"   # Single message in TUI
        cdd-agent chat --model small      # Use smaller model
        cdd-agent chat --no-stream        # Disable streaming
    """
    config = ConfigManager()

    # Check if configured
    if not config.exists():
        console.print(
            Panel.fit(
                "[bold red]No configuration found![/bold red]\n\n"
                "Please run [cyan]cdd-agent auth setup[/cyan] first to configure your LLM provider.",
                border_style="red",
                title="❌ Error",
            )
        )
        return

    try:
        # Load provider config
        provider_config = config.get_effective_config(provider)

        # Create tool registry with default tools
        tool_registry = create_default_registry()

        # Create agent
        agent = Agent(
            provider_config=provider_config,
            tool_registry=tool_registry,
            model_tier=model,
            max_iterations=25,  # Increased from default 10
        )

        # Decide which UI to use
        if simple or no_stream:
            # Use simple streaming UI
            ui = StreamingUI(console)

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
            # Use full TUI (default)
            run_tui(
                agent=agent,
                provider=provider or "default",
                model=provider_config.get_model(model),
                system_prompt=system,
            )

    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye![/dim]")
    except Exception as e:
        console.print(
            Panel.fit(
                f"[bold red]Error:[/bold red]\n\n{str(e)}",
                border_style="red",
                title="❌ Error",
            )
        )
        import traceback

        console.print(f"\n[dim]{traceback.format_exc()}[/dim]")


def _run_single_message(
    agent: Agent, ui: StreamingUI, prompt: str, system: str, no_stream: bool
):
    """Run a single message (non-interactive).

    Args:
        agent: Agent instance
        ui: UI instance
        prompt: User message
        system: System prompt
        no_stream: Whether to disable streaming
    """
    console.print(f"[bold]>[/bold] {prompt}\n")

    if no_stream:
        # Non-streaming mode (original behavior)
        response = agent.run(prompt, system_prompt=system)
        console.print(Markdown(response))
    else:
        # Streaming mode
        event_stream = agent.stream(prompt, system_prompt=system)
        ui.stream_response(event_stream)

    console.print("\n[green]✓ Done![/green]")


def _run_interactive_chat(
    agent: Agent, ui: StreamingUI, system: str, no_stream: bool
):
    """Run interactive chat loop.

    Args:
        agent: Agent instance
        ui: UI instance
        system: System prompt
        no_stream: Whether to disable streaming
    """
    while True:
        try:
            # Show prompt
            ui.show_prompt(">")

            # Get user input
            user_input = input()

            # Handle empty input
            if not user_input.strip():
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                if _handle_slash_command(user_input, agent, ui):
                    break  # Exit if quit command
                continue

            # Send to agent
            console.print()  # Blank line before response

            if no_stream:
                response = agent.run(user_input, system_prompt=system)
                console.print(Markdown(response))
            else:
                event_stream = agent.stream(user_input, system_prompt=system)
                ui.stream_response(event_stream)

            console.print()  # Blank line after response

        except KeyboardInterrupt:
            console.print("\n[dim]Use /quit to exit or Ctrl+D[/dim]")
            continue
        except EOFError:
            break


def _handle_slash_command(command: str, agent: Agent, ui: StreamingUI) -> bool:
    """Handle slash commands.

    Args:
        command: Command string (e.g., "/help")
        agent: Agent instance
        ui: UI instance

    Returns:
        True if should exit, False otherwise
    """
    cmd = command.strip().lower()

    if cmd == "/help":
        ui.show_help()
        return False

    elif cmd == "/quit" or cmd == "/exit":
        console.print("[dim]Goodbye![/dim]")
        return True

    elif cmd == "/clear":
        agent.clear_history()
        console.print("[green]✓ Conversation history cleared[/green]")
        return False

    elif cmd.startswith("/save"):
        # TODO: Implement conversation saving
        console.print("[yellow]⚠ Conversation saving not yet implemented[/yellow]")
        return False

    elif cmd == "/new":
        agent.clear_history()
        console.print("[green]✓ Starting new conversation[/green]")
        return False

    else:
        console.print(f"[red]Unknown command: {command}[/red]")
        console.print("[dim]Type /help for available commands[/dim]")
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
    config = ConfigManager()
    auth_manager = AuthManager(config)
    auth_manager.interactive_setup()


@auth.command(name="status")
def auth_status():
    """Show current authentication status.

    Displays configured providers, API key status, and model mappings.

    Example:
        cdd-agent auth status
    """
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
    config = ConfigManager()

    if not config.exists():
        console.print(
            "[red]No configuration found. Run 'cdd-agent auth setup' first.[/red]"
        )
        return

    settings = config.load()

    if provider not in settings.providers:
        console.print(f"[red]Provider '{provider}' not found.[/red]")
        console.print(
            f"[yellow]Available providers: {', '.join(settings.providers.keys())}[/yellow]"
        )
        return

    settings.default_provider = provider
    config.save(settings)
    console.print(f"[green]✓ Default provider set to: {provider}[/green]")


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
    config = ConfigManager()

    if not config.exists():
        console.print(
            "[red]No configuration found. Run 'cdd-agent auth setup' first.[/red]"
        )
        return

    try:
        provider_config = config.get_effective_config(provider)
        console.print(
            f"[cyan]Testing {provider or 'default'} provider...[/cyan]"
        )

        # Try to import and test based on provider type
        api_key = provider_config.get_api_key()
        if not api_key:
            console.print("[red]✗ No API key configured[/red]")
            return

        # Detect provider type
        if "anthropic" in provider_config.base_url or provider_config.provider_type == "anthropic":
            success = _test_anthropic(provider_config)
        elif "openai" in provider_config.base_url or provider_config.provider_type == "openai":
            success = _test_openai(provider_config)
        else:
            console.print(
                "[yellow]⚠ Unknown provider type, cannot test automatically[/yellow]"
            )
            return

        if success:
            console.print("[green]✓ Authentication successful![/green]")
        else:
            console.print("[red]✗ Authentication failed[/red]")

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")


def _test_anthropic(provider_config) -> bool:
    """Test Anthropic API."""
    try:
        import anthropic

        client = anthropic.Anthropic(
            api_key=provider_config.get_api_key(),
            base_url=provider_config.base_url
        )

        response = client.messages.create(
            model=provider_config.get_model("small"),
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}],
        )

        console.print(f"[dim]Model: {provider_config.get_model('small')}[/dim]")
        console.print(f"[dim]Response: {response.content[0].text}[/dim]")
        return True
    except Exception as e:
        console.print(f"[dim]Error: {e}[/dim]")
        return False


def _test_openai(provider_config) -> bool:
    """Test OpenAI API."""
    try:
        import openai

        client = openai.OpenAI(
            api_key=provider_config.get_api_key(),
            base_url=provider_config.base_url
        )

        response = client.chat.completions.create(
            model=provider_config.get_model("small"),
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}],
        )

        console.print(f"[dim]Model: {provider_config.get_model('small')}[/dim]")
        console.print(f"[dim]Response: {response.choices[0].message.content}[/dim]")
        return True
    except Exception as e:
        console.print(f"[dim]Error: {e}[/dim]")
        return False


if __name__ == "__main__":
    cli()
