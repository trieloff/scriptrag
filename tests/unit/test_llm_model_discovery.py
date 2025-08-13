"""Unit tests for LLM model discovery system."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.llm.model_discovery import (
    ClaudeCodeModelDiscovery,
    GitHubModelsDiscovery,
    ModelDiscovery,
    ModelDiscoveryCache,
)
from scriptrag.llm.models import LLMProvider, Model


class TestModelDiscoveryCache:
    """Test model discovery caching functionality."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            with patch.object(ModelDiscoveryCache, "CACHE_DIR", cache_dir):
                yield cache_dir

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create cache instance with temporary directory."""
        return ModelDiscoveryCache("test_provider", ttl=3600)

    @pytest.fixture
    def sample_models(self):
        """Sample models for testing."""
        return [
            Model(
                id="model-1",
                name="Test Model 1",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["completion"],
                context_window=100000,
                max_output_tokens=4096,
            ),
            Model(
                id="model-2",
                name="Test Model 2",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["completion", "chat"],
                context_window=200000,
                max_output_tokens=8192,
            ),
        ]

    def test_cache_initialization(self, temp_cache_dir):
        """Test cache initialization."""
        cache = ModelDiscoveryCache("test_provider")
        assert cache.provider_name == "test_provider"
        assert cache.ttl == ModelDiscoveryCache.DEFAULT_TTL
        assert cache.cache_file.name == "test_provider_models.json"
        assert cache.cache_file.parent == temp_cache_dir

    def test_cache_initialization_custom_ttl(self, temp_cache_dir):
        """Test cache initialization with custom TTL."""
        custom_ttl = 7200
        cache = ModelDiscoveryCache("test_provider", ttl=custom_ttl)
        assert cache.ttl == custom_ttl

    def test_ensure_cache_dir_creates_directory(self, temp_cache_dir):
        """Test cache directory creation."""
        # Remove the directory
        temp_cache_dir.rmdir()
        assert not temp_cache_dir.exists()

        # Create cache instance - should recreate directory
        cache = ModelDiscoveryCache("test_provider")
        assert temp_cache_dir.exists()
        assert temp_cache_dir.is_dir()

    def test_set_and_get_models(self, cache, sample_models):
        """Test caching and retrieving models."""
        # Cache models
        cache.set(sample_models)
        assert cache.cache_file.exists()

        # Retrieve models
        cached_models = cache.get()
        assert cached_models is not None
        assert len(cached_models) == 2
        assert cached_models[0].id == "model-1"
        assert cached_models[0].name == "Test Model 1"
        assert cached_models[1].id == "model-2"
        assert cached_models[1].name == "Test Model 2"

    def test_get_nonexistent_cache(self, cache):
        """Test getting from non-existent cache."""
        result = cache.get()
        assert result is None

    def test_get_expired_cache(self, cache, sample_models):
        """Test expired cache returns None."""
        # Create cache with very short TTL
        short_ttl_cache = ModelDiscoveryCache("test_provider", ttl=1)
        short_ttl_cache.set(sample_models)

        # Wait for expiration
        time.sleep(2)

        result = short_ttl_cache.get()
        assert result is None

    def test_cache_corrupted_json(self, cache):
        """Test handling corrupted cache file."""
        # Create corrupted cache file
        cache.cache_file.write_text("invalid json")

        result = cache.get()
        assert result is None

    def test_cache_missing_fields(self, cache):
        """Test handling cache with missing required fields."""
        # Create cache with missing timestamp
        cache_data = {"models": []}
        cache.cache_file.write_text(json.dumps(cache_data))

        result = cache.get()
        assert result is None

    def test_cache_invalid_model_data(self, cache):
        """Test handling cache with invalid model data."""
        # Create cache with invalid model data
        cache_data = {
            "timestamp": time.time(),
            "models": [{"invalid": "model_data"}],
        }
        cache.cache_file.write_text(json.dumps(cache_data))

        result = cache.get()
        assert result is None

    def test_clear_cache(self, cache, sample_models):
        """Test clearing cache."""
        # Create cache
        cache.set(sample_models)
        assert cache.cache_file.exists()

        # Clear cache
        cache.clear()
        assert not cache.cache_file.exists()

    def test_clear_nonexistent_cache(self, cache):
        """Test clearing non-existent cache doesn't error."""
        # Should not raise exception
        cache.clear()

    def test_set_cache_write_error(self, cache, sample_models):
        """Test handling write errors when setting cache."""
        # Make cache file read-only
        cache.cache_file.touch()
        cache.cache_file.chmod(0o444)

        try:
            # Should not raise exception, just log warning
            cache.set(sample_models)
        except PermissionError:
            # This is expected on some systems
            pass
        finally:
            # Reset permissions for cleanup
            cache.cache_file.chmod(0o644)


