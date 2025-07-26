"""Type definitions for search functionality."""

from enum import Enum
from typing import Any, TypeAlias, TypedDict


class SearchType(str, Enum):
    """Types of search operations."""

    DIALOGUE = "dialogue"
    ACTION = "action"
    CHARACTER = "character"
    LOCATION = "location"
    OBJECT = "object"
    SCENE = "scene"
    SEMANTIC = "semantic"
    SIMILARITY = "similarity"
    TEMPORAL = "temporal"
    FULL_TEXT = "full_text"


class SearchResult(TypedDict):
    """Standard search result format."""

    id: str
    type: str
    content: str
    score: float
    metadata: dict[str, Any]
    highlights: list[str]


SearchResults: TypeAlias = list[SearchResult]
