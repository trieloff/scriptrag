"""Tests for LLM factory module."""

import os
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.utils.llm_client import LLMClient, LLMProvider
from scriptrag.utils.llm_factory import create_llm_client, get_default_llm_client


class TestCreateLLMClient:
    """Test create_llm_client function."""

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_defaults(self, mock_get_settings):
        """Test creating client with default settings."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()
        assert isinstance(client, LLMClient)
        assert client.preferred_provider is None

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_preferred_provider(self, mock_get_settings):
        """Test creating client with preferred provider."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        client = create_llm_client(preferred_provider="github_models")
        assert isinstance(client, LLMClient)
        assert client.preferred_provider == LLMProvider.GITHUB_MODELS

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_invalid_preferred_provider(self, mock_get_settings):
        """Test creating client with invalid preferred provider."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        # Invalid provider should be ignored
        client = create_llm_client(preferred_provider="invalid_provider")
        assert isinstance(client, LLMClient)
        assert client.preferred_provider is None

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_fallback_order(self, mock_get_settings):
        """Test creating client with fallback order."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        fallback_order = ["openai_compatible", "github_models", "claude_code"]
        client = create_llm_client(fallback_order=fallback_order)
        assert isinstance(client, LLMClient)
        assert client.fallback_order == [
            LLMProvider.OPENAI_COMPATIBLE,
            LLMProvider.GITHUB_MODELS,
            LLMProvider.CLAUDE_CODE,
        ]

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_invalid_fallback_order(self, mock_get_settings):
        """Test creating client with partially invalid fallback order."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        # Invalid providers should be skipped
        fallback_order = [
            "openai_compatible",
            "invalid",
            "github_models",
            "another_invalid",
        ]
        client = create_llm_client(fallback_order=fallback_order)
        assert isinstance(client, LLMClient)
        assert client.fallback_order == [
            LLMProvider.OPENAI_COMPATIBLE,
            LLMProvider.GITHUB_MODELS,
        ]

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_github_token(self, mock_get_settings):
        """Test creating client with GitHub token."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        token = "ghp_test_token"  # noqa: S105
        client = create_llm_client(github_token=token)
        assert isinstance(client, LLMClient)
        assert client.github_token == token

    @patch.dict(os.environ, {"GITHUB_TOKEN": "env_github_token"})
    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_github_token_from_env(self, mock_get_settings):
        """Test creating client with GitHub token from environment."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()
        assert isinstance(client, LLMClient)
        assert client.github_token == "env_github_token"  # noqa: S105

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_openai_endpoint(self, mock_get_settings):
        """Test creating client with OpenAI endpoint."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        endpoint = "https://api.example.com/v1"
        client = create_llm_client(openai_endpoint=endpoint)
        assert isinstance(client, LLMClient)
        assert client.openai_endpoint == endpoint

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_openai_endpoint_from_settings(self, mock_get_settings):
        """Test creating client with OpenAI endpoint from settings."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = "https://settings.example.com/v1"
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()
        assert isinstance(client, LLMClient)
        assert client.openai_endpoint == "https://settings.example.com/v1"

    @patch.dict(os.environ, {"SCRIPTRAG_LLM_ENDPOINT": "https://env.example.com/v1"})
    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_openai_endpoint_from_env(self, mock_get_settings):
        """Test creating client with OpenAI endpoint from environment."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()
        assert isinstance(client, LLMClient)
        assert client.openai_endpoint == "https://env.example.com/v1"

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_openai_api_key(self, mock_get_settings):
        """Test creating client with OpenAI API key."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        api_key = "sk-test-key"  # pragma: allowlist secret
        client = create_llm_client(openai_api_key=api_key)
        assert isinstance(client, LLMClient)
        assert client.openai_api_key == api_key

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_openai_api_key_from_settings(self, mock_get_settings):
        """Test creating client with OpenAI API key from settings."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = "sk-settings-key"  # pragma: allowlist secret
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()
        assert isinstance(client, LLMClient)
        assert client.openai_api_key == "sk-settings-key"  # pragma: allowlist secret

    @patch.dict(
        os.environ,
        {"SCRIPTRAG_LLM_API_KEY": "sk-env-key"},  # pragma: allowlist secret
    )
    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_openai_api_key_from_env(self, mock_get_settings):
        """Test creating client with OpenAI API key from environment."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()
        assert isinstance(client, LLMClient)
        assert client.openai_api_key == "sk-env-key"  # pragma: allowlist secret

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_timeout(self, mock_get_settings):
        """Test creating client with custom timeout."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        timeout = 60.0
        client = create_llm_client(timeout=timeout)
        assert isinstance(client, LLMClient)
        assert client.timeout == timeout

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_provider_from_settings(self, mock_get_settings):
        """Test creating client with provider from settings."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = "openai_compatible"
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()
        assert isinstance(client, LLMClient)
        assert client.preferred_provider == LLMProvider.OPENAI_COMPATIBLE

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_all_parameters(self, mock_get_settings):
        """Test creating client with all parameters specified."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = "github_models"  # Should be overridden
        mock_settings.llm_endpoint = (
            "https://settings.example.com"  # Should be overridden
        )
        # Should be overridden
        mock_settings.llm_api_key = "sk-settings"  # pragma: allowlist secret
        mock_get_settings.return_value = mock_settings

        client = create_llm_client(
            preferred_provider="openai_compatible",
            fallback_order=["github_models", "claude_code"],
            github_token="ghp_custom",  # noqa: S106
            openai_endpoint="https://custom.example.com",
            openai_api_key="sk-custom",  # pragma: allowlist secret
            timeout=45.0,
        )

        assert isinstance(client, LLMClient)
        assert client.preferred_provider == LLMProvider.OPENAI_COMPATIBLE
        assert client.fallback_order == [
            LLMProvider.GITHUB_MODELS,
            LLMProvider.CLAUDE_CODE,
        ]
        assert client.github_token == "ghp_custom"  # noqa: S105
        assert client.openai_endpoint == "https://custom.example.com"
        assert client.openai_api_key == "sk-custom"  # pragma: allowlist secret
        assert client.timeout == 45.0

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_precedence_order(self, mock_get_settings):
        """Test precedence order: params > settings > env vars."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = "https://settings.example.com"
        mock_settings.llm_api_key = "sk-settings"  # pragma: allowlist secret
        mock_get_settings.return_value = mock_settings

        with patch.dict(
            os.environ,
            {
                "GITHUB_TOKEN": "env_token",
                "SCRIPTRAG_LLM_ENDPOINT": "https://env.example.com",
                "SCRIPTRAG_LLM_API_KEY": "sk-env",  # pragma: allowlist secret
            },
        ):
            # Settings should override env vars
            client = create_llm_client()
            assert client.github_token == "env_token"  # Only from env  # noqa: S105
            assert (
                client.openai_endpoint == "https://settings.example.com"
            )  # Settings wins
            # Settings wins
            assert client.openai_api_key == "sk-settings"  # pragma: allowlist secret

            # Params should override both settings and env
            client = create_llm_client(
                github_token="param_token",  # noqa: S106
                openai_endpoint="https://param.example.com",
                openai_api_key="sk-param",  # pragma: allowlist secret
            )
            assert client.github_token == "param_token"  # noqa: S105
            assert client.openai_endpoint == "https://param.example.com"
            assert client.openai_api_key == "sk-param"  # pragma: allowlist secret


class TestGetDefaultLLMClient:
    """Test get_default_llm_client function."""

    @pytest.mark.asyncio
    @patch("scriptrag.utils.llm_factory.create_llm_client")
    async def test_get_default_client(self, mock_create):
        """Test getting default LLM client."""
        mock_client = MagicMock(spec=LLMClient)
        mock_create.return_value = mock_client

        client = await get_default_llm_client()
        assert client == mock_client
        mock_create.assert_called_once_with()

    @pytest.mark.asyncio
    @patch("scriptrag.utils.llm_factory.create_llm_client")
    async def test_get_default_client_creates_new_each_time(self, mock_create):
        """Test that get_default_llm_client creates new client each time."""
        mock_client1 = MagicMock(spec=LLMClient)
        mock_client2 = MagicMock(spec=LLMClient)
        mock_create.side_effect = [mock_client1, mock_client2]

        client1 = await get_default_llm_client()
        client2 = await get_default_llm_client()

        assert client1 == mock_client1
        assert client2 == mock_client2
        assert client1 is not client2
        assert mock_create.call_count == 2
