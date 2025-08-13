"""Tests for LLM factory module."""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_llm_client():
    """Mock LLMClient to avoid creating real HTTP clients."""
    with patch("scriptrag.utils.llm_factory.LLMClient") as mock_client_class:
        # Create a mock that behaves like LLMClient
        mock_instance = Mock()
        mock_instance.preferred_provider = None
        mock_instance.fallback_order = None
        mock_instance.github_token = None
        mock_instance.openai_endpoint = None
        mock_instance.openai_api_key = None
        mock_instance.timeout = 30.0
        mock_client_class.return_value = mock_instance
        yield mock_client_class


@pytest.fixture(autouse=True)
def clean_env():
    """Clean environment variables for tests."""
    # Store original env vars that might affect tests
    env_vars_to_clear = [
        "GITHUB_TOKEN",
        "SCRIPTRAG_LLM_ENDPOINT",
        "SCRIPTRAG_LLM_API_KEY",
        "OPENAI_API_KEY",
    ]
    original = {}
    for var in env_vars_to_clear:
        if var in os.environ:
            original[var] = os.environ.pop(var)

    yield

    # Restore original values
    for var, value in original.items():
        os.environ[var] = value


# Import after patching to avoid instantiation issues
from scriptrag.llm import LLMProvider  # noqa: E402
from scriptrag.utils.llm_factory import (  # noqa: E402
    create_llm_client,
    get_default_llm_client,
)


