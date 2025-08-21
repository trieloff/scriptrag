"""Utility type definitions."""

import logging
from typing import Any, TypeAlias

# Logger types
Logger: TypeAlias = logging.Logger

# Generic utility types
JSONData: TypeAlias = dict[str, Any]
Metadata: TypeAlias = dict[str, Any]
ConfigData: TypeAlias = dict[str, Any]

# Path and file types
FilePath: TypeAlias = str
DirectoryPath: TypeAlias = str
