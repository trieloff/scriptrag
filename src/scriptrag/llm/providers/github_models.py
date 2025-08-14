"""GitHub Models provider using OpenAI-compatible API."""

import json
import os
import re
import time
from typing import Any, ClassVar, Literal, TypedDict

import httpx

from scriptrag.config import get_logger
from scriptrag.llm.base import BaseLLMProvider
from scriptrag.llm.model_discovery import GitHubModelsDiscovery
from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
    Model,
)

logger = get_logger(__name__)


# Type definitions for structured data
class GitHubErrorInfo(TypedDict, total=False):
    """Type for GitHub API error information."""

    code: str
    message: str
    type: str


class GitHubErrorResponse(TypedDict, total=False):
    """Type for GitHub API error response."""

    error: GitHubErrorInfo


class CompletionChoice(TypedDict):
    """Type for completion choice."""

    index: int
    message: dict[str, str]
    finish_reason: Literal["stop", "length", "content_filter"]


class CompletionUsage(TypedDict):
    """Type for completion usage stats."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class EmbeddingData(TypedDict):
    """Type for embedding data."""

    index: int
    embedding: list[float]
    object: Literal["embedding"]


class EmbeddingUsage(TypedDict):
    """Type for embedding usage stats."""

    prompt_tokens: int
    total_tokens: int


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

    # Static model list as fallback
    STATIC_MODELS: ClassVar[list[Model]] = [
        Model(
            id="gpt-4o",
            name="GPT-4o",
            provider=LLMProvider.GITHUB_MODELS,
            capabilities=["completion", "chat"],
            context_window=128000,
            max_output_tokens=16384,
        ),
        Model(
            id="gpt-4o-mini",
            name="GPT-4o Mini",
            provider=LLMProvider.GITHUB_MODELS,
            capabilities=["completion", "chat"],
            context_window=128000,
            max_output_tokens=16384,
        ),
    ]

    def __init__(self, token: str | None = None, timeout: float = 30.0) -> None:
        """Initialize GitHub Models provider.

        Args:
            token: GitHub token. If not provided, checks GITHUB_TOKEN env var.
            timeout: HTTP request timeout in seconds.
        """
        self.token: str | None = token or os.getenv("GITHUB_TOKEN")
        self.timeout: float = timeout
        self.client: httpx.AsyncClient = httpx.AsyncClient(timeout=timeout)
        self._availability_cache: bool | None = None
        self._cache_timestamp: float = 0
        self._rate_limit_reset_time: float = 0  # Track when rate limit resets

        # Initialize model discovery
        from scriptrag.config import get_settings

        settings = get_settings()

        self.model_discovery: GitHubModelsDiscovery = GitHubModelsDiscovery(
            provider_name="github_models",
            static_models=self.STATIC_MODELS,
            client=self.client,
            token=self.token,
            base_url=self.base_url,
            cache_ttl=(
                settings.llm_model_cache_ttl
                if settings.llm_model_cache_ttl > 0
                else None
            ),
            use_cache=settings.llm_model_cache_ttl > 0,
            force_static=settings.llm_force_static_models,
        )

        logger.info(
            "Initialized GitHub Models provider",
            endpoint=self.base_url,
            has_token=bool(self.token),
            timeout=timeout,
            force_static=settings.llm_force_static_models,
        )

    async def is_available(self) -> bool:
        """Check if GitHub token is available and valid."""
        if not self.token:
            logger.debug(
                "GitHub Models not available",
                reason="no token configured",
            )
            return False

        # Check if we're rate limited
        if (
            self._rate_limit_reset_time > 0
            and time.time() < self._rate_limit_reset_time
        ):
            logger.debug(
                "GitHub Models not available due to rate limit",
                reset_time=self._rate_limit_reset_time,
                seconds_until_reset=self._rate_limit_reset_time - time.time(),
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

    def _parse_rate_limit_error(self, error_text: str) -> int | None:
        """Parse rate limit error and return seconds to wait.

        Args:
            error_text: Error response text from API

        Returns:
            Number of seconds to wait, or None if not a rate limit error
        """
        try:
            # Parse JSON error response
            error_data: dict[str, Any] = json.loads(error_text)
            if "error" in error_data:
                error_info = error_data["error"]
                if error_info.get("code") == "RateLimitReached":
                    # Extract wait time from message
                    # "Please wait 42911 seconds before retrying."
                    message = error_info.get("message", "")
                    match = re.search(r"wait (\d+) seconds", message)
                    if match:
                        return int(match.group(1))
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
        return None

    async def __aenter__(self) -> "GitHubModelsProvider":
        """Enter async context manager."""
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Exit async context manager and cleanup."""
        await self.client.aclose()

    async def list_models(self) -> list[Model]:
        """List available models using dynamic discovery with fallback."""
        return await self.model_discovery.discover_models()

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completion using GitHub Models."""
        if not self.token:
            raise ValueError("GitHub token not configured")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        # Prepare OpenAI-compatible request
        # GitHub Models API expects specific model IDs
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

                # Check for rate limit error
                if response.status_code == 429:
                    wait_seconds = self._parse_rate_limit_error(error_text)
                    if wait_seconds:
                        # Set rate limit reset time
                        self._rate_limit_reset_time = time.time() + wait_seconds
                        self._availability_cache = False
                        self._cache_timestamp = time.time()
                        logger.warning(
                            "GitHub Models rate limited",
                            wait_seconds=wait_seconds,
                            reset_time=self._rate_limit_reset_time,
                            model=request.model,
                        )

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
                error_text = response.text

                # Check for rate limit error
                if response.status_code == 429:
                    wait_seconds = self._parse_rate_limit_error(error_text)
                    if wait_seconds:
                        # Set rate limit reset time
                        self._rate_limit_reset_time = time.time() + wait_seconds
                        self._availability_cache = False
                        self._cache_timestamp = time.time()
                        logger.warning(
                            "GitHub Models rate limited on embeddings",
                            wait_seconds=wait_seconds,
                            reset_time=self._rate_limit_reset_time,
                            model=request.model,
                        )

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
