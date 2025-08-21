"""Protocol definitions for LLM providers and related interfaces."""

from typing import Any, Protocol, runtime_checkable

from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    Model,
)


@runtime_checkable
class LLMProviderProtocol(Protocol):
    """Protocol for LLM provider implementations."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate a completion for the given request."""
        ...

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate embeddings for the given request."""
        ...

    async def list_models(self) -> list[Model]:
        """List available models from this provider."""
        ...

    async def is_available(self) -> bool:
        """Check if the provider is available and configured."""
        ...


@runtime_checkable
class ModelDiscoveryProtocol(Protocol):
    """Protocol for model discovery implementations."""

    async def discover_models(self) -> list[Model]:
        """Discover available models from the provider."""
        ...


@runtime_checkable
class MetricsProtocol(Protocol):
    """Protocol for metrics tracking."""

    def record_success(self, provider_name: str) -> None:
        """Record a successful request."""
        ...

    def record_failure(self, provider_name: str, error: Exception) -> None:
        """Record a failed request."""
        ...

    def record_retry(self) -> None:
        """Record a retry attempt."""
        ...

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics."""
        ...
