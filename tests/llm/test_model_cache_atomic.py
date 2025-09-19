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

    def test_file_descriptor_cleanup_on_fdopen_failure(self, tmp_path):
        """File descriptor is properly closed when os.fdopen fails."""
        import os

        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            models = [
                Model(
                    id="model-fd-test",
                    name="FD Cleanup Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            # Track open file descriptors before the operation
            open_fds_before = set()
            try:
                # Try to get a list of open file descriptors
                for fd in range(3, 256):  # Skip stdin/stdout/stderr
                    try:
                        os.fstat(fd)
                        open_fds_before.add(fd)
                    except OSError:
                        pass
            except Exception:
                pass  # If we can't track FDs, skip this check

            # Patch os.fdopen to raise immediately (before taking ownership)
            with patch("os.fdopen", side_effect=OSError("Simulated fdopen failure")):
                cache.set(models)

            # Verify no new file descriptors are leaked
            open_fds_after = set()
            try:
                for fd in range(3, 256):
                    try:
                        os.fstat(fd)
                        open_fds_after.add(fd)
                    except OSError:
                        pass
            except Exception:
                pass

            # No new file descriptors should be open
            new_fds = open_fds_after - open_fds_before
            assert len(new_fds) == 0, f"File descriptors leaked: {new_fds}"

            # Also verify no temp files left behind
            temp_files = list(
                cache.CACHE_DIR.glob(f".{cache.provider_name}_models_*.tmp")
            )
            assert len(temp_files) == 0

    def test_file_descriptor_cleanup_on_json_dump_failure(self, tmp_path):
        """File descriptor is closed when json.dump fails after fdopen succeeds."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            models = [
                Model(
                    id="model-json-test",
                    name="JSON Dump Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            # Patch json.dump to raise after fdopen has taken ownership
            with patch("json.dump", side_effect=OSError("Simulated json.dump failure")):
                cache.set(models)

            # Verify no temp files left behind
            temp_files = list(
                cache.CACHE_DIR.glob(f".{cache.provider_name}_models_*.tmp")
            )
            assert len(temp_files) == 0

            # The file descriptor should have been closed by the context manager
            # even though json.dump failed
