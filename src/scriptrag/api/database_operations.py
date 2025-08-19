"""Database operations for indexing scripts into ScriptRAG database.

This module serves as the main interface for database operations, delegating
to specialized modules for connection management, script operations, scene
operations, and embedding operations.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from scriptrag.api.db_connection import DatabaseConnectionManager
from scriptrag.api.db_embedding_ops import EmbeddingOperations
from scriptrag.api.db_scene_ops import SceneOperations
from scriptrag.api.db_script_ops import ScriptOperations, ScriptRecord
from scriptrag.config import ScriptRAGSettings
from scriptrag.parser import Dialogue, Scene, Script

# Re-export ScriptRecord for backward compatibility
__all__ = ["DatabaseOperations", "ScriptRecord"]


class DatabaseOperations:
    """Handles all database operations for indexing.

    This class coordinates between specialized operation modules to provide
    a unified interface for database operations.
    """

    def __init__(self, settings: ScriptRAGSettings) -> None:
        """Initialize database operations with settings.

        Args:
            settings: Configuration settings for database connection
        """
        self.settings = settings
        self.db_path = settings.database_path

        # Initialize specialized operation handlers
        self._conn_manager = DatabaseConnectionManager(settings)
        self._script_ops = ScriptOperations()
        self._scene_ops = SceneOperations()
        self._embedding_ops = EmbeddingOperations()

    # Connection management - delegate to connection manager
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper configuration.

        Returns:
            Configured SQLite connection
        """
        return self._conn_manager.get_connection()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a transactional database context.

        Yields:
            Database connection within a transaction context
        """
        with self._conn_manager.transaction() as conn:
            yield conn

    def check_database_exists(self) -> bool:
        """Check if the database exists and is initialized.

        Returns:
            True if database exists and has schema, False otherwise
        """
        return self._conn_manager.check_database_exists()

    # Script operations - delegate to script operations module
    def get_existing_script(
        self, conn: sqlite3.Connection, file_path: Path
    ) -> ScriptRecord | None:
        """Get existing script record by file path.

        Args:
            conn: Database connection
            file_path: Path to the script file

        Returns:
            ScriptRecord if found, None otherwise
        """
        return self._script_ops.get_existing_script(conn, file_path)

    def upsert_script(
        self, conn: sqlite3.Connection, script: Script, file_path: Path
    ) -> int:
        """Insert or update script record using file_path as unique key.

        Args:
            conn: Database connection
            script: Script object to store
            file_path: Path to the script file

        Returns:
            ID of the inserted or updated script
        """
        return self._script_ops.upsert_script(conn, script, file_path)

    def clear_script_data(self, conn: sqlite3.Connection, script_id: int) -> None:
        """Clear all existing data for a script before re-indexing.

        Args:
            conn: Database connection
            script_id: ID of the script to clear
        """
        self._script_ops.clear_script_data(conn, script_id)

    def get_script_stats(
        self, conn: sqlite3.Connection, script_id: int
    ) -> dict[str, int]:
        """Get statistics for an indexed script.

        Args:
            conn: Database connection
            script_id: ID of the script

        Returns:
            Dictionary with counts of scenes, characters, dialogues, and actions
        """
        return self._script_ops.get_script_stats(conn, script_id)

    # Scene operations - delegate to scene operations module
    def upsert_scene(
        self, conn: sqlite3.Connection, scene: Scene, script_id: int
    ) -> tuple[int, bool]:
        """Insert or update scene record.

        Args:
            conn: Database connection
            scene: Scene object to store
            script_id: ID of the parent script

        Returns:
            Tuple of (scene_id, content_changed) where content_changed is True
            if the scene content has changed
        """
        return self._scene_ops.upsert_scene(conn, scene, script_id)

    def upsert_characters(
        self, conn: sqlite3.Connection, script_id: int, characters: set[str]
    ) -> dict[str, int]:
        """Insert or update character records.

        Args:
            conn: Database connection
            script_id: ID of the parent script
            characters: Set of character names

        Returns:
            Mapping of character names to their IDs
        """
        return self._scene_ops.upsert_characters(conn, script_id, characters)

    def clear_scene_content(self, conn: sqlite3.Connection, scene_id: int) -> None:
        """Clear dialogues and actions for a scene before re-inserting.

        Args:
            conn: Database connection
            scene_id: ID of the scene to clear
        """
        self._scene_ops.clear_scene_content(conn, scene_id)

    def insert_dialogues(
        self,
        conn: sqlite3.Connection,
        scene_id: int,
        dialogues: list[Dialogue],
        character_map: dict[str, int],
    ) -> int:
        """Insert dialogue records.

        Args:
            conn: Database connection
            scene_id: ID of the parent scene
            dialogues: List of dialogue objects
            character_map: Mapping of character names to IDs

        Returns:
            Number of dialogues inserted
        """
        return self._scene_ops.insert_dialogues(
            conn, scene_id, dialogues, character_map
        )

    def insert_actions(
        self, conn: sqlite3.Connection, scene_id: int, actions: list[str]
    ) -> int:
        """Insert action records.

        Args:
            conn: Database connection
            scene_id: ID of the parent scene
            actions: List of action text lines

        Returns:
            Number of actions inserted
        """
        return self._scene_ops.insert_actions(conn, scene_id, actions)

    # Embedding operations - delegate to embedding operations module
    def upsert_embedding(
        self,
        conn: sqlite3.Connection,
        entity_type: str,
        entity_id: int,
        embedding_model: str,
        embedding_data: bytes | None = None,
        embedding_path: str | None = None,
    ) -> int:
        """Insert or update embedding record.

        Args:
            conn: Database connection
            entity_type: Type of entity ('scene', 'character', etc.)
            entity_id: ID of the entity
            embedding_model: Model used to generate embedding
            embedding_data: Binary embedding data (if storing directly)
            embedding_path: Path to embedding file in Git LFS (if storing reference)

        Returns:
            ID of the inserted or updated embedding
        """
        return self._embedding_ops.upsert_embedding(
            conn,
            entity_type,
            entity_id,
            embedding_model,
            embedding_data,
            embedding_path,
        )

    def get_scene_embeddings(
        self,
        conn: sqlite3.Connection,
        script_id: int,
        embedding_model: str,
    ) -> list[tuple[int, bytes]]:
        """Get all scene embeddings for a script.

        Args:
            conn: Database connection
            script_id: ID of the script
            embedding_model: Model used for embeddings

        Returns:
            List of (scene_id, embedding_data) tuples
        """
        return self._embedding_ops.get_scene_embeddings(
            conn, script_id, embedding_model
        )

    def get_embedding(
        self,
        conn: sqlite3.Connection,
        entity_type: str,
        entity_id: int,
        embedding_model: str,
    ) -> bytes | None:
        """Get embedding for a specific entity.

        Args:
            conn: Database connection
            entity_type: Type of entity ('scene', 'character', etc.)
            entity_id: ID of the entity
            embedding_model: Model used for embedding

        Returns:
            Binary embedding data if found, None otherwise
        """
        return self._embedding_ops.get_embedding(
            conn, entity_type, entity_id, embedding_model
        )

    def search_similar_scenes(
        self,
        conn: sqlite3.Connection,
        query_embedding: bytes,
        script_id: int | None,
        embedding_model: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for similar scenes using vector similarity.

        This method retrieves all scene embeddings and performs similarity
        calculation in Python. For production use with large datasets,
        consider using a dedicated vector database.

        Args:
            conn: Database connection
            query_embedding: Query embedding vector (binary)
            script_id: Optional script ID to limit search
            embedding_model: Model used for embeddings
            limit: Maximum number of results

        Returns:
            List of scene records with similarity scores
        """
        return self._embedding_ops.search_similar_scenes(
            conn, query_embedding, script_id, embedding_model, limit
        )
