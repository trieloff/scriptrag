"""Retry strategy for LLM operations."""

import asyncio
import re
import time
from collections.abc import Callable
from typing import Any, TypeVar

from scriptrag.config import get_logger
from scriptrag.exceptions import LLMRetryableError, RateLimitError

logger = get_logger(__name__)

T = TypeVar("T")


class RetryStrategy:
    """Handles retry logic with exponential backoff for LLM operations."""

    def __init__(
        self,
        max_retries: int = 3,
        base_retry_delay: float = 1.0,
        max_retry_delay: float = 10.0,
    ) -> None:
        """Initialize retry strategy.

        Args:
            max_retries: Maximum number of retry attempts.
            base_retry_delay: Base delay in seconds for exponential backoff.
            max_retry_delay: Maximum delay in seconds for exponential backoff.
        """
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.max_retry_delay = max_retry_delay

    def calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = min(self.base_retry_delay * (2 ** (attempt - 1)), self.max_retry_delay)
        # Add some jitter to prevent thundering herd
        # Use both fractional part and a hash-based component for better variation
        time_fraction = time.time() % 1
        # Add hash-based jitter using attempt number to ensure variation even
        # with mocked time
        hash_jitter = (hash(f"{attempt}_{time.time()}") % 1000) / 10000.0
        jitter = delay * 0.1 * max(time_fraction, hash_jitter)
        return float(delay + jitter)

    def is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable."""
        # Rate limit errors are retryable
        if isinstance(error, RateLimitError):
            return True

        # Common retryable exception types
        retryable_types = (
            ConnectionError,
            TimeoutError,
            # Add other timeout-related exceptions
        )
        if isinstance(error, retryable_types):
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

    def extract_retry_after(self, error: Exception) -> float | None:
        """Extract retry-after information from error."""
        if isinstance(error, RateLimitError):
            return error.retry_after

        # Try to extract from error message
        error_message = str(error).lower()
        if "retry after" in error_message:
            try:
                match = re.search(r"retry after (\d+(?:\.\d+)?)", error_message)
                if match:
                    return float(match.group(1))
            except (ValueError, AttributeError, TypeError):
                pass  # Extracting retry_after is optional, okay to fail

        return None

    async def execute_with_retry(
        self,
        operation_func: Callable[..., Any],
        provider_name: str,
        metrics_callback: Callable[[str, Exception | None], None] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute an operation with exponential backoff retry logic.

        Args:
            operation_func: Async function to execute.
            provider_name: Name of the provider for logging.
            metrics_callback: Optional callback for metrics recording.
            *args: Positional arguments for operation_func.
            **kwargs: Keyword arguments for operation_func.

        Returns:
            Result from operation_func.

        Raises:
            LLMRetryableError: If all retry attempts fail.
        """
        last_error = None

        # Always try at least once, even with max_retries=0
        # In this codebase, max_retries actually means max total attempts
        # max_retries=3 means 3 total attempts (not 1 initial + 3 retries)
        # max_retries=0 means 1 attempt (no retries)
        total_attempts = max(1, self.max_retries)

        for attempt in range(1, total_attempts + 1):
            try:
                result = await operation_func(*args, **kwargs)
                if metrics_callback:
                    metrics_callback(provider_name, None)
                return result
            except Exception as e:
                last_error = e
                if metrics_callback:
                    metrics_callback(provider_name, e)

                # Check if the error is retryable - do this first
                if not self.is_retryable_error(e):
                    # Non-retryable error - fail immediately
                    raise e

                # If this is the last attempt, don't retry
                if attempt >= total_attempts:
                    break

                # Calculate delay and record retry
                retry_after = self.extract_retry_after(e)
                delay = retry_after or self.calculate_retry_delay(attempt)

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
