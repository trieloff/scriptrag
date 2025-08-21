"""SQLite VSS service using sqlite-vec for vector similarity search.

This module exposes the public ``VSSService`` while delegating heavy lifting to
focused helper modules to keep file size and complexity in check.
"""

import sqlite3
from pathlib import Path
from typing import Any, TypeAlias

import numpy as np
import numpy.typing as npt
import sqlite_vec
from sqlite_vec import serialize_float32

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.exceptions import DatabaseError

from .vss_admin import get_embedding_stats as admin_stats
from .vss_admin import migrate_from_blob_storage as admin_migrate
from .vss_bible_ops import (
    search_similar_bible_chunks as bible_search,
)
from .vss_bible_ops import (
    store_bible_embedding as bible_store,
)
from .vss_scene_ops import (
    search_similar_scenes as scene_search,
)
from .vss_scene_ops import (
    store_scene_embedding as scene_store,
)
from .vss_setup import initialize_vss_tables

logger = get_logger(__name__)

# Type aliases for clarity
FloatArray: TypeAlias = npt.NDArray[np.float32]
SearchResult: TypeAlias = dict[str, Any]
EmbeddingVector: TypeAlias = list[float] | FloatArray


class VSSService:
    """Service for managing vector similarity search using sqlite-vec."""

    def __init__(self, settings: ScriptRAGSettings, db_path: Path | None = None):
        """Initialize VSS service.

        Args:
            settings: Configuration settings
            db_path: Optional database path (defaults to settings.database_path)
        """
        self.settings = settings
        self.db_path = db_path or settings.database_path
        self._ensure_vss_support()

    def _ensure_vss_support(self) -> None:
        """Ensure sqlite-vec extension is loaded and VSS tables exist."""
        with self.get_connection() as conn:
            # Check if VSS tables exist
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE '%_embeddings'"
            )
            tables: list[str] = [row[0] for row in cursor]

            if not any("scene_embeddings" in t for t in tables):
                logger.info("Creating VSS tables for first time...")
                self._initialize_vss_tables(conn)

    def _initialize_vss_tables(self, conn: sqlite3.Connection) -> None:
        """Initialize VSS virtual tables via migration helper."""
        try:
            initialize_vss_tables(conn)
            logger.info("VSS tables initialized successfully")
        except sqlite3.OperationalError as e:
            # Keep previous behavior of logging and continuing on benign errors
            if "already exists" not in str(e):
                logger.warning(f"Migration statement failed: {e}")

    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection with sqlite-vec loaded.

        Returns:
            Database connection with VSS support
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")

        # Load sqlite-vec extension if supported
        # macOS default SQLite doesn't support loadable extensions
        if hasattr(conn, "enable_load_extension"):
            try:
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
                conn.enable_load_extension(False)
            except (AttributeError, sqlite3.OperationalError) as e:
                logger.debug(f"SQLite extension loading not available: {e}")
                # Continue without VSS support - tests will mock this functionality

        return conn

    def store_scene_embedding(
        self,
        scene_id: int,
        embedding: list[float] | np.ndarray,
        model: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        """Store scene embedding in VSS table.

        Args:
            scene_id: ID of the scene
            embedding: Embedding vector
            model: Model used to generate embedding
            conn: Optional database connection
        """
        if conn is None:
            conn = self.get_connection()
            close_conn = True
        else:
            close_conn = False

        try:
            # Delegate to ops
            scene_store(
                conn,
                scene_id,
                embedding,
                model,
                serializer=serialize_float32,
            )

            conn.commit()
            logger.debug(f"Stored embedding for scene {scene_id} using model {model}")

        except Exception as e:
            conn.rollback()
            raise DatabaseError(
                message=f"Failed to store scene embedding: {e}",
                hint="Check database connection and embedding format",
                details={"scene_id": scene_id, "model": model},
            ) from e
        finally:
            if close_conn:
                conn.close()

    def search_similar_scenes(
        self,
        query_embedding: list[float] | np.ndarray,
        model: str,
        limit: int = 10,
        script_id: int | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar scenes using VSS.

        Args:
            query_embedding: Query vector
            model: Embedding model to search
            limit: Maximum number of results
            script_id: Optional script ID to filter results
            conn: Optional database connection

        Returns:
            List of similar scenes with scores
        """
        if conn is None:
            conn = self.get_connection()
            close_conn = True
        else:
            close_conn = False

        try:
            # Delegate to ops
            return scene_search(
                conn,
                query_embedding,
                model,
                limit=limit,
                script_id=script_id,
                serializer=serialize_float32,
            )

        except Exception as e:
            raise DatabaseError(
                message=f"Failed to search similar scenes: {e}",
                hint="Check query embedding format and model",
                details={"model": model, "limit": limit},
            ) from e
        finally:
            if close_conn:
                conn.close()

    def store_bible_embedding(
        self,
        chunk_id: int,
        embedding: list[float] | np.ndarray,
        model: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        """Store bible chunk embedding in VSS table.

        Args:
            chunk_id: ID of the bible chunk
            embedding: Embedding vector
            model: Model used to generate embedding
            conn: Optional database connection
        """
        if conn is None:
            conn = self.get_connection()
            close_conn = True
        else:
            close_conn = False

        try:
            # Delegate to ops
            bible_store(
                conn,
                chunk_id,
                embedding,
                model,
                serializer=serialize_float32,
            )

            conn.commit()
            logger.debug(
                f"Stored embedding for bible chunk {chunk_id} using model {model}"
            )

        except Exception as e:
            conn.rollback()
            raise DatabaseError(
                message=f"Failed to store bible embedding: {e}",
                hint="Check database connection and embedding format",
                details={"chunk_id": chunk_id, "model": model},
            ) from e
        finally:
            if close_conn:
                conn.close()

    def search_similar_bible_chunks(
        self,
        query_embedding: list[float] | np.ndarray,
        model: str,
        limit: int = 10,
        script_id: int | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar bible chunks using VSS.

        Args:
            query_embedding: Query vector
            model: Embedding model to search
            limit: Maximum number of results
            script_id: Optional script ID to filter results
            conn: Optional database connection

        Returns:
            List of similar bible chunks with scores
        """
        if conn is None:
            conn = self.get_connection()
            close_conn = True
        else:
            close_conn = False

        try:
            # Delegate to ops
            return bible_search(
                conn,
                query_embedding,
                model,
                limit=limit,
                script_id=script_id,
                serializer=serialize_float32,
            )

        except Exception as e:
            raise DatabaseError(
                message=f"Failed to search similar bible chunks: {e}",
                hint="Check query embedding format and model",
                details={"model": model, "limit": limit},
            ) from e
        finally:
            if close_conn:
                conn.close()

    def get_embedding_stats(
        self, conn: sqlite3.Connection | None = None
    ) -> dict[str, Any]:
        """Get statistics about stored embeddings.

        Args:
            conn: Optional database connection

        Returns:
            Dictionary with embedding statistics
        """
        if conn is None:
            conn = self.get_connection()
            close_conn = True
        else:
            close_conn = False

        try:
            return admin_stats(conn)

        finally:
            if close_conn:
                conn.close()

    def migrate_from_blob_storage(
        self, conn: sqlite3.Connection | None = None
    ) -> tuple[int, int]:
        """Migrate existing BLOB embeddings to VSS tables.

        Args:
            conn: Optional database connection

        Returns:
            Tuple of (scenes_migrated, bible_chunks_migrated)
        """
        if conn is None:
            conn = self.get_connection()
            close_conn = True
        else:
            close_conn = False

        try:
            # Provide wrappers so tests can patch our public methods
            def _store_scene(
                conn_: sqlite3.Connection,
                entity_id: int,
                values: list[float],
                model: str,
                _serializer: Any,
            ) -> None:
                return self.store_scene_embedding(entity_id, values, model, conn=conn_)

            def _store_bible(
                conn_: sqlite3.Connection,
                entity_id: int,
                values: list[float],
                model: str,
                _serializer: Any,
            ) -> None:
                return self.store_bible_embedding(entity_id, values, model, conn=conn_)

            scenes_migrated, bible_migrated = admin_migrate(
                conn,
                serializer=serialize_float32,
                store_scene_fn=_store_scene,
                store_bible_fn=_store_bible,
            )
            logger.info(
                f"Migrated {scenes_migrated} scene embeddings and "
                f"{bible_migrated} bible embeddings"
            )
            return (scenes_migrated, bible_migrated)

        finally:
            if close_conn:
                conn.close()
