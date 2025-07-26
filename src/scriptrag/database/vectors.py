"""Vector operations module for sqlite-vec integration in ScriptRAG.

This module provides vector storage, retrieval, and similarity search capabilities
using the sqlite-vec extension. It supports multiple vector formats and distance
metrics for semantic search in screenplay data.

The module is compatible with Simon Willison's LLM CLI embedding format and
provides efficient SIMD-accelerated vector operations.
"""

import json
from typing import Any, TypeAlias, cast

import numpy as np
import sqlite_vec

from scriptrag.config import get_logger

logger = get_logger(__name__)

# Vector types supported by sqlite-vec
VectorType: TypeAlias = list[float] | np.ndarray | bytes
DistanceMetric = str  # 'cosine', 'l2', 'l1', 'hamming'


class VectorError(Exception):
    """Base exception for vector operations."""


class VectorDimensionError(VectorError):
    """Raised when vector dimensions don't match."""


class VectorOperations:
    """High-level interface for vector operations using sqlite-vec."""

    def __init__(self, db_connection: Any) -> None:
        """Initialize vector operations with DatabaseConnection.

        Args:
            db_connection: DatabaseConnection instance for managing connections
        """
        self.db_connection = db_connection
        self._load_sqlite_vec()

    def _load_sqlite_vec(self) -> None:
        """Load sqlite-vec extension into the connection."""
        try:
            with self.db_connection.get_connection() as conn:
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
                conn.enable_load_extension(False)
            logger.debug("sqlite-vec extension loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load sqlite-vec extension: {e}")
            raise VectorError(f"Could not load sqlite-vec: {e}") from e

    def store_embedding(
        self,
        entity_type: str,
        entity_id: str,
        content: str,
        embedding: VectorType,
        model_name: str,
        vector_type: str = "float32",
    ) -> bool:
        """Store an embedding vector in the database.

        Args:
            entity_type: Type of entity (scene, character, dialogue, etc.)
            entity_id: Unique identifier for the entity
            content: Text content that was embedded
            embedding: Vector embedding as list, numpy array, or bytes
            model_name: Name of the embedding model used
            vector_type: Type of vector storage ('float32', 'int8', 'bit')

        Returns:
            True if successful, False otherwise
        """
        try:
            vector_blob = self._convert_to_blob(embedding, vector_type)
            dimension = self._get_vector_dimension(embedding)

            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO embeddings (
                        id, entity_type, entity_id, content, embedding_model,
                        vector_blob, vector_type, dimension, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    (
                        f"{entity_type}_{entity_id}_{model_name}",
                        entity_type,
                        entity_id,
                        content,
                        model_name,
                        vector_blob,
                        vector_type,
                        dimension,
                    ),
                )
                conn.commit()

            logger.debug(
                f"Stored {vector_type} vector for {entity_type}:{entity_id} "
                f"(dim={dimension}, model={model_name})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to store embedding: {e}")
            return False

    def get_embedding(
        self, entity_type: str, entity_id: str, model_name: str
    ) -> tuple[np.ndarray, dict[str, Any]] | None:
        """Retrieve an embedding vector from the database.

        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            model_name: Embedding model name

        Returns:
            Tuple of (vector_array, metadata) or None if not found
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT vector_blob, vector_type, dimension, content, created_at
                    FROM embeddings
                    WHERE entity_type = ? AND entity_id = ? AND embedding_model = ?
                """,
                    (entity_type, entity_id, model_name),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                vector_blob, vector_type, dimension, content, created_at = row
                vector_array = self._convert_from_blob(
                    vector_blob, vector_type, dimension
                )

                metadata = {
                    "content": content,
                    "vector_type": vector_type,
                    "dimension": dimension,
                    "created_at": created_at,
                }

                return vector_array, metadata

        except Exception as e:
            logger.error(f"Failed to retrieve embedding: {e}")
            return None

    def find_similar(
        self,
        query_vector: VectorType,
        entity_type: str | None = None,
        model_name: str | None = None,
        distance_metric: str = "cosine",
        limit: int = 10,
        threshold: float | None = None,
    ) -> list[tuple[str, str, float, dict[str, Any]]]:
        """Find similar vectors using semantic search.

        Args:
            query_vector: Query vector to find similarities for
            entity_type: Filter by entity type (optional)
            model_name: Filter by embedding model (optional)
            distance_metric: Distance metric ('cosine', 'l2', 'l1')
            limit: Maximum number of results
            threshold: Minimum similarity threshold (optional)

        Returns:
            List of tuples: (entity_type, entity_id, distance, metadata)
        """
        try:
            # Convert query vector to blob
            query_blob = self._convert_to_blob(query_vector, "float32")

            # Build WHERE clause
            where_conditions = []
            params: list[Any] = [query_blob]  # Mixed types: bytes, str, int

            if entity_type:
                where_conditions.append("entity_type = ?")
                params.append(entity_type)

            if model_name:
                where_conditions.append("embedding_model = ?")
                params.append(model_name)

            where_clause = " AND ".join(where_conditions)
            if where_clause:
                where_clause = "WHERE " + where_clause

            # Select distance function
            distance_func = self._get_distance_function(distance_metric)

            # Build and execute query
            # Note: distance_func is validated by _get_distance_function()
            sql = f"""  # noqa: S608
                SELECT
                    entity_type,
                    entity_id,
                    {distance_func}(vector_blob, ?) as distance,
                    content,
                    embedding_model,
                    dimension,
                    created_at
                FROM embeddings
                {where_clause}
                ORDER BY distance
                LIMIT ?
            """

            params.append(limit)

            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)

                results = []
                for row in cursor.fetchall():
                    (
                        entity_type_result,
                        entity_id,
                        distance,
                        content,
                        model,
                        dimension,
                        created_at,
                    ) = row

                    # Apply threshold filter if specified
                    if threshold is not None and distance > threshold:
                        continue

                    metadata = {
                        "content": content,
                        "embedding_model": model,
                        "dimension": dimension,
                        "created_at": created_at,
                        "distance": distance,
                    }

                    results.append((entity_type_result, entity_id, distance, metadata))

            logger.debug(
                f"Found {len(results)} similar vectors using {distance_metric} "
                f"distance (limit={limit})"
            )
            return results

        except Exception as e:
            logger.error(f"Failed to find similar vectors: {e}")
            return []

    def find_similar_to_entity(
        self,
        entity_type: str,
        entity_id: str,
        model_name: str,
        target_entity_type: str | None = None,
        distance_metric: str = "cosine",
        limit: int = 10,
        exclude_self: bool = True,
    ) -> list[tuple[str, str, float, dict[str, Any]]]:
        """Find entities similar to a specific entity.

        Args:
            entity_type: Source entity type
            entity_id: Source entity ID
            model_name: Embedding model name
            target_entity_type: Target entity type to search (optional)
            distance_metric: Distance metric to use
            limit: Maximum results
            exclude_self: Whether to exclude the source entity from results

        Returns:
            List of similar entities with distances and metadata
        """
        # Get the source entity's embedding
        embedding_result = self.get_embedding(entity_type, entity_id, model_name)
        if not embedding_result:
            logger.warning(
                f"No embedding found for {entity_type}:{entity_id} "
                f"with model {model_name}"
            )
            return []

        source_vector, _ = embedding_result

        # Find similar entities
        results = self.find_similar(
            query_vector=source_vector,
            entity_type=target_entity_type,
            model_name=model_name,
            distance_metric=distance_metric,
            limit=limit + (1 if exclude_self else 0),  # Account for self in results
        )

        # Filter out self if requested
        if exclude_self:
            results = [
                r for r in results if not (r[0] == entity_type and r[1] == entity_id)
            ][:limit]

        return results

    def get_vector_stats(self) -> dict[str, Any]:
        """Get statistics about stored vectors.

        Returns:
            Dictionary with vector storage statistics
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()

                # Get basic counts
                cursor.execute("SELECT COUNT(*) FROM embeddings")
                total_count = cursor.fetchone()[0]

                # Get counts by entity type
                cursor.execute(
                    """
                    SELECT entity_type, COUNT(*)
                    FROM embeddings
                    GROUP BY entity_type
                    ORDER BY COUNT(*) DESC
                """
                )
                entity_counts = dict(cursor.fetchall())

                # Get counts by model
                cursor.execute(
                    """
                    SELECT embedding_model, COUNT(*)
                    FROM embeddings
                    GROUP BY embedding_model
                    ORDER BY COUNT(*) DESC
                """
                )
                model_counts = dict(cursor.fetchall())

                # Get dimension distribution
                cursor.execute(
                    """
                    SELECT dimension, COUNT(*)
                    FROM embeddings
                    GROUP BY dimension
                    ORDER BY COUNT(*) DESC
                """
                )
                dimension_counts = dict(cursor.fetchall())

                # Get vector type distribution
                cursor.execute(
                    """
                    SELECT vector_type, COUNT(*)
                    FROM embeddings
                    GROUP BY vector_type
                    ORDER BY COUNT(*) DESC
                """
                )
                type_counts = dict(cursor.fetchall())

                return {
                    "total_vectors": total_count,
                    "entity_type_counts": entity_counts,
                    "model_counts": model_counts,
                    "dimension_counts": dimension_counts,
                    "vector_type_counts": type_counts,
                }

        except Exception as e:
            logger.error(f"Failed to get vector statistics: {e}")
            return {}

    def _convert_to_blob(self, vector: VectorType, vector_type: str) -> bytes:
        """Convert vector to binary blob format for sqlite-vec."""
        if isinstance(vector, list):
            vector = np.array(vector, dtype=np.float32)
        elif isinstance(vector, bytes):
            return vector

        if vector_type == "float32":
            # Type annotation: tobytes() returns bytes
            result: bytes = vector.astype(np.float32).tobytes()
            return result
        if vector_type == "int8":
            # Type annotation: tobytes() returns bytes
            int8_result: bytes = vector.astype(np.int8).tobytes()
            return int8_result
        if vector_type == "bit":
            # Convert to binary vector (0/1 values)
            binary_vector = (vector > 0).astype(np.uint8)
            # Type annotation: packbits().tobytes() returns bytes
            bit_result: bytes = np.packbits(binary_vector).tobytes()
            return bit_result
        raise VectorError(f"Unsupported vector type: {vector_type}")

    def _convert_from_blob(
        self, blob: bytes, vector_type: str, dimension: int
    ) -> np.ndarray:
        """Convert binary blob back to numpy array."""
        if vector_type == "float32":
            return np.frombuffer(blob, dtype=np.float32)
        if vector_type == "int8":
            return np.frombuffer(blob, dtype=np.int8)
        if vector_type == "bit":
            packed = np.frombuffer(blob, dtype=np.uint8)
            return np.unpackbits(packed)[:dimension]
        raise VectorError(f"Unsupported vector type: {vector_type}")

    def _get_vector_dimension(self, vector: VectorType) -> int:
        """Get the dimension of a vector."""
        if isinstance(vector, list):
            return len(vector)
        if isinstance(vector, np.ndarray):
            return cast(int, vector.shape[0])
        if isinstance(vector, bytes):
            # Cannot determine dimension from bytes alone
            raise VectorError("Cannot determine dimension from bytes vector")
        raise VectorError(f"Unsupported vector type: {type(vector)}")

    def _get_distance_function(self, metric: str) -> str:
        """Get the sqlite-vec distance function name."""
        distance_functions = {
            "cosine": "vec_distance_cosine",
            "l2": "vec_distance_l2",
            "l1": "vec_distance_l1",
            "hamming": "vec_distance_hamming",
        }

        if metric not in distance_functions:
            raise VectorError(
                f"Unsupported distance metric: {metric}. "
                f"Supported: {list(distance_functions.keys())}"
            )

        return distance_functions[metric]

    def delete_embeddings(
        self,
        entity_type: str | None = None,
        entity_id: str | None = None,
        model_name: str | None = None,
    ) -> int:
        """Delete embeddings matching the given criteria.

        Args:
            entity_type: Filter by entity type (optional)
            entity_id: Filter by entity ID (optional)
            model_name: Filter by model name (optional)

        Returns:
            Number of embeddings deleted
        """
        try:
            where_conditions = []
            params: list[Any] = []

            if entity_type:
                where_conditions.append("entity_type = ?")
                params.append(entity_type)

            if entity_id:
                where_conditions.append("entity_id = ?")
                params.append(entity_id)

            if model_name:
                where_conditions.append("embedding_model = ?")
                params.append(model_name)

            if not where_conditions:
                # Safety check - don't delete all embeddings without explicit criteria
                logger.warning("Attempted to delete all embeddings - operation blocked")
                return 0

            where_clause = " AND ".join(where_conditions)

            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM embeddings WHERE {where_clause}", params)
                deleted_count = cast(int, cursor.rowcount)
                conn.commit()

            logger.info(f"Deleted {deleted_count} embeddings")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to delete embeddings: {e}")
            return 0


# Utility functions for vector format compatibility


def convert_llm_embedding_format(vector_json: str) -> np.ndarray:
    """Convert LLM CLI JSON embedding format to numpy array.

    Args:
        vector_json: JSON string representation of vector

    Returns:
        Numpy array representation
    """
    try:
        vector_list = json.loads(vector_json)
        return np.array(vector_list, dtype=np.float32)
    except (json.JSONDecodeError, ValueError) as e:
        raise VectorError(f"Invalid JSON embedding format: {e}") from e


def convert_to_llm_format(vector: np.ndarray) -> str:
    """Convert numpy array to LLM CLI JSON format.

    Args:
        vector: Numpy array vector

    Returns:
        JSON string representation
    """
    try:
        return json.dumps(vector.tolist())
    except Exception as e:
        raise VectorError(f"Failed to convert to JSON format: {e}") from e
