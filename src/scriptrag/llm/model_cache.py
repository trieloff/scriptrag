"""Model discovery cache with TTL support."""

import contextlib
import errno
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, ClassVar, TypedDict, cast

from pydantic_core import ValidationError

from scriptrag.config import get_logger
from scriptrag.llm.models import Model

logger = get_logger(__name__)


class CacheData(TypedDict):
    """Type for cache data structure."""

    timestamp: float
    models: list[dict[str, Any]]
    provider: str


class ModelDiscoveryCache:
    """Cache for discovered models with TTL support."""

    DEFAULT_TTL: ClassVar[int] = 3600  # 1 hour default TTL
    CACHE_DIR: ClassVar[Path] = Path.home() / ".cache" / "scriptrag"

    # In-memory cache to avoid repeated file I/O and JSON parsing
    # In-memory cache structure: provider_name -> (timestamp, models[, cache_dir])
    # The optional 3rd element (cache_dir) namespaces the entry by the CACHE_DIR
    # to avoid cross-test contamination when different tests monkeypatch CACHE_DIR.
    _memory_cache: ClassVar[dict[str, tuple]] = {}

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
        """Ensure cache directory exists with restrictive permissions."""
        try:
            # Always attempt to create the directory (idempotent with exist_ok),
            # but only set permissions when it's created the first time.
            existed = self.CACHE_DIR.exists()
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            if not existed:
                # Set restrictive permissions (owner read/write/execute only)
                self.CACHE_DIR.chmod(0o700)
        except OSError as e:
            logger.error(f"Failed to create cache directory: {e}")
            raise

    def get(self) -> list[Model] | None:
        """Get cached models if still valid.

        Returns:
            List of cached models or None if cache is invalid/missing
        """
        # Check in-memory cache first
        if self.provider_name in self._memory_cache:
            entry = self._memory_cache[self.provider_name]
            # Entry shape with namespace: (timestamp, models, cache_dir)
            if isinstance(entry, tuple) and len(entry) == 3:
                timestamp = cast(float, entry[0])
                models = cast(list[Model], entry[1])
                cache_dir = cast(str, entry[2])
                same_namespace = str(Path(cache_dir)) == str(self.CACHE_DIR.resolve())
                if not same_namespace:
                    logger.debug(
                        (
                            "Ignoring in-memory cache for provider "
                            "due to different namespace"
                        ),
                        stored_namespace=cache_dir,
                        current_namespace=str(self.CACHE_DIR.resolve()),
                    )
                elif time.time() - timestamp <= self.ttl:
                    logger.debug(
                        f"Using in-memory cached models for {self.provider_name}",
                        count=len(models),
                        age=int(time.time() - timestamp),
                    )
                    return models
                else:
                    # Expired entry
                    del self._memory_cache[self.provider_name]
                    logger.debug(
                        f"In-memory cache expired for {self.provider_name}",
                        age=int(time.time() - timestamp),
                    )
            else:
                # Backward-compat: older 2-tuple shape (timestamp, models)
                timestamp = cast(float, entry[0])
                models = cast(list[Model], entry[1])
                if time.time() - timestamp <= self.ttl:
                    logger.debug(
                        f"Using in-memory cached models for {self.provider_name}",
                        count=len(models),
                        age=int(time.time() - timestamp),
                    )
                    return models
                # Clear expired in-memory cache
                del self._memory_cache[self.provider_name]
                logger.debug(f"In-memory cache expired for {self.provider_name}")

        # Fall back to file cache
        if not self.cache_file.exists():
            logger.debug(f"No cache file found for {self.provider_name}")
            return None

        try:
            with self.cache_file.open("r") as f:
                cache_data: dict[str, Any] = json.load(f)

            timestamp = cache_data.get("timestamp", 0)
            if time.time() - timestamp > self.ttl:
                logger.debug(
                    f"File cache expired for {self.provider_name}",
                    age=time.time() - timestamp,
                    ttl=self.ttl,
                )
                return None

            models_data: list[dict[str, Any]] = cache_data.get("models", [])
            cached_models: list[Model] = [
                Model(**model_dict) for model_dict in models_data
            ]

            # Store in memory cache for faster subsequent access
            self._memory_cache[self.provider_name] = (
                timestamp,
                cached_models,
                str(self.CACHE_DIR.resolve()),
            )

            logger.info(
                f"Using file cached models for {self.provider_name}",
                count=len(cached_models),
                age=int(time.time() - timestamp),
            )
            return cached_models

        except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as e:
            logger.warning(f"Failed to read cache for {self.provider_name}: {e}")
            return None

    def set(self, models: list[Model]) -> None:
        """Cache models with current timestamp using atomic write operation.

        Args:
            models: List of models to cache
        """
        timestamp = time.time()

        # Update in-memory cache immediately
        self._memory_cache[self.provider_name] = (
            timestamp,
            models,
            str(self.CACHE_DIR.resolve()),
        )

        # Initialize for safe cleanup if temporary file creation fails early
        temp_path: str | None = None
        temp_fd: int | None = None
        try:
            cache_data = {
                "timestamp": timestamp,
                "models": [model.model_dump() for model in models],
                "provider": self.provider_name,
            }

            # Write to a temporary file first (atomic operation)
            # Use the same directory to ensure atomic rename works
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.CACHE_DIR,
                prefix=f".{self.provider_name}_models_",
                suffix=".tmp",
            )

            try:
                # Write data to temp file
                # fdopen takes ownership of the file descriptor
                with os.fdopen(temp_fd, "w") as f:
                    json.dump(cache_data, f, indent=2)
                    # After this point, temp_fd is closed by fdopen's context manager

                # Mark that fd was consumed by fdopen
                temp_fd = None

                # Set restrictive permissions on the temp file
                Path(temp_path).chmod(0o600)

                # Atomic rename (replaces existing file if present)
                Path(temp_path).replace(self.cache_file)

                logger.info(
                    f"Cached {len(models)} models for {self.provider_name}",
                    cache_file=self.cache_file,
                )

            except Exception:

                # Clean up file descriptor if it wasn't consumed by fdopen
                if temp_fd is not None:
                    with contextlib.suppress(OSError):
                        os.close(temp_fd)

                # Clean up temp file if it exists
                if temp_path is not None:
                    with contextlib.suppress(OSError):
                        Path(temp_path).unlink()

                raise

        except OSError as e:
            # Specific handling for disk space and permission issues
            if e.errno == errno.ENOSPC:  # No space left on device
                logger.error(
                    f"Insufficient disk space to cache models for {self.provider_name}"
                )
            elif e.errno == errno.EACCES:  # Permission denied
                logger.error(
                    f"Permission denied when caching models for {self.provider_name}"
                )
            else:
                logger.error(
                    f"OS error when caching models for {self.provider_name}: {e}"
                )
        except Exception as e:
            logger.warning(f"Failed to cache models for {self.provider_name}: {e}")

    def clear(self) -> None:
        """Clear the cache file and in-memory cache."""
        # Clear in-memory cache
        if self.provider_name in self._memory_cache:
            del self._memory_cache[self.provider_name]

        # Clear file cache
        if self.cache_file.exists():
            self.cache_file.unlink()
            logger.debug(f"Cleared cache for {self.provider_name}")

    @classmethod
    def clear_all_memory_cache(cls) -> None:
        """Clear all in-memory cache data across all providers.

        This is particularly useful for testing to prevent cache contamination
        between test runs.
        """
        cls._memory_cache.clear()
        logger.debug("Cleared all in-memory cache data")
