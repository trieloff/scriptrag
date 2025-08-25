"""Rate limiting utilities for LLM providers."""

import json
import re
import time
from typing import Any

from scriptrag.config import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Manages rate limiting for API calls."""

    def __init__(self) -> None:
        """Initialize rate limiter."""
        self._rate_limit_reset_time: float = 0
        self._availability_cache: bool | None = None
        self._cache_timestamp: float = 0

    def is_rate_limited(self) -> bool:
        """Check if currently rate limited.

        Returns:
            True if rate limited, False otherwise
        """
        if (
            self._rate_limit_reset_time > 0
            and time.time() < self._rate_limit_reset_time
        ):
            logger.debug(
                "API rate limited",
                reset_time=self._rate_limit_reset_time,
                seconds_until_reset=self._rate_limit_reset_time - time.time(),
            )
            return True
        return False

    def set_rate_limit(self, wait_seconds: int, provider: str = "API") -> None:
        """Set rate limit reset time.

        Args:
            wait_seconds: Number of seconds to wait
            provider: Name of the provider for logging
        """
        self._rate_limit_reset_time = time.time() + wait_seconds
        self._availability_cache = False
        self._cache_timestamp = time.time()
        logger.warning(
            f"{provider} rate limited",
            wait_seconds=wait_seconds,
            reset_time=self._rate_limit_reset_time,
        )

    def check_availability_cache(self, cache_ttl: int = 300) -> bool | None:
        """Check cached availability status.

        Args:
            cache_ttl: Cache time-to-live in seconds (default 5 minutes)

        Returns:
            Cached availability status or None if cache expired
        """
        if (
            self._availability_cache is not None
            and (time.time() - self._cache_timestamp) < cache_ttl
        ):
            logger.debug(
                "Using cached availability",
                is_available=self._availability_cache,
                cache_age=time.time() - self._cache_timestamp,
            )
            return self._availability_cache
        return None

    def update_availability_cache(self, is_available: bool) -> None:
        """Update availability cache.

        Args:
            is_available: Current availability status
        """
        self._availability_cache = is_available
        self._cache_timestamp = time.time()


class GitHubRateLimitParser:
    """Parse GitHub Models rate limit errors."""

    @staticmethod
    def parse_rate_limit_error(error_text: str) -> int | None:
        """Parse rate limit error and return seconds to wait.

        Args:
            error_text: Error response text from API

        Returns:
            Number of seconds to wait, or None if not a rate limit error
        """
        try:
            # Parse JSON error response
            error_data: dict[str, Any] = json.loads(error_text)
            if "error" in error_data:
                error_info = error_data["error"]
                if error_info.get("code") == "RateLimitReached":
                    # Extract wait time from message
                    # "Please wait 42911 seconds before retrying."
                    message: str = error_info.get("message", "")
                    match = re.search(r"wait (\d+) seconds", message)
                    if match:
                        return int(match.group(1))
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
        return None


class RetryHandler:
    """Handle retry logic for API calls."""

    def __init__(self, max_retries: int = 3) -> None:
        """Initialize retry handler.

        Args:
            max_retries: Maximum number of retry attempts
        """
        self.max_retries = max_retries

    def should_retry(self, attempt: int, error: Exception | None = None) -> bool:
        """Check if should retry based on attempt number and error.

        Args:
            attempt: Current attempt number (0-indexed)
            error: Optional error that occurred

        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.max_retries - 1:
            return False

        # Add specific error checking if needed
        if error:
            # Could check for specific retryable errors
            logger.debug(
                f"Retry check for attempt {attempt + 1}/{self.max_retries}",
                error_type=type(error).__name__,
            )

        return True

    def log_retry(self, attempt: int, reason: str = "") -> None:
        """Log retry attempt.

        Args:
            attempt: Current attempt number (0-indexed)
            reason: Optional reason for retry
        """
        logger.info(
            f"Retrying (attempt {attempt + 2}/{self.max_retries})",
            reason=reason if reason else "Previous attempt failed",
        )
