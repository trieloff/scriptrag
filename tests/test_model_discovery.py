"""Tests for dynamic model discovery with caching."""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scriptrag.llm.discovery_base import ModelDiscovery
from scriptrag.llm.model_cache import ModelDiscoveryCache
from scriptrag.llm.model_discovery import (
    ClaudeCodeModelDiscovery,
    GitHubModelsDiscovery,
)
from scriptrag.llm.models import LLMProvider, Model


class TestModelDiscoveryCache:
    """Test model discovery cache functionality."""

    @pytest.fixture
    def cache(self, tmp_path, monkeypatch):
        """Create a cache instance with temp directory."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)
        # Clear any existing in-memory cache to prevent test contamination
        ModelDiscoveryCache.clear_all_memory_cache()
        return ModelDiscoveryCache("test_provider", ttl=60)

    def test_cache_initialization(self, cache, tmp_path):
        """Test cache initialization creates proper structure."""
        assert cache.provider_name == "test_provider"
        assert cache.ttl == 60
        assert cache.cache_file == tmp_path / "test_provider_models.json"
        assert tmp_path.exists()

    def test_cache_miss_no_file(self, cache):
        """Test cache returns None when file doesn't exist."""
        result = cache.get()
        assert result is None

    def test_cache_set_and_get(self, cache):
        """Test setting and getting cached models."""
        models = [
            Model(
                id="model-1",
                name="Test Model 1",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["chat"],
            ),
            Model(
                id="model-2",
                name="Test Model 2",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["chat", "completion"],
            ),
        ]

        cache.set(models)
        assert cache.cache_file.exists()

        # Retrieve cached models
        cached_models = cache.get()
        assert cached_models is not None
        assert len(cached_models) == 2
        assert cached_models[0].id == "model-1"
        assert cached_models[1].id == "model-2"

    def test_cache_expiry(self, cache):
        """Test cache expiry based on TTL."""
        models = [
            Model(
                id="model-1",
                name="Test Model",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["chat"],
            )
        ]

        cache.set(models)

        # Manually modify timestamp to simulate expiry
        with cache.cache_file.open("r") as f:
            data = json.load(f)

        data["timestamp"] = time.time() - 120  # 2 minutes ago

        with cache.cache_file.open("w") as f:
            json.dump(data, f)

        # Clear in-memory cache so it reads from the modified file
        if cache.provider_name in cache._memory_cache:
            del cache._memory_cache[cache.provider_name]

        # Cache should be expired
        result = cache.get()
        assert result is None

    def test_cache_clear(self, cache):
        """Test clearing cache."""
        models = [
            Model(
                id="model-1",
                name="Test Model",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["chat"],
            )
        ]

        cache.set(models)
        assert cache.cache_file.exists()

        cache.clear()
        assert not cache.cache_file.exists()

    def test_cache_corrupted_file(self, cache):
        """Test handling of corrupted cache file."""
        # Write invalid JSON
        cache.cache_file.write_text("not valid json")

        result = cache.get()
        assert result is None

    def test_cache_set_write_error(self, cache, monkeypatch):
        """Test cache set when file write fails."""
        models = [
            Model(
                id="model-1",
                name="Test Model",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["chat"],
            )
        ]

        # Mock file open to raise an exception
        def mock_open_error(*args, **kwargs):
            raise PermissionError("Cannot write file")

        monkeypatch.setattr("builtins.open", mock_open_error)

        # Should not raise, just log warning
        cache.set(models)  # This should handle the exception gracefully

    def test_cache_set_non_permission_error(self, cache, monkeypatch):
        """Test cache set when file write fails with non-PermissionError."""
        models = [
            Model(
                id="model-1",
                name="Test Model",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["chat"],
            )
        ]

        # Mock json.dump to raise an exception (lines 94-95)
        import json

        def mock_json_dump(*args, **kwargs):
            raise ValueError("JSON serialization failed")

        monkeypatch.setattr(json, "dump", mock_json_dump)

        # Should not raise, just log warning (should hit exception handler)
        cache.set(models)

    def test_cache_clear_nonexistent_file(self, cache):
        """Test clearing cache when file doesn't exist (line 99)."""
        # Ensure cache file doesn't exist
        if cache.cache_file.exists():
            cache.cache_file.unlink()

        # Should not raise exception
        cache.clear()


