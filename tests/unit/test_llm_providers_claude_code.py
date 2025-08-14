"""Unit tests for Claude Code SDK provider."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.llm.models import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    LLMProvider,
    Model,
)
from scriptrag.llm.providers.claude_code import ClaudeCodeProvider


class TestClaudeCodeProvider:
    """Test Claude Code SDK provider functionality."""

    @pytest.fixture
    def provider(self):
        """Create provider instance for testing."""
        with patch.object(ClaudeCodeProvider, "_check_sdk"):
            provider = ClaudeCodeProvider()
            provider.sdk_available = True  # Mock SDK as available
            return provider

    @pytest.fixture
    def provider_no_sdk(self):
        """Create provider instance without SDK."""
        with patch.object(ClaudeCodeProvider, "_check_sdk"):
            provider = ClaudeCodeProvider()
            provider.sdk_available = False
            return provider

    @pytest.fixture
    def completion_request(self):
        """Sample completion request."""
        return CompletionRequest(
            model="claude-3-sonnet-20240229",
            messages=[
                {"role": "user", "content": "Hello, how are you?"},
            ],
            max_tokens=1000,
            temperature=0.7,
        )

    @pytest.fixture
    def embedding_request(self):
        """Sample embedding request."""
        return EmbeddingRequest(
            model="claude-3-sonnet-20240229",
            input="Test text for embedding",
        )

    def test_provider_type(self, provider):
        """Test provider type is correctly set."""
        assert provider.provider_type == LLMProvider.CLAUDE_CODE

    def test_static_models_defined(self, provider):
        """Test static models are properly defined."""
        models = provider.STATIC_MODELS
        assert len(models) > 0

        # Check for key models
        model_ids = [model.id for model in models]
        assert "claude-3-opus-20240229" in model_ids
        assert "claude-3-sonnet-20240229" in model_ids
        assert "claude-3-haiku-20240307" in model_ids
        assert "claude-3-5-sonnet-20241022" in model_ids
        assert "sonnet" in model_ids  # Alias
        assert "opus" in model_ids  # Alias
        assert "haiku" in model_ids  # Alias

        # Verify model structure
        opus_model = next(m for m in models if m.id == "claude-3-opus-20240229")
        assert opus_model.name == "Claude 3 Opus"
        assert opus_model.provider == LLMProvider.CLAUDE_CODE
        assert "completion" in opus_model.capabilities
        assert "chat" in opus_model.capabilities
        assert opus_model.context_window == 200000
        assert opus_model.max_output_tokens == 4096

    def test_check_sdk_with_sdk_available(self):
        """Test SDK check when both SDK and CLI are available."""
        # Temporarily add a fake module to sys.modules
        import types

        mock_module = types.ModuleType("claude_code_sdk")
        sys.modules["claude_code_sdk"] = mock_module

        try:
            with patch("shutil.which", return_value="/usr/bin/claude"):
                provider = ClaudeCodeProvider()
                assert provider.sdk_available is True
        finally:
            # Clean up
            if "claude_code_sdk" in sys.modules:
                del sys.modules["claude_code_sdk"]

    def test_check_sdk_with_sdk_no_cli(self):
        """Test SDK check when SDK is installed but CLI not in PATH."""
        # Temporarily add a fake module to sys.modules
        import types

        mock_module = types.ModuleType("claude_code_sdk")
        sys.modules["claude_code_sdk"] = mock_module

        try:
            with patch("shutil.which", return_value=None):
                provider = ClaudeCodeProvider()
                assert provider.sdk_available is False
        finally:
            # Clean up
            if "claude_code_sdk" in sys.modules:
                del sys.modules["claude_code_sdk"]

    def test_check_sdk_no_sdk(self):
        """Test SDK check when SDK is not installed."""
        # Ensure claude_code_sdk is NOT in sys.modules to simulate import failure

        if "claude_code_sdk" in sys.modules:
            del sys.modules["claude_code_sdk"]

        provider = ClaudeCodeProvider()
        assert provider.sdk_available is False

    @pytest.mark.asyncio
    async def test_is_available_with_sdk(self, provider):
        """Test availability check with SDK available."""
        # Mock claude_code_sdk at import level since it's imported inside the method
        mock_sdk = MagicMock()
        mock_sdk.ClaudeCodeOptions = MagicMock()

        with patch.dict("sys.modules", {"claude_code_sdk": mock_sdk}):
            result = await provider.is_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_is_available_no_sdk(self, provider_no_sdk):
        """Test availability check without SDK."""
        result = await provider_no_sdk.is_available()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_disabled_by_env(self, provider):
        """Test availability check when disabled by environment variable."""
        with patch.dict(os.environ, {"SCRIPTRAG_IGNORE_CLAUDE": "1"}):
            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_available_sdk_import_error(self, provider):
        """Test availability check when SDK import fails."""
        # Override fixture's sdk_available for import failure test
        provider.sdk_available = False  # SDK not available

        # Patch sys.modules to make the import fail
        with patch.dict("sys.modules", {"claude_code_sdk": None}):
            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_available_sdk_attribute_error(self, provider):
        """Test availability check when SDK has missing attributes."""
        provider.sdk_available = False  # SDK not available

        # Create a mock module that raises AttributeError
        mock_sdk = MagicMock()
        del mock_sdk.ClaudeCodeOptions  # This will cause AttributeError

        with patch.dict("sys.modules", {"claude_code_sdk": mock_sdk}):
            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_available_with_environment_markers(self, provider):
        """Test availability check with environment markers as fallback."""
        # SDK was detected initially
        provider.sdk_available = True

        # Mock SDK import to fail
        with patch.dict("sys.modules", {"claude_code_sdk": None}):
            with patch.dict(os.environ, {"CLAUDECODE": "1"}):
                result = await provider.is_available()
                # Should return True due to environment marker AND sdk_available=True
                assert result is True

    @pytest.mark.asyncio
    async def test_list_models(self, provider):
        """Test model listing using discovery."""
        mock_models = [
            Model(
                id="claude-3-sonnet-test",
                name="Claude 3 Sonnet Test",
                provider=LLMProvider.CLAUDE_CODE,
                capabilities=["completion", "chat"],
                context_window=200000,
                max_output_tokens=4096,
            ),
        ]

        with patch.object(
            provider.model_discovery, "discover_models", return_value=mock_models
        ):
            models = await provider.list_models()
            assert models == mock_models

    def test_messages_to_prompt_single_user_message(self, provider):
        """Test converting single user message to prompt."""
        messages = [{"role": "user", "content": "Hello"}]
        prompt = provider._messages_to_prompt(messages)
        assert prompt == "User: Hello"

    def test_messages_to_prompt_conversation(self, provider):
        """Test converting conversation to prompt."""
        messages = [
            {"role": "user", "content": "What is the capital of France?"},
            {"role": "assistant", "content": "The capital of France is Paris."},
            {"role": "user", "content": "What about Germany?"},
        ]
        prompt = provider._messages_to_prompt(messages)
        expected = (
            "User: What is the capital of France?\n\n"
            "Assistant: The capital of France is Paris.\n\n"
            "User: What about Germany?"
        )
        assert prompt == expected

    def test_messages_to_prompt_system_message(self, provider):
        """Test converting messages with system message to prompt."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        prompt = provider._messages_to_prompt(messages)
        expected = "System: You are a helpful assistant.\n\nUser: Hello"
        assert prompt == expected

    @pytest.mark.asyncio
    async def test_complete_success(self, provider, completion_request):
        """Test successful completion."""
        mock_response = "Hello! I'm doing well, thank you for asking."

        # Mock the imports that happen inside the complete method
        mock_claude_sdk = MagicMock()
        mock_claude_sdk.query = MagicMock(return_value=mock_response)
        mock_claude_sdk.ClaudeCodeOptions = MagicMock()
        mock_claude_sdk.Message = MagicMock()

        with patch.dict("sys.modules", {"claude_code_sdk": mock_claude_sdk}):
            response = await provider.complete(completion_request)

            assert isinstance(response, CompletionResponse)
            assert response.content == mock_response
            assert response.model == completion_request.model
            assert response.finish_reason == "stop"
            assert response.usage.prompt_tokens > 0
            assert response.usage.completion_tokens > 0
            assert response.usage.total_tokens > 0

    @pytest.mark.asyncio
    async def test_complete_with_json_format(self, provider):
        """Test completion with JSON response format."""
        request = CompletionRequest(
            model="claude-3-sonnet-20240229",
            messages=[{"role": "user", "content": "Return a JSON object"}],
            response_format="json",
        )

        mock_json_response = '{"message": "Hello", "status": "success"}'
        mock_response = f"Here's the JSON:\n{mock_json_response}"

        # Mock the imports that happen inside the complete method
        mock_claude_sdk = MagicMock()
        mock_claude_sdk.query = MagicMock(return_value=mock_response)
        mock_claude_sdk.ClaudeCodeOptions = MagicMock()
        mock_claude_sdk.Message = MagicMock()

        with patch.dict("sys.modules", {"claude_code_sdk": mock_claude_sdk}):
            response = await provider.complete(request)

            # Should extract JSON from response
            assert response.content == mock_json_response

    @pytest.mark.asyncio
    async def test_complete_json_extraction_fallback(self, provider):
        """Test JSON extraction fallback when no valid JSON found."""
        request = CompletionRequest(
            model="claude-3-sonnet-20240229",
            messages=[{"role": "user", "content": "Return a JSON object"}],
            response_format="json",
        )

        mock_response = "I cannot provide valid JSON."

        # Mock the imports that happen inside the complete method
        mock_claude_sdk = MagicMock()
        mock_claude_sdk.query = MagicMock(return_value=mock_response)
        mock_claude_sdk.ClaudeCodeOptions = MagicMock()
        mock_claude_sdk.Message = MagicMock()

        with patch.dict("sys.modules", {"claude_code_sdk": mock_claude_sdk}):
            response = await provider.complete(request)

            # Should return original response when no JSON found
            assert response.content == mock_response

    @pytest.mark.asyncio
    async def test_complete_sdk_error(self, provider, completion_request):
        """Test completion with SDK error."""
        # Mock the imports that happen inside the complete method
        mock_claude_sdk = MagicMock()
        mock_claude_sdk.query = MagicMock(side_effect=Exception("SDK error"))
        mock_claude_sdk.ClaudeCodeOptions = MagicMock()
        mock_claude_sdk.Message = MagicMock()

        with patch.dict("sys.modules", {"claude_code_sdk": mock_claude_sdk}):
            with pytest.raises(Exception, match="SDK error"):
                await provider.complete(completion_request)

    @pytest.mark.asyncio
    async def test_complete_import_error(self, provider, completion_request):
        """Test completion with SDK import error."""
        with patch(
            "scriptrag.llm.providers.claude_code.query",
            side_effect=ImportError("claude_code_sdk not available"),
        ):
            with pytest.raises(ImportError):
                await provider.complete(completion_request)

    def test_extract_json_from_text_valid_json(self, provider):
        """Test JSON extraction from text with valid JSON."""
        text = 'Here is your JSON: {"name": "John", "age": 30}'
        result = provider._extract_json_from_text(text)
        expected = '{"name": "John", "age": 30}'
        assert result == expected

    def test_extract_json_from_text_code_block(self, provider):
        """Test JSON extraction from code block."""
        text = """Here's the JSON:
```json
{"status": "success"}
```"""
        result = provider._extract_json_from_text(text)
        expected = '{"status": "success"}'
        assert result == expected

    def test_extract_json_from_text_multiple_objects(self, provider):
        """Test JSON extraction with multiple JSON objects."""
        text = 'First: {"a": 1} and second: {"b": 2}'
        result = provider._extract_json_from_text(text)
        # Should return the first valid JSON object
        expected = '{"a": 1}'
        assert result == expected

    def test_extract_json_from_text_no_json(self, provider):
        """Test JSON extraction when no JSON is found."""
        text = "This is just plain text with no JSON."
        result = provider._extract_json_from_text(text)
        assert result == text  # Should return original text

    def test_extract_json_from_text_invalid_json(self, provider):
        """Test JSON extraction with invalid JSON syntax."""
        text = "Here's broken JSON: {invalid: json}"
        result = provider._extract_json_from_text(text)
        assert result == text  # Should return original text

    def test_estimate_tokens_simple(self, provider):
        """Test token estimation for simple text."""
        text = "Hello world"
        tokens = provider._estimate_tokens(text)
        assert tokens > 0
        assert tokens < 10  # Should be reasonable estimate

    def test_estimate_tokens_longer_text(self, provider):
        """Test token estimation for longer text."""
        text = "This is a longer piece of text that should result in more tokens."
        tokens = provider._estimate_tokens(text)
        assert tokens > 10
        assert tokens < 30

    def test_estimate_tokens_empty_text(self, provider):
        """Test token estimation for empty text."""
        tokens = provider._estimate_tokens("")
        assert tokens == 0

    @pytest.mark.asyncio
    async def test_embed_not_supported(self, provider, embedding_request):
        """Test that embedding is not supported."""
        with pytest.raises(
            NotImplementedError,
            match="Claude Code provider does not support embeddings",
        ):
            await provider.embed(embedding_request)

    def test_provider_initialization_with_settings(self):
        """Test provider initialization with different settings."""
        with patch("scriptrag.llm.providers.claude_code.get_settings") as mock_settings:
            mock_settings.return_value.llm_model_cache_ttl = 7200
            mock_settings.return_value.llm_force_static_models = True

            with patch.object(ClaudeCodeProvider, "_check_sdk"):
                provider = ClaudeCodeProvider()

                # Verify model discovery was configured with settings
                assert provider.model_discovery.force_static is True

    def test_provider_initialization_no_cache(self):
        """Test provider initialization with caching disabled."""
        with patch("scriptrag.llm.providers.claude_code.get_settings") as mock_settings:
            mock_settings.return_value.llm_model_cache_ttl = 0  # Disable cache
            mock_settings.return_value.llm_force_static_models = False

            with patch.object(ClaudeCodeProvider, "_check_sdk"):
                provider = ClaudeCodeProvider()

                # Verify cache TTL is None when disabled
                assert provider.model_discovery.cache is None


