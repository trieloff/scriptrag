"""Metrics tracking for LLM operations."""

import time
from typing import Any


class LLMMetrics:
    """Track metrics for LLM provider operations."""

    def __init__(self) -> None:
        """Initialize metrics tracker."""
        self.provider_metrics: dict[str, Any] = {}
        self.reset()

    def reset(self) -> None:
        """Reset all metrics."""
        self.provider_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "provider_successes": {},
            "provider_failures": {},
            "retry_attempts": 0,
            "fallback_chains": [],
        }

    def record_success(self, provider_name: str) -> None:
        """Record a successful request for a provider."""
        self.provider_metrics["total_requests"] += 1
        self.provider_metrics["successful_requests"] += 1
        self.provider_metrics["provider_successes"][provider_name] = (
            self.provider_metrics["provider_successes"].get(provider_name, 0) + 1
        )

    def record_failure(self, provider_name: str, error: Exception) -> None:
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

    def record_retry(self) -> None:
        """Record a retry attempt."""
        self.provider_metrics["retry_attempts"] += 1

    def record_fallback_chain(self, chain: list[str]) -> None:
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
