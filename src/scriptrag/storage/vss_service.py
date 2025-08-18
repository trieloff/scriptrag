"""SQLite VSS service using sqlite-vec for vector similarity search."""

import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
import sqlite_vec
from sqlite_vec import serialize_float32

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.exceptions import DatabaseError

logger = get_logger(__name__)


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
            tables = [row[0] for row in cursor]

            if not any("scene_embeddings" in t for t in tables):
                logger.info("Creating VSS tables for first time...")
                self._initialize_vss_tables(conn)

    def _initialize_vss_tables(self, conn: sqlite3.Connection) -> None:
        """Initialize VSS virtual tables.

        Args:
            conn: Database connection
        """
        # Read and execute migration SQL
        migration_path = (
            Path(__file__).parent / "database" / "sql" / "vss_migration.sql"
        )
        if migration_path.exists():
            migration_sql = migration_path.read_text()
            # Execute statements one by one (skip .load command)
            for statement in migration_sql.split(";"):
                statement = statement.strip()
                if (
                    statement
                    and not statement.startswith("--")
                    and ".load" not in statement
                ):
                    try:
                        conn.execute(statement)
                    except sqlite3.OperationalError as e:
                        # Skip if table already exists
                        if "already exists" not in str(e):
                            logger.warning(f"Migration statement failed: {e}")
            conn.commit()
            logger.info("VSS tables initialized successfully")

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
            # Use sqlite-vec's serialization
            if isinstance(embedding, list):
                embedding_blob = serialize_float32(embedding)
            else:
                # NumPy arrays work directly via Buffer protocol
                embedding_blob = embedding.astype(np.float32)

            # Store in VSS table
            conn.execute(
                """
                INSERT OR REPLACE INTO scene_embeddings
                (scene_id, embedding_model, embedding)
                VALUES (?, ?, ?)
                """,
                (scene_id, model, embedding_blob),
            )

            # Update metadata
            dimensions = len(embedding)
            conn.execute(
                """
                INSERT OR REPLACE INTO embedding_metadata
                (entity_type, entity_id, embedding_model, dimensions)
                VALUES ('scene', ?, ?, ?)
                """,
                (scene_id, model, dimensions),
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
            # Use sqlite-vec's serialization
            if isinstance(query_embedding, list):
                query_blob = serialize_float32(query_embedding)
            else:
                # NumPy arrays work directly via Buffer protocol
                query_blob = query_embedding.astype(np.float32)

            # Build query based on script_id filter
            params: tuple[Any, ...]
            if script_id:
                query = """
                    SELECT
                        s.*,
                        se.scene_id,
                        se.distance
                    FROM scene_embeddings se
                    JOIN scenes s ON s.id = se.scene_id
                    WHERE se.embedding_model = ?
                    AND s.script_id = ?
                    AND se.embedding MATCH ?
                    ORDER BY se.distance
                    LIMIT ?
                """
                params = (
                    model,
                    script_id,
                    query_blob,
                    limit,
                )
            else:
                query = """
                    SELECT
                        s.*,
                        se.scene_id,
                        se.distance
                    FROM scene_embeddings se
                    JOIN scenes s ON s.id = se.scene_id
                    WHERE se.embedding_model = ?
                    AND se.embedding MATCH ?
                    ORDER BY se.distance
                    LIMIT ?
                """
                params = (
                    model,
                    query_blob,
                    limit,
                )

            cursor = conn.execute(query, params)

            results = []
            for row in cursor:
                result = dict(row)
                # Convert distance to similarity score (1 - normalized_distance)
                # Assuming cosine distance, convert to similarity
                result["similarity_score"] = 1.0 - (result.pop("distance", 0) / 2.0)
                results.append(result)

            return results

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
            # Use sqlite-vec's serialization
            if isinstance(embedding, list):
                embedding_blob = serialize_float32(embedding)
            else:
                # NumPy arrays work directly via Buffer protocol
                embedding_blob = embedding.astype(np.float32)

            # Store in VSS table
            conn.execute(
                """
                INSERT OR REPLACE INTO bible_embeddings
                (chunk_id, embedding_model, embedding)
                VALUES (?, ?, ?)
                """,
                (chunk_id, model, embedding_blob),
            )

            # Update metadata
            dimensions = len(embedding)
            conn.execute(
                """
                INSERT OR REPLACE INTO embedding_metadata
                (entity_type, entity_id, embedding_model, dimensions)
                VALUES ('bible_chunk', ?, ?, ?)
                """,
                (chunk_id, model, dimensions),
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
            # Use sqlite-vec's serialization
            if isinstance(query_embedding, list):
                query_blob = serialize_float32(query_embedding)
            else:
                # NumPy arrays work directly via Buffer protocol
                query_blob = query_embedding.astype(np.float32)

            # Build query based on script_id filter
            params: tuple[Any, ...]
            if script_id:
                query = """
                    SELECT
                        bc.*,
                        sb.title as bible_title,
                        sb.script_id,
                        be.chunk_id,
                        be.distance
                    FROM bible_embeddings be
                    JOIN bible_chunks bc ON bc.id = be.chunk_id
                    JOIN script_bibles sb ON bc.bible_id = sb.id
                    WHERE be.embedding_model = ?
                    AND sb.script_id = ?
                    AND be.embedding MATCH ?
                    ORDER BY be.distance
                    LIMIT ?
                """
                params = (
                    model,
                    script_id,
                    query_blob,
                    limit,
                )
            else:
                query = """
                    SELECT
                        bc.*,
                        sb.title as bible_title,
                        sb.script_id,
                        be.chunk_id,
                        be.distance
                    FROM bible_embeddings be
                    JOIN bible_chunks bc ON bc.id = be.chunk_id
                    JOIN script_bibles sb ON bc.bible_id = sb.id
                    WHERE be.embedding_model = ?
                    AND be.embedding MATCH ?
                    ORDER BY be.distance
                    LIMIT ?
                """
                params = (
                    model,
                    query_blob,
                    limit,
                )

            cursor = conn.execute(query, params)

            results = []
            for row in cursor:
                result = dict(row)
                # Convert distance to similarity score
                result["similarity_score"] = 1.0 - (result.pop("distance", 0) / 2.0)
                results.append(result)

            return results

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
            stats = {}

            # Count scene embeddings
            cursor = conn.execute(
                "SELECT COUNT(*) as count, embedding_model "
                "FROM scene_embeddings GROUP BY embedding_model"
            )
            stats["scene_embeddings"] = {
                row["embedding_model"]: row["count"] for row in cursor
            }

            # Count bible embeddings
            cursor = conn.execute(
                "SELECT COUNT(*) as count, embedding_model "
                "FROM bible_embeddings GROUP BY embedding_model"
            )
            stats["bible_embeddings"] = {
                row["embedding_model"]: row["count"] for row in cursor
            }

            # Get metadata stats
            cursor = conn.execute(
                """
                SELECT entity_type, COUNT(*) as count, AVG(dimensions) as avg_dims
                FROM embedding_metadata
                GROUP BY entity_type
                """
            )
            stats["metadata"] = {
                row["entity_type"]: {
                    "count": row["count"],
                    "avg_dimensions": row["avg_dims"],
                }
                for row in cursor
            }

            return stats

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

        scenes_migrated = 0
        bible_migrated = 0

        try:
            # Check if old embeddings table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='embeddings_old'"
            )
            if not cursor.fetchone():
                logger.info("No old embeddings table to migrate from")
                return (0, 0)

            # Migrate scene embeddings
            cursor = conn.execute(
                """
                SELECT entity_id, embedding_model, embedding
                FROM embeddings_old
                WHERE entity_type = 'scene' AND embedding IS NOT NULL
                """
            )

            for row in cursor:
                try:
                    # Decode the binary embedding
                    import struct

                    data = row["embedding"]
                    dimension = struct.unpack("<I", data[:4])[0]
                    format_str = f"<{dimension}f"
                    values = struct.unpack(format_str, data[4 : 4 + dimension * 4])

                    # Store in VSS
                    self.store_scene_embedding(
                        row["entity_id"], list(values), row["embedding_model"], conn
                    )
                    scenes_migrated += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to migrate scene embedding {row['entity_id']}: {e}"
                    )

            # Migrate bible chunk embeddings
            cursor = conn.execute(
                """
                SELECT entity_id, embedding_model, embedding
                FROM embeddings_old
                WHERE entity_type = 'bible_chunk' AND embedding IS NOT NULL
                """
            )

            for row in cursor:
                try:
                    # Decode the binary embedding
                    import struct

                    data = row["embedding"]
                    dimension = struct.unpack("<I", data[:4])[0]
                    format_str = f"<{dimension}f"
                    values = struct.unpack(format_str, data[4 : 4 + dimension * 4])

                    # Store in VSS
                    self.store_bible_embedding(
                        row["entity_id"], list(values), row["embedding_model"], conn
                    )
                    bible_migrated += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to migrate bible embedding {row['entity_id']}: {e}"
                    )

            logger.info(
                f"Migrated {scenes_migrated} scene embeddings and "
                f"{bible_migrated} bible embeddings"
            )
            return (scenes_migrated, bible_migrated)

        finally:
            if close_conn:
                conn.close()
