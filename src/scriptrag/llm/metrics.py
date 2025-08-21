"""Metrics tracking for LLM operations."""

import time

from typing_extensions import TypedDict

from scriptrag.llm.types import ClientMetrics


class FailureEntry(TypedDict):
    """Structure for recording failure details."""

    error_type: str
    error_message: str
    timestamp: float


class FallbackChain(TypedDict):
    """Structure for recording fallback chain details."""

    chain: list[str]
    timestamp: float


class LLMProviderMetrics(TypedDict):
    """Structure for internal provider metrics data."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    provider_successes: dict[str, int]
    provider_failures: dict[str, list[FailureEntry]]
    retry_attempts: int
    fallback_chains: list[FallbackChain]


class LLMMetrics:
    """Track metrics for LLM provider operations with memory limits."""

    # Maximum number of failure entries per provider to prevent memory growth
    MAX_FAILURE_ENTRIES = 100
    # Maximum number of fallback chains to store
    MAX_FALLBACK_CHAINS = 50

    def __init__(self) -> None:
        """Initialize metrics tracker."""
        self.provider_metrics: LLMProviderMetrics
        self.reset()

    def reset(self) -> None:
        """Reset all metrics."""
        self.provider_metrics = LLMProviderMetrics(
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            provider_successes={},
            provider_failures={},
            retry_attempts=0,
            fallback_chains=[],
        )

    def record_success(self, provider_name: str) -> None:
        """Record a successful request for a provider."""
        self.provider_metrics["total_requests"] += 1
        self.provider_metrics["successful_requests"] += 1
        self.provider_metrics["provider_successes"][provider_name] = (
            self.provider_metrics["provider_successes"].get(provider_name, 0) + 1
        )

    def record_failure(self, provider_name: str, error: Exception) -> None:
        """Record a failed request for a provider with sliding window."""
        self.provider_metrics["total_requests"] += 1
        self.provider_metrics["failed_requests"] += 1
        if provider_name not in self.provider_metrics["provider_failures"]:
            self.provider_metrics["provider_failures"][provider_name] = []

        failures = self.provider_metrics["provider_failures"][provider_name]
        failure_entry = FailureEntry(
            error_type=type(error).__name__,
            error_message=str(error),
            timestamp=time.time(),
        )
        failures.append(failure_entry)

        # Implement sliding window to prevent unbounded memory growth
        if len(failures) > self.MAX_FAILURE_ENTRIES:
            # Keep only the most recent entries
            self.provider_metrics["provider_failures"][provider_name] = failures[
                -self.MAX_FAILURE_ENTRIES :
            ]

    def record_retry(self) -> None:
        """Record a retry attempt."""
        self.provider_metrics["retry_attempts"] += 1

    def record_fallback_chain(self, chain: list[str]) -> None:
        """Record a fallback chain for analysis with sliding window."""
        fallback_chain = FallbackChain(
            chain=chain,
            timestamp=time.time(),
        )
        self.provider_metrics["fallback_chains"].append(fallback_chain)

        # Implement sliding window to prevent unbounded memory growth
        if len(self.provider_metrics["fallback_chains"]) > self.MAX_FALLBACK_CHAINS:
            # Keep only the most recent chains
            self.provider_metrics["fallback_chains"] = self.provider_metrics[
                "fallback_chains"
            ][-self.MAX_FALLBACK_CHAINS :]

    def get_metrics(self) -> ClientMetrics:
        """Get current provider metrics."""
        # Convert internal metrics format to ClientMetrics format
        from scriptrag.llm.types import ProviderMetrics as ClientProviderMetrics

        provider_metrics: dict[str, ClientProviderMetrics] = {}

        # Get all provider names from both successes and failures
        all_providers = set(self.provider_metrics["provider_successes"].keys()) | set(
            self.provider_metrics["provider_failures"].keys()
        )

        for provider_name in all_providers:
            success_count = self.provider_metrics["provider_successes"].get(
                provider_name, 0
            )
            failure_count = len(
                self.provider_metrics["provider_failures"].get(provider_name, [])
            )

            provider_metrics[provider_name] = {
                "provider": provider_name,
                "success_count": success_count,
                "failure_count": failure_count,
                "retry_count": self.provider_metrics[
                    "retry_attempts"
                ],  # Shared across all providers
                "total_requests": success_count + failure_count,
                "avg_response_time": 0.0,  # Not currently tracked
            }

        return ClientMetrics(
            total_requests=self.provider_metrics["total_requests"],
            successful_requests=self.provider_metrics["successful_requests"],
            failed_requests=self.provider_metrics["failed_requests"],
            retry_attempts=self.provider_metrics["retry_attempts"],
            fallback_attempts=len(self.provider_metrics["fallback_chains"]),
            providers=provider_metrics,
        )

    def cleanup_old_metrics(self, max_age_seconds: float = 3600) -> None:
        """Remove metrics older than specified age.

        Args:
            max_age_seconds: Maximum age in seconds for metrics to keep (default 1 hour)
        """
        current_time = time.time()

        # Clean up old failure entries
        for provider in self.provider_metrics["provider_failures"]:
            failures = self.provider_metrics["provider_failures"][provider]
            self.provider_metrics["provider_failures"][provider] = [
                f for f in failures if current_time - f["timestamp"] <= max_age_seconds
            ]

        # Clean up old fallback chains
        self.provider_metrics["fallback_chains"] = [
            chain
            for chain in self.provider_metrics["fallback_chains"]
            if current_time - chain["timestamp"] <= max_age_seconds
        ]
