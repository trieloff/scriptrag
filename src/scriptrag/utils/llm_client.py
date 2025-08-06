"""Multi-provider LLM client with automatic fallback.

This module provides backward compatibility by re-exporting the refactored
LLM client components from the new modular structure.
"""

# Re-export everything from the new modular structure
from scriptrag.llm import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMClient,
    LLMProvider,
    Model,
)
from scriptrag.llm.base import BaseLLMProvider
from scriptrag.llm.providers import (
    ClaudeCodeProvider,
    GitHubModelsProvider,
    OpenAICompatibleProvider,
)

__all__ = [
    "BaseLLMProvider",
    "ClaudeCodeProvider",
    "CompletionRequest",
    "CompletionResponse",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "GitHubModelsProvider",
    "LLMClient",
    "LLMProvider",
    "Model",
    "OpenAICompatibleProvider",
]
