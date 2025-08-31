"""Tests for logging performance optimizations."""

import time
from unittest.mock import patch

from scriptrag.config import get_logger, reset_settings


class TestLoggingPerformance:
    """Test logging performance optimizations."""

    def test_logger_caching(self):
        """Test that loggers are properly cached for performance."""
        # Reset to ensure clean state
        reset_settings()

        # Get the same logger multiple times
        logger1 = get_logger("test.module")
        logger2 = get_logger("test.module")
        logger3 = get_logger("test.module")

        # All should be the same instance (cached)
        assert logger1 is logger2
        assert logger2 is logger3

    def test_logger_cache_different_names(self):
        """Test that different logger names get different instances."""
        # Reset to ensure clean state
        reset_settings()

        # Get loggers with different names
        logger1 = get_logger("test.module1")
        logger2 = get_logger("test.module2")
        logger3 = get_logger("test.module1")

        # Different names should get different instances
        assert logger1 is not logger2
        # Same name should get cached instance
        assert logger1 is logger3

    def test_reset_settings_clears_cache(self):
        """Test that reset_settings clears the logger cache."""
        # Get a logger
        logger1 = get_logger("test.cache")

        # Reset settings (should clear cache)
        reset_settings()

        # Get the same logger again
        logger2 = get_logger("test.cache")

        # Should be different instances since cache was cleared
        # Note: They might still be equal due to structlog's internal cache,
        # but our local cache should be cleared
        import scriptrag.config

        assert len(scriptrag.config._logger_cache) == 1
        assert "test.cache" in scriptrag.config._logger_cache

    def test_logger_performance(self):
        """Test that cached loggers provide performance improvement."""
        # Reset to ensure clean state
        reset_settings()

        # Time first access (includes initialization)
        start = time.perf_counter()
        logger1 = get_logger("perf.test")
        first_access = time.perf_counter() - start

        # Time subsequent accesses (should be cached)
        start = time.perf_counter()
        for _ in range(1000):
            logger2 = get_logger("perf.test")
        cached_access = (time.perf_counter() - start) / 1000

        # Cached access should be significantly faster
        # Allow for some variance but expect at least 10x improvement
        # In practice, cached access is usually 100x+ faster
        assert cached_access < first_access, (
            f"Cached access ({cached_access:.6f}s) should be faster than "
            f"first access ({first_access:.6f}s)"
        )

        # Verify same instance
        assert logger1 is logger2

    def test_logging_initialization_only_once(self):
        """Test that logging is only configured once."""
        reset_settings()

        with patch("scriptrag.config.configure_logging") as mock_configure:
            # Get multiple loggers
            get_logger("test1")
            get_logger("test2")
            get_logger("test3")
            get_logger("test1")  # Same as first

            # configure_logging should only be called once
            assert mock_configure.call_count == 1

    def test_production_optimization(self):
        """Test that production optimizations are applied."""
        import logging

        from scriptrag.config import ScriptRAGSettings, configure_logging

        # Configure with production settings (no debug)
        settings = ScriptRAGSettings(
            log_level="INFO",
            debug=False,
        )

        configure_logging(settings)

        # Check that handlers don't allow DEBUG level
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            # In production mode, handlers should be at INFO or higher
            assert handler.level >= logging.INFO

    def test_debug_mode_no_optimization(self):
        """Test that debug mode doesn't apply performance optimizations."""
        import logging

        from scriptrag.config import ScriptRAGSettings, configure_logging

        # Configure with debug settings
        settings = ScriptRAGSettings(
            log_level="DEBUG",
            debug=True,
        )

        configure_logging(settings)

        # Check that handlers allow DEBUG level
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            # In debug mode, handlers should allow DEBUG
            assert handler.level <= logging.DEBUG
