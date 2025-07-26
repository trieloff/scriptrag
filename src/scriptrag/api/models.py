"""Simplified models for API operations."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SceneModel(BaseModel):
    """Scene model for API operations."""

    id: int | None = None
    script_id: int | None = None
    scene_number: int
    heading: str
    content: str
    characters: list[str] = Field(default_factory=list)
    page_start: float | None = None
    page_end: float | None = None
    metadata: dict[str, Any] | None = None
    embedding: list[float] | None = None


class ScriptModel(BaseModel):
    """Script model for API operations."""

    id: int | None = None
    title: str
    author: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    scenes: list[SceneModel] = Field(default_factory=list)
    characters: set[str] = Field(default_factory=set)
