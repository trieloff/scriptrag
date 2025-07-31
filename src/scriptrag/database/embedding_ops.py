"""Embedding and vector operations for screenplay semantic search.

This module handles storage and retrieval of embeddings for scenes,
characters, and dialogue.
"""

from typing import Any

from scriptrag.config import get_logger

from .connection import DatabaseConnection
from .vectors import VectorOperations

logger = get_logger(__name__)


class EmbeddingOperations:
    """Operations for managing embeddings and semantic search."""

    def __init__(
        self, connection: DatabaseConnection, vectors: VectorOperations
    ) -> None:
        """Initialize embedding operations.

        Args:
            connection: Database connection instance
            vectors: Vector operations instance
        """
        self.connection = connection
        self.vectors = vectors

    def store_scene_embedding(
        self,
        scene_id: str,
        embedding: list[float],
        content: str = "",
        model_name: str = "default",
    ) -> bool:
        """Store embedding for a scene.

        Args:
            scene_id: Scene ID
            embedding: Embedding vector
            content: Text content that was embedded
            model_name: Name of the embedding model used

        Returns:
            True if successful
        """
        return self.vectors.store_embedding(
            entity_type="scene",
            entity_id=scene_id,
            content=content,
            embedding=embedding,
            model_name=model_name,
        )

    def store_character_embedding(
        self,
        character_id: str,
        embedding: list[float],
        content: str = "",
        model_name: str = "default",
    ) -> bool:
        """Store embedding for a character.

        Args:
            character_id: Character ID
            embedding: Embedding vector
            content: Text content that was embedded
            model_name: Name of the embedding model used

        Returns:
            True if successful
        """
        return self.vectors.store_embedding(
            entity_type="character",
            entity_id=character_id,
            content=content,
            embedding=embedding,
            model_name=model_name,
        )

    def store_dialogue_embedding(
        self,
        dialogue_id: str,
        embedding: list[float],
        content: str = "",
        model_name: str = "default",
    ) -> bool:
        """Store embedding for dialogue.

        Args:
            dialogue_id: Dialogue ID
            embedding: Embedding vector
            content: Text content that was embedded
            model_name: Name of the embedding model used

        Returns:
            True if successful
        """
        return self.vectors.store_embedding(
            entity_type="dialogue",
            entity_id=dialogue_id,
            content=content,
            embedding=embedding,
            model_name=model_name,
        )

    def find_similar_scenes(
        self,
        scene_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.7,
        exclude_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Find scenes similar to a given embedding.

        Args:
            scene_embedding: Query embedding
            limit: Maximum number of results
            threshold: Minimum similarity threshold
            exclude_ids: Scene IDs to exclude

        Returns:
            List of similar scenes with scores
        """
        results = self.vectors.find_similar(
            query_vector=scene_embedding,
            entity_type="scene",
            limit=limit,
            threshold=threshold,
        )

        # Convert tuple results to dict format and filter out excluded IDs
        formatted_results = []
        for entity_type_result, entity_id, distance, metadata in results:
            if exclude_ids and entity_id in exclude_ids:
                continue
            formatted_results.append(
                {
                    "entity_type": entity_type_result,
                    "entity_id": entity_id,
                    "distance": distance,
                    "metadata": metadata,
                }
            )

        return formatted_results

    def find_similar_characters(
        self,
        character_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.7,
        exclude_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Find characters similar to a given embedding.

        Args:
            character_embedding: Query embedding
            limit: Maximum number of results
            threshold: Minimum similarity threshold
            exclude_ids: Character IDs to exclude

        Returns:
            List of similar characters with scores
        """
        results = self.vectors.find_similar(
            query_vector=character_embedding,
            entity_type="character",
            limit=limit,
            threshold=threshold,
        )

        # Convert tuple results to dict format and filter out excluded IDs
        formatted_results = []
        for entity_type_result, entity_id, distance, metadata in results:
            if exclude_ids and entity_id in exclude_ids:
                continue
            formatted_results.append(
                {
                    "entity_type": entity_type_result,
                    "entity_id": entity_id,
                    "distance": distance,
                    "metadata": metadata,
                }
            )

        return formatted_results

    def semantic_search_scenes(
        self,
        query_embedding: list[float],
        script_id: str | None = None,
        limit: int = 20,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Search for scenes using semantic similarity.

        Args:
            query_embedding: Query embedding
            script_id: Optional script ID to filter by
            limit: Maximum number of results
            threshold: Minimum similarity threshold

        Returns:
            List of matching scenes with scores
        """
        results = self.vectors.find_similar(
            query_vector=query_embedding,
            entity_type="scene",
            limit=limit,
            threshold=threshold,
        )

        # Convert tuple results to dict format and filter by script if specified
        formatted_results = []
        script_scene_ids = None

        if script_id:
            # Get scenes belonging to this script
            with self.connection.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT id FROM scenes WHERE script_id = ?", (script_id,)
                )
                script_scene_ids = {row[0] for row in cursor.fetchall()}

        for entity_type_result, entity_id, distance, metadata in results:
            if script_scene_ids and entity_id not in script_scene_ids:
                continue
            formatted_results.append(
                {
                    "entity_type": entity_type_result,
                    "entity_id": entity_id,
                    "distance": distance,
                    "metadata": metadata,
                }
            )

        return formatted_results

    def semantic_search_dialogue(
        self,
        query_embedding: list[float],
        character_id: str | None = None,
        limit: int = 20,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Search for dialogue using semantic similarity.

        Args:
            query_embedding: Query embedding
            character_id: Optional character ID to filter by
            limit: Maximum number of results
            threshold: Minimum similarity threshold

        Returns:
            List of matching dialogue with scores
        """
        results = self.vectors.find_similar(
            query_vector=query_embedding,
            entity_type="dialogue",
            limit=limit,
            threshold=threshold,
        )

        # Convert tuple results to dict format and filter by character if specified
        formatted_results = []
        for entity_type_result, entity_id, distance, metadata in results:
            if character_id and metadata.get("character_id") != character_id:
                continue
            formatted_results.append(
                {
                    "entity_type": entity_type_result,
                    "entity_id": entity_id,
                    "distance": distance,
                    "metadata": metadata,
                }
            )

        return formatted_results

    def get_embedding_stats(self) -> dict[str, Any]:
        """Get statistics about stored embeddings.

        Returns:
            Dictionary of embedding statistics
        """
        return self.vectors.get_vector_stats()

    def delete_entity_embeddings(self, entity_type: str, entity_id: str) -> int:
        """Delete all embeddings for a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID

        Returns:
            Number of embeddings deleted
        """
        return self.vectors.delete_embeddings(
            entity_type=entity_type,
            entity_id=entity_id,
        )

    def batch_store_embeddings(
        self,
        embeddings: list[dict[str, Any]],
        batch_size: int = 100,
    ) -> dict[str, int]:
        """Store multiple embeddings in batches.

        Args:
            embeddings: List of embedding data dictionaries
            batch_size: Batch size for insertion

        Returns:
            Dictionary with counts of stored embeddings by type
        """
        counts = {"scene": 0, "character": 0, "dialogue": 0, "failed": 0}

        for i in range(0, len(embeddings), batch_size):
            batch = embeddings[i : i + batch_size]

            for emb_data in batch:
                try:
                    entity_type = emb_data.get("entity_type")
                    if entity_type not in counts:
                        counts["failed"] += 1
                        continue

                    result = self.vectors.store_embedding(
                        entity_type=entity_type,
                        entity_id=emb_data.get("entity_id") or "",
                        content=emb_data.get("content") or "",
                        embedding=emb_data.get("embedding") or [],
                        model_name=emb_data.get("model_name") or "default",
                    )

                    if result:
                        counts[entity_type] += 1
                    else:
                        counts["failed"] += 1

                except Exception as e:
                    logger.error(f"Failed to store embedding: {e}")
                    counts["failed"] += 1

        logger.info(
            f"Stored embeddings - Scenes: {counts['scene']}, "
            f"Characters: {counts['character']}, Dialogue: {counts['dialogue']}, "
            f"Failed: {counts['failed']}"
        )

        return counts

    def update_embedding_metadata(
        self,
        entity_type: str,
        entity_id: str,
        metadata: dict[str, Any],
        merge: bool = True,
    ) -> bool:
        """Update metadata for an embedding.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            metadata: New metadata
            merge: Whether to merge with existing metadata

        Returns:
            True if successful
        """
        try:
            # Get existing embedding
            with self.connection.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, metadata FROM embeddings
                    WHERE entity_type = ? AND entity_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (entity_type, entity_id),
                )
                row = cursor.fetchone()

                if not row:
                    logger.warning(f"No embedding found for {entity_type} {entity_id}")
                    return False

                embedding_id, existing_metadata = row

                if merge and existing_metadata:
                    # Merge with existing metadata
                    import json

                    existing = json.loads(existing_metadata)
                    existing.update(metadata)
                    metadata = existing

                # Update metadata
                conn.execute(
                    """
                    UPDATE embeddings
                    SET metadata = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (json.dumps(metadata), embedding_id),
                )

            logger.debug(f"Updated embedding metadata for {entity_type} {entity_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update embedding metadata: {e}")
            return False

    def get_entity_embedding(
        self, entity_type: str, entity_id: str
    ) -> dict[str, Any] | None:
        """Get the latest embedding for an entity.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID

        Returns:
            Embedding data or None
        """
        # Get embedding with default model name
        result = self.vectors.get_embedding(entity_type, entity_id, "default")
        if result:
            vector_array, metadata = result
            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "embedding": vector_array.tolist(),
                "metadata": metadata,
            }
        return None
