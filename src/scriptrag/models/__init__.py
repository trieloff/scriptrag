"""ScriptRAG Data Models.

This module defines the data models for screenplay elements that will be stored
in the graph database. These models are designed to work with the Fountain
format parser and support the GraphRAG pattern.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    SCRIPT = "script"  # Order as written in script
    TEMPORAL = "temporal"  # Chronological story order
    LOGICAL = "logical"  # Logical dependency order


class SceneDependencyType(str, Enum):
    """Types of logical dependencies between scenes."""

    REQUIRES = "requires"  # Scene A requires Scene B to have happened
    REFERENCES = "references"  # Scene A references events from Scene B
    CONTINUES = "continues"  # Scene A directly continues from Scene B
    FLASHBACK_TO = "flashback_to"  # Scene A is a flashback to Scene B


class NodeType(str, Enum):
    """Types of nodes in the knowledge graph."""

    SCRIPT = "script"
    SCENE = "scene"
    CHARACTER = "character"
    LOCATION = "location"
    PROP = "prop"
    DIALOGUE = "dialogue"
    ACTION = "action"
    EPISODE = "episode"
    SEASON = "season"


class EdgeType(str, Enum):
    """Types of edges in the knowledge graph."""

    CONTAINS = "contains"
    APPEARS_IN = "appears_in"
    SPEAKS_TO = "speaks_to"
    FOLLOWS = "follows"
    REFERENCES = "references"
    INTRODUCES = "introduces"
    USES = "uses"
    LOCATED_AT = "located_at"
    PART_OF = "part_of"


class BaseEntity(BaseModel):
    """Base class for all screenplay entities."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

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
    time: str | None = None  # e.g., "DAY", "NIGHT"
    raw_text: str  # Original scene heading text

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        """Validate that location name is not empty."""
        if not v or not v.strip():
            raise ValueError("Location name cannot be empty")
        return v.strip().upper()

    def __str__(self) -> str:
        """Return formatted location string in fountain format."""
        prefix = "INT." if self.interior else "EXT."
        time_suffix = f" - {self.time}" if self.time else ""
        return f"{prefix} {self.name}{time_suffix}"


class Character(BaseEntity):
    """Represents a character in the screenplay."""

    name: str
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)  # Alternative names/spellings

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        """Validate that character name is not empty."""
        if not v or not v.strip():
            raise ValueError("Character name cannot be empty")
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
    associated_dialogue_id: UUID | None = None


class Transition(SceneElement):
    """Transition element (CUT TO, FADE IN, etc.)."""

    element_type: Literal[ElementType.TRANSITION] = ElementType.TRANSITION


class Scene(BaseEntity):
    """Represents a scene in the screenplay."""

    location: Location | None = None
    heading: str | None = None  # Raw scene heading
    description: str | None = None
    script_order: int  # Order in the original script
    temporal_order: int | None = None  # Chronological story order
    logical_order: int | None = None  # Logical dependency order

    # Parent references
    episode_id: UUID | None = None
    season_id: UUID | None = None
    script_id: UUID

    # Scene content
    elements: list[SceneElement] = Field(default_factory=list)
    characters: list[UUID] = Field(
        default_factory=list
    )  # Character IDs appearing in scene

    # Time metadata
    estimated_duration_minutes: float | None = None
    time_of_day: str | None = None
    date_in_story: str | None = None


class Episode(BaseEntity):
    """Represents an episode in a TV series."""

    title: str
    number: int  # Episode number within season
    season_id: UUID
    script_id: UUID

    # Episode metadata
    description: str | None = None
    air_date: datetime | None = None
    writer: str | None = None
    director: str | None = None

    # Content
    scenes: list[UUID] = Field(default_factory=list)  # Scene IDs
    characters: list[UUID] = Field(default_factory=list)  # Character IDs

    @field_validator("number")
    @classmethod
    def number_must_be_positive(cls, v: int) -> int:
        """Validate that episode number is positive."""
        if v <= 0:
            raise ValueError("Episode number must be positive")
        return v


class Season(BaseEntity):
    """Represents a season of a TV series."""

    number: int
    title: str | None = None
    script_id: UUID

    # Season metadata
    description: str | None = None
    year: int | None = None

    # Content
    episodes: list[UUID] = Field(default_factory=list)  # Episode IDs

    @field_validator("number")
    @classmethod
    def number_must_be_positive(cls, v: int) -> int:
        """Validate that season number is positive."""
        if v <= 0:
            raise ValueError("Season number must be positive")
        return v


