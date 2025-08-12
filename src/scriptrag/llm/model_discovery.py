"""Dynamic model discovery with caching for LLM providers."""

import json
import time
from pathlib import Path
from typing import Any, ClassVar

from scriptrag.config import get_logger
from scriptrag.llm.models import Model

logger = get_logger(__name__)


class ModelDiscoveryCache:
    """Cache for discovered models with TTL support."""

    DEFAULT_TTL: ClassVar[int] = 3600  # 1 hour default TTL
    CACHE_DIR: ClassVar[Path] = Path.home() / ".cache" / "scriptrag"

    def __init__(self, provider_name: str, ttl: int | None = None) -> None:
        """Initialize model discovery cache.

        Args:
            provider_name: Name of the provider (e.g., "claude_code", "github_models")
            ttl: Time-to-live in seconds for cached models. None uses DEFAULT_TTL.
        """
        self.provider_name = provider_name
        self.ttl = ttl or self.DEFAULT_TTL
        self.cache_file = self.CACHE_DIR / f"{provider_name}_models.json"
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get(self) -> list[Model] | None:
        """Get cached models if still valid.

        Returns:
            List of cached models or None if cache is invalid/missing
        """
        if not self.cache_file.exists():
            logger.debug(f"No cache file found for {self.provider_name}")
            return None

        try:
            with self.cache_file.open("r") as f:
                cache_data = json.load(f)

            timestamp = cache_data.get("timestamp", 0)
            if time.time() - timestamp > self.ttl:
                logger.debug(
                    f"Cache expired for {self.provider_name}",
                    age=time.time() - timestamp,
                    ttl=self.ttl,
                )
                return None

            models_data = cache_data.get("models", [])
            models = [Model(**model_dict) for model_dict in models_data]

            logger.info(
                f"Using cached models for {self.provider_name}",
                count=len(models),
                age=int(time.time() - timestamp),
            )
            return models

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to read cache for {self.provider_name}: {e}")
            return None

    def set(self, models: list[Model]) -> None:
        """Cache models with current timestamp.

        Args:
            models: List of models to cache
        """
        try:
            cache_data = {
                "timestamp": time.time(),
                "models": [model.model_dump() for model in models],
                "provider": self.provider_name,
            }

            with self.cache_file.open("w") as f:
                json.dump(cache_data, f, indent=2)

            logger.info(
                f"Cached {len(models)} models for {self.provider_name}",
                cache_file=self.cache_file,
            )

        except Exception as e:
            logger.warning(f"Failed to cache models for {self.provider_name}: {e}")

    def clear(self) -> None:
        """Clear the cache file."""
        if self.cache_file.exists():
            self.cache_file.unlink()
            logger.debug(f"Cleared cache for {self.provider_name}")


class ModelDiscovery:
    """Base class for model discovery implementations."""

    def __init__(
        self,
        provider_name: str,
        static_models: list[Model],
        cache_ttl: int | None = None,
        use_cache: bool = True,
        force_static: bool = False,
    ) -> None:
        """Initialize model discovery.

        Args:
            provider_name: Name of the provider
            static_models: Fallback static list of models
            cache_ttl: Cache TTL in seconds
            use_cache: Whether to use caching
            force_static: Force static model list (skip dynamic discovery)
        """
        self.provider_name = provider_name
        self.static_models = static_models
        self.force_static = force_static
        self.cache = (
            ModelDiscoveryCache(provider_name, cache_ttl) if use_cache else None
        )

    async def discover_models(self) -> list[Model]:
        """Discover available models with caching and fallback.

        Returns:
            List of discovered models
        """
        # If forced to use static, return immediately
        if self.force_static:
            logger.debug(f"Using static models for {self.provider_name} (forced)")
            return self.static_models

        # Check cache first
        if self.cache:
            cached_models = self.cache.get()
            if cached_models is not None:
                return cached_models

        # Try dynamic discovery
        try:
            logger.debug(f"Attempting dynamic model discovery for {self.provider_name}")
            models = await self._fetch_models()

            if models:
                logger.info(
                    f"Discovered {len(models)} models for {self.provider_name}",
                    model_ids=[m.id for m in models[:5]],  # Log first 5 model IDs
                )
                # Cache the discovered models
                if self.cache:
                    self.cache.set(models)
                return models

        except Exception as e:
            logger.warning(
                f"Dynamic discovery failed for {self.provider_name}: {e}",
                fallback_count=len(self.static_models),
            )

        # Fall back to static models
        logger.info(
            f"Using static models for {self.provider_name}",
            count=len(self.static_models),
        )
        # Cache static models too (to avoid repeated failed attempts)
        if self.cache:
            self.cache.set(self.static_models)
        return self.static_models

    async def _fetch_models(self) -> list[Model] | None:
        """Fetch models from the provider's API.

        This should be overridden by specific implementations.

        Returns:
            List of discovered models or None if not implemented
        """
        return None


