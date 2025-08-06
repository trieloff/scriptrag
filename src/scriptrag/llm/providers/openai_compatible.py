"""Generic OpenAI-compatible API provider."""

import os
import time
from typing import Any

import httpx

from scriptrag.config import get_logger
from scriptrag.llm.base import BaseLLMProvider
from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
    Model,
)

logger = get_logger(__name__)


class OpenAICompatibleProvider(BaseLLMProvider):
    """Generic OpenAI-compatible API provider."""

    provider_type = LLMProvider.OPENAI_COMPATIBLE

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize OpenAI-compatible provider.

        Args:
            endpoint: API endpoint URL. If not provided, checks SCRIPTRAG_LLM_ENDPOINT.
            api_key: API key. If not provided, checks SCRIPTRAG_LLM_API_KEY.
            timeout: HTTP request timeout in seconds.
        """
        self.base_url = endpoint or os.getenv("SCRIPTRAG_LLM_ENDPOINT", "")
        self.api_key = api_key or os.getenv("SCRIPTRAG_LLM_API_KEY", "")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self._availability_cache: bool | None = None
        self._cache_timestamp: float = 0

    async def is_available(self) -> bool:
        """Check if endpoint and API key are configured."""
        if not self.base_url or not self.api_key:
            return False

        # Check cache (valid for 5 minutes)
        if (
            self._availability_cache is not None
            and (time.time() - self._cache_timestamp) < 300
        ):
            return self._availability_cache

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            }
            response = await self.client.get(f"{self.base_url}/models", headers=headers)
            result = bool(response.status_code == 200)
            self._availability_cache = result
            self._cache_timestamp = time.time()
            return result
        except Exception as e:
            logger.debug(f"OpenAI-compatible endpoint not available: {e}")
            self._availability_cache = False
            self._cache_timestamp = time.time()
            return False

    async def __aenter__(self) -> "OpenAICompatibleProvider":
        """Enter async context manager."""
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Exit async context manager and cleanup."""
        await self.client.aclose()

    async def list_models(self) -> list[Model]:
        """List available models from OpenAI-compatible endpoint."""
        if not self.base_url or not self.api_key:
            return []

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            }
            response = await self.client.get(f"{self.base_url}/models", headers=headers)

            if response.status_code != 200:
                logger.warning(f"Failed to list models: {response.status_code}")
                return []

            data = response.json()

            # Handle OpenAI response format
            if isinstance(data, dict) and "data" in data:
                models_data = data["data"]
            else:
                models_data = []

            models = []
            for model_info in models_data:
                model_id = model_info.get("id", "")

                # Determine capabilities
                capabilities = ["completion", "chat"]
                if "embedding" in model_id.lower():
                    capabilities = ["embedding"]

                models.append(
                    Model(
                        id=model_id,
                        name=model_id,
                        provider=self.provider_type,
                        capabilities=capabilities,
                    )
                )

            return models

        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completion using OpenAI-compatible API."""
        if not self.base_url or not self.api_key:
            raise ValueError("OpenAI-compatible endpoint not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": request.stream,
        }

        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        if request.system:
            system_msg = [{"role": "system", "content": request.system}]
            payload["messages"] = system_msg + request.messages

        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                raise ValueError(f"API error: {response.text}")

            data = response.json()
            return CompletionResponse(
                id=data.get("id", ""),
                model=data.get("model", request.model),
                choices=data.get("choices", []),
                usage=data.get("usage", {}),
                provider=self.provider_type,
            )

        except Exception as e:
            logger.error(f"Completion failed: {e}")
            raise

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate embeddings using OpenAI-compatible API."""
        if not self.base_url or not self.api_key:
            raise ValueError("OpenAI-compatible endpoint not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, str | list[str] | int] = {
            "model": request.model,
            "input": request.input,
        }

        if request.dimensions:
            payload["dimensions"] = request.dimensions

        try:
            response = await self.client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                raise ValueError(f"API error: {response.text}")

            data = response.json()
            return EmbeddingResponse(
                model=data.get("model", request.model),
                data=data.get("data", []),
                usage=data.get("usage", {}),
                provider=self.provider_type,
            )

        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise
