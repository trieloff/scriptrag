"""Data models for scene management API."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from scriptrag.parser import Scene


@dataclass
class SceneIdentifier:
    """Unique identifier for scenes in hierarchical projects."""

    project: str
    scene_number: int
    season: int | None = None
    episode: int | None = None

    @property
    def key(self) -> str:
        """Generate unique key for scene identification."""
        if self.season is not None and self.episode is not None:
            return (
                f"{self.project}:S{self.season:02d}E{self.episode:02d}:"
                f"{self.scene_number:03d}"
            )
        return f"{self.project}:{self.scene_number:03d}"

    @classmethod
    def from_string(cls, key: str) -> "SceneIdentifier":
        """Parse scene identifier from string key."""
        parts = key.split(":")
        if len(parts) == 2:
            # Feature film format: "project:scene"
            return cls(
                project=parts[0],
                scene_number=int(parts[1]),
            )
        if len(parts) == 3:
            # TV format: "project:S##E##:scene"
            season_episode = parts[1]
            if season_episode.startswith("S") and "E" in season_episode:
                season_str, episode_str = season_episode[1:].split("E")
                return cls(
                    project=parts[0],
                    season=int(season_str),
                    episode=int(episode_str),
                    scene_number=int(parts[2]),
                )
        raise ValueError(f"Invalid scene key format: {key}")


@dataclass
class ValidationResult:
    """Result of scene content validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    parsed_scene: Scene | None = None


@dataclass
class ReadSceneResult:
    """Result of reading a scene."""

    success: bool
    error: str | None
    scene: Scene | None
    last_read: datetime | None = None


@dataclass
class UpdateSceneResult:
    """Result of updating a scene."""

    success: bool
    error: str | None
    updated_scene: Scene | None = None
    validation_errors: list[str] = field(default_factory=list)


@dataclass
class AddSceneResult:
    """Result of adding a scene."""

    success: bool
    error: str | None
    created_scene: Scene | None = None
    renumbered_scenes: list[int] = field(default_factory=list)


@dataclass
class DeleteSceneResult:
    """Result of deleting a scene."""

    success: bool
    error: str | None
    renumbered_scenes: list[int] = field(default_factory=list)


@dataclass
class BibleReadResult:
    """Result of reading script bible content."""

    success: bool
    error: str | None
    bible_files: list[dict[str, Any]] = field(default_factory=list)
    content: str | None = None
