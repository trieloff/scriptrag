"""Data models for Fountain screenplay parsing."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Dialogue:
    """Represents a dialogue entry."""

    character: str
    text: str
    parenthetical: str | None = None


@dataclass
class Scene:
    """Represents a scene in a screenplay."""

    number: int
    heading: str
    content: str
    original_text: str
    content_hash: str
    type: str = "INT"  # INT or EXT
    location: str = ""
    time_of_day: str = ""
    dialogue_lines: list[Dialogue] = field(default_factory=list)
    action_lines: list[str] = field(default_factory=list)
    boneyard_metadata: dict[str, Any] | None = None
    has_new_metadata: bool = False

    def update_boneyard(self, metadata: dict[str, Any]) -> None:
        """Update the boneyard metadata for this scene."""
        if self.boneyard_metadata is None:
            self.boneyard_metadata = {}
        self.boneyard_metadata.update(metadata)
        self.has_new_metadata = True


@dataclass
class Script:
    """Represents a parsed screenplay."""

    title: str | None
    author: str | None
    scenes: list[Scene]
    metadata: dict[str, Any] = field(default_factory=dict)
