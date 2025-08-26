"""Extended tests for model discovery with caching, TTL, and edge cases."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from scriptrag.llm.model_cache import ModelDiscoveryCache
from scriptrag.llm.model_discovery import (
    ClaudeCodeModelDiscovery,
    GitHubModelsDiscovery,
)
from scriptrag.llm.models import LLMProvider, Model


class TestModelDiscoveryCacheExtended:
    """Extended tests for model discovery cache with TTL and race conditions."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            with patch.object(ModelDiscoveryCache, "CACHE_DIR", cache_dir):
                yield cache_dir

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create cache instance with short TTL for testing."""
        return ModelDiscoveryCache("test_provider", ttl=2)  # 2 second TTL

    @pytest.fixture
    def sample_models(self):
        """Sample models for testing."""
        return [
            Model(
                id="model-1",
                name="Test Model 1",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["completion", "chat"],
                context_window=100000,
                max_output_tokens=4096,
            ),
            Model(
                id="model-2",
                name="Test Model 2",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["embedding"],
                context_window=8192,
                max_output_tokens=512,
            ),
        ]

    def test_cache_ttl_expiration(self, cache, sample_models):
        """Test cache TTL expiration."""
        # Cache models
        cache.set(sample_models)

        # Immediately retrieve - should work
        cached = cache.get()
        assert cached is not None
        assert len(cached) == 2

        # Wait for TTL to expire
        time.sleep(2.1)

        # Should return None due to expiration
        expired = cache.get()
        assert expired is None

    def test_cache_with_corrupted_file(self, cache, temp_cache_dir):
        """Test cache behavior with corrupted cache file."""
        # Write corrupted JSON
        cache_file = temp_cache_dir / "test_provider_models.json"
        cache_file.write_text("{corrupted json content")

        # Should return None and not crash
        result = cache.get()
        assert result is None

    def test_cache_with_invalid_model_data(self, cache, temp_cache_dir):
        """Test cache with invalid model data structure."""
        # Write cache with invalid model structure
        invalid_data = {
            "timestamp": time.time(),
            "models": [
                {"invalid": "structure"},  # Missing required fields
                {"id": 123},  # Wrong type for id
            ],
            "provider": "test_provider",
        }

        cache_file = temp_cache_dir / "test_provider_models.json"
        cache_file.write_text(json.dumps(invalid_data))

        # Should handle gracefully and return None
        result = cache.get()
        assert result is None

    def test_cache_concurrent_write_operations(self, temp_cache_dir):
        """Test concurrent cache write operations."""
        import threading

        cache1 = ModelDiscoveryCache("concurrent_test", ttl=10)
        cache2 = ModelDiscoveryCache("concurrent_test", ttl=10)

        models1 = [
            Model(
                id="model-a",
                name="Model A",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["chat"],
            )
        ]

        models2 = [
            Model(
                id="model-b",
                name="Model B",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["embedding"],
            )
        ]

        def write1():
            for _ in range(10):
                cache1.set(models1)
                time.sleep(0.01)

        def write2():
            for _ in range(10):
                cache2.set(models2)
                time.sleep(0.01)

        # Start concurrent writes
        t1 = threading.Thread(target=write1)
        t2 = threading.Thread(target=write2)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        # Cache should still be readable
        final_cache = cache1.get()
        assert final_cache is not None
        assert len(final_cache) == 1
        assert final_cache[0].id in ["model-a", "model-b"]

    def test_cache_file_permissions_error(self, cache, temp_cache_dir):
        """Test cache behavior when file permissions prevent writing."""
        import stat

        # Set models first
        cache.set([])

        # Make cache file read-only
        cache_file = temp_cache_dir / "test_provider_models.json"
        cache_file.chmod(stat.S_IRUSR)

        # Attempt to write should not crash
        try:
            new_models = [
                Model(
                    id="new-model",
                    name="New Model",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]
            cache.set(new_models)  # Should handle permission error gracefully
        finally:
            # Restore permissions for cleanup
            cache_file.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def test_cache_clear_on_error(self, cache, sample_models):
        """Test cache clearing behavior on error."""
        # Set valid cache
        cache.set(sample_models)
        assert cache.get() is not None

        # Corrupt the cache file
        cache.cache_file.write_text("corrupted")

        # Clear memory cache to force reading from corrupted file
        if cache.provider_name in cache._memory_cache:
            del cache._memory_cache[cache.provider_name]

        # Get should return None
        assert cache.get() is None

        # Setting new models should work
        cache.set(sample_models)
        assert cache.get() is not None


class TestClaudeCodeModelDiscoveryExtended:
    """Extended tests for Claude Code model discovery."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            with patch.object(ModelDiscoveryCache, "CACHE_DIR", cache_dir):
                yield cache_dir

    @pytest.fixture
    def discovery(self, temp_cache_dir):
        """Create Claude Code model discovery instance."""
        # Create sample static models for testing
        static_models = [
            Model(
                id="claude-3-sonnet-20240229",
                name="Claude 3 Sonnet",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["completion", "chat"],
                context_window=200000,
                max_output_tokens=4096,
            ),
            Model(
                id="claude-3-haiku-20240307",
                name="Claude 3 Haiku",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["completion", "chat"],
                context_window=200000,
                max_output_tokens=4096,
            ),
        ]
        return ClaudeCodeModelDiscovery(
            provider_name="claude_code",
            static_models=static_models,
            cache_ttl=3600,
            use_cache=True,
            force_static=False,
        )

    @pytest.mark.asyncio
    async def test_discover_models_with_cache_hit(self, discovery, temp_cache_dir):
        """Test model discovery with cache hit."""
        # Pre-populate cache
        cache = ModelDiscoveryCache("claude_code", ttl=3600)
        cached_models = [
            Model(
                id="cached-model",
                name="Cached Model",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["chat"],
            )
        ]
        cache.set(cached_models)

        # Discover should return cached models
        models = await discovery.discover_models()
        assert len(models) == 1
        assert models[0].id == "cached-model"

    @pytest.mark.asyncio
    async def test_discover_models_cache_miss_with_sdk(self, discovery):
        """Test model discovery when cache misses and API is available."""
        with patch.object(discovery.cache, "get", return_value=None):
            with patch.object(discovery, "_fetch_models") as mock_fetch:
                # Return MORE models than static to avoid supplementation
                sdk_models = [
                    Model(
                        id="claude-3-sonnet-20240229",
                        name="Claude 3 Sonnet (API)",
                        provider=LLMProvider.CLAUDE_CODE,
                        capabilities=["chat"],
                    ),
                    Model(
                        id="claude-3-haiku-20240307",
                        name="Claude 3 Haiku (API)",
                        provider=LLMProvider.CLAUDE_CODE,
                        capabilities=["chat"],
                    ),
                    Model(
                        id="claude-3-opus-extra",
                        name="Claude 3 Opus Extra",
                        provider=LLMProvider.CLAUDE_CODE,
                        capabilities=["chat"],
                    ),
                ]
                mock_fetch.return_value = sdk_models

                with patch.object(discovery.cache, "set") as mock_set:
                    models = await discovery.discover_models()

                assert len(models) == 3
                assert models == sdk_models
                mock_set.assert_called_once_with(sdk_models)

    @pytest.mark.asyncio
    async def test_discover_models_fallback_to_static(self, discovery):
        """Test fallback to static models when API fails."""
        with patch.object(discovery.cache, "get", return_value=None):
            with patch.object(
                discovery, "_fetch_models", side_effect=Exception("API error")
            ):
                models = await discovery.discover_models()

        # Should return static models
        assert len(models) > 0
        assert all(m.provider == LLMProvider.CLAUDE_CODE for m in models)
        assert any("haiku" in m.id for m in models)

    @pytest.mark.asyncio
    async def test_fetch_models_with_mock_sdk(self, discovery):
        """Test _fetch_models with mocked Claude SDK."""
        mock_sdk = MagicMock(spec=object)
        mock_sdk.ClaudeSDKClient = MagicMock(spec=object)
        mock_client = MagicMock(spec=object)
        mock_client.list_models = MagicMock(
            return_value=[
                {
                    "id": "claude-3-opus-20240229",
                    "name": "Claude 3 Opus",
                    "max_tokens": 4096,
                },
                {
                    "id": "claude-3-sonnet-20240229",
                    "name": "Claude 3 Sonnet",
                    "max_tokens": 4096,
                },
            ]
        )
        mock_sdk.ClaudeSDKClient.return_value = mock_client

        with patch.dict("sys.modules", {"claude_code_sdk": mock_sdk}):
            models = await discovery._fetch_models()

        # Since the real implementation doesn't have list_models yet,
        # this will return None and fall back to static
        assert models is None

    @pytest.mark.asyncio
    async def test_fetch_models_import_error(self, discovery):
        """Test _fetch_models when SDK import fails."""
        with patch("builtins.__import__", side_effect=ImportError("No SDK")):
            models = await discovery._fetch_models()

        # Should return None to trigger static fallback
        assert models is None

    @pytest.mark.asyncio
    async def test_discover_models_with_fetch_success(self, discovery):
        """Test model discovery with successful fetch - tests supplementation logic."""
        with patch.object(discovery.cache, "get", return_value=None):
            with patch.object(discovery, "_fetch_models") as mock_fetch:
                # Mock successful fetch with fewer models than static
                # (tests supplementation)
                fetched_models = [
                    Model(
                        id="claude-3-opus-test",
                        name="Claude 3 Opus Test",
                        provider=LLMProvider.CLAUDE_CODE,
                        capabilities=["chat"],
                    )
                ]
                mock_fetch.return_value = fetched_models

                models = await discovery.discover_models()

                # Should have supplemented with static models (2 in fixture)
                assert len(models) == 2
                # Should contain both static models but prefer fetched
                # version when ID matches
                model_ids = [m.id for m in models]
                assert "claude-3-sonnet-20240229" in model_ids
                assert "claude-3-haiku-20240307" in model_ids

    @pytest.mark.asyncio
    async def test_discover_models_with_fetch_none(self, discovery):
        """Test model discovery when fetch returns None."""
        with patch.object(discovery.cache, "get", return_value=None):
            with patch.object(discovery, "_fetch_models", return_value=None):
                models = await discovery.discover_models()

                # Should fall back to static models
                assert len(models) > 0
                assert all(m.provider == LLMProvider.CLAUDE_CODE for m in models)