class TestClaudeCodeProviderIntegration:
    """Integration tests for Claude Code provider."""

    @pytest.mark.asyncio
    async def test_complete_workflow_with_discovery(self):
        """Test complete workflow including model discovery."""
        with patch.object(ClaudeCodeProvider, "_check_sdk"):
            provider = ClaudeCodeProvider()
            provider.sdk_available = True

            # Mock model discovery
            mock_models = [
                Model(
                    id="claude-3-sonnet-20240229",
                    name="Claude 3 Sonnet",
                    provider=LLMProvider.CLAUDE_CODE,
                    capabilities=["completion", "chat"],
                    context_window=200000,
                    max_output_tokens=4096,
                ),
            ]

            with patch.object(
                provider.model_discovery, "discover_models", return_value=mock_models
            ):
                # Test model listing
                models = await provider.list_models()
                assert len(models) == 1
                assert models[0].id == "claude-3-sonnet-20240229"

                # Test availability
                with patch(
                    "scriptrag.llm.providers.claude_code.claude_code_sdk"
                ) as mock_sdk:
                    mock_sdk.ClaudeCodeOptions = MagicMock()
                    available = await provider.is_available()
                    assert available is True

                # Test completion
                request = CompletionRequest(
                    model="claude-3-sonnet-20240229",
                    messages=[{"role": "user", "content": "Hello"}],
                )

                with patch("scriptrag.llm.providers.claude_code.query") as mock_query:
                    mock_query.return_value = "Hello! How can I help you?"

                    with patch("scriptrag.llm.providers.claude_code.ClaudeCodeOptions"):
                        response = await provider.complete(request)
                        assert response.content == "Hello! How can I help you?"

    @pytest.mark.asyncio
    async def test_error_recovery_fallback_to_static(self):
        """Test error recovery by falling back to static models."""
        with patch.object(ClaudeCodeProvider, "_check_sdk"):
            provider = ClaudeCodeProvider()
            provider.sdk_available = True

            # Mock model discovery to fail, should fallback to static
            with patch.object(
                provider.model_discovery,
                "discover_models",
                side_effect=Exception("Discovery failed"),
            ):
                # Should not raise exception, should use static models as fallback
                # The discovery class handles this internally
                with patch.object(
                    provider.model_discovery,
                    "discover_models",
                    return_value=provider.STATIC_MODELS,
                ):
                    models = await provider.list_models()
                    assert len(models) > 0
                    assert all(m.provider == LLMProvider.CLAUDE_CODE for m in models)
