"""ScriptRAG API module.

This module provides the main API components for ScriptRAG:
- AnalyzeCommand: Command for analyzing scripts
- AnalyzeResult, FileResult: Results from script analysis
- DatabaseInitializer: Initialize and manage the database
- DatabaseOperations, ScriptRecord: Database operations and records
- IndexCommand, IndexResult, IndexOperationResult: Indexing operations
- FountainMetadata, ScriptLister: Script listing and metadata
- QueryAPI: Query interface for the database
"""

from scriptrag.api.analyze import AnalyzeCommand as AnalyzeCommand
from scriptrag.api.analyze_results import AnalyzeResult as AnalyzeResult
from scriptrag.api.analyze_results import FileResult as FileResult
from scriptrag.api.database import DatabaseInitializer as DatabaseInitializer
from scriptrag.api.database_operations import DatabaseOperations as DatabaseOperations
from scriptrag.api.db_script_ops import ScriptRecord as ScriptRecord
from scriptrag.api.index import IndexCommand as IndexCommand
from scriptrag.api.index import IndexOperationResult as IndexOperationResult
from scriptrag.api.index import IndexResult as IndexResult
from scriptrag.api.list import FountainMetadata as FountainMetadata
from scriptrag.api.list import ScriptLister as ScriptLister
from scriptrag.api.query import QueryAPI as QueryAPI

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
