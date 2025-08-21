"""Type definitions for LLM modules."""

from typing import Any, TypeAlias, TypedDict

# Provider configuration types
ProviderConfig: TypeAlias = dict[str, Any]
ModelConfig: TypeAlias = dict[str, Any]


# LLM response types
class LLMUsage(TypedDict, total=False):
    """Usage statistics from LLM calls."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LLMChoice(TypedDict):
    """A choice from LLM completion."""

    index: int
    message: dict[str, str]
    finish_reason: str


class LLMCompletion(TypedDict):
    """LLM completion response structure."""

    id: str
    object: str
    created: int
    model: str
    choices: list[LLMChoice]
    usage: LLMUsage


# Retry and fallback types
class RetryAttempt(TypedDict):
    """Information about a retry attempt."""

    attempt: int
    provider: str
    error: str
    wait_time: float


class FallbackResult(TypedDict):
    """Result from fallback operation."""

    success: bool
    provider: str
    attempts: list[RetryAttempt]
    final_result: Any | None


# Model discovery types
class ModelInfo(TypedDict, total=False):
    """Generic model information."""

    id: str
    name: str
    provider: str
    context_window: int
    max_output_tokens: int
    capabilities: list[str]
    pricing: dict[str, float]
