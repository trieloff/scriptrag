"""Embedding pipeline for screenplay elements using LLM client.

This module provides functionality for generating, storing, and searching
embeddings for screenplay content including scenes, characters, dialogue,
and other elements. It uses the existing LLM client infrastructure and
stores vectors in SQLite with sqlite-vec extension support.
"""

import json
import struct
from typing import Any, TypedDict

from scriptrag.config import get_logger, get_settings
from scriptrag.llm.client import LLMClient, LLMClientError

from .connection import DatabaseConnection

logger = get_logger(__name__)


class EmbeddingContent(TypedDict):
    """Typed dictionary for embedding content."""

    entity_type: str
    entity_id: str
    content: str
    metadata: dict[str, Any]


class EmbeddingResult(TypedDict):
    """Typed dictionary for embedding search results."""

    entity_type: str
    entity_id: str
    content: str
    similarity: float
    metadata: dict[str, Any]


class EmbeddingError(Exception):
    """Base exception for embedding operations."""


class EmbeddingManager:
    """Manages embeddings for screenplay elements.

    Provides functionality to generate, store, update, and search embeddings
    for various screenplay elements using the existing LLM client and database
    infrastructure.
    """

    def __init__(
        self,
        connection: DatabaseConnection,
        llm_client: LLMClient | None = None,
        embedding_model: str | None = None,
    ) -> None:
        """Initialize embedding manager.

        Args:
            connection: Database connection instance
            llm_client: LLM client for generating embeddings
            embedding_model: Model name for embeddings
        """
        self.connection = connection
        self.config = get_settings()

        # Use provided client or create new one
        self.llm_client = llm_client or LLMClient()

        # Use provided model or default
        self.embedding_model = (
            embedding_model or self.llm_client.default_embedding_model
        )

    async def generate_embedding(
        self,
        content: str,
        model: str | None = None,
    ) -> list[float]:
        """Generate embedding for a single piece of content.

        Args:
            content: Text content to embed
            model: Model to use (defaults to configured model)

        Returns:
            Embedding vector as list of floats

        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not content.strip():
            raise EmbeddingError("Cannot generate embedding for empty content")

        try:
            model = model or self.embedding_model
            embedding = await self.llm_client.generate_embedding(content, model=model)

            logger.debug(
                "Generated embedding",
                content_length=len(content),
                model=model,
                embedding_dim=len(embedding),
            )

            return embedding

        except LLMClientError as e:
            logger.error(
                "Failed to generate embedding",
                content=content[:100],
                error=str(e),
            )
            raise EmbeddingError(f"Embedding generation failed: {e}") from e

    async def generate_embeddings(
        self,
        contents: list[EmbeddingContent],
        model: str | None = None,
        batch_size: int | None = None,
    ) -> list[tuple[EmbeddingContent, list[float]]]:
        """Generate embeddings for multiple pieces of content.

        Args:
            contents: List of content to embed
            model: Model to use (defaults to configured model)
            batch_size: Number of embeddings to generate in each batch
                (uses config default if None)

        Returns:
            List of (content, embedding) tuples

        Raises:
            EmbeddingError: If batch embedding generation fails
        """
        if not contents:
            return []

        model = model or self.embedding_model
        # Use configured batch size if none provided
        if batch_size is None:
            batch_size = self.config.llm.batch_size
        results = []

        logger.info(
            "Generating embeddings",
            count=len(contents),
            model=model,
            batch_size=batch_size,
        )

        try:
            # Process in batches for efficiency
            for i in range(0, len(contents), batch_size):
                batch = contents[i : i + batch_size]
                texts = [content["content"] for content in batch]

                # Generate embeddings for this batch
                embeddings = await self.llm_client.generate_embeddings(
                    texts, model=model
                )

                # Pair each content with its embedding
                for content, embedding in zip(batch, embeddings, strict=True):
                    results.append((content, embedding))

                logger.debug(
                    "Processed batch",
                    batch_start=i,
                    batch_size=len(batch),
                    total_processed=len(results),
                )

            logger.info("Generated all embeddings", total_count=len(results))
            return results

        except LLMClientError as e:
            logger.error("Batch embedding generation failed", error=str(e))
            raise EmbeddingError(f"Batch embedding generation failed: {e}") from e

    def _vector_to_blob(self, vector: list[float]) -> bytes:
        """Convert embedding vector to binary blob for sqlite-vec storage.

        Args:
            vector: Embedding vector as list of floats

        Returns:
            Binary representation of the vector
        """
        return struct.pack(f"{len(vector)}f", *vector)

    def _blob_to_vector(self, blob: bytes) -> list[float]:
        """Convert binary blob back to embedding vector.

        Args:
            blob: Binary representation of vector

        Returns:
            Embedding vector as list of floats
        """
        # Each float is 4 bytes
        count = len(blob) // 4
        return list(struct.unpack(f"{count}f", blob))

    def _parse_vector_json(self, vector_json_str: str) -> list[float] | None:
        """Parse and validate vector JSON data.

        Args:
            vector_json_str: JSON string containing vector data

        Returns:
            Validated vector as list of floats, or None if invalid
        """
        try:
            vector_data = json.loads(vector_json_str)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in vector data", vector_json=vector_json_str)
            return None

        if not isinstance(vector_data, list):
            logger.warning("Vector JSON is not a list", vector_json=vector_json_str)
            return None

        # Validate all elements are numeric
        for i, x in enumerate(vector_data):
            if not isinstance(x, int | float):
                logger.warning(
                    "Non-numeric value in vector",
                    vector_json=vector_json_str,
                    position=i,
                    value=x,
                )
                return None

        return [float(x) for x in vector_data]

    def _validate_embedding_dimension(
        self, embedding: list[float], expected_dim: int | None = None
    ) -> None:
        """Validate embedding vector dimension.

        Args:
            embedding: Embedding vector to validate
            expected_dim: Expected dimension (if None, gets from existing embeddings)

        Raises:
            EmbeddingError: If dimension validation fails
        """
        if not embedding:
            raise EmbeddingError("Cannot validate empty embedding")

        current_dim = len(embedding)

        if expected_dim is None:
            # Get expected dimension from existing embeddings, fallback to config
            stats = self.get_embeddings_stats()
            expected_dim = (
                stats.get("dimension") or self.config.llm.embedding_dimensions
            )

        if expected_dim is not None and current_dim != expected_dim:
            raise EmbeddingError(
                f"Embedding dimension mismatch: expected {expected_dim}, "
                f"got {current_dim}"
            )

    def store_embedding(
        self,
        entity_type: str,
        entity_id: str,
        content: str,
        embedding: list[float],
        model: str | None = None,
    ) -> None:
        """Store an embedding in the database.

        Args:
            entity_type: Type of entity (scene, character, dialogue, etc.)
            entity_id: ID of the entity
            content: Original text content
            embedding: Embedding vector
            model: Model used for embedding

        Raises:
            EmbeddingError: If storage fails
        """
        if not embedding:
            raise EmbeddingError("Cannot store empty embedding")

        # Validate embedding dimension consistency
        self._validate_embedding_dimension(embedding)

        model = model or self.embedding_model
        vector_blob = self._vector_to_blob(embedding)
        vector_json = json.dumps(embedding)  # Legacy format for compatibility
        dimension = len(embedding)

        try:
            with self.connection.transaction() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO embeddings
                    (entity_type, entity_id, content, embedding_model,
                     vector_blob, vector_json, dimension)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entity_type,
                        entity_id,
                        content,
                        model,
                        vector_blob,
                        vector_json,
                        dimension,
                    ),
                )

            logger.debug(
                "Stored embedding",
                entity_type=entity_type,
                entity_id=entity_id,
                model=model,
                dimension=dimension,
            )

        except Exception as e:
            logger.error(
                "Failed to store embedding",
                entity_type=entity_type,
                entity_id=entity_id,
                error=str(e),
            )
            raise EmbeddingError(f"Failed to store embedding: {e}") from e

    async def store_embeddings(
        self,
        embeddings: list[tuple[EmbeddingContent, list[float]]],
        model: str | None = None,
    ) -> int:
        """Store multiple embeddings in the database.

        Args:
            embeddings: List of (content, embedding) tuples
            model: Model used for embeddings

        Returns:
            Number of embeddings stored

        Raises:
            EmbeddingError: If storage fails
        """
        if not embeddings:
            return 0

        model = model or self.embedding_model
        stored_count = 0

        logger.info("Storing embeddings", count=len(embeddings), model=model)

        try:
            with self.connection.transaction() as conn:
                for content, embedding in embeddings:
                    if not embedding:
                        logger.warning(
                            "Skipping empty embedding",
                            entity_type=content["entity_type"],
                            entity_id=content["entity_id"],
                        )
                        continue

                    # Validate embedding dimension consistency
                    try:
                        self._validate_embedding_dimension(embedding)
                    except EmbeddingError as e:
                        logger.warning(
                            "Skipping embedding with invalid dimension",
                            entity_type=content["entity_type"],
                            entity_id=content["entity_id"],
                            error=str(e),
                        )
                        continue

                    vector_blob = self._vector_to_blob(embedding)
                    vector_json = json.dumps(embedding)
                    dimension = len(embedding)

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO embeddings
                        (entity_type, entity_id, content, embedding_model,
                         vector_blob, vector_json, dimension)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            content["entity_type"],
                            content["entity_id"],
                            content["content"],
                            model,
                            vector_blob,
                            vector_json,
                            dimension,
                        ),
                    )
                    stored_count += 1

            logger.info("Stored embeddings", count=stored_count, model=model)
            return stored_count

        except Exception as e:
            logger.error("Failed to store embeddings", error=str(e))
            raise EmbeddingError(f"Failed to store embeddings: {e}") from e

    def get_embedding(
        self,
        entity_type: str,
        entity_id: str,
        model: str | None = None,
    ) -> list[float] | None:
        """Retrieve an embedding from the database.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            model: Model used for embedding

        Returns:
            Embedding vector or None if not found
        """
        model = model or self.embedding_model

        try:
            row = self.connection.fetch_one(
                """
                SELECT vector_blob, vector_json FROM embeddings
                WHERE entity_type = ? AND entity_id = ? AND embedding_model = ?
                """,
                (entity_type, entity_id, model),
            )

            if not row:
                return None

            # Prefer binary blob format, fall back to JSON
            if row["vector_blob"]:
                return self._blob_to_vector(row["vector_blob"])
            if row["vector_json"]:
                return self._parse_vector_json(row["vector_json"])

            return None

        except Exception as e:
            logger.error(
                "Failed to retrieve embedding",
                entity_type=entity_type,
                entity_id=entity_id,
                error=str(e),
            )
            return None

    def delete_embedding(
        self,
        entity_type: str,
        entity_id: str,
        model: str | None = None,
    ) -> bool:
        """Delete an embedding from the database.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            model: Model used for embedding

        Returns:
            True if embedding was deleted
        """
        model = model or self.embedding_model

        try:
            with self.connection.transaction() as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM embeddings
                    WHERE entity_type = ? AND entity_id = ? AND embedding_model = ?
                    """,
                    (entity_type, entity_id, model),
                )
                deleted = cursor.rowcount > 0

            if deleted:
                logger.debug(
                    "Deleted embedding",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    model=model,
                )

            return deleted

        except Exception as e:
            logger.error(
                "Failed to delete embedding",
                entity_type=entity_type,
                entity_id=entity_id,
                error=str(e),
            )
            return False

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score between -1 and 1
        """
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have the same dimension")

        # Calculate dot product and magnitudes
        dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=True))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        # Avoid division by zero
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        # Ensure the division returns a float
        return float(dot_product / (magnitude1 * magnitude2))

    def find_similar(
        self,
        query_embedding: list[float],
        entity_type: str | None = None,
        model: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.0,
    ) -> list[EmbeddingResult]:
        """Find similar embeddings using cosine similarity.

        Args:
            query_embedding: Query vector to find similar items for
            entity_type: Filter by entity type
            model: Model used for embeddings
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold

        Returns:
            List of similar embeddings with similarity scores
        """
        model = model or self.embedding_model
        conditions = ["embedding_model = ?"]
        params = [model]

        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)

        where_clause = f"WHERE {' AND '.join(conditions)}"

        try:
            rows = self.connection.fetch_all(
                f"""
                SELECT entity_type, entity_id, content, vector_blob, vector_json
                FROM embeddings
                {where_clause}
                ORDER BY created_at DESC
                """,
                tuple(params),
            )

            results = []
            for row in rows:
                # Get embedding vector
                if row["vector_blob"]:
                    embedding = self._blob_to_vector(row["vector_blob"])
                elif row["vector_json"]:
                    embedding = json.loads(row["vector_json"])
                else:
                    continue

                # Calculate similarity
                try:
                    similarity = self.cosine_similarity(query_embedding, embedding)
                except ValueError:
                    # Skip vectors with different dimensions
                    continue

                if similarity >= min_similarity:
                    results.append(
                        EmbeddingResult(
                            entity_type=row["entity_type"],
                            entity_id=row["entity_id"],
                            content=row["content"],
                            similarity=similarity,
                            metadata={},
                        )
                    )

            # Sort by similarity (highest first) and limit
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error("Similarity search failed", error=str(e))
            return []

    async def semantic_search(
        self,
        query: str,
        entity_type: str | None = None,
        model: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.1,
    ) -> list[EmbeddingResult]:
        """Perform semantic search using natural language query.

        Args:
            query: Natural language search query
            entity_type: Filter by entity type
            model: Model to use for query embedding
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold

        Returns:
            List of semantically similar content

        Raises:
            EmbeddingError: If search fails
        """
        if not query.strip():
            return []

        try:
            # Generate embedding for the query
            query_embedding = await self.generate_embedding(query, model=model)

            # Find similar embeddings
            return self.find_similar(
                query_embedding,
                entity_type=entity_type,
                model=model,
                limit=limit,
                min_similarity=min_similarity,
            )

        except Exception as e:
            logger.error("Semantic search failed", query=query, error=str(e))
            raise EmbeddingError(f"Semantic search failed: {e}") from e

    def get_embeddings_stats(self, model: str | None = None) -> dict[str, Any]:
        """Get statistics about stored embeddings.

        Args:
            model: Filter by specific model

        Returns:
            Dictionary with embedding statistics
        """
        model = model or self.embedding_model

        try:
            # Get total count and by entity type
            total_row = self.connection.fetch_one(
                "SELECT COUNT(*) as count FROM embeddings WHERE embedding_model = ?",
                (model,),
            )
            total_count = total_row["count"] if total_row else 0

            # Get counts by entity type
            type_rows = self.connection.fetch_all(
                """
                SELECT entity_type, COUNT(*) as count
                FROM embeddings
                WHERE embedding_model = ?
                GROUP BY entity_type
                ORDER BY count DESC
                """,
                (model,),
            )

            entity_counts = {row["entity_type"]: row["count"] for row in type_rows}

            # Get dimension info
            dim_row = self.connection.fetch_one(
                """
                SELECT dimension
                FROM embeddings
                WHERE embedding_model = ?
                LIMIT 1
                """,
                (model,),
            )
            dimension = dim_row["dimension"] if dim_row else None

            return {
                "model": model,
                "total_embeddings": total_count,
                "dimension": dimension,
                "entity_counts": entity_counts,
            }

        except Exception as e:
            logger.error("Failed to get embedding stats", error=str(e))
            return {
                "model": model,
                "total_embeddings": 0,
                "dimension": None,
                "entity_counts": {},
                "error": str(e),
            }

    async def refresh_embeddings(
        self,
        entity_type: str | None = None,
        entity_ids: list[str] | None = None,
        model: str | None = None,
        force: bool = False,
    ) -> int:
        """Refresh embeddings for specified entities.

        Args:
            entity_type: Filter by entity type
            entity_ids: Specific entity IDs to refresh
            model: Model to use for new embeddings
            force: Force refresh even if embeddings already exist

        Returns:
            Number of embeddings refreshed

        Raises:
            EmbeddingError: If refresh fails
        """
        model = model or self.embedding_model

        # This is a placeholder implementation
        # In a real implementation, you would:
        # 1. Query the entities that need refreshing
        # 2. Extract their content
        # 3. Generate new embeddings
        # 4. Store them in the database

        logger.info(
            "Refresh embeddings (placeholder)",
            entity_type=entity_type,
            entity_count=len(entity_ids) if entity_ids else "all",
            model=model,
            force=force,
        )

        # For now, return 0 as this is a placeholder
        return 0

    async def close(self) -> None:
        """Close the embedding manager and cleanup resources."""
        if self.llm_client:
            await self.llm_client.close()
