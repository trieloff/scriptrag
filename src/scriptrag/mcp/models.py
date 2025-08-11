"""Shared Pydantic models for MCP tools."""

from typing import Any

from pydantic import BaseModel


# Script Management Models
class ScriptMetadata(BaseModel):
    """Script metadata information."""

    script_id: int
    title: str
    file_path: str
    scene_count: int
    character_count: int
    created_at: str
    updated_at: str | None = None


class ScriptDetail(BaseModel):
    """Detailed script information."""

    script_id: int
    title: str
    file_path: str
    content_hash: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: str
    updated_at: str | None = None


# Scene Models
class SceneSummary(BaseModel):
    """Scene summary information."""

    scene_id: int
    script_id: int
    scene_number: int
    heading: str
    location: str | None = None
    time_of_day: str | None = None
    character_count: int
    dialogue_count: int


class SceneDetail(BaseModel):
    """Detailed scene information."""

    scene_id: int
    script_id: int
    scene_number: int
    heading: str
    location: str | None = None
    time_of_day: str | None = None
    content: str
    characters: list[str]
    metadata: dict[str, Any] | None = None


class DialogueLine(BaseModel):
    """Individual dialogue line."""

    character: str
    text: str
    line_number: int
    metadata: dict[str, Any] | None = None


# Character Models
class CharacterSummary(BaseModel):
    """Character summary information."""

    name: str
    dialogue_count: int
    scene_count: int
    first_appearance_scene: int | None = None
    last_appearance_scene: int | None = None


class CharacterDetail(BaseModel):
    """Detailed character information."""

    name: str
    dialogue_count: int
    scene_count: int
    total_words: int
    average_words_per_line: float
    first_appearance: SceneSummary | None = None
    last_appearance: SceneSummary | None = None
    metadata: dict[str, Any] | None = None


class CharacterInfo(BaseModel):
    """Basic character information."""

    name: str
    total_dialogue_lines: int
    total_scenes: int
    first_appearance: str | None = None
    last_appearance: str | None = None


class CharacterRelationship(BaseModel):
    """Character relationship information."""

    character1: str
    character2: str
    shared_scenes: int
    interaction_count: int
    relationship_type: str | None = None


class CharacterAppearance(BaseModel):
    """Character appearance in a scene."""

    scene_id: int
    scene_number: int
    scene_heading: str
    dialogue_count: int
    is_speaking: bool


# Search Models
class DialogueSearchResult(BaseModel):
    """Dialogue search result."""

    scene_id: int
    script_id: int
    scene_number: int
    character: str
    dialogue: str
    match_score: float | None = None
    context: dict[str, Any] | None = None


class SemanticSearchResult(BaseModel):
    """Semantic search result."""

    content_type: str  # "scene", "dialogue", "action", "bible"
    content_id: int
    content: str
    similarity_score: float
    metadata: dict[str, Any] | None = None


class BibleSearchResult(BaseModel):
    """Bible search result."""

    bible_id: int
    script_id: int
    content: str
    similarity_score: float
    chunk_index: int | None = None


class SearchQueryInfo(BaseModel):
    """Search query information."""

    query: str
    search_type: str
    filters_applied: dict[str, Any] | None = None
    execution_time_ms: float | None = None


# Analysis Models
class AgentInfo(BaseModel):
    """Analysis agent information."""

    name: str
    category: str | None = None
    description: str
    is_builtin: bool
    parameters: dict[str, Any] | None = None


class DialogueStats(BaseModel):
    """Dialogue statistics for a character."""

    total_lines: int
    total_words: int
    average_words_per_line: float
    longest_line_words: int
    shortest_line_words: int
    vocabulary_size: int | None = None


class SceneAppearance(BaseModel):
    """Scene appearance information."""

    scene_id: int
    scene_number: int
    scene_heading: str
    dialogue_count: int
    action_mentions: int


class ScriptInfo(BaseModel):
    """Basic script information."""

    script_id: int
    title: str
    total_scenes: int
    total_characters: int