class TestModelDiscovery:
    """Test base model discovery functionality."""

    @pytest.fixture
    def static_models(self):
        """Create static model list for testing."""
        return [
            Model(
                id="static-model-1",
                name="Static Model 1",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["chat"],
            ),
            Model(
                id="static-model-2",
                name="Static Model 2",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["completion"],
            ),
        ]

    @pytest.mark.asyncio
    async def test_force_static_models(self, static_models, tmp_path, monkeypatch):
        """Test forcing static models skips dynamic discovery."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)
        # Clear any existing in-memory cache to prevent test contamination
        ModelDiscoveryCache.clear_all_memory_cache()

        discovery = ModelDiscovery(
            provider_name="test",
            static_models=static_models,
            force_static=True,
        )

        models = await discovery.discover_models()
        assert len(models) == 2
        assert models[0].id == "static-model-1"

    @pytest.mark.asyncio
    async def test_cache_hit(self, static_models, tmp_path, monkeypatch):
        """Test returning cached models when available."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)
        # Clear any existing in-memory cache to prevent test contamination
        ModelDiscoveryCache.clear_all_memory_cache()

        discovery = ModelDiscovery(
            provider_name="test",
            static_models=static_models,
            use_cache=True,
        )

        # Pre-populate cache
        cached_models = [
            Model(
                id="cached-model",
                name="Cached Model",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["chat"],
            )
        ]
        discovery.cache.set(cached_models)

        models = await discovery.discover_models()
        assert len(models) == 1
        assert models[0].id == "cached-model"

    @pytest.mark.asyncio
    async def test_fallback_to_static(self, static_models, tmp_path, monkeypatch):
        """Test fallback to static models when dynamic discovery fails."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)
        # Clear any existing in-memory cache to prevent test contamination
        ModelDiscoveryCache.clear_all_memory_cache()

        class FailingDiscovery(ModelDiscovery):
            async def _fetch_models(self):
                raise Exception("API error")

        discovery = FailingDiscovery(
            provider_name="test",
            static_models=static_models,
            use_cache=True,
        )

        models = await discovery.discover_models()
        assert len(models) == 2
        assert models[0].id == "static-model-1"

    @pytest.mark.asyncio
    async def test_base_fetch_models_returns_none(
        self, static_models, tmp_path, monkeypatch
    ):
        """Test base ModelDiscovery._fetch_models returns None."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)
        # Clear any existing in-memory cache to prevent test contamination
        ModelDiscoveryCache.clear_all_memory_cache()

        discovery = ModelDiscovery(
            provider_name="test",
            static_models=static_models,
            use_cache=False,
        )

        # Base implementation should return None
        result = await discovery._fetch_models()
        assert result is None

        # And discover_models should fall back to static
        models = await discovery.discover_models()
        assert len(models) == 2
        assert models[0].id == "static-model-1"


