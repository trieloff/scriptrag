"""Tests for Claude Code SDK provider."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from scriptrag.llm.models import CompletionRequest, EmbeddingRequest, LLMProvider
from scriptrag.llm.providers.claude_code import ClaudeCodeProvider


class TestClaudeCodeProvider:
    """Test Claude Code SDK provider."""

    @pytest.fixture
    def provider(self) -> ClaudeCodeProvider:
        """Create provider instance."""
        with patch.object(ClaudeCodeProvider, "_check_sdk"):
            provider = ClaudeCodeProvider()
            provider.sdk_available = True
            return provider

    def test_provider_type(self, provider: ClaudeCodeProvider) -> None:
        """Test provider type."""
        assert provider.provider_type == LLMProvider.CLAUDE_CODE

    def test_init_checks_sdk(self) -> None:
        """Test that initialization checks SDK availability."""
        with patch.object(ClaudeCodeProvider, "_check_sdk") as mock_check:
            ClaudeCodeProvider()
            mock_check.assert_called_once()

    @patch("shutil.which")
    def test_check_sdk_with_executable(self, mock_which: Mock) -> None:
        """Test SDK check when executable is available."""
        mock_which.return_value = "/usr/local/bin/claude"

        with patch("builtins.__import__") as mock_import:
            provider = ClaudeCodeProvider()
            assert provider.sdk_available is True
            # Check that claude_code_sdk was imported
            assert any(
                call[0][0] == "claude_code_sdk" for call in mock_import.call_args_list
            )

    @patch(
        "builtins.__import__",
        side_effect=ImportError("No module named 'claude_code_sdk'"),
    )
    def test_check_sdk_without_import(self, mock_import: Mock) -> None:  # noqa: ARG002
        """Test SDK check when import fails."""
        provider = ClaudeCodeProvider()
        assert provider.sdk_available is False

    @pytest.mark.asyncio
    async def test_is_available_with_ignore_env(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test availability check with ignore environment variable."""
        with patch.dict(os.environ, {"SCRIPTRAG_IGNORE_CLAUDE": "1"}):
            assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_without_sdk(self) -> None:
        """Test availability when SDK is not available."""
        provider = ClaudeCodeProvider()
        provider.sdk_available = False
        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_with_sdk_import(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test availability when SDK can be imported."""
        with patch("claude_code_sdk.ClaudeCodeOptions"):
            assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_with_sdk_import_error(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test availability when SDK import fails."""
        with (
            patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'claude_code_sdk'"),
            ),
            patch.dict(os.environ, {"CLAUDECODE": "1"}),
        ):
            # Should be True because sdk_available is True (from fixture)
            # AND environment marker is set
            assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_with_environment_markers(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test availability with environment markers."""
        with patch(
            "builtins.__import__",
            side_effect=ImportError("No module named 'claude_code_sdk'"),
        ):
            with patch.dict(os.environ, {"CLAUDECODE": "1"}):
                assert await provider.is_available() is True

            with patch.dict(os.environ, {"CLAUDE_CODE_SESSION": "session123"}):
                assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_with_sdk_exception(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test availability when SDK check raises exception."""
        with (
            patch(
                "builtins.__import__",
                side_effect=Exception("Unexpected error"),
            ),
            patch.dict(os.environ, {"CLAUDECODE": "1"}),
        ):
            # Falls back to environment markers - True because sdk_available
            # is True AND environment marker is set
            assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_list_models(self, provider: ClaudeCodeProvider) -> None:
        """Test listing available models."""
        models = await provider.list_models()
        assert len(models) == 3
        assert all(m.provider == LLMProvider.CLAUDE_CODE for m in models)
        assert any("opus" in m.id for m in models)
        assert any("sonnet" in m.id for m in models)
        assert any("haiku" in m.id for m in models)

    @pytest.mark.asyncio
    async def test_embed_not_implemented(self, provider: ClaudeCodeProvider) -> None:
        """Test that embed raises NotImplementedError."""
        request = EmbeddingRequest(model="claude-3-opus", input="test text")
        with pytest.raises(NotImplementedError):
            await provider.embed(request)

    def test_messages_to_prompt(self, provider: ClaudeCodeProvider) -> None:
        """Test converting messages to prompt."""
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]

        prompt = provider._messages_to_prompt(messages)
        assert "System: You are helpful" in prompt
        assert "User: Hello" in prompt
        assert "Assistant: Hi there" in prompt
        assert "User: How are you?" in prompt
        # System should be first
        assert prompt.startswith("System: You are helpful")

    def test_messages_to_prompt_no_system(self, provider: ClaudeCodeProvider) -> None:
        """Test converting messages without system message."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        prompt = provider._messages_to_prompt(messages)
        assert prompt == "User: Hello\n\nAssistant: Hi"

    def test_extract_schema_info_json_schema(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test extracting schema from OpenAI-style format."""
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "test_response",
                "schema": {
                    "type": "object",
                    "properties": {"result": {"type": "string"}},
                },
            },
        }

        schema_info = provider._extract_schema_info(response_format)
        assert schema_info is not None
        assert schema_info["name"] == "test_response"
        assert "properties" in schema_info["schema"]

    def test_extract_schema_info_json_object(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test extracting schema for simple json_object type."""
        response_format = {"type": "json_object"}

        schema_info = provider._extract_schema_info(response_format)
        assert schema_info is not None
        assert schema_info["name"] == "response"
        assert schema_info["schema"] == {}

    def test_extract_schema_info_direct_schema(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test extracting direct schema format."""
        response_format = {
            "name": "my_response",
            "schema": {
                "type": "object",
                "properties": {"value": {"type": "number"}},
            },
        }

        schema_info = provider._extract_schema_info(response_format)
        assert schema_info is not None
        assert schema_info["name"] == "my_response"
        assert "properties" in schema_info["schema"]

    def test_extract_schema_info_none(self, provider: ClaudeCodeProvider) -> None:
        """Test extracting schema with no format."""
        assert provider._extract_schema_info(None) is None
        assert provider._extract_schema_info({}) is None

    def test_add_json_instructions(self, provider: ClaudeCodeProvider) -> None:
        """Test adding JSON instructions to prompt."""
        prompt = "Generate a response"
        schema_info = {
            "name": "response",
            "schema": {
                "type": "object",
                "properties": {
                    "result": {
                        "type": "string",
                        "description": "The result",
                    },
                    "count": {"type": "integer"},
                },
                "required": ["result"],
            },
        }

        modified = provider._add_json_instructions(prompt, schema_info)
        assert "IMPORTANT: You must respond with valid JSON" in modified
        assert "result (string) [REQUIRED]: The result" in modified
        assert "count (integer)" in modified
        assert "Example JSON structure:" in modified

    def test_generate_example_from_schema(self, provider: ClaudeCodeProvider) -> None:
        """Test generating example from schema."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "active": {"type": "boolean"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "metadata": {"type": "object"},
            },
        }

        example = provider._generate_example_from_schema(schema)
        assert example is not None
        assert example["name"] == ""
        assert example["age"] == 0
        assert example["active"] is False
        assert example["tags"] == []
        assert example["metadata"] == {}

    def test_generate_example_complex_array(self, provider: ClaudeCodeProvider) -> None:
        """Test generating example with complex array items."""
        schema = {
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                    },
                }
            }
        }

        example = provider._generate_example_from_schema(schema)
        assert example is not None
        assert len(example["items"]) == 1
        assert example["items"][0] == {"id": ""}

    def test_generate_object_example(self, provider: ClaudeCodeProvider) -> None:
        """Test generating object example."""
        obj_schema = {
            "properties": {
                "field1": {"type": "string"},
                "field2": {"type": "number"},
                "field3": {"type": "boolean"},
                "field4": {"type": "array"},
                "field5": {"type": "object"},
            }
        }

        example = provider._generate_object_example(obj_schema)
        assert example["field1"] == ""
        assert example["field2"] == 0
        assert example["field3"] is False
        assert example["field4"] == []
        assert example["field5"] == {}

    def test_generate_object_example_empty(self, provider: ClaudeCodeProvider) -> None:
        """Test generating object example with no properties."""
        example = provider._generate_object_example({})
        assert example == {}

    @pytest.mark.asyncio
    async def test_complete_basic(self, provider: ClaudeCodeProvider) -> None:
        """Test basic completion."""
        # Mock the SDK components
        mock_message = MagicMock()
        mock_message.__class__.__name__ = "AssistantMessage"
        mock_text_block = MagicMock()
        mock_text_block.text = "Test response"
        mock_message.content = [mock_text_block]

        async def mock_query(prompt: str, options: object) -> AsyncMock:  # noqa: ARG001
            yield mock_message

        with (
            patch("claude_code_sdk.query", mock_query),
            patch("claude_code_sdk.ClaudeCodeOptions"),
        ):
            request = CompletionRequest(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Hello"}],
            )

            response = await provider.complete(request)
            assert response.model == "claude-3-opus"
            assert response.choices[0]["message"]["content"] == "Test response"
            assert response.provider == LLMProvider.CLAUDE_CODE

    @pytest.mark.asyncio
    async def test_complete_with_system(self, provider: ClaudeCodeProvider) -> None:
        """Test completion with system prompt."""
        mock_message = MagicMock()
        mock_message.__class__.__name__ = "AssistantMessage"
        mock_text_block = MagicMock()
        mock_text_block.text = "Response with system"
        mock_message.content = [mock_text_block]

        captured_options = None

        async def mock_query(prompt: str, options: object) -> AsyncMock:  # noqa: ARG001
            nonlocal captured_options
            captured_options = options
            yield mock_message

        with (
            patch("claude_code_sdk.query", mock_query),
            patch("claude_code_sdk.ClaudeCodeOptions") as mock_options,
        ):
            request = CompletionRequest(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Hello"}],
                system="You are helpful",
            )

            response = await provider.complete(request)
            assert response.choices[0]["message"]["content"] == "Response with system"
            # Check that system prompt was passed to options
            mock_options.assert_called_with(
                max_turns=1, system_prompt="You are helpful"
            )

    @pytest.mark.asyncio
    async def test_complete_fallback_to_result_message(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test completion falling back to ResultMessage."""
        mock_message = MagicMock()
        mock_message.__class__.__name__ = "ResultMessage"
        mock_message.result = "Result text"

        async def mock_query(prompt: str, options: object) -> AsyncMock:  # noqa: ARG001
            yield mock_message

        with (
            patch("claude_code_sdk.query", mock_query),
            patch("claude_code_sdk.ClaudeCodeOptions"),
        ):
            request = CompletionRequest(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Hello"}],
            )

            response = await provider.complete(request)
            assert response.choices[0]["message"]["content"] == "Result text"

    @pytest.mark.asyncio
    async def test_complete_with_json_response_format(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test completion with JSON response format."""
        # Return valid JSON
        mock_message = MagicMock()
        mock_message.__class__.__name__ = "AssistantMessage"
        mock_text_block = MagicMock()
        mock_text_block.text = '{"result": "success", "value": 42}'
        mock_message.content = [mock_text_block]

        async def mock_query(prompt: str, options: object) -> AsyncMock:  # noqa: ARG001
            yield mock_message

        with (
            patch("claude_code_sdk.query", mock_query),
            patch("claude_code_sdk.ClaudeCodeOptions"),
        ):
            request = CompletionRequest(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Generate JSON"}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "result": {"type": "string"},
                                "value": {"type": "integer"},
                            },
                            "required": ["result"],
                        }
                    },
                },
            )

            response = await provider.complete(request)
            content = response.choices[0]["message"]["content"]
            assert json.loads(content) == {"result": "success", "value": 42}

    @pytest.mark.asyncio
    async def test_complete_json_in_code_block(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test extracting JSON from markdown code block."""
        mock_message = MagicMock()
        mock_message.__class__.__name__ = "AssistantMessage"
        mock_text_block = MagicMock()
        mock_text_block.text = (
            'Here is the JSON:\n```json\n{"result": "extracted"}\n```\n'
        )
        mock_message.content = [mock_text_block]

        async def mock_query(prompt: str, options: object) -> AsyncMock:  # noqa: ARG001
            yield mock_message

        with (
            patch("claude_code_sdk.query", mock_query),
            patch("claude_code_sdk.ClaudeCodeOptions"),
        ):
            request = CompletionRequest(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Generate JSON"}],
                response_format={"type": "json_object"},
            )

            response = await provider.complete(request)
            content = response.choices[0]["message"]["content"]
            assert content == '{"result": "extracted"}'

    @pytest.mark.asyncio
    async def test_complete_json_retry_on_invalid(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test JSON retry on invalid response."""
        call_count = 0

        async def mock_query(prompt: str, options: object) -> AsyncMock:  # noqa: ARG001
            nonlocal call_count
            call_count += 1

            mock_message = MagicMock()
            mock_message.__class__.__name__ = "AssistantMessage"
            mock_text_block = MagicMock()

            if call_count == 1:
                # First attempt: invalid JSON
                mock_text_block.text = "This is not JSON"
            else:
                # Second attempt: valid JSON
                mock_text_block.text = '{"retry": "success"}'

            mock_message.content = [mock_text_block]
            yield mock_message

        with (
            patch("claude_code_sdk.query", mock_query),
            patch("claude_code_sdk.ClaudeCodeOptions"),
        ):
            request = CompletionRequest(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Generate JSON"}],
                response_format={"type": "json_object"},
            )

            response = await provider.complete(request)
            assert call_count == 2
            content = response.choices[0]["message"]["content"]
            assert json.loads(content) == {"retry": "success"}

    @pytest.mark.asyncio
    async def test_complete_json_max_retries_exceeded(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test JSON validation fails after max retries."""

        async def mock_query(prompt: str, options: object) -> AsyncMock:  # noqa: ARG001
            mock_message = MagicMock()
            mock_message.__class__.__name__ = "AssistantMessage"
            mock_text_block = MagicMock()
            mock_text_block.text = "Always invalid"
            mock_message.content = [mock_text_block]
            yield mock_message

        with (
            patch("claude_code_sdk.query", mock_query),
            patch("claude_code_sdk.ClaudeCodeOptions"),
        ):
            request = CompletionRequest(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Generate JSON"}],
                response_format={"type": "json_object"},
            )

            # Should still return response even if JSON invalid
            response = await provider.complete(request)
            assert response.choices[0]["message"]["content"] == "Always invalid"

    @pytest.mark.asyncio
    async def test_complete_import_error(self, provider: ClaudeCodeProvider) -> None:
        """Test completion when SDK not available."""
        with patch(
            "builtins.__import__",
            side_effect=ImportError("claude_code_sdk not found"),
        ):
            request = CompletionRequest(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Hello"}],
            )

            with pytest.raises(RuntimeError) as exc_info:
                await provider.complete(request)

            assert "Claude Code environment detected but SDK not available" in str(
                exc_info.value
            )

    @pytest.mark.asyncio
    async def test_complete_general_exception(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test completion with general exception."""
        with (
            patch(
                "claude_code_sdk.query",
                side_effect=Exception("Something went wrong"),
            ),
            patch("claude_code_sdk.ClaudeCodeOptions"),
        ):
            request = CompletionRequest(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Hello"}],
            )

            with pytest.raises(Exception) as exc_info:
                await provider.complete(request)

            assert "Something went wrong" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_progress_logging(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test progress logging during long-running queries."""

        async def slow_query(prompt: str, options: object) -> AsyncMock:  # noqa: ARG001
            # Simulate slow response
            await asyncio.sleep(0.05)  # Small delay to test progress

            mock_message = MagicMock()
            mock_message.__class__.__name__ = "AssistantMessage"
            mock_text_block = MagicMock()
            mock_text_block.text = "Slow response"
            mock_message.content = [mock_text_block]
            yield mock_message

        with (
            patch("claude_code_sdk.query", slow_query),
            patch("claude_code_sdk.ClaudeCodeOptions"),
            patch("scriptrag.llm.providers.claude_code.logger") as mock_logger,
        ):
            request = CompletionRequest(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Hello"}],
            )

            response = await provider.complete(request)
            assert response.choices[0]["message"]["content"] == "Slow response"

            # Check that start and completion were logged
            mock_logger.info.assert_any_call(
                "Claude Code query started (attempt 1/1)",
                prompt_length=11,
                has_system=False,
            )
            # Completion log should have been called
            assert any(
                "Claude Code query completed" in str(call)
                for call in mock_logger.info.call_args_list
            )

    @pytest.mark.asyncio
    async def test_complete_json_validation_with_required_fields(
        self, provider: ClaudeCodeProvider
    ) -> None:
        """Test JSON validation checks required fields."""
        call_count = 0

        async def mock_query(prompt: str, options: object) -> AsyncMock:  # noqa: ARG001
            nonlocal call_count
            call_count += 1

            mock_message = MagicMock()
            mock_message.__class__.__name__ = "AssistantMessage"
            mock_text_block = MagicMock()

            if call_count == 1:
                # Missing required field
                mock_text_block.text = '{"optional": "value"}'
            else:
                # Include required field
                mock_text_block.text = '{"required": "present", "optional": "value"}'

            mock_message.content = [mock_text_block]
            yield mock_message

        with (
            patch("claude_code_sdk.query", mock_query),
            patch("claude_code_sdk.ClaudeCodeOptions"),
        ):
            request = CompletionRequest(
                model="claude-3-opus",
                messages=[{"role": "user", "content": "Generate JSON"}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "required": {"type": "string"},
                                "optional": {"type": "string"},
                            },
                            "required": ["required"],
                        }
                    },
                },
            )

            response = await provider.complete(request)
            assert call_count == 2
            content = json.loads(response.choices[0]["message"]["content"])
            assert content["required"] == "present"
