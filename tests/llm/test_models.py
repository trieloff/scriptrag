"""Tests for LLM models module."""

from __future__ import annotations

import pytest

from scriptrag.llm.models import CompletionResponse, LLMProvider


class TestCompletionResponse:
    """Tests for CompletionResponse model."""

    def test_content_property_success(self) -> None:
        """Test content property returns the correct content."""
        response = CompletionResponse(
            id="test-id",
            model="test-model",
            provider=LLMProvider.OPENAI_COMPATIBLE,
            choices=[
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "This is the response content",
                    },
                    "finish_reason": "stop",
                }
            ],
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )

        assert response.content == "This is the response content"

    def test_content_property_no_choices(self) -> None:
        """Test content property raises IndexError when no choices."""
        response = CompletionResponse(
            id="test-id",
            model="test-model",
            provider=LLMProvider.OPENAI_COMPATIBLE,
            choices=[],
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )

        with pytest.raises(IndexError, match="No choices available in response"):
            _ = response.content

    def test_content_property_multiple_choices(self) -> None:
        """Test content property returns first choice when multiple available."""
        response = CompletionResponse(
            id="test-id",
            model="test-model",
            provider=LLMProvider.OPENAI_COMPATIBLE,
            choices=[
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "First response",
                    },
                    "finish_reason": "stop",
                },
                {
                    "index": 1,
                    "message": {
                        "role": "assistant",
                        "content": "Second response",
                    },
                    "finish_reason": "stop",
                },
            ],
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )

        assert response.content == "First response"

    def test_content_property_converts_to_string(self) -> None:
        """Test content property converts non-string content to string."""
        response = CompletionResponse(
            id="test-id",
            model="test-model",
            provider=LLMProvider.OPENAI_COMPATIBLE,
            choices=[
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": 12345,  # Non-string content
                    },
                    "finish_reason": "stop",
                }
            ],
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )

        assert response.content == "12345"
        assert isinstance(response.content, str)

    def test_content_property_none_content(self) -> None:
        """Test content property handles None content."""
        response = CompletionResponse(
            id="test-id",
            model="test-model",
            provider=LLMProvider.OPENAI_COMPATIBLE,
            choices=[
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                    },
                    "finish_reason": "stop",
                }
            ],
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )

        assert response.content == "None"

    def test_content_property_empty_string(self) -> None:
        """Test content property handles empty string content."""
        response = CompletionResponse(
            id="test-id",
            model="test-model",
            provider=LLMProvider.OPENAI_COMPATIBLE,
            choices=[
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "",
                    },
                    "finish_reason": "stop",
                }
            ],
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )

        assert response.content == ""

    def test_completion_response_full_structure(self) -> None:
        """Test CompletionResponse model with full structure."""
        response = CompletionResponse(
            id="chatcmpl-123",
            model="gpt-3.5-turbo",
            provider=LLMProvider.OPENAI_COMPATIBLE,
            choices=[
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help you today?",
                    },
                    "finish_reason": "stop",
                }
            ],
            usage={
                "prompt_tokens": 15,
                "completion_tokens": 10,
                "total_tokens": 25,
            },
        )

        assert response.id == "chatcmpl-123"
        assert response.model == "gpt-3.5-turbo"
        assert response.provider == LLMProvider.OPENAI_COMPATIBLE
        assert len(response.choices) == 1
        assert (
            response.choices[0]["message"]["content"]
            == "Hello! How can I help you today?"
        )
        assert response.usage["total_tokens"] == 25
        assert response.content == "Hello! How can I help you today?"
