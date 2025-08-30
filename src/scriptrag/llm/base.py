"""Base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
    Model,
)


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""

    provider_type: LLMProvider

    @abstractmethod
    async def list_models(self) -> list[Model]:
        """List available models."""
        pass

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate text completion."""
        pass

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate text embeddings."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is available."""
        pass
