"""Atomic write tests for ModelDiscoveryCache."""

import sys
from unittest.mock import patch

import pytest

from scriptrag.llm.model_cache import ModelDiscoveryCache
from scriptrag.llm.models import LLMProvider, Model


class TestModelCacheAtomicWrites:
    def setup_method(self):
        """Ensure clean in-memory cache before each test."""
        ModelDiscoveryCache.clear_all_memory_cache()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="POSIX permission bits are not reliably enforced on Windows",
    )
    def test_atomic_write_permissions(self, tmp_path):
        """Cache files and directory should have restrictive permissions."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            models = [
                Model(
                    id="model-perm",
                    name="Perm Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            cache.set(models)

            # Verify file permissions (POSIX only)
            assert cache.cache_file.exists()
            file_stat = cache.cache_file.stat()
            assert file_stat.st_mode & 0o777 == 0o600

            # Verify directory permissions
            dir_stat = cache.CACHE_DIR.stat()
            assert dir_stat.st_mode & 0o777 == 0o700

    def test_atomic_write_temp_file_cleanup(self, tmp_path):
        """Temp files are cleaned up on write failure."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            models = [
                Model(
                    id="model-clean",
                    name="Cleanup Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            # Patch os.fdopen to raise during write, after mkstemp has created a file
            with patch("os.fdopen", side_effect=OSError("Simulated failure")):
                cache.set(models)

            # Verify no temp files left behind
            temp_files = list(
                cache.CACHE_DIR.glob(f".{cache.provider_name}_models_*.tmp")
            )
            assert len(temp_files) == 0

    def test_file_descriptor_cleanup_on_error(self, tmp_path):
        """File descriptors are properly closed even when fd is 0."""
        import os

        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            models = [
                Model(
                    id="model-fd",
                    name="FD Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            # Track which file descriptors get closed
            closed_fds = []
            original_close = os.close

            def mock_close(fd):
                closed_fds.append(fd)
                # Don't actually close since we're mocking

            # Mock mkstemp to return fd=0 (valid but falsy)
            test_tmp_file = str(tmp_path / "test.tmp")
            with patch("tempfile.mkstemp", return_value=(0, test_tmp_file)):
                # Mock fdopen to raise an exception after mkstemp
                mock_err = OSError("Simulated write failure")
                with patch("os.fdopen", side_effect=mock_err):
                    # Mock os.close to track what gets closed
                    with patch("os.close", side_effect=mock_close):
                        # This should handle the cleanup properly even with fd=0
                        cache.set(models)

            # Verify that fd 0 was attempted to be closed during cleanup
            assert 0 in closed_fds, "FD 0 should have been closed"

    def test_file_descriptor_not_closed_after_fdopen_success(self, tmp_path):
        """File descriptor is not double-closed after successful fdopen."""
        import os

        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            models = [
                Model(
                    id="model-success",
                    name="Success Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            # Track close attempts
            close_attempts = []
            original_close = os.close

            def mock_close(fd):
                close_attempts.append(fd)
                original_close(fd)

            # Successful write should NOT attempt to close the fd in cleanup
            # since fdopen takes ownership
            with patch("os.close", side_effect=mock_close):
                cache.set(models)

            # The fd should not be in close_attempts since fdopen handled it
            err_msg = "No manual close should occur after successful fdopen"
            assert len(close_attempts) == 0, err_msg
