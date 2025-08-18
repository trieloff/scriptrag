"""Dynamic model discovery with caching for LLM providers."""

import os
from typing import Any

from scriptrag.config import get_logger
from scriptrag.llm.discovery_base import ModelDiscovery
from scriptrag.llm.models import LLMProvider, Model

logger = get_logger(__name__)


class ClaudeCodeModelDiscovery(ModelDiscovery):
    """Model discovery for Claude Code provider."""

    async def _fetch_models(self) -> list[Model] | None:
        """Fetch models from Claude Code SDK or Anthropic API.

        Attempts to discover available models through:
        1. Claude Code SDK (if it adds model enumeration in the future)
        2. Anthropic API /v1/models endpoint (if API key is available)

        Returns None if model discovery is not available.
        """
        # Try Claude Code SDK first (currently doesn't support model enumeration)
        try:
            from claude_code_sdk import ClaudeSDKClient

            client = ClaudeSDKClient()

            # Check if SDK has model enumeration (not available as of v0.0.20)
            # Check for list_models method (most likely interface if added)
            if hasattr(client, "list_models") and callable(client.list_models):
                logger.info("Using Claude SDK list_models method")
                models_data = await client.list_models()
                return self._parse_claude_models(models_data)

            # Check for models attribute (alternative interface)
            if hasattr(client, "models") and client.models is not None:
                logger.info("Using Claude SDK models attribute")
                return self._parse_claude_models(client.models)

        except ImportError:
            logger.debug("Claude Code SDK not available")
        except Exception as e:
            logger.debug(f"Error checking Claude Code SDK: {e}")

        # Try Anthropic API models endpoint if API key is available
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            return await self._fetch_from_anthropic_api(api_key)

        logger.debug("No model discovery available - using static models")
        return None

    async def _fetch_from_anthropic_api(self, api_key: str) -> list[Model] | None:
        """Fetch models from Anthropic API /v1/models endpoint.

        Args:
            api_key: Anthropic API key

        Returns:
            List of models from API or None on error
        """
        try:
            import httpx

            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers=headers,
                    timeout=10.0,
                )

                if response.status_code != 200:
                    logger.debug(
                        f"Anthropic models endpoint returned {response.status_code}"
                    )
                    return None

                data = response.json()
                models_list = data.get("data", [])

                if not models_list:
                    return None

                return self._parse_anthropic_models(models_list)

        except ImportError:
            logger.debug("httpx not available for Anthropic API calls")
            return None
        except Exception as e:
            logger.debug(f"Failed to fetch models from Anthropic API: {e}")
            return None

    def _parse_anthropic_models(
        self, models_data: list[dict[str, Any]]
    ) -> list[Model] | None:
        """Parse model data from Anthropic API into Model objects.

        Args:
            models_data: Raw model data from Anthropic API

        Returns:
            List of Model objects or None if parsing fails
        """
        if not models_data:
            return None

        try:
            models = []
            for model_info in models_data:
                model_id = model_info.get("id")
                if not model_id:
                    continue

                # Extract display name or use ID
                name = model_info.get("display_name") or model_id

                # Default capabilities for Claude models
                capabilities = ["completion", "chat"]

                # Default context window and output tokens for Claude models
                # These may need adjustment based on actual API response
                context_window = 200000
                max_output = 8192

                # Adjust for specific model types if needed
                if "haiku" in model_id.lower() or "opus" in model_id.lower():
                    max_output = 4096

                models.append(
                    Model(
                        id=model_id,
                        name=name,
                        provider=LLMProvider.CLAUDE_CODE,
                        capabilities=capabilities,
                        context_window=context_window,
                        max_output_tokens=max_output,
                    )
                )

            return models if models else None

        except Exception as e:
            logger.warning(f"Failed to parse Anthropic models data: {e}")
            return None

    def _parse_claude_models(self, models_data: Any) -> list[Model] | None:
        """Parse model data from Claude SDK into Model objects.

        This method is retained for future compatibility if the Claude Code SDK
        adds model enumeration support.

        Args:
            models_data: Raw model data from SDK

        Returns:
            List of Model objects or None if parsing fails
        """
        if not models_data:
            return None

        try:
            models = []

            # Handle list format (most likely format from SDK)
            if isinstance(models_data, list):
                for model_info in models_data:
                    if isinstance(model_info, dict):
                        model_id = model_info.get("id") or model_info.get("model_id")
                        if model_id:
                            models.append(
                                Model(
                                    id=model_id,
                                    name=model_info.get("name") or model_id,
                                    provider=LLMProvider.CLAUDE_CODE,
                                    capabilities=model_info.get(
                                        "capabilities", ["completion", "chat"]
                                    ),
                                    context_window=model_info.get(
                                        "context_window", 200000
                                    ),
                                    max_output_tokens=model_info.get(
                                        "max_tokens", 8192
                                    ),
                                )
                            )

            # Handle dict format (models attribute might return dict)
            elif isinstance(models_data, dict):
                for model_id, model_info in models_data.items():
                    if isinstance(model_info, dict):
                        name = model_info.get("name") or model_id
                        capabilities = model_info.get(
                            "capabilities", ["completion", "chat"]
                        )
                        context_window = model_info.get("context_window", 200000)
                        max_output = model_info.get("max_tokens", 8192)
                    else:
                        # Simple value, use defaults
                        name = model_id
                        capabilities = ["completion", "chat"]
                        context_window = 200000
                        max_output = 8192

                    models.append(
                        Model(
                            id=model_id,
                            name=name,
                            provider=LLMProvider.CLAUDE_CODE,
                            capabilities=capabilities,
                            context_window=context_window,
                            max_output_tokens=max_output,
                        )
                    )

            return models if models else None

        except Exception as e:
            logger.warning(f"Failed to parse Claude SDK models data: {e}")
            return None


