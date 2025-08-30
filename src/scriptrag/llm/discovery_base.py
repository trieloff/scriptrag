"""Base class for model discovery implementations."""

from __future__ import annotations

from scriptrag.config import get_logger
from scriptrag.llm.model_cache import ModelDiscoveryCache
from scriptrag.llm.models import Model

logger = get_logger(__name__)


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

                # If discovery returned fewer models than static list,
                # supplement with static models. This ensures fallback when
                # API only returns subset of expected models
                if self.static_models and len(models) < len(self.static_models):
                    logger.info(
                        f"Discovery returned {len(models)} models, "
                        "supplementing with static models",
                        static_count=len(self.static_models),
                    )
                    # Create combined list preserving static model order
                    # Start with static models, then replace with
                    # discovered versions where available
                    discovered_by_id = {m.id: m for m in models}
                    combined_models = []

                    for static_model in self.static_models:
                        if static_model.id in discovered_by_id:
                            # Use discovered version (may have different metadata)
                            combined_models.append(discovered_by_id[static_model.id])
                        else:
                            # Use static version
                            combined_models.append(static_model)

                    models = combined_models
                    logger.info(
                        f"Combined model list has {len(models)} models in static order",
                        discovered_count=len(discovered_by_id),
                        static_supplemented=len(self.static_models)
                        - len(discovered_by_id),
                    )

                # Cache the final model list
                if self.cache:
                    self.cache.set(models)
                return models

        except Exception as e:
            logger.warning(
                f"Dynamic discovery failed for {self.provider_name}: {e}",
                fallback_count=len(self.static_models) if self.static_models else 0,
            )

        # Fall back to static models
        fallback_models = self.static_models or []
        logger.info(
            f"Using static models for {self.provider_name}",
            count=len(fallback_models),
        )
        # Cache static models too (to avoid repeated failed attempts)
        if self.cache and fallback_models:
            self.cache.set(fallback_models)
        return fallback_models

    async def _fetch_models(self) -> list[Model] | None:
        """Fetch models from the provider's API.

        This should be overridden by specific implementations.

        Returns:
            List of discovered models or None if not implemented
        """
        return None
