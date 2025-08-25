"""Comprehensive unit tests for rate_limiter.py to achieve 99% code coverage.

Tests focusing on missing coverage lines:
- Lines 32-37: is_rate_limited debug logging and return True path
- Lines 69-74: check_availability_cache debug logging and return cached value path
- Lines 100-114: GitHubRateLimitParser parse_rate_limit_error exception handling paths
- Line 126: RetryHandler should_retry at max boundary conditions
- Lines 138-149: RetryHandler should_retry with error and debug logging
- Line 158: RetryHandler log_retry with custom reason
"""

import json
import time
from unittest.mock import Mock, patch

import pytest

from scriptrag.llm.rate_limiter import (
    GitHubRateLimitParser,
    RateLimiter,
    RetryHandler,
)


class TestRateLimiterCompleteCoverage:
    """Comprehensive tests for RateLimiter to achieve complete coverage."""

    def test_is_rate_limited_debug_logging_path(self):
        """Test is_rate_limited debug logging and True return path (lines 32-37)."""
        rate_limiter = RateLimiter()

        # Set rate limit for future time to ensure True path
        future_time = time.time() + 60  # 60 seconds in future
        rate_limiter._rate_limit_reset_time = future_time

        # Mock logger to verify debug logging is called
        with patch("scriptrag.llm.rate_limiter.logger") as mock_logger:
            result = rate_limiter.is_rate_limited()

            # Should return True since we're rate limited
            assert result is True

            # Verify debug logging was called with correct parameters
            mock_logger.debug.assert_called_once_with(
                "API rate limited",
                reset_time=future_time,
                seconds_until_reset=pytest.approx(
                    60, abs=1
                ),  # Allow 1 second tolerance
            )

    def test_is_rate_limited_exactly_at_reset_time(self):
        """Test is_rate_limited exactly at reset time boundary."""
        rate_limiter = RateLimiter()

        # Set reset time to current time (edge case)
        current_time = time.time()
        rate_limiter._rate_limit_reset_time = current_time

        # At exactly the reset time, should still be rate limited
        # Due to the < comparison in line 30
        with patch("time.time", return_value=current_time):
            result = rate_limiter.is_rate_limited()
            # At exactly reset time, time < reset_time is False, so not rate limited
            assert result is False

    def test_check_availability_cache_debug_logging_path(self):
        """Test check_availability_cache debug logging and cached return (69-74)."""
        rate_limiter = RateLimiter()

        # Set up cache with valid data
        current_time = time.time()
        rate_limiter._availability_cache = True
        rate_limiter._cache_timestamp = current_time - 100  # 100 seconds ago

        # Mock logger to verify debug logging
        with patch("scriptrag.llm.rate_limiter.logger") as mock_logger:
            # Use cache TTL of 300 seconds, so 100 seconds old is still valid
            result = rate_limiter.check_availability_cache(cache_ttl=300)

            # Should return the cached value
            assert result is True

            # Verify debug logging was called
            mock_logger.debug.assert_called_once_with(
                "Using cached availability",
                is_available=True,
                cache_age=pytest.approx(100, abs=1),  # Allow 1 second tolerance
            )

    def test_check_availability_cache_false_value_debug_logging(self):
        """Test debug logging path when cached value is False."""
        rate_limiter = RateLimiter()

        # Set up cache with False value
        current_time = time.time()
        rate_limiter._availability_cache = False  # False value
        rate_limiter._cache_timestamp = current_time - 50  # 50 seconds ago

        with patch("scriptrag.llm.rate_limiter.logger") as mock_logger:
            result = rate_limiter.check_availability_cache(cache_ttl=300)

            # Should return the cached False value
            assert result is False

            # Verify debug logging was called with is_available=False
            mock_logger.debug.assert_called_once_with(
                "Using cached availability",
                is_available=False,
                cache_age=pytest.approx(50, abs=1),
            )


