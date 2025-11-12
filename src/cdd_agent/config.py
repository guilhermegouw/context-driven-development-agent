"""Configuration management for CDD Agent.

This module handles:
- Loading/saving settings from ~/.cdd-agent/settings.json
- Provider configuration (Anthropic, OpenAI, custom)
- Model tier mappings (haiku/sonnet/opus)
- Environment variable overrides
"""

import json
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ApprovalMode(str, Enum):
    """Approval mode for tool execution.

    - PARANOID: Ask for approval on every tool execution
    - BALANCED: Auto-approve safe read-only tools, ask for writes
    - TRUSTING: Remember approvals within session, minimal interruptions
    """

    PARANOID = "paranoid"
    BALANCED = "balanced"
    TRUSTING = "trusting"


class OAuthTokens(BaseModel):
    """OAuth token storage for plan-based authentication.

    Stores OAuth tokens for Claude Pro/Max plans, enabling zero-cost API access.
    Tokens are automatically refreshed when they expire.
    """

    type: Literal["oauth"] = "oauth"
    refresh_token: str
    access_token: str
    expires_at: int  # Unix timestamp


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""

    auth_token: Optional[str] = None
    api_key: Optional[str] = None  # Alias for auth_token (OpenAI style)
    oauth: Optional[OAuthTokens] = None  # OAuth tokens for plan-based auth
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
        """Get API key (handles both auth_token and api_key).

        Note: If OAuth is configured, this returns an empty string.
        The OAuth access token should be used instead via the oauth property.
        """
        if self.oauth:
            # OAuth is configured - access token will be used instead
            return ""
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
    approval_mode: ApprovalMode = ApprovalMode.BALANCED
    default_execution_mode: str = "normal"  # "normal" or "plan"
    ui: Dict[str, Any] = Field(default_factory=dict)
    conversation: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("default_execution_mode")
    @classmethod
    def validate_execution_mode(cls, v: str) -> str:
        """Validate execution mode is either 'normal' or 'plan'."""
        if v not in ("normal", "plan"):
            raise ValueError("default_execution_mode must be 'normal' or 'plan'")
        return v

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
            approval_mode=ApprovalMode.BALANCED,
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

    def get_effective_config(self, provider: Optional[str] = None) -> ProviderConfig:
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

    def get_effective_approval_mode(
        self, override: Optional[str] = None
    ) -> ApprovalMode:
        """Get effective approval mode with environment variable and CLI override.

        Priority order (highest to lowest):
        1. CLI flag override (passed as parameter)
        2. CDD_APPROVAL_MODE environment variable
        3. Settings file value
        4. Default (balanced)

        Args:
            override: CLI flag override (optional)

        Returns:
            ApprovalMode enum value

        Raises:
            ValueError: If invalid approval mode specified
        """
        settings = self.load()

        # Priority 1: CLI flag override
        if override:
            try:
                return ApprovalMode(override)
            except ValueError:
                raise ValueError(
                    f"Invalid approval mode: {override}. "
                    f"Valid modes: {', '.join(m.value for m in ApprovalMode)}"
                )

        # Priority 2: Environment variable
        env_mode = os.getenv("CDD_APPROVAL_MODE")
        if env_mode:
            try:
                return ApprovalMode(env_mode)
            except ValueError:
                raise ValueError(
                    f"Invalid CDD_APPROVAL_MODE: {env_mode}. "
                    f"Valid modes: {', '.join(m.value for m in ApprovalMode)}"
                )

        # Priority 3: Settings file
        return settings.approval_mode

    def get_effective_execution_mode(self, plan_flag: bool = False) -> str:
        """Get effective execution mode with environment variable and CLI override.

        Priority order (highest to lowest):
        1. CLI flag override (--plan)
        2. CDD_EXECUTION_MODE environment variable
        3. Settings file value (default_execution_mode)
        4. Default ("normal")

        Args:
            plan_flag: CLI --plan flag (True means Plan Mode)

        Returns:
            Execution mode string ("normal" or "plan")

        Raises:
            ValueError: If invalid execution mode specified
        """
        settings = self.load()

        # Priority 1: CLI flag override
        if plan_flag:
            return "plan"

        # Priority 2: Environment variable
        env_mode = os.getenv("CDD_EXECUTION_MODE")
        if env_mode:
            if env_mode not in ("normal", "plan"):
                raise ValueError(
                    f"Invalid CDD_EXECUTION_MODE: {env_mode}. "
                    "Valid modes: normal, plan"
                )
            return env_mode

        # Priority 3: Settings file
        return settings.default_execution_mode
