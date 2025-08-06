"""Multi-provider LLM client with automatic fallback."""

import asyncio
import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, Field

from scriptrag.config import get_logger

logger = get_logger(__name__)


class LLMProvider(str, Enum):
    """Available LLM providers."""

    CLAUDE_CODE = "claude_code"
    GITHUB_MODELS = "github_models"
    OPENAI_COMPATIBLE = "openai_compatible"


class Model(BaseModel):
    """LLM model information."""

    id: str
    name: str
    provider: LLMProvider
    capabilities: list[str] = Field(default_factory=list)
    context_window: int | None = None
    max_output_tokens: int | None = None


class CompletionRequest(BaseModel):
    """Request for text completion."""

    model: str
    messages: list[dict[str, str]]
    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float = 1.0
    stream: bool = False
    system: str | None = None


class CompletionResponse(BaseModel):
    """Response from text completion."""

    id: str
    model: str
    choices: list[dict[str, Any]]
    usage: dict[str, int] = Field(default_factory=dict)
    provider: LLMProvider


class EmbeddingRequest(BaseModel):
    """Request for text embedding."""

    model: str
    input: str | list[str]
    dimensions: int | None = None


class EmbeddingResponse(BaseModel):
    """Response from text embedding."""

    model: str
    data: list[dict[str, Any]]
    usage: dict[str, int] = Field(default_factory=dict)
    provider: LLMProvider


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""

    provider_type: LLMProvider

    @abstractmethod
    async def list_models(self) -> list[Model]:
        """List available models."""
        pass

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate text completion."""
        pass

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate text embeddings."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is available."""
        pass


