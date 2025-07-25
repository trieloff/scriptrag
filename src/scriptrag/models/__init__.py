"""
ScriptRAG Data Models

This module defines the data models for screenplay elements that will be stored
in the graph database. These models are designed to work with the Fountain
format parser and support the GraphRAG pattern.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, ConfigDict


class ElementType(str, Enum):
    """Fountain screenplay element types."""
    ACTION = "action"
    SCENE_HEADING = "scene_heading"
    CHARACTER = "character"
    DIALOGUE = "dialogue"
    PARENTHETICAL = "parenthetical"
    TRANSITION = "transition"
    SHOT = "shot"
    BONEYARD = "boneyard"
    PAGE_BREAK = "page_break"
    SYNOPSIS = "synopsis"
    SECTION = "section"


class SceneOrderType(str, Enum):
    """Types of scene ordering."""
    SCRIPT = "script"      # Order as written in script
    TEMPORAL = "temporal"  # Chronological story order
    LOGICAL = "logical"    # Logical dependency order


class BaseEntity(BaseModel):
    """Base class for all screenplay entities."""
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_encoders={
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }
    )


class Location(BaseModel):
    """Represents a location where scenes take place."""
    interior: bool = True  # INT/EXT
    name: str  # e.g., "COFFEE SHOP"
    time: Optional[str] = None  # e.g., "DAY", "NIGHT"
    raw_text: str  # Original scene heading text

    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Location name cannot be empty')
        return v.strip().upper()

    def __str__(self) -> str:
        prefix = "INT." if self.interior else "EXT."
        time_suffix = f" - {self.time}" if self.time else ""
        return f"{prefix} {self.name}{time_suffix}"


class Character(BaseEntity):
    """Represents a character in the screenplay."""
    name: str
    description: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)  # Alternative names/spellings

    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Character name cannot be empty')
        return v.strip().upper()


class SceneElement(BaseEntity):
    """Base class for elements within a scene."""
    element_type: ElementType
    text: str
    raw_text: str  # Original fountain text
    scene_id: UUID
    order_in_scene: int


class Action(SceneElement):
    """Action or description element."""
    element_type: Literal[ElementType.ACTION] = ElementType.ACTION


class Dialogue(SceneElement):
    """Dialogue element."""
    element_type: Literal[ElementType.DIALOGUE] = ElementType.DIALOGUE
    character_id: UUID
    character_name: str  # Denormalized for easy access


class Parenthetical(SceneElement):
    """Parenthetical direction element."""
    element_type: Literal[ElementType.PARENTHETICAL] = ElementType.PARENTHETICAL
    associated_dialogue_id: Optional[UUID] = None


class Transition(SceneElement):
    """Transition element (CUT TO, FADE IN, etc.)."""
    element_type: Literal[ElementType.TRANSITION] = ElementType.TRANSITION


class Scene(BaseEntity):
    """Represents a scene in the screenplay."""
    location: Optional[Location] = None
    heading: Optional[str] = None  # Raw scene heading
    description: Optional[str] = None
    script_order: int  # Order in the original script
    temporal_order: Optional[int] = None  # Chronological story order
    logical_order: Optional[int] = None  # Logical dependency order

    # Parent references
    episode_id: Optional[UUID] = None
    season_id: Optional[UUID] = None
    script_id: UUID

    # Scene content
    elements: List[SceneElement] = Field(default_factory=list)
    characters: List[UUID] = Field(default_factory=list)  # Character IDs appearing in scene

    # Time metadata
    estimated_duration_minutes: Optional[float] = None
    time_of_day: Optional[str] = None
    date_in_story: Optional[str] = None


class Episode(BaseEntity):
    """Represents an episode in a TV series."""
    title: str
    number: int  # Episode number within season
    season_id: UUID
    script_id: UUID

    # Episode metadata
    description: Optional[str] = None
    air_date: Optional[datetime] = None
    writer: Optional[str] = None
    director: Optional[str] = None

    # Content
    scenes: List[UUID] = Field(default_factory=list)  # Scene IDs
    characters: List[UUID] = Field(default_factory=list)  # Character IDs

    @field_validator('number')
    @classmethod
    def number_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Episode number must be positive')
        return v


class Season(BaseEntity):
    """Represents a season of a TV series."""
    number: int
    title: Optional[str] = None
    script_id: UUID

    # Season metadata
    description: Optional[str] = None
    year: Optional[int] = None

    # Content
    episodes: List[UUID] = Field(default_factory=list)  # Episode IDs

    @field_validator('number')
    @classmethod
    def number_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Season number must be positive')
        return v


class Script(BaseEntity):
    """Represents a complete screenplay or script."""
    title: str
    format: str = "screenplay"  # screenplay, teleplay, etc.

    # Script metadata
    author: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    logline: Optional[str] = None

    # Source information
    fountain_source: Optional[str] = None  # Original fountain text
    source_file: Optional[str] = None  # Source file path

    # Content organization
    is_series: bool = False  # True for TV series, False for single screenplay
    seasons: List[UUID] = Field(default_factory=list)  # Season IDs (for series)
    episodes: List[UUID] = Field(default_factory=list)  # Episode IDs
    scenes: List[UUID] = Field(default_factory=list)  # Scene IDs
    characters: List[UUID] = Field(default_factory=list)  # Character IDs

    # Title page metadata
    title_page: Dict[str, str] = Field(default_factory=dict)

    @field_validator('title')
    @classmethod
    def title_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Script title cannot be empty')
        return v.strip()


# Relationship models for the graph database
class Relationship(BaseModel):
    """Base class for relationships between entities."""
    from_id: UUID
    to_id: UUID
    relationship_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CharacterAppears(Relationship):
    """Character appears in scene relationship."""
    relationship_type: Literal["APPEARS_IN"] = "APPEARS_IN"
    speaking_lines: int = 0
    action_mentions: int = 0


class SceneFollows(Relationship):
    """Scene follows another scene relationship."""
    relationship_type: Literal["FOLLOWS"] = "FOLLOWS"
    order_type: SceneOrderType


class CharacterSpeaksTo(Relationship):
    """Character speaks to another character relationship."""
    relationship_type: Literal["SPEAKS_TO"] = "SPEAKS_TO"
    scene_id: UUID
    dialogue_count: int = 1


class SceneAtLocation(Relationship):
    """Scene takes place at location relationship."""
    relationship_type: Literal["AT_LOCATION"] = "AT_LOCATION"


# Export all models
__all__ = [
    # Enums
    "ElementType",
    "SceneOrderType",

    # Base classes
    "BaseEntity",
    "SceneElement",

    # Core entities
    "Script",
    "Season",
    "Episode",
    "Scene",
    "Character",
    "Location",

    # Scene elements
    "Action",
    "Dialogue",
    "Parenthetical",
    "Transition",

    # Relationships
    "Relationship",
    "CharacterAppears",
    "SceneFollows",
    "CharacterSpeaksTo",
    "SceneAtLocation",
]
