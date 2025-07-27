"""Base classes for the ScriptRAG Mentors System.

This module defines the abstract base classes and data models that all mentors
must implement. The design follows the plugin architecture pattern with
standardized interfaces for analysis results.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class MentorType(str, Enum):
    """Types of mentors available in the system."""

    STORY_STRUCTURE = "story_structure"  # Save the Cat, Hero's Journey, etc.
    CHARACTER_ARC = "character_arc"  # Character development analysis
    DIALOGUE = "dialogue"  # Dialogue quality and style
    PACING = "pacing"  # Pacing and rhythm analysis
    THEME = "theme"  # Thematic analysis
    GENRE = "genre"  # Genre-specific conventions
    FORMATTING = "formatting"  # Fountain format compliance


class AnalysisSeverity(str, Enum):
    """Severity levels for analysis findings."""

    INFO = "info"  # Informational note
    SUGGESTION = "suggestion"  # Mild suggestion for improvement
    WARNING = "warning"  # Issue that should be addressed
    ERROR = "error"  # Significant problem requiring attention


class MentorAnalysis(BaseModel):
    """Individual analysis finding from a mentor."""

    id: UUID = Field(default_factory=uuid4)
    title: str = Field(..., description="Brief title of the analysis finding")
    description: str = Field(..., description="Detailed description of the finding")
    severity: AnalysisSeverity = Field(..., description="Severity level of the finding")

    # Location information
    scene_id: UUID | None = Field(None, description="Scene this analysis applies to")
    character_id: UUID | None = Field(
        None, description="Character this analysis applies to"
    )
    element_id: UUID | None = Field(
        None, description="Scene element this analysis applies to"
    )

    # Analysis metadata
    category: str = Field(
        ..., description="Category of analysis (e.g., 'beat_sheet', 'character_arc')"
    )
    mentor_name: str = Field(
        ..., description="Name of the mentor that generated this analysis"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence in the analysis"
    )

    # Recommendations
    recommendations: list[str] = Field(
        default_factory=list, description="Specific recommendations"
    )
    examples: list[str] = Field(
        default_factory=list, description="Examples to illustrate the point"
    )

    # Additional data
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional mentor-specific data"
    )

    model_config = ConfigDict(
        json_encoders={
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }
    )


class MentorResult(BaseModel):
    """Complete analysis result from a mentor."""

    id: UUID = Field(default_factory=uuid4)
    mentor_name: str = Field(
        ..., description="Name of the mentor that performed the analysis"
    )
    mentor_version: str = Field(..., description="Version of the mentor")
    script_id: UUID = Field(..., description="Script that was analyzed")

    # Analysis results
    analyses: list[MentorAnalysis] = Field(
        default_factory=list, description="Individual findings"
    )
    summary: str = Field(..., description="Overall summary of the analysis")
    score: float | None = Field(
        None, ge=0.0, le=100.0, description="Overall score (0-100)"
    )

    # Analysis metadata
    analysis_date: datetime = Field(default_factory=datetime.utcnow)
    execution_time_ms: int | None = Field(
        None, description="Time taken to perform analysis"
    )

    # Configuration used
    config: dict[str, Any] = Field(
        default_factory=dict, description="Configuration used for analysis"
    )

    model_config = ConfigDict(
        json_encoders={
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }
    )

    @property
    def error_count(self) -> int:
        """Count of error-level findings."""
        return len([a for a in self.analyses if a.severity == AnalysisSeverity.ERROR])

    @property
    def warning_count(self) -> int:
        """Count of warning-level findings."""
        return len([a for a in self.analyses if a.severity == AnalysisSeverity.WARNING])

    @property
    def suggestion_count(self) -> int:
        """Count of suggestion-level findings."""
        return len(
            [a for a in self.analyses if a.severity == AnalysisSeverity.SUGGESTION]
        )

    def get_analyses_by_category(self, category: str) -> list[MentorAnalysis]:
        """Get all analyses for a specific category."""
        return [a for a in self.analyses if a.category == category]

    def get_analyses_by_scene(self, scene_id: UUID) -> list[MentorAnalysis]:
        """Get all analyses for a specific scene."""
        return [a for a in self.analyses if a.scene_id == scene_id]


class BaseMentor(ABC):
    """Abstract base class for all mentors.

    Mentors analyze screenplays and provide feedback based on various storytelling
    frameworks. Each mentor should inherit from this base class and implement
    the required abstract methods.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the mentor with optional configuration.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self._version = "1.0.0"  # Default version, should be overridden

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name identifier for this mentor."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this mentor analyzes."""
        pass

    @property
    @abstractmethod
    def mentor_type(self) -> MentorType:
        """Type category this mentor belongs to."""
        pass

    @property
    def version(self) -> str:
        """Version of this mentor implementation."""
        return self._version

    @property
    def categories(self) -> list[str]:
        """Categories of analysis this mentor provides.

        Should be overridden by subclasses to specify what categories
        of analysis they provide (e.g., ['beat_sheet', 'catalyst']).
        """
        return ["general"]

    @abstractmethod
    async def analyze_script(
        self,
        script_id: UUID,
        db_operations: Any,  # Type hint for database operations
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> MentorResult:
        """Analyze a complete script and return results.

        Args:
            script_id: UUID of the script to analyze
            db_operations: Database operations interface for querying script data
            progress_callback: Optional callback for progress updates (0.0 to 1.0)

        Returns:
            Complete analysis result
        """
        pass

    async def analyze_scene(
        self,
        scene_id: UUID,  # noqa: ARG002
        script_id: UUID,  # noqa: ARG002
        db_operations: Any,  # noqa: ARG002
        _context: dict[str, Any] | None = None,
    ) -> list[MentorAnalysis]:
        """Analyze a single scene and return findings.

        Optional method that mentors can override to provide scene-level analysis.
        Default implementation returns empty list.

        Args:
            scene_id: UUID of the scene to analyze
            script_id: UUID of the parent script
            db_operations: Database operations interface
            _context: Optional context data for the analysis

        Returns:
            List of analysis findings for the scene
        """
        return []

    async def analyze_character(
        self,
        character_id: UUID,  # noqa: ARG002
        script_id: UUID,  # noqa: ARG002
        db_operations: Any,  # noqa: ARG002
        _context: dict[str, Any] | None = None,
    ) -> list[MentorAnalysis]:
        """Analyze a character and return findings.

        Optional method that mentors can override to provide character-level analysis.
        Default implementation returns empty list.

        Args:
            character_id: UUID of the character to analyze
            script_id: UUID of the parent script
            db_operations: Database operations interface
            _context: Optional context data for the analysis

        Returns:
            List of analysis findings for the character
        """
        return []

    def validate_config(self) -> bool:
        """Validate the mentor's configuration.

        Should be overridden by subclasses that require specific configuration.

        Returns:
            True if configuration is valid, False otherwise
        """
        return True

    def get_config_schema(self) -> dict[str, Any]:
        """Get the configuration schema for this mentor.

        Should be overridden by subclasses to provide configuration schema.

        Returns:
            JSON schema for the mentor's configuration
        """
        return {"type": "object", "properties": {}, "additionalProperties": True}

    def __str__(self) -> str:
        """String representation of the mentor."""
        return f"{self.name} v{self.version} ({self.mentor_type.value})"

    def __repr__(self) -> str:
        """Detailed string representation of the mentor."""
        return (
            f"<{self.__class__.__name__}(name='{self.name}', version='{self.version}')>"
        )
