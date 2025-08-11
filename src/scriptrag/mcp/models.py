"""Shared type definitions for MCP tools."""

from typing import Any, TypedDict


# Script Management Types
class ScriptMetadata(TypedDict):
    """Script metadata information."""

    script_id: int
    title: str
    file_path: str
    scene_count: int
    character_count: int
    created_at: str
    updated_at: str | None


class ScriptDetail(TypedDict):
    """Detailed script information."""

    script_id: int
    title: str
    file_path: str
    content_hash: str | None
    metadata: dict[str, Any] | None
    created_at: str
    updated_at: str | None


# Scene Types
class SceneSummary(TypedDict):
    """Scene summary information."""

    scene_id: int
    script_id: int
    scene_number: int
    heading: str
    location: str | None
    time_of_day: str | None
    character_count: int
    dialogue_count: int


class SceneDetail(TypedDict):
    """Detailed scene information."""

    scene_id: int
    script_id: int
    scene_number: int
    heading: str
    location: str | None
    time_of_day: str | None
    content: str
    characters: list[str]
    metadata: dict[str, Any] | None


class DialogueLine(TypedDict):
    """Individual dialogue line."""

    character: str
    text: str
    line_number: int
    metadata: dict[str, Any] | None


# Character Types
class CharacterSummary(TypedDict):
    """Character summary information."""

    name: str
    dialogue_count: int
    scene_count: int
    first_appearance_scene: int | None
    last_appearance_scene: int | None


class CharacterDetail(TypedDict):
    """Detailed character information."""

    name: str
    dialogue_count: int
    scene_count: int
    total_words: int
    average_words_per_line: float
    first_appearance: SceneSummary | None
    last_appearance: SceneSummary | None
    metadata: dict[str, Any] | None


class CharacterInfo(TypedDict):
    """Basic character information."""

    name: str
    total_dialogue_lines: int
    total_scenes: int
    first_appearance: str | None
    last_appearance: str | None


class CharacterRelationship(TypedDict):
    """Character relationship information."""

    character1: str
    character2: str
    shared_scenes: int
    interaction_count: int
    relationship_type: str | None


class CharacterAppearance(TypedDict):
    """Character appearance in a scene."""

    scene_id: int
    scene_number: int
    scene_heading: str
    dialogue_count: int
    is_speaking: bool


# Search Types
class DialogueSearchResult(TypedDict):
    """Dialogue search result."""

    scene_id: int
    script_id: int
    scene_number: int
    character: str
    dialogue: str
    match_score: float | None
    context: dict[str, Any] | None


class SemanticSearchResult(TypedDict):
    """Semantic search result."""

    content_type: str  # "scene", "dialogue", "action", "bible"
    content_id: int
    content: str
    similarity_score: float
    metadata: dict[str, Any] | None


class BibleSearchResult(TypedDict):
    """Bible search result."""

    bible_id: int
    script_id: int
    content: str
    similarity_score: float
    chunk_index: int | None


class SearchQueryInfo(TypedDict):
    """Search query information."""

    query: str
    search_type: str
    filters_applied: dict[str, Any] | None
    execution_time_ms: float | None


# Analysis Types
class AgentInfo(TypedDict):
    """Analysis agent information."""

    name: str
    category: str | None
    description: str
    is_builtin: bool
    parameters: dict[str, Any] | None


class DialogueStats(TypedDict):
    """Dialogue statistics for a character."""

    total_lines: int
    total_words: int
    average_words_per_line: float
    longest_line_words: int
    shortest_line_words: int
    vocabulary_size: int | None


class SceneAppearance(TypedDict):
    """Scene appearance information."""

    scene_id: int
    scene_number: int
    scene_heading: str
    dialogue_count: int
    action_mentions: int


class ScriptInfo(TypedDict):
    """Basic script information."""

    script_id: int
    title: str
    total_scenes: int
    total_characters: int
