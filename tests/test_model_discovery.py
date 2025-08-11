"""Tests for dynamic model discovery with caching."""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scriptrag.llm.model_discovery import (
    ClaudeCodeModelDiscovery,
    GitHubModelsDiscovery,
    ModelDiscovery,
    ModelDiscoveryCache,
)
from scriptrag.llm.models import LLMProvider, Model


class TestModelDiscoveryCache:
    """Test model discovery cache functionality."""

    @pytest.fixture
    def cache(self, tmp_path, monkeypatch):
        """Create a cache instance with temp directory."""
        monkeypatch.setattr(ModelDiscoveryCache, "CACHE_DIR", tmp_path)
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
        mock_sdk = MagicMock()
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
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "gpt-4o-mini",
                    "name": "GPT-4o Mini",
                },
                {
                    "id": "gpt-3.5-turbo",
                    "name": "GPT-3.5 Turbo",
                },
            ]
        }
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
        assert len(models) == 2
        assert models[0].id == "gpt-4o-mini"
        assert models[1].id == "gpt-3.5-turbo"

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

        # Mock rate limited response
        mock_response = MagicMock()
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

        # Mock unexpected response format
        mock_response = MagicMock()
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
            client=MagicMock(),
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
