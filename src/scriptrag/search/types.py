"""Type definitions for search modules."""

from __future__ import annotations

from typing import Any, TypeAlias, TypedDict


# Search query types
class SearchQuery(TypedDict, total=False):
    """Search query parameters."""

    text: str
    filters: dict[str, Any]
    limit: int
    offset: int
    include_metadata: bool


class SearchFilter(TypedDict, total=False):
    """Search filter parameters."""

    script_id: str | None
    character: str | None
    location: str | None
    scene_type: str | None


# Search result types
class SearchMatch(TypedDict):
    """Individual search match."""

    scene_id: int
    script_id: str
    score: float
    snippet: str
    highlights: list[str]


class SearchResponse(TypedDict):
    """Search operation response."""

    matches: list[SearchMatch]
    total_results: int
    execution_time: float
    query: str


# Vector search types
class VectorQuery(TypedDict):
    """Vector similarity query."""

    vector: list[float]
    limit: int
    threshold: float | None


class VectorResult(TypedDict):
    """Vector search result."""

    id: int
    score: float
    metadata: dict[str, Any]


# Search engine configuration
SearchEngineConfig: TypeAlias = dict[str, Any]
SearchMetrics: TypeAlias = dict[str, Any]
