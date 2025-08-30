"""Type definitions for agent modules."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentMetadata(TypedDict, total=False):
    """Metadata for an agent."""

    name: str
    version: str
    description: str
    requires_llm: bool
    author: str
    tags: list[str]
    created_at: str
    updated_at: str


class AgentPrompt(TypedDict):
    """Prompt configuration for an agent."""

    system: str
    user: str
    temperature: float
    max_tokens: int


class AgentContext(TypedDict, total=False):
    """Context data for agent execution."""

    script_id: str
    scene_id: int
    character: str | None
    location: str | None
    previous_scenes: list[dict[str, Any]]
    next_scenes: list[dict[str, Any]]


class AgentOutput(TypedDict, total=False):
    """Output from agent execution."""

    result: dict[str, Any]
    confidence: float
    explanation: str | None
    metadata: dict[str, Any]


class AgentConfig(TypedDict, total=False):
    """Configuration for an agent."""

    model: str
    temperature: float
    max_tokens: int
    timeout: int
    retry_count: int
    cache_results: bool


class ContextQuery(TypedDict):
    """Query for context information."""

    type: str
    parameters: dict[str, Any]
    limit: int


class ContextResult(TypedDict):
    """Result from context query."""

    query: ContextQuery
    results: list[dict[str, Any]]
    count: int