class TestClaudeCodeModelDiscovery:
    """Test Claude Code model discovery."""

    @pytest.fixture
    def static_models(self):
        """Create Claude Code static models."""
        return [
            Model(
                id="claude-3-opus",
                name="Claude 3 Opus",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["chat"],
            )
        ]

    @pytest.mark.asyncio
    async def test_claude_code_no_sdk(self, static_models, tmp_path, monkeypatch):
        """Test Claude Code falls back to static when SDK unavailable."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        discovery = ClaudeCodeModelDiscovery(
            provider_name="claude_code",
            static_models=static_models,
            use_cache=False,
        )

        models = await discovery.discover_models()
        assert len(models) == 1
        assert models[0].id == "claude-3-opus"

    @pytest.mark.asyncio
    async def test_claude_code_with_mock_sdk(
        self, static_models, tmp_path, monkeypatch
    ):
        """Test Claude Code with mocked SDK (currently returns None)."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock the SDK import
        mock_sdk = MagicMock(spec=object)
        mock_sdk.ClaudeSDKClient = MagicMock
        mock_sdk.ClaudeCodeOptions = MagicMock
        with patch.dict("sys.modules", {"claude_code_sdk": mock_sdk}):
            discovery = ClaudeCodeModelDiscovery(
                provider_name="claude_code",
                static_models=static_models,
                use_cache=False,
            )

            models = await discovery.discover_models()
            # Should still use static models as SDK doesn't support enumeration
            assert len(models) == 1
            assert models[0].id == "claude-3-opus"

    @pytest.mark.asyncio
    async def test_claude_code_with_list_models_method(
        self, static_models, tmp_path, monkeypatch
    ):
        """Test Claude Code when SDK has list_models method."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock SDK with list_models method
        mock_sdk = MagicMock(spec=object)
        mock_client = MagicMock(spec=object)
        mock_client.list_models = AsyncMock(
            return_value=[
                {"id": "claude-3-5-sonnet", "name": "Claude 3.5 Sonnet"},
                {"id": "claude-3-opus", "name": "Claude 3 Opus"},
            ]
        )
        mock_sdk.ClaudeSDKClient.return_value = mock_client
        mock_sdk.ClaudeCodeOptions = MagicMock

        with patch.dict("sys.modules", {"claude_code_sdk": mock_sdk}):
            discovery = ClaudeCodeModelDiscovery(
                provider_name="claude_code",
                static_models=static_models,
                use_cache=False,
            )

            models = await discovery.discover_models()
            assert len(models) == 2
            assert models[0].id == "claude-3-5-sonnet"
            assert models[1].id == "claude-3-opus"

    @pytest.mark.asyncio
    async def test_claude_code_with_models_attribute(
        self, static_models, tmp_path, monkeypatch
    ):
        """Test Claude Code when SDK has models attribute."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock SDK with models attribute (but no list_models or get_models)
        mock_sdk = MagicMock(spec=object)
        mock_client = MagicMock(spec=["models"])  # Only has models attribute
        mock_client.models = {
            "claude-3-5-haiku": {"name": "Claude 3.5 Haiku", "context_window": 200000},
            "claude-4-opus": {"name": "Claude 4 Opus", "max_tokens": 10000},
        }
        mock_sdk.ClaudeSDKClient.return_value = mock_client
        mock_sdk.ClaudeCodeOptions = MagicMock

        with patch.dict("sys.modules", {"claude_code_sdk": mock_sdk}):
            discovery = ClaudeCodeModelDiscovery(
                provider_name="claude_code",
                static_models=static_models,
                use_cache=False,
            )

            models = await discovery.discover_models()
            assert len(models) == 2
            assert models[0].id == "claude-3-5-haiku"
            assert models[1].id == "claude-4-opus"
            assert models[1].max_output_tokens == 10000

    @pytest.mark.asyncio
    async def test_claude_code_sdk_exception(
        self, static_models, tmp_path, monkeypatch
    ):
        """Test Claude Code when SDK raises an exception."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock SDK that raises an exception
        mock_sdk = MagicMock(spec=object)
        mock_sdk.ClaudeSDKClient.side_effect = RuntimeError("SDK initialization failed")
        mock_sdk.ClaudeCodeOptions = MagicMock

        with patch.dict("sys.modules", {"claude_code_sdk": mock_sdk}):
            discovery = ClaudeCodeModelDiscovery(
                provider_name="claude_code",
                static_models=static_models,
                use_cache=False,
            )

            models = await discovery.discover_models()
            # Should fall back to static models
            assert len(models) == 1
            assert models[0].id == "claude-3-opus"

    @pytest.mark.asyncio
    async def test_claude_code_parse_models_empty(
        self, static_models, tmp_path, monkeypatch
    ):
        """Test Claude Code when SDK returns empty models."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock SDK with list_models returning empty list
        mock_sdk = MagicMock(spec=object)
        mock_client = MagicMock(spec=object)
        mock_client.list_models = AsyncMock(return_value=[])
        mock_sdk.ClaudeSDKClient.return_value = mock_client
        mock_sdk.ClaudeCodeOptions = MagicMock

        with patch.dict("sys.modules", {"claude_code_sdk": mock_sdk}):
            discovery = ClaudeCodeModelDiscovery(
                provider_name="claude_code",
                static_models=static_models,
                use_cache=False,
            )

            models = await discovery.discover_models()
            # Should fall back to static models when empty
            assert len(models) == 1
            assert models[0].id == "claude-3-opus"

    @pytest.mark.asyncio
    async def test_claude_code_parse_models_invalid_data(
        self, static_models, tmp_path, monkeypatch
    ):
        """Test Claude Code when SDK returns invalid model data."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock SDK with list_models returning invalid data
        mock_sdk = MagicMock(spec=object)
        mock_client = MagicMock(spec=object)
        # Return list with invalid items (no id)
        mock_client.list_models = AsyncMock(
            return_value=[
                {"name": "Model without ID"},
                {"id": None, "name": "Model with None ID"},
                "not a dict",
            ]
        )
        mock_sdk.ClaudeSDKClient.return_value = mock_client
        mock_sdk.ClaudeCodeOptions = MagicMock

        with patch.dict("sys.modules", {"claude_code_sdk": mock_sdk}):
            discovery = ClaudeCodeModelDiscovery(
                provider_name="claude_code",
                static_models=static_models,
                use_cache=False,
            )

            models = await discovery.discover_models()
            # Should fall back to static models when parsing fails
            assert len(models) == 1
            assert models[0].id == "claude-3-opus"

    @pytest.mark.asyncio
    async def test_claude_code_import_error(self, static_models, tmp_path, monkeypatch):
        """Test Claude Code when SDK import fails (line 221)."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock import to raise ImportError
        with patch.dict("sys.modules", {"claude_code_sdk": None}):
            discovery = ClaudeCodeModelDiscovery(
                provider_name="claude_code",
                static_models=static_models,
                use_cache=False,
            )

            models = await discovery.discover_models()
            # Should fall back to static models
            assert len(models) == 1
            assert models[0].id == "claude-3-opus"

    @pytest.mark.asyncio
    async def test_claude_code_with_anthropic_api_key(
        self, static_models, tmp_path, monkeypatch
    ):
        """Test Claude Code with ANTHROPIC_API_KEY set (line 230)."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key")

        # Mock httpx for successful API response
        mock_httpx = MagicMock(spec=object)
        mock_client = AsyncMock(spec=object)
        mock_response = MagicMock(spec=object)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "claude-3-5-sonnet-20241022",
                    "display_name": "Claude 3.5 Sonnet",
                }
            ]
        }
        mock_client.get.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client
        mock_httpx.AsyncClient.return_value.__aexit__.return_value = None

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            discovery = ClaudeCodeModelDiscovery(
                provider_name="claude_code",
                static_models=static_models,
                use_cache=False,
            )

            models = await discovery.discover_models()
            assert len(models) == 1
            assert models[0].id == "claude-3-5-sonnet-20241022"

    @pytest.mark.asyncio
    async def test_anthropic_api_success(self, static_models, tmp_path, monkeypatch):
        """Test successful Anthropic API call (lines 244-278)."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock httpx for successful API response
        mock_httpx = MagicMock(spec=object)
        mock_client = AsyncMock(spec=object)
        mock_response = MagicMock(spec=object)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "claude-3-opus-20240229", "display_name": "Claude 3 Opus"},
                {"id": "claude-3-haiku-20240307", "display_name": "Claude 3 Haiku"},
            ]
        }
        mock_client.get.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client
        mock_httpx.AsyncClient.return_value.__aexit__.return_value = None

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            discovery = ClaudeCodeModelDiscovery(
                provider_name="claude_code",
                static_models=static_models,
                use_cache=False,
            )

            result = await discovery._fetch_from_anthropic_api("test-api-key")
            assert result is not None
            assert len(result) == 2
            assert result[0].id == "claude-3-opus-20240229"
            assert result[1].id == "claude-3-haiku-20240307"
            # Test haiku gets smaller max_output (line 313-314)
            assert result[1].max_output_tokens == 4096

    @pytest.mark.asyncio
    async def test_anthropic_api_non_200_status(
        self, static_models, tmp_path, monkeypatch
    ):
        """Test Anthropic API with non-200 status code (lines 259-263)."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock httpx for non-200 response
        mock_httpx = MagicMock(spec=object)
        mock_client = AsyncMock(spec=object)
        mock_response = MagicMock(spec=object)
        mock_response.status_code = 401
        mock_client.get.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client
        mock_httpx.AsyncClient.return_value.__aexit__.return_value = None

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            discovery = ClaudeCodeModelDiscovery(
                provider_name="claude_code",
                static_models=static_models,
                use_cache=False,
            )

            result = await discovery._fetch_from_anthropic_api("test-api-key")
            assert result is None

    @pytest.mark.asyncio
    async def test_anthropic_api_empty_models(
        self, static_models, tmp_path, monkeypatch
    ):
        """Test Anthropic API with empty models list (lines 268-269)."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock httpx for empty models response
        mock_httpx = MagicMock(spec=object)
        mock_client = AsyncMock(spec=object)
        mock_response = MagicMock(spec=object)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_client.get.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client
        mock_httpx.AsyncClient.return_value.__aexit__.return_value = None

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            discovery = ClaudeCodeModelDiscovery(
                provider_name="claude_code",
                static_models=static_models,
                use_cache=False,
            )

            result = await discovery._fetch_from_anthropic_api("test-api-key")
            assert result is None

    @pytest.mark.asyncio
    async def test_anthropic_api_httpx_not_available(
        self, static_models, tmp_path, monkeypatch
    ):
        """Test Anthropic API when httpx not available (lines 273-275)."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock import to raise ImportError for httpx
        with patch.dict("sys.modules", {"httpx": None}):
            discovery = ClaudeCodeModelDiscovery(
                provider_name="claude_code",
                static_models=static_models,
                use_cache=False,
            )

            result = await discovery._fetch_from_anthropic_api("test-api-key")
            assert result is None

    @pytest.mark.asyncio
    async def test_anthropic_api_general_exception(
        self, static_models, tmp_path, monkeypatch
    ):
        """Test Anthropic API with general exception (lines 276-278)."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock httpx to raise general exception
        mock_httpx = MagicMock(spec=object)
        mock_httpx.AsyncClient.side_effect = Exception("Network error")

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            discovery = ClaudeCodeModelDiscovery(
                provider_name="claude_code",
                static_models=static_models,
                use_cache=False,
            )

            result = await discovery._fetch_from_anthropic_api("test-api-key")
            assert result is None

    def test_parse_anthropic_models_empty_list(self, static_models):
        """Test parsing empty Anthropic models list (lines 291-292)."""
        discovery = ClaudeCodeModelDiscovery(
            provider_name="claude_code",
            static_models=static_models,
            use_cache=False,
        )

        result = discovery._parse_anthropic_models([])
        assert result is None

    def test_parse_anthropic_models_missing_id(self, static_models):
        """Test parsing Anthropic models with missing IDs (lines 297-299)."""
        discovery = ClaudeCodeModelDiscovery(
            provider_name="claude_code",
            static_models=static_models,
            use_cache=False,
        )

        models_data = [
            {"display_name": "Model without ID"},
            {"id": "", "display_name": "Model with empty ID"},
            {"id": "claude-3-opus", "display_name": "Valid model"},
        ]

        result = discovery._parse_anthropic_models(models_data)
        assert result is not None
        assert len(result) == 1
        assert result[0].id == "claude-3-opus"

    def test_parse_anthropic_models_haiku_opus_types(self, static_models):
        """Test parsing Anthropic models with haiku/opus types (lines 313-314)."""
        discovery = ClaudeCodeModelDiscovery(
            provider_name="claude_code",
            static_models=static_models,
            use_cache=False,
        )

        models_data = [
            {"id": "claude-3-haiku-20240307", "display_name": "Claude 3 Haiku"},
            {"id": "claude-3-opus-20240229", "display_name": "Claude 3 Opus"},
            {"id": "claude-3-sonnet-20240229", "display_name": "Claude 3 Sonnet"},
        ]

        result = discovery._parse_anthropic_models(models_data)
        assert result is not None
        assert len(result) == 3

        # Haiku and Opus should have reduced max_output
        haiku_model = next(m for m in result if "haiku" in m.id.lower())
        opus_model = next(m for m in result if "opus" in m.id.lower())
        sonnet_model = next(m for m in result if "sonnet" in m.id.lower())

        assert haiku_model.max_output_tokens == 4096
        assert opus_model.max_output_tokens == 4096
        assert sonnet_model.max_output_tokens == 8192

    def test_parse_anthropic_models_exception(self, static_models):
        """Test parsing Anthropic models with exception (lines 329-331)."""
        discovery = ClaudeCodeModelDiscovery(
            provider_name="claude_code",
            static_models=static_models,
            use_cache=False,
        )

        # Pass invalid data that will cause an exception
        result = discovery._parse_anthropic_models("not a list")
        assert result is None

    def test_parse_claude_models_dict_format(self, static_models):
        """Test parsing Claude SDK models in dict format (lines 377-404)."""
        discovery = ClaudeCodeModelDiscovery(
            provider_name="claude_code",
            static_models=static_models,
            use_cache=False,
        )

        # Dict format with complex model info
        models_data = {
            "claude-3-5-sonnet": {
                "name": "Claude 3.5 Sonnet",
                "capabilities": ["chat", "completion"],
                "context_window": 200000,
                "max_tokens": 8192,
            },
            "claude-4-opus": {"name": "Claude 4 Opus", "max_tokens": 10000},
        }

        result = discovery._parse_claude_models(models_data)
        assert result is not None
        assert len(result) == 2

        sonnet_model = next(m for m in result if m.id == "claude-3-5-sonnet")
        opus_model = next(m for m in result if m.id == "claude-4-opus")

        assert sonnet_model.name == "Claude 3.5 Sonnet"
        assert sonnet_model.max_output_tokens == 8192
        assert opus_model.max_output_tokens == 10000

    def test_parse_claude_models_dict_simple_values(self, static_models):
        """Test parsing Claude SDK models dict format with simple values.

        Tests lines 388-391 of model_discovery.py.
        """
        discovery = ClaudeCodeModelDiscovery(
            provider_name="claude_code",
            static_models=static_models,
            use_cache=False,
        )

        # Dict format with simple values (not dict)
        models_data = {"claude-instant": "Claude Instant", "claude-2": "Claude 2"}

        result = discovery._parse_claude_models(models_data)
        assert result is not None
        assert len(result) == 2

        instant_model = next(m for m in result if m.id == "claude-instant")
        claude2_model = next(m for m in result if m.id == "claude-2")

        # Should use defaults for simple values
        assert instant_model.name == "claude-instant"
        assert instant_model.capabilities == ["completion", "chat"]
        assert instant_model.context_window == 200000
        assert instant_model.max_output_tokens == 8192

    def test_parse_claude_models_exception(self, static_models):
        """Test parsing Claude SDK models with exception (lines 406-408)."""
        discovery = ClaudeCodeModelDiscovery(
            provider_name="claude_code",
            static_models=static_models,
            use_cache=False,
        )

        # Mock the Model constructor to raise an exception
        with patch(
            "scriptrag.llm.model_discovery.Model",
            side_effect=Exception("Model creation failed"),
        ):
            result = discovery._parse_claude_models([{"id": "test-model"}])
            assert result is None


