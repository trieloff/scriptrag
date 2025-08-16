"""Multi-provider LLM client with automatic fallback."""

import asyncio
import time
import traceback
from typing import Any, cast

from scriptrag.config import get_logger
from scriptrag.exceptions import (
    LLMFallbackError,
    LLMRetryableError,
    RateLimitError,
)
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

        # Retry configuration
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.max_retry_delay = max_retry_delay
        self.debug_mode = debug_mode

        # Store credentials (also expose as public for testing)
        self.github_token = self._github_token = github_token
        self.openai_endpoint = self._openai_endpoint = openai_endpoint
        self.openai_api_key = self._openai_api_key = openai_api_key

        # Error tracking for metrics and debugging
        self.provider_metrics: dict[str, Any] = {}
        self._reset_metrics()

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

    def _reset_metrics(self) -> None:
        """Reset provider metrics."""
        self.provider_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "provider_successes": {},
            "provider_failures": {},
            "retry_attempts": 0,
            "fallback_chains": [],
        }

    def _record_success(self, provider_name: str) -> None:
        """Record a successful request for a provider."""
        self.provider_metrics["total_requests"] += 1
        self.provider_metrics["successful_requests"] += 1
        self.provider_metrics["provider_successes"][provider_name] = (
            self.provider_metrics["provider_successes"].get(provider_name, 0) + 1
        )

    def _record_failure(self, provider_name: str, error: Exception) -> None:
        """Record a failed request for a provider."""
        self.provider_metrics["total_requests"] += 1
        self.provider_metrics["failed_requests"] += 1
        if provider_name not in self.provider_metrics["provider_failures"]:
            self.provider_metrics["provider_failures"][provider_name] = []
        self.provider_metrics["provider_failures"][provider_name].append(
            {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "timestamp": time.time(),
            }
        )

    def _record_retry(self) -> None:
        """Record a retry attempt."""
        self.provider_metrics["retry_attempts"] += 1

    def _record_fallback_chain(self, chain: list[str]) -> None:
        """Record a fallback chain for analysis."""
        self.provider_metrics["fallback_chains"].append(
            {
                "chain": chain,
                "timestamp": time.time(),
            }
        )

    def get_metrics(self) -> dict[str, Any]:
        """Get current provider metrics."""
        return self.provider_metrics.copy()

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = min(self.base_retry_delay * (2 ** (attempt - 1)), self.max_retry_delay)
        # Add some jitter to prevent thundering herd
        jitter = delay * 0.1 * (time.time() % 1)
        return float(delay + jitter)

    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable."""
        # Rate limit errors are retryable
        if isinstance(error, RateLimitError):
            return True

        # Network-related errors (connection timeouts, etc.)
        error_message = str(error).lower()
        retryable_keywords = [
            "timeout",
            "connection",
            "network",
            "temporary",
            "unavailable",
            "service unavailable",
            "bad gateway",
            "gateway timeout",
            "internal server error",
            "too many requests",
        ]

        return any(keyword in error_message for keyword in retryable_keywords)

    def _extract_retry_after(self, error: Exception) -> float | None:
        """Extract retry-after information from error."""
        if isinstance(error, RateLimitError):
            return error.retry_after

        # Try to extract from error message
        error_message = str(error).lower()
        if "retry after" in error_message:
            try:
                # Simple regex-like extraction
                import re

                match = re.search(r"retry after (\d+(?:\.\d+)?)", error_message)
                if match:
                    return float(match.group(1))
            except Exception:  # noqa: S110
                pass  # Extracting retry_after is optional, okay to fail

        return None

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

    async def _try_with_retry(
        self,
        operation_func: Any,
        provider_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Try an operation with exponential backoff retry logic."""
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                result = await operation_func(*args, **kwargs)
                self._record_success(provider_name)
                return result
            except Exception as e:
                last_error = e
                self._record_failure(provider_name, e)

                # Check if the error is retryable - do this first
                if not self._is_retryable_error(e):
                    # Non-retryable error - fail immediately
                    raise e

                # If this is the last attempt, don't retry
                if attempt == self.max_retries:
                    break

                # Calculate delay and record retry
                retry_after = self._extract_retry_after(e)
                delay = retry_after or self._calculate_retry_delay(attempt)

                self._record_retry()

                logger.warning(
                    f"Attempt {attempt}/{self.max_retries} failed for {provider_name}, "
                    f"retrying in {delay:.2f}s",
                    error=str(e),
                    error_type=type(e).__name__,
                    provider=provider_name,
                    retry_delay=delay,
                )

                await asyncio.sleep(delay)

        # All attempts failed
        if last_error:
            raise LLMRetryableError(
                f"Provider {provider_name} failed after {self.max_retries} attempts",
                provider=provider_name,
                attempt=self.max_retries,
                max_attempts=self.max_retries,
                original_error=last_error,
            )

        raise RuntimeError(f"Provider {provider_name} failed without error details")

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
            models = await provider.list_models()
            model_count = len(models) if models else 0
            logger.info(
                f"Auto-selecting model from {model_count} available models",
                provider=provider_name,
            )
            if models:
                # Pick first chat-capable model (models sorted by preference)
                for m in models:
                    if "chat" in m.capabilities or "completion" in m.capabilities:
                        request.model = m.id
                        logger.info(
                            f"Auto-selected chat-capable model: {m.id}",
                            provider=provider_name,
                            capabilities=m.capabilities,
                        )
                        break

                # If no chat-capable model found, use the first one
                if not request.model and models:
                    request.model = models[0].id
                    logger.info(
                        f"Using first available model: {models[0].id}",
                        provider=provider_name,
                        capabilities=models[0].capabilities,
                        reason="no chat-capable model found",
                    )
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
            response = await self._try_with_retry(
                provider.complete, provider_name, request
            )

            logger.info(
                f"Successfully completed request with {provider_name}",
                model=response.model,
                provider=response.provider.value if response.provider else "unknown",
                response_length=len(response.content),
            )
            return cast(CompletionResponse, response)
        except Exception as e:
            error_details = {
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
            raise

    async def _complete_with_fallback(
        self, request: CompletionRequest
    ) -> CompletionResponse:
        """Try completion with providers in fallback order with enhanced tracking."""
        provider_errors: dict[str, Exception] = {}
        attempted_providers: list[str] = []
        fallback_chain: list[str] = []
        debug_info: dict[str, Any] = {}

        logger.info(
            "Starting LLM completion with fallback strategy",
            preferred_provider=self.preferred_provider.value
            if self.preferred_provider
            else "none",
            fallback_order=[p.value for p in self.fallback_order],
        )

        # Build the complete fallback chain
        if self.preferred_provider:
            fallback_chain.append(self.preferred_provider.value)
        fallback_chain.extend(
            [p.value for p in self.fallback_order if p != self.preferred_provider]
        )

        # Try preferred provider first
        if self.preferred_provider:
            provider = self.registry.get_provider(self.preferred_provider)
            if provider:
                is_available = await provider.is_available()
                provider_name = provider.__class__.__name__
                attempted_providers.append(self.preferred_provider.value)

                logger.info(
                    f"Checking preferred provider: {provider_name}",
                    is_available=is_available,
                )

                if is_available:
                    try:
                        result = await self._try_complete_with_provider(
                            provider, request
                        )
                        self._record_fallback_chain(fallback_chain)
                        return result
                    except Exception as e:
                        provider_errors[provider_name] = e
                        error_details = {
                            "provider": provider_name,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        }

                        if self.debug_mode:
                            error_details["stack_trace"] = traceback.format_exc()
                            debug_info[f"{self.preferred_provider.value}_error"] = {
                                "exception": e,
                                "stack_trace": traceback.format_exc(),
                                "timestamp": time.time(),
                            }

                        logger.warning("Preferred provider failed", **error_details)
                else:
                    error_msg = f"Provider {provider_name} not available"
                    provider_errors[provider_name] = RuntimeError(error_msg)
                    logger.warning(error_msg)
            else:
                error_msg = (
                    f"Preferred provider {self.preferred_provider.value} "
                    "not found in registry"
                )
                provider_errors[self.preferred_provider.value] = RuntimeError(error_msg)
                attempted_providers.append(self.preferred_provider.value)
                logger.warning(error_msg)

        # Try fallback providers in order
        for provider_type in self.fallback_order:
            if provider_type == self.preferred_provider:
                logger.debug(
                    f"Skipping {provider_type.value} (already tried as preferred)"
                )
                continue  # Already tried

            provider = self.registry.get_provider(provider_type)
            if provider:
                is_available = await provider.is_available()
                provider_name = provider.__class__.__name__
                attempted_providers.append(provider_type.value)

                logger.info(
                    f"Checking fallback provider: {provider_name}",
                    is_available=is_available,
                )

                if is_available:
                    try:
                        result = await self._try_complete_with_provider(
                            provider, request
                        )
                        self._record_fallback_chain(fallback_chain)
                        return result
                    except Exception as e:
                        provider_errors[provider_name] = e
                        error_details = {
                            "provider": provider_name,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        }

                        if self.debug_mode:
                            error_details["stack_trace"] = traceback.format_exc()
                            debug_info[f"{provider_type.value}_error"] = {
                                "exception": e,
                                "stack_trace": traceback.format_exc(),
                                "timestamp": time.time(),
                            }

                        logger.warning(
                            f"Fallback provider {provider_name} failed", **error_details
                        )
                else:
                    error_msg = f"Fallback provider {provider_name} not available"
                    provider_errors[provider_name] = RuntimeError(error_msg)
                    logger.debug(error_msg)
            else:
                error_msg = (
                    f"Fallback provider {provider_type.value} not found in registry"
                )
                provider_errors[provider_type.value] = RuntimeError(error_msg)
                attempted_providers.append(provider_type.value)
                logger.debug(error_msg)

        # Record the failed fallback chain
        self._record_fallback_chain(fallback_chain)

        # All providers failed - create comprehensive error
        logger.error(
            "All LLM providers failed",
            provider_errors={k: str(v) for k, v in provider_errors.items()},
            attempted_providers=attempted_providers,
            fallback_chain=fallback_chain,
        )

        raise LLMFallbackError(
            message="All LLM providers failed",
            provider_errors=provider_errors,
            attempted_providers=attempted_providers,
            fallback_chain=fallback_chain,
            debug_info=debug_info if self.debug_mode else None,
        )

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
        """Try embedding with a specific provider with model selection and retry."""
        provider_name = provider.__class__.__name__

        # Update model if not specified
        if request.model == "text-embedding-ada-002":  # Our temporary fallback
            models = await provider.list_models()
            if models:
                # Pick first embedding-capable model
                for m in models:
                    if "embedding" in m.capabilities:
                        request.model = m.id
                        break

        try:
            # Use retry logic for the embedding
            response = await self._try_with_retry(
                provider.embed, provider_name, request
            )

            logger.info(
                f"Successfully embedded text with {provider_name}",
                model=response.model,
                provider=response.provider.value if response.provider else "unknown",
                embedding_count=len(response.data),
            )
            return cast(EmbeddingResponse, response)
        except Exception as e:
            error_details = {
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
            raise

    async def _embed_with_fallback(
        self, request: EmbeddingRequest
    ) -> EmbeddingResponse:
        """Try embedding with providers in fallback order with enhanced tracking."""
        provider_errors: dict[str, Exception] = {}
        attempted_providers: list[str] = []
        fallback_chain: list[str] = []
        debug_info: dict[str, Any] = {}

        # Build the complete fallback chain
        if self.preferred_provider:
            fallback_chain.append(self.preferred_provider.value)
        fallback_chain.extend(
            [p.value for p in self.fallback_order if p != self.preferred_provider]
        )

        # Try preferred provider first
        if self.preferred_provider:
            provider = self.registry.get_provider(self.preferred_provider)
            if provider and await provider.is_available():
                provider_name = provider.__class__.__name__
                attempted_providers.append(self.preferred_provider.value)

                try:
                    result = await self._try_embed_with_provider(provider, request)
                    self._record_fallback_chain(fallback_chain)
                    return result
                except Exception as e:
                    provider_errors[provider_name] = e
                    error_details = {
                        "provider": provider_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }

                    if self.debug_mode:
                        error_details["stack_trace"] = traceback.format_exc()
                        debug_info[f"{self.preferred_provider.value}_error"] = {
                            "exception": e,
                            "stack_trace": traceback.format_exc(),
                            "timestamp": time.time(),
                        }

                    logger.debug(
                        f"Preferred provider {provider_name} failed", **error_details
                    )

        # Try fallback providers in order
        for provider_type in self.fallback_order:
            if provider_type == self.preferred_provider:
                continue  # Already tried

            provider = self.registry.get_provider(provider_type)
            if provider and await provider.is_available():
                provider_name = provider.__class__.__name__
                attempted_providers.append(provider_type.value)

                try:
                    result = await self._try_embed_with_provider(provider, request)
                    self._record_fallback_chain(fallback_chain)
                    return result
                except Exception as e:
                    provider_errors[provider_name] = e
                    error_details = {
                        "provider": provider_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }

                    if self.debug_mode:
                        error_details["stack_trace"] = traceback.format_exc()
                        debug_info[f"{provider_type.value}_error"] = {
                            "exception": e,
                            "stack_trace": traceback.format_exc(),
                            "timestamp": time.time(),
                        }

                    logger.debug(
                        f"Fallback provider {provider_name} failed", **error_details
                    )

        # Record the failed fallback chain
        self._record_fallback_chain(fallback_chain)

        # All providers failed - create comprehensive error
        raise LLMFallbackError(
            message="All LLM providers failed for embedding",
            provider_errors=provider_errors,
            attempted_providers=attempted_providers,
            fallback_chain=fallback_chain,
            debug_info=debug_info if self.debug_mode else None,
        )

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
