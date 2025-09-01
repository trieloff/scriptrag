"""Model registry for managing static and dynamic model lists."""

from __future__ import annotations

from typing import ClassVar

from scriptrag.llm.models import LLMProvider, Model


class ModelRegistry:
    """Registry for managing model definitions across providers."""

    # GitHub Models static list
    GITHUB_MODELS: ClassVar[list[Model]] = [
        Model(
            id="gpt-4o",
            name="GPT-4o",
            provider=LLMProvider.GITHUB_MODELS,
            capabilities=["chat", "json"],  # Supports JSON schema structured outputs
            context_window=128000,
            max_output_tokens=16384,
        ),
        Model(
            id="gpt-4o-mini",
            name="GPT-4o Mini",
            provider=LLMProvider.GITHUB_MODELS,
            capabilities=["chat"],  # No JSON schema support
            context_window=128000,
            max_output_tokens=16384,
        ),
    ]

    # Claude Code static list - updated with latest models
    CLAUDE_CODE_MODELS: ClassVar[list[Model]] = [
        # Claude 3 models
        Model(
            id="claude-3-opus-20240229",
            name="Claude 3 Opus",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["chat", "json"],  # Claude supports JSON output
            context_window=200000,
            max_output_tokens=4096,
        ),
        Model(
            id="claude-3-sonnet-20240229",
            name="Claude 3 Sonnet",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["chat", "json"],  # Claude supports JSON output
            context_window=200000,
            max_output_tokens=4096,
        ),
        Model(
            id="claude-3-haiku-20240307",
            name="Claude 3 Haiku",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["chat", "json"],  # Claude supports JSON output
            context_window=200000,
            max_output_tokens=4096,
        ),
        # Claude 3.5 models
        Model(
            id="claude-3-5-sonnet-20241022",
            name="Claude 3.5 Sonnet",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["chat", "json"],  # Claude supports JSON output
            context_window=200000,
            max_output_tokens=8192,
        ),
        Model(
            id="claude-3-5-haiku-20241022",
            name="Claude 3.5 Haiku",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["chat", "json"],  # Claude supports JSON output
            context_window=200000,
            max_output_tokens=8192,
        ),
        # Latest Claude models (model aliases)
        Model(
            id="sonnet",
            name="Claude Sonnet (Latest)",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["chat", "json"],  # Claude supports JSON output
            context_window=200000,
            max_output_tokens=8192,
        ),
        Model(
            id="opus",
            name="Claude Opus (Latest)",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["chat", "json"],  # Claude supports JSON output
            context_window=200000,
            max_output_tokens=8192,
        ),
        Model(
            id="haiku",
            name="Claude Haiku (Latest)",
            provider=LLMProvider.CLAUDE_CODE,
            capabilities=["chat", "json"],  # Claude supports JSON output
            context_window=200000,
            max_output_tokens=8192,
        ),
    ]

    # Map Azure registry paths to simple model IDs for GitHub Models
    GITHUB_MODEL_ID_MAP: ClassVar[dict[str, str]] = {
        (
            "azureml://registries/azureml-meta/models/Meta-Llama-3-70B-Instruct/"
            "versions/6"
        ): "Meta-Llama-3-70B-Instruct",
        (
            "azureml://registries/azureml-meta/models/Meta-Llama-3-8B-Instruct/"
            "versions/6"
        ): "Meta-Llama-3-8B-Instruct",
        (
            "azureml://registries/azureml-meta/models/Meta-Llama-3.1-405B-Instruct/"
            "versions/1"
        ): "Meta-Llama-3.1-405B-Instruct",
        (
            "azureml://registries/azureml-meta/models/Meta-Llama-3.1-70B-Instruct/"
            "versions/1"
        ): "Meta-Llama-3.1-70B-Instruct",
        (
            "azureml://registries/azureml-meta/models/Meta-Llama-3.1-8B-Instruct/"
            "versions/1"
        ): "Meta-Llama-3.1-8B-Instruct",
        "azureml://registries/azure-openai/models/gpt-4o-mini/versions/1": (
            "gpt-4o-mini"
        ),
        "azureml://registries/azure-openai/models/gpt-4o/versions/2": "gpt-4o",
    }

    @classmethod
    def get_static_models(cls, provider: LLMProvider) -> list[Model]:
        """Get static model list for a provider.

        Args:
            provider: The LLM provider

        Returns:
            List of static models for the provider
        """
        if provider == LLMProvider.GITHUB_MODELS:
            return cls.GITHUB_MODELS
        if provider == LLMProvider.CLAUDE_CODE:
            return cls.CLAUDE_CODE_MODELS
        return []