class TestModelDiscovery:
    """Test base model discovery functionality."""

    @pytest.fixture
    def static_models(self):
        """Static models for testing."""
        return [
            Model(
                id="static-1",
                name="Static Model 1",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["completion"],
                context_window=100000,
                max_output_tokens=4096,
            ),
        ]

    @pytest.fixture
    def discovery(self, static_models):
        """Create model discovery instance."""
        return ModelDiscovery(
            provider_name="test_provider",
            static_models=static_models,
            use_cache=False,  # Disable cache for base tests
        )

    @pytest.fixture
    def discovery_with_cache(self, static_models):
        """Create model discovery instance with cache."""
        with patch.object(ModelDiscoveryCache, "CACHE_DIR", Path("/tmp/test_cache")):
            return ModelDiscovery(
                provider_name="test_provider",
                static_models=static_models,
                cache_ttl=3600,
                use_cache=True,
            )

    def test_discovery_initialization(self, static_models):
        """Test model discovery initialization."""
        discovery = ModelDiscovery(
            provider_name="test_provider",
            static_models=static_models,
            cache_ttl=7200,
            use_cache=True,
            force_static=True,
        )

        assert discovery.provider_name == "test_provider"
        assert discovery.static_models == static_models
        assert discovery.force_static is True
        assert discovery.cache is not None

    def test_discovery_no_cache(self, static_models):
        """Test model discovery without cache."""
        discovery = ModelDiscovery(
            provider_name="test_provider",
            static_models=static_models,
            use_cache=False,
        )

        assert discovery.cache is None

    @pytest.mark.asyncio
    async def test_discover_models_force_static(self, discovery, static_models):
        """Test forced static model discovery."""
        discovery.force_static = True

        models = await discovery.discover_models()
        assert models == static_models

    @pytest.mark.asyncio
    async def test_discover_models_from_cache(
        self, discovery_with_cache, static_models
    ):
        """Test model discovery from cache."""
        cached_models = [
            Model(
                id="cached-1",
                name="Cached Model 1",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["completion"],
                context_window=150000,
                max_output_tokens=6144,
            ),
        ]

        # Mock cache to return models
        with patch.object(
            discovery_with_cache.cache, "get", return_value=cached_models
        ):
            models = await discovery_with_cache.discover_models()
            assert models == cached_models

    @pytest.mark.asyncio
    async def test_discover_models_dynamic_success(self, discovery_with_cache):
        """Test successful dynamic model discovery."""
        dynamic_models = [
            Model(
                id="dynamic-1",
                name="Dynamic Model 1",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["completion"],
                context_window=120000,
                max_output_tokens=5120,
            ),
        ]

        # Mock cache miss and successful dynamic discovery
        with patch.object(discovery_with_cache.cache, "get", return_value=None):
            with patch.object(
                discovery_with_cache,
                "_fetch_models",
                return_value=dynamic_models,
            ):
                with patch.object(discovery_with_cache.cache, "set") as mock_set:
                    models = await discovery_with_cache.discover_models()
                    assert models == dynamic_models
                    mock_set.assert_called_once_with(dynamic_models)

    @pytest.mark.asyncio
    async def test_discover_models_dynamic_failure_fallback(
        self, discovery_with_cache, static_models
    ):
        """Test fallback to static models when dynamic discovery fails."""
        # Mock cache miss and failed dynamic discovery
        with patch.object(discovery_with_cache.cache, "get", return_value=None):
            with patch.object(
                discovery_with_cache,
                "_fetch_models",
                side_effect=Exception("API error"),
            ):
                models = await discovery_with_cache.discover_models()
                assert models == static_models

    @pytest.mark.asyncio
    async def test_fetch_models_not_implemented(self, discovery):
        """Test base class _fetch_models raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await discovery._fetch_models()


class TestClaudeCodeModelDiscovery:
    """Test Claude Code specific model discovery."""

    @pytest.fixture
    def static_models(self):
        """Static Claude models for testing."""
        return [
            Model(
                id="claude-3-sonnet-20240229",
                name="Claude 3 Sonnet",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["completion", "chat"],
                context_window=200000,
                max_output_tokens=4096,
            ),
        ]

    @pytest.fixture
    def discovery(self, static_models):
        """Create Claude Code model discovery instance."""
        return ClaudeCodeModelDiscovery(
            provider_name="claude_code",
            static_models=static_models,
            use_cache=False,
        )

    @pytest.mark.asyncio
    async def test_fetch_models_sdk_available(self, discovery):
        """Test model fetching when Claude SDK is available."""
        # Mock SDK client with list_models method
        mock_client = MagicMock()
        mock_models_data = [
            {
                "id": "claude-3-5-sonnet-20241022",
                "name": "Claude 3.5 Sonnet",
                "context_window": 200000,
                "max_output_tokens": 8192,
            },
        ]
        mock_client.list_models = AsyncMock(return_value=mock_models_data)

        with patch("claude_code_sdk.ClaudeSDKClient", return_value=mock_client):
            models = await discovery._fetch_models()

            assert models is not None
            assert len(models) == 1
            assert models[0].id == "claude-3-5-sonnet-20241022"
            assert models[0].name == "Claude 3.5 Sonnet"
            assert models[0].provider == LLMProvider.CLAUDE_CODE

    @pytest.mark.asyncio
    async def test_fetch_models_sdk_not_available(self, discovery):
        """Test model fetching when Claude SDK is not available."""
        with patch(
            "claude_code_sdk.ClaudeSDKClient",
            side_effect=ImportError("No module named 'claude_code_sdk'"),
        ):
            with patch("os.environ.get", return_value=None):
                models = await discovery._fetch_models()
                assert models is None

    @pytest.mark.asyncio
    async def test_fetch_models_anthropic_api_success(self, discovery):
        """Test model fetching from Anthropic API when SDK not available."""
        mock_response_data = {
            "data": [
                {
                    "id": "claude-3-opus-20240229",
                    "type": "model",
                    "display_name": "Claude 3 Opus",
                }
            ]
        }

        with patch("claude_code_sdk.ClaudeSDKClient", side_effect=ImportError):
            with patch("os.environ.get", return_value="test-api-key"):
                with patch(
                    "scriptrag.llm.model_discovery.httpx.AsyncClient"
                ) as mock_client_context:
                    mock_client = MagicMock()
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = mock_response_data
                    mock_client.get.return_value = mock_response
                    mock_client_context.return_value.__aenter__.return_value = (
                        mock_client
                    )

                    models = await discovery._fetch_models()
                    assert models is not None

    @pytest.mark.asyncio
    async def test_fetch_models_no_discovery_available(self, discovery):
        """Test model fetching when no discovery methods are available."""
        # Mock SDK not available and no API key
        with patch("claude_code_sdk.ClaudeSDKClient", side_effect=ImportError):
            with patch("os.environ.get", return_value=None):
                models = await discovery._fetch_models()
                assert models is None


class TestGitHubModelsDiscovery:
    """Test GitHub Models specific model discovery."""

    @pytest.fixture
    def static_models(self):
        """Static GitHub models for testing."""
        return [
            Model(
                id="gpt-4o",
                name="GPT-4o",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["completion", "chat"],
                context_window=128000,
                max_output_tokens=4096,
            ),
        ]

    @pytest.fixture
    def discovery(self, static_models):
        """Create GitHub model discovery instance."""
        return GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            use_cache=False,
        )

    @pytest.mark.asyncio
    async def test_fetch_dynamic_models_success(self, discovery):
        """Test successful GitHub API model fetching."""
        mock_api_response = {
            "data": [
                {
                    "id": "gpt-4o-mini",
                    "name": "GPT-4o Mini",
                    "context_length": 128000,
                    "max_output_tokens": 16384,
                },
                {
                    "id": "claude-3-5-sonnet",
                    "name": "Claude 3.5 Sonnet",
                    "context_length": 200000,
                    "max_output_tokens": 8192,
                },
            ]
        }

        with patch(
            "scriptrag.llm.model_discovery.aiohttp.ClientSession"
        ) as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_api_response)
            (
                mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value
            ) = mock_response

            models = await discovery._fetch_dynamic_models()

            assert len(models) == 2
            assert models[0].id == "gpt-4o-mini"
            assert models[0].name == "GPT-4o Mini"
            assert models[0].provider == LLMProvider.GITHUB_MODELS
            assert models[1].id == "claude-3-5-sonnet"

    @pytest.mark.asyncio
    async def test_fetch_dynamic_models_api_error(self, discovery):
        """Test GitHub API error handling."""
        with patch(
            "scriptrag.llm.model_discovery.aiohttp.ClientSession"
        ) as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_response.text = AsyncMock(return_value="Unauthorized")
            (
                mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value
            ) = mock_response

            with pytest.raises(Exception, match="GitHub API error"):
                await discovery._fetch_models()

    @pytest.mark.asyncio
    async def test_fetch_dynamic_models_network_error(self, discovery):
        """Test network error handling."""
        with patch(
            "scriptrag.llm.model_discovery.aiohttp.ClientSession"
        ) as mock_session:
            mock_session.return_value.__aenter__.return_value.get.side_effect = (
                Exception("Connection failed")
            )

            with pytest.raises(Exception, match="Connection failed"):
                await discovery._fetch_models()

    @pytest.mark.asyncio
    async def test_fetch_dynamic_models_no_auth_token(self, discovery):
        """Test discovery without authentication token."""
        with patch("scriptrag.llm.model_discovery.os.getenv", return_value=None):
            with pytest.raises(Exception, match="GitHub token not available"):
                await discovery._fetch_models()

    @pytest.mark.asyncio
    async def test_fetch_dynamic_models_invalid_response_format(self, discovery):
        """Test handling invalid API response format."""
        # Response missing 'data' field
        mock_api_response = {"models": []}

        with patch(
            "scriptrag.llm.model_discovery.aiohttp.ClientSession"
        ) as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_api_response)
            (
                mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value
            ) = mock_response

            with pytest.raises(Exception, match="Invalid response format"):
                await discovery._fetch_models()


class TestModelDiscoveryIntegration:
    """Integration tests for model discovery."""

    @pytest.mark.asyncio
    async def test_end_to_end_cache_workflow(self):
        """Test complete workflow with caching."""
        static_models = [
            Model(
                id="static-model",
                name="Static Model",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["completion"],
                context_window=100000,
                max_output_tokens=4096,
            ),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            with patch.object(ModelDiscoveryCache, "CACHE_DIR", cache_dir):
                discovery = ClaudeCodeModelDiscovery(
                    provider_name="claude_code",
                    static_models=static_models,
                    cache_ttl=3600,
                    use_cache=True,
                )

                # Mock dynamic discovery to return different models
                dynamic_models = [
                    Model(
                        id="dynamic-model",
                        name="Dynamic Model",
                        provider=LLMProvider.CLAUDE_CODE,
                        capabilities=["completion"],
                        context_window=150000,
                        max_output_tokens=6144,
                    ),
                ]

                with patch.object(
                    discovery, "_fetch_dynamic_models", return_value=dynamic_models
                ):
                    # First call - should fetch and cache
                    models1 = await discovery.discover_models()
                    assert models1 == dynamic_models
                    assert discovery.cache.cache_file.exists()

                # Second call - should use cache (mock fetch not called again)
                with patch.object(
                    discovery,
                    "_fetch_models",
                    side_effect=Exception("Should not be called"),
                ):
                    models2 = await discovery.discover_models()
                    assert models2 == dynamic_models

    @pytest.mark.asyncio
    async def test_cache_corruption_recovery(self):
        """Test recovery from cache corruption."""
        static_models = [
            Model(
                id="static-model",
                name="Static Model",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["completion"],
                context_window=100000,
                max_output_tokens=4096,
            ),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            with patch.object(ModelDiscoveryCache, "CACHE_DIR", cache_dir):
                discovery = ClaudeCodeModelDiscovery(
                    provider_name="claude_code",
                    static_models=static_models,
                    cache_ttl=3600,
                    use_cache=True,
                )

                # Create corrupted cache file
                discovery.cache.cache_file.write_text("corrupted json")

                # Should fallback to dynamic discovery, then static
                with patch.object(
                    discovery,
                    "_fetch_models",
                    side_effect=Exception("API error"),
                ):
                    models = await discovery.discover_models()
                    assert models == static_models
