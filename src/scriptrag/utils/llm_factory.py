"""Factory for creating LLM clients with settings integration."""

import contextlib
import os

from scriptrag.config import get_settings
from scriptrag.llm import LLMClient, LLMProvider


def create_llm_client(
    preferred_provider: str | None = None,
    fallback_order: list[str] | None = None,
    github_token: str | None = None,
    openai_endpoint: str | None = None,
    openai_api_key: str | None = None,
    timeout: float = 30.0,
) -> LLMClient:
    """Create an LLM client using configuration settings.

    Args:
        preferred_provider: Override for preferred provider.
        fallback_order: Override for fallback order.
        github_token: GitHub token for GitHub Models provider.
        openai_endpoint: Endpoint URL for OpenAI-compatible provider.
        openai_api_key: API key for OpenAI-compatible provider.
        timeout: Default timeout for HTTP requests.

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

    # Use provided credentials or fall back to settings/env vars
    # Note: We pass credentials directly to the client instead of
    # modifying os.environ to avoid exposing them to other processes
    github_token = github_token or os.getenv("GITHUB_TOKEN")
    openai_endpoint = (
        openai_endpoint or settings.llm_endpoint or os.getenv("SCRIPTRAG_LLM_ENDPOINT")
    )
    openai_api_key = (
        openai_api_key or settings.llm_api_key or os.getenv("SCRIPTRAG_LLM_API_KEY")
    )

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

    # Create client with credentials passed directly
    return LLMClient(
        preferred_provider=provider_enum,
        fallback_order=fallback_enums,
        github_token=github_token,
        openai_endpoint=openai_endpoint,
        openai_api_key=openai_api_key,
        timeout=timeout,
    )


async def get_default_llm_client() -> LLMClient:
    """Get or create the default LLM client.

    Returns:
        Default LLM client instance.
    """
    # For now, create a new client each time
    # In the future, we might want to cache this
    return create_llm_client()
