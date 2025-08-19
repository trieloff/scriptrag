"""Atomic write tests for ModelDiscoveryCache."""

from unittest.mock import patch

from scriptrag.llm.model_cache import ModelDiscoveryCache
from scriptrag.llm.models import LLMProvider, Model


class TestModelCacheAtomicWrites:
    def setup_method(self):
        """Ensure clean in-memory cache before each test."""
        ModelDiscoveryCache.clear_all_memory_cache()

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

            # Verify file permissions
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
