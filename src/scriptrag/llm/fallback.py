"""Fallback logic for multi-provider LLM operations."""

import time
import traceback
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from scriptrag.config import get_logger
from scriptrag.exceptions import LLMFallbackError
from scriptrag.llm.base import BaseLLMProvider
from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMProvider,
)
from scriptrag.llm.registry import ProviderRegistry

logger = get_logger(__name__)

# Type variables for generic request/response handling
T = TypeVar("T", CompletionRequest, EmbeddingRequest)
U = TypeVar("U", CompletionResponse, EmbeddingResponse)


class FallbackHandler:
    """Handles fallback logic for LLM operations across multiple providers."""

    def __init__(
        self,
        registry: ProviderRegistry,
        preferred_provider: LLMProvider | None = None,
        fallback_order: list[LLMProvider] | None = None,
        debug_mode: bool = False,
    ) -> None:
        """Initialize fallback handler.

        Args:
            registry: Provider registry containing available providers.
            preferred_provider: Preferred provider to try first.
            fallback_order: Order of providers to try if preferred fails.
            debug_mode: Enable debug mode for detailed error information.
        """
        self.registry = registry
        self.preferred_provider = preferred_provider
        self.fallback_order = fallback_order or [
            LLMProvider.CLAUDE_CODE,
            LLMProvider.GITHUB_MODELS,
            LLMProvider.OPENAI_COMPATIBLE,
        ]
        self.debug_mode = debug_mode

    async def complete_with_fallback(
        self,
        request: CompletionRequest,
        try_provider_func: Callable[
            [BaseLLMProvider, CompletionRequest], Awaitable[CompletionResponse]
        ],
        record_chain_func: Callable[[list[str]], None],
    ) -> CompletionResponse:
        """Try completion with providers in fallback order.

        Args:
            request: Completion request.
            try_provider_func: Function to try completion with a provider.
            record_chain_func: Function to record fallback chain.

        Returns:
            Completion response from successful provider.

        Raises:
            LLMFallbackError: If all providers fail.
        """
        provider_errors: dict[str, Exception] = {}
        attempted_providers: list[str] = []
        fallback_chain: list[str] = []
        debug_info: dict[str, Any] = {}

        logger.info(
            "Starting LLM completion with fallback strategy",
            preferred_provider=self.preferred_provider.value
            if self.preferred_provider
            else "none",
            fallback_order=[p.value for p in self.fallback_order],
        )

        # Build the complete fallback chain
        if self.preferred_provider:
            fallback_chain.append(self.preferred_provider.value)
        fallback_chain.extend(
            [p.value for p in self.fallback_order if p != self.preferred_provider]
        )

        # Try preferred provider first
        if self.preferred_provider:
            result = await self._try_provider(
                self.preferred_provider,
                request,
                try_provider_func,
                provider_errors,
                attempted_providers,
                debug_info,
                "preferred",
            )
            if result:
                record_chain_func(fallback_chain)
                return result

        # Try fallback providers in order
        for provider_type in self.fallback_order:
            if provider_type == self.preferred_provider:
                logger.debug(
                    f"Skipping {provider_type.value} (already tried as preferred)"
                )
                continue

            result = await self._try_provider(
                provider_type,
                request,
                try_provider_func,
                provider_errors,
                attempted_providers,
                debug_info,
                "fallback",
            )
            if result:
                record_chain_func(fallback_chain)
                return result

        # Record the failed fallback chain
        record_chain_func(fallback_chain)

        # All providers failed - create comprehensive error
        logger.error(
            "All LLM providers failed",
            provider_errors={k: str(v) for k, v in provider_errors.items()},
            attempted_providers=attempted_providers,
            fallback_chain=fallback_chain,
        )

        raise LLMFallbackError(
            message="All LLM providers failed",
            provider_errors=provider_errors,
            attempted_providers=attempted_providers,
            fallback_chain=fallback_chain,
            debug_info=debug_info if self.debug_mode else None,
        )

    async def embed_with_fallback(
        self,
        request: EmbeddingRequest,
        try_provider_func: Callable[
            [BaseLLMProvider, EmbeddingRequest], Awaitable[EmbeddingResponse]
        ],
        record_chain_func: Callable[[list[str]], None],
    ) -> EmbeddingResponse:
        """Try embedding with providers in fallback order.

        Args:
            request: Embedding request.
            try_provider_func: Function to try embedding with a provider.
            record_chain_func: Function to record fallback chain.

        Returns:
            Embedding response from successful provider.

        Raises:
            LLMFallbackError: If all providers fail.
        """
        provider_errors: dict[str, Exception] = {}
        attempted_providers: list[str] = []
        fallback_chain: list[str] = []
        debug_info: dict[str, Any] = {}

        # Build the complete fallback chain
        if self.preferred_provider:
            fallback_chain.append(self.preferred_provider.value)
        fallback_chain.extend(
            [p.value for p in self.fallback_order if p != self.preferred_provider]
        )

        # Try preferred provider first
        if self.preferred_provider:
            result = await self._try_provider(
                self.preferred_provider,
                request,
                try_provider_func,
                provider_errors,
                attempted_providers,
                debug_info,
                "preferred",
            )
            if result:
                record_chain_func(fallback_chain)
                return result

        # Try fallback providers in order
        for provider_type in self.fallback_order:
            if provider_type == self.preferred_provider:
                continue

            result = await self._try_provider(
                provider_type,
                request,
                try_provider_func,
                provider_errors,
                attempted_providers,
                debug_info,
                "fallback",
            )
            if result:
                record_chain_func(fallback_chain)
                return result

        # Record the failed fallback chain
        record_chain_func(fallback_chain)

        # All providers failed - create comprehensive error
        raise LLMFallbackError(
            message="All LLM providers failed for embedding",
            provider_errors=provider_errors,
            attempted_providers=attempted_providers,
            fallback_chain=fallback_chain,
            debug_info=debug_info if self.debug_mode else None,
        )

    async def _try_provider(
        self,
        provider_type: LLMProvider,
        request: T,
        try_func: Callable[[BaseLLMProvider, T], Awaitable[U]],
        provider_errors: dict[str, Exception],
        attempted_providers: list[str],
        debug_info: dict[str, Any],
        provider_role: str,
    ) -> U | None:
        """Try a single provider for an operation.

        Args:
            provider_type: Type of provider to try.
            request: Request object.
            try_func: Function to execute with provider.
            provider_errors: Dictionary to store provider errors.
            attempted_providers: List of attempted provider names.
            debug_info: Dictionary for debug information.
            provider_role: Role of provider (preferred/fallback).

        Returns:
            Response from provider if successful, None otherwise.
        """
        provider = self.registry.get_provider(provider_type)
        if not provider:
            error_msg = (
                f"{provider_role.capitalize()} provider "
                f"{provider_type.value} not found in registry"
            )
            provider_errors[provider_type.value] = RuntimeError(error_msg)
            attempted_providers.append(provider_type.value)
            logger.warning(error_msg)
            return None

        is_available = await provider.is_available()
        provider_name = provider.__class__.__name__
        attempted_providers.append(provider_type.value)

        logger.info(
            f"Checking {provider_role} provider: {provider_name}",
            is_available=is_available,
        )

        if not is_available:
            error_msg = f"Provider {provider_name} not available"
            provider_errors[provider_name] = RuntimeError(error_msg)
            logger.warning(error_msg)
            return None

        try:
            return await try_func(provider, request)
        except Exception as e:
            provider_errors[provider_name] = e
            error_details = {
                "provider": provider_name,
                "error": str(e),
                "error_type": type(e).__name__,
            }

            if self.debug_mode:
                error_details["stack_trace"] = traceback.format_exc()
                debug_info[f"{provider_type.value}_error"] = {
                    "exception": e,
                    "stack_trace": traceback.format_exc(),
                    "timestamp": time.time(),
                }

            logger.warning(
                f"{provider_role.capitalize()} provider failed", **error_details
            )
            return None
