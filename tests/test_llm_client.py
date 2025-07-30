"""Tests for LLM client module."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice, CompletionUsage
from openai.types.create_embedding_response import CreateEmbeddingResponse, Embedding
from openai.types.create_embedding_response import Usage as EmbeddingUsage
from openai.types.model import Model

from scriptrag.llm.client import LLMClient, LLMClientError


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock()
    settings.llm_endpoint = "http://localhost:8080/v1"
    settings.llm_api_key = "test-api-key"  # pragma: allowlist secret
    return settings


@pytest.fixture
def mock_openai_client():
    """Create mock OpenAI client."""
    client = AsyncMock()
    client.models = AsyncMock()
    client.chat = AsyncMock()
    client.chat.completions = AsyncMock()
    client.embeddings = AsyncMock()
    return client


@pytest.mark.asyncio
class TestLLMClient:
    """Test LLMClient class."""

    async def test_init_with_config(self, mock_settings):
        """Test client initialization with config values."""
        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI") as mock_openai,
        ):
            client = LLMClient()

            assert client.endpoint == "http://localhost:8080/v1"
            assert client.api_key == "test-api-key"  # pragma: allowlist secret
            assert client.default_chat_model == "qwen3-30b-a3b-mlx"
            assert (
                client.default_embedding_model == "text-embedding-nomic-embed-text-v1.5"
            )

            mock_openai.assert_called_once_with(
                api_key="test-api-key",  # pragma: allowlist secret
                base_url="http://localhost:8080/v1",
                timeout=httpx.Timeout(60.0),
            )

    async def test_init_with_custom_values(self, mock_settings):
        """Test client initialization with custom values."""
        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI"),
        ):
            client = LLMClient(
                endpoint="http://custom:9090/v1/chat/completions",
                api_key="custom-key",  # pragma: allowlist secret
                default_chat_model="custom-chat",
                default_embedding_model="custom-embed",
            )

            assert client.endpoint == "http://custom:9090/v1/chat/completions"
            assert client.api_key == "custom-key"  # pragma: allowlist secret
            assert client.default_chat_model == "custom-chat"
            assert client.default_embedding_model == "custom-embed"

    async def test_init_missing_endpoint(self, mock_settings):
        """Test client initialization fails with missing endpoint."""
        mock_settings.llm_endpoint = None
        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            pytest.raises(LLMClientError, match="LLM endpoint not configured"),
        ):
            LLMClient()

    async def test_init_missing_api_key(self, mock_settings):
        """Test client initialization fails with missing API key."""
        mock_settings.llm_api_key = None
        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            pytest.raises(LLMClientError, match="LLM API key not configured"),
        ):
            LLMClient()

    async def test_get_available_models(self, mock_settings, mock_openai_client):
        """Test retrieving available models."""
        # Setup mock models
        models = [
            Model(id="model1", created=0, object="model", owned_by="test"),
            Model(id="model2", created=0, object="model", owned_by="test"),
        ]
        mock_response = Mock(data=models)
        mock_openai_client.models.list.return_value = mock_response

        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            client = LLMClient()
            available = await client.get_available_models()

            assert available == ["model1", "model2"]
            assert client._available_models == ["model1", "model2"]

            # Test caching
            await client.get_available_models()
            mock_openai_client.models.list.assert_called_once()

    async def test_get_available_models_error(self, mock_settings, mock_openai_client):
        """Test error handling when retrieving models."""
        mock_openai_client.models.list.side_effect = Exception("API error")

        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            client = LLMClient()
            with pytest.raises(LLMClientError, match="Failed to retrieve models"):
                await client.get_available_models()

    async def test_generate_text_success(self, mock_settings, mock_openai_client):
        """Test successful text generation."""
        # Setup available models
        models = [
            Model(id="qwen3-30b-a3b-mlx", created=0, object="model", owned_by="test")
        ]
        mock_openai_client.models.list.return_value = Mock(data=models)

        # Setup chat completion response
        message = ChatCompletionMessage(role="assistant", content="Generated text")
        choice = Choice(finish_reason="stop", index=0, message=message)
        usage = CompletionUsage(completion_tokens=10, prompt_tokens=5, total_tokens=15)
        response = ChatCompletion(
            id="test-id",
            choices=[choice],
            created=0,
            model="qwen3-30b-a3b-mlx",
            object="chat.completion",
            usage=usage,
        )
        mock_openai_client.chat.completions.create.return_value = response

        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            client = LLMClient()
            result = await client.generate_text("Test prompt")

            assert result == "Generated text"
            mock_openai_client.chat.completions.create.assert_called_once_with(
                model="qwen3-30b-a3b-mlx",
                messages=[{"role": "user", "content": "Test prompt"}],
                max_tokens=1000,
                temperature=0.7,
            )

    async def test_generate_text_with_system_prompt(
        self, mock_settings, mock_openai_client
    ):
        """Test text generation with system prompt."""
        # Setup available models
        models = [Model(id="custom-model", created=0, object="model", owned_by="test")]
        mock_openai_client.models.list.return_value = Mock(data=models)

        # Setup response
        message = ChatCompletionMessage(role="assistant", content="Response")
        choice = Choice(finish_reason="stop", index=0, message=message)
        usage = CompletionUsage(completion_tokens=10, prompt_tokens=5, total_tokens=15)
        response = ChatCompletion(
            id="test-id",
            choices=[choice],
            created=0,
            model="custom-model",
            object="chat.completion",
            usage=usage,
        )
        mock_openai_client.chat.completions.create.return_value = response

        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            client = LLMClient()
            result = await client.generate_text(
                "User prompt",
                model="custom-model",
                system_prompt="System instructions",
                max_tokens=500,
                temperature=0.5,
            )

            assert result == "Response"
            mock_openai_client.chat.completions.create.assert_called_once_with(
                model="custom-model",
                messages=[
                    {"role": "system", "content": "System instructions"},
                    {"role": "user", "content": "User prompt"},
                ],
                max_tokens=500,
                temperature=0.5,
            )

    async def test_generate_text_model_fallback(
        self, mock_settings, mock_openai_client
    ):
        """Test model fallback when requested model is not available."""
        # Setup available models without requested model
        models = [
            Model(id="qwen3-30b-a3b-mlx", created=0, object="model", owned_by="test")
        ]
        mock_openai_client.models.list.return_value = Mock(data=models)

        # Setup response
        message = ChatCompletionMessage(role="assistant", content="Fallback response")
        choice = Choice(finish_reason="stop", index=0, message=message)
        usage = CompletionUsage(completion_tokens=10, prompt_tokens=5, total_tokens=15)
        response = ChatCompletion(
            id="test-id",
            choices=[choice],
            created=0,
            model="qwen3-30b-a3b-mlx",
            object="chat.completion",
            usage=usage,
        )
        mock_openai_client.chat.completions.create.return_value = response

        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            client = LLMClient()
            result = await client.generate_text("Test", model="unavailable-model")

            assert result == "Fallback response"
            # Should use default model
            mock_openai_client.chat.completions.create.assert_called_once()
            call_args = mock_openai_client.chat.completions.create.call_args
            assert call_args.kwargs["model"] == "qwen3-30b-a3b-mlx"

    async def test_generate_text_no_choices(self, mock_settings, mock_openai_client):
        """Test error when no choices returned."""
        # Setup available models
        models = [
            Model(id="qwen3-30b-a3b-mlx", created=0, object="model", owned_by="test")
        ]
        mock_openai_client.models.list.return_value = Mock(data=models)

        # Setup response with no choices
        usage = CompletionUsage(completion_tokens=0, prompt_tokens=5, total_tokens=5)
        response = ChatCompletion(
            id="test-id",
            choices=[],
            created=0,
            model="qwen3-30b-a3b-mlx",
            object="chat.completion",
            usage=usage,
        )
        mock_openai_client.chat.completions.create.return_value = response

        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            client = LLMClient()
            with pytest.raises(LLMClientError, match="No choices returned from LLM"):
                await client.generate_text("Test")

    async def test_generate_text_no_content(self, mock_settings, mock_openai_client):
        """Test error when no content in response."""
        # Setup available models
        models = [
            Model(id="qwen3-30b-a3b-mlx", created=0, object="model", owned_by="test")
        ]
        mock_openai_client.models.list.return_value = Mock(data=models)

        # Setup response with None content
        message = ChatCompletionMessage(role="assistant", content=None)
        choice = Choice(finish_reason="stop", index=0, message=message)
        usage = CompletionUsage(completion_tokens=0, prompt_tokens=5, total_tokens=5)
        response = ChatCompletion(
            id="test-id",
            choices=[choice],
            created=0,
            model="qwen3-30b-a3b-mlx",
            object="chat.completion",
            usage=usage,
        )
        mock_openai_client.chat.completions.create.return_value = response

        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            client = LLMClient()
            with pytest.raises(LLMClientError, match="No content in LLM response"):
                await client.generate_text("Test")

    async def test_generate_text_reasoning_content(
        self, mock_settings, mock_openai_client
    ):
        """Test handling of reasoning_content fallback."""
        # Setup available models
        models = [
            Model(id="qwen3-30b-a3b-mlx", created=0, object="model", owned_by="test")
        ]
        mock_openai_client.models.list.return_value = Mock(data=models)

        # Setup response with reasoning_content
        message = ChatCompletionMessage(role="assistant", content="")
        message.reasoning_content = "Reasoning response"
        choice = Choice(finish_reason="stop", index=0, message=message)
        response = Mock()
        response.choices = [choice]
        mock_openai_client.chat.completions.create.return_value = response

        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            client = LLMClient()
            result = await client.generate_text("Test")

            assert result == "Reasoning response"

    async def test_generate_text_retry_on_timeout(
        self, mock_settings, mock_openai_client
    ):
        """Test retry logic on timeout errors."""
        # Setup available models
        models = [
            Model(id="qwen3-30b-a3b-mlx", created=0, object="model", owned_by="test")
        ]
        mock_openai_client.models.list.return_value = Mock(data=models)

        # First call times out, second succeeds
        message = ChatCompletionMessage(role="assistant", content="Success after retry")
        choice = Choice(finish_reason="stop", index=0, message=message)
        usage = CompletionUsage(completion_tokens=10, prompt_tokens=5, total_tokens=15)
        response = ChatCompletion(
            id="test-id",
            choices=[choice],
            created=0,
            model="qwen3-30b-a3b-mlx",
            object="chat.completion",
            usage=usage,
        )
        mock_openai_client.chat.completions.create.side_effect = [
            httpx.TimeoutException("Timeout"),
            response,
        ]

        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            client = LLMClient()
            result = await client.generate_text("Test")

            assert result == "Success after retry"
            assert mock_openai_client.chat.completions.create.call_count == 2

    async def test_generate_embeddings_success(self, mock_settings, mock_openai_client):
        """Test successful embedding generation."""
        # Setup available models
        models = [
            Model(
                id="text-embedding-nomic-embed-text-v1.5",
                created=0,
                object="model",
                owned_by="test",
            )
        ]
        mock_openai_client.models.list.return_value = Mock(data=models)

        # Setup embedding response
        embeddings_data = [
            Embedding(embedding=[0.1, 0.2, 0.3], index=0, object="embedding"),
            Embedding(embedding=[0.4, 0.5, 0.6], index=1, object="embedding"),
        ]
        usage = EmbeddingUsage(prompt_tokens=10, total_tokens=10)
        response = CreateEmbeddingResponse(
            data=embeddings_data,
            model="text-embedding-nomic-embed-text-v1.5",
            object="list",
            usage=usage,
        )
        mock_openai_client.embeddings.create.return_value = response

        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            client = LLMClient()
            result = await client.generate_embeddings(["text1", "text2"])

            assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
            mock_openai_client.embeddings.create.assert_called_once_with(
                model="text-embedding-nomic-embed-text-v1.5",
                input=["text1", "text2"],
            )

    async def test_generate_embeddings_model_fallback(
        self, mock_settings, mock_openai_client
    ):
        """Test embedding model fallback when requested model is not available."""
        # Setup available models without requested model
        models = [
            Model(
                id="text-embedding-nomic-embed-text-v1.5",
                created=0,
                object="model",
                owned_by="test",
            )
        ]
        mock_openai_client.models.list.return_value = Mock(data=models)

        # Setup response
        embeddings_data = [Embedding(embedding=[0.1, 0.2], index=0, object="embedding")]
        usage = EmbeddingUsage(prompt_tokens=5, total_tokens=5)
        response = CreateEmbeddingResponse(
            data=embeddings_data,
            model="text-embedding-nomic-embed-text-v1.5",
            object="list",
            usage=usage,
        )
        mock_openai_client.embeddings.create.return_value = response

        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            client = LLMClient()
            result = await client.generate_embeddings(
                ["text"], model="unavailable-embed"
            )

            assert result == [[0.1, 0.2]]
            # Should use default model
            call_args = mock_openai_client.embeddings.create.call_args
            assert call_args.kwargs["model"] == "text-embedding-nomic-embed-text-v1.5"

    async def test_generate_embeddings_error(self, mock_settings, mock_openai_client):
        """Test error handling in embedding generation."""
        # Setup available models
        models = [
            Model(
                id="text-embedding-nomic-embed-text-v1.5",
                created=0,
                object="model",
                owned_by="test",
            )
        ]
        mock_openai_client.models.list.return_value = Mock(data=models)

        # Setup error
        mock_openai_client.embeddings.create.side_effect = Exception("API error")

        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            client = LLMClient()
            with pytest.raises(LLMClientError, match="Embedding generation failed"):
                await client.generate_embeddings(["text"])

    async def test_generate_embedding_single(self, mock_settings, mock_openai_client):
        """Test single embedding generation."""
        # Setup available models
        models = [
            Model(
                id="text-embedding-nomic-embed-text-v1.5",
                created=0,
                object="model",
                owned_by="test",
            )
        ]
        mock_openai_client.models.list.return_value = Mock(data=models)

        # Setup response
        embeddings_data = [
            Embedding(embedding=[0.7, 0.8, 0.9], index=0, object="embedding")
        ]
        usage = EmbeddingUsage(prompt_tokens=5, total_tokens=5)
        response = CreateEmbeddingResponse(
            data=embeddings_data,
            model="text-embedding-nomic-embed-text-v1.5",
            object="list",
            usage=usage,
        )
        mock_openai_client.embeddings.create.return_value = response

        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            client = LLMClient()
            result = await client.generate_embedding("single text")

            assert result == [0.7, 0.8, 0.9]
            mock_openai_client.embeddings.create.assert_called_once_with(
                model="text-embedding-nomic-embed-text-v1.5",
                input=["single text"],
            )

    async def test_context_manager(self, mock_settings, mock_openai_client):
        """Test async context manager functionality."""
        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            async with LLMClient() as client:
                assert isinstance(client, LLMClient)

            mock_openai_client.close.assert_called_once()

    async def test_close(self, mock_settings, mock_openai_client):
        """Test close method."""
        with (
            patch("scriptrag.llm.client.get_settings", return_value=mock_settings),
            patch("scriptrag.llm.client.AsyncOpenAI", return_value=mock_openai_client),
        ):
            client = LLMClient()
            await client.close()

            mock_openai_client.close.assert_called_once()
