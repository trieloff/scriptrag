"""Pydantic schemas for API request/response models."""

import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    title: str = Field(
        description="Script title",
        min_length=1,
        max_length=200,
    )
    content: str = Field(
        description="Fountain format content",
        min_length=1,
        max_length=10 * 1024 * 1024,  # 10MB limit
    )
    author: str | None = Field(
        default=None,
        description="Script author",
        min_length=1,
        max_length=100,
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title is not whitespace and has alphanumeric characters."""
        if not v or v.isspace():
            raise ValueError("Title cannot be empty or contain only whitespace")

        # Check if title contains at least one alphanumeric character
        if not re.search(r"[a-zA-Z0-9]", v):
            raise ValueError("Title must contain at least one alphanumeric character")

        return v.strip()

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate content is not empty and appears to be Fountain format."""
        if not v or v.isspace():
            raise ValueError("Content cannot be empty or contain only whitespace")

        # Basic Fountain format validation - check for at least one of:
        # - Scene heading (INT./EXT./EST./INT/EXT/EST)
        # - Character name (all caps line followed by dialogue)
        # - Transition (ends with TO:)
        # - Action lines (just need some text)

        lines = v.strip().split("\n")
        non_empty_lines = [line.strip() for line in lines if line.strip()]

        if not non_empty_lines:
            raise ValueError("Content must contain some non-empty lines")

        # Check for scene headings
        scene_heading_pattern = re.compile(
            r"^(INT\.?|EXT\.?|EST\.?|I\/E\.?)[\s\.]|^\.[A-Z]", re.IGNORECASE
        )

        # Check for character names (all caps, possibly with extensions)
        character_pattern = re.compile(r"^[A-Z][A-Z0-9\s]+(?:\s*\([^)]+\))?$")

        # Check for transitions
        transition_pattern = re.compile(r"TO:$|^>")

        has_screenplay_element = False

        for i, line in enumerate(non_empty_lines):
            # Scene heading check
            if scene_heading_pattern.match(line):
                has_screenplay_element = True
                break

            # Character/dialogue check
            if character_pattern.match(line) and i + 1 < len(non_empty_lines):
                # Next line should be dialogue (not all caps)
                next_line = non_empty_lines[i + 1]
                if next_line and not next_line.isupper():
                    has_screenplay_element = True
                    break

            # Transition check
            if transition_pattern.search(line):
                has_screenplay_element = True
                break

        if not has_screenplay_element:
            raise ValueError(
                "Content must contain recognizable Fountain/screenplay elements "
                "(scene headings, character dialogue, or transitions)"
            )

        return v

    @field_validator("author")
    @classmethod
    def validate_author(cls, v: str | None) -> str | None:
        """Validate author name if provided."""
        if v is None:
            return v

        if v.isspace():
            raise ValueError("Author cannot contain only whitespace")

        # Check if author contains at least one alphanumeric character
        if not re.search(r"[a-zA-Z0-9]", v):
            raise ValueError("Author must contain at least one alphanumeric character")

        return v.strip()


class ScriptResponse(BaseModel):
    """Script response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
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

    id: str
    script_id: str
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

    scene_number: int = Field(ge=1, description="Scene number must be positive")
    heading: str = Field(min_length=1, description="Scene heading")
    content: str = Field(min_length=1, description="Scene content")

    @field_validator("heading")
    @classmethod
    def validate_heading(cls, v: str) -> str:
        """Validate heading is not empty."""
        if not v or v.isspace():
            raise ValueError("Heading cannot be empty or contain only whitespace")
        return v.strip()


class SceneUpdateRequest(BaseModel):
    """Scene update request."""

    scene_number: int | None = None
    heading: str | None = None
    content: str | None = None
    location: str | None = None
    time_of_day: str | None = None


class SceneOrderingRequest(BaseModel):
    """Scene ordering request."""

    scene_ids: list[str] = Field(description="List of scene IDs in desired order")
    order_type: str = Field(
        default="script",
        description="Type of ordering: script, temporal, or logical",
    )


class SceneOrderingResponse(BaseModel):
    """Scene ordering response."""

    script_id: str
    order_type: str
    scene_ids: list[str]
    message: str


# Embedding models
class EmbeddingGenerateRequest(BaseModel):
    """Embedding generation request."""

    regenerate: bool = Field(
        default=False, description="Force regeneration of existing embeddings"
    )
    batch_size: int = Field(default=32, description="Batch size for generation")


class EmbeddingResponse(BaseResponse):
    """Embedding generation response."""

    script_id: str
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

    query: str = Field(description="Text search query")
    script_id: str | None = Field(default=None, description="Filter by script")
    character: str | None = Field(default=None, description="Filter by character")
    scene_numbers: list[int] | None = Field(
        default=None, description="Filter by scene numbers"
    )


class SemanticSearchRequest(SearchRequest):
    """Semantic similarity search request."""

    query: str = Field(description="Semantic search query")
    script_id: str | None = Field(default=None, description="Filter by script")
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
    ACT = "act"
    DAY = "day"


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
    script_id: str | None = None
    depth: int = Field(default=2, ge=1, le=5)
    min_interaction_count: int = Field(default=1, ge=1)


class TimelineGraphRequest(BaseModel):
    """Timeline visualization request."""

    script_id: str
    group_by: str = Field(default="act", description="Grouping: act, sequence, or none")
    include_characters: bool = Field(default=True)


# Forward references
ScriptDetailResponse.model_rebuild()
SearchResultItem.model_rebuild()