class TestGitHubRateLimitParserCompleteErrors:
    """Test GitHubRateLimitParser error handling paths (lines 100-114)."""

    def test_parse_rate_limit_error_json_decode_error(self):
        """Test JSONDecodeError handling (line 112-113)."""
        # Invalid JSON should trigger JSONDecodeError
        invalid_json = '{"error": {"code": "RateLimited"}'  # Missing braces

        result = GitHubRateLimitParser.parse_rate_limit_error(invalid_json)

        # Should return None due to JSONDecodeError exception
        assert result is None

    def test_parse_rate_limit_error_key_error(self):
        """Test KeyError handling (line 112-113)."""
        # JSON with missing "error" key
        json_missing_error = json.dumps(
            {"status": "failed", "message": "wait 456 seconds"}
        )

        result = GitHubRateLimitParser.parse_rate_limit_error(json_missing_error)

        # Should return None due to KeyError exception
        assert result is None

    def test_parse_rate_limit_error_value_error(self):
        """Test ValueError handling (line 112-113)."""
        # Valid JSON structure but invalid integer in regex match
        # We need to trigger ValueError in int() conversion
        error_text = json.dumps(
            {
                "error": {
                    "code": "RateLimitReached",
                    "message": "Please wait not_a_number seconds before retrying.",
                }
            }
        )

        # This will match regex but int() will fail
        with patch("re.search") as mock_search:
            mock_match = Mock()
            mock_match.group.return_value = "not_a_number"  # Invalid int
            mock_search.return_value = mock_match

            result = GitHubRateLimitParser.parse_rate_limit_error(error_text)

            # Should return None due to ValueError in int() conversion
            assert result is None

    def test_parse_rate_limit_error_nested_key_error(self):
        """Test KeyError on nested dictionary access."""
        # JSON with "error" key but missing nested keys
        error_text = json.dumps(
            {
                "error": {}  # Missing "code" and "message" keys
            }
        )

        result = GitHubRateLimitParser.parse_rate_limit_error(error_text)

        # Should return None due to KeyError on error_info.get()
        assert result is None

    def test_parse_rate_limit_error_no_regex_match(self):
        """Test case where regex doesn't match."""
        error_text = json.dumps(
            {
                "error": {
                    "code": "RateLimitReached",
                    "message": "Rate limit reached. Please retry later.",  # No pattern
                }
            }
        )

        result = GitHubRateLimitParser.parse_rate_limit_error(error_text)

        # Should return None when regex doesn't match
        assert result is None

    def test_parse_rate_limit_error_success_path(self):
        """Test successful parsing to ensure we don't break the happy path."""
        error_text = json.dumps(
            {
                "error": {
                    "code": "RateLimitReached",
                    "message": "Please wait 789 seconds before retrying.",
                }
            }
        )

        result = GitHubRateLimitParser.parse_rate_limit_error(error_text)

        # Should successfully parse and return the wait time
        assert result == 789


class TestRetryHandlerCompleteEdgeCases:
    """Test RetryHandler edge cases and error handling paths."""

    def test_should_retry_exactly_at_max_retries_boundary(self):
        """Test should_retry exactly at max_retries boundary (line 138)."""
        # Test the boundary condition: attempt >= self.max_retries - 1
        handler = RetryHandler(max_retries=3)

        # attempt = 2, max_retries = 3, so 2 >= 3-1 (2) is True -> should return False
        result = handler.should_retry(2)  # Third attempt (0-indexed)
        assert result is False

        # attempt = 1, max_retries = 3, so 1 >= 3-1 (2) is False -> continue
        result = handler.should_retry(1)  # Second attempt
        assert result is True

    def test_should_retry_with_error_debug_logging(self):
        """Test should_retry with error parameter and debug logging (lines 142-149)."""
        handler = RetryHandler(max_retries=5)

        test_error = ValueError("Test error message")

        # Mock logger to capture debug logging
        with patch("scriptrag.llm.rate_limiter.logger") as mock_logger:
            # Test with error at valid attempt number
            result = handler.should_retry(2, error=test_error)  # attempt 2 with max 5

            # Should return True (can retry)
            assert result is True

            # Verify debug logging was called with error information
            mock_logger.debug.assert_called_once_with(
                "Retry check for attempt 3/5",  # attempt+1 for human-readable numbering
                error_type="ValueError",
            )

    def test_should_retry_with_different_error_types_debug_logging(self):
        """Test debug logging with various error types."""
        handler = RetryHandler(max_retries=4)

        error_types = [
            (ConnectionError("Connection failed"), "ConnectionError"),
            (TimeoutError("Request timeout"), "TimeoutError"),
            (RuntimeError("Runtime issue"), "RuntimeError"),
            (Exception("Generic exception"), "Exception"),
        ]

        for error, expected_type_name in error_types:
            with patch("scriptrag.llm.rate_limiter.logger") as mock_logger:
                result = handler.should_retry(1, error=error)

                assert result is True  # All should allow retry at attempt 1

                mock_logger.debug.assert_called_once_with(
                    "Retry check for attempt 2/4",
                    error_type=expected_type_name,
                )

    def test_should_retry_with_error_at_boundary(self):
        """Test should_retry with error at max retry boundary."""
        handler = RetryHandler(max_retries=2)

        test_error = ConnectionError("Network issue")

        with patch("scriptrag.llm.rate_limiter.logger") as mock_logger:
            # At max boundary with error - should return False and not log
            result = handler.should_retry(1, error=test_error)  # attempt 1 with max 2

            # Should return False (max retries reached)
            assert result is False

            # Debug logging should NOT be called because we return early
            mock_logger.debug.assert_not_called()

    def test_log_retry_with_custom_reason(self):
        """Test log_retry with custom reason string (line 158)."""
        handler = RetryHandler(max_retries=3)

        custom_reason = "API rate limit exceeded"

        with patch("scriptrag.llm.rate_limiter.logger") as mock_logger:
            handler.log_retry(1, reason=custom_reason)  # attempt 1 (second attempt)

            # Verify info logging with custom reason
            mock_logger.info.assert_called_once_with(
                "Retrying (attempt 3/3)",  # attempt+2 for human-readable numbering
                reason=custom_reason,
            )

    def test_log_retry_with_empty_string_reason(self):
        """Test log_retry with empty string reason."""
        handler = RetryHandler(max_retries=4)

        with patch("scriptrag.llm.rate_limiter.logger") as mock_logger:
            handler.log_retry(2, reason="")  # Empty reason

            # Should use default reason when empty string provided
            mock_logger.info.assert_called_once_with(
                "Retrying (attempt 4/4)",
                reason="Previous attempt failed",  # Default reason for empty string
            )

    def test_log_retry_no_reason_parameter(self):
        """Test log_retry without reason parameter (default)."""
        handler = RetryHandler(max_retries=5)

        with patch("scriptrag.llm.rate_limiter.logger") as mock_logger:
            handler.log_retry(3)  # No reason parameter

            # Should use default reason
            mock_logger.info.assert_called_once_with(
                "Retrying (attempt 5/5)",
                reason="Previous attempt failed",
            )


