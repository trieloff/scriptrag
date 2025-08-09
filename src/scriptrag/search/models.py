"""Data models for search functionality."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SearchMode(str, Enum):
    """Search mode enumeration."""

    STRICT = "strict"
    FUZZY = "fuzzy"
    AUTO = "auto"


@dataclass
class SearchQuery:
    """Parsed search query with components."""

    raw_query: str
    text_query: str | None = None
    characters: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    dialogue: str | None = None
    parenthetical: str | None = None
    action: str | None = None
    project: str | None = None
    season_start: int | None = None
    season_end: int | None = None
    episode_start: int | None = None
    episode_end: int | None = None
    mode: SearchMode = SearchMode.AUTO
    limit: int = 5
    offset: int = 0

    @property
    def needs_vector_search(self) -> bool:
        """Determine if vector search should be used."""
        if self.mode == SearchMode.STRICT:
            return False
        if self.mode == SearchMode.FUZZY:
            return True
        # Auto mode: use vector search for longer queries
        query_text = self.dialogue or self.action or self.text_query or ""
        word_count = len(query_text.split())
        return word_count > 10


@dataclass
class SearchResult:
    """Individual search result."""

    script_id: int
    script_title: str
    script_author: str | None
    scene_id: int
    scene_number: int
    scene_heading: str
    scene_location: str | None
    scene_time: str | None
    scene_content: str
    season: int | None = None
    episode: int | None = None
    match_type: str = "text"  # text, dialogue, action, vector
    relevance_score: float = 1.0
    matched_text: str | None = None
    character_name: str | None = None


@dataclass
class SearchResponse:
    """Complete search response with results and metadata."""

    query: SearchQuery
    results: list[SearchResult]
    total_count: int
    has_more: bool
    execution_time_ms: float | None = None
    search_methods: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