class ClaudeCodeModelDiscovery(ModelDiscovery):
    """Model discovery for Claude Code provider."""

    async def _fetch_models(self) -> list[Model] | None:
        """Fetch models from Claude Code SDK.

        Currently, the Claude Code SDK doesn't provide model enumeration,
        so this returns None to use static models.
        """
        try:
            # Try to import and check for model listing capability
            import claude_code_sdk

            # Check if SDK is available by accessing the module
            _ = claude_code_sdk.ClaudeCodeOptions

            # TODO: When SDK adds model enumeration, implement it here
            # For now, the SDK doesn't expose available models
            logger.debug("Claude Code SDK doesn't support model enumeration yet")
            return None

        except (ImportError, AttributeError):
            logger.debug("Claude Code SDK not available for model discovery")
            return None


class GitHubModelsDiscovery(ModelDiscovery):
    """Model discovery for GitHub Models provider."""

    def __init__(
        self,
        provider_name: str,
        static_models: list[Model],
        client: Any,
        token: str | None,
        base_url: str,
        cache_ttl: int | None = None,
        use_cache: bool = True,
        force_static: bool = False,
    ) -> None:
        """Initialize GitHub Models discovery.

        Args:
            provider_name: Name of the provider
            static_models: Fallback static list of models
            client: HTTP client for API calls
            token: GitHub API token
            base_url: API base URL
            cache_ttl: Cache TTL in seconds
            use_cache: Whether to use caching
            force_static: Force static model list
        """
        super().__init__(
            provider_name, static_models, cache_ttl, use_cache, force_static
        )
        self.client = client
        self.token = token
        self.base_url = base_url

    async def _fetch_models(self) -> list[Model] | None:
        """Fetch models from GitHub Models API.

        Returns:
            List of discovered models or None on error
        """
        if not self.token:
            return None

        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            }

            response = await self.client.get(f"{self.base_url}/models", headers=headers)

            if response.status_code == 429:
                # Rate limited - extract wait time from headers or response
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    logger.warning(
                        f"GitHub Models API rate limited, retry after {retry_after}s",
                        status_code=429,
                    )
                else:
                    # Try to parse from response body
                    import re

                    match = re.search(r"wait (\d+) seconds", response.text)
                    if match:
                        wait_seconds = int(match.group(1))
                        logger.warning(
                            f"GitHub Models API rate limited, wait {wait_seconds}s",
                            status_code=429,
                        )
                return None

            if response.status_code != 200:
                logger.debug(
                    f"GitHub Models API returned {response.status_code}",
                    response_preview=response.text[:200],
                )
                return None

            data = response.json()

            # Parse the response based on format
            if isinstance(data, list):
                models_data = data
            elif isinstance(data, dict) and "data" in data:
                models_data = data["data"]
            else:
                logger.warning("Unexpected GitHub Models API response format")
                return None

            # Process models from API response
            models = self._process_github_models(models_data)
            return models if models else None

        except Exception as e:
            logger.debug(f"Failed to fetch GitHub Models: {e}")
            return None

    def _process_github_models(self, models_data: list[dict]) -> list[Model]:
        """Process raw model data from GitHub API.

        Args:
            models_data: Raw model data from API

        Returns:
            List of processed Model objects
        """
        from scriptrag.llm.models import LLMProvider

        # Known working model patterns
        supported_patterns = [
            "gpt-4",
            "gpt-3.5",
            "claude",
            "llama",
            "mistral",
            "phi",
            "cohere",
            "embedding",
            "ada",
        ]

        models = []
        for model_info in models_data:
            model_id = model_info.get("id", "")
            name = model_info.get("name") or model_info.get("friendly_name", model_id)

            # Skip if no valid ID
            if not model_id:
                continue

            # Check if model matches supported patterns
            model_id_lower = model_id.lower()
            if not any(pattern in model_id_lower for pattern in supported_patterns):
                logger.debug(f"Skipping unsupported model: {model_id}")
                continue

            # Determine capabilities
            capabilities = []
            if "embedding" in model_id_lower:
                capabilities.append("embedding")
            elif any(
                term in model_id_lower for term in ["gpt", "llama", "claude", "mistral"]
            ):
                capabilities = ["completion", "chat"]

            # Default to chat capabilities if not specified
            if not capabilities:
                capabilities = ["chat"]

            # Extract context window and token limits from metadata
            context_window = model_info.get("context_window", 4096)
            max_output = model_info.get("max_output_tokens", 4096)

            models.append(
                Model(
                    id=model_id,
                    name=name,
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=capabilities,
                    context_window=context_window,
                    max_output_tokens=max_output,
                )
            )

        return models