class TestGitHubModelsDiscovery:
    """Test GitHub Models discovery."""

    @pytest.fixture
    def static_models(self):
        """Create GitHub Models static models."""
        return [
            Model(
                id="gpt-4o",
                name="GPT-4o",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["chat"],
            )
        ]

    @pytest.fixture
    def mock_client(self):
        """Create mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_github_models_success(
        self, static_models, mock_client, tmp_path, monkeypatch
    ):
        """Test successful GitHub Models API discovery."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock successful API response
        mock_response = MagicMock(spec=object)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "gpt-4o",
                    "name": "GPT-4o",
                },
                {
                    "id": "gpt-4o-mini",
                    "name": "GPT-4o Mini",
                },
            ]
        }
        mock_client.get.return_value = mock_response

        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=None,  # Don't use static models for API test
            client=mock_client,
            token="test-token",  # noqa: S106
            base_url="https://api.test.com",
            use_cache=False,  # Disable cache to ensure API call
        )

        models = await discovery.discover_models()
        assert len(models) == 2
        assert models[0].id == "gpt-4o"
        assert models[1].id == "gpt-4o-mini"

        # Check API was called correctly
        mock_client.get.assert_called_once_with(
            "https://api.test.com/models",
            headers={
                "Authorization": "Bearer test-token",
                "Accept": "application/json",
            },
        )

    @pytest.mark.asyncio
    async def test_github_models_rate_limited(
        self, static_models, mock_client, tmp_path, monkeypatch
    ):
        """Test GitHub Models API rate limiting."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)
        # Clear any existing in-memory cache to prevent test contamination
        ModelDiscoveryCache.clear_all_memory_cache()

        # Mock rate limited response
        mock_response = MagicMock(spec=object)
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.text = "Rate limit exceeded. Please wait 60 seconds."
        mock_client.get.return_value = mock_response

        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            client=mock_client,
            token="test-token",  # noqa: S106
            base_url="https://api.test.com",
            use_cache=True,
        )

        models = await discovery.discover_models()
        # Should fall back to static models
        assert len(models) == 1
        assert models[0].id == "gpt-4o"

    @pytest.mark.asyncio
    async def test_github_models_no_token(
        self, static_models, mock_client, tmp_path, monkeypatch
    ):
        """Test GitHub Models with no token."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)
        # Clear any existing in-memory cache to prevent test contamination
        ModelDiscoveryCache.clear_all_memory_cache()

        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            client=mock_client,
            token=None,
            base_url="https://api.test.com",
            use_cache=False,
        )

        models = await discovery.discover_models()
        # Should use static models
        assert len(models) == 1
        assert models[0].id == "gpt-4o"

        # API should not be called
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_github_models_api_error(
        self, static_models, mock_client, tmp_path, monkeypatch
    ):
        """Test GitHub Models API error handling."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)
        # Clear any existing in-memory cache to prevent test contamination
        ModelDiscoveryCache.clear_all_memory_cache()

        # Mock API error
        mock_client.get.side_effect = httpx.RequestError("Connection failed")

        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            client=mock_client,
            token="test-token",  # noqa: S106
            base_url="https://api.test.com",
            use_cache=True,
        )

        models = await discovery.discover_models()
        # Should fall back to static models
        assert len(models) == 1
        assert models[0].id == "gpt-4o"

    @pytest.mark.asyncio
    async def test_github_models_unexpected_format(
        self, static_models, mock_client, tmp_path, monkeypatch
    ):
        """Test GitHub Models with unexpected API response format."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)
        # Clear any existing in-memory cache to prevent test contamination
        ModelDiscoveryCache.clear_all_memory_cache()

        # Mock unexpected response format
        mock_response = MagicMock(spec=object)
        mock_response.status_code = 200
        mock_response.json.return_value = {"unexpected": "format"}
        mock_client.get.return_value = mock_response

        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            client=mock_client,
            token="test-token",  # noqa: S106
            base_url="https://api.test.com",
            use_cache=False,
        )

        models = await discovery.discover_models()
        # Should fall back to static models
        assert len(models) == 1
        assert models[0].id == "gpt-4o"

    def test_process_github_models(self, static_models):
        """Test processing of raw GitHub model data."""
        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            client=MagicMock(spec=object),
            token="test",  # noqa: S106
            base_url="https://api.test.com",
        )

        raw_models = [
            {"id": "gpt-4o", "name": "GPT-4o", "context_window": 128000},
            {"id": "claude-3-opus", "name": "Claude 3 Opus"},
            {"id": "llama-2-70b", "friendly_name": "Llama 2 70B"},
            {"id": "text-embedding-ada", "name": "Ada Embeddings"},
            {"id": "unknown-model", "name": "Unknown"},
        ]

        processed = discovery._process_github_models(raw_models)

        # Should include supported models
        assert len(processed) == 4
        model_ids = [m.id for m in processed]
        assert "gpt-4o" in model_ids
        assert "claude-3-opus" in model_ids
        assert "llama-2-70b" in model_ids
        assert "text-embedding-ada" in model_ids
        assert "unknown-model" not in model_ids

        # Check capabilities
        gpt_model = next(m for m in processed if m.id == "gpt-4o")
        assert "chat" in gpt_model.capabilities
        assert "completion" in gpt_model.capabilities

        embedding_model = next(m for m in processed if m.id == "text-embedding-ada")
        assert "embedding" in embedding_model.capabilities

    @pytest.mark.asyncio
    async def test_github_models_list_response_format(
        self, static_models, mock_client, tmp_path, monkeypatch
    ):
        """Test GitHub Models API with list response format."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock response as a list (not dict with "data" key)
        mock_response = MagicMock(spec=object)
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "gpt-4", "name": "GPT-4"},
            {"id": "claude-3", "name": "Claude 3"},
        ]
        mock_client.get.return_value = mock_response

        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            client=mock_client,
            token="test-token",  # noqa: S106
            base_url="https://api.test.com",
            use_cache=False,
        )

        models = await discovery.discover_models()
        assert len(models) == 2
        assert models[0].id == "gpt-4"
        assert models[1].id == "claude-3"

    @pytest.mark.asyncio
    async def test_github_models_rate_limit_without_retry_header(
        self, static_models, mock_client, tmp_path, monkeypatch
    ):
        """Test GitHub Models API rate limiting without Retry-After header."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock rate limited response without Retry-After header
        mock_response = MagicMock(spec=object)
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_response.text = "Rate limit exceeded. Please wait 30 seconds."
        mock_client.get.return_value = mock_response

        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            client=mock_client,
            token="test-token",  # noqa: S106
            base_url="https://api.test.com",
            use_cache=False,
        )

        models = await discovery.discover_models()
        # Should fall back to static models
        assert len(models) == 1
        assert models[0].id == "gpt-4o"

    @pytest.mark.asyncio
    async def test_github_models_non_200_status(
        self, static_models, mock_client, tmp_path, monkeypatch
    ):
        """Test GitHub Models API with non-200 status code."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock response with 403 Forbidden
        mock_response = MagicMock(spec=object)
        mock_response.status_code = 403
        mock_response.text = "Forbidden: Invalid token"
        mock_client.get.return_value = mock_response

        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            client=mock_client,
            token="test-token",  # noqa: S106
            base_url="https://api.test.com",
            use_cache=False,
        )

        models = await discovery.discover_models()
        # Should fall back to static models
        assert len(models) == 1
        assert models[0].id == "gpt-4o"

    def test_process_github_models_with_empty_id(self, static_models):
        """Test processing GitHub models with empty or missing IDs."""
        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            client=MagicMock(spec=object),
            token="test",  # noqa: S106
            base_url="https://api.test.com",
        )

        raw_models = [
            {"id": "", "name": "Empty ID Model"},
            {"name": "No ID Model"},  # Missing id key
            {"id": "gpt-4", "name": "Valid Model"},
        ]

        processed = discovery._process_github_models(raw_models)

        # Should only include model with valid ID
        assert len(processed) == 1
        assert processed[0].id == "gpt-4"

    def test_process_github_models_with_cohere(self, static_models):
        """Test processing GitHub models with Cohere models."""
        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            client=MagicMock(spec=object),
            token="test",  # noqa: S106
            base_url="https://api.test.com",
        )

        raw_models = [
            {"id": "cohere-command", "name": "Cohere Command"},
            {"id": "phi-2", "name": "Phi 2"},
        ]

        processed = discovery._process_github_models(raw_models)

        # Should include both models
        assert len(processed) == 2
        model_ids = [m.id for m in processed]
        assert "cohere-command" in model_ids
        assert "phi-2" in model_ids

        # Check capabilities
        cohere_model = next(m for m in processed if m.id == "cohere-command")
        assert "chat" in cohere_model.capabilities

    @pytest.mark.asyncio
    async def test_github_models_rate_limit_no_match_in_text(
        self, static_models, mock_client, tmp_path, monkeypatch
    ):
        """Test GitHub Models rate limit without matching text pattern.

        Tests line 474->480 of model_discovery.py.
        """
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock rate limited response without Retry-After header
        # and no matching regex pattern
        mock_response = MagicMock(spec=object)
        mock_response.status_code = 429
        mock_response.headers = {}
        # No "wait X seconds" pattern in response text
        mock_response.text = "Rate limit exceeded. Try again later."
        mock_client.get.return_value = mock_response

        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            client=mock_client,
            token="test-token",  # noqa: S106
            base_url="https://api.test.com",
            use_cache=False,
        )

        models = await discovery.discover_models()
        # Should fall back to static models when no regex match
        assert len(models) == 1
        assert models[0].id == "gpt-4o"

    @pytest.mark.asyncio
    async def test_model_discovery_fallback_when_fewer_discovered(
        self, static_models, mock_client, tmp_path, monkeypatch
    ):
        """Test fallback logic when discovery returns fewer models than static list."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Create static models list with 3 models
        static_models_extended = [
            *static_models,
            Model(
                id="claude-3-opus",
                name="Claude 3 Opus",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["chat"],
            ),
            Model(
                id="llama-2-70b",
                name="Llama 2 70B",
                provider=LLMProvider.GITHUB_MODELS,
                capabilities=["chat"],
            ),
        ]

        # Mock API response with only 1 model (fewer than static)
        mock_response = MagicMock(spec=object)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "gpt-4o",
                    "name": "GPT-4o Updated",  # Different name than static
                },
            ]
        }
        mock_client.get.return_value = mock_response

        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models_extended,
            client=mock_client,
            token="test-token",  # noqa: S106
            base_url="https://api.test.com",
            use_cache=False,
        )

        models = await discovery.discover_models()

        # Should have all 3 static models in original order
        assert len(models) == 3
        model_ids = [m.id for m in models]
        assert model_ids == ["gpt-4o", "claude-3-opus", "llama-2-70b"]

        # The discovered gpt-4o should replace static one
        gpt_model = next(m for m in models if m.id == "gpt-4o")
        assert gpt_model.name == "GPT-4o Updated"  # Uses discovered version

    @pytest.mark.asyncio
    async def test_github_models_discovery_with_model_id_map(
        self, static_models, mock_client, tmp_path, monkeypatch
    ):
        """Test GitHub Models discovery with model ID mapping."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)

        # Mock API response with Azure registry IDs
        mock_response = MagicMock(spec=object)
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "azureml://registries/azure-openai/models/gpt-4o-mini/versions/1",
                "name": "GPT-4o Mini",
            },
            {
                "id": "azureml://registries/meta/models/llama-2-70b/versions/1",
                "name": "Llama 2 70B",
            },
        ]
        mock_client.get.return_value = mock_response

        # Model ID mapping
        model_id_map = {
            "azureml://registries/azure-openai/models/gpt-4o-mini/versions/1": (
                "gpt-4o-mini"
            ),
            "azureml://registries/meta/models/llama-2-70b/versions/1": "llama-2-70b",
        }

        discovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=static_models,
            client=mock_client,
            token="test-token",  # noqa: S106
            base_url="https://api.test.com",
            model_id_map=model_id_map,
            use_cache=False,
        )

        models = await discovery.discover_models()

        # Should map Azure registry IDs to simple IDs
        assert len(models) == 2
        model_ids = [m.id for m in models]
        assert "gpt-4o-mini" in model_ids
        assert "llama-2-70b" in model_ids

        # Ensure no Azure registry paths in final IDs
        for model_id in model_ids:
            assert not model_id.startswith("azureml://")
