"""Comprehensive tests for LLM retry strategy with exponential backoff."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from scriptrag.exceptions import LLMRetryableError, RateLimitError
from scriptrag.llm.retry_strategy import RetryStrategy


class TestRetryStrategy:
    """Test retry strategy with exponential backoff and jitter."""

    @pytest.fixture
    def retry_strategy(self):
        """Create retry strategy with default settings."""
        return RetryStrategy(
            max_retries=3,
            base_retry_delay=1.0,
            max_retry_delay=10.0,
        )

    @pytest.fixture
    def custom_retry_strategy(self):
        """Create retry strategy with custom settings."""
        return RetryStrategy(
            max_retries=5,
            base_retry_delay=0.5,
            max_retry_delay=20.0,
        )

    def test_initialization_defaults(self):
        """Test retry strategy initialization with defaults."""
        strategy = RetryStrategy()
        assert strategy.max_retries == 3
        assert strategy.base_retry_delay == 1.0
        assert strategy.max_retry_delay == 10.0

    def test_initialization_custom(self):
        """Test retry strategy initialization with custom values."""
        strategy = RetryStrategy(
            max_retries=10,
            base_retry_delay=2.0,
            max_retry_delay=30.0,
        )
        assert strategy.max_retries == 10
        assert strategy.base_retry_delay == 2.0
        assert strategy.max_retry_delay == 30.0

    def test_calculate_retry_delay_exponential_backoff(self, retry_strategy):
        """Test exponential backoff calculation."""
        # Mock time to control jitter
        with patch("time.time", return_value=1234567890.5):
            # First attempt: base_delay * 2^0 = 1.0
            delay1 = retry_strategy.calculate_retry_delay(1)
            assert 1.0 <= delay1 <= 1.15  # Base + up to 10% jitter

            # Second attempt: base_delay * 2^1 = 2.0
            delay2 = retry_strategy.calculate_retry_delay(2)
            assert 2.0 <= delay2 <= 2.25

            # Third attempt: base_delay * 2^2 = 4.0
            delay3 = retry_strategy.calculate_retry_delay(3)
            assert 4.0 <= delay3 <= 4.45

            # Fourth attempt: base_delay * 2^3 = 8.0
            delay4 = retry_strategy.calculate_retry_delay(4)
            assert 8.0 <= delay4 <= 8.85

    def test_calculate_retry_delay_respects_max_delay(self, retry_strategy):
        """Test that retry delay respects maximum delay."""
        with patch("time.time", return_value=1234567890.5):
            # Very high attempt number should still respect max_delay
            delay = retry_strategy.calculate_retry_delay(10)
            assert delay <= retry_strategy.max_retry_delay * 1.1  # Max + jitter

    def test_calculate_retry_delay_jitter_varies(self, retry_strategy):
        """Test that jitter adds variation to delays."""
        delays = []
        for i in range(10):
            with patch("time.time", return_value=1234567890.0 + i * 0.1):
                delay = retry_strategy.calculate_retry_delay(1)
                delays.append(delay)

        # All delays should be slightly different due to jitter
        unique_delays = set(delays)
        assert len(unique_delays) > 1
        assert all(1.0 <= d <= 1.11 for d in delays)

    def test_is_retryable_error_rate_limit(self, retry_strategy):
        """Test that rate limit errors are retryable."""
        error = RateLimitError("Rate limit exceeded", retry_after=5.0)
        assert retry_strategy.is_retryable_error(error) is True

    def test_is_retryable_error_network_errors(self, retry_strategy):
        """Test that network-related errors are retryable."""
        retryable_errors = [
            ConnectionError("Connection timeout"),
            TimeoutError("Request timeout"),
            RuntimeError("Network unavailable"),
            ValueError("Service temporarily unavailable"),
            Exception("503 Service Unavailable"),
            Exception("502 Bad Gateway"),
            Exception("504 Gateway Timeout"),
            Exception("500 Internal Server Error"),
            Exception("Too many requests"),
        ]

        for error in retryable_errors:
            assert retry_strategy.is_retryable_error(error) is True

    def test_is_retryable_error_non_retryable(self, retry_strategy):
        """Test that certain errors are not retryable."""
        non_retryable_errors = [
            ValueError("Invalid API key"),
            TypeError("Wrong argument type"),
            AttributeError("Method not found"),
            KeyError("Missing required field"),
            Exception("Authentication failed"),
            Exception("Permission denied"),
        ]

        for error in non_retryable_errors:
            assert retry_strategy.is_retryable_error(error) is False

    def test_extract_retry_after_from_rate_limit_error(self, retry_strategy):
        """Test extracting retry_after from RateLimitError."""
        error = RateLimitError("Rate limit", retry_after=7.5)
        assert retry_strategy.extract_retry_after(error) == 7.5

    def test_extract_retry_after_from_message(self, retry_strategy):
        """Test extracting retry_after from error message."""
        errors_with_retry = [
            (Exception("Retry after 5 seconds"), 5.0),
            (Exception("Please retry after 10.5 seconds"), 10.5),
            (Exception("RETRY AFTER 3"), 3.0),
            (ValueError("Error: retry after 2.25 sec"), 2.25),
        ]

        for error, expected in errors_with_retry:
            assert retry_strategy.extract_retry_after(error) == expected

    def test_extract_retry_after_no_info(self, retry_strategy):
        """Test extracting retry_after when no info available."""
        errors_without_retry = [
            Exception("Generic error"),
            ValueError("Invalid input"),
            Exception("Retry later"),  # No specific time
            Exception("After some time"),  # No number
        ]

        for error in errors_without_retry:
            assert retry_strategy.extract_retry_after(error) is None

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_first_attempt(self, retry_strategy):
        """Test successful execution on first attempt."""
        mock_func = AsyncMock(return_value="success")
        mock_metrics = Mock(spec=object)

        result = await retry_strategy.execute_with_retry(
            mock_func,
            "test_provider",
            mock_metrics,
            "arg1",
            kwarg1="value1",
        )

        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")
        mock_metrics.assert_called_once_with("test_provider", None)

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_after_retries(self, retry_strategy):
        """Test successful execution after retries."""
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary network error")
            return "success_after_retries"

        mock_metrics = Mock(spec=object)

        with patch("asyncio.sleep") as mock_sleep:
            result = await retry_strategy.execute_with_retry(
                mock_func,
                "test_provider",
                mock_metrics,
            )

        assert result == "success_after_retries"
        assert call_count == 3
        assert mock_sleep.call_count == 2  # Two retries
        assert mock_metrics.call_count == 3  # One per attempt

    @pytest.mark.asyncio
    async def test_execute_with_retry_all_attempts_fail(self, retry_strategy):
        """Test when all retry attempts fail."""

        async def mock_func():
            raise ConnectionError("Connection timeout")  # Use retryable error message

        mock_metrics = Mock(spec=object)

        with patch("asyncio.sleep"):
            with pytest.raises(LLMRetryableError) as exc_info:
                await retry_strategy.execute_with_retry(
                    mock_func,
                    "test_provider",
                    mock_metrics,
                )

        error = exc_info.value
        assert "failed after 3 attempts" in str(error)
        assert error.provider == "test_provider"
        assert error.max_attempts == 3
        assert isinstance(error.original_error, ConnectionError)
        # mock_func is now a regular function, not a Mock
        assert mock_metrics.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_non_retryable_error(self, retry_strategy):
        """Test immediate failure on non-retryable error."""
        non_retryable = ValueError("Invalid API key")

        async def mock_func():
            raise non_retryable

        mock_metrics = Mock(spec=object)

        with pytest.raises(ValueError) as exc_info:
            await retry_strategy.execute_with_retry(
                mock_func,
                "test_provider",
                mock_metrics,
            )

        assert exc_info.value == non_retryable
        # mock_func is now a regular function, not a Mock
        mock_metrics.assert_called_once_with("test_provider", non_retryable)

    @pytest.mark.asyncio
    async def test_execute_with_retry_respects_retry_after(self, retry_strategy):
        """Test that retry respects retry_after from RateLimitError."""
        error = RateLimitError("Rate limited", retry_after=2.5)
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise error
            return "success"

        mock_metrics = Mock(spec=object)

        with patch("asyncio.sleep") as mock_sleep:
            result = await retry_strategy.execute_with_retry(
                mock_func,
                "test_provider",
                mock_metrics,
            )

        assert result == "success"
        assert call_count == 2
        # Should use retry_after value, not exponential backoff
        mock_sleep.assert_called_once()
        sleep_delay = mock_sleep.call_args[0][0]
        assert sleep_delay == 2.5

    @pytest.mark.asyncio
    async def test_execute_with_retry_exponential_delays(self, retry_strategy):
        """Test exponential backoff delays between retries."""
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Connection timeout")
            if call_count == 2:
                raise ConnectionError("Network unavailable")
            return "success"

        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with patch("time.time", return_value=1234567890.0):
                result = await retry_strategy.execute_with_retry(
                    mock_func,
                    "test_provider",
                    None,
                )

        assert result == "success"
        assert len(sleep_calls) == 2
        # First retry: ~1.0 seconds
        assert 1.0 <= sleep_calls[0] <= 1.1
        # Second retry: ~2.0 seconds
        assert 2.0 <= sleep_calls[1] <= 2.2

    @pytest.mark.asyncio
    async def test_execute_with_retry_without_metrics_callback(self, retry_strategy):
        """Test retry execution without metrics callback."""
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("Request timeout")
            return "success"

        with patch("asyncio.sleep"):
            result = await retry_strategy.execute_with_retry(
                mock_func,
                "test_provider",
                None,  # No metrics callback
            )

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_retry_complex_error_patterns(self, retry_strategy):
        """Test retry with complex error patterns."""
        errors = [
            ConnectionError("Network error"),
            RateLimitError("Rate limit", retry_after=0.5),
            # Only 2 errors so the 3rd attempt will succeed
        ]

        call_count = 0

        async def mock_func():
            nonlocal call_count
            if call_count < len(errors):
                error = errors[call_count]
                call_count += 1
                raise error
            call_count += 1
            return "success"

        mock_metrics = Mock(spec=object)
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with patch("time.time", return_value=1234567890.0):
                result = await retry_strategy.execute_with_retry(
                    mock_func,
                    "test_provider",
                    mock_metrics,
                )

        # With max_retries=3, we expect 3 total attempts
        # 2 failures followed by 1 success
        assert result == "success"
        assert call_count == 3
        assert len(sleep_calls) == 2
        # Second sleep should use retry_after from RateLimitError
        assert sleep_calls[1] == 0.5

    @pytest.mark.asyncio
    async def test_execute_with_retry_max_attempts_boundary(self):
        """Test retry behavior at max attempts boundary."""
        # Test with exactly max_retries failures
        strategy = RetryStrategy(max_retries=2)
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Connection timeout")
            if call_count == 2:
                raise ConnectionError("Network error")
            # Should never get here
            return "should_not_reach"

        with patch("asyncio.sleep"):
            with pytest.raises(LLMRetryableError) as exc_info:
                await strategy.execute_with_retry(
                    mock_func,
                    "test_provider",
                    None,
                )

        assert call_count == 2
        assert exc_info.value.max_attempts == 2

    @pytest.mark.asyncio
    async def test_execute_with_retry_zero_retries(self):
        """Test with zero retries configured."""
        strategy = RetryStrategy(max_retries=0)

        async def mock_func():
            raise ValueError("Non-retryable error")  # Use non-retryable error

        # Should fail immediately without any retries
        with pytest.raises(ValueError):
            await strategy.execute_with_retry(
                mock_func,
                "test_provider",
                None,
            )

    def test_jitter_calculation_deterministic_with_fixed_time(self, retry_strategy):
        """Test that jitter calculation is deterministic with fixed time."""
        with patch("time.time", return_value=1234567890.123):
            delay1 = retry_strategy.calculate_retry_delay(1)
            delay2 = retry_strategy.calculate_retry_delay(1)
            assert delay1 == delay2

    def test_jitter_calculation_varies_with_time(self, retry_strategy):
        """Test that jitter varies with different timestamps."""
        delays = []
        for i in range(5):
            with patch("time.time", return_value=1234567890.0 + i):
                delay = retry_strategy.calculate_retry_delay(1)
                delays.append(delay)

        # Should have some variation due to jitter
        assert len(set(delays)) > 1

    @pytest.mark.asyncio
    async def test_execute_with_retry_preserves_error_context(self, retry_strategy):
        """Test that original error context is preserved."""
        original_error = ConnectionError("Connection timeout with detailed context")

        async def mock_func():
            raise original_error

        with patch("asyncio.sleep"):
            with pytest.raises(LLMRetryableError) as exc_info:
                await retry_strategy.execute_with_retry(
                    mock_func,
                    "test_provider",
                    None,
                )

        error = exc_info.value
        assert error.original_error == original_error
        assert "Connection timeout with detailed context" in str(error.original_error)

    @pytest.mark.asyncio
    async def test_concurrent_retries_with_different_strategies(self):
        """Test concurrent retry operations with different strategies."""
        strategy1 = RetryStrategy(max_retries=2, base_retry_delay=0.1)
        strategy2 = RetryStrategy(max_retries=3, base_retry_delay=0.2)

        call_counts = {"s1": 0, "s2": 0}

        async def func1():
            call_counts["s1"] += 1
            if call_counts["s1"] < 2:
                raise ConnectionError("Connection timeout")
            return "s1_success"

        async def func2():
            call_counts["s2"] += 1
            if call_counts["s2"] < 3:
                raise TimeoutError("S2 error")
            return "s2_success"

        with patch("asyncio.sleep"):
            results = await asyncio.gather(
                strategy1.execute_with_retry(func1, "provider1", None),
                strategy2.execute_with_retry(func2, "provider2", None),
            )

        assert results == ["s1_success", "s2_success"]
        assert call_counts["s1"] == 2
        assert call_counts["s2"] == 3

    @pytest.mark.asyncio
    async def test_retry_logging_shows_correct_attempt_numbers(
        self, retry_strategy, caplog
    ):
        """Test retry logging shows correct attempt numbers out of total attempts."""
        import logging

        caplog.set_level(logging.WARNING)

        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # Fail first 2 attempts
                raise ConnectionError("Temporary network error")
            return "success"

        with patch("asyncio.sleep"):
            result = await retry_strategy.execute_with_retry(
                mock_func,
                "test_provider",
                None,
            )

        assert result == "success"

        # Check log messages for correct attempt numbering
        log_messages = [record.message for record in caplog.records]

        # Should see "Attempt 1/3 failed" and "Attempt 2/3 failed"
        assert any("Attempt 1/3 failed" in msg for msg in log_messages)
        assert any("Attempt 2/3 failed" in msg for msg in log_messages)
        # Should NOT see "Attempt 3/3 failed" because the third attempt succeeded
        assert not any("Attempt 3/3 failed" in msg for msg in log_messages)

    @pytest.mark.asyncio
    async def test_retry_error_message_uses_total_attempts(self):
        """Test that the final error message correctly states total attempts."""
        strategy = RetryStrategy(max_retries=4)  # 4 total attempts

        async def mock_func():
            raise ConnectionError("Persistent error")

        with patch("asyncio.sleep"):
            with pytest.raises(LLMRetryableError) as exc_info:
                await strategy.execute_with_retry(
                    mock_func,
                    "test_provider",
                    None,
                )

        error = exc_info.value
        # Should say "failed after 4 attempts" not "after 4 retries"
        assert "failed after 4 attempts" in str(error)
        assert error.max_attempts == 4
        assert error.attempt == 4

    @pytest.mark.asyncio
    async def test_retry_with_max_retries_one(self):
        """Test retry behavior with max_retries=1 (single attempt)."""
        strategy = RetryStrategy(max_retries=1)

        async def mock_func():
            raise ConnectionError("Connection failed")

        with patch("asyncio.sleep"):
            with pytest.raises(LLMRetryableError) as exc_info:
                await strategy.execute_with_retry(
                    mock_func,
                    "test_provider",
                    None,
                )

        error = exc_info.value
        # Should say "failed after 1 attempts" - singular would be better,
        # but consistency is key
        assert "failed after 1 attempts" in str(error)
        assert error.max_attempts == 1
        assert error.attempt == 1
