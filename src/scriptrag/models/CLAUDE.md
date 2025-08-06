# Data Models

This directory contains all data models and type definitions used throughout ScriptRAG. These models ensure type safety and consistent data structures.

## Architecture Role

The models provide:

- Type-safe data structures for all entities
- Validation of data integrity
- Serialization/deserialization support
- Clear contracts between components

## Core Models

```python
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import hashlib

@dataclass
class DialogueLine:
    """A line of dialogue in a scene."""
    character: str
    text: str
    parenthetical: Optional[str] = None

    def __str__(self) -> str:
        if self.parenthetical:
            return f"{self.character}\n({self.parenthetical})\n{self.text}"
        return f"{self.character}\n{self.text}"

@dataclass
class Scene:
    """A scene in a screenplay."""
    content_hash: str
    type: str  # INT or EXT
    location: str
    time_of_day: Optional[str] = None
    scene_number: Optional[int] = None
    action_text: Optional[str] = None
    dialogue_lines: List[DialogueLine] = field(default_factory=list)
    original_text: str = ""
    boneyard_metadata: Optional[Dict[str, Any]] = None

    @property
    def has_dialogue(self) -> bool:
        return len(self.dialogue_lines) > 0

    @property
    def characters(self) -> List[str]:
        """Get unique characters in scene."""
        return list(set(d.character for d in self.dialogue_lines))

    def calculate_hash(self) -> str:
        """Calculate content hash for scene."""
        content = f"{self.type}|{self.location}|{self.time_of_day or ''}|"
        content += self.action_text or ""
        content += "|".join(str(d) for d in self.dialogue_lines)

        return hashlib.sha256(content.encode()).hexdigest()[:16]

@dataclass
class Script:
    """A screenplay script."""
    id: str  # Usually file path
    title: str
    file_path: Path
    format_type: str = "feature"  # feature, tv
    series_id: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    movie_number: Optional[int] = None  # For franchises
    scenes: List[Scene] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_modified: Optional[datetime] = None

    @property
    def scene_count(self) -> int:
        return len(self.scenes)

    def get_scene_by_number(self, number: int) -> Optional[Scene]:
        """Get scene by scene number."""
        for scene in self.scenes:
            if scene.scene_number == number:
                return scene
        return None
```

## Character Models

```python
@dataclass
class Character:
    """A character in a series."""
    character_id: str  # {series_id}:{name}
    series_id: str
    name: str
    normalized_name: str
    aliases: List[str] = field(default_factory=list)
    bible_path: Optional[Path] = None
    bible_embedding_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_name(cls, name: str, series_id: str) -> "Character":
        """Create character from name and series."""
        normalized = cls.normalize_name(name)
        return cls(
            character_id=f"{series_id}:{normalized}",
            series_id=series_id,
            name=name,
            normalized_name=normalized
        )

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize character name."""
        # Remove parentheticals like (V.O.) or (CONT'D)
        import re
        name = re.sub(r'\([^)]+\)', '', name).strip()
        return name.upper()

@dataclass
class CharacterAppearance:
    """A character's appearance in a scene."""
    character_id: str
    scene_hash: str
    dialogue_count: int = 0
    mentioned: bool = False

    @property
    def speaks(self) -> bool:
        return self.dialogue_count > 0
```

## Series Models

```python
@dataclass
class Series:
    """A TV series or film franchise."""
    series_id: str
    title: str
    type: str  # tv, feature
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Validate type
        if self.type not in ["tv", "feature"]:
            raise ValueError(f"Invalid series type: {self.type}")
```

## Search Models

```python
@dataclass
class SearchQuery:
    """A search query."""
    text: str
    search_type: str = "hybrid"  # dialogue, semantic, hybrid
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: int = 10
    offset: int = 0

    def with_filter(self, key: str, value: Any) -> "SearchQuery":
        """Add a filter to the query."""
        self.filters[key] = value
        return self

@dataclass
class SearchResult:
    """A search result."""
    scene: Scene
    score: float
    match_type: str  # dialogue, semantic, hybrid
    highlights: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: "SearchResult") -> bool:
        """Sort by score descending."""
        return self.score > other.score
```

## Metadata Models

```python
@dataclass
class ExtractedMetadata:
    """Metadata extracted by insight agents."""
    content_hash: str
    characters_present: List[str] = field(default_factory=list)
    props: List[str] = field(default_factory=list)
    emotional_tone: Optional[str] = None
    themes: List[str] = field(default_factory=list)
    story_function: Optional[str] = None
    custom_properties: Dict[str, Any] = field(default_factory=dict)

    def merge(self, property_name: str, value: Any) -> None:
        """Merge a property from an agent."""
        if property_name in self.__annotations__:
            # Standard property
            setattr(self, property_name, value)
        else:
            # Custom property
            self.custom_properties[property_name] = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        result = {
            "content_hash": self.content_hash,
            "characters_present": self.characters_present,
            "props": self.props,
            "emotional_tone": self.emotional_tone,
            "themes": self.themes,
            "story_function": self.story_function
        }
        result.update(self.custom_properties)
        return result
```

## Embedding Models

```python
@dataclass
class Embedding:
    """An embedding vector for a scene."""
    content_hash: str
    file_path: str  # Path in Git LFS
    dimensions: int
    model_version: str
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def filename(self) -> str:
        """Get the filename from path."""
        return Path(self.file_path).name
```

## Change Tracking Models

```python
@dataclass
class ChangeSet:
    """Changes detected in fountain files."""
    added: set[str] = field(default_factory=set)  # Content hashes
    removed: set[str] = field(default_factory=set)
    modified_files: set[Path] = field(default_factory=set)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed)

    def merge(self, other: "ChangeSet") -> None:
        """Merge another changeset into this one."""
        self.added.update(other.added)
        self.removed.update(other.removed)
        self.modified_files.update(other.modified_files)
```

## Type Aliases

```python
from typing import NewType

# Type aliases for clarity
ScriptID = NewType('ScriptID', str)
SceneHash = NewType('SceneHash', str)
CharacterID = NewType('CharacterID', str)
SeriesID = NewType('SeriesID', str)

# File types
class FileType:
    FOUNTAIN = "fountain"
    BIBLE = "bible"
    AGENT = "agent"
```

## Validation

All models include validation in their `__post_init__` methods:

```python
def __post_init__(self):
    """Validate model after initialization."""
    if not self.content_hash:
        raise ValueError("Scene must have content_hash")

    if self.type not in ["INT", "EXT"]:
        raise ValueError(f"Invalid scene type: {self.type}")

    if not self.location:
        raise ValueError("Scene must have location")
```

## Testing

Each model should have comprehensive tests:

- Initialization tests
- Validation tests  
- Serialization/deserialization tests
- Property calculation tests
- Edge case handling
