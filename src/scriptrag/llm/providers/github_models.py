"""GitHub Models provider using OpenAI-compatible API."""

import os
import time
from typing import Any, ClassVar

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

    # Map Azure registry paths to simple model IDs
    MODEL_ID_MAP: ClassVar[dict[str, str]] = {
        (
            "azureml://registries/azureml-meta/models/Meta-Llama-3-70B-Instruct/"
            "versions/6"
        ): "Meta-Llama-3-70B-Instruct",
        (
            "azureml://registries/azureml-meta/models/Meta-Llama-3-8B-Instruct/"
            "versions/6"
        ): "Meta-Llama-3-8B-Instruct",
        (
            "azureml://registries/azureml-meta/models/Meta-Llama-3.1-405B-Instruct/"
            "versions/1"
        ): "Meta-Llama-3.1-405B-Instruct",
        (
            "azureml://registries/azureml-meta/models/Meta-Llama-3.1-70B-Instruct/"
            "versions/1"
        ): "Meta-Llama-3.1-70B-Instruct",
        (
            "azureml://registries/azureml-meta/models/Meta-Llama-3.1-8B-Instruct/"
            "versions/1"
        ): "Meta-Llama-3.1-8B-Instruct",
        "azureml://registries/azure-openai/models/gpt-4o-mini/versions/1": (
            "gpt-4o-mini"
        ),
        "azureml://registries/azure-openai/models/gpt-4o/versions/2": "gpt-4o",
    }

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

        logger.info(
            "Initialized GitHub Models provider",
            endpoint=self.base_url,
            has_token=bool(self.token),
            timeout=timeout,
        )

    async def is_available(self) -> bool:
        """Check if GitHub token is available and valid."""
        if not self.token:
            logger.debug(
                "GitHub Models not available",
                reason="no token configured",
            )
            return False

        # Check cache (valid for 5 minutes)
        if (
            self._availability_cache is not None
            and (time.time() - self._cache_timestamp) < 300
        ):
            logger.debug(
                "Using cached GitHub Models availability",
                is_available=self._availability_cache,
                cache_age=time.time() - self._cache_timestamp,
            )
            return self._availability_cache

        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            }
            models_url = f"{self.base_url}/models"
            logger.debug(f"Checking GitHub Models availability at {models_url}")
            response = await self.client.get(models_url, headers=headers)
            result = bool(response.status_code == 200)
            self._availability_cache = result
            self._cache_timestamp = time.time()
            logger.info(
                "GitHub Models availability check",
                is_available=result,
                status_code=response.status_code,
                endpoint=self.base_url,
            )
            return result
        except Exception as e:
            logger.warning(
                "GitHub Models not available",
                error=str(e),
                error_type=type(e).__name__,
                endpoint=self.base_url,
            )
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
                azure_id = model_info.get("id", "")
                name = model_info.get("name") or model_info.get("friendly_name", "")

                # Map Azure registry path to simple model ID
                model_id = self.MODEL_ID_MAP.get(azure_id, azure_id)

                # Skip models we don't have mappings for
                if model_id == azure_id and azure_id.startswith("azureml://"):
                    logger.debug(f"Skipping unmapped model: {azure_id}")
                    continue

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
        # GitHub Models API expects simple model IDs like "gpt-4o-mini", not Azure paths
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

        # Add response_format if specified (GitHub Models uses OpenAI-compatible API)
        if hasattr(request, "response_format") and request.response_format:
            payload["response_format"] = request.response_format
            logger.debug(
                "GitHub Models using structured output format",
                response_format_type=request.response_format.get("type"),
                has_schema="schema" in request.response_format
                or "json_schema" in request.response_format,
            )

        try:
            logger.info(
                "Sending GitHub Models completion request",
                endpoint=f"{self.base_url}/chat/completions",
                model=request.model,
                message_count=len(request.messages),
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                has_response_format=bool(payload.get("response_format")),
            )

            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                error_text = response.text
                logger.error(
                    "GitHub Models API error",
                    status_code=response.status_code,
                    error_text=error_text[:500]
                    if len(error_text) > 500
                    else error_text,
                    endpoint=f"{self.base_url}/chat/completions",
                    model=request.model,
                )
                raise ValueError(f"GitHub Models API error: {response.text}")

            data = response.json()

            # Log successful response
            choices = data.get("choices", [])
            response_content = ""
            if choices and len(choices) > 0:
                response_content = choices[0].get("message", {}).get("content", "")

            logger.info(
                "GitHub Models completion successful",
                model=data.get("model", request.model),
                response_length=len(response_content),
                usage=data.get("usage", {}),
                response_preview=response_content[:200]
                if len(response_content) > 200
                else response_content,
            )

            # Extract usage data, handling GitHub Models' nested structure
            usage_data = data.get("usage", {})
            usage = {
                "prompt_tokens": usage_data.get("prompt_tokens", 0),
                "completion_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            }

            return CompletionResponse(
                id=data.get("id", ""),
                model=data.get("model", request.model),
                choices=data.get("choices", []),
                usage=usage,
                provider=self.provider_type,
            )

        except Exception as e:
            logger.error(
                "GitHub Models completion failed",
                error=str(e),
                error_type=type(e).__name__,
                endpoint=f"{self.base_url}/chat/completions",
                model=request.model,
            )
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
