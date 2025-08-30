"""Type definitions for LLM modules."""

from __future__ import annotations

from typing import Any, NotRequired, TypeAlias

from typing_extensions import TypedDict

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


# Client-specific types
class ProviderMetrics(TypedDict):
    """Metrics for a specific LLM provider."""

    provider: str
    success_count: int
    failure_count: int
    retry_count: int
    total_requests: int
    avg_response_time: float


class ClientMetrics(TypedDict):
    """Overall client metrics."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    retry_attempts: int
    fallback_attempts: int
    providers: dict[str, ProviderMetrics]


class ErrorDetails(TypedDict, total=False):
    """Error details for logging and debugging."""

    error: str
    error_type: str
    model: str
    provider: str
    stack_trace: NotRequired[str]


class ModelSelectionCacheEntry(TypedDict):
    """Cache entry for model selection results."""

    model_id: str
    capability_type: str
    timestamp: float