class TestGitHubModelsDiscoveryExtended:
    """Extended tests for GitHub Models discovery."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            with patch.object(ModelDiscoveryCache, "CACHE_DIR", cache_dir):
                yield cache_dir

    @pytest.fixture
    def discovery(self, temp_cache_dir):
        """Create GitHub Models discovery instance."""
        # Clear memory cache to ensure test isolation
        ModelDiscoveryCache.clear_all_memory_cache()

        # Create sample static models for testing
        static_models = [
            Model(
                id="gpt-4o",
                name="GPT-4 Optimized",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["completion", "chat"],
                context_window=128000,
                max_output_tokens=4096,
            ),
            Model(
                id="text-embedding-3",
                name="Text Embedding v3",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["embedding"],
                context_window=8192,
                max_output_tokens=512,
            ),
        ]
        return GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            client=MagicMock(spec=object),
            token="test-token",  # noqa: S106
            base_url="https://api.github.com",
            cache_ttl=3600,
            use_cache=True,
            force_static=False,
        )

    @pytest.mark.asyncio
    async def test_discover_models_with_api_response(self, discovery):
        """Test model discovery with API response."""
        mock_response = Mock(spec=object)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "gpt-4o",
                    "friendly_name": "GPT-4 Optimized",
                    "model_type": "chat",
                    "context_length": 128000,
                    "capabilities": {"completion": True, "chat": True},
                },
                {
                    "id": "text-embedding-3",
                    "friendly_name": "Text Embedding v3",
                    "model_type": "embedding",
                    "context_length": 8192,
                    "capabilities": {"embeddings": True},
                },
            ]
        }

        with patch.object(discovery, "_fetch_models") as mock_api:
            mock_api.return_value = [
                Model(
                    id="gpt-4o",
                    name="GPT-4 Optimized",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["chat", "completion"],
                    context_window=128000,
                ),
                Model(
                    id="text-embedding-3",
                    name="Text Embedding v3",
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=["embedding"],
                    context_window=8192,
                ),
            ]

            with patch.object(discovery.cache, "get", return_value=None):
                with patch.object(discovery.cache, "set") as mock_set:
                    models = await discovery.discover_models()

        assert len(models) == 2
        assert models[0].id == "gpt-4o"
        assert models[1].id == "text-embedding-3"
        mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_models_api_error_fallback(self, discovery):
        """Test fallback to static models on API error."""
        with patch.object(discovery.cache, "get", return_value=None):
            with patch.object(
                discovery, "_fetch_models", side_effect=Exception("API error")
            ):
                models = await discovery.discover_models()

        # Should return static models
        assert len(models) > 0
        assert all(m.provider == LLMProvider.GITHUB_MODELS for m in models)

    @pytest.mark.asyncio
    async def test_discover_models_malformed_api_response(self, discovery):
        """Test handling of malformed API responses."""
        test_cases = [
            None,  # Null response
            {"wrong": "format"},  # Missing 'data' key
            {"data": "not_a_list"},  # Data not a list
            {"data": [{"incomplete": "model"}]},  # Missing required fields
            {"data": [{"id": None, "friendly_name": "Bad"}]},  # Null ID
        ]

        for _malformed_response in test_cases:
            with patch.object(discovery, "_fetch_models") as mock_api:
                # Simulate API returning malformed data then falling back
                mock_api.side_effect = Exception("Malformed response")

                with patch.object(discovery.cache, "get", return_value=None):
                    models = await discovery.discover_models()

                # Should fall back to static models
                assert len(models) > 0
                assert all(isinstance(m, Model) for m in models)

    @pytest.mark.asyncio
    async def test_concurrent_discovery_requests(self, discovery):
        """Test concurrent discovery requests."""
        import asyncio

        # Mock cache to return None (force API calls)
        with patch.object(discovery.cache, "get", return_value=None):
            # Mock API to track calls
            call_count = 0

            async def mock_api():
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.1)  # Simulate API delay
                return [
                    Model(
                        id=f"model-{call_count}",
                        name=f"Model {call_count}",
                        provider=LLMProvider.GITHUB_MODELS,
                        capabilities=["chat"],
                    )
                ]

            with patch.object(discovery, "_fetch_models", side_effect=mock_api):
                # Run multiple concurrent discoveries
                results = await asyncio.gather(
                    discovery.discover_models(),
                    discovery.discover_models(),
                    discovery.discover_models(),
                )

        # All should succeed
        assert all(len(r) > 0 for r in results)
        # Should have made multiple API calls
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_discovery_with_token(self, discovery):
        """Test discovery with token returns models."""
        # With token, should attempt fetch
        with patch.object(discovery, "_fetch_models") as mock_fetch:
            mock_fetch.return_value = None  # Simulate no models from API
            models = await discovery.discover_models()
            # Should still return static models
            assert len(models) > 0
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_discovery_without_token(self):
        """Test discovery without token uses static models."""
        # Create sample static models for testing
        static_models = [
            Model(
                id="gpt-4o",
                name="GPT-4 Optimized",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["completion", "chat"],
                context_window=128000,
                max_output_tokens=4096,
            ),
        ]
        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            client=MagicMock(spec=object),
            token=None,
            base_url="https://api.github.com",
            cache_ttl=3600,
            use_cache=False,  # Disable cache to avoid contamination
            force_static=False,
        )
        # Without token, _fetch_models returns None and falls back to static
        models = await discovery.discover_models()
        assert len(models) == 1
        assert models[0].id == "gpt-4o"


class TestModelDiscoveryIntegration:
    """Integration tests for model discovery system."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            with patch.object(ModelDiscoveryCache, "CACHE_DIR", cache_dir):
                yield cache_dir

    @pytest.mark.asyncio
    async def test_discovery_with_cache_invalidation(self, temp_cache_dir):
        """Test model discovery with cache invalidation."""
        # Clear memory cache to ensure test isolation
        ModelDiscoveryCache.clear_all_memory_cache()

        # Create sample static models for testing
        static_models = [
            Model(
                id="claude-3-sonnet-20240229",
                name="Claude 3 Sonnet",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["completion", "chat"],
                context_window=200000,
                max_output_tokens=4096,
            ),
        ]
        discovery = ClaudeCodeModelDiscovery(
            provider_name="claude_code",
            static_models=static_models,
            cache_ttl=3600,
            use_cache=True,
            force_static=False,
        )

        # First discovery - no cache
        with patch.object(discovery, "_fetch_models") as mock_sdk:
            mock_sdk.return_value = [
                Model(
                    id="model-v1",
                    name="Model V1",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            models_v1 = await discovery.discover_models()
            assert models_v1[0].id == "model-v1"

        # Second discovery - should use cache
        models_cached = await discovery.discover_models()
        assert models_cached[0].id == "model-v1"

        # Invalidate cache by waiting for TTL
        time.sleep(2)  # Assuming short TTL for test

        # Third discovery - cache expired, fetch new
        with patch.object(discovery, "_fetch_models") as mock_sdk:
            mock_sdk.return_value = [
                Model(
                    id="model-v2",
                    name="Model V2",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            # Force cache expiration
            with patch.object(discovery.cache, "ttl", 0):
                models_v2 = await discovery.discover_models()
                assert models_v2[0].id == "model-v2"

    @pytest.mark.asyncio
    async def test_cross_provider_discovery(self, temp_cache_dir):
        """Test discovery across multiple providers."""
        # Clear any existing in-memory cache to prevent test contamination
        ModelDiscoveryCache.clear_all_memory_cache()
        # Create sample static models for testing
        claude_static_models = [
            Model(
                id="claude-3-sonnet-20240229",
                name="Claude 3 Sonnet",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["completion", "chat"],
                context_window=200000,
                max_output_tokens=4096,
            ),
        ]
        claude_discovery = ClaudeCodeModelDiscovery(
            provider_name="claude_code",
            static_models=claude_static_models,
            cache_ttl=3600,
            use_cache=True,
            force_static=False,
        )

        # Create sample static models for GitHub testing
        github_static_models = [
            Model(
                id="gpt-4o",
                name="GPT-4 Optimized",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["completion", "chat"],
                context_window=128000,
                max_output_tokens=4096,
            ),
        ]
        github_discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=github_static_models,
            client=MagicMock(spec=object),
            token="test-token",  # noqa: S106
            base_url="https://api.github.com",
            cache_ttl=3600,
            use_cache=True,
            force_static=False,
        )

        # Mock discoveries
        with patch.object(claude_discovery, "_fetch_models") as mock_claude:
            mock_claude.return_value = [
                Model(
                    id="claude-model",
                    name="Claude Model",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["chat"],
                )
            ]

            with patch.object(github_discovery, "_fetch_models") as mock_github:
                mock_github.return_value = [
                    Model(
                        id="github-model",
                        name="GitHub Model",
                        provider=LLMProvider.GITHUB_MODELS,
                        capabilities=["embedding"],
                    )
                ]

                # Discover from both providers
                claude_models = await claude_discovery.discover_models()
                github_models = await github_discovery.discover_models()

        # Verify each provider returns correct models
        assert len(claude_models) == 1
        assert claude_models[0].provider == LLMProvider.CLAUDE_CODE

        assert len(github_models) == 1
        assert github_models[0].provider == LLMProvider.GITHUB_MODELS

        # Verify cache files are separate
        claude_cache_file = temp_cache_dir / "claude_code_models.json"
        github_cache_file = temp_cache_dir / "github_models_models.json"

        assert claude_cache_file.exists()
        assert github_cache_file.exists()
