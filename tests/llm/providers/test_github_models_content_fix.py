"""Tests for GitHub Models provider handling of malformed content fields."""

from unittest.mock import MagicMock, patch

import pytest

from scriptrag.llm.models import CompletionRequest, LLMProvider
from scriptrag.llm.providers.github_models import GitHubModelsProvider


class TestGitHubModelsContentHandling:
    """Test GitHub Models provider's handling of malformed content fields."""

    @pytest.fixture
    def provider(self) -> GitHubModelsProvider:
        """Create provider instance with token."""
        return GitHubModelsProvider(token="test-token")  # noqa: S106

    @pytest.mark.asyncio
    async def test_content_as_integer(self, provider: GitHubModelsProvider) -> None:
        """Test handling when content field is an integer."""
        mock_response = MagicMock(spec=["status_code", "json", "text"])
        mock_response.status_code = 200
        mock_response.text = '{"choices": [{"message": {"content": 42}}]}'
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": 42,  # Integer instead of string
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        provider._init_http_client()
        with patch.object(provider.client, "post", return_value=mock_response):
            request = CompletionRequest(
                model="gpt-4o", messages=[{"role": "user", "content": "Test"}]
            )
            response = await provider.complete(request)

            # Should convert integer to string
            assert response.choices[0]["message"]["content"] == "42"
            assert response.provider == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_content_as_dict(self, provider: GitHubModelsProvider) -> None:
        """Test handling when content field is a dictionary."""
        mock_response = MagicMock(spec=["status_code", "json", "text"])
        mock_response.status_code = 200
        text = '{"choices": [{"message": {"content": {"text": "hello"}}}]}'
        mock_response.text = text
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        # Dict instead of string
                        "content": {"text": "hello", "metadata": "data"},
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        provider._init_http_client()
        with patch.object(provider.client, "post", return_value=mock_response):
            request = CompletionRequest(
                model="gpt-4o", messages=[{"role": "user", "content": "Test"}]
            )
            response = await provider.complete(request)

            # Should convert dict to string representation
            content = response.choices[0]["message"]["content"]
            assert isinstance(content, str)
            assert "text" in content
            assert "hello" in content
            assert response.provider == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_content_as_list(self, provider: GitHubModelsProvider) -> None:
        """Test handling when content field is a list."""
        mock_response = MagicMock(spec=["status_code", "json", "text"])
        mock_response.status_code = 200
        text = '{"choices": [{"message": {"content": ["hello", "world"]}}]}'
        mock_response.text = text
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": ["hello", "world"],  # List instead of string
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        provider._init_http_client()
        with patch.object(provider.client, "post", return_value=mock_response):
            request = CompletionRequest(
                model="gpt-4o", messages=[{"role": "user", "content": "Test"}]
            )
            response = await provider.complete(request)

            # Should convert list to string representation
            content = response.choices[0]["message"]["content"]
            assert isinstance(content, str)
            assert "hello" in content
            assert "world" in content
            assert response.provider == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_content_as_boolean(self, provider: GitHubModelsProvider) -> None:
        """Test handling when content field is a boolean."""
        mock_response = MagicMock(spec=["status_code", "json", "text"])
        mock_response.status_code = 200
        mock_response.text = '{"choices": [{"message": {"content": true}}]}'
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": True,  # Boolean instead of string
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        provider._init_http_client()
        with patch.object(provider.client, "post", return_value=mock_response):
            request = CompletionRequest(
                model="gpt-4o", messages=[{"role": "user", "content": "Test"}]
            )
            response = await provider.complete(request)

            # Should convert boolean to string
            assert response.choices[0]["message"]["content"] == "True"
            assert response.provider == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_content_as_float(self, provider: GitHubModelsProvider) -> None:
        """Test handling when content field is a float."""
        mock_response = MagicMock(spec=["status_code", "json", "text"])
        mock_response.status_code = 200
        mock_response.text = '{"choices": [{"message": {"content": 3.14}}]}'
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": 3.14,  # Float instead of string
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        provider._init_http_client()
        with patch.object(provider.client, "post", return_value=mock_response):
            request = CompletionRequest(
                model="gpt-4o", messages=[{"role": "user", "content": "Test"}]
            )
            response = await provider.complete(request)

            # Should convert float to string
            assert response.choices[0]["message"]["content"] == "3.14"
            assert response.provider == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_content_as_nested_dict(self, provider: GitHubModelsProvider) -> None:
        """Test handling when content field is a complex nested structure."""
        mock_response = MagicMock(spec=["status_code", "json", "text"])
        mock_response.status_code = 200
        complex_content = {
            "response": {
                "text": "Hello",
                "metadata": {"confidence": 0.95, "tokens": ["hello", "world"]},
            }
        }
        text = f'{{"choices": [{{"message": {{"content": {complex_content}}}}}]}}'
        mock_response.text = text
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": complex_content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        provider._init_http_client()
        with patch.object(provider.client, "post", return_value=mock_response):
            request = CompletionRequest(
                model="gpt-4o", messages=[{"role": "user", "content": "Test"}]
            )
            response = await provider.complete(request)

            # Should convert complex dict to string representation
            content = response.choices[0]["message"]["content"]
            assert isinstance(content, str)
            assert "response" in content
            assert "metadata" in content
            assert response.provider == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_logging_handles_malformed_content(
        self, provider: GitHubModelsProvider
    ) -> None:
        """Test that logging doesn't fail with malformed content."""
        mock_response = MagicMock(spec=["status_code", "json", "text"])
        mock_response.status_code = 200

        # Create a very long content that should be truncated in logging
        long_dict = {f"key_{i}": f"value_{i}" for i in range(50)}

        text = f'{{"choices": [{{"message": {{"content": {long_dict}}}}}]}}'
        mock_response.text = text
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": long_dict},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        provider._init_http_client()

        # Capture log output to verify no errors
        with patch.object(provider.client, "post", return_value=mock_response):
            request = CompletionRequest(
                model="gpt-4o", messages=[{"role": "user", "content": "Test"}]
            )
            response = await provider.complete(request)

            # Should handle long content gracefully
            content = response.choices[0]["message"]["content"]
            assert isinstance(content, str)
            # The actual content should be the full stringified dict
            assert "key_0" in content
            assert response.provider == LLMProvider.GITHUB_MODELS

    @pytest.mark.asyncio
    async def test_fallback_parsing_with_malformed_content(
        self, provider: GitHubModelsProvider
    ) -> None:
        """Test the fallback parsing logic with malformed content."""
        mock_response = MagicMock(spec=["status_code", "json", "text"])
        mock_response.status_code = 200
        mock_response.text = '{"choices": [{"message": {"content": [1, 2, 3]}}]}'

        # Create a response that triggers the fallback parsing
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": [1, 2, 3],  # List of numbers
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        provider._init_http_client()
        with patch.object(provider.client, "post", return_value=mock_response):
            request = CompletionRequest(
                model="gpt-4o", messages=[{"role": "user", "content": "Test"}]
            )
            response = await provider.complete(request)

            # Verify the response is properly handled
            content = response.choices[0]["message"]["content"]
            assert isinstance(content, str)
            assert content == "[1, 2, 3]"
            assert response.provider == LLMProvider.GITHUB_MODELS
