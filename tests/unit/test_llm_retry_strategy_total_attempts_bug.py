"""Test for retry strategy total_attempts bug fix.

This test module specifically tests the fix for the bug where logging and error
messages incorrectly used self.max_retries instead of total_attempts, leading to
misleading messages when max_retries=0 (which means 1 total attempt).
"""

from unittest.mock import patch

import pytest

from scriptrag.exceptions import LLMRetryableError, RateLimitError
from scriptrag.llm.retry_strategy import RetryStrategy


class TestRetryStrategyTotalAttemptsBug:
    """Test the fix for total_attempts vs max_retries confusion."""

    @pytest.mark.asyncio
    async def test_zero_retries_correct_logging_message(self):
        """Test that max_retries=0 logs correct attempt count (1, not 0)."""
        strategy = RetryStrategy(max_retries=0)

        async def mock_func():
            raise ConnectionError("Connection timeout")

        # Capture the actual log message
        with patch("scriptrag.llm.retry_strategy.logger") as mock_logger:
            with patch("asyncio.sleep"):
                with pytest.raises(LLMRetryableError):
                    await strategy.execute_with_retry(
                        mock_func,
                        "test_provider",
                        None,
                    )

        # Should not have any warning logs since we only try once
        mock_logger.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_zero_retries_correct_error_message(self):
        """Test that max_retries=0 raises error with correct attempt count."""
        strategy = RetryStrategy(max_retries=0)

        async def mock_func():
            raise ConnectionError("Connection timeout")

        with patch("asyncio.sleep"):
            with pytest.raises(LLMRetryableError) as exc_info:
                await strategy.execute_with_retry(
                    mock_func,
                    "test_provider",
                    None,
                )

        error = exc_info.value
        # Should say "failed after 1 attempts" not "failed after 0 attempts"
        assert "failed after 1 attempts" in str(error)
        assert error.attempt == 1
        assert error.max_attempts == 1

    @pytest.mark.asyncio
    async def test_one_retry_correct_logging_message(self):
        """Test that max_retries=1 logs correct attempt count during retry."""
        strategy = RetryStrategy(max_retries=1)
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Connection timeout")

        # Capture the actual log message
        with patch("scriptrag.llm.retry_strategy.logger") as mock_logger:
            with patch("asyncio.sleep"):
                with pytest.raises(LLMRetryableError):
                    await strategy.execute_with_retry(
                        mock_func,
                        "test_provider",
                        None,
                    )

        # max_retries=1 means 1 total attempt, so no retries should happen
        # and no warning logs should be generated
        assert call_count == 1
        mock_logger.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_three_retries_correct_logging_messages(self):
        """Test that max_retries=3 logs correct attempt counts during retries."""
        strategy = RetryStrategy(max_retries=3)
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Connection timeout")

        # Capture the actual log messages
        log_messages = []

        def capture_warning(msg, *args, **kwargs):
            log_messages.append(msg)

        with patch(
            "scriptrag.llm.retry_strategy.logger.warning", side_effect=capture_warning
        ):
            with patch("asyncio.sleep"):
                with pytest.raises(LLMRetryableError) as exc_info:
                    await strategy.execute_with_retry(
                        mock_func,
                        "test_provider",
                        None,
                    )

        # With max_retries=3, we should see:
        # - Attempt 1/3 failed, retrying...
        # - Attempt 2/3 failed, retrying...
        # No log for attempt 3 since it's the last attempt
        assert len(log_messages) == 2
        assert "Attempt 1/3 failed" in log_messages[0]
        assert "Attempt 2/3 failed" in log_messages[1]

        error = exc_info.value
        assert "failed after 3 attempts" in str(error)
        assert error.attempt == 3
        assert error.max_attempts == 3

    @pytest.mark.asyncio
    async def test_two_retries_with_success_correct_logging(self):
        """Test correct logging when retry eventually succeeds."""
        strategy = RetryStrategy(max_retries=3)
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection timeout")
            return "success"

        log_messages = []

        def capture_warning(msg, *args, **kwargs):
            log_messages.append(msg)

        with patch(
            "scriptrag.llm.retry_strategy.logger.warning", side_effect=capture_warning
        ):
            with patch("asyncio.sleep"):
                result = await strategy.execute_with_retry(
                    mock_func,
                    "test_provider",
                    None,
                )

        assert result == "success"
        assert call_count == 3

        # Should see 2 retry warnings (attempts 1 and 2 failed)
        assert len(log_messages) == 2
        assert "Attempt 1/3 failed" in log_messages[0]
        assert "Attempt 2/3 failed" in log_messages[1]

    @pytest.mark.asyncio
    async def test_rate_limit_with_retry_after_correct_logging(self):
        """Test correct logging with RateLimitError that has retry_after."""
        strategy = RetryStrategy(max_retries=2)
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError("Rate limited", retry_after=0.5)
            return "success"

        log_messages = []

        def capture_warning(msg, *args, **kwargs):
            log_messages.append(msg)

        with patch(
            "scriptrag.llm.retry_strategy.logger.warning", side_effect=capture_warning
        ):
            with patch("asyncio.sleep") as mock_sleep:
                result = await strategy.execute_with_retry(
                    mock_func,
                    "test_provider",
                    None,
                )

        assert result == "success"
        assert call_count == 2

        # Should see 1 retry warning with correct attempt count
        assert len(log_messages) == 1
        assert "Attempt 1/2 failed" in log_messages[0]
        assert "retrying in 0.50s" in log_messages[0]

        # Should have used retry_after value
        mock_sleep.assert_called_once_with(0.5)

    @pytest.mark.asyncio
    async def test_metrics_callback_receives_correct_counts(self):
        """Test that metrics callback receives correct attempt information."""
        strategy = RetryStrategy(max_retries=3)
        call_count = 0
        metrics_calls = []

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection timeout")
            return "success"

        def mock_metrics(provider_name, error):
            metrics_calls.append((provider_name, error))

        with patch("asyncio.sleep"):
            result = await strategy.execute_with_retry(
                mock_func,
                "test_provider",
                mock_metrics,
            )

        assert result == "success"
        assert len(metrics_calls) == 3

        # First two calls should have errors, last should be None (success)
        assert metrics_calls[0][0] == "test_provider"
        assert isinstance(metrics_calls[0][1], ConnectionError)

        assert metrics_calls[1][0] == "test_provider"
        assert isinstance(metrics_calls[1][1], ConnectionError)

        assert metrics_calls[2][0] == "test_provider"
        assert metrics_calls[2][1] is None  # Success

    @pytest.mark.asyncio
    async def test_edge_case_negative_max_retries(self):
        """Test edge case with negative max_retries (should be treated as 0)."""
        # While this shouldn't happen in practice, let's ensure robust behavior
        strategy = RetryStrategy(max_retries=-5)  # Invalid, but let's test

        async def mock_func():
            return "success"

        # Should still execute at least once even with negative max_retries
        result = await strategy.execute_with_retry(
            mock_func,
            "test_provider",
            None,
        )

        assert result == "success"

    @pytest.mark.asyncio
    async def test_large_max_retries_correct_logging(self):
        """Test correct logging with a large max_retries value."""
        strategy = RetryStrategy(max_retries=100)
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 5:  # Fail 4 times, succeed on 5th
                raise ConnectionError("Connection timeout")
            return "success"

        log_messages = []

        def capture_warning(msg, *args, **kwargs):
            log_messages.append(msg)

        with patch(
            "scriptrag.llm.retry_strategy.logger.warning", side_effect=capture_warning
        ):
            with patch("asyncio.sleep"):
                result = await strategy.execute_with_retry(
                    mock_func,
                    "test_provider",
                    None,
                )

        assert result == "success"
        assert call_count == 5

        # Should see 4 retry warnings with correct total attempt count
        assert len(log_messages) == 4
        assert "Attempt 1/100 failed" in log_messages[0]
        assert "Attempt 2/100 failed" in log_messages[1]
        assert "Attempt 3/100 failed" in log_messages[2]
        assert "Attempt 4/100 failed" in log_messages[3]
