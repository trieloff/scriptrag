"""Type definitions for API modules."""

from __future__ import annotations

from typing import Any, TypedDict


class SceneData(TypedDict, total=False):
    """Data structure for scene information."""

    id: int
    script_id: str
    scene_number: int | str
    heading: str
    content: str
    characters: list[str]
    location: str
    time_of_day: str
    page_number: float
    metadata: dict[str, Any]


class ScriptData(TypedDict, total=False):
    """Data structure for script information."""

    id: str
    title: str
    author: str | None
    scenes: list[SceneData]
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


class EmbeddingData(TypedDict):
    """Data structure for embeddings."""

    scene_id: int
    script_id: str
    embedding: list[float]
    model: str
    created_at: str


class SearchQuery(TypedDict, total=False):
    """Search query parameters."""

    text: str
    script_id: str | None
    character: str | None
    location: str | None
    limit: int
    offset: int


class SearchResultData(TypedDict):
    """Search result data."""

    scene_id: int
    script_id: str
    score: float
    heading: str
    content: str
    metadata: dict[str, Any]


class AnalysisRequest(TypedDict, total=False):
    """Request for scene analysis."""

    scene_id: int
    script_id: str
    analyzer: str
    parameters: dict[str, Any]


class AnalysisResultData(TypedDict):
    """Result from scene analysis."""

    scene_id: int
    script_id: str
    analyzer: str
    version: str
    results: dict[str, Any]
    timestamp: str


class DatabaseStats(TypedDict):
    """Database statistics."""

    total_scripts: int
    total_scenes: int
    total_embeddings: int
    total_characters: int
    database_size: int
