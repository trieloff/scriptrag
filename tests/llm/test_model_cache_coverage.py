"""Comprehensive tests for Model Cache to achieve 99% coverage."""

import errno
import json
import sys
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

    def test_disk_cache_only(self, tmp_path):
        """Test disk cache fallback when memory cache misses."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # First, set some models to create disk cache
            test_models = [
                Model(
                    id="test",
                    name="Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]
            cache.set(test_models)

            # Clear memory cache to force disk read
            ModelDiscoveryCache.clear_all_memory_cache()

            # Create new cache instance
            cache2 = ModelDiscoveryCache("test_provider")

            with patch("scriptrag.llm.model_cache.logger.info") as mock_info:
                result = cache2.get()

                # Should find models from disk
                assert result is not None
                assert len(result) == 1
                assert result[0].id == "test"

                # Check for disk cache hit message - logs at INFO level
                info_calls = [call[0][0] for call in mock_info.call_args_list]
                assert any(
                    "Using file cached models for test_provider" in msg
                    for msg in info_calls
                )

    def test_cache_miss(self, tmp_path):
        """Test complete cache miss (no memory or disk cache)."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            with patch("scriptrag.llm.model_cache.logger.debug") as mock_debug:
                result = cache.get()

                # Should return None for cache miss
                assert result is None

                # Check for the actual debug messages
                debug_calls = [call[0][0] for call in mock_debug.call_args_list]
                # Should log no cache file found - new message format
                assert any(
                    "No cache file found for test_provider" in msg
                    for msg in debug_calls
                )

    def test_disk_cache_expiry(self, tmp_path):
        """Test disk cache expiry check."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Create expired disk cache file with new structured format
            cache_file = tmp_path / "test_provider_models.json"
            old_time = time.time() - cache.ttl - 1

            # Write expired cache in new structured format
            cache_data = {
                "timestamp": old_time,
                "models": [
                    {
                        "id": "test",
                        "name": "Test",
                        "provider": "claude_code",
                        "capabilities": ["chat"],
                        "context_window": None,
                        "max_output_tokens": None,
                        "description": None,
                    }
                ],
                "provider": "test_provider",
            }
            cache_file.write_text(json.dumps(cache_data))

            with patch("scriptrag.llm.model_cache.logger.debug") as mock_debug:
                result = cache.get()

                # Should return None for expired disk cache
                assert result is None

                # Check for expired disk cache message
                debug_calls = [call[0][0] for call in mock_debug.call_args_list]
                assert any(
                    "File cache expired for test_provider" in msg for msg in debug_calls
                )

    def test_invalid_json_cache(self, tmp_path):
        """Test handling of invalid JSON in cache file."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Create invalid JSON cache file with new filename format
            cache_file = tmp_path / "test_provider_models.json"
            cache_file.write_text("{'invalid': json}")

            with patch("scriptrag.llm.model_cache.logger.warning") as mock_warning:
                result = cache.get()

                # Should return None for invalid cache
                assert result is None

                # Should log warning about cache read failure - new message format
                mock_warning.assert_called_once()
                warning_msg = mock_warning.call_args[0][0]
                assert "Failed to read cache for test_provider" in warning_msg

    def test_invalid_model_data_in_cache(self, tmp_path):
        """Test handling of invalid model data in cache."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Create cache with invalid model data in new structured format
            cache_file = tmp_path / "test_provider_models.json"
            invalid_cache_data = {
                "timestamp": time.time(),
                "models": [
                    {"id": "test", "invalid": "data"}
                ],  # Missing required fields
                "provider": "test_provider",
            }
            cache_file.write_text(json.dumps(invalid_cache_data))

            with patch("scriptrag.llm.model_cache.logger.warning") as mock_warning:
                result = cache.get()

                # Should return None for invalid model data
                assert result is None

                # Should log warning about cache read failure - new message format
                mock_warning.assert_called_once()
                warning_msg = mock_warning.call_args[0][0]
                assert "Failed to read cache for test_provider" in warning_msg

    def test_set_with_existing_memory_cache(self, tmp_path):
        """Test set when memory cache already exists."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            test_models = [
                Model(
                    id="test1",
                    name="Test 1",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            # Set initial models
            cache.set(test_models)

            # Set new models (should overwrite)
            new_models = [
                Model(
                    id="test2",
                    name="Test 2",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]
            cache.set(new_models)

            # Memory cache should have new models - now 3-tuple format
            assert "test_provider" in cache._memory_cache
            _, cached_models, _ = cache._memory_cache["test_provider"]
            assert len(cached_models) == 1
            assert cached_models[0].id == "test2"

    def test_concurrent_cache_access(self, tmp_path):
        """Test concurrent access to cache."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache1 = ModelDiscoveryCache("test_provider")
            cache2 = ModelDiscoveryCache("test_provider")

            test_models = [
                Model(
                    id="test",
                    name="Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            # Set from first cache instance
            cache1.set(test_models)

            # Get from second instance (should hit memory cache)
            result = cache2.get()
            assert result is not None
            assert len(result) == 1
            assert result[0].id == "test"

    def test_different_providers(self, tmp_path):
        """Test caching for different providers."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache1 = ModelDiscoveryCache("provider1")
            cache2 = ModelDiscoveryCache("provider2")

            models1 = [
                Model(
                    id="model1",
                    name="Model 1",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]
            models2 = [
                Model(
                    id="model2",
                    name="Model 2",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["chat"],
                )
            ]

            cache1.set(models1)
            cache2.set(models2)

            # Each provider should have its own cache
            result1 = cache1.get()
            result2 = cache2.get()

            assert result1[0].id == "model1"
            assert result2[0].id == "model2"

            # Check disk cache files - new filename format without dot prefix
            cache_files = list(tmp_path.glob("*_models.json"))
            assert len(cache_files) == 2

    def test_clear_memory_cache(self, tmp_path):
        """Test clearing memory cache."""
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

            cache.set(test_models)
            assert "test_provider" in cache._memory_cache

            # Clear memory cache
            ModelDiscoveryCache.clear_all_memory_cache()
            assert "test_provider" not in cache._memory_cache

    def test_corrupted_memory_cache_format(self, tmp_path):
        """Test handling of corrupted memory cache format."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Corrupt the memory cache with wrong format
            cache._memory_cache["test_provider"] = "invalid_format"

            with patch("scriptrag.llm.model_cache.logger.warning") as mock_warning:
                result = cache.get()

                # Should return None and log warning
                assert result is None
                mock_warning.assert_called_once()
                warning_msg = mock_warning.call_args[0][0]
                assert "Invalid cache entry for test_provider, clearing" in warning_msg

    def test_memory_cache_with_invalid_timestamp(self, tmp_path):
        """Test memory cache with invalid timestamp."""
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

            # Add entry with invalid timestamp
            cache._memory_cache["test_provider"] = ("not_a_timestamp", test_models)

            with patch("scriptrag.llm.model_cache.logger.warning") as mock_warning:
                result = cache.get()

                # Should return None and log warning
                assert result is None
                mock_warning.assert_called_once()
                warning_msg = mock_warning.call_args[0][0]
                assert "Invalid cache entry for test_provider, clearing" in warning_msg

    def test_cache_directory_permission_error_on_read(self, tmp_path):
        """Test permission error when reading cache directory."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Create cache file with new structured format
            cache_file = tmp_path / "test_provider_models.json"
            test_cache_data = {
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
            cache_file.write_text(json.dumps(test_cache_data))

            # Clear memory cache to force disk read
            ModelDiscoveryCache.clear_all_memory_cache()

            # Mock pathlib.Path.open to raise PermissionError
            with (
                patch("pathlib.Path.open", side_effect=PermissionError),
                patch("scriptrag.llm.model_cache.logger.warning") as mock_warning,
            ):
                result = cache.get()

                # Should return None
                assert result is None

                # Should log warning with new message format
                mock_warning.assert_called_once()
                warning_msg = mock_warning.call_args[0][0]
                assert "Failed to read cache for test_provider" in warning_msg

    def test_empty_models_list(self, tmp_path):
        """Test caching an empty models list."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Set empty list
            cache.set([])

            # Should still be cached
            result = cache.get()
            assert result is not None
            assert len(result) == 0

            # Check disk cache - new filename format and structured data
            cache_file = tmp_path / "test_provider_models.json"
            assert cache_file.exists()
            cache_data = json.loads(cache_file.read_text())
            assert cache_data["models"] == []

    def test_models_with_all_optional_fields(self, tmp_path):
        """Test caching models with all optional fields set."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            test_models = [
                Model(
                    id="test",
                    name="Test Model",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat", "code", "vision"],
                    context_window=100000,
                    max_output_tokens=4096,
                )
            ]

            cache.set(test_models)
            result = cache.get()

            assert result is not None
            assert len(result) == 1
            model = result[0]
            assert model.id == "test"
            assert model.context_window == 100000
            assert model.max_output_tokens == 4096

    def test_cache_with_long_provider_name(self, tmp_path):
        """Test caching with a very long provider name."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            long_provider = "a" * 255  # Max filename length on most systems
            cache = ModelDiscoveryCache(long_provider)

            test_models = [
                Model(
                    id="test",
                    name="Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            cache.set(test_models)
            result = cache.get()

            assert result is not None
            assert len(result) == 1

    def test_unicode_in_model_data(self, tmp_path):
        """Test caching models with unicode characters."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            test_models = [
                Model(
                    id="test",
                    name="测试模型 🚀",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            cache.set(test_models)
            result = cache.get()

            assert result is not None
            assert result[0].name == "测试模型 🚀"

    def test_memory_cache_with_unexpected_tuple_size(self, tmp_path):
        """Test memory cache with unexpected tuple size (not 2 or 3)."""
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

            # Add entry with 4-tuple (unexpected)
            cache._memory_cache["test_provider"] = (
                time.time(),
                test_models,
                str(tmp_path),
                "extra",
            )

            with patch("scriptrag.llm.model_cache.logger.warning") as mock_warning:
                result = cache.get()

                # Should return None and log warning
                assert result is None
                mock_warning.assert_called_once()
                warning_msg = mock_warning.call_args[0][0]
                warning_kwargs = mock_warning.call_args[1]

                assert "Invalid cache entry for test_provider, clearing" in warning_msg
                assert warning_kwargs["entry_type"] == "tuple"
                assert warning_kwargs["entry_len"] == 4

                # Should have cleared the invalid entry
                assert "test_provider" not in cache._memory_cache

    def test_cache_dir_creation_os_error(self, tmp_path):
        """Test OSError during cache directory creation (lines 62-64)."""
        # Create a cache dir that already exists but as a file (not directory)
        broken_cache_dir = tmp_path / "broken_cache"
        broken_cache_dir.write_text("This is a file, not a directory")

        with (
            patch.object(ModelDiscoveryCache, "CACHE_DIR", broken_cache_dir),
            patch("scriptrag.llm.model_cache.logger.error") as mock_error,
            pytest.raises(OSError),
        ):
            ModelDiscoveryCache("test_provider")

            # Should log the error
            mock_error.assert_called_once()
            error_msg = mock_error.call_args[0][0]
            assert "Failed to create cache directory" in error_msg

    def test_memory_cache_namespace_mismatch(self, tmp_path):
        """Test namespace mismatch in memory cache (line 82)."""
        cache_dir_1 = tmp_path / "cache1"
        cache_dir_2 = tmp_path / "cache2"

        # Create cache with first directory
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", cache_dir_1):
            cache1 = ModelDiscoveryCache("test_provider")

            # Add to memory cache with first namespace
            test_models = [
                Model(
                    id="test",
                    name="Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]
            cache1._memory_cache["test_provider"] = (
                time.time(),
                test_models,
                str(cache_dir_1.resolve()),
            )

        # Now create cache with different directory
        with (
            patch.object(ModelDiscoveryCache, "CACHE_DIR", cache_dir_2),
            patch("scriptrag.llm.model_cache.logger.debug") as mock_debug,
        ):
            cache2 = ModelDiscoveryCache("test_provider")
            result = cache2.get()

            # Should return None due to namespace mismatch
            assert result is None

            # Should log the namespace mismatch
            debug_calls = [call[0][0] for call in mock_debug.call_args_list]
            assert any(
                "Ignoring in-memory cache for provider due to different namespace"
                in msg
                for msg in debug_calls
            )

    def test_memory_cache_3_tuple_expiry(self, tmp_path):
        """Test expiry handling for 3-tuple memory cache entries (lines 99-100)."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", tmp_path):
            cache = ModelDiscoveryCache("test_provider")

            # Add expired 3-tuple entry to memory cache
            old_timestamp = time.time() - cache.ttl - 1
            test_models = [
                Model(
                    id="test",
                    name="Test",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]
            cache._memory_cache["test_provider"] = (
                old_timestamp,
                test_models,
                str(tmp_path.resolve()),
            )

            with patch("scriptrag.llm.model_cache.logger.debug") as mock_debug:
                result = cache.get()

                # Should return None and clear expired entry
                assert result is None
                assert "test_provider" not in cache._memory_cache

                # Should log expiry
                debug_calls = [call[0][0] for call in mock_debug.call_args_list]
                assert any("expired" in msg for msg in debug_calls)

    def test_temp_file_creation_exception_cleanup(self, tmp_path):
        """Test exception cleanup in temp file creation (lines 222-233)."""
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

            # Mock tempfile.mkstemp to succeed but os.fdopen to fail
            mock_fd = 99  # Fake file descriptor
            mock_temp_path = str(tmp_path / "fake_temp_file.tmp")

            with (
                patch("tempfile.mkstemp") as mock_mkstemp,
                patch("os.fdopen") as mock_fdopen,
                patch("os.close") as mock_close,
                patch("pathlib.Path.unlink") as mock_unlink,
            ):
                mock_mkstemp.return_value = (mock_fd, mock_temp_path)
                mock_fdopen.side_effect = Exception("Write failed")

                # This should trigger cleanup of both fd and temp file
                cache.set(test_models)

                # Should have attempted to close the file descriptor
                mock_close.assert_called_once_with(mock_fd)

                # Should have attempted to unlink the temp file
                mock_unlink.assert_called_once()

    def test_disk_space_error_handling(self, tmp_path):
        """Test specific ENOSPC error handling (line 238)."""
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

            # Create an OSError with ENOSPC errno
            disk_full_error = OSError(errno.ENOSPC, "No space left on device")

            with (
                patch("tempfile.mkstemp", side_effect=disk_full_error),
                patch("scriptrag.llm.model_cache.logger.error") as mock_error,
            ):
                cache.set(test_models)

                # Should log specific disk space error
                mock_error.assert_called_once()
                error_msg = mock_error.call_args[0][0]
                assert "Insufficient disk space to cache models" in error_msg

    def test_permission_denied_error_handling(self, tmp_path):
        """Test specific EACCES error handling (line 242)."""
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

            # Create an OSError with EACCES errno
            permission_error = OSError(errno.EACCES, "Permission denied")

            with (
                patch("tempfile.mkstemp", side_effect=permission_error),
                patch("scriptrag.llm.model_cache.logger.error") as mock_error,
            ):
                cache.set(test_models)

                # Should log specific permission error
                mock_error.assert_called_once()
                error_msg = mock_error.call_args[0][0]
                assert "Permission denied when caching models" in error_msg

    def test_general_exception_handling_in_set(self, tmp_path):
        """Test general Exception handling in set method (lines 249-250)."""
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

            # Create a general exception (not OSError)
            general_error = ValueError("Some random error")

            with (
                patch("json.dump", side_effect=general_error),
                patch("scriptrag.llm.model_cache.logger.warning") as mock_warning,
            ):
                cache.set(test_models)

                # Should log general exception warning
                mock_warning.assert_called_once()
                warning_msg = mock_warning.call_args[0][0]
                assert "Failed to cache models for test_provider" in warning_msg

                # Memory cache should still be updated even with file write failure
                assert "test_provider" in cache._memory_cache

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows file handle semantics differ for mocked file operations",
    )
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
