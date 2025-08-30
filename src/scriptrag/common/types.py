"""Common type definitions used across ScriptRAG modules."""

from __future__ import annotations

from typing import TypeAlias

# JSON-compatible types
JSONValue: TypeAlias = (
    str | int | float | bool | None | dict[str, "JSONValue"] | list["JSONValue"]
)
JSONDict: TypeAlias = dict[str, JSONValue]

# Database row types
DatabaseRow: TypeAlias = dict[str, str | int | float | bool | None]

# Configuration types
ConfigValue: TypeAlias = str | int | float | bool | list[str] | dict[str, str]
ConfigDict: TypeAlias = dict[str, ConfigValue]
