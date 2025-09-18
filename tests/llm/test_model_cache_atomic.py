"""Atomic write tests for ModelDiscoveryCache."""

import os
import sys
from pathlib import Path
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

            # Track resources that need cleanup
            closed_fds = []
            removed_files = []

            def mock_close(fd):
                closed_fds.append(fd)
                # Don't actually close since we're testing

            # Test with fd=0 (valid but falsy in boolean context)
            test_tmp_file = str(tmp_path / "test.tmp")

            # Create actual temp file to verify cleanup
            Path(test_tmp_file).touch()

            with patch("tempfile.mkstemp", return_value=(0, test_tmp_file)):
                # Simulate fdopen failure BEFORE it takes ownership
                with patch("os.fdopen", side_effect=OSError("Write failed")):
                    with patch("os.close", side_effect=mock_close):
                        # Mock Path.unlink to track file removals
                        original_unlink = Path.unlink

                        def mock_unlink(self):
                            removed_files.append(str(self))
                            # Don't actually remove

                        with patch.object(Path, "unlink", mock_unlink):
                            # This should properly clean up fd=0
                            cache.set(models)

            # Verify both fd and file are cleaned up
            assert 0 in closed_fds, "FD 0 should be closed on error"
            assert test_tmp_file in removed_files, "Temp file should be removed"

    def test_file_descriptor_not_closed_after_fdopen_success(self, tmp_path):
        """Verify proper fd ownership transfer to fdopen on success."""
        import json

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

            # Successfully write the cache
            cache.set(models)

            # Verify the file was written correctly
            assert cache.cache_file.exists(), "Cache file should be created"

            # Read and verify content
            with cache.cache_file.open() as f:
                data = json.load(f)
                assert len(data["models"]) == 1
                assert data["models"][0]["id"] == "model-success"
                assert data["provider"] == "test_provider"

            # Verify permissions are restrictive (Unix only)
            if sys.platform != "win32":
                stat_result = cache.cache_file.stat()
                assert stat_result.st_mode & 0o777 == 0o600

    def test_fd_zero_integration(self, tmp_path):
        """Integration test for fd=0 handling with real file operations."""
        import tempfile

        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_fd_zero")

            models = [
                Model(
                    id="fd-zero-test",
                    name="FD Zero Integration",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            # Mock mkstemp to return fd=0 but still create a real temp file
            original_mkstemp = tempfile.mkstemp

            def mock_mkstemp(*args, **kwargs):
                # Create real temp file
                real_fd, real_path = original_mkstemp(*args, **kwargs)
                # Close the real fd and return 0 with the real path
                os.close(real_fd)
                # Open stdin (fd=0) for write to simulate fd=0 scenario
                # Note: In real scenario this would be problematic, but for testing
                # we're demonstrating the edge case handling
                return (0, real_path)

            # Patch mkstemp but let everything else work normally
            with patch("tempfile.mkstemp", side_effect=mock_mkstemp):
                # Mock fdopen to fail, simulating the edge case
                with patch("os.fdopen", side_effect=OSError("FD 0 error")):
                    # The cache.set should handle this gracefully
                    cache.set(models)

            # Verify no temp files are left behind
            temp_files = list(tmp_path.glob(".test_fd_zero_models_*.tmp"))
            assert len(temp_files) == 0, "No temp files should remain"
