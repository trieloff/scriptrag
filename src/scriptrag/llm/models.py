"""Data models for LLM integration."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class LLMProvider(str, Enum):
    """Available LLM providers."""

    CLAUDE_CODE = "claude_code"
    GITHUB_MODELS = "github_models"
    OPENAI_COMPATIBLE = "openai_compatible"


# TypedDict definitions for structured data
class CompletionMessage(TypedDict):
    """Message in completion choice."""

    role: str
    content: Any  # Can be str, int, None - converted to str in the property


class CompletionChoice(TypedDict):
    """Choice in completion response."""

    index: int
    message: CompletionMessage
    finish_reason: str


class EmbeddingData(TypedDict, total=False):
    """Embedding data structure."""

    object: str
    index: int
    embedding: list[float]


class UsageInfo(TypedDict, total=False):
    """Token usage information."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def _default_usage_info() -> UsageInfo:
    """Create default empty UsageInfo."""
    return UsageInfo()


class ResponseFormat(TypedDict, total=False):
    """Response format specification for completions."""

    type: str  # e.g., "json_object", "text"
    schema: dict[str, Any]  # JSON schema when type is "json_object"


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
    response_format: ResponseFormat | None = None


class CompletionResponse(BaseModel):
    """Response from text completion."""

    id: str
    model: str
    choices: list[CompletionChoice]
    usage: UsageInfo = Field(default_factory=_default_usage_info)
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
    data: list[EmbeddingData]
    usage: UsageInfo = Field(default_factory=_default_usage_info)
    provider: LLMProvider
