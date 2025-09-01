"""Tests for LLM model capability-based selection."""

import pytest

from scriptrag.llm import (
    CompletionRequest,
    CompletionResponse,
    LLMClient,
    LLMProvider,
    Model,
)
from scriptrag.llm.base import BaseLLMProvider
from scriptrag.llm.model_registry import ModelRegistry
from scriptrag.llm.registry import ProviderRegistry


class MockProviderWithCapabilities(BaseLLMProvider):
    """Mock provider with configurable model capabilities."""

    def __init__(self, models: list[Model]):
        self.models = models
        self.provider_type = LLMProvider.GITHUB_MODELS

    async def is_available(self) -> bool:
        return True

    async def list_models(self) -> list[Model]:
        return self.models

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            id="test",
            model=request.model,
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "test"},
                    "finish_reason": "stop",
                }
            ],
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            provider=self.provider_type,
        )

    async def embed(self, request):
        raise NotImplementedError("Not needed for this test")


@pytest.mark.asyncio
async def test_static_model_capabilities():
    """Test that static models have correct capabilities defined."""
    # Test GitHub Models
    gpt4o = next((m for m in ModelRegistry.GITHUB_MODELS if m.id == "gpt-4o"), None)
    assert gpt4o is not None
    assert "chat" in gpt4o.capabilities
    assert "json" in gpt4o.capabilities, "GPT-4o should support JSON schema"

    gpt4o_mini = next(
        (m for m in ModelRegistry.GITHUB_MODELS if m.id == "gpt-4o-mini"), None
    )
    assert gpt4o_mini is not None
    assert "chat" in gpt4o_mini.capabilities
    assert "json" not in gpt4o_mini.capabilities, (
        "GPT-4o-mini should NOT support JSON schema"
    )

    # Test Claude Code models
    for model in ModelRegistry.CLAUDE_CODE_MODELS:
        assert "chat" in model.capabilities
        assert "json" in model.capabilities, (
            f"Claude model {model.id} should support JSON"
        )


@pytest.mark.asyncio
async def test_capability_based_model_selection():
    """Test that model selection respects capability requirements."""
    # Create test models with different capabilities
    test_models = [
        Model(
            id="chat-only",
            name="Chat Only Model",
            provider=LLMProvider.GITHUB_MODELS,
            capabilities=["chat"],
        ),
        Model(
            id="chat-json",
            name="Chat + JSON Model",
            provider=LLMProvider.GITHUB_MODELS,
            capabilities=["chat", "json"],
        ),
        Model(
            id="embeddings-only",
            name="Embeddings Model",
            provider=LLMProvider.GITHUB_MODELS,
            capabilities=["embeddings"],
        ),
    ]

    provider = MockProviderWithCapabilities(test_models)
    client = LLMClient()

    # Test 1: Select model for chat only
    selected = await client._select_best_model(provider, ["chat"])
    assert selected == "chat-only", "Should select first chat-capable model"

    # Test 2: Select model for JSON capability
    selected = await client._select_best_model(provider, ["json"])
    assert selected == "chat-json", "Should select JSON-capable model"

    # Test 3: Select model for chat + JSON
    selected = await client._select_best_model(provider, ["chat", "json"])
    assert selected == "chat-json", "Should select model with both capabilities"

    # Test 4: Fallback when capability not found
    selected = await client._select_best_model(provider, ["video"])
    assert selected == "chat-only", (
        "Should fallback to first model when capability not found"
    )


@pytest.mark.asyncio
async def test_automatic_json_capability_detection():
    """Test that JSON capability is automatically detected from request."""
    # Create test models
    test_models = [
        Model(
            id="chat-only",
            name="Chat Only",
            provider=LLMProvider.GITHUB_MODELS,
            capabilities=["chat"],
        ),
        Model(
            id="chat-json",
            name="Chat + JSON",
            provider=LLMProvider.GITHUB_MODELS,
            capabilities=["chat", "json"],
        ),
    ]

    provider = MockProviderWithCapabilities(test_models)

    # Create registry and client
    registry = ProviderRegistry()
    registry.providers[LLMProvider.GITHUB_MODELS] = provider

    client = LLMClient(
        preferred_provider=LLMProvider.GITHUB_MODELS,
        registry=registry,
    )

    # Test with JSON response format - should select JSON-capable model
    request_with_json = CompletionRequest(
        model="",  # Auto-select
        messages=[{"role": "user", "content": "test"}],
        response_format={"type": "json_object", "schema": {"type": "object"}},
    )

    response = await client.complete(request_with_json)
    assert response.model == "chat-json", (
        "Should auto-select JSON-capable model for structured output"
    )

    # Test without JSON format - should select first chat model
    request_without_json = CompletionRequest(
        model="",  # Auto-select
        messages=[{"role": "user", "content": "test"}],
    )

    response = await client.complete(request_without_json)
    assert response.model == "chat-only", (
        "Should select first chat model when JSON not needed"
    )


@pytest.mark.asyncio
async def test_json_capability_fallback():
    """Test fallback behavior when JSON capability is requested but not available."""
    # Create models without JSON capability
    test_models = [
        Model(
            id="chat-model-1",
            name="Chat Model 1",
            provider=LLMProvider.GITHUB_MODELS,
            capabilities=["chat"],
        ),
        Model(
            id="chat-model-2",
            name="Chat Model 2",
            provider=LLMProvider.GITHUB_MODELS,
            capabilities=["chat"],
        ),
    ]

    provider = MockProviderWithCapabilities(test_models)
    client = LLMClient()

    # Request JSON capability when no model supports it
    selected = await client._select_best_model(provider, ["chat", "json"])

    # Should fallback to a chat model with a warning
    assert selected == "chat-model-1", (
        "Should fallback to chat model when JSON not available"
    )


@pytest.mark.asyncio
async def test_capability_caching():
    """Test that model selection results are cached."""
    test_models = [
        Model(
            id="model-1",
            name="Model 1",
            provider=LLMProvider.GITHUB_MODELS,
            capabilities=["chat"],
        ),
    ]

    provider = MockProviderWithCapabilities(test_models)
    client = LLMClient()

    # First call should populate cache
    selected1 = await client._select_best_model(provider, ["chat"])
    assert selected1 == "model-1"

    # Clear the models to simulate provider unavailable
    provider.models = []

    # Second call should use cache
    selected2 = await client._select_best_model(provider, ["chat"])
    assert selected2 == "model-1", "Should use cached result"

    # Different capabilities should not use cache
    selected3 = await client._select_best_model(provider, ["embeddings"])
    assert selected3 is None, "Different capabilities should not use cache"