class GitHubModelsDiscovery(ModelDiscovery):
    """Model discovery for GitHub Models provider."""

    def __init__(
        self,
        provider_name: str,
        static_models: list[Model],
        client: Any,  # HTTP client with async get method
        token: str | None,
        base_url: str,
        model_id_map: dict[str, str] | None = None,
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
            model_id_map: Optional mapping from Azure registry IDs to simple IDs
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
        self.model_id_map = model_id_map or {}

    async def _fetch_models(self) -> list[Model] | None:
        """Fetch models from GitHub Models API.

        Returns:
            List of discovered models or None on error
        """
        if not self.token:
            return None

        try:
            headers: dict[str, str] = {
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

            data: dict[str, Any] | list[Any] = response.json()

            # Parse the response based on format
            models_data: list[dict[str, Any]]
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

    def _process_github_models(self, models_data: list[dict[str, Any]]) -> list[Model]:
        """Process raw model data from GitHub API.

        Args:
            models_data: Raw model data from API

        Returns:
            List of processed Model objects
        """
        # Known working model patterns
        supported_patterns: list[str] = [
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

        models: list[Model] = []
        for model_info in models_data:
            model_id: str = model_info.get("id", "")
            name: str = model_info.get("name") or model_info.get(
                "friendly_name", model_id
            )

            # Skip if no valid ID
            if not model_id:
                continue

            # Check if model matches supported patterns
            model_id_lower: str = model_id.lower()
            if not any(pattern in model_id_lower for pattern in supported_patterns):
                logger.debug(f"Skipping unsupported model: {model_id}")
                continue

            # Determine capabilities
            capabilities: list[str] = []
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
            context_window: int = model_info.get("context_window", 4096)
            max_output: int = model_info.get("max_output_tokens", 4096)

            # Use mapped ID if available, otherwise use original ID
            final_model_id = self.model_id_map.get(model_id, model_id)

            models.append(
                Model(
                    id=final_model_id,
                    name=name,
                    provider=LLMProvider.GITHUB_MODELS,
                    capabilities=capabilities,
                    context_window=context_window,
                    max_output_tokens=max_output,
                )
            )

        return models
