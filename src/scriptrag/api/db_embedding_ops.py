"""Embedding-related database operations for ScriptRAG."""

import sqlite3
from typing import Any

from scriptrag.config import get_logger
from scriptrag.exceptions import DatabaseError

logger = get_logger(__name__)


class EmbeddingOperations:
    """Handles embedding-related database operations."""

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
        # Note: embedding_path is reserved for future Git LFS storage support
        # Currently, we store binary data directly in the database
        _ = embedding_path  # Mark as intentionally unused

        # Check if embedding exists
        cursor = conn.execute(
            """
            SELECT id FROM embeddings
            WHERE entity_type = ? AND entity_id = ? AND embedding_model = ?
            """,
            (entity_type, entity_id, embedding_model),
        )
        existing = cursor.fetchone()

        # For Git LFS storage, we store the path reference instead of raw data
        # The actual embedding will be loaded from the file when needed
        embedding_blob = embedding_data if embedding_data else b""

        if existing:
            # Update existing embedding
            conn.execute(
                """
                UPDATE embeddings
                SET embedding = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (embedding_blob, existing["id"]),
            )
            embedding_id = int(existing["id"])
            logger.debug(
                f"Updated embedding {embedding_id} for {entity_type}:{entity_id}"
            )
        else:
            # Insert new embedding
            cursor = conn.execute(
                """
                INSERT INTO embeddings
                (entity_type, entity_id, embedding_model, embedding)
                VALUES (?, ?, ?, ?)
                """,
                (entity_type, entity_id, embedding_model, embedding_blob),
            )
            lastrowid = cursor.lastrowid
            if lastrowid is None:
                raise DatabaseError(
                    message="Failed to get embedding ID after database insert",
                    hint="Database constraint violation or embedding storage issue",
                    details={
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "operation": "INSERT INTO embeddings",
                    },
                )
            embedding_id = lastrowid
            logger.debug(
                f"Inserted embedding {embedding_id} for {entity_type}:{entity_id}"
            )

        return embedding_id

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
        cursor = conn.execute(
            """
            SELECT s.id, e.embedding
            FROM scenes s
            JOIN embeddings e ON e.entity_id = s.id
            WHERE s.script_id = ?
            AND e.entity_type = 'scene'
            AND e.embedding_model = ?
            AND e.embedding IS NOT NULL
            """,
            (script_id, embedding_model),
        )

        results = []
        for row in cursor:
            results.append((row["id"], row["embedding"]))

        return results

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
        cursor = conn.execute(
            """
            SELECT embedding FROM embeddings
            WHERE entity_type = ? AND entity_id = ? AND embedding_model = ?
            """,
            (entity_type, entity_id, embedding_model),
        )
        row = cursor.fetchone()
        return row["embedding"] if row else None

    def search_similar_scenes(
        self,
        conn: sqlite3.Connection,
        query_embedding: bytes,  # noqa: ARG002
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
        # Build query based on whether script_id is provided
        params: tuple[Any, ...]
        if script_id:
            query = """
                SELECT s.*, e.embedding
                FROM scenes s
                JOIN embeddings e ON e.entity_id = s.id
                WHERE s.script_id = ?
                AND e.entity_type = 'scene'
                AND e.embedding_model = ?
                AND e.embedding IS NOT NULL
            """
            params = (script_id, embedding_model)
        else:
            query = """
                SELECT s.*, e.embedding
                FROM scenes s
                JOIN embeddings e ON e.entity_id = s.id
                WHERE e.entity_type = 'scene'
                AND e.embedding_model = ?
                AND e.embedding IS NOT NULL
            """
            params = (embedding_model,)

        cursor = conn.execute(query, params)

        # Note: For production use with large datasets, the similarity
        # calculation should be done in a specialized vector database
        # or using database extensions like sqlite-vss
        scenes = []
        for row in cursor:
            scene_dict = dict(row)
            # Store embedding for similarity calculation
            scene_dict["_embedding"] = scene_dict.pop("embedding")
            scenes.append(scene_dict)

        # Return scenes with embeddings for external similarity calculation
        return scenes[:limit]  # Limit applied after retrieval for now
