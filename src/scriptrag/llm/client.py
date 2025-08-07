"""Multi-provider LLM client with automatic fallback."""

from typing import Any

from scriptrag.config import get_logger
from scriptrag.llm.base import BaseLLMProvider
from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
    Model,
)
from scriptrag.llm.registry import ProviderRegistry

logger = get_logger(__name__)


class LLMClient:
    """Multi-provider LLM client with automatic fallback."""

    def __init__(
        self,
        preferred_provider: LLMProvider | None = None,
        fallback_order: list[LLMProvider] | None = None,
        github_token: str | None = None,
        openai_endpoint: str | None = None,
        openai_api_key: str | None = None,
        timeout: float = 30.0,
        registry: ProviderRegistry | None = None,
    ) -> None:
        """Initialize LLM client with provider preferences.

        Args:
            preferred_provider: Preferred provider to use if available.
            fallback_order: Order of providers to try if preferred isn't available.
            github_token: GitHub token for GitHub Models provider.
            openai_endpoint: Endpoint URL for OpenAI-compatible provider.
            openai_api_key: API key for OpenAI-compatible provider.
            timeout: Default timeout for HTTP requests.
            registry: Optional provider registry to use. If not provided,
                creates a new one.
        """
        self.current_provider: BaseLLMProvider | None = None
        self.preferred_provider = preferred_provider

        # Default fallback order
        if fallback_order is None:
            fallback_order = [
                LLMProvider.CLAUDE_CODE,
                LLMProvider.GITHUB_MODELS,
                LLMProvider.OPENAI_COMPATIBLE,
            ]
        self.fallback_order = fallback_order
        self.timeout = timeout

        # Store credentials (also expose as public for testing)
        self.github_token = self._github_token = github_token
        self.openai_endpoint = self._openai_endpoint = openai_endpoint
        self.openai_api_key = self._openai_api_key = openai_api_key

        # Use provided registry or create a new one
        if registry is not None:
            self.registry = registry
        else:
            self.registry = ProviderRegistry()
            # Initialize default providers
            self.registry.initialize_default_providers(
                github_token=self._github_token,
                openai_endpoint=self._openai_endpoint,
                openai_api_key=self._openai_api_key,
                timeout=self.timeout,
            )

        # Provider selection is done lazily via ensure_provider()

    @property
    def providers(self) -> dict[LLMProvider, BaseLLMProvider]:
        """Get all providers from the registry."""
        return self.registry.providers

    async def _select_provider(self) -> None:
        """Select the best available provider based on preferences."""
        # Try preferred provider first
        if self.preferred_provider:
            provider = self.registry.get_provider(self.preferred_provider)
            if provider and await provider.is_available():
                self.current_provider = provider
                logger.info(
                    f"Using preferred provider: {self.preferred_provider.value}"
                )
                return

        # Try fallback providers in order
        for provider_type in self.fallback_order:
            provider = self.registry.get_provider(provider_type)
            if provider and await provider.is_available():
                self.current_provider = provider
                logger.info(f"Using provider: {provider_type.value}")
                return

        logger.warning("No LLM providers available")

    async def ensure_provider(self) -> BaseLLMProvider:
        """Ensure a provider is selected and available."""
        if not self.current_provider:
            await self._select_provider()

        if not self.current_provider:
            raise RuntimeError(
                "No LLM provider available. Please configure credentials."
            )

        return self.current_provider

    async def list_models(self, provider: LLMProvider | None = None) -> list[Model]:
        """List all available models across all available providers.

        Args:
            provider: Optional specific provider to list models from.

        Returns:
            List of available models.
        """
        if provider:
            # List models from specific provider
            provider_instance = self.registry.get_provider(provider)
            if provider_instance and await provider_instance.is_available():
                try:
                    return await provider_instance.list_models()
                except Exception as e:
                    logger.debug(f"Failed to list models from {provider.value}: {e}")
            return []

        # List models from all available providers
        all_models = []
        for provider_type, provider_instance in self.providers.items():
            try:
                if await provider_instance.is_available():
                    models = await provider_instance.list_models()
                    all_models.extend(models)
            except Exception as e:
                logger.debug(f"Failed to list models from {provider_type.value}: {e}")

        return all_models

    async def get_provider_for_model(self, model_id: str) -> LLMProvider | None:
        """Get the provider type for a specific model.

        Args:
            model_id: The model ID to look up.

        Returns:
            The provider type that supports this model, or None if not found.
        """
        all_models = await self.list_models()
        for model in all_models:
            if model.id == model_id:
                return model.provider
        return None

    async def complete(
        self,
        messages: list[dict[str, str]] | CompletionRequest,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        system: str | None = None,
        provider: LLMProvider | None = None,
    ) -> CompletionResponse:
        """Generate text completion.

        Args:
            messages: List of message dictionaries with 'role' and 'content',
                or CompletionRequest.
            model: Model ID to use. If None, uses provider default.
            temperature: Sampling temperature (0-2).
            max_tokens: Maximum tokens to generate.
            system: System prompt to prepend.
            provider: Specific provider to use, bypassing fallback logic.

        Returns:
            Completion response with generated text.
        """
        # Handle both signatures: CompletionRequest object or separate parameters
        if isinstance(messages, CompletionRequest):
            request = messages
        else:
            # Use default model if not specified
            # Use empty string to indicate model should be auto-selected
            request = CompletionRequest(
                model=model or "",  # Empty means auto-select
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                system=system,
            )

        # Try completion with fallback logic
        if provider:
            # User specified a specific provider
            provider_instance = self.registry.get_provider(provider)
            if provider_instance and await provider_instance.is_available():
                return await self._try_complete_with_provider(
                    provider_instance, request
                )
            raise RuntimeError(f"Requested provider {provider.value} is not available")
        # Try providers in fallback order
        return await self._complete_with_fallback(request)

    async def _try_complete_with_provider(
        self, provider: BaseLLMProvider, request: CompletionRequest
    ) -> CompletionResponse:
        """Try completion with a specific provider, handling model selection."""
        # Update model if not specified or empty
        if not request.model or request.model == "":
            models = await provider.list_models()
            if models:
                # Pick first chat-capable model (models sorted by preference)
                for m in models:
                    if "chat" in m.capabilities or "completion" in m.capabilities:
                        request.model = m.id
                        logger.debug(f"Auto-selected model: {m.id}")
                        break

                # If no chat-capable model found, use the first one
                if not request.model and models:
                    request.model = models[0].id
                    logger.debug(f"Using first available model: {models[0].id}")

        return await provider.complete(request)

    async def _complete_with_fallback(
        self, request: CompletionRequest
    ) -> CompletionResponse:
        """Try completion with providers in fallback order."""
        errors = []

        # Try preferred provider first
        if self.preferred_provider:
            provider = self.registry.get_provider(self.preferred_provider)
            if provider and await provider.is_available():
                try:
                    return await self._try_complete_with_provider(provider, request)
                except Exception as e:
                    logger.debug(
                        f"Preferred provider {self.preferred_provider.value} "
                        f"failed: {e}"
                    )
                    errors.append(f"{self.preferred_provider.value}: {e}")

        # Try fallback providers in order
        for provider_type in self.fallback_order:
            if provider_type == self.preferred_provider:
                continue  # Already tried

            provider = self.registry.get_provider(provider_type)
            if provider and await provider.is_available():
                try:
                    return await self._try_complete_with_provider(provider, request)
                except Exception as e:
                    logger.debug(f"Fallback provider {provider_type.value} failed: {e}")
                    errors.append(f"{provider_type.value}: {e}")

        # All providers failed
        raise RuntimeError(f"All LLM providers failed: {'; '.join(errors)}")

    async def embed(
        self,
        text: str | list[str] | EmbeddingRequest,
        model: str | None = None,
        dimensions: int | None = None,
        provider: LLMProvider | None = None,
    ) -> EmbeddingResponse:
        """Generate text embeddings.

        Args:
            text: Text or list of texts to embed, or EmbeddingRequest.
            model: Model ID to use. If None, uses provider default.
            dimensions: Output embedding dimensions.
            provider: Specific provider to use, bypassing fallback logic.

        Returns:
            Embedding response with vector representations.
        """
        # Handle both signatures: EmbeddingRequest object or separate parameters
        if isinstance(text, EmbeddingRequest):
            request = text
        else:
            request = EmbeddingRequest(
                model=model or "text-embedding-ada-002",  # Temporary fallback
                input=text,
                dimensions=dimensions,
            )

        # Try embedding with fallback logic
        if provider:
            # User specified a specific provider
            provider_instance = self.registry.get_provider(provider)
            if provider_instance and await provider_instance.is_available():
                return await self._try_embed_with_provider(provider_instance, request)
            raise RuntimeError(f"Requested provider {provider.value} is not available")
        # Try providers in fallback order
        return await self._embed_with_fallback(request)

    async def _try_embed_with_provider(
        self, provider: BaseLLMProvider, request: EmbeddingRequest
    ) -> EmbeddingResponse:
        """Try embedding with a specific provider, handling model selection."""
        # Update model if not specified
        if request.model == "text-embedding-ada-002":  # Our temporary fallback
            models = await provider.list_models()
            if models:
                # Pick first embedding-capable model
                for m in models:
                    if "embedding" in m.capabilities:
                        request.model = m.id
                        break

        return await provider.embed(request)

    async def _embed_with_fallback(
        self, request: EmbeddingRequest
    ) -> EmbeddingResponse:
        """Try embedding with providers in fallback order."""
        errors = []

        # Try preferred provider first
        if self.preferred_provider:
            provider = self.registry.get_provider(self.preferred_provider)
            if provider and await provider.is_available():
                try:
                    return await self._try_embed_with_provider(provider, request)
                except Exception as e:
                    logger.debug(
                        f"Preferred provider {self.preferred_provider.value} "
                        f"failed: {e}"
                    )
                    errors.append(f"{self.preferred_provider.value}: {e}")

        # Try fallback providers in order
        for provider_type in self.fallback_order:
            if provider_type == self.preferred_provider:
                continue  # Already tried

            provider = self.registry.get_provider(provider_type)
            if provider and await provider.is_available():
                try:
                    return await self._try_embed_with_provider(provider, request)
                except Exception as e:
                    logger.debug(f"Fallback provider {provider_type.value} failed: {e}")
                    errors.append(f"{provider_type.value}: {e}")

        # All providers failed
        raise RuntimeError(f"All LLM providers failed: {'; '.join(errors)}")

    def get_current_provider(self) -> LLMProvider | None:
        """Get the currently active provider type."""
        if self.current_provider:
            return self.current_provider.provider_type
        return None

    async def switch_provider(self, provider_type: LLMProvider) -> bool:
        """Manually switch to a specific provider.

        Args:
            provider_type: Provider to switch to.

        Returns:
            True if switch was successful, False otherwise.
        """
        provider = self.registry.get_provider(provider_type)
        if provider and await provider.is_available():
            self.current_provider = provider
            logger.info(f"Switched to provider: {provider_type.value}")
            return True
        return False

    async def cleanup(self) -> None:
        """Clean up resources for all providers."""
        await self.registry.cleanup()

    async def __aenter__(self) -> "LLMClient":
        """Enter async context manager."""
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Exit async context manager and cleanup."""
        await self.cleanup()
