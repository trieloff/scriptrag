#!/usr/bin/env python3
"""
Unit tests for LLM client with mocked API calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai.types import Model
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.create_embedding_response import CreateEmbeddingResponse, Embedding

from scriptrag.llm.client import LLMClient, LLMClientError


class TestLLMClient:
    """Test LLMClient class with mocked API calls."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        settings = MagicMock()
        settings.llm_endpoint = "http://localhost:1234/v1"
        settings.llm_api_key = "test-api-key"  # pragma: allowlist secret
        settings.llm.batch_size = 10
        settings.llm.embedding_dimensions = 768
        return settings

    @pytest.fixture
    def client(self, mock_settings):
        """Create LLM client with mocked settings."""
        with patch("scriptrag.llm.client.get_settings", return_value=mock_settings):
            return LLMClient()

    def test_client_initialization(self, mock_settings):
        """Test client initialization with various configurations."""
        with patch("scriptrag.llm.client.get_settings", return_value=mock_settings):
            # Default initialization
            client = LLMClient()
            assert client.endpoint == "http://localhost:1234/v1"
            assert client.api_key == "test-api-key"  # pragma: allowlist secret
            assert client.default_chat_model == "qwen3-30b-a3b-mlx"
            assert (
                client.default_embedding_model == "text-embedding-nomic-embed-text-v1.5"
            )

            # Custom initialization
            client = LLMClient(
                endpoint="http://custom:8080/v1",
                api_key="custom-key",  # pragma: allowlist secret
                default_chat_model="custom-chat",
                default_embedding_model="custom-embed",
            )
            assert client.endpoint == "http://custom:8080/v1"
            assert client.api_key == "custom-key"  # pragma: allowlist secret
            assert client.default_chat_model == "custom-chat"
            assert client.default_embedding_model == "custom-embed"

    def test_client_initialization_no_endpoint(self, mock_settings):
        """Test client initialization fails without endpoint."""
        mock_settings.llm_endpoint = None
        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            pytest.raises(LLMClientError, match="endpoint not configured"),
        ):
            LLMClient()

    def test_client_initialization_no_api_key(self, mock_settings):
        """Test client initialization fails without API key."""
        mock_settings.llm_api_key = None
        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            pytest.raises(LLMClientError, match="API key not configured"),
        ):
            LLMClient()

    def test_base_url_extraction(self, mock_settings):
        """Test that base URL is properly extracted from endpoint."""
        test_cases = [
            ("http://localhost:1234/v1/chat/completions", "http://localhost:1234/v1"),
            ("http://localhost:1234/v1", "http://localhost:1234/v1"),
            ("http://localhost:1234/v1/", "http://localhost:1234/v1"),
            ("https://api.example.com/chat/completions", "https://api.example.com"),
        ]

        for endpoint, expected_base in test_cases:
            mock_settings.llm_endpoint = endpoint
            with patch("scriptrag.llm.client.get_settings", return_value=mock_settings):
                client = LLMClient()
                assert client.client.base_url.raw[0] == expected_base.encode()

    @pytest.mark.asyncio
    async def test_get_available_models(self, client):
        """Test retrieving available models."""
        # Mock model list response
        mock_models = [
            Model(id="model1", created=0, object="model", owned_by="test"),
            Model(id="model2", created=0, object="model", owned_by="test"),
            Model(id="model3", created=0, object="model", owned_by="test"),
        ]

        with patch.object(
            client.client.models, "list", new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = MagicMock(data=mock_models)

            models = await client.get_available_models()
            assert models == ["model1", "model2", "model3"]
            assert client._available_models == models  # Cached

            # Second call should use cache
            models2 = await client.get_available_models()
            assert models2 == models
            mock_list.assert_called_once()  # Only called once

    @pytest.mark.asyncio
    async def test_get_available_models_error(self, client):
        """Test error handling when retrieving models fails."""
        with patch.object(
            client.client.models, "list", new_callable=AsyncMock
        ) as mock_list:
            mock_list.side_effect = Exception("API error")

            with pytest.raises(LLMClientError, match="Failed to retrieve models"):
                await client.get_available_models()

    @pytest.mark.asyncio
    async def test_generate_text_basic(self, client):
        """Test basic text generation."""
        # Mock completion response
        mock_response = ChatCompletion(
            id="test-completion",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="Generated text response", role="assistant"
                    ),
                )
            ],
            created=0,
            model="test-model",
            object="chat.completion",
        )

        with patch.object(
            client, "get_available_models", new_callable=AsyncMock
        ) as mock_models:
            mock_models.return_value = ["test-model"]

            with patch.object(
                client.client.chat.completions, "create", new_callable=AsyncMock
            ) as mock_create:
                mock_create.return_value = mock_response

                result = await client.generate_text(
                    prompt="Test prompt",
                    model="test-model",
                    max_tokens=100,
                    temperature=0.5,
                )

                assert result == "Generated text response"

                # Verify API call
                mock_create.assert_called_once()
                call_args = mock_create.call_args[1]
                assert call_args["model"] == "test-model"
                assert call_args["max_tokens"] == 100
                assert call_args["temperature"] == 0.5
                assert len(call_args["messages"]) == 1
                assert call_args["messages"][0]["content"] == "Test prompt"

    @pytest.mark.asyncio
    async def test_generate_text_with_system_prompt(self, client):
        """Test text generation with system prompt."""
        mock_response = ChatCompletion(
            id="test-completion",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="Response with system context", role="assistant"
                    ),
                )
            ],
            created=0,
            model="test-model",
            object="chat.completion",
        )

        with patch.object(
            client, "get_available_models", new_callable=AsyncMock
        ) as mock_models:
            mock_models.return_value = ["test-model"]

            with patch.object(
                client.client.chat.completions, "create", new_callable=AsyncMock
            ) as mock_create:
                mock_create.return_value = mock_response

                result = await client.generate_text(
                    prompt="User prompt",
                    system_prompt="You are a helpful assistant",
                    model="test-model",
                )

                assert result == "Response with system context"

                # Verify messages include system prompt
                call_args = mock_create.call_args[1]
                assert len(call_args["messages"]) == 2
                assert call_args["messages"][0]["role"] == "system"
                assert (
                    call_args["messages"][0]["content"] == "You are a helpful assistant"
                )
                assert call_args["messages"][1]["role"] == "user"
                assert call_args["messages"][1]["content"] == "User prompt"

    @pytest.mark.asyncio
    async def test_generate_text_model_fallback(self, client):
        """Test fallback to default model when requested model unavailable."""
        mock_response = ChatCompletion(
            id="test-completion",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="Fallback response", role="assistant"
                    ),
                )
            ],
            created=0,
            model=client.default_chat_model,
            object="chat.completion",
        )

        with patch.object(
            client, "get_available_models", new_callable=AsyncMock
        ) as mock_models:
            # Requested model not in available list
            mock_models.return_value = [client.default_chat_model, "other-model"]

            with patch.object(
                client.client.chat.completions, "create", new_callable=AsyncMock
            ) as mock_create:
                mock_create.return_value = mock_response

                result = await client.generate_text(
                    prompt="Test", model="unavailable-model"
                )

                assert result == "Fallback response"

                # Verify default model was used
                call_args = mock_create.call_args[1]
                assert call_args["model"] == client.default_chat_model

    @pytest.mark.asyncio
    async def test_generate_text_reasoning_content(self, client):
        """Test handling of reasoning models with reasoning_content field."""
        # Mock response with reasoning_content instead of content
        mock_message = ChatCompletionMessage(content="", role="assistant")
        mock_message.reasoning_content = "Reasoning model response"  # type: ignore

        mock_response = ChatCompletion(
            id="test-completion",
            choices=[Choice(finish_reason="stop", index=0, message=mock_message)],
            created=0,
            model="reasoning-model",
            object="chat.completion",
        )

        with patch.object(
            client, "get_available_models", new_callable=AsyncMock
        ) as mock_models:
            mock_models.return_value = ["reasoning-model"]

            with patch.object(
                client.client.chat.completions, "create", new_callable=AsyncMock
            ) as mock_create:
                mock_create.return_value = mock_response

                result = await client.generate_text(
                    prompt="Test", model="reasoning-model"
                )

                assert result == "Reasoning model response"

    @pytest.mark.asyncio
    async def test_generate_text_no_choices(self, client):
        """Test error handling when no choices returned."""
        mock_response = ChatCompletion(
            id="test-completion",
            choices=[],
            created=0,
            model="test-model",
            object="chat.completion",
        )

        with patch.object(
            client, "get_available_models", new_callable=AsyncMock
        ) as mock_models:
            mock_models.return_value = ["test-model"]

            with patch.object(
                client.client.chat.completions, "create", new_callable=AsyncMock
            ) as mock_create:
                mock_create.return_value = mock_response

                with pytest.raises(LLMClientError, match="No choices returned"):
                    await client.generate_text(prompt="Test")

    @pytest.mark.asyncio
    async def test_generate_text_no_content(self, client):
        """Test error handling when no content in response."""
        mock_response = ChatCompletion(
            id="test-completion",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(content=None, role="assistant"),
                )
            ],
            created=0,
            model="test-model",
            object="chat.completion",
        )

        with patch.object(
            client, "get_available_models", new_callable=AsyncMock
        ) as mock_models:
            mock_models.return_value = ["test-model"]

            with patch.object(
                client.client.chat.completions, "create", new_callable=AsyncMock
            ) as mock_create:
                mock_create.return_value = mock_response

                with pytest.raises(LLMClientError, match="No content in LLM response"):
                    await client.generate_text(prompt="Test")

    @pytest.mark.asyncio
    async def test_generate_text_retry_on_timeout(self, client):
        """Test retry logic on timeout errors."""
        mock_response = ChatCompletion(
            id="test-completion",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="Success after retry", role="assistant"
                    ),
                )
            ],
            created=0,
            model="test-model",
            object="chat.completion",
        )

        with patch.object(
            client, "get_available_models", new_callable=AsyncMock
        ) as mock_models:
            mock_models.return_value = ["test-model"]

            with patch.object(
                client.client.chat.completions, "create", new_callable=AsyncMock
            ) as mock_create:
                # First call times out, second succeeds
                mock_create.side_effect = [
                    httpx.TimeoutException("Request timed out"),
                    mock_response,
                ]

                result = await client.generate_text(prompt="Test")
                assert result == "Success after retry"
                assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_text_retry_exhausted(self, client):
        """Test error when all retries are exhausted."""
        with patch.object(
            client, "get_available_models", new_callable=AsyncMock
        ) as mock_models:
            mock_models.return_value = ["test-model"]

            with patch.object(
                client.client.chat.completions, "create", new_callable=AsyncMock
            ) as mock_create:
                # All retries fail
                mock_create.side_effect = httpx.TimeoutException("Timeout")

                with pytest.raises(LLMClientError, match="Text generation failed"):
                    await client.generate_text(prompt="Test")

                # Should retry 3 times
                assert mock_create.call_count == 3

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self, client):
        """Test batch embedding generation."""
        # Mock embedding response
        mock_response = CreateEmbeddingResponse(
            data=[
                Embedding(embedding=[0.1, 0.2, 0.3], index=0, object="embedding"),
                Embedding(embedding=[0.4, 0.5, 0.6], index=1, object="embedding"),
                Embedding(embedding=[0.7, 0.8, 0.9], index=2, object="embedding"),
            ],
            model="embed-model",
            object="list",
            usage={"prompt_tokens": 10, "total_tokens": 10},
        )

        with patch.object(
            client, "get_available_models", new_callable=AsyncMock
        ) as mock_models:
            mock_models.return_value = ["embed-model"]

            with patch.object(
                client.client.embeddings, "create", new_callable=AsyncMock
            ) as mock_create:
                mock_create.return_value = mock_response

                texts = ["text1", "text2", "text3"]
                embeddings = await client.generate_embeddings(
                    texts, model="embed-model"
                )

                assert len(embeddings) == 3
                assert embeddings[0] == [0.1, 0.2, 0.3]
                assert embeddings[1] == [0.4, 0.5, 0.6]
                assert embeddings[2] == [0.7, 0.8, 0.9]

                # Verify API call
                mock_create.assert_called_once_with(model="embed-model", input=texts)

    @pytest.mark.asyncio
    async def test_generate_embeddings_empty_list(self, client):
        """Test handling empty text list."""
        embeddings = await client.generate_embeddings([])
        # Should handle gracefully, implementation may vary
        assert isinstance(embeddings, list)

    @pytest.mark.asyncio
    async def test_generate_embedding_single(self, client):
        """Test single embedding generation."""
        mock_response = CreateEmbeddingResponse(
            data=[
                Embedding(embedding=[0.1, 0.2, 0.3, 0.4], index=0, object="embedding"),
            ],
            model="embed-model",
            object="list",
            usage={"prompt_tokens": 5, "total_tokens": 5},
        )

        with patch.object(
            client, "get_available_models", new_callable=AsyncMock
        ) as mock_models:
            mock_models.return_value = ["embed-model"]

            with patch.object(
                client.client.embeddings, "create", new_callable=AsyncMock
            ) as mock_create:
                mock_create.return_value = mock_response

                embedding = await client.generate_embedding("single text")

                assert embedding == [0.1, 0.2, 0.3, 0.4]

                # Verify it called generate_embeddings with list
                mock_create.assert_called_once_with(
                    model=client.default_embedding_model, input=["single text"]
                )

    @pytest.mark.asyncio
    async def test_generate_embeddings_error_handling(self, client):
        """Test error handling in embedding generation."""
        with patch.object(
            client, "get_available_models", new_callable=AsyncMock
        ) as mock_models:
            mock_models.return_value = ["embed-model"]

            with patch.object(
                client.client.embeddings, "create", new_callable=AsyncMock
            ) as mock_create:
                mock_create.side_effect = Exception("Embedding API error")

                with pytest.raises(LLMClientError, match="Embedding generation failed"):
                    await client.generate_embeddings(["test"])

    @pytest.mark.asyncio
    async def test_context_manager(self, client):
        """Test client as async context manager."""
        async with client as ctx_client:
            assert ctx_client is client
            assert ctx_client.client is not None

        # After context, client should be closed
        # Note: AsyncOpenAI doesn't have is_closed attribute, verify no errors

    @pytest.mark.asyncio
    async def test_close_client(self, client):
        """Test closing the client."""
        with patch.object(client.client, "close", new_callable=AsyncMock) as mock_close:
            await client.close()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_additional_kwargs_passed_through(self, client):
        """Test that additional kwargs are passed to API calls."""
        mock_response = ChatCompletion(
            id="test-completion",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(content="Response", role="assistant"),
                )
            ],
            created=0,
            model="test-model",
            object="chat.completion",
        )

        with patch.object(
            client, "get_available_models", new_callable=AsyncMock
        ) as mock_models:
            mock_models.return_value = ["test-model"]

            with patch.object(
                client.client.chat.completions, "create", new_callable=AsyncMock
            ) as mock_create:
                mock_create.return_value = mock_response

                await client.generate_text(
                    prompt="Test",
                    model="test-model",
                    top_p=0.9,
                    presence_penalty=0.5,
                    custom_param="value",
                )

                # Verify additional params were passed
                call_args = mock_create.call_args[1]
                assert call_args["top_p"] == 0.9
                assert call_args["presence_penalty"] == 0.5
                assert call_args["custom_param"] == "value"

    def test_sync_initialization_error_handling(self):
        """Test synchronous error handling during initialization."""
        # Test various initialization errors
        with pytest.raises(LLMClientError):
            LLMClient(endpoint=None, api_key="key")  # pragma: allowlist secret

        with pytest.raises(LLMClientError):
            LLMClient(endpoint="http://test", api_key=None)
