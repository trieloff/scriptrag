"""Search functionality for ScriptRAG.

This module provides comprehensive search capabilities including text-based,
entity-based, semantic, and temporal search across screenplay content.
"""

from .interface import SearchInterface
from .ranking import SearchRanker
from .text_search import TextSearchEngine
from .types import SearchResult, SearchResults, SearchType

__all__ = [
    "SearchInterface",
    "SearchRanker",
    "SearchResult",
    "SearchResults",
    "SearchType",
    "TextSearchEngine",
]
