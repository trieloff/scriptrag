"""Vector search functionality for semantic search."""

import json
import sqlite3
import struct
from contextlib import suppress
from types import TracebackType

import numpy as np

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.llm.client import LLMClient
from scriptrag.llm.models import EmbeddingRequest
from scriptrag.search.models import SearchQuery, SearchResult
from scriptrag.utils import get_default_llm_client

logger = get_logger(__name__)


class VectorSearchEngine:
    """Handle vector/semantic search operations."""

    def __init__(self, settings: ScriptRAGSettings | None = None):
        """Initialize vector search engine.

        Args:
            settings: Configuration settings
        """
        if settings is None:
            from scriptrag.config import get_settings

            settings = get_settings()

        self.settings = settings
        self.llm_client: LLMClient | None = None
        self._query_embeddings_cache: dict[str, np.ndarray] = {}

    async def initialize(self) -> None:
        """Initialize the LLM client for embeddings."""
        if self.llm_client is None:
            self.llm_client = await get_default_llm_client()
            logger.info("Initialized LLM client for vector search")

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if self.llm_client is not None:
                # If the client has a cleanup method, call it
                if hasattr(self.llm_client, "cleanup"):
                    await self.llm_client.cleanup()
                elif hasattr(self.llm_client, "close"):
                    await self.llm_client.close()
        except Exception as e:
            logger.warning(f"Error cleaning up LLM client: {e}")
        finally:
            self.llm_client = None
            self._query_embeddings_cache.clear()

    async def __aenter__(self) -> "VectorSearchEngine":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.cleanup()

    async def generate_query_embedding(self, query_text: str) -> np.ndarray:
        """Generate embedding for a search query.

        Args:
            query_text: The query text to embed

        Returns:
            Numpy array of embeddings

        Raises:
            RuntimeError: If embedding generation fails
        """
        # Check cache first
        if query_text in self._query_embeddings_cache:
            logger.debug("Using cached query embedding")
            return self._query_embeddings_cache[query_text]

        if self.llm_client is None:
            try:
                await self.initialize()
            except Exception as e:
                logger.error(f"Failed to initialize LLM client: {e}")
                raise RuntimeError(f"Failed to initialize LLM client: {e}") from e

        if self.llm_client is None:
            raise RuntimeError("LLM client initialization returned None")

        # Generate embedding
        request = EmbeddingRequest(
            model=self.settings.llm_embedding_model or "",
            input=query_text,
            dimensions=self.settings.llm_embedding_dimensions,
        )

        try:
            response = await self.llm_client.embed(request)

            # Extract embedding vector
            if response.data and len(response.data) > 0:
                embedding_data = response.data[0]
                if hasattr(embedding_data, "embedding"):
                    embedding = np.array(embedding_data.embedding, dtype=np.float32)
                else:
                    # Handle dict response
                    embedding = np.array(embedding_data["embedding"], dtype=np.float32)

                # Cache it
                self._query_embeddings_cache[query_text] = embedding
                return embedding

            raise RuntimeError("No embedding data in response")

        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            raise RuntimeError(f"Failed to generate query embedding: {e}") from e

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score between -1 and 1
        """
        # Normalize vectors
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Calculate cosine similarity
        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def decode_embedding_blob(self, blob: bytes) -> np.ndarray:
        """Decode embedding blob from database.

        Args:
            blob: Binary blob from database

        Returns:
            Numpy array of embeddings
        """
        # Assuming embeddings are stored as float32 binary
        num_floats = len(blob) // 4
        floats = struct.unpack(f"{num_floats}f", blob)
        return np.array(floats, dtype=np.float32)

    async def search_similar_scenes(
        self,
        conn: sqlite3.Connection,
        query: SearchQuery,
        query_embedding: np.ndarray,
        limit: int = 10,
        threshold: float = 0.5,
    ) -> list[tuple[SearchResult, float]]:
        """Search for similar scenes using vector similarity.

        Args:
            conn: Database connection
            query: Search query
            query_embedding: Query embedding vector
            limit: Maximum number of results
            threshold: Minimum similarity threshold

        Returns:
            List of (SearchResult, similarity_score) tuples
        """
        results = []

        # Build base SQL query to get scenes with embeddings
        sql = """
            SELECT
                s.id as script_id,
                s.title as script_title,
                s.author as script_author,
                s.metadata as script_metadata,
                sc.id as scene_id,
                sc.scene_number,
                sc.heading as scene_heading,
                sc.location as scene_location,
                sc.time_of_day as scene_time,
                sc.content as scene_content,
                e.embedding as embedding_blob,
                e.embedding_model
            FROM embeddings e
            JOIN scenes sc ON e.entity_id = sc.id
            JOIN scripts s ON sc.script_id = s.id
            WHERE e.entity_type = 'scene'
        """

        params = []

        # Add filters if specified
        filters = []
        if query.project:
            filters.append("s.title = ?")
            params.append(query.project)

        if query.season_start is not None and query.season_end is not None:
            filters.append("json_extract(s.metadata, '$.season') BETWEEN ? AND ?")
            params.extend([str(query.season_start), str(query.season_end)])
        elif query.season_start is not None:
            filters.append("json_extract(s.metadata, '$.season') = ?")
            params.append(str(query.season_start))

        if query.episode_start is not None and query.episode_end is not None:
            filters.append("json_extract(s.metadata, '$.episode') BETWEEN ? AND ?")
            params.extend([str(query.episode_start), str(query.episode_end)])
        elif query.episode_start is not None:
            filters.append("json_extract(s.metadata, '$.episode') = ?")
            params.append(str(query.episode_start))

        if filters:
            sql += " AND " + " AND ".join(filters)

        try:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

            for row in rows:
                try:
                    # Decode embedding
                    scene_embedding = self.decode_embedding_blob(row["embedding_blob"])

                    # Calculate similarity
                    similarity = self.cosine_similarity(
                        query_embedding, scene_embedding
                    )

                    if similarity >= threshold:
                        # Parse metadata
                        metadata = {}
                        if row["script_metadata"]:
                            with suppress(json.JSONDecodeError, TypeError):
                                metadata = json.loads(row["script_metadata"])

                        result = SearchResult(
                            script_id=row["script_id"],
                            script_title=row["script_title"],
                            script_author=row["script_author"],
                            scene_id=row["scene_id"],
                            scene_number=row["scene_number"],
                            scene_heading=row["scene_heading"],
                            scene_location=row["scene_location"],
                            scene_time=row["scene_time"],
                            scene_content=row["scene_content"],
                            season=metadata.get("season"),
                            episode=metadata.get("episode"),
                            match_type="vector",
                            relevance_score=similarity,
                        )
                        results.append((result, similarity))

                except Exception as e:
                    logger.warning(
                        f"Failed to process embedding for scene {row['scene_id']}: {e}"
                    )
                    continue

            # Sort by similarity score (descending)
            results.sort(key=lambda x: x[1], reverse=True)

            # Apply limit
            results = results[:limit]

            logger.info(
                f"Found {len(results)} similar scenes with threshold {threshold}"
            )

        except Exception as e:
            logger.error(f"Failed to search similar scenes: {e}")
            # Return empty results on error
            return []

        return results

    async def enhance_results_with_vector_search(
        self,
        conn: sqlite3.Connection,
        query: SearchQuery,
        existing_results: list[SearchResult],
        limit: int = 5,
    ) -> list[SearchResult]:
        """Enhance search results with vector search.

        Args:
            conn: Database connection
            query: Search query
            existing_results: Results from SQL search
            limit: Maximum number of vector results to add

        Returns:
            Combined and deduplicated results
        """
        # Extract query text for embedding
        query_text = query.dialogue or query.action or query.text_query or ""

        if not query_text:
            # No text to generate embeddings from
            return existing_results

        try:
            # Generate query embedding
            query_embedding = await self.generate_query_embedding(query_text)

            # Search for similar scenes
            vector_results = await self.search_similar_scenes(
                conn=conn,
                query=query,
                query_embedding=query_embedding,
                limit=limit * 2,  # Get more to allow for deduplication
                threshold=self.settings.search_vector_similarity_threshold,
            )

            # Create a set of existing scene IDs for deduplication
            existing_scene_ids = {r.scene_id for r in existing_results}

            # Add non-duplicate vector results
            added_count = 0
            combined_results = list(existing_results)

            for result, _ in vector_results:
                if result.scene_id not in existing_scene_ids:
                    combined_results.append(result)
                    existing_scene_ids.add(result.scene_id)
                    added_count += 1
                    if added_count >= limit:
                        break

            logger.info(f"Added {added_count} vector search results")
            return combined_results

        except Exception as e:
            logger.error(f"Failed to enhance with vector search: {e}")
            # Return original results on error
            return existing_results
