"""LLM client for ScriptRAG using OpenAI-compatible API."""

from typing import Any, cast

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scriptrag.config import get_logger, get_settings


class LLMClientError(Exception):
    """Base exception for LLM client errors."""


class LLMClient:
    """OpenAI-compatible client for LMStudio and other compatible endpoints.

    Provides text generation and embeddings with retry logic, error handling,
    and response caching.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        default_chat_model: str | None = None,
        default_embedding_model: str | None = None,
    ) -> None:
        """Initialize LLM client.

        Args:
            endpoint: API endpoint URL. Defaults to config value.
            api_key: API key. Defaults to config value.
            default_chat_model: Default model for chat completions.
            default_embedding_model: Default model for embeddings.
        """
        self.config = get_settings()
        self.logger = get_logger(__name__)

        # Use provided values or fall back to config
        self.endpoint = endpoint or self.config.llm_endpoint
        self.api_key = api_key or self.config.llm_api_key

        if not self.endpoint:
            raise LLMClientError("LLM endpoint not configured")
        if not self.api_key:
            raise LLMClientError("LLM API key not configured")

        # Extract base URL from endpoint (remove /chat/completions if present)
        base_url = self.endpoint.replace("/chat/completions", "").rstrip("/")

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=base_url,
            timeout=httpx.Timeout(60.0),
        )

        # Set defaults based on available models
        self.default_chat_model = default_chat_model or "qwen3-30b-a3b-mlx"
        self.default_embedding_model = (
            default_embedding_model or "text-embedding-nomic-embed-text-v1.5"
        )

        self._available_models: list[str] | None = None

    async def get_available_models(self) -> list[str]:
        """Get list of available models from the endpoint."""
        if self._available_models is None:
            try:
                models = await self.client.models.list()
                self._available_models = [model.id for model in models.data]
                self.logger.info(
                    "Retrieved available models", count=len(self._available_models)
                )
            except Exception as e:
                self.logger.error("Failed to retrieve models", error=str(e))
                raise LLMClientError(f"Failed to retrieve models: {e}") from e

        return self._available_models

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def generate_text(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate text using the LLM.

        Args:
            prompt: User prompt for text generation.
            model: Model to use. Defaults to default_chat_model.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            system_prompt: Optional system prompt.
            **kwargs: Additional parameters for the API.

        Returns:
            Generated text.

        Raises:
            LLMClientError: If generation fails.
        """
        model = model or self.default_chat_model

        # Ensure model is available
        available_models = await self.get_available_models()
        if model not in available_models:
            self.logger.warning(
                "Requested model not available, using default",
                requested=model,
                default=self.default_chat_model,
                available=available_models,
            )
            model = self.default_chat_model

        messages: list[ChatCompletionMessageParam] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )

            if not response.choices:
                raise LLMClientError("No choices returned from LLM")

            content = response.choices[0].message.content

            # Handle reasoning models that put content in reasoning_content
            if content is None or content == "":
                reasoning_content = getattr(
                    response.choices[0].message, "reasoning_content", None
                )
                if reasoning_content:
                    content = reasoning_content

            if content is None or content == "":
                raise LLMClientError("No content in LLM response")

            # Type cast: content is guaranteed to be str after None check
            content = cast(str, content)

            self.logger.debug(
                "Generated text",
                model=model,
                prompt_length=len(prompt),
                response_length=len(content),
            )

            return content

        except Exception as e:
            self.logger.error("Text generation failed", model=model, error=str(e))
            raise LLMClientError(f"Text generation failed: {e}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def generate_embeddings(
        self,
        texts: list[str],
        model: str | None = None,
        **kwargs: Any,
    ) -> list[list[float]]:
        """Generate embeddings for the given texts.

        Args:
            texts: List of texts to embed.
            model: Model to use. Defaults to default_embedding_model.
            **kwargs: Additional parameters for the API.

        Returns:
            List of embedding vectors.

        Raises:
            LLMClientError: If embedding generation fails.
        """
        model = model or self.default_embedding_model

        # Ensure model is available
        available_models = await self.get_available_models()
        if model not in available_models:
            self.logger.warning(
                "Requested embedding model not available, using default",
                requested=model,
                default=self.default_embedding_model,
                available=available_models,
            )
            model = self.default_embedding_model

        try:
            response = await self.client.embeddings.create(
                model=model,
                input=texts,
                **kwargs,
            )

            embeddings = [item.embedding for item in response.data]

            self.logger.debug(
                "Generated embeddings",
                model=model,
                text_count=len(texts),
                embedding_dim=len(embeddings[0]) if embeddings else 0,
            )

            return embeddings

        except Exception as e:
            self.logger.error("Embedding generation failed", model=model, error=str(e))
            raise LLMClientError(f"Embedding generation failed: {e}") from e

    async def generate_embedding(
        self,
        text: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed.
            model: Model to use. Defaults to default_embedding_model.
            **kwargs: Additional parameters for the API.

        Returns:
            Embedding vector.

        Raises:
            LLMClientError: If embedding generation fails.
        """
        embeddings = await self.generate_embeddings([text], model=model, **kwargs)
        # Type annotation: embeddings[0] is list[float]
        embedding: list[float] = embeddings[0]
        return embedding

    async def close(self) -> None:
        """Close the client and cleanup resources."""
        await self.client.close()

    async def __aenter__(self) -> "LLMClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, _exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
