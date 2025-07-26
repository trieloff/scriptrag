"""Factory functions for creating LLM clients."""

from scriptrag.config import get_settings

from .client import LLMClient


def create_llm_client(
    endpoint: str | None = None,
    api_key: str | None = None,
    default_chat_model: str | None = None,
    default_embedding_model: str | None = None,
) -> LLMClient:
    """Create an LLM client with default configuration.

    Args:
        endpoint: API endpoint URL. Defaults to config value.
        api_key: API key. Defaults to config value.
        default_chat_model: Default model for chat completions.
        default_embedding_model: Default model for embeddings.

    Returns:
        Configured LLMClient instance.
    """
    settings = get_settings()

    return LLMClient(
        endpoint=endpoint or settings.llm_endpoint,
        api_key=api_key or settings.llm_api_key,
        default_chat_model=default_chat_model,
        default_embedding_model=default_embedding_model,
    )