class Script(BaseEntity):
    """Represents a complete screenplay or script."""

    title: str
    format: str = "screenplay"  # screenplay, teleplay, etc.

    # Script metadata
    author: str | None = None
    description: str | None = None
    genre: str | None = None
    logline: str | None = None

    # Source information
    fountain_source: str | None = None  # Original fountain text
    source_file: str | None = None  # Source file path

    # Content organization
    is_series: bool = False  # True for TV series, False for single screenplay
    seasons: list[UUID] = Field(default_factory=list)  # Season IDs (for series)
    episodes: list[UUID] = Field(default_factory=list)  # Episode IDs
    scenes: list[UUID] = Field(default_factory=list)  # Scene IDs
    characters: list[UUID] = Field(default_factory=list)  # Character IDs

    # Title page metadata
    title_page: dict[str, str] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, v: str) -> str:
        """Validate that script title is not empty."""
        if not v or not v.strip():
            raise ValueError("Script title cannot be empty")
        return v.strip()


# Relationship models for the graph database
class Relationship(BaseModel):
    """Base class for relationships between entities."""

    from_id: UUID
    to_id: UUID
    relationship_type: str
    properties: dict[str, Any] = Field(default_factory=dict)
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


class SceneDependency(BaseEntity):
    """Represents a logical dependency between scenes."""

    from_scene_id: UUID
    to_scene_id: UUID
    dependency_type: SceneDependencyType
    description: str | None = None
    strength: float = Field(default=1.0, ge=0.0, le=1.0)  # 0.0 to 1.0

    @field_validator("strength")
    @classmethod
    def validate_strength(cls, v: float) -> float:
        """Validate that strength is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Dependency strength must be between 0.0 and 1.0")
        return v


# Script Bible and Continuity Management Models


class BibleType(str, Enum):
    """Types of script bibles."""

    SERIES = "series"
    MOVIE = "movie"
    ANTHOLOGY = "anthology"


class BibleStatus(str, Enum):
    """Status of a script bible."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"


class SeriesBible(BaseEntity):
    """Represents a script bible for a series or film."""

    script_id: UUID
    title: str
    description: str | None = None
    version: int = 1
    created_by: str | None = None
    status: BibleStatus = BibleStatus.ACTIVE
    bible_type: BibleType = BibleType.SERIES

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, v: str) -> str:
        """Validate that bible title is not empty."""
        if not v or not v.strip():
            raise ValueError("Bible title cannot be empty")
        return v.strip()


class CharacterProfile(BaseEntity):
    """Extended character profile for continuity tracking."""

    character_id: UUID
    script_id: UUID
    series_bible_id: UUID | None = None

    # Core character information
    full_name: str | None = None
    age: int | None = None
    occupation: str | None = None
    background: str | None = None
    personality_traits: str | None = None
    motivations: str | None = None
    fears: str | None = None
    goals: str | None = None

    # Physical description
    physical_description: str | None = None
    distinguishing_features: str | None = None

    # Relationships
    family_background: str | None = None
    relationship_status: str | None = None

    # Character arc tracking
    initial_state: str | None = None
    character_arc: str | None = None
    growth_trajectory: str | None = None

    # Continuity tracking
    first_appearance_episode_id: UUID | None = None
    last_appearance_episode_id: UUID | None = None
    total_appearances: int = 0

    # Notes
    notes: str | None = None

    @field_validator("age")
    @classmethod
    def validate_age(cls, v: int | None) -> int | None:
        """Validate that age is reasonable."""
        if v is not None and (v < 0 or v > 200):
            raise ValueError("Age must be between 0 and 200")
        return v


class WorldElementType(str, Enum):
    """Types of world elements."""

    LOCATION = "location"
    PROP = "prop"
    CONCEPT = "concept"
    RULE = "rule"
    TECHNOLOGY = "technology"
    CULTURE = "culture"


class WorldElement(BaseEntity):
    """Represents a world building element."""

    script_id: UUID
    series_bible_id: UUID | None = None

    # Element classification
    element_type: WorldElementType
    name: str
    category: str | None = None  # subcategory within type

    # Description and rules
    description: str | None = None
    rules_and_constraints: str | None = None
    visual_description: str | None = None

    # Usage tracking
    first_introduced_episode_id: UUID | None = None
    first_introduced_scene_id: UUID | None = None
    usage_frequency: int = 0
    importance_level: int = Field(default=1, ge=1, le=5)  # 1-5 scale

    # Relationships to other elements
    related_locations: list[UUID] = Field(default_factory=list)
    related_characters: list[UUID] = Field(default_factory=list)

    # Continuity tracking
    continuity_notes: str | None = None
    established_rules: dict[str, Any] = Field(default_factory=dict)

    # Notes
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        """Validate that element name is not empty."""
        if not v or not v.strip():
            raise ValueError("Element name cannot be empty")
        return v.strip()


