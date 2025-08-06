"""Data models for LLM integration."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LLMProvider(str, Enum):
    """Available LLM providers."""

    CLAUDE_CODE = "claude_code"
    GITHUB_MODELS = "github_models"
    OPENAI_COMPATIBLE = "openai_compatible"


class Model(BaseModel):
    """LLM model information."""

    id: str
    name: str
    provider: LLMProvider
    capabilities: list[str] = Field(default_factory=list)
    context_window: int | None = None
    max_output_tokens: int | None = None


class CompletionRequest(BaseModel):
    """Request for text completion."""

    model: str
    messages: list[dict[str, str]]
    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float = 1.0
    stream: bool = False
    system: str | None = None


class CompletionResponse(BaseModel):
    """Response from text completion."""

    id: str
    model: str
    choices: list[dict[str, Any]]
    usage: dict[str, int] = Field(default_factory=dict)
    provider: LLMProvider

    @property
    def content(self) -> str:
        """Get the content from the first choice message.

        Returns:
            The content text from the first choice's message.

        Raises:
            IndexError: If no choices available.
            KeyError: If message structure is invalid.
        """
        if not self.choices:
            raise IndexError("No choices available in response")
        return str(self.choices[0]["message"]["content"])


class EmbeddingRequest(BaseModel):
    """Request for text embedding."""

    model: str
    input: str | list[str]
    dimensions: int | None = None


class EmbeddingResponse(BaseModel):
    """Response from text embedding."""

    model: str
    data: list[dict[str, Any]]
    usage: dict[str, int] = Field(default_factory=dict)
    provider: LLMProvider
