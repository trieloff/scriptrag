"""Multi-provider LLM client with automatic fallback."""

import traceback
from typing import Any, cast

from scriptrag.config import get_logger, get_settings
from scriptrag.exceptions import LLMError, LLMProviderError
from scriptrag.llm.base import BaseLLMProvider
from scriptrag.llm.fallback import FallbackHandler
from scriptrag.llm.metrics import LLMMetrics
from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
    Model,
)
from scriptrag.llm.registry import ProviderRegistry
from scriptrag.llm.retry_strategy import RetryStrategy
from scriptrag.llm.types import ClientMetrics, ErrorDetails

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
        max_retries: int = 3,
        base_retry_delay: float = 1.0,
        max_retry_delay: float = 10.0,
        debug_mode: bool = False,
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
            max_retries: Maximum number of retry attempts for transient failures.
            base_retry_delay: Base delay in seconds for exponential backoff.
            max_retry_delay: Maximum delay in seconds for exponential backoff.
            debug_mode: Enable debug mode for detailed error information.
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
        self.debug_mode = debug_mode

        # Store credentials (also expose as public for testing)
        self.github_token = self._github_token = github_token
        self.openai_endpoint = self._openai_endpoint = openai_endpoint
        self.openai_api_key = self._openai_api_key = openai_api_key

        # Initialize metrics tracking
        self.metrics = LLMMetrics()

        # Cache for model selection results (provider -> model mapping)
        self._model_selection_cache: dict[str, str] = {}

        # Initialize retry strategy
        self.retry_strategy = RetryStrategy(
            max_retries=max_retries,
            base_retry_delay=base_retry_delay,
            max_retry_delay=max_retry_delay,
        )

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

        # Initialize fallback handler
        self.fallback_handler = FallbackHandler(
            registry=self.registry,
            preferred_provider=self.preferred_provider,
            fallback_order=self.fallback_order,
            debug_mode=self.debug_mode,
        )

        # Provider selection is done lazily via ensure_provider()

    def get_metrics(self) -> ClientMetrics:
        """Get current provider metrics."""
        return self.metrics.get_metrics()

    def _metrics_callback(self, provider_name: str, error: Exception | None) -> None:
        """Callback for metrics recording during retry operations."""
        if error:
            self.metrics.record_failure(provider_name, error)
            if self.retry_strategy.is_retryable_error(error):
                self.metrics.record_retry()
        else:
            self.metrics.record_success(provider_name)

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
                except (AttributeError, ValueError, RuntimeError, OSError) as e:
                    logger.debug(f"Failed to list models from {provider.value}: {e}")
            return []

        # List models from all available providers
        all_models = []
        for provider_type, provider_instance in self.providers.items():
            try:
                if await provider_instance.is_available():
                    models = await provider_instance.list_models()
                    all_models.extend(models)
            except (AttributeError, ValueError, RuntimeError, OSError) as e:
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
        return await self.fallback_handler.complete_with_fallback(
            request,
            self._try_complete_with_provider,
            self.metrics.record_fallback_chain,
        )

    async def _select_best_model(
        self, provider: BaseLLMProvider, capability_type: str = "chat"
    ) -> str | None:
        """Select the best model for a provider based on capability type.

        Uses caching to avoid repeated model discovery and searching.

        Args:
            provider: The LLM provider to select a model for
            capability_type: Type of capability ("chat", "completion", "embedding")

        Returns:
            Model ID if found, None otherwise
        """
        provider_name = provider.__class__.__name__
        cache_key = f"{provider_name}:{capability_type}"

        # Check cache first
        if cache_key in self._model_selection_cache:
            logger.debug(
                f"Using cached model selection for {provider_name}",
                model=self._model_selection_cache[cache_key],
                capability=capability_type,
            )
            return self._model_selection_cache[cache_key]

        # Get models from provider
        models = await provider.list_models()
        if not models:
            logger.warning(f"No models available from {provider_name}")
            return None

        selected_model = None

        # Find the first model with the desired capability
        # Models are already sorted by preference in most providers
        for model in models:
            if capability_type in model.capabilities:
                selected_model = model.id
                logger.info(
                    f"Selected {capability_type}-capable model: {model.id}",
                    provider=provider_name,
                    capabilities=model.capabilities,
                )
                break

        # Fallback to first model if no specific capability found
        if not selected_model and models:
            selected_model = models[0].id
            logger.info(
                f"Using first available model: {models[0].id}",
                provider=provider_name,
                capabilities=models[0].capabilities,
                reason=f"no {capability_type}-capable model found",
            )

        # Cache the result
        if selected_model:
            self._model_selection_cache[cache_key] = selected_model

        return selected_model

    async def _try_complete_with_provider(
        self, provider: BaseLLMProvider, request: CompletionRequest
    ) -> CompletionResponse:
        """Try completion with a specific provider, handling model selection."""
        provider_name = provider.__class__.__name__
        logger.info(
            f"Attempting completion with provider: {provider_name}",
            model_requested=request.model if request.model else "auto-select",
        )

        # Update model if not specified or empty
        if not request.model or request.model == "":
            # Use optimized model selection with caching
            selected_model = await self._select_best_model(provider, "chat")
            if not selected_model:
                # Try "completion" capability as fallback
                selected_model = await self._select_best_model(provider, "completion")

            if selected_model:
                request.model = selected_model
            else:
                logger.error(f"No models available from {provider_name}")
                raise RuntimeError(f"No models available from provider {provider_name}")
        else:
            logger.info(
                f"Using specified model: {request.model}",
                provider=provider_name,
            )

        # Log the actual request being made
        logger.debug(
            f"Sending request to provider {provider_name}",
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            message_count=len(request.messages),
        )

        try:
            # Use retry logic for the completion
            response = await self.retry_strategy.execute_with_retry(
                provider.complete,
                provider_name,
                self._metrics_callback,
                request,
            )

            logger.info(
                f"Successfully completed request with {provider_name}",
                model=response.model,
                provider=response.provider.value if response.provider else "unknown",
                response_length=len(response.content),
            )
            return cast(CompletionResponse, response)
        except LLMError:
            # Re-raise our specific LLM errors
            raise
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as e:
            error_details: ErrorDetails = {
                "error": str(e),
                "error_type": type(e).__name__,
                "model": request.model,
                "provider": provider_name,
            }

            if self.debug_mode:
                error_details["stack_trace"] = traceback.format_exc()

            logger.error(
                f"Provider {provider_name} failed to complete request", **error_details
            )
            raise LLMProviderError(
                message=f"Failed to complete prompt: {e}",
                hint="Check provider configuration and request format",
                details=dict(error_details),
            ) from e

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
            # Use configured default embedding model from settings
            config = get_settings()
            default_model = config.llm_embedding_model or "text-embedding-ada-002"
            request = EmbeddingRequest(
                model=model or default_model,
                input=text,
                dimensions=dimensions or config.llm_embedding_dimensions,
            )

        # Try embedding with fallback logic
        if provider:
            # User specified a specific provider
            provider_instance = self.registry.get_provider(provider)
            if provider_instance and await provider_instance.is_available():
                return await self._try_embed_with_provider(provider_instance, request)
            raise RuntimeError(f"Requested provider {provider.value} is not available")
        # Try providers in fallback order
        return await self.fallback_handler.embed_with_fallback(
            request,
            self._try_embed_with_provider,
            self.metrics.record_fallback_chain,
        )

    async def _try_embed_with_provider(
        self, provider: BaseLLMProvider, request: EmbeddingRequest
    ) -> EmbeddingResponse:
        """Try embedding with a specific provider with model selection and retry."""
        provider_name = provider.__class__.__name__

        # Auto-select model if using default placeholder
        config = get_settings()
        default_model = config.llm_embedding_model or "text-embedding-ada-002"

        # If model is the default and not explicitly configured, auto-select
        if request.model == default_model and not config.llm_embedding_model:
            selected_model = await self._select_best_model(provider, "embedding")
            if selected_model:
                request.model = selected_model

        try:
            # Use retry logic for the embedding
            response = await self.retry_strategy.execute_with_retry(
                provider.embed,
                provider_name,
                self._metrics_callback,
                request,
            )

            logger.info(
                f"Successfully embedded text with {provider_name}",
                model=response.model,
                provider=response.provider.value if response.provider else "unknown",
                embedding_count=len(response.data),
            )
            return cast(EmbeddingResponse, response)
        except LLMError:
            # Re-raise our specific LLM errors
            raise
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as e:
            error_details: ErrorDetails = {
                "error": str(e),
                "error_type": type(e).__name__,
                "model": request.model,
                "provider": provider_name,
            }

            if self.debug_mode:
                error_details["stack_trace"] = traceback.format_exc()

            logger.error(
                f"Provider {provider_name} failed to embed text", **error_details
            )
            raise LLMProviderError(
                message=f"Failed to generate embeddings: {e}",
                hint="Check provider configuration and embedding request format",
                details=dict(error_details),
            ) from e

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

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager and cleanup."""
        await self.cleanup()
