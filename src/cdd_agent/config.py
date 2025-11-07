"""Configuration management for CDD Agent.

This module handles:
- Loading/saving settings from ~/.cdd-agent/settings.json
- Provider configuration (Anthropic, OpenAI, custom)
- Model tier mappings (haiku/sonnet/opus)
- Environment variable overrides
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""

    auth_token: Optional[str] = None
    api_key: Optional[str] = None  # Alias for auth_token (OpenAI style)
    base_url: str
    timeout_ms: int = 300000
    models: Dict[str, str] = Field(default_factory=dict)
    default_model: str = "mid"
    provider_type: Optional[str] = None  # For custom providers (anthropic/openai)

    @field_validator("models")
    @classmethod
    def validate_models(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Ensure small/mid/big are defined."""
        required = {"small", "mid", "big"}
        if not required.issubset(v.keys()):
            raise ValueError(f"Models must include: {required}")
        return v

    def get_api_key(self) -> str:
        """Get API key (handles both auth_token and api_key)."""
        return self.auth_token or self.api_key or ""

    def get_model(self, tier: Optional[str] = None) -> str:
        """Get model name by tier or default."""
        tier = tier or self.default_model
        return self.models.get(tier, self.models[self.default_model])


class Settings(BaseModel):
    """Main settings configuration."""

    version: str = "1.0"
    default_provider: str = "anthropic"
    providers: Dict[str, ProviderConfig]
    ui: Dict[str, Any] = Field(default_factory=dict)
    conversation: Dict[str, Any] = Field(default_factory=dict)

    def get_provider(self, name: Optional[str] = None) -> ProviderConfig:
        """Get provider config by name or default."""
        provider_name = name or self.default_provider
        if provider_name not in self.providers:
            raise ValueError(f"Provider '{provider_name}' not configured")
        return self.providers[provider_name]


class ConfigManager:
    """Manages configuration file operations."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize config manager.

        Args:
            config_dir: Config directory path (defaults to ~/.cdd-agent)
        """
        self.config_dir = config_dir or Path.home() / ".cdd-agent"
        self.config_file = self.config_dir / "settings.json"
        self._settings: Optional[Settings] = None

    def ensure_config_dir(self) -> None:
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def exists(self) -> bool:
        """Check if configuration file exists."""
        return self.config_file.exists()

    def load(self) -> Settings:
        """Load settings from file or create default.

        Returns:
            Settings object

        Raises:
            RuntimeError: If config file is invalid
        """
        if self._settings:
            return self._settings

        if not self.config_file.exists():
            return self.create_default()

        try:
            with open(self.config_file, "r") as f:
                data = json.load(f)
            self._settings = Settings(**data)
            return self._settings
        except Exception as e:
            raise RuntimeError(f"Failed to load config: {e}")

    def save(self, settings: Settings) -> None:
        """Save settings to file.

        Args:
            settings: Settings object to save
        """
        self.ensure_config_dir()
        with open(self.config_file, "w") as f:
            json.dump(settings.model_dump(), f, indent=2)
        self._settings = settings

    def create_default(self) -> Settings:
        """Create default settings template.

        Returns:
            Settings object with default Anthropic configuration
        """
        settings = Settings(
            default_provider="anthropic",
            providers={
                "anthropic": ProviderConfig(
                    base_url="https://api.anthropic.com",
                    models={
                        "small": "claude-3-5-haiku-20241022",
                        "mid": "claude-sonnet-4-5-20250929",
                        "big": "claude-opus-4-20250514",
                    },
                )
            },
            ui={"stream_responses": True, "syntax_highlighting": True},
            conversation={"auto_save": True, "history_limit": 100},
        )
        return settings

    def get_effective_config(
        self, provider: Optional[str] = None
    ) -> ProviderConfig:
        """Get effective config with environment variable overrides.

        Args:
            provider: Provider name (uses default if None)

        Returns:
            ProviderConfig with env overrides applied
        """
        settings = self.load()
        provider_config = settings.get_provider(provider)

        # Environment variable overrides (Claude Code style)
        env_token = os.getenv("CDD_AUTH_TOKEN") or os.getenv("ANTHROPIC_AUTH_TOKEN")
        env_base_url = os.getenv("CDD_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL")
        env_api_key = os.getenv("OPENAI_API_KEY")

        # Create a copy to avoid modifying the original
        config_dict = provider_config.model_dump()

        # Apply overrides (only if set)
        if env_token:
            config_dict["auth_token"] = env_token
        if env_base_url:
            config_dict["base_url"] = env_base_url
        if env_api_key and provider == "openai":
            config_dict["api_key"] = env_api_key

        return ProviderConfig(**config_dict)
