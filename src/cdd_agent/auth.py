"""Authentication management for CDD Agent.

This module handles:
- Interactive provider setup
- API key validation
- Configuration display
"""

from typing import Dict

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .config import ConfigManager, ProviderConfig, Settings

console = Console()


class AuthManager:
    """Manages authentication setup and validation."""

    def __init__(self, config_manager: ConfigManager):
        """Initialize auth manager.

        Args:
            config_manager: ConfigManager instance
        """
        self.config = config_manager

    def interactive_setup(self) -> Settings:
        """Guide user through initial setup.

        Returns:
            Settings object after setup
        """
        console.print(
            Panel.fit(
                "[bold cyan]Welcome to CDD Agent![/bold cyan]\n\n"
                "Let's set up your LLM provider authentication.",
                border_style="cyan",
            )
        )

        # Choose provider
        provider_choice = Prompt.ask(
            "\nWhich LLM provider do you want to use?",
            choices=["anthropic", "openai", "custom"],
            default="anthropic",
        )

        if provider_choice == "anthropic":
            return self._setup_anthropic()
        elif provider_choice == "openai":
            return self._setup_openai()
        else:
            return self._setup_custom()

    def _setup_anthropic(self) -> Settings:
        """Set up Anthropic configuration.

        Returns:
            Settings object with Anthropic provider
        """
        console.print("\n[bold]Anthropic Setup[/bold]")
        console.print("Get your API key from: [link]https://console.anthropic.com/[/link]")

        api_key = Prompt.ask("Enter your Anthropic API key", password=True)

        # Test the key
        if self._validate_anthropic_key(api_key):
            console.print("[green]✓ API key validated successfully![/green]")
        else:
            console.print(
                "[yellow]⚠ Could not validate API key (but saving anyway)[/yellow]"
            )

        # Model selection
        use_defaults = Confirm.ask("Use default model mappings?", default=True)

        if use_defaults:
            models = {
                "small": "claude-3-5-haiku-20241022",
                "mid": "claude-sonnet-4-5-20250929",
                "big": "claude-opus-4-20250514",
            }
        else:
            models = self._prompt_models()

        provider_config = ProviderConfig(
            auth_token=api_key, base_url="https://api.anthropic.com", models=models
        )

        settings = Settings(
            default_provider="anthropic", providers={"anthropic": provider_config}
        )

        self.config.save(settings)
        console.print(
            f"[green]✓ Configuration saved to {self.config.config_file}[/green]"
        )
        return settings

    def _setup_openai(self) -> Settings:
        """Set up OpenAI configuration.

        Returns:
            Settings object with OpenAI provider
        """
        console.print("\n[bold]OpenAI Setup[/bold]")
        console.print("Get your API key from: [link]https://platform.openai.com/[/link]")

        api_key = Prompt.ask("Enter your OpenAI API key", password=True)

        # Model selection
        use_defaults = Confirm.ask("Use default model mappings?", default=True)

        if use_defaults:
            models = {
                "small": "gpt-4o-mini",
                "mid": "gpt-4o",
                "big": "o1-preview",
            }
        else:
            models = self._prompt_models()

        provider_config = ProviderConfig(
            api_key=api_key, base_url="https://api.openai.com/v1", models=models
        )

        settings = Settings(
            default_provider="openai", providers={"openai": provider_config}
        )

        self.config.save(settings)
        console.print(
            f"[green]✓ Configuration saved to {self.config.config_file}[/green]"
        )
        return settings

    def _setup_custom(self) -> Settings:
        """Set up custom provider (like z.ai).

        Returns:
            Settings object with custom provider
        """
        console.print("\n[bold]Custom Provider Setup[/bold]")
        console.print(
            "This is for alternative providers (like z.ai, local servers, proxies)"
        )

        base_url = Prompt.ask(
            "\nEnter base URL",
            default="https://api.z.ai/api/anthropic",
        )

        api_key = Prompt.ask("Enter your API key/token", password=True)

        provider_type = Prompt.ask(
            "\nAPI compatibility (which API format does it use?)",
            choices=["anthropic", "openai"],
            default="anthropic",
        )

        console.print("\n[bold]Model Configuration[/bold]")
        console.print("Map model tiers to actual model names:")

        models = {
            "small": Prompt.ask("  Small model (fast/cheap)", default="glm-4.5-air"),
            "mid": Prompt.ask(
                "  Mid model (balanced)", default="glm-4.6"
            ),
            "big": Prompt.ask("  Big model (powerful)", default="glm-4.6"),
        }

        provider_config = ProviderConfig(
            auth_token=api_key,
            base_url=base_url,
            models=models,
            provider_type=provider_type,
        )

        settings = Settings(
            default_provider="custom", providers={"custom": provider_config}
        )

        self.config.save(settings)
        console.print(
            f"[green]✓ Custom provider configured and saved to {self.config.config_file}[/green]"
        )
        return settings

    def _prompt_models(self) -> Dict[str, str]:
        """Prompt user for custom model mappings.

        Returns:
            Dictionary mapping tier names to model names
        """
        console.print("\n[bold]Custom Model Configuration[/bold]")
        return {
            "small": Prompt.ask("  Small model (fast/cheap)"),
            "mid": Prompt.ask("  Mid model (balanced)"),
            "big": Prompt.ask("  Big model (powerful)"),
        }

    def _validate_anthropic_key(self, api_key: str) -> bool:
        """Test Anthropic API key.

        Args:
            api_key: API key to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            import anthropic

            client = anthropic.Anthropic(
                api_key=api_key,
                max_retries=5,  # Increase from default 2 to handle overloaded errors
                timeout=600.0,  # 10 minutes timeout for long-running requests
            )
            # Try a minimal request
            client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception as e:
            console.print(f"[dim]Validation error: {e}[/dim]")
            return False

    def display_current_config(self) -> None:
        """Show current configuration in a table."""
        if not self.config.exists():
            console.print(
                "[yellow]No configuration found. Run 'cdd-agent auth setup' first.[/yellow]"
            )
            return

        settings = self.config.load()

        table = Table(title="Current Configuration")
        table.add_column("Provider", style="cyan")
        table.add_column("Base URL", style="green")
        table.add_column("Default Model", style="yellow")
        table.add_column("Status", style="magenta")

        for name, provider in settings.providers.items():
            is_default = "⭐ Default" if name == settings.default_provider else ""
            has_key = "✓ Configured" if provider.get_api_key() else "✗ Missing Key"

            table.add_row(
                name, provider.base_url, provider.get_model(), f"{is_default} {has_key}"
            )

        console.print(table)

        # Show config file location
        console.print(f"\n[dim]Config file: {self.config.config_file}[/dim]")
