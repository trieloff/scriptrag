"""Tests for LLM factory utilities."""

import os
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.llm import LLMClient, LLMProvider
from scriptrag.utils.llm_factory import create_llm_client, get_default_llm_client


class TestCreateLLMClient:
    """Tests for create_llm_client function."""

    def test_default_client_creation(self):
        """Test creating a client with default settings."""
        client = create_llm_client()
        assert isinstance(client, LLMClient)

    def test_preferred_provider_string(self):
        """Test setting preferred provider as string."""
        client = create_llm_client(preferred_provider="github_models")
        assert client.preferred_provider == LLMProvider.GITHUB_MODELS

    def test_preferred_provider_invalid(self):
        """Test invalid preferred provider falls back to defaults."""
        # Invalid provider should not raise error
        client = create_llm_client(preferred_provider="invalid_provider")
        assert isinstance(client, LLMClient)

    def test_fallback_order_conversion(self):
        """Test conversion of fallback order strings to enums."""
        fallback_order = ["github_models", "claude_code", "openai_compatible"]
        client = create_llm_client(fallback_order=fallback_order)
        expected = [
            LLMProvider.GITHUB_MODELS,
            LLMProvider.CLAUDE_CODE,
            LLMProvider.OPENAI_COMPATIBLE,
        ]
        assert client.fallback_order == expected

    def test_fallback_order_with_invalid(self):
        """Test fallback order with invalid provider names (should skip)."""
        fallback_order = ["github_models", "invalid", "claude_code"]
        client = create_llm_client(fallback_order=fallback_order)
        expected = [LLMProvider.GITHUB_MODELS, LLMProvider.CLAUDE_CODE]
        assert client.fallback_order == expected

    def test_github_token_parameter(self):
        """Test passing GitHub token directly."""
        token = "test-github-token-123"  # noqa: S105 # pragma: allowlist secret
        client = create_llm_client(github_token=token)
        assert client.github_token == token

    @patch.dict(os.environ, {"GITHUB_TOKEN": "env-github-token"})
    def test_github_token_from_env(self):
        """Test GitHub token fallback to environment variable."""
        client = create_llm_client()
        assert client.github_token == "env-github-token"  # noqa: S105 # pragma: allowlist secret

    def test_github_token_parameter_overrides_env(self):
        """Test that parameter overrides environment variable."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "env-token"}):
            client = create_llm_client(
                github_token="param-token"  # noqa: S106 # pragma: allowlist secret
            )
            assert client.github_token == "param-token"  # noqa: S105 # pragma: allowlist secret

    def test_openai_endpoint_parameter(self):
        """Test passing OpenAI endpoint directly."""
        endpoint = "https://custom.openai.com/v1"
        client = create_llm_client(openai_endpoint=endpoint)
        assert client.openai_endpoint == endpoint

    def test_openai_endpoint_from_env(self):
        """Test OpenAI endpoint fallback to environment variable."""
        with patch.dict(
            os.environ, {"SCRIPTRAG_LLM_ENDPOINT": "https://env.openai.com/v1"}
        ):
            client = create_llm_client()
            assert client.openai_endpoint == "https://env.openai.com/v1"

    def test_openai_api_key_parameter(self):
        """Test passing OpenAI API key directly."""
        api_key = "test-api-key-123"  # pragma: allowlist secret
        client = create_llm_client(openai_api_key=api_key)
        assert client.openai_api_key == api_key

    def test_openai_api_key_from_env(self):
        """Test OpenAI API key fallback to environment variable."""
        env = {"SCRIPTRAG_LLM_API_KEY": "env-api-key"}  # pragma: allowlist secret
        with patch.dict(os.environ, env):
            client = create_llm_client()
            assert client.openai_api_key == "env-api-key"  # pragma: allowlist secret

    def test_timeout_parameter(self):
        """Test setting custom timeout."""
        client = create_llm_client(timeout=60.0)
        assert client.timeout == 60.0

    def test_timeout_default(self):
        """Test default timeout value."""
        client = create_llm_client()
        assert client.timeout == 30.0

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_settings_integration(self, mock_get_settings):
        """Test integration with settings."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = "claude_code"
        mock_settings.llm_endpoint = "https://settings.openai.com/v1"
        mock_settings.llm_api_key = "settings-key"  # pragma: allowlist secret
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()
        assert client.preferred_provider == LLMProvider.CLAUDE_CODE
        assert client.openai_endpoint == "https://settings.openai.com/v1"
        assert client.openai_api_key == "settings-key"  # pragma: allowlist secret

    @patch("scriptrag.utils.llm_factory.get_settings")
    def test_parameter_overrides_settings(self, mock_get_settings):
        """Test that parameters override settings."""
        mock_settings = MagicMock()
        mock_settings.llm_provider = "claude_code"
        mock_settings.llm_endpoint = "https://settings.openai.com/v1"
        mock_settings.llm_api_key = "settings-key"  # pragma: allowlist secret
        mock_get_settings.return_value = mock_settings

        client = create_llm_client(
            preferred_provider="github_models",
            openai_endpoint="https://param.openai.com/v1",
            openai_api_key="param-key",  # pragma: allowlist secret
        )
        assert client.preferred_provider == LLMProvider.GITHUB_MODELS
        assert client.openai_endpoint == "https://param.openai.com/v1"
        assert client.openai_api_key == "param-key"  # pragma: allowlist secret

    def test_empty_fallback_order(self):
        """Test with empty fallback order list."""
        client = create_llm_client(fallback_order=[])
        assert client.fallback_order is None

    def test_all_invalid_fallback_order(self):
        """Test with all invalid provider names in fallback order."""
        client = create_llm_client(fallback_order=["invalid1", "invalid2"])
        assert client.fallback_order is None

    @patch("scriptrag.utils.llm_factory.logger")
    def test_logging_with_credentials(self, mock_logger):
        """Test that logging occurs with appropriate credential masking."""
        create_llm_client(
            preferred_provider="github_models",
            github_token="secret-token",  # noqa: S106 # pragma: allowlist secret
            openai_api_key="secret-key",  # pragma: allowlist secret
            openai_endpoint="https://api.openai.com/v1",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "Creating LLM client"
        kwargs = call_args[1]
        assert kwargs["preferred_provider"] == "github_models"
        assert kwargs["has_github_token"] is True
        assert kwargs["has_openai_api_key"] is True
        assert kwargs["openai_endpoint"] == "https://api.openai.com/v1"
        # Ensure secrets are not logged directly
        assert "secret-token" not in str(call_args)
        assert "secret-key" not in str(call_args)

    @patch("scriptrag.utils.llm_factory.logger")
    def test_logging_without_credentials(self, mock_logger):
        """Test logging when no credentials are provided."""
        create_llm_client()

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        kwargs = call_args[1]
        assert kwargs["preferred_provider"] == "auto"
        assert kwargs["fallback_order"] == "default"
        assert kwargs["has_github_token"] is False
        assert kwargs["has_openai_api_key"] is False
        assert kwargs["openai_endpoint"] == "not configured"


class TestGetDefaultLLMClient:
    """Tests for get_default_llm_client function."""

    @pytest.mark.asyncio
    async def test_returns_llm_client(self):
        """Test that get_default_llm_client returns an LLMClient instance."""
        client = await get_default_llm_client()
        assert isinstance(client, LLMClient)

    @pytest.mark.asyncio
    @patch("scriptrag.utils.llm_factory.create_llm_client")
    async def test_calls_create_llm_client(self, mock_create):
        """Test that get_default_llm_client calls create_llm_client."""
        mock_client = MagicMock(spec=LLMClient)
        mock_create.return_value = mock_client

        result = await get_default_llm_client()
        assert result == mock_client
        mock_create.assert_called_once_with()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"})
    async def test_uses_environment_variables(self):
        """Test that default client uses environment variables."""
        client = await get_default_llm_client()
        assert client.github_token == "test-token"  # noqa: S105 # pragma: allowlist secret


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_none_parameters(self):
        """Test with all None parameters."""
        client = create_llm_client(
            preferred_provider=None,
            fallback_order=None,
            github_token=None,
            openai_endpoint=None,
            openai_api_key=None,
        )
        assert isinstance(client, LLMClient)

    def test_mixed_valid_invalid_providers(self):
        """Test with mix of valid and invalid provider names."""
        client = create_llm_client(
            preferred_provider="invalid",
            fallback_order=["invalid1", "github_models", "invalid2", "claude_code"],
        )
        assert isinstance(client, LLMClient)
        assert client.fallback_order == [
            LLMProvider.GITHUB_MODELS,
            LLMProvider.CLAUDE_CODE,
        ]

    @patch.dict(os.environ, {}, clear=True)
    def test_no_environment_variables(self):
        """Test when no relevant environment variables are set."""
        client = create_llm_client()
        assert client.github_token is None
        assert client.openai_endpoint is None
        assert client.openai_api_key is None

    def test_case_sensitive_provider_names(self):
        """Test that provider names are case-sensitive."""
        # These should be invalid due to case
        client = create_llm_client(
            preferred_provider="GitHub_Models",
            fallback_order=["Claude_Code", "OpenAI_Compatible"],
        )
        # Should fall back to defaults due to invalid names
        assert isinstance(client, LLMClient)
        assert client.fallback_order is None
