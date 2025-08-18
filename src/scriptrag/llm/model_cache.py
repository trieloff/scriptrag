"""Model discovery cache with TTL support."""

import json
import time
from pathlib import Path
from typing import Any, ClassVar

from pydantic_core import ValidationError

from scriptrag.config import get_logger
from scriptrag.llm.models import Model

logger = get_logger(__name__)


class CacheData:
    """Type for cache data structure."""

    timestamp: float
    models: list[dict[str, Any]]
    provider: str


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
                cache_data: dict[str, Any] = json.load(f)

            timestamp = cache_data.get("timestamp", 0)
            if time.time() - timestamp > self.ttl:
                logger.debug(
                    f"Cache expired for {self.provider_name}",
                    age=time.time() - timestamp,
                    ttl=self.ttl,
                )
                return None

            models_data: list[dict[str, Any]] = cache_data.get("models", [])
            models: list[Model] = [Model(**model_dict) for model_dict in models_data]

            logger.info(
                f"Using cached models for {self.provider_name}",
                count=len(models),
                age=int(time.time() - timestamp),
            )
            return models

        except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as e:
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
