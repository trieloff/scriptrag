"""High-level embedding pipeline for screenplay content.

This module provides a complete pipeline for generating, storing, and
managing embeddings for screenplay elements. It orchestrates the content
extraction, embedding generation, and storage processes.
"""

from typing import Any

from scriptrag.config import get_logger, get_settings
from scriptrag.llm.client import LLMClient

from .connection import DatabaseConnection
from .content_extractor import ContentExtractor
from .embeddings import EmbeddingContent, EmbeddingError, EmbeddingManager

logger = get_logger(__name__)


class EmbeddingPipeline:
    """High-level pipeline for managing screenplay embeddings.

    Provides convenient methods for generating embeddings for entire scripts,
    individual elements, and managing the embedding lifecycle.
    """

    def __init__(
        self,
        connection: DatabaseConnection,
        llm_client: LLMClient | None = None,
        embedding_model: str | None = None,
    ) -> None:
        """Initialize embedding pipeline.

        Args:
            connection: Database connection instance
            llm_client: LLM client for generating embeddings
            embedding_model: Model name for embeddings
        """
        self.connection = connection
        self.config = get_settings()

        # Initialize components
        self.llm_client = llm_client or LLMClient()
        self.embedding_manager = EmbeddingManager(
            connection, self.llm_client, embedding_model
        )
        self.content_extractor = ContentExtractor(connection)

    def _filter_existing_embeddings(
        self, contents: list[EmbeddingContent], force_refresh: bool
    ) -> list[EmbeddingContent]:
        """Filter out existing embeddings unless force refresh is enabled.

        Args:
            contents: List of content to filter
            force_refresh: If True, return all contents without filtering

        Returns:
            Filtered list of contents without existing embeddings
        """
        if force_refresh:
            return contents

        filtered_contents = []
        for content in contents:
            existing = self.embedding_manager.get_embedding(
                content["entity_type"], content["entity_id"]
            )
            if existing is None:
                filtered_contents.append(content)

        skipped_count = len(contents) - len(filtered_contents)
        if skipped_count > 0:
            logger.info(
                "Skipping existing embeddings",
                skipped=skipped_count,
                remaining=len(filtered_contents),
            )

        return filtered_contents

    async def process_script(
        self,
        script_id: str,
        force_refresh: bool = False,
        batch_size: int | None = None,
    ) -> dict[str, Any]:
        """Process all elements of a script for embedding generation.

        Args:
            script_id: Script ID to process
            force_refresh: Force regeneration of existing embeddings
            batch_size: Batch size for embedding generation
                (uses config default if None)

        Returns:
            Processing results with statistics

        Raises:
            EmbeddingError: If processing fails
        """
        # Use configured batch size if none provided
        if batch_size is None:
            batch_size = self.config.llm.batch_size

        logger.info(
            "Starting script embedding processing",
            script_id=script_id,
            force_refresh=force_refresh,
            batch_size=batch_size,
        )

        try:
            # Extract all content from the script
            contents = self.content_extractor.extract_all_script_elements(script_id)

            if not contents:
                logger.warning("No content extracted from script", script_id=script_id)
                return {
                    "script_id": script_id,
                    "total_contents": 0,
                    "embeddings_generated": 0,
                    "embeddings_stored": 0,
                    "status": "no_content",
                }

            # Filter out existing embeddings if not forcing refresh
            contents = self._filter_existing_embeddings(contents, force_refresh)

            if not contents:
                logger.info("All embeddings already exist", script_id=script_id)
                return {
                    "script_id": script_id,
                    "total_contents": len(contents),
                    "embeddings_generated": 0,
                    "embeddings_stored": 0,
                    "status": "already_exists",
                }

            # Generate embeddings in batches
            embeddings = await self.embedding_manager.generate_embeddings(
                contents, batch_size=batch_size
            )

            # Store embeddings
            stored_count = await self.embedding_manager.store_embeddings(embeddings)

            # Get final statistics
            stats = self.embedding_manager.get_embeddings_stats()

            logger.info(
                "Completed script embedding processing",
                script_id=script_id,
                contents_processed=len(contents),
                embeddings_generated=len(embeddings),
                embeddings_stored=stored_count,
            )

            return {
                "script_id": script_id,
                "total_contents": len(contents),
                "embeddings_generated": len(embeddings),
                "embeddings_stored": stored_count,
                "status": "success",
                "embedding_stats": stats,
            }

        except Exception as e:
            logger.error(
                "Script embedding processing failed",
                script_id=script_id,
                error=str(e),
            )
            raise EmbeddingError(f"Script processing failed: {e}") from e

    async def process_scene(
        self,
        scene_id: str,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Process a single scene for embedding generation.

        Args:
            scene_id: Scene ID to process
            force_refresh: Force regeneration of existing embeddings

        Returns:
            Processing results

        Raises:
            EmbeddingError: If processing fails
        """
        logger.info("Processing scene", scene_id=scene_id, force_refresh=force_refresh)

        try:
            # Extract scene content
            contents = self.content_extractor.extract_scene_content(scene_id)

            if not contents:
                return {
                    "scene_id": scene_id,
                    "total_contents": 0,
                    "embeddings_generated": 0,
                    "embeddings_stored": 0,
                    "status": "no_content",
                }

            # Filter existing if not forcing refresh
            contents = self._filter_existing_embeddings(contents, force_refresh)

            if not contents:
                return {
                    "scene_id": scene_id,
                    "total_contents": 0,
                    "embeddings_generated": 0,
                    "embeddings_stored": 0,
                    "status": "already_exists",
                }

            # Generate and store embeddings
            embeddings = await self.embedding_manager.generate_embeddings(contents)
            stored_count = await self.embedding_manager.store_embeddings(embeddings)

            logger.info(
                "Processed scene",
                scene_id=scene_id,
                embeddings_stored=stored_count,
            )

            return {
                "scene_id": scene_id,
                "total_contents": len(contents),
                "embeddings_generated": len(embeddings),
                "embeddings_stored": stored_count,
                "status": "success",
            }

        except Exception as e:
            logger.error("Scene processing failed", scene_id=scene_id, error=str(e))
            raise EmbeddingError(f"Scene processing failed: {e}") from e

    async def process_character(
        self,
        character_id: str,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Process a single character for embedding generation.

        Args:
            character_id: Character ID to process
            force_refresh: Force regeneration of existing embeddings

        Returns:
            Processing results

        Raises:
            EmbeddingError: If processing fails
        """
        logger.info(
            "Processing character",
            character_id=character_id,
            force_refresh=force_refresh,
        )

        try:
            # Extract character content
            contents = self.content_extractor.extract_character_content(character_id)

            if not contents:
                return {
                    "character_id": character_id,
                    "total_contents": 0,
                    "embeddings_generated": 0,
                    "embeddings_stored": 0,
                    "status": "no_content",
                }

            # Filter existing if not forcing refresh
            contents = self._filter_existing_embeddings(contents, force_refresh)

            if not contents:
                return {
                    "character_id": character_id,
                    "total_contents": 0,
                    "embeddings_generated": 0,
                    "embeddings_stored": 0,
                    "status": "already_exists",
                }

            # Generate and store embeddings
            embeddings = await self.embedding_manager.generate_embeddings(contents)
            stored_count = await self.embedding_manager.store_embeddings(embeddings)

            logger.info(
                "Processed character",
                character_id=character_id,
                embeddings_stored=stored_count,
            )

            return {
                "character_id": character_id,
                "total_contents": len(contents),
                "embeddings_generated": len(embeddings),
                "embeddings_stored": stored_count,
                "status": "success",
            }

        except Exception as e:
            logger.error(
                "Character processing failed",
                character_id=character_id,
                error=str(e),
            )
            raise EmbeddingError(f"Character processing failed: {e}") from e

    async def semantic_search(
        self,
        query: str,
        entity_type: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.1,
    ) -> list[dict[str, Any]]:
        """Perform semantic search across screenplay content.

        Args:
            query: Natural language search query
            entity_type: Filter by entity type (scene, character, etc.)
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold

        Returns:
            List of search results with entity details

        Raises:
            EmbeddingError: If search fails
        """
        logger.info(
            "Performing semantic search",
            query=query[:50],
            entity_type=entity_type,
            limit=limit,
        )

        try:
            # Perform embedding-based search
            results = await self.embedding_manager.semantic_search(
                query,
                entity_type=entity_type,
                limit=limit,
                min_similarity=min_similarity,
            )

            # Enhance results with entity details
            enhanced_results = []
            for result in results:
                enhanced_result = dict(result)

                # Add entity details based on type
                if result["entity_type"] == "scene":
                    scene_row = self.connection.fetch_one(
                        "SELECT heading, script_order FROM scenes WHERE id = ?",
                        (result["entity_id"],),
                    )
                    if scene_row:
                        enhanced_result["entity_details"] = {
                            "heading": scene_row["heading"],
                            "script_order": scene_row["script_order"],
                        }

                elif result["entity_type"] == "character":
                    char_row = self.connection.fetch_one(
                        "SELECT name, description FROM characters WHERE id = ?",
                        (result["entity_id"],),
                    )
                    if char_row:
                        enhanced_result["entity_details"] = {
                            "name": char_row["name"],
                            "description": char_row["description"],
                        }

                elif result["entity_type"] == "location":
                    loc_row = self.connection.fetch_one(
                        "SELECT name, raw_text FROM locations WHERE id = ?",
                        (result["entity_id"],),
                    )
                    if loc_row:
                        enhanced_result["entity_details"] = {
                            "name": loc_row["name"],
                            "raw_text": loc_row["raw_text"],
                        }

                enhanced_results.append(enhanced_result)

            logger.info(
                "Semantic search completed",
                query=query[:50],
                results_count=len(enhanced_results),
            )

            return enhanced_results

        except Exception as e:
            logger.error("Semantic search failed", query=query[:50], error=str(e))
            raise EmbeddingError(f"Semantic search failed: {e}") from e

    async def get_similar_scenes(
        self,
        scene_id: str,
        limit: int = 10,
        min_similarity: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Find scenes similar to a given scene.

        Args:
            scene_id: Reference scene ID
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold

        Returns:
            List of similar scenes with similarity scores

        Raises:
            EmbeddingError: If search fails
        """
        try:
            # Get embedding for the reference scene
            scene_embedding = self.embedding_manager.get_embedding("scene", scene_id)

            if not scene_embedding:
                logger.warning("No embedding found for scene", scene_id=scene_id)
                return []

            # Find similar scenes
            results = self.embedding_manager.find_similar(
                scene_embedding,
                entity_type="scene",
                limit=limit + 1,  # +1 to account for the scene itself
                min_similarity=min_similarity,
            )

            # Filter out the reference scene itself and enhance with details
            similar_scenes = []
            for result in results:
                if result["entity_id"] != scene_id:
                    scene_row = self.connection.fetch_one(
                        """
                        SELECT heading, script_order, description
                        FROM scenes WHERE id = ?
                        """,
                        (result["entity_id"],),
                    )

                    if scene_row:
                        enhanced_result = dict(result)
                        enhanced_result["entity_details"] = {
                            "heading": scene_row["heading"],
                            "script_order": scene_row["script_order"],
                            "description": scene_row["description"],
                        }
                        similar_scenes.append(enhanced_result)

            logger.info(
                "Found similar scenes",
                scene_id=scene_id,
                similar_count=len(similar_scenes),
            )

            return similar_scenes[:limit]

        except Exception as e:
            logger.error("Similar scene search failed", scene_id=scene_id, error=str(e))
            raise EmbeddingError(f"Similar scene search failed: {e}") from e

    def get_embedding_stats(self) -> dict[str, Any]:
        """Get comprehensive embedding statistics.

        Returns:
            Dictionary with embedding statistics
        """
        try:
            return self.embedding_manager.get_embeddings_stats()
        except Exception as e:
            logger.error("Failed to get embedding stats", error=str(e))
            return {"error": str(e)}

    async def cleanup_embeddings(
        self,
        entity_type: str | None = None,
        older_than_days: int | None = None,
    ) -> int:
        """Clean up old or orphaned embeddings.

        Args:
            entity_type: Filter by entity type
            older_than_days: Remove embeddings older than N days

        Returns:
            Number of embeddings removed
        """
        try:
            where_conditions = []
            params = []

            # Add entity type filter if specified
            if entity_type:
                where_conditions.append("entity_type = ?")
                params.append(entity_type)

            # Add age filter if specified
            if older_than_days:
                where_conditions.append("created_at < datetime('now', '-{} days')".format(older_than_days))

            # Build the WHERE clause
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

            with self.connection.transaction() as conn:
                cursor = conn.execute(
                    f"DELETE FROM embeddings WHERE {where_clause}",
                    params,
                )
                deleted_count = cursor.rowcount

            logger.info(
                "Cleanup embeddings completed",
                entity_type=entity_type,
                older_than_days=older_than_days,
                deleted_count=deleted_count,
            )
            return deleted_count

        except Exception as e:
            logger.error(
                "Failed to cleanup embeddings",
                entity_type=entity_type,
                older_than_days=older_than_days,
                error=str(e),
            )
            raise

    async def close(self) -> None:
        """Close the pipeline and cleanup resources."""
        if self.embedding_manager:
            await self.embedding_manager.close()


# Convenience functions for common operations
async def create_script_embeddings(
    script_id: str,
    connection: DatabaseConnection,
    llm_client: LLMClient | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Create embeddings for an entire script.

    Args:
        script_id: Script ID to process
        connection: Database connection
        llm_client: LLM client (created if None)
        force_refresh: Force regeneration of existing embeddings

    Returns:
        Processing results
    """
    pipeline = EmbeddingPipeline(connection, llm_client)
    try:
        return await pipeline.process_script(script_id, force_refresh=force_refresh)
    finally:
        await pipeline.close()


async def search_screenplay_content(
    query: str,
    connection: DatabaseConnection,
    llm_client: LLMClient | None = None,
    entity_type: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search screenplay content using natural language.

    Args:
        query: Search query
        connection: Database connection
        llm_client: LLM client (created if None)
        entity_type: Filter by entity type
        limit: Maximum results

    Returns:
        Search results
    """
    pipeline = EmbeddingPipeline(connection, llm_client)
    try:
        return await pipeline.semantic_search(
            query, entity_type=entity_type, limit=limit
        )
    finally:
        await pipeline.close()