class TestCreateLLMClient:
    """Test create_llm_client function."""

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_defaults(self, mock_get_settings, mock_llm_client):
        """Test creating client with default settings."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()

        # Verify LLMClient was called with correct arguments
        mock_llm_client.assert_called_once_with(
            preferred_provider=None,
            fallback_order=None,
            github_token=None,
            openai_endpoint=None,
            openai_api_key=None,
            timeout=30.0,
        )

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_preferred_provider(self, mock_get_settings, mock_llm_client):
        """Test creating client with preferred provider."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        client = create_llm_client(preferred_provider="github_models")

        # Verify LLMClient was called with correct arguments
        mock_llm_client.assert_called_once_with(
            preferred_provider=LLMProvider.GITHUB_MODELS,
            fallback_order=None,
            github_token=None,
            openai_endpoint=None,
            openai_api_key=None,
            timeout=30.0,
        )

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_invalid_preferred_provider(
        self, mock_get_settings, mock_llm_client
    ):
        """Test creating client with invalid preferred provider."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        # Invalid provider should be ignored
        client = create_llm_client(preferred_provider="invalid_provider")

        # Should be called with None since invalid provider
        mock_llm_client.assert_called_once_with(
            preferred_provider=None,
            fallback_order=None,
            github_token=None,
            openai_endpoint=None,
            openai_api_key=None,
            timeout=30.0,
        )

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_fallback_order(self, mock_get_settings, mock_llm_client):
        """Test creating client with fallback order."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        fallback_order = ["openai_compatible", "github_models", "claude_code"]
        client = create_llm_client(fallback_order=fallback_order)

        mock_llm_client.assert_called_once_with(
            preferred_provider=None,
            fallback_order=[
                LLMProvider.OPENAI_COMPATIBLE,
                LLMProvider.GITHUB_MODELS,
                LLMProvider.CLAUDE_CODE,
            ],
            github_token=None,
            openai_endpoint=None,
            openai_api_key=None,
            timeout=30.0,
        )

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_invalid_fallback_order(
        self, mock_get_settings, mock_llm_client
    ):
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

        mock_llm_client.assert_called_once_with(
            preferred_provider=None,
            fallback_order=[
                LLMProvider.OPENAI_COMPATIBLE,
                LLMProvider.GITHUB_MODELS,
            ],
            github_token=None,
            openai_endpoint=None,
            openai_api_key=None,
            timeout=30.0,
        )

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_github_token(self, mock_get_settings, mock_llm_client):
        """Test creating client with GitHub token."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        token = "ghp_test_token"  # noqa: S105
        client = create_llm_client(github_token=token)

        mock_llm_client.assert_called_once_with(
            preferred_provider=None,
            fallback_order=None,
            github_token=token,
            openai_endpoint=None,
            openai_api_key=None,
            timeout=30.0,
        )

    @patch.dict(os.environ, {"GITHUB_TOKEN": "env_github_token"})
    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_github_token_from_env(
        self, mock_get_settings, mock_llm_client
    ):
        """Test creating client with GitHub token from environment."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()

        mock_llm_client.assert_called_once_with(
            preferred_provider=None,
            fallback_order=None,
            github_token="env_github_token",  # pragma: allowlist secret
            openai_endpoint=None,
            openai_api_key=None,
            timeout=30.0,
        )

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_openai_endpoint(self, mock_get_settings, mock_llm_client):
        """Test creating client with OpenAI endpoint."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        endpoint = "https://api.example.com/v1"
        client = create_llm_client(openai_endpoint=endpoint)

        mock_llm_client.assert_called_once_with(
            preferred_provider=None,
            fallback_order=None,
            github_token=None,
            openai_endpoint=endpoint,
            openai_api_key=None,
            timeout=30.0,
        )

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_openai_endpoint_from_settings(
        self, mock_get_settings, mock_llm_client
    ):
        """Test creating client with OpenAI endpoint from settings."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = "https://settings.example.com/v1"
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()

        mock_llm_client.assert_called_once_with(
            preferred_provider=None,
            fallback_order=None,
            github_token=None,
            openai_endpoint="https://settings.example.com/v1",
            openai_api_key=None,
            timeout=30.0,
        )

    @patch.dict(os.environ, {"SCRIPTRAG_LLM_ENDPOINT": "https://env.example.com/v1"})
    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_openai_endpoint_from_env(
        self, mock_get_settings, mock_llm_client
    ):
        """Test creating client with OpenAI endpoint from environment."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()

        mock_llm_client.assert_called_once_with(
            preferred_provider=None,
            fallback_order=None,
            github_token=None,
            openai_endpoint="https://env.example.com/v1",
            openai_api_key=None,
            timeout=30.0,
        )

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_openai_api_key(self, mock_get_settings, mock_llm_client):
        """Test creating client with OpenAI API key."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        api_key = "sk-test-key"  # pragma: allowlist secret
        client = create_llm_client(openai_api_key=api_key)

        mock_llm_client.assert_called_once_with(
            preferred_provider=None,
            fallback_order=None,
            github_token=None,
            openai_endpoint=None,
            openai_api_key=api_key,
            timeout=30.0,
        )

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_openai_api_key_from_settings(
        self, mock_get_settings, mock_llm_client
    ):
        """Test creating client with OpenAI API key from settings."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = "sk-settings-key"  # pragma: allowlist secret
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()

        mock_llm_client.assert_called_once_with(
            preferred_provider=None,
            fallback_order=None,
            github_token=None,
            openai_endpoint=None,
            openai_api_key="sk-settings-key",  # pragma: allowlist secret
            timeout=30.0,
        )

    @patch.dict(
        os.environ,
        {"SCRIPTRAG_LLM_API_KEY": "sk-env-key"},  # pragma: allowlist secret
    )
    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_openai_api_key_from_env(
        self, mock_get_settings, mock_llm_client
    ):
        """Test creating client with OpenAI API key from environment."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()

        mock_llm_client.assert_called_once_with(
            preferred_provider=None,
            fallback_order=None,
            github_token=None,
            openai_endpoint=None,
            openai_api_key="sk-env-key",  # pragma: allowlist secret
            timeout=30.0,
        )

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_timeout(self, mock_get_settings, mock_llm_client):
        """Test creating client with custom timeout."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = None
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        timeout = 60.0
        client = create_llm_client(timeout=timeout)

        mock_llm_client.assert_called_once_with(
            preferred_provider=None,
            fallback_order=None,
            github_token=None,
            openai_endpoint=None,
            openai_api_key=None,
            timeout=timeout,
        )

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_provider_from_settings(
        self, mock_get_settings, mock_llm_client
    ):
        """Test creating client with provider from settings."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = "openai_compatible"
        mock_settings.llm_endpoint = None
        mock_settings.llm_api_key = None
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()

        mock_llm_client.assert_called_once_with(
            preferred_provider=LLMProvider.OPENAI_COMPATIBLE,
            fallback_order=None,
            github_token=None,
            openai_endpoint=None,
            openai_api_key=None,
            timeout=30.0,
        )

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_create_with_all_parameters(self, mock_get_settings, mock_llm_client):
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
            github_token="ghp_custom",  # pragma: allowlist secret  # noqa: S106
            openai_endpoint="https://custom.example.com",
            openai_api_key="sk-custom",  # pragma: allowlist secret
            timeout=45.0,
        )

        mock_llm_client.assert_called_once_with(
            preferred_provider=LLMProvider.OPENAI_COMPATIBLE,
            fallback_order=[
                LLMProvider.GITHUB_MODELS,
                LLMProvider.CLAUDE_CODE,
            ],
            github_token="ghp_custom",  # pragma: allowlist secret
            openai_endpoint="https://custom.example.com",
            openai_api_key="sk-custom",  # pragma: allowlist secret
            timeout=45.0,
        )

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_precedence_order(self, mock_get_settings, mock_llm_client):
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

            mock_llm_client.assert_called_with(
                preferred_provider=None,
                fallback_order=None,
                github_token="env_token",  # pragma: allowlist secret
                openai_endpoint="https://settings.example.com",  # Settings wins
                openai_api_key="sk-settings",  # pragma: allowlist secret
                timeout=30.0,
            )

            mock_llm_client.reset_mock()

            # Params should override both settings and env
            client = create_llm_client(
                github_token="param_token",  # pragma: allowlist secret  # noqa: S106
                openai_endpoint="https://param.example.com",
                openai_api_key="sk-param",  # pragma: allowlist secret
            )

            mock_llm_client.assert_called_with(
                preferred_provider=None,
                fallback_order=None,
                github_token="param_token",  # pragma: allowlist secret
                openai_endpoint="https://param.example.com",
                openai_api_key="sk-param",  # pragma: allowlist secret
                timeout=30.0,
            )


class TestGetDefaultLLMClient:
    """Test get_default_llm_client function."""

    @pytest.mark.asyncio
    @patch("scriptrag.utils.llm_factory.create_llm_client")
    async def test_get_default_client(self, mock_create):
        """Test getting default LLM client."""
        mock_client = Mock()
        mock_create.return_value = mock_client

        client = await get_default_llm_client()
        assert client == mock_client
        mock_create.assert_called_once_with()

    @pytest.mark.asyncio
    @patch("scriptrag.utils.llm_factory.create_llm_client")
    async def test_get_default_client_creates_new_each_time(self, mock_create):
        """Test that get_default_llm_client creates new client each time."""
        mock_client1 = Mock()
        mock_client2 = Mock()
        mock_create.side_effect = [mock_client1, mock_client2]

        client1 = await get_default_llm_client()
        client2 = await get_default_llm_client()

        assert client1 == mock_client1
        assert client2 == mock_client2
        assert client1 is not client2
        assert mock_create.call_count == 2
