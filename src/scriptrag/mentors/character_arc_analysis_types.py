"""Character Arc Analysis Type Definitions.

This module contains TypedDict definitions for various analysis data
structures used in character arc evaluation.
"""

from __future__ import annotations

from typing import Any, TypedDict


class MentorCandidate(TypedDict):
    """Type definition for mentor candidate data."""

    character: dict[str, Any]
    score: int
    teaching_moments: list[dict[str, str]]


class ShadowCandidate(TypedDict):
    """Type definition for shadow/antagonist candidate data."""

    character: dict[str, Any]
    score: int
    mirror_moments: list[dict[str, str]]
    direct_conflicts: list[str]


class RomanceCandidate(TypedDict):
    """Type definition for romance candidate data."""

    character: dict[str, Any]
    score: int
    romantic_moments: list[dict[str, str]]
    growth_catalysts: list[str]
