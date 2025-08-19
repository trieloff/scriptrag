"""Comprehensive tests for LLM Metrics to achieve 99% coverage."""

import time
from unittest.mock import patch

from scriptrag.llm.metrics import LLMMetrics


class TestLLMMetricsCoverage:
    """Tests to cover missing lines in LLMMetrics."""

    def test_record_failure_sliding_window(self):
        """Test failure record sliding window behavior (line 59)."""
        metrics = LLMMetrics()

        # Add failures beyond the max limit
        for i in range(LLMMetrics.MAX_FAILURE_ENTRIES + 5):
            error = Exception(f"Error {i}")
            metrics.record_failure("test_provider", error)

        # Should only keep the most recent MAX_FAILURE_ENTRIES
        failures = metrics.provider_metrics["provider_failures"]["test_provider"]
        assert len(failures) == LLMMetrics.MAX_FAILURE_ENTRIES

        # Should have the most recent errors
        assert "Error 104" in failures[-1]["error_message"]  # 100 + 5 - 1
        assert "Error 5" in failures[0]["error_message"]  # First kept entry

    def test_record_retry(self):
        """Test record_retry method (line 65)."""
        metrics = LLMMetrics()

        # Initial state
        assert metrics.provider_metrics["retry_attempts"] == 0

        # Record some retries
        metrics.record_retry()
        metrics.record_retry()
        metrics.record_retry()

        assert metrics.provider_metrics["retry_attempts"] == 3

    def test_record_fallback_chain_sliding_window(self):
        """Test fallback chain sliding window behavior (line 79)."""
        metrics = LLMMetrics()

        # Add fallback chains beyond the max limit
        for i in range(LLMMetrics.MAX_FALLBACK_CHAINS + 5):
            chain = [f"provider_{i}", f"fallback_{i}"]
            metrics.record_fallback_chain(chain)

        # Should only keep the most recent MAX_FALLBACK_CHAINS
        chains = metrics.provider_metrics["fallback_chains"]
        assert len(chains) == LLMMetrics.MAX_FALLBACK_CHAINS

        # Should have the most recent chains
        assert "provider_54" in chains[-1]["chain"]  # 50 + 5 - 1
        assert "provider_5" in chains[0]["chain"]  # First kept entry

    def test_get_metrics_returns_copy(self):
        """Test get_metrics returns a copy (line 85)."""
        metrics = LLMMetrics()

        # Record some data
        metrics.record_success("test_provider")

        # Get metrics
        result = metrics.get_metrics()

        # Modify the returned dict
        result["total_requests"] = 999
        result["new_key"] = "new_value"

        # Original should be unchanged
        original = metrics.get_metrics()
        assert original["total_requests"] == 1
        assert "new_key" not in original

    def test_cleanup_old_metrics_failures(self):
        """Test cleanup of old failure metrics (lines 93-103)."""
        metrics = LLMMetrics()

        # Add old and new failures
        old_time = time.time() - 7200  # 2 hours ago
        new_time = time.time() - 1800  # 30 minutes ago

        with patch("scriptrag.llm.metrics.time.time", return_value=old_time):
            metrics.record_failure("provider1", Exception("Old error"))

        with patch("scriptrag.llm.metrics.time.time", return_value=new_time):
            metrics.record_failure("provider1", Exception("New error"))

        # Cleanup with 1 hour max age
        metrics.cleanup_old_metrics(max_age_seconds=3600)

        # Should only have the new failure
        failures = metrics.provider_metrics["provider_failures"]["provider1"]
        assert len(failures) == 1
        assert "New error" in failures[0]["error_message"]

    def test_cleanup_old_metrics_fallback_chains(self):
        """Test cleanup of old fallback chains (lines 93-103)."""
        metrics = LLMMetrics()

        # Add old and new fallback chains
        old_time = time.time() - 7200  # 2 hours ago
        new_time = time.time() - 1800  # 30 minutes ago

        with patch("scriptrag.llm.metrics.time.time", return_value=old_time):
            metrics.record_fallback_chain(["old_provider"])

        with patch("scriptrag.llm.metrics.time.time", return_value=new_time):
            metrics.record_fallback_chain(["new_provider"])

        # Cleanup with 1 hour max age
        metrics.cleanup_old_metrics(max_age_seconds=3600)

        # Should only have the new chain
        chains = metrics.provider_metrics["fallback_chains"]
        assert len(chains) == 1
        assert "new_provider" in chains[0]["chain"]

    def test_cleanup_old_metrics_multiple_providers(self):
        """Test cleanup with multiple providers."""
        metrics = LLMMetrics()

        old_time = time.time() - 7200  # 2 hours ago
        new_time = time.time() - 1800  # 30 minutes ago

        # Add failures for multiple providers
        with patch("scriptrag.llm.metrics.time.time", return_value=old_time):
            metrics.record_failure("provider1", Exception("Old error 1"))
            metrics.record_failure("provider2", Exception("Old error 2"))

        with patch("scriptrag.llm.metrics.time.time", return_value=new_time):
            metrics.record_failure("provider1", Exception("New error 1"))
            metrics.record_failure("provider2", Exception("New error 2"))

        # Cleanup with 1 hour max age
        metrics.cleanup_old_metrics(max_age_seconds=3600)

        # Both providers should only have new failures
        failures1 = metrics.provider_metrics["provider_failures"]["provider1"]
        failures2 = metrics.provider_metrics["provider_failures"]["provider2"]

        assert len(failures1) == 1
        assert len(failures2) == 1
        assert "New error 1" in failures1[0]["error_message"]
        assert "New error 2" in failures2[0]["error_message"]

    def test_cleanup_empty_providers(self):
        """Test cleanup when some providers have no recent failures."""
        metrics = LLMMetrics()

        # Add only old failures
        old_time = time.time() - 7200  # 2 hours ago

        with patch("scriptrag.llm.metrics.time.time", return_value=old_time):
            metrics.record_failure("provider1", Exception("Old error"))

        # Cleanup with 1 hour max age
        metrics.cleanup_old_metrics(max_age_seconds=3600)

        # Provider should have empty failure list
        failures = metrics.provider_metrics["provider_failures"]["provider1"]
        assert len(failures) == 0

    def test_comprehensive_metrics_flow(self):
        """Test a comprehensive flow to ensure all metrics work together."""
        metrics = LLMMetrics()

        # Record various activities
        metrics.record_success("provider1")
        metrics.record_success("provider2")
        metrics.record_failure("provider1", Exception("Failure 1"))
        metrics.record_retry()
        metrics.record_fallback_chain(["provider1", "provider2"])

        # Get final metrics
        result = metrics.get_metrics()

        assert result["total_requests"] == 3
        assert result["successful_requests"] == 2
        assert result["failed_requests"] == 1
        assert result["retry_attempts"] == 1
        assert result["provider_successes"]["provider1"] == 1
        assert result["provider_successes"]["provider2"] == 1
        assert len(result["provider_failures"]["provider1"]) == 1
        assert len(result["fallback_chains"]) == 1
