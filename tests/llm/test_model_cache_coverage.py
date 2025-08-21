"""Comprehensive tests for Model Cache to achieve 99% coverage."""

import errno
import json
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
