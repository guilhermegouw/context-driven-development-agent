"""Factory for creating LLM providers.

This module provides a factory function that creates the appropriate
provider based on the configuration.
"""

from typing import Union

from ..config import ProviderConfig
from ..logging import get_logger
from .anthropic_oauth_provider import AnthropicOAuthProvider
from .anthropic_provider import AnthropicProvider


logger = get_logger(__name__)

# Type alias for all provider types
Provider = Union[AnthropicProvider, AnthropicOAuthProvider]


def create_provider(
    provider_config: ProviderConfig,
    model_tier: str = "mid",
    max_retries: int = 5,
    timeout: float = 600.0,
) -> Provider:
    """Create the appropriate provider based on configuration.

    This factory function examines the provider configuration and
    creates the correct provider instance:
    - If OAuth is configured → AnthropicOAuthProvider
    - Otherwise → AnthropicProvider (API key)

    Future: Will support OpenAI and custom providers based on
    provider_config.provider_type.

    Args:
        provider_config: Provider configuration
        model_tier: Model tier to use (small/mid/big)
        max_retries: Maximum retry attempts for API calls
        timeout: Request timeout in seconds

    Returns:
        Appropriate provider instance

    Example:
        config = config_manager.get_effective_config()
        provider = create_provider(config, model_tier="mid")
        response = provider.create_message(messages, tools, system)
    """
    # Check if OAuth is configured (safely handle Mock objects in tests)
    oauth_config = getattr(provider_config, "oauth", None)
    if oauth_config is not None:
        logger.info("Creating AnthropicOAuthProvider (OAuth authentication)")
        return AnthropicOAuthProvider(
            provider_config=provider_config,
            model_tier=model_tier,
            max_retries=max_retries,
            timeout=timeout,
        )

    # Default to API key authentication
    logger.info("Creating AnthropicProvider (API key authentication)")
    return AnthropicProvider(
        provider_config=provider_config,
        model_tier=model_tier,
        max_retries=max_retries,
        timeout=timeout,
    )


def is_oauth_provider(provider: Provider) -> bool:
    """Check if a provider uses OAuth authentication.

    Args:
        provider: Provider instance

    Returns:
        True if provider uses OAuth, False otherwise
    """
    return isinstance(provider, AnthropicOAuthProvider)
