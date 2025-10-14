"""GitHub Models provider using OpenAI-compatible API."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from scriptrag.config import get_logger
from scriptrag.exceptions import LLMProviderError
from scriptrag.llm.base_provider import EnhancedBaseLLMProvider
from scriptrag.llm.model_discovery import GitHubModelsDiscovery
from scriptrag.llm.model_registry import ModelRegistry
from scriptrag.llm.models import (
    CompletionChoice,
    CompletionMessage,
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
    Model,
    UsageInfo,
)
from scriptrag.llm.rate_limiter import GitHubRateLimitParser

logger = get_logger(__name__)


class GitHubModelsProvider(EnhancedBaseLLMProvider):
    """GitHub Models provider using OpenAI-compatible API."""

    provider_type = LLMProvider.GITHUB_MODELS

    def __init__(self, token: str | None = None, timeout: float = 30.0) -> None:
        """Initialize GitHub Models provider.

        Args:
            token: GitHub token. If not provided, checks GITHUB_TOKEN env var.
            timeout: HTTP request timeout in seconds.
        """
        token = token or os.getenv("GITHUB_TOKEN")
        super().__init__(
            token=token,
            timeout=timeout,
            base_url="https://models.inference.ai.azure.com",
        )

        # Initialize model discovery
        self.model_discovery: GitHubModelsDiscovery = self._init_model_discovery(
            GitHubModelsDiscovery,
            ModelRegistry.GITHUB_MODELS,
            client=self.client,
            token=self.token,
            base_url=self.base_url,
            model_id_map=ModelRegistry.GITHUB_MODEL_ID_MAP,
        )

        logger.info(
            "Initialized GitHub Models provider",
            endpoint=self.base_url,
            has_token=bool(self.token),
            timeout=timeout,
        )

    async def _validate_availability(self) -> bool:
        """Validate GitHub Models availability with API call."""
        try:
            if not self.client:
                self._init_http_client()

            if not self.client:
                return False

            headers = self._get_auth_headers()
            headers["Accept"] = "application/json"

            response = await self.client.get(
                f"{self.base_url}/models",
                headers=headers,
            )
            result = bool(response.status_code == 200)

            self.rate_limiter.update_availability_cache(result)
            logger.info(
                "GitHub Models availability check",
                is_available=result,
                status_code=response.status_code,
            )
            return result

        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            logger.warning(
                "GitHub Models not available",
                error=str(e),
                error_type=type(e).__name__,
            )
            self.rate_limiter.update_availability_cache(False)
            return False
        except (httpx.RequestError, ValueError, TypeError, OSError) as e:
            # RequestError: General httpx request errors
            # ValueError/TypeError: JSON parsing or data validation issues
            # OSError: Network/system level errors
            logger.warning(
                "GitHub Models availability check failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            self.rate_limiter.update_availability_cache(False)
            return False

    async def is_available(self) -> bool:
        """Check if GitHub Models is available."""
        # Use base class implementation for common checks
        if not await super().is_available():
            return False

        # Check if we have a cached result that's still valid
        cached_result = self.rate_limiter.check_availability_cache()
        if cached_result is not None:
            return cached_result

        # Perform actual availability validation only if no valid cache
        return await self._validate_availability()

    async def list_models(self) -> list[Model]:
        """List available models using dynamic discovery with fallback."""
        return await self.model_discovery.discover_models()

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completion using GitHub Models."""
        if not self.token:
            raise ValueError("GitHub token not configured")

        if not self.client:
            self._init_http_client()

        headers = self._get_auth_headers()

        # Prepare OpenAI-compatible request
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
            # Prepend system message
            system_msg: list[dict[str, str]] = [
                {"role": "system", "content": request.system}
            ]
            payload["messages"] = system_msg + request.messages

        # Add response_format if specified
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
                model=request.model,
                message_count=len(request.messages),
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            if not self.client:
                raise RuntimeError("HTTP client not initialized")

            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                error_text = response.text

                # Check for rate limit error
                if response.status_code == 429:
                    wait_seconds = GitHubRateLimitParser.parse_rate_limit_error(
                        error_text
                    )
                    if wait_seconds:
                        self.rate_limiter.set_rate_limit(wait_seconds, "GitHub Models")

                logger.error(
                    "GitHub Models API error",
                    status_code=response.status_code,
                    error_text=error_text[:500]
                    if len(error_text) > 500
                    else error_text,
                    model=request.model,
                )
                raise ValueError(f"GitHub Models API error: {response.text}")

            data: dict[str, Any] = response.json()

            # Extract response content for logging (safely handle malformed data)
            choices_raw = data.get("choices", [])
            response_content: str = ""
            if isinstance(choices_raw, list) and len(choices_raw) > 0:
                first_choice = choices_raw[0]
                if isinstance(first_choice, dict):
                    message = first_choice.get("message", {})
                    if isinstance(message, dict):
                        response_content = message.get("content", "") or ""

            logger.info(
                "GitHub Models completion successful",
                model=data.get("model", request.model),
                response_length=len(response_content),
                usage=data.get("usage", {}),
            )

            # Parse and validate response
            return self._parse_completion_response(data, request.model)

        except httpx.HTTPError as e:
            logger.error(
                "GitHub Models completion failed",
                error=str(e),
                error_type=type(e).__name__,
                model=request.model,
            )
            raise
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(
                "GitHub Models response parsing failed",
                error=str(e),
                error_type=type(e).__name__,
                model=request.model,
            )
            raise ValueError(f"Invalid API response: {e}") from e
        except (RuntimeError, OSError, TimeoutError) as e:
            # Catch runtime/network errors and convert to LLMProviderError
            logger.error(
                "GitHub Models completion failed with unexpected error",
                error=str(e),
                error_type=type(e).__name__,
                endpoint=f"{self.base_url}/chat/completions",
                model=request.model,
            )
            raise LLMProviderError(f"GitHub Models API error: {e}") from e

    def _parse_completion_response(
        self, data: dict[str, Any], model: str
    ) -> CompletionResponse:
        """Parse completion response data.

        Args:
            data: Response data from API
            model: Model name used

        Returns:
            Parsed completion response
        """
        # Extract usage data
        usage_data: dict[str, Any] = data.get("usage", {})
        usage: UsageInfo = {
            "prompt_tokens": usage_data.get("prompt_tokens", 0),
            "completion_tokens": usage_data.get("completion_tokens", 0),
            "total_tokens": usage_data.get("total_tokens", 0),
        }

        try:
            return CompletionResponse(
                id=data.get("id", ""),
                model=data.get("model", model),
                choices=data.get("choices", []),
                usage=usage,
                provider=self.provider_type,
            )
        except Exception as e:
            # Handle response validation errors
            logger.warning(
                "GitHub Models response validation failed, creating safe response",
                error=str(e),
            )

            # Sanitize choices data
            raw_choices = data.get("choices", [])
            sanitized_choices: list[CompletionChoice] = []

            for choice in raw_choices:
                if isinstance(choice, dict):
                    # Safely extract message, handling None case
                    message_data = choice.get("message")
                    if not isinstance(message_data, dict):
                        message_data = {}

                    message: CompletionMessage = {
                        "role": message_data.get("role") or "assistant",
                        "content": message_data.get("content") or "",
                    }
                    sanitized_choice: CompletionChoice = {
                        "index": choice.get("index", 0),
                        "message": message,
                        "finish_reason": choice.get("finish_reason", "stop"),
                    }
                    sanitized_choices.append(sanitized_choice)

            # Create default if no valid choices
            if not sanitized_choices:
                default_message: CompletionMessage = {
                    "role": "assistant",
                    "content": "",
                }
                default_choice: CompletionChoice = {
                    "index": 0,
                    "message": default_message,
                    "finish_reason": "stop",
                }
                sanitized_choices = [default_choice]

            return CompletionResponse(
                id=data.get("id", ""),
                model=data.get("model", model),
                choices=sanitized_choices,
                usage=usage,
                provider=self.provider_type,
            )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate embeddings using GitHub Models."""
        if not self.token:
            raise ValueError("GitHub token not configured")

        if not self.client:
            self._init_http_client()

        headers = self._get_auth_headers()

        payload: dict[str, str | list[str] | int] = {
            "model": request.model,
            "input": request.input,
        }

        if request.dimensions:
            payload["dimensions"] = request.dimensions

        try:
            if not self.client:
                raise RuntimeError("HTTP client not initialized")

            response = await self.client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                error_text = response.text

                # Check for rate limit error
                if response.status_code == 429:
                    wait_seconds = GitHubRateLimitParser.parse_rate_limit_error(
                        error_text
                    )
                    if wait_seconds:
                        self.rate_limiter.set_rate_limit(wait_seconds, "GitHub Models")

                raise ValueError(f"GitHub Models API error: {response.text}")

            data: dict[str, Any] = response.json()

            # Validate that we have embedding data
            embedding_data = data.get("data", [])
            if not embedding_data or len(embedding_data) == 0:
                raise ValueError("GitHub Models API returned empty embedding data")

            # Validate that each embedding entry has the required structure
            for idx, entry in enumerate(embedding_data):
                if not isinstance(entry, dict) or "embedding" not in entry:
                    raise ValueError(
                        f"Invalid embedding data at index {idx}: "
                        "missing 'embedding' field"
                    )
                if not isinstance(entry.get("embedding"), list):
                    raise ValueError(
                        f"Invalid embedding data at index {idx}: "
                        "'embedding' must be a list"
                    )

            return EmbeddingResponse(
                model=data.get("model", request.model),
                data=embedding_data,
                usage=data.get("usage", {}),
                provider=self.provider_type,
            )

        except httpx.HTTPError as e:
            logger.error(f"GitHub Models embedding request failed: {e}")
            raise
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"GitHub Models embedding response parsing failed: {e}")
            raise ValueError(f"Invalid embedding response: {e}") from e
