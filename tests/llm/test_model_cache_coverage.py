"""Comprehensive tests for Model Cache to achieve 99% coverage."""

import json
import tempfile
import time
from unittest.mock import patch

import pytest

from scriptrag.llm.model_cache import ModelDiscoveryCache
from scriptrag.llm.models import LLMProvider, Model


class TestModelCacheCoverage:
    """Tests to cover missing lines in ModelDiscoveryCache."""

    def setup_method(self):
        """Clear memory cache before each test."""
        ModelDiscoveryCache.clear_all_memory_cache()

    def test_memory_cache_expiry(self, tmp_path):
        """Test in-memory cache expiry (lines 66-67)."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Add to memory cache with old timestamp
            old_time = time.time() - cache.ttl - 1  # Expired
            test_models = [
                Model(
                    id="test",
                    name="Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]
            cache._memory_cache["test_provider"] = (old_time, test_models)

            with patch("scriptrag.llm.model_cache.logger.debug") as mock_debug:
                result = cache.get()

                # Should return None and log expiry
                assert result is None

                # Check for the actual debug message that gets called
                debug_calls = [call[0][0] for call in mock_debug.call_args_list]
                assert any("expired" in msg for msg in debug_calls)

                # Should have cleared the expired entry
                assert "test_provider" not in cache._memory_cache

    def test_file_cache_expiry(self, tmp_path):
        """Test file cache expiry (lines 80-85)."""
        # Set up cache with temporary directory
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Create expired cache file
            cache_data = {
                "timestamp": time.time() - cache.ttl - 1,  # Expired
                "models": [
                    {
                        "id": "test",
                        "name": "Test",
                        "provider": "claude_code",
                        "capabilities": ["chat"],
                    }
                ],
                "provider": "test_provider",
            }

            cache.cache_file.write_text(json.dumps(cache_data))

            with patch("scriptrag.llm.model_cache.logger.debug") as mock_debug:
                result = cache.get()

                # Should return None and log expiry
                assert result is None
                mock_debug.assert_called_with(
                    "File cache expired for test_provider",
                    age=pytest.approx(cache.ttl + 1, abs=1),
                    ttl=cache.ttl,
                )

    def test_file_cache_json_decode_error(self, tmp_path):
        """Test JSON decode error handling (lines 102-104)."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Create invalid JSON file
            cache.cache_file.write_text("invalid json {")

            with patch("scriptrag.llm.model_cache.logger.warning") as mock_warning:
                result = cache.get()

                assert result is None
                # Just check that warning was called with the provider name
                mock_warning.assert_called_once()
                warning_msg = mock_warning.call_args[0][0]
                assert "Failed to read cache for test_provider" in warning_msg

    def test_file_cache_model_creation_error(self, tmp_path):
        """Test Model creation error handling (lines 102-104)."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Create cache with valid structure but invalid model data
            cache_data = {
                "timestamp": time.time(),
                "models": [
                    {"invalid_model": "data"}
                ],  # Missing required fields for Model
                "provider": "test_provider",
            }
            cache.cache_file.write_text(json.dumps(cache_data))

            with patch("scriptrag.llm.model_cache.logger.warning") as mock_warning:
                result = cache.get()

                assert result is None
                mock_warning.assert_called_once()
                # Should mention the error
                warning_msg = mock_warning.call_args[0][0]
                assert "Failed to read cache for test_provider" in warning_msg

    def test_file_cache_validation_error(self, tmp_path):
        """Test ValidationError handling (lines 102-104)."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Create cache with invalid model data
            cache_data = {
                "timestamp": time.time(),
                "models": [{"invalid": "model_data"}],  # Missing required fields
                "provider": "test_provider",
            }
            cache.cache_file.write_text(json.dumps(cache_data))

            with patch("scriptrag.llm.model_cache.logger.warning") as mock_warning:
                result = cache.get()

                assert result is None
                mock_warning.assert_called()
                warning_msg = mock_warning.call_args[0][0]
                assert "Failed to read cache for test_provider" in warning_msg

    def test_set_cache_write_error(self, tmp_path):
        """Test cache write error handling (lines 132-133)."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            test_models = [
                Model(
                    id="test",
                    name="Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            # Mock tempfile.mkstemp to raise an exception during temp file creation
            with (
                patch("scriptrag.llm.model_cache.logger.error") as mock_error,
                patch("tempfile.mkstemp") as mock_mkstemp,
            ):
                mock_mkstemp.side_effect = PermissionError("Write failed")
                cache.set(test_models)

                # PermissionError is OSError, uses error level logging
                mock_error.assert_called_once()
                error_msg = mock_error.call_args[0][0]
                assert (
                    "OS error when caching models for test_provider: Write failed"
                    in error_msg
                )

                # Memory cache should still be updated
                assert "test_provider" in cache._memory_cache

    def test_clear_memory_cache_only(self, tmp_path):
        """Test clearing memory cache when provider exists (line 139)."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Add to memory cache
            test_models = [
                Model(
                    id="test",
                    name="Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]
            cache._memory_cache["test_provider"] = (time.time(), test_models)

            # Ensure no file cache exists
            assert not cache.cache_file.exists()

            # Clear should only affect memory cache
            cache.clear()

            # Should clear memory cache
            assert "test_provider" not in cache._memory_cache

    def test_clear_file_cache_only(self, tmp_path):
        """Test clearing file cache when it exists (lines 143-144)."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Create file cache
            cache_data = {
                "timestamp": time.time(),
                "models": [
                    {
                        "id": "test",
                        "name": "Test",
                        "provider": "claude_code",
                        "capabilities": ["chat"],
                    }
                ],
                "provider": "test_provider",
            }
            cache.cache_file.write_text(json.dumps(cache_data))

            # Verify file exists
            assert cache.cache_file.exists()

            with patch("scriptrag.llm.model_cache.logger.debug") as mock_debug:
                cache.clear()

                # Should remove file
                assert not cache.cache_file.exists()
                mock_debug.assert_called_with("Cleared cache for test_provider")

    def test_clear_all_memory_cache_class_method(self):
        """Test clearing all memory cache (lines 153-154)."""
        # Add test data to memory cache for multiple providers
        test_models = [
            Model(
                id="test",
                name="Test",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["chat"],
            )
        ]
        ModelDiscoveryCache._memory_cache["provider1"] = (time.time(), test_models)
        ModelDiscoveryCache._memory_cache["provider2"] = (time.time(), test_models)

        # Verify cache has data
        assert len(ModelDiscoveryCache._memory_cache) == 2

        with patch("scriptrag.llm.model_cache.logger.debug") as mock_debug:
            ModelDiscoveryCache.clear_all_memory_cache()

            # Should clear all cache data
            assert len(ModelDiscoveryCache._memory_cache) == 0
            mock_debug.assert_called_with("Cleared all in-memory cache data")

    def test_comprehensive_cache_flow(self, tmp_path):
        """Test comprehensive cache flow covering edge cases."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider", ttl=60)

            # Start with empty cache
            assert cache.get() is None

            # Set cache
            test_models = [
                Model(
                    id="model1",
                    name="Model 1",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                ),
                Model(
                    id="model2",
                    name="Model 2",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["embedding"],
                ),
            ]
            cache.set(test_models)

            # Should be in memory cache
            result = cache.get()
            assert len(result) == 2
            assert result[0].id == "model1"

            # Clear memory cache, should fall back to file
            del cache._memory_cache["test_provider"]
            result = cache.get()
            assert len(result) == 2
            assert result[0].id == "model1"

            # Should have restored memory cache
            assert "test_provider" in cache._memory_cache

            # Clear everything
            cache.clear()
            assert cache.get() is None
            assert "test_provider" not in cache._memory_cache
            assert not cache.cache_file.exists()

    def test_cache_with_custom_ttl(self, tmp_path):
        """Test cache with custom TTL settings."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            # Test with custom TTL
            cache = ModelDiscoveryCache("test_provider", ttl=10)
            assert cache.ttl == 10

            # Test with None TTL (uses default)
            cache_default = ModelDiscoveryCache("test_provider2", ttl=None)
            assert cache_default.ttl == ModelDiscoveryCache.DEFAULT_TTL

    def test_cache_directory_creation(self, tmp_path):
        """Test cache directory creation."""
        # Use a non-existent subdirectory
        cache_dir = tmp_path / "non_existent" / "cache"

        with patch.object(ModelDiscoveryCache, "CACHE_DIR", cache_dir):
            cache = ModelDiscoveryCache("test_provider")

            # Directory should be created
            assert cache_dir.exists()
            assert cache_dir.is_dir()

    def test_memory_cache_hit_with_valid_data(self, tmp_path):
        """Test memory cache hit with valid data and logging."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Add fresh data to memory cache
            test_models = [
                Model(
                    id="test",
                    name="Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]
            cache._memory_cache["test_provider"] = (time.time(), test_models)

            with patch("scriptrag.llm.model_cache.logger.debug") as mock_debug:
                result = cache.get()

                assert result == test_models
                mock_debug.assert_called()
                debug_msg = mock_debug.call_args[0][0]
                assert "Using in-memory cached models for test_provider" in debug_msg

    def test_file_cache_with_successful_restore_to_memory(self, tmp_path):
        """Test file cache restoration to memory cache."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Create valid file cache
            cache_data = {
                "timestamp": time.time(),
                "models": [
                    {
                        "id": "test_model",
                        "name": "Test Model",
                        "provider": "claude_code",
                        "capabilities": ["chat", "completion"],
                    }
                ],
                "provider": "test_provider",
            }
            cache.cache_file.write_text(json.dumps(cache_data))

            with patch("scriptrag.llm.model_cache.logger.info") as mock_info:
                result = cache.get()

                # Should successfully load and restore to memory
                assert len(result) == 1
                assert result[0].id == "test_model"
                assert result[0].capabilities == ["chat", "completion"]

                # Should be restored to memory cache
                assert "test_provider" in cache._memory_cache

                # Should log successful cache use
                mock_info.assert_called()
                info_msg = mock_info.call_args[0][0]
                assert "Using file cached models for test_provider" in info_msg

    def test_invalid_memory_cache_entry_empty_tuple(self, tmp_path):
        """Test handling of invalid empty tuple in memory cache."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Add invalid empty tuple to memory cache
            cache._memory_cache["test_provider"] = ()

            with patch("scriptrag.llm.model_cache.logger.warning") as mock_warning:
                result = cache.get()

                # Should return None for invalid entry
                assert result is None

                # Should log warning about invalid entry
                mock_warning.assert_called_once()
                warning_msg = mock_warning.call_args[0][0]
                assert "Invalid cache entry for test_provider" in warning_msg

                # Should include entry details in kwargs
                warning_kwargs = mock_warning.call_args[1]
                assert warning_kwargs["entry_type"] == "tuple"
                assert warning_kwargs["entry_len"] == 0

                # Should have cleared the invalid entry
                assert "test_provider" not in cache._memory_cache

    def test_invalid_memory_cache_entry_single_tuple(self, tmp_path):
        """Test handling of invalid single-element tuple in memory cache."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Add invalid single-element tuple to memory cache
            cache._memory_cache["test_provider"] = (time.time(),)

            with patch("scriptrag.llm.model_cache.logger.warning") as mock_warning:
                result = cache.get()

                # Should return None for invalid entry
                assert result is None

                # Should log warning about invalid entry
                mock_warning.assert_called_once()
                warning_msg = mock_warning.call_args[0][0]
                assert "Invalid cache entry for test_provider" in warning_msg

                # Should include entry details in kwargs
                warning_kwargs = mock_warning.call_args[1]
                assert warning_kwargs["entry_type"] == "tuple"
                assert warning_kwargs["entry_len"] == 1

                # Should have cleared the invalid entry
                assert "test_provider" not in cache._memory_cache

    def test_invalid_memory_cache_entry_non_tuple(self, tmp_path):
        """Test handling of non-tuple invalid entry in memory cache."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Add invalid non-tuple entry to memory cache
            cache._memory_cache["test_provider"] = "invalid_string_entry"

            with patch("scriptrag.llm.model_cache.logger.warning") as mock_warning:
                result = cache.get()

                # Should return None for invalid entry
                assert result is None

                # Should log warning about invalid entry
                mock_warning.assert_called_once()
                warning_msg = mock_warning.call_args[0][0]
                assert "Invalid cache entry for test_provider" in warning_msg

                # Should include entry details in kwargs
                warning_kwargs = mock_warning.call_args[1]
                assert warning_kwargs["entry_type"] == "str"
                assert warning_kwargs["entry_len"] == "N/A"

                # Should have cleared the invalid entry
                assert "test_provider" not in cache._memory_cache

    def test_invalid_memory_cache_entry_wrong_sized_tuple(self, tmp_path):
        """Test handling of wrong-sized tuple (not 2 or 3) in memory cache."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Add invalid 4-element tuple to memory cache
            cache._memory_cache["test_provider"] = (time.time(), [], "extra", "invalid")

            with patch("scriptrag.llm.model_cache.logger.warning") as mock_warning:
                result = cache.get()

                # Should return None for invalid entry
                assert result is None

                # Should log warning about invalid entry
                mock_warning.assert_called_once()
                warning_msg = mock_warning.call_args[0][0]
                assert "Invalid cache entry for test_provider" in warning_msg

                # Should include entry details in kwargs
                warning_kwargs = mock_warning.call_args[1]
                assert warning_kwargs["entry_type"] == "tuple"
                assert warning_kwargs["entry_len"] == 4

                # Should have cleared the invalid entry
                assert "test_provider" not in cache._memory_cache

    def test_set_fdopen_failure_cleanup(self, tmp_path):
        """Test that file descriptor is properly closed when fdopen fails.

        This test verifies the fix for PR #323 where fdopen could fail after
        mkstemp succeeds, potentially leaking file descriptors on Windows.
        """
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            test_models = [
                Model(
                    id="model1",
                    name="Test Model",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            # Track the file descriptor from mkstemp
            captured_fd = None
            original_mkstemp = tempfile.mkstemp

            def mock_mkstemp(*args, **kwargs):
                nonlocal captured_fd
                fd, path = original_mkstemp(*args, **kwargs)
                captured_fd = fd
                return fd, path

            # Mock fdopen to fail after mkstemp succeeds
            with (
                patch("tempfile.mkstemp", side_effect=mock_mkstemp),
                patch("os.fdopen", side_effect=OSError("fdopen failed")),
                patch("os.close") as mock_close,
                patch("scriptrag.llm.model_cache.logger.error") as mock_error,
            ):
                # Should not raise, but handle cleanup properly
                cache.set(test_models)

                # Verify that os.close was called on the file descriptor
                assert captured_fd is not None, "mkstemp should have been called"
                mock_close.assert_called_once_with(captured_fd)

                # Verify error was logged
                mock_error.assert_called_once()
                error_msg = mock_error.call_args[0][0]
                assert "OS error when caching models for test_provider" in error_msg

                # Memory cache should still be updated despite file write failure
                assert "test_provider" in cache._memory_cache
                cached_entry = cache._memory_cache["test_provider"]
                assert len(cached_entry) == 3  # (timestamp, models, cache_dir)
                assert cached_entry[1] == test_models

            # Verify no temp files leaked
            temp_files = list(tmp_path.glob(".test_provider_models_*.tmp"))
            assert len(temp_files) == 0, "Temp files should be cleaned up"
