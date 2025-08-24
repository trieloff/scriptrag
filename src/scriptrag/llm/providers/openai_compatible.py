"""Generic OpenAI-compatible API provider."""

import asyncio
import json
import os
import time
from typing import Any, ClassVar

import httpx

from scriptrag.config import get_logger
from scriptrag.exceptions import LLMProviderError
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

    # Model preference order - faster models first
    MODEL_PREFERENCE_ORDER: ClassVar[list[str]] = [
        "qwen/qwen3-30b-a3b-mlx",  # Fastest
        "mlx-community/glm-4-9b-chat-4bit",  # Slower but still acceptable
        # Add more models here in order of preference
    ]

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
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
        # Use a longer timeout for the httpx client
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        self._availability_cache: bool | None = None
        self._cache_timestamp: float = 0
        # Semaphore to prevent concurrent requests for local LLM servers
        self._request_semaphore = asyncio.Semaphore(1)

        logger.info(
            "Initialized OpenAI-compatible provider",
            endpoint=self.base_url if self.base_url else "not configured",
            has_api_key=bool(self.api_key),
            timeout=timeout,
        )

    async def is_available(self) -> bool:
        """Check if endpoint and API key are configured."""
        if not self.base_url or not self.api_key:
            logger.debug(
                "OpenAI-compatible provider not available",
                reason="missing configuration",
                has_endpoint=bool(self.base_url),
                has_api_key=bool(self.api_key),
            )
            return False

        # Check cache (valid for 5 minutes)
        if (
            self._availability_cache is not None
            and (time.time() - self._cache_timestamp) < 300
        ):
            logger.debug(
                "Using cached availability",
                is_available=self._availability_cache,
                cache_age=time.time() - self._cache_timestamp,
            )
            return self._availability_cache

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            }
            models_url = f"{self.base_url}/models"
            logger.debug(f"Checking OpenAI-compatible availability at {models_url}")
            response = await self.client.get(models_url, headers=headers)
            result = bool(response.status_code == 200)
            self._availability_cache = result
            self._cache_timestamp = time.time()
            logger.info(
                "OpenAI-compatible provider availability check",
                is_available=result,
                status_code=response.status_code,
                endpoint=self.base_url,
            )
            return result
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            # httpx.ConnectError: Connection refused or network issues
            # httpx.TimeoutException: Request timeout
            # httpx.HTTPStatusError: Non-2xx status codes
            logger.warning(
                "OpenAI-compatible endpoint not available",
                error=str(e),
                error_type=type(e).__name__,
                endpoint=self.base_url,
            )
            self._availability_cache = False
            self._cache_timestamp = time.time()
            return False
        except Exception as e:
            # Any other unexpected error during availability check
            logger.warning(
                "OpenAI-compatible endpoint not available due to unexpected error",
                error=str(e),
                error_type=type(e).__name__,
                endpoint=self.base_url,
            )
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

            data: dict[str, Any] = response.json()

            # Handle OpenAI response format
            models_data: list[dict[str, Any]]
            if isinstance(data, dict) and "data" in data:
                models_data = data["data"]
            else:
                models_data = []

            models: list[Model] = []
            for model_info in models_data:
                model_id: str = model_info.get("id", "")

                # Determine capabilities
                capabilities: list[str] = ["completion", "chat"]
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

            # Sort models by preference order
            def model_sort_key(model: Model) -> tuple[int, str]:
                try:
                    # Check if model ID is in preference list
                    idx = self.MODEL_PREFERENCE_ORDER.index(model.id)
                    return (idx, model.id)
                except ValueError:
                    # Not in preference list, put at end
                    return (len(self.MODEL_PREFERENCE_ORDER), model.id)

            models.sort(key=model_sort_key)
            return models

        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError) as e:
            # httpx.HTTPError: Base class for all httpx errors
            # json.JSONDecodeError: Invalid JSON response
            # KeyError: Missing expected fields in response
            # TypeError: Unexpected response structure
            logger.error(f"Failed to list models: {e}")
            return []
        except Exception as e:
            # Any other unexpected error during model listing
            logger.error(f"Failed to list models due to unexpected error: {e}")
            return []

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completion using OpenAI-compatible API."""
        if not self.base_url or not self.api_key:
            raise ValueError("OpenAI-compatible endpoint not configured")

        # Use semaphore to prevent concurrent requests for local LLM servers
        async with self._request_semaphore:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload: dict[str, Any] = {
                "model": request.model,
                "messages": request.messages,
                "temperature": request.temperature,
                "top_p": request.top_p,
                "stream": request.stream,
            }

            if request.max_tokens:
                payload["max_tokens"] = request.max_tokens
            if request.system:
                system_msg: list[dict[str, str]] = [
                    {"role": "system", "content": request.system}
                ]
                payload["messages"] = system_msg + request.messages

            # Add response_format if specified
            if hasattr(request, "response_format") and request.response_format:
                payload["response_format"] = request.response_format
                logger.debug(
                    "Using structured output format",
                    response_format_type=request.response_format.get("type"),
                    has_schema="schema" in request.response_format,
                )

            completions_url = f"{self.base_url}/chat/completions"
            logger.info(
                "Sending OpenAI-compatible completion request",
                endpoint=completions_url,
                model=request.model,
                message_count=len(request.messages),
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                has_response_format=bool(payload.get("response_format")),
            )

            try:
                response = await self.client.post(
                    completions_url,
                    headers=headers,
                    json=payload,
                )

                if response.status_code != 200:
                    error_text = response.text
                    logger.error(
                        "OpenAI-compatible API error",
                        status_code=response.status_code,
                        error_text=error_text[:500]
                        if len(error_text) > 500
                        else error_text,
                        endpoint=completions_url,
                        model=request.model,
                    )
                    raise ValueError(f"API error: {response.text}")

                data: dict[str, Any] = response.json()

                # Log successful response
                choices: list[dict[str, Any]] = data.get("choices", [])
                response_content: str = ""
                if choices and len(choices) > 0:
                    response_content = choices[0].get("message", {}).get("content", "")

                logger.info(
                    "OpenAI-compatible completion successful",
                    model=data.get("model", request.model),
                    response_length=len(response_content),
                    usage=data.get("usage", {}),
                    response_preview=response_content[:200]
                    if len(response_content) > 200
                    else response_content,
                )

                return CompletionResponse(
                    id=data.get("id", ""),
                    model=data.get("model", request.model),
                    choices=data.get("choices", []),
                    usage=data.get("usage", {}),
                    provider=self.provider_type,
                )

            except httpx.HTTPError as e:
                # httpx.HTTPError: Base class for all httpx errors
                logger.error(
                    "OpenAI-compatible completion failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    endpoint=completions_url,
                    model=request.model,
                )
                raise
            except (json.JSONDecodeError, KeyError) as e:
                # json.JSONDecodeError: Invalid JSON in response
                # KeyError: Missing required fields in response
                logger.error(
                    "OpenAI-compatible completion response parsing failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    endpoint=completions_url,
                    model=request.model,
                )
                raise ValueError(f"Invalid API response: {e}") from e
            except Exception as e:
                # Catch any other unexpected errors and convert to LLMProviderError
                logger.error(
                    "OpenAI-compatible completion failed with unexpected error",
                    error=str(e),
                    error_type=type(e).__name__,
                    endpoint=completions_url,
                    model=request.model,
                )
                raise LLMProviderError(f"OpenAI-compatible API error: {e}") from e

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

            data: dict[str, Any] = response.json()
            return EmbeddingResponse(
                model=data.get("model", request.model),
                data=data.get("data", []),
                usage=data.get("usage", {}),
                provider=self.provider_type,
            )

        except httpx.HTTPError as e:
            # httpx.HTTPError: Base class for all httpx errors
            logger.error(f"Embedding request failed: {e}")
            raise
        except (json.JSONDecodeError, KeyError) as e:
            # json.JSONDecodeError: Invalid JSON in response
            # KeyError: Missing required fields in response
            logger.error(f"Embedding response parsing failed: {e}")
            raise ValueError(f"Invalid embedding response: {e}") from e
