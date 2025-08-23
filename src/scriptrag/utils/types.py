"""Utility type definitions."""

from typing import Any, TypeAlias

# Generic utility types
JSONData: TypeAlias = dict[str, Any]
Metadata: TypeAlias = dict[str, Any]
ConfigData: TypeAlias = dict[str, Any]

# Path and file types
FilePath: TypeAlias = str
DirectoryPath: TypeAlias = str
