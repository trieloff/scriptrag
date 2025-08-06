"""Factory for creating LLM clients with settings integration."""

import contextlib
import os

from scriptrag.config import get_settings
from scriptrag.utils.llm_client import LLMClient, LLMProvider


def create_llm_client(
    preferred_provider: str | None = None,
    fallback_order: list[str] | None = None,
) -> LLMClient:
    """Create an LLM client using configuration settings.

    Args:
        preferred_provider: Override for preferred provider.
        fallback_order: Override for fallback order.

    Returns:
        Configured LLM client.
    """
    settings = get_settings()

    # Determine preferred provider
    if not preferred_provider:
        preferred_provider = settings.llm_provider

    # Convert string to enum if provided
    provider_enum = None
    if preferred_provider:
        with contextlib.suppress(ValueError):
            # Invalid provider name will use defaults
            provider_enum = LLMProvider(preferred_provider)

    # Set up environment variables from settings if not already set
    if settings.llm_endpoint and not os.getenv("SCRIPTRAG_LLM_ENDPOINT"):
        os.environ["SCRIPTRAG_LLM_ENDPOINT"] = settings.llm_endpoint

    if settings.llm_api_key and not os.getenv("SCRIPTRAG_LLM_API_KEY"):
        os.environ["SCRIPTRAG_LLM_API_KEY"] = settings.llm_api_key

    # Convert fallback order strings to enums
    fallback_enums = None
    if fallback_order:
        fallback_enums = []
        for provider_str in fallback_order:
            try:
                fallback_enums.append(LLMProvider(provider_str))
            except ValueError:
                # Skip invalid provider names
                continue

    # Create client
    return LLMClient(
        preferred_provider=provider_enum,
        fallback_order=fallback_enums,
    )


async def get_default_llm_client() -> LLMClient:
    """Get or create the default LLM client.

    Returns:
        Default LLM client instance.
    """
    # For now, create a new client each time
    # In the future, we might want to cache this
    return create_llm_client()
