"""Provider registry for managing LLM provider instances."""

from __future__ import annotations

from typing import Any

from scriptrag.config import get_logger
from scriptrag.llm.base import BaseLLMProvider
from scriptrag.llm.models import LLMProvider
from scriptrag.llm.providers import (
    ClaudeCodeProvider,
    GitHubModelsProvider,
    OpenAICompatibleProvider,
)

logger = get_logger(__name__)


class ProviderRegistry:
    """Registry for managing LLM provider instances."""

    def __init__(self) -> None:
        """Initialize the provider registry."""
        self.providers: dict[LLMProvider, BaseLLMProvider] = {}
        self._custom_providers: dict[LLMProvider, type[BaseLLMProvider]] = {}

    def register_provider_class(
        self, provider_type: LLMProvider, provider_class: type[BaseLLMProvider]
    ) -> None:
        """Register a custom provider class.

        Args:
            provider_type: The provider type identifier.
            provider_class: The provider class to register.
        """
        self._custom_providers[provider_type] = provider_class
        logger.debug(f"Registered provider class: {provider_type.value}")

    def create_provider(
        self, provider_type: LLMProvider, **kwargs: Any
    ) -> BaseLLMProvider:
        """Create a provider instance.

        Args:
            provider_type: The provider type to create.
            **kwargs: Provider-specific initialization arguments.

        Returns:
            The created provider instance.

        Raises:
            ValueError: If the provider type is unknown.
        """
        # Check for custom registered providers first
        if provider_type in self._custom_providers:
            provider_class = self._custom_providers[provider_type]
            return provider_class(**kwargs)

        # Default providers
        if provider_type == LLMProvider.CLAUDE_CODE:
            return ClaudeCodeProvider(**kwargs)
        if provider_type == LLMProvider.GITHUB_MODELS:
            return GitHubModelsProvider(**kwargs)
        if provider_type == LLMProvider.OPENAI_COMPATIBLE:
            return OpenAICompatibleProvider(**kwargs)
        raise ValueError(f"Unknown provider type: {provider_type}")

    def initialize_default_providers(
        self,
        github_token: str | None = None,
        openai_endpoint: str | None = None,
        openai_api_key: str | None = None,
        timeout: float = 30.0,
    ) -> dict[LLMProvider, BaseLLMProvider]:
        """Initialize default provider instances.

        Args:
            github_token: GitHub token for GitHub Models provider.
            openai_endpoint: Endpoint URL for OpenAI-compatible provider.
            openai_api_key: API key for OpenAI-compatible provider.
            timeout: Default timeout for HTTP requests.

        Returns:
            Dictionary of initialized providers.
        """
        providers = {}

        # Initialize Claude Code provider
        providers[LLMProvider.CLAUDE_CODE] = self.create_provider(
            LLMProvider.CLAUDE_CODE
        )

        # Initialize GitHub Models provider
        providers[LLMProvider.GITHUB_MODELS] = self.create_provider(
            LLMProvider.GITHUB_MODELS,
            token=github_token,
            timeout=timeout,
        )

        # Initialize OpenAI-compatible provider
        providers[LLMProvider.OPENAI_COMPATIBLE] = self.create_provider(
            LLMProvider.OPENAI_COMPATIBLE,
            endpoint=openai_endpoint,
            api_key=openai_api_key,
            timeout=timeout,
        )

        self.providers = providers
        return providers

    def get_provider(self, provider_type: LLMProvider) -> BaseLLMProvider | None:
        """Get a provider instance by type.

        Args:
            provider_type: The provider type to retrieve.

        Returns:
            The provider instance if available, None otherwise.
        """
        return self.providers.get(provider_type)

    def set_provider(
        self, provider_type: LLMProvider, provider: BaseLLMProvider
    ) -> None:
        """Set a provider instance.

        Args:
            provider_type: The provider type identifier.
            provider: The provider instance to set.
        """
        self.providers[provider_type] = provider
        logger.debug(f"Set provider: {provider_type.value}")

    def remove_provider(self, provider_type: LLMProvider) -> None:
        """Remove a provider from the registry.

        Args:
            provider_type: The provider type to remove.
        """
        if provider_type in self.providers:
            del self.providers[provider_type]
            logger.debug(f"Removed provider: {provider_type.value}")

    def list_providers(self) -> list[LLMProvider]:
        """List all registered provider types.

        Returns:
            List of provider types.
        """
        return list(self.providers.keys())

    async def cleanup(self) -> None:
        """Clean up resources for all providers."""
        for provider in self.providers.values():
            if hasattr(provider, "client") and provider.client is not None:
                await provider.client.aclose()
                logger.debug(f"Cleaned up provider: {provider.provider_type.value}")
