"""GitHub Models provider using OpenAI-compatible API."""

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


class GitHubModelsProvider(BaseLLMProvider):
    """GitHub Models provider using OpenAI-compatible API."""

    provider_type = LLMProvider.GITHUB_MODELS
    base_url = "https://models.inference.ai.azure.com"

    def __init__(self, token: str | None = None, timeout: float = 30.0) -> None:
        """Initialize GitHub Models provider.

        Args:
            token: GitHub token. If not provided, checks GITHUB_TOKEN env var.
            timeout: HTTP request timeout in seconds.
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self._availability_cache: bool | None = None
        self._cache_timestamp: float = 0

    async def is_available(self) -> bool:
        """Check if GitHub token is available and valid."""
        if not self.token:
            return False

        # Check cache (valid for 5 minutes)
        if (
            self._availability_cache is not None
            and (time.time() - self._cache_timestamp) < 300
        ):
            return self._availability_cache

        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            }
            response = await self.client.get(f"{self.base_url}/models", headers=headers)
            result = bool(response.status_code == 200)
            self._availability_cache = result
            self._cache_timestamp = time.time()
            return result
        except Exception as e:
            logger.debug(f"GitHub Models not available: {e}")
            self._availability_cache = False
            self._cache_timestamp = time.time()
            return False

    async def __aenter__(self) -> "GitHubModelsProvider":
        """Enter async context manager."""
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Exit async context manager and cleanup."""
        await self.client.aclose()

    async def list_models(self) -> list[Model]:
        """List available models from GitHub Models."""
        if not self.token:
            return []

        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            }
            response = await self.client.get(f"{self.base_url}/models", headers=headers)

            if response.status_code != 200:
                logger.warning(f"Failed to list GitHub models: {response.status_code}")
                return []

            data = response.json()

            # Handle different response formats
            if isinstance(data, list):
                models_data = data
            elif isinstance(data, dict) and "data" in data:
                models_data = data["data"]
            else:
                models_data = []

            models = []
            for model_info in models_data:
                model_id = model_info.get("id", "")
                name = model_info.get("name") or model_info.get("friendly_name", "")

                # Determine capabilities based on model type
                capabilities = []
                if "gpt" in model_id.lower() or "llama" in model_id.lower():
                    capabilities = ["completion", "chat"]
                if "embedding" in model_id.lower():
                    capabilities.append("embedding")

                models.append(
                    Model(
                        id=model_id,
                        name=name or model_id,
                        provider=self.provider_type,
                        capabilities=capabilities,
                    )
                )

            return models

        except Exception as e:
            logger.error(f"Failed to list GitHub models: {e}")
            return []

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completion using GitHub Models."""
        if not self.token:
            raise ValueError("GitHub token not configured")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        # Prepare OpenAI-compatible request
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
            # Prepend system message
            system_msg = [{"role": "system", "content": request.system}]
            payload["messages"] = system_msg + request.messages

        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                raise ValueError(f"GitHub Models API error: {response.text}")

            data = response.json()
            return CompletionResponse(
                id=data.get("id", ""),
                model=data.get("model", request.model),
                choices=data.get("choices", []),
                usage=data.get("usage", {}),
                provider=self.provider_type,
            )

        except Exception as e:
            logger.error(f"GitHub Models completion failed: {e}")
            raise

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate embeddings using GitHub Models."""
        if not self.token:
            raise ValueError("GitHub token not configured")

        headers = {
            "Authorization": f"Bearer {self.token}",
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
                raise ValueError(f"GitHub Models API error: {response.text}")

            data = response.json()
            return EmbeddingResponse(
                model=data.get("model", request.model),
                data=data.get("data", []),
                usage=data.get("usage", {}),
                provider=self.provider_type,
            )

        except Exception as e:
            logger.error(f"GitHub Models embedding failed: {e}")
            raise