class TimelineType(str, Enum):
    """Types of story timelines."""

    MAIN = "main"
    FLASHBACK = "flashback"
    ALTERNATE = "alternate"
    PARALLEL = "parallel"


class StoryTimeline(BaseEntity):
    """Represents a story timeline."""

    script_id: UUID
    series_bible_id: UUID | None = None

    # Timeline identification
    name: str
    timeline_type: TimelineType = TimelineType.MAIN
    description: str | None = None

    # Temporal boundaries
    start_date: str | None = None  # Story date (can be relative like "Day 1")
    end_date: str | None = None
    duration_description: str | None = None

    # Reference information
    reference_episodes: list[UUID] = Field(default_factory=list)
    reference_scenes: list[UUID] = Field(default_factory=list)

    # Notes
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        """Validate that timeline name is not empty."""
        if not v or not v.strip():
            raise ValueError("Timeline name cannot be empty")
        return v.strip()


class EventType(str, Enum):
    """Types of timeline events."""

    PLOT = "plot"
    CHARACTER = "character"
    WORLD = "world"
    BACKSTORY = "backstory"


class TimelineEvent(BaseEntity):
    """Represents an event in a story timeline."""

    timeline_id: UUID
    script_id: UUID

    # Event identification
    event_name: str
    event_type: EventType = EventType.PLOT
    description: str | None = None

    # Temporal positioning
    story_date: str | None = None  # Date within the story world
    relative_order: int | None = None  # Order within timeline
    duration_minutes: int | None = None  # Event duration

    # References
    scene_id: UUID | None = None
    episode_id: UUID | None = None
    related_characters: list[UUID] = Field(default_factory=list)

    # Continuity tracking
    establishes: list[str] = Field(default_factory=list)  # What this event establishes
    requires: list[str] = Field(default_factory=list)  # What this event requires
    affects: list[str] = Field(default_factory=list)  # What this event affects

    # Notes
    notes: str | None = None

    @field_validator("event_name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        """Validate that event name is not empty."""
        if not v or not v.strip():
            raise ValueError("Event name cannot be empty")
        return v.strip()


class NoteType(str, Enum):
    """Types of continuity notes."""

    ERROR = "error"
    INCONSISTENCY = "inconsistency"
    RULE = "rule"
    REMINDER = "reminder"
    QUESTION = "question"


class NoteSeverity(str, Enum):
    """Severity levels for continuity notes."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NoteStatus(str, Enum):
    """Status of continuity notes."""

    OPEN = "open"
    RESOLVED = "resolved"
    IGNORED = "ignored"
    DEFERRED = "deferred"


class ContinuityNote(BaseEntity):
    """Represents a continuity note or issue."""

    script_id: UUID
    series_bible_id: UUID | None = None

    # Note classification
    note_type: NoteType
    severity: NoteSeverity = NoteSeverity.MEDIUM
    status: NoteStatus = NoteStatus.OPEN

    # Content
    title: str
    description: str
    suggested_resolution: str | None = None

    # References
    episode_id: UUID | None = None
    scene_id: UUID | None = None
    character_id: UUID | None = None
    world_element_id: UUID | None = None
    timeline_event_id: UUID | None = None

    # Related references (for cross-references)
    related_episodes: list[UUID] = Field(default_factory=list)
    related_scenes: list[UUID] = Field(default_factory=list)
    related_characters: list[UUID] = Field(default_factory=list)

    # Tracking
    reported_by: str | None = None
    assigned_to: str | None = None
    resolution_notes: str | None = None
    resolved_at: datetime | None = None

    # Tags
    tags: list[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, v: str) -> str:
        """Validate that note title is not empty."""
        if not v or not v.strip():
            raise ValueError("Note title cannot be empty")
        return v.strip()

    @field_validator("description")
    @classmethod
    def description_must_not_be_empty(cls, v: str) -> str:
        """Validate that note description is not empty."""
        if not v or not v.strip():
            raise ValueError("Note description cannot be empty")
        return v.strip()


class KnowledgeType(str, Enum):
    """Types of character knowledge."""

    FACT = "fact"
    SECRET = "secret"  # noqa: S105  # pragma: allowlist secret - Not a password, it's a knowledge type
    SKILL = "skill"
    RELATIONSHIP = "relationship"
    LOCATION = "location"
    EVENT = "event"


class AcquisitionMethod(str, Enum):
    """Methods of knowledge acquisition."""

    WITNESSED = "witnessed"
    TOLD = "told"
    DISCOVERED = "discovered"
    ASSUMED = "assumed"


class VerificationStatus(str, Enum):
    """Knowledge verification status."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    VIOLATED = "violated"


class CharacterKnowledge(BaseEntity):
    """Represents character knowledge for continuity tracking."""

    character_id: UUID
    script_id: UUID

    # Knowledge details
    knowledge_type: KnowledgeType
    knowledge_subject: str  # What the knowledge is about
    knowledge_description: str | None = None

    # Acquisition tracking
    acquired_episode_id: UUID | None = None
    acquired_scene_id: UUID | None = None
    acquisition_method: AcquisitionMethod | None = None

    # Usage tracking
    first_used_episode_id: UUID | None = None
    first_used_scene_id: UUID | None = None
    usage_count: int = 0

    # Continuity validation
    should_know_before: str | None = (
        None  # Episode/scene where character should know this
    )
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED

    # Metadata
    confidence_level: float = Field(default=1.0, ge=0.0, le=1.0)  # 0.0 to 1.0
    notes: str | None = None

    @field_validator("knowledge_subject")
    @classmethod
    def subject_must_not_be_empty(cls, v: str) -> str:
        """Validate that knowledge subject is not empty."""
        if not v or not v.strip():
            raise ValueError("Knowledge subject cannot be empty")
        return v.strip()


class PlotThreadType(str, Enum):
    """Types of plot threads."""

    MAIN = "main"
    SUBPLOT = "subplot"
    ARC = "arc"
    MYSTERY = "mystery"
    ROMANCE = "romance"


class PlotThreadStatus(str, Enum):
    """Status of plot threads."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"
    SUSPENDED = "suspended"


class PlotThread(BaseEntity):
    """Represents a plot thread or storyline."""

    script_id: UUID
    series_bible_id: UUID | None = None

    # Thread identification
    name: str
    thread_type: PlotThreadType = PlotThreadType.MAIN
    priority: int = Field(default=1, ge=1, le=5)  # 1-5 scale

    # Thread details
    description: str | None = None
    initial_setup: str | None = None
    central_conflict: str | None = None
    resolution: str | None = None

    # Status tracking
    status: PlotThreadStatus = PlotThreadStatus.ACTIVE

    # Episode tracking
    introduced_episode_id: UUID | None = None
    resolved_episode_id: UUID | None = None
    total_episodes_involved: int = 0

    # Character involvement
    primary_characters: list[UUID] = Field(default_factory=list)
    supporting_characters: list[UUID] = Field(default_factory=list)

    # Scene tracking
    key_scenes: list[UUID] = Field(default_factory=list)
    resolution_scenes: list[UUID] = Field(default_factory=list)

    # Notes
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        """Validate that thread name is not empty."""
        if not v or not v.strip():
            raise ValueError("Thread name cannot be empty")
        return v.strip()


# Export all models
__all__ = [
    "AcquisitionMethod",
    "Action",
    "BaseEntity",
    "BibleStatus",
    "BibleType",
    "Character",
    "CharacterAppears",
    "CharacterKnowledge",
    "CharacterProfile",
    "CharacterSpeaksTo",
    "ContinuityNote",
    "Dialogue",
    "EdgeType",
    "ElementType",
    "Episode",
    "EventType",
    "KnowledgeType",
    "Location",
    "NodeType",
    "NoteSeverity",
    "NoteStatus",
    "NoteType",
    "Parenthetical",
    "PlotThread",
    "PlotThreadStatus",
    "PlotThreadType",
    "Relationship",
    "Scene",
    "SceneAtLocation",
    "SceneDependency",
    "SceneDependencyType",
    "SceneElement",
    "SceneFollows",
    "SceneOrderType",
    "Script",
    "Season",
    "SeriesBible",
    "StoryTimeline",
    "TimelineEvent",
    "TimelineType",
    "Transition",
    "VerificationStatus",
    "WorldElement",
    "WorldElementType",
]
