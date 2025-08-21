"""Common type definitions and aliases for ScriptRAG."""

from typing import Any, Protocol, TypeAlias, TypedDict

# Scene and Script related types
SceneID: TypeAlias = int
ScriptID: TypeAlias = str
CharacterName: TypeAlias = str
Location: TypeAlias = str
TimeOfDay: TypeAlias = str
SceneNumber: TypeAlias = int | str
PageNumber: TypeAlias = float


# Metadata types
class SceneMetadata(TypedDict, total=False):
    """Metadata for a scene."""

    hash: str
    characters: list[CharacterName]
    location: Location
    time_of_day: TimeOfDay
    page_number: PageNumber
    duration: float
    word_count: int
    dialogue_count: int
    action_count: int


class ScriptMetadata(TypedDict, total=False):
    """Metadata for a script."""

    source_file: str
    episode: int | str
    season: int | str
    series_title: str
    project_title: str
    author: str
    title: str
    total_scenes: int
    total_pages: float
    total_words: int


# Database record types
class SceneRecord(TypedDict):
    """Database record for a scene."""

    id: SceneID
    script_id: ScriptID
    scene_number: SceneNumber
    heading: str
    content: str
    metadata: SceneMetadata
    embedding: list[float] | None


class ScriptRecord(TypedDict):
    """Database record for a script."""

    id: ScriptID
    title: str
    author: str | None
    metadata: ScriptMetadata
    created_at: str
    updated_at: str


# Analysis result types
class AnalysisResult(TypedDict, total=False):
    """Result from an analysis operation."""

    analyzer: str
    version: str
    scene_id: SceneID
    script_id: ScriptID
    results: dict[str, Any]
    confidence: float
    timestamp: str


# LLM related types
class LLMMessage(TypedDict):
    """Message format for LLM interactions."""

    role: str
    content: str


class LLMResponse(TypedDict):
    """Response from LLM."""

    content: str
    model: str
    usage: dict[str, int]
    metadata: dict[str, Any]


# Search and query types
class SearchResult(TypedDict):
    """Result from a search operation."""

    scene_id: SceneID
    script_id: ScriptID
    score: float
    heading: str
    content: str
    metadata: SceneMetadata


class QueryResult(TypedDict):
    """Result from a query operation."""

    query: str
    results: list[SearchResult]
    total: int
    execution_time: float


# Embedding types
EmbeddingVector: TypeAlias = list[float]
EmbeddingModel: TypeAlias = str


class EmbeddingResult(TypedDict):
    """Result from embedding operation."""

    text: str
    embedding: EmbeddingVector
    model: EmbeddingModel
    dimensions: int


# Protocol definitions
class Analyzer(Protocol):
    """Protocol for scene analyzers."""

    name: str
    version: str
    requires_llm: bool

    async def analyze(self, scene: dict[str, Any]) -> dict[str, Any]:
        """Analyze a scene."""
        ...

    async def initialize(self) -> None:
        """Initialize the analyzer."""
        ...

    async def cleanup(self) -> None:
        """Clean up resources."""
        ...


class Embedder(Protocol):
    """Protocol for text embedders."""

    model: str
    dimensions: int

    async def embed(self, text: str) -> EmbeddingVector:
        """Embed a single text."""
        ...

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingVector]:
        """Embed multiple texts."""
        ...


class QueryEngine(Protocol):
    """Protocol for query engines."""

    async def query(self, query: str, limit: int = 10) -> QueryResult:
        """Execute a query."""
        ...

    async def search(self, text: str, limit: int = 10) -> list[SearchResult]:
        """Search for text."""
        ...
