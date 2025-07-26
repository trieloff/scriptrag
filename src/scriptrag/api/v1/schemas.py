"""Pydantic schemas for API request/response models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResponseStatus(str, Enum):
    """API response status."""

    SUCCESS = "success"
    ERROR = "error"


class BaseResponse(BaseModel):
    """Base response model."""

    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
    message: str | None = Field(default=None)


class ErrorResponse(BaseResponse):
    """Error response model."""

    status: ResponseStatus = Field(default=ResponseStatus.ERROR)
    error: str = Field(description="Error message")
    details: dict[str, Any] | None = Field(default=None, description="Error details")


# Script models
class ScriptUploadRequest(BaseModel):
    """Script upload request."""

    title: str = Field(description="Script title")
    content: str = Field(description="Fountain format content")
    author: str | None = Field(default=None, description="Script author")


class ScriptResponse(BaseModel):
    """Script response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: str | None
    created_at: datetime
    updated_at: datetime
    scene_count: int
    character_count: int
    has_embeddings: bool = Field(default=False)


class ScriptDetailResponse(ScriptResponse):
    """Detailed script response."""

    scenes: list["SceneResponse"] = Field(default_factory=list)
    characters: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# Scene models
class SceneResponse(BaseModel):
    """Scene response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    script_id: int
    scene_number: int
    heading: str
    content: str
    character_count: int
    word_count: int
    page_start: float | None
    page_end: float | None
    has_embedding: bool = Field(default=False)


class SceneCreateRequest(BaseModel):
    """Scene creation request."""

    scene_number: int
    heading: str
    content: str


class SceneUpdateRequest(BaseModel):
    """Scene update request."""

    scene_number: int | None = None
    heading: str | None = None
    content: str | None = None


# Embedding models
class EmbeddingGenerateRequest(BaseModel):
    """Embedding generation request."""

    regenerate: bool = Field(
        default=False, description="Force regeneration of existing embeddings"
    )
    batch_size: int = Field(default=32, description="Batch size for generation")


class EmbeddingResponse(BaseResponse):
    """Embedding generation response."""

    script_id: int
    scenes_processed: int
    scenes_skipped: int
    processing_time: float


# Search models
class SearchRequest(BaseModel):
    """Search request base."""

    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SceneSearchRequest(SearchRequest):
    """Scene search request."""

    query: str | None = Field(default=None, description="Text search query")
    script_id: int | None = Field(default=None, description="Filter by script")
    character: str | None = Field(default=None, description="Filter by character")
    scene_numbers: list[int] | None = Field(
        default=None, description="Filter by scene numbers"
    )


class SemanticSearchRequest(SearchRequest):
    """Semantic similarity search request."""

    query: str = Field(description="Semantic search query")
    script_id: int | None = Field(default=None, description="Filter by script")
    threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Similarity threshold"
    )


class SearchResultItem(BaseModel):
    """Search result item."""

    scene: SceneResponse
    score: float | None = Field(default=None, description="Relevance/similarity score")
    highlights: list[str] = Field(default_factory=list, description="Text highlights")


class SearchResponse(BaseResponse):
    """Search response."""

    results: list[SearchResultItem]
    total: int
    limit: int
    offset: int


# Graph models
class GraphNodeType(str, Enum):
    """Graph node types."""

    SCENE = "scene"
    CHARACTER = "character"
    LOCATION = "location"


class GraphNode(BaseModel):
    """Graph node."""

    id: str
    type: GraphNodeType
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Graph edge."""

    source: str
    target: str
    type: str
    weight: float = Field(default=1.0)
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphResponse(BaseResponse):
    """Graph visualization response."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    metadata: dict[str, Any] = Field(default_factory=dict)


class CharacterGraphRequest(BaseModel):
    """Character relationship graph request."""

    character_name: str
    script_id: int | None = None
    depth: int = Field(default=2, ge=1, le=5)
    min_interaction_count: int = Field(default=1, ge=1)


class TimelineGraphRequest(BaseModel):
    """Timeline visualization request."""

    script_id: int
    group_by: str = Field(default="act", description="Grouping: act, sequence, or none")
    include_characters: bool = Field(default=True)


# Forward references
ScriptDetailResponse.model_rebuild()
SearchResultItem.model_rebuild()
