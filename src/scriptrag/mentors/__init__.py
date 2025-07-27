"""ScriptRAG Mentors System.

This module provides the pluggable mentors infrastructure for automated screenplay
analysis based on established storytelling frameworks. The system includes:

1. Base classes for creating custom mentors
2. Registry system for managing mentor plugins
3. Database integration for storing analysis results
4. CLI and MCP integration points

Mentors analyze screenplays and provide feedback based on various storytelling
frameworks like Save the Cat, Hero's Journey, etc.
"""

from scriptrag.mentors.base import (
    AnalysisSeverity,
    BaseMentor,
    MentorAnalysis,
    MentorResult,
)
from scriptrag.mentors.database import MentorDatabaseOperations
from scriptrag.mentors.registry import MentorRegistry, get_mentor_registry

__all__ = [
    "AnalysisSeverity",
    "BaseMentor",
    "MentorAnalysis",
    "MentorDatabaseOperations",
    "MentorRegistry",
    "MentorResult",
    "get_mentor_registry",
]
