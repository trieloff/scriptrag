"""Type definitions for Claude Code provider."""

from typing import Literal, TypedDict


class MessageDict(TypedDict):
    """Type for message dictionary."""

    role: Literal["user", "assistant", "system"]
    content: str


class CompletionChoice(TypedDict):
    """Type for completion choice."""

    index: int
    message: MessageDict
    finish_reason: Literal["stop", "length", "content_filter"]


class CompletionUsage(TypedDict):
    """Type for completion usage stats."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class JSONSchema(TypedDict, total=False):
    """Type for JSON Schema structure."""

    type: str
    properties: dict[str, "JSONSchemaProperty"]
    required: list[str]
    items: "JSONSchemaProperty"


class JSONSchemaProperty(TypedDict, total=False):
    """Type for JSON Schema property."""

    type: str
    description: str
    properties: dict[str, "JSONSchemaProperty"]
    items: "JSONSchemaProperty"


class ResponseFormat(TypedDict, total=False):
    """Type for response format specification."""

    type: Literal["json_object", "json_schema"]
    json_schema: "JSONSchemaSpec"
    schema: JSONSchema
    name: str


class JSONSchemaSpec(TypedDict, total=False):
    """Type for JSON schema specification."""

    name: str
    schema: JSONSchema
    strict: bool


class SchemaInfo(TypedDict, total=False):
    """Type for extracted schema information."""

    name: str
    schema: JSONSchema
