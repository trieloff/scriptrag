"""ScriptRAG Database Package.

This package provides the SQLite-based graph database functionality for ScriptRAG.
It includes schema management, graph operations, and query interfaces for
screenplay data storage and retrieval.
"""

from .connection import DatabaseConnection
from .content_extractor import ContentExtractor
from .embedding_pipeline import (
    EmbeddingPipeline,
    create_script_embeddings,
    search_screenplay_content,
)
from .embeddings import (
    EmbeddingContent,
    EmbeddingError,
    EmbeddingManager,
    EmbeddingResult,
)
from .graph import GraphDatabase
from .migrations import MigrationRunner, initialize_database
from .operations import GraphOperations
from .schema import DatabaseSchema, create_database, migrate_database
from .utils import (
    DatabaseBackup,
    DatabaseMaintenance,
    DatabaseStats,
    export_data_to_json,
    get_database_health_report,
)

__all__ = [
    "ContentExtractor",
    "DatabaseBackup",
    "DatabaseConnection",
    "DatabaseMaintenance",
    "DatabaseSchema",
    "DatabaseStats",
    "EmbeddingContent",
    "EmbeddingError",
    "EmbeddingManager",
    "EmbeddingPipeline",
    "EmbeddingResult",
    "GraphDatabase",
    "GraphOperations",
    "MigrationRunner",
    "create_database",
    "create_script_embeddings",
    "export_data_to_json",
    "get_database_health_report",
    "initialize_database",
    "migrate_database",
    "search_screenplay_content",
]
