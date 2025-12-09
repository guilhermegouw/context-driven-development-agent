"""LLM Provider implementations.

This module provides a Strategy pattern implementation for LLM providers,
enabling clean separation between different authentication methods and
future multi-provider support.

Available Providers:
- AnthropicProvider: Standard API key authentication
- AnthropicOAuthProvider: OAuth authentication for Claude Pro/Max plans

Usage:
    from cdd_agent.providers import create_provider

    provider = create_provider(provider_config)
    response = provider.create_message(messages, tools, system)
"""

from .anthropic_oauth_provider import AnthropicOAuthProvider
from .anthropic_provider import AnthropicProvider
from .base import ProviderStrategy
from .factory import create_provider


__all__ = [
    "AnthropicOAuthProvider",
    "AnthropicProvider",
    "ProviderStrategy",
    "create_provider",
]