@pytest.mark.parametrize("max_retries", [0, 1, 2, 5, 10])
def test_retry_handler_various_max_retries(max_retries):
    """Test RetryHandler with various max_retries values."""
    handler = RetryHandler(max_retries=max_retries)

    assert handler.max_retries == max_retries

    if max_retries <= 1:
        # With 0 or 1 max_retries, no retries should be allowed
        assert handler.should_retry(0) is False
    else:
        # With more than 1 max_retries, first attempt should allow retry
        assert handler.should_retry(0) is True
        # Last allowed attempt should not allow retry
        assert handler.should_retry(max_retries - 1) is False


@pytest.mark.parametrize(
    "cache_ttl,expected_result",
    [
        (0, None),  # TTL of 0 means immediate expiration
        (1, None),  # Very short TTL
        (300, True),  # Standard 5-minute TTL should return cached value
        (3600, True),  # Long TTL should return cached value
    ],
)
def test_rate_limiter_cache_ttl_variations(cache_ttl, expected_result):
    """Test rate limiter cache with various TTL values."""
    rate_limiter = RateLimiter()

    # Set cache 2 seconds ago
    rate_limiter._availability_cache = True
    rate_limiter._cache_timestamp = time.time() - 2

    result = rate_limiter.check_availability_cache(cache_ttl=cache_ttl)
    assert result == expected_result


class TestRateLimiterCompleteInitialization:
    """Test RateLimiter initialization and state management."""

    def test_rate_limiter_initial_state(self):
        """Test RateLimiter initial state."""
        rate_limiter = RateLimiter()

        # Verify initial state
        assert rate_limiter._rate_limit_reset_time == 0
        assert rate_limiter._availability_cache is None
        assert rate_limiter._cache_timestamp == 0

        # Should not be rate limited initially
        assert rate_limiter.is_rate_limited() is False

    def test_set_rate_limit_cache_invalidation(self):
        """Test set_rate_limit properly invalidates cache."""
        rate_limiter = RateLimiter()

        # Set initial cache state
        rate_limiter._availability_cache = True
        rate_limiter._cache_timestamp = time.time() - 100

        # Set rate limit should invalidate cache
        with patch("scriptrag.llm.rate_limiter.logger"):
            rate_limiter.set_rate_limit(60, "TestProvider")

        # Cache should be invalidated (set to False)
        assert rate_limiter._availability_cache is False
        # Cache timestamp should be updated to current time
        assert rate_limiter._cache_timestamp > 0

    def test_update_availability_cache_timestamp_update(self):
        """Test update_availability_cache updates timestamp."""
        rate_limiter = RateLimiter()

        original_timestamp = rate_limiter._cache_timestamp

        # Update cache
        rate_limiter.update_availability_cache(True)

        # Timestamp should be updated
        assert rate_limiter._cache_timestamp > original_timestamp
        assert rate_limiter._availability_cache is True
