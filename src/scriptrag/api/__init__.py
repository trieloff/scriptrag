"""ScriptRAG API module."""

from scriptrag.api.analyze import AnalyzeCommand
from scriptrag.api.analyze_results import AnalyzeResult, FileResult
from scriptrag.api.database import DatabaseInitializer
from scriptrag.api.database_operations import DatabaseOperations, ScriptRecord
from scriptrag.api.index import IndexCommand, IndexOperationResult, IndexResult
from scriptrag.api.list import FountainMetadata, ScriptLister
from scriptrag.api.query import QueryAPI

__all__ = [
    "AnalyzeCommand",
    "AnalyzeResult",
    "DatabaseInitializer",
    "DatabaseOperations",
    "FileResult",
    "FountainMetadata",
    "IndexCommand",
    "IndexOperationResult",
    "IndexResult",
    "QueryAPI",
    "ScriptLister",
    "ScriptRecord",
]
