"""Type definitions for analyzer modules."""

from typing import Any, TypeAlias, TypedDict


# Analyzer result types
class AnalyzerResult(TypedDict, total=False):
    """Result from an analyzer operation."""

    success: bool
    data: dict[str, Any]
    error: str | None
    metadata: dict[str, Any]


class EmbeddingAnalyzerResult(TypedDict):
    """Result from embedding analysis."""

    embedding: list[float]
    model: str
    dimensions: int
    embedding_path: str | None


class CharacterAnalyzerResult(TypedDict):
    """Result from character analysis."""

    characters: list[str]
    main_characters: list[str]
    character_count: int


class LocationAnalyzerResult(TypedDict):
    """Result from location analysis."""

    locations: list[str]
    primary_location: str | None
    location_changes: int


# Analyzer configuration types
AnalyzerConfig: TypeAlias = dict[str, Any]
AnalyzerMetadata: TypeAlias = dict[str, Any]
