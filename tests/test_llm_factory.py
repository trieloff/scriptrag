"""Tests for LLM factory module."""

from unittest.mock import Mock, patch

import pytest

from scriptrag.llm.factory import create_llm_client


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock()
    settings.llm_endpoint = "http://localhost:8080/v1"
    settings.llm_api_key = "test-api-key"  # pragma: allowlist secret
    return settings


class TestCreateLLMClient:
    """Test create_llm_client factory function."""

    def test_create_with_defaults(self, mock_settings):
        """Test creating client with default settings."""
        with (
            patch("scriptrag.llm.factory.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.factory.LLMClient") as mock_client_class,
        ):
            mock_client_instance = Mock()
            mock_client_class.return_value = mock_client_instance

            client = create_llm_client()

            assert client == mock_client_instance
            mock_client_class.assert_called_once_with(
                endpoint="http://localhost:8080/v1",
                api_key="test-api-key",  # pragma: allowlist secret
                default_chat_model=None,
                default_embedding_model=None,
            )

    def test_create_with_custom_endpoint(self, mock_settings):
        """Test creating client with custom endpoint."""
        with (
            patch("scriptrag.llm.factory.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.factory.LLMClient") as mock_client_class,
        ):
            mock_client_instance = Mock()
            mock_client_class.return_value = mock_client_instance

            client = create_llm_client(endpoint="http://custom:9090/v1")

            assert client == mock_client_instance
            mock_client_class.assert_called_once_with(
                endpoint="http://custom:9090/v1",
                api_key="test-api-key",  # pragma: allowlist secret
                default_chat_model=None,
                default_embedding_model=None,
            )

    def test_create_with_custom_api_key(self, mock_settings):
        """Test creating client with custom API key."""
        with (
            patch("scriptrag.llm.factory.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.factory.LLMClient") as mock_client_class,
        ):
            mock_client_instance = Mock()
            mock_client_class.return_value = mock_client_instance

            client = create_llm_client(api_key="custom-key")  # pragma: allowlist secret

            assert client == mock_client_instance
            mock_client_class.assert_called_once_with(
                endpoint="http://localhost:8080/v1",
                api_key="custom-key",  # pragma: allowlist secret
                default_chat_model=None,
                default_embedding_model=None,
            )

    def test_create_with_custom_models(self, mock_settings):
        """Test creating client with custom model configurations."""
        with (
            patch("scriptrag.llm.factory.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.factory.LLMClient") as mock_client_class,
        ):
            mock_client_instance = Mock()
            mock_client_class.return_value = mock_client_instance

            client = create_llm_client(
                default_chat_model="custom-chat-model",
                default_embedding_model="custom-embed-model",
            )

            assert client == mock_client_instance
            mock_client_class.assert_called_once_with(
                endpoint="http://localhost:8080/v1",
                api_key="test-api-key",  # pragma: allowlist secret
                default_chat_model="custom-chat-model",
                default_embedding_model="custom-embed-model",
            )

    def test_create_with_all_custom_parameters(self, mock_settings):
        """Test creating client with all custom parameters."""
        with (
            patch("scriptrag.llm.factory.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.factory.LLMClient") as mock_client_class,
        ):
            mock_client_instance = Mock()
            mock_client_class.return_value = mock_client_instance

            client = create_llm_client(
                endpoint="http://custom:9090/v1",
                api_key="custom-key",  # pragma: allowlist secret
                default_chat_model="custom-chat-model",
                default_embedding_model="custom-embed-model",
            )

            assert client == mock_client_instance
            mock_client_class.assert_called_once_with(
                endpoint="http://custom:9090/v1",
                api_key="custom-key",  # pragma: allowlist secret
                default_chat_model="custom-chat-model",
                default_embedding_model="custom-embed-model",
            )

    def test_create_with_none_values_uses_settings(self, mock_settings):
        """Test that None values fallback to settings."""
        with (
            patch("scriptrag.llm.factory.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.factory.LLMClient") as mock_client_class,
        ):
            mock_client_instance = Mock()
            mock_client_class.return_value = mock_client_instance

            client = create_llm_client(
                endpoint=None,
                api_key=None,
            )

            assert client == mock_client_instance
            mock_client_class.assert_called_once_with(
                endpoint="http://localhost:8080/v1",
                api_key="test-api-key",  # pragma: allowlist secret
                default_chat_model=None,
                default_embedding_model=None,
            )

    def test_create_respects_settings_priority(self, mock_settings):
        """Test that settings are used when no overrides provided."""
        # Modify settings to have different values
        mock_settings.llm_endpoint = "http://settings:8081/v1"
        mock_settings.llm_api_key = "settings-key"  # pragma: allowlist secret

        with (
            patch("scriptrag.llm.factory.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.factory.LLMClient") as mock_client_class,
        ):
            mock_client_instance = Mock()
            mock_client_class.return_value = mock_client_instance

            client = create_llm_client()

            assert client == mock_client_instance
            mock_client_class.assert_called_once_with(
                endpoint="http://settings:8081/v1",
                api_key="settings-key",  # pragma: allowlist secret
                default_chat_model=None,
                default_embedding_model=None,
            )