class ClaudeCodeProvider(BaseLLMProvider):
    """Claude Code SDK provider for local development."""

    provider_type = LLMProvider.CLAUDE_CODE

    def __init__(self) -> None:
        """Initialize Claude Code provider."""
        self.sdk_available = False
        self._check_sdk()

    def _check_sdk(self) -> None:
        """Check if Claude Code SDK is available."""
        try:
            import claude_code_sdk  # noqa: F401

            self.sdk_available = True
            logger.debug("Claude Code SDK is available")
        except ImportError:
            logger.debug("Claude Code SDK not installed")
            self.sdk_available = False

    async def is_available(self) -> bool:
        """Check if running in Claude Code environment."""
        if not self.sdk_available:
            return False

        # Primary method: Try to import and use the SDK directly
        try:
            from claude_code_sdk import ClaudeCodeOptions  # noqa: F401

            # If import succeeds, we likely have SDK access
            return True
        except ImportError:
            pass  # SDK not available, try fallback detection
        except Exception as e:
            logger.debug(f"Claude Code SDK check failed: {e}")

        # Fallback method: Check for Claude Code environment markers
        # This is less reliable but kept for backward compatibility
        claude_markers = [
            "CLAUDE_CODE_SESSION",
            "CLAUDE_SESSION_ID",
            "CLAUDE_WORKSPACE",
        ]

        return any(os.getenv(marker) for marker in claude_markers)

    async def list_models(self) -> list[Model]:
        """List available Claude models."""
        # TODO: Implement dynamic model discovery when Claude Code SDK supports it
        # Currently the SDK doesn't provide a way to list available models,
        # so we return a static list that may become outdated.
        # This should be updated when the SDK adds model enumeration support.
        return [
            Model(
                id="claude-3-opus-20240229",
                name="Claude 3 Opus",
                provider=self.provider_type,
                capabilities=["completion", "chat"],
                context_window=200000,
                max_output_tokens=4096,
            ),
            Model(
                id="claude-3-sonnet-20240229",
                name="Claude 3 Sonnet",
                provider=self.provider_type,
                capabilities=["completion", "chat"],
                context_window=200000,
                max_output_tokens=4096,
            ),
            Model(
                id="claude-3-haiku-20240307",
                name="Claude 3 Haiku",
                provider=self.provider_type,
                capabilities=["completion", "chat"],
                context_window=200000,
                max_output_tokens=4096,
            ),
        ]

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completion using Claude Code SDK."""
        try:
            from claude_code_sdk import ClaudeCodeOptions, Message, query

            # Convert messages to prompt
            prompt = self._messages_to_prompt(request.messages)

            # Set up options
            options = ClaudeCodeOptions(
                max_turns=1,
                system_prompt=request.system,
            )

            # Execute query
            messages: list[Message] = []
            async for message in query(prompt=prompt, options=options):
                messages.append(message)

            # Convert to response format
            response_text = ""
            if messages:
                # Extract text content from last message
                last_msg = messages[-1]
                if hasattr(last_msg, "content"):
                    response_text = str(last_msg.content)

            return CompletionResponse(
                id=f"claude-code-{os.getpid()}",
                model=request.model,
                choices=[
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": response_text},
                        "finish_reason": "stop",
                    }
                ],
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                provider=self.provider_type,
            )

        except Exception as e:
            logger.error(f"Claude Code completion failed: {e}")
            raise

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Claude Code doesn't support embeddings directly."""
        raise NotImplementedError("Claude Code SDK doesn't support embeddings")

    def _messages_to_prompt(self, messages: list[dict[str, str]]) -> str:
        """Convert messages list to single prompt string."""
        prompt_parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.insert(0, f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        return "\n\n".join(prompt_parts)


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
        import time

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

    async def __aexit__(self, *args: Any) -> None:
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
        import time

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

    async def __aexit__(self, *args: Any) -> None:
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


class LLMClient:
    """Multi-provider LLM client with automatic fallback."""

    def __init__(
        self,
        preferred_provider: LLMProvider | None = None,
        fallback_order: list[LLMProvider] | None = None,
        github_token: str | None = None,
        openai_endpoint: str | None = None,
        openai_api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize LLM client with provider preferences.

        Args:
            preferred_provider: Preferred provider to use if available.
            fallback_order: Order of providers to try if preferred isn't available.
            github_token: GitHub token for GitHub Models provider.
            openai_endpoint: Endpoint URL for OpenAI-compatible provider.
            openai_api_key: API key for OpenAI-compatible provider.
            timeout: Default timeout for HTTP requests.
        """
        self.providers: dict[LLMProvider, BaseLLMProvider] = {}
        self.current_provider: BaseLLMProvider | None = None
        self.preferred_provider = preferred_provider

        # Default fallback order
        if fallback_order is None:
            fallback_order = [
                LLMProvider.CLAUDE_CODE,
                LLMProvider.GITHUB_MODELS,
                LLMProvider.OPENAI_COMPATIBLE,
            ]
        self.fallback_order = fallback_order
        self.timeout = timeout

        # Store credentials
        self._github_token = github_token
        self._openai_endpoint = openai_endpoint
        self._openai_api_key = openai_api_key

        # Initialize providers
        self._init_providers()

        # Select best available provider
        self._provider_task = asyncio.create_task(self._select_provider())

    def _init_providers(self) -> None:
        """Initialize all provider instances."""
        self.providers[LLMProvider.CLAUDE_CODE] = ClaudeCodeProvider()
        self.providers[LLMProvider.GITHUB_MODELS] = GitHubModelsProvider(
            token=self._github_token,
            timeout=self.timeout,
        )
        self.providers[LLMProvider.OPENAI_COMPATIBLE] = OpenAICompatibleProvider(
            endpoint=self._openai_endpoint,
            api_key=self._openai_api_key,
            timeout=self.timeout,
        )

    async def _select_provider(self) -> None:
        """Select the best available provider based on preferences."""
        # Try preferred provider first
        if self.preferred_provider:
            provider = self.providers.get(self.preferred_provider)
            if provider and await provider.is_available():
                self.current_provider = provider
                logger.info(
                    f"Using preferred provider: {self.preferred_provider.value}"
                )
                return

        # Try fallback providers in order
        for provider_type in self.fallback_order:
            provider = self.providers.get(provider_type)
            if provider and await provider.is_available():
                self.current_provider = provider
                logger.info(f"Using provider: {provider_type.value}")
                return

        logger.warning("No LLM providers available")

    async def ensure_provider(self) -> BaseLLMProvider:
        """Ensure a provider is selected and available."""
        if not self.current_provider:
            await self._select_provider()

        if not self.current_provider:
            raise RuntimeError(
                "No LLM provider available. Please configure credentials."
            )

        return self.current_provider

    async def list_models(self) -> list[Model]:
        """List all available models across all available providers."""
        all_models = []

        for provider_type, provider in self.providers.items():
            try:
                if await provider.is_available():
                    models = await provider.list_models()
                    all_models.extend(models)
            except Exception as e:
                logger.debug(f"Failed to list models from {provider_type.value}: {e}")

        return all_models

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        system: str | None = None,
    ) -> CompletionResponse:
        """Generate text completion.

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            model: Model ID to use. If None, uses provider default.
            temperature: Sampling temperature (0-2).
            max_tokens: Maximum tokens to generate.
            system: System prompt to prepend.

        Returns:
            Completion response with generated text.
        """
        provider = await self.ensure_provider()

        # Use default model if not specified
        if not model:
            models = await provider.list_models()
            if models:
                # Pick first chat-capable model
                for m in models:
                    if "chat" in m.capabilities or "completion" in m.capabilities:
                        model = m.id
                        break
            if not model:
                model = "gpt-4"  # Fallback default

        request = CompletionRequest(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            system=system,
        )

        return await provider.complete(request)

    async def embed(
        self,
        text: str | list[str],
        model: str | None = None,
        dimensions: int | None = None,
    ) -> EmbeddingResponse:
        """Generate text embeddings.

        Args:
            text: Text or list of texts to embed.
            model: Model ID to use. If None, uses provider default.
            dimensions: Output embedding dimensions.

        Returns:
            Embedding response with vector representations.
        """
        provider = await self.ensure_provider()

        # Use default embedding model if not specified
        if not model:
            models = await provider.list_models()
            if models:
                # Pick first embedding-capable model
                for m in models:
                    if "embedding" in m.capabilities:
                        model = m.id
                        break
            if not model:
                model = "text-embedding-ada-002"  # Fallback default

        request = EmbeddingRequest(
            model=model,
            input=text,
            dimensions=dimensions,
        )

        return await provider.embed(request)

    def get_current_provider(self) -> LLMProvider | None:
        """Get the currently active provider type."""
        if self.current_provider:
            return self.current_provider.provider_type
        return None

    async def switch_provider(self, provider_type: LLMProvider) -> bool:
        """Manually switch to a specific provider.

        Args:
            provider_type: Provider to switch to.

        Returns:
            True if switch was successful, False otherwise.
        """
        provider = self.providers.get(provider_type)
        if provider and await provider.is_available():
            self.current_provider = provider
            logger.info(f"Switched to provider: {provider_type.value}")
            return True
        return False

    async def cleanup(self) -> None:
        """Clean up resources for all providers."""
        for provider in self.providers.values():
            if hasattr(provider, "client"):
                await provider.client.aclose()

    async def __aenter__(self) -> "LLMClient":
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context manager and cleanup."""
        await self.cleanup()
