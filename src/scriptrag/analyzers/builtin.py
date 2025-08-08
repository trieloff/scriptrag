"""Built-in scene analyzers for ScriptRAG."""

from .base import BaseSceneAnalyzer

# Registry of built-in analyzers - now empty as all analyzers are markdown-based
BUILTIN_ANALYZERS: dict[str, type[BaseSceneAnalyzer]] = {}
