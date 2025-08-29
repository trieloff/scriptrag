"""Search engine for executing queries."""

import asyncio
import sqlite3
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.database.readonly import get_read_only_connection
from scriptrag.exceptions import DatabaseError
from scriptrag.search.builder import QueryBuilder
from scriptrag.search.filters import BibleContentFilter, DuplicateFilter
from scriptrag.search.models import (
    BibleSearchResult,
    SearchQuery,
    SearchResponse,
    SearchResult,
)
from scriptrag.search.rankers import BibleResultRanker, HybridRanker
from scriptrag.search.semantic_adapter import SemanticSearchAdapter
from scriptrag.search.utils import SearchResultUtils

logger = get_logger(__name__)


class SearchEngine:
    """Execute search queries against the database."""

    def __init__(self, settings: ScriptRAGSettings | None = None) -> None:
        """Initialize search engine.

        Args:
            settings: Configuration settings
        """
        if settings is None:
            from scriptrag.config import get_settings

            settings = get_settings()

        self.settings = settings
        self.db_path = settings.database_path
        self.query_builder = QueryBuilder()
        self.semantic_adapter = SemanticSearchAdapter(settings)
        self.result_utils = SearchResultUtils()
        self.ranker = HybridRanker()
        self.duplicate_filter = DuplicateFilter()

    @contextmanager
    def get_read_only_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a read-only database connection.

        Yields:
            Database connection in read-only mode

        Raises:
            DatabaseError: If database path is invalid or connection fails
        """
        # The path validation is already handled in get_read_only_connection
        # which performs comprehensive security checks including:
        # - Path traversal detection
        # - Disallowed system directories
        # - Proper cross-platform validation
        try:
            with get_read_only_connection(self.settings) as conn:
                yield conn
        except ValueError as e:
            # Only catch path validation errors, not other ValueErrors
            if "Invalid database path detected" in str(e):
                # Convert path validation errors to DatabaseError
                raise DatabaseError(
                    message="Invalid database path",
                    hint="Check database path configuration",
                    details={"error": str(e), "path": str(self.settings.database_path)},
                ) from e
            else:
                # Re-raise other ValueErrors as-is
                raise

    def _cleanup_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Clean up an event loop by cancelling pending tasks.

        Args:
            loop: The event loop to clean up
        """
        # Cancel all pending tasks before closing the loop
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        # Run the loop one more time to let tasks handle cancellation
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

    def search(self, query: SearchQuery) -> SearchResponse:
        """Execute a search query (synchronous wrapper).

        Args:
            query: Parsed search query

        Returns:
            Search response with results

        Raises:
            FileNotFoundError: If database doesn't exist
            ValueError: If database path is invalid
            DatabaseError: If database operations fail
        """
        # Check if we're already in an event loop
        try:
            asyncio.get_running_loop()
            # We're in an async context, can't use run_until_complete
            # Create a new thread to run the async function

            result: SearchResponse | None = None
            exception: Exception | None = None

            def run_in_new_loop() -> None:
                nonlocal result, exception
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result = new_loop.run_until_complete(self.search_async(query))
                except Exception as e:
                    exception = e
                finally:
                    self._cleanup_event_loop(new_loop)
                    new_loop.close()

            thread = threading.Thread(target=run_in_new_loop)
            thread.start()
            thread.join(timeout=self.settings.search_thread_timeout)

            # Check if thread is still alive (timeout occurred)
            if thread.is_alive():
                logger.error(
                    "Search thread timed out after %s seconds",
                    self.settings.search_thread_timeout,
                )
                raise RuntimeError("Search operation timed out")

            if exception is not None:
                logger.error(
                    "Search failed",
                    query=query.raw_query[:100] if query.raw_query else None,
                    error=str(exception),
                )
                raise exception
            if result is None:
                raise RuntimeError("Search result should not be None")
            return result
        except RuntimeError:
            # No event loop is running, we can create one
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self.search_async(query))
            except Exception as e:
                logger.error(
                    "Search failed",
                    query=query.raw_query[:100] if query.raw_query else None,
                    error=str(e),
                )
                raise
            finally:
                self._cleanup_event_loop(loop)
                loop.close()

    async def search_async(self, query: SearchQuery) -> SearchResponse:
        """Execute a search query asynchronously.

        Args:
            query: Parsed search query

        Returns:
            Search response with results

        Raises:
            FileNotFoundError: If database doesn't exist
            ValueError: If database path is invalid
        """
        start_time = time.time()

        # Check if database exists
        if not self.db_path.exists():
            import os
            from pathlib import Path

            # Check for common database locations
            hints = []
            if Path("scriptrag.db").exists():
                hints.append("Found scriptrag.db here. Use --database scriptrag.db")
            else:
                hints.append("Run 'scriptrag init' to create a new database")

            raise DatabaseError(
                message=f"Database not found at {self.db_path}",
                hint=" ".join(hints),
                details={
                    "searched_path": str(self.db_path),
                    "current_dir": str(Path.cwd()),
                    "env_var": os.environ.get("SCRIPTRAG_DATABASE_PATH", "Not set"),
                },
            )

        with self.get_read_only_connection() as conn:
            results: list[SearchResult] = []
            bible_results: list[BibleSearchResult] = []
            total_count = 0
            bible_total_count = 0

            # Search script content unless only_bible is True
            if not query.only_bible:
                # Build and execute search query
                sql, params = self.query_builder.build_search_query(query)

                logger.debug(f"Executing search query: {sql[:200]}...")
                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()

                # Build and execute count query for pagination
                count_sql, count_params = self.query_builder.build_count_query(query)
                count_cursor = conn.execute(count_sql, count_params)
                count_result = count_cursor.fetchone()
                # Handle None result or missing 'total' key gracefully
                if count_result:
                    try:
                        total_count = count_result["total"] or 0
                    except (KeyError, TypeError, IndexError):
                        # Handle various cases where 'total' key is missing
                        total_count = 0
                else:
                    total_count = 0

                # Convert rows to SearchResult objects
                for idx, row in enumerate(rows):
                    # Parse metadata using utility
                    metadata = self.result_utils.parse_metadata(
                        row["script_metadata"],
                        {"row_index": idx, "script_id": row["script_id"]},
                    )

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
                        match_type=self.result_utils.determine_match_type(query),
                    )
                    results.append(result)

            # Search bible content if include_bible is True or only_bible is True
            if query.include_bible or query.only_bible:
                bible_results, bible_total_count = self._search_bible_content(
                    conn, query
                )

            # Check if semantic search is needed
            search_methods = ["sql"]
            if query.needs_vector_search:
                search_methods.append("semantic")
                logger.info("Performing semantic search to enhance results")

                # Enhance results with semantic search
                try:
                    # Use configurable settings for semantic search
                    limit_factor = self.settings.search_vector_result_limit_factor
                    semantic_limit = max(
                        self.settings.search_vector_min_results,
                        int(query.limit * limit_factor),
                    )
                    enhance = self.semantic_adapter.enhance_results_with_semantic_search
                    (
                        enhanced_results,
                        semantic_bible_results,
                    ) = await enhance(
                        query=query,
                        existing_results=results,
                        limit=semantic_limit,
                    )
                    results = enhanced_results

                    # Merge semantic bible results with existing ones
                    if semantic_bible_results:
                        # Add to existing bible results, avoiding duplicates
                        existing_bible_ids = {br.chunk_id for br in bible_results}
                        for sbr in semantic_bible_results:
                            if sbr.chunk_id not in existing_bible_ids:
                                bible_results.append(sbr)
                                existing_bible_ids.add(sbr.chunk_id)

                except Exception as e:
                    logger.error(
                        "Semantic search failed, falling back to SQL results",
                        error=str(e),
                        query=query.raw_query[:100] if query.raw_query else None,
                        error_type=type(e).__name__,
                    )
                    # Continue with SQL results only - this is a graceful degradation

            # Apply duplicate filtering and ranking
            results = self.duplicate_filter.filter(results, query)
            results = self.ranker.rank(results, query)

            # Rank bible results if present
            if bible_results:
                bible_results = BibleContentFilter.deduplicate(bible_results)
                query_text = query.dialogue or query.action or query.text_query or ""
                if query_text:
                    bible_results = BibleResultRanker.rank_by_relevance(
                        bible_results, query_text
                    )
                else:
                    bible_results = BibleResultRanker.rank_by_hierarchy(bible_results)

            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000

            # Create response
            total_results = len(results) + len(bible_results)
            combined_total = total_count + bible_total_count
            response = SearchResponse(
                query=query,
                results=results,
                bible_results=bible_results,
                total_count=total_count,
                bible_total_count=bible_total_count,
                has_more=(combined_total > query.offset + query.limit),
                execution_time_ms=execution_time_ms,
                search_methods=search_methods,
            )

            logger.info(
                f"Search completed: {total_results} results found "
                f"(scenes: {len(results)}, bible: {len(bible_results)}) "
                f"in {execution_time_ms:.2f}ms"
            )

            return response

    def _search_bible_content(
        self, conn: sqlite3.Connection, query: SearchQuery
    ) -> tuple[list[BibleSearchResult], int]:
        """Search bible content based on query.

        Args:
            conn: Database connection
            query: Search query

        Returns:
            Tuple of (bible results, total count)
        """
        bible_results = []
        bible_total_count = 0

        try:
            # Build SQL for bible search
            sql_parts = []
            params = []

            # Base query
            base_sql = """
                SELECT
                    s.id AS script_id,
                    s.title AS script_title,
                    sb.id AS bible_id,
                    sb.title AS bible_title,
                    bc.id AS chunk_id,
                    bc.heading AS chunk_heading,
                    bc.level AS chunk_level,
                    bc.content AS chunk_content
                FROM bible_chunks bc
                JOIN script_bibles sb ON bc.bible_id = sb.id
                JOIN scripts s ON sb.script_id = s.id
                WHERE 1=1
            """
            sql_parts.append(base_sql)

            # Add text search conditions
            if query.text_query:
                sql_parts.append("AND (bc.content LIKE ? OR bc.heading LIKE ?)")
                search_pattern = f"%{query.text_query}%"
                params.extend([search_pattern, search_pattern])

            # Add project filter if specified
            if query.project:
                sql_parts.append("AND s.title = ?")
                params.append(query.project)

            # Add ordering and pagination
            sql_parts.append("ORDER BY bc.bible_id, bc.chunk_number")
            sql_parts.append(f"LIMIT {query.limit} OFFSET {query.offset}")

            # Execute search query
            sql = " ".join(sql_parts)
            logger.debug(f"Executing bible search query: {sql[:200]}...")
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

            # Count query (without LIMIT/OFFSET)
            count_sql = (
                " ".join(sql_parts[:-2])
                .replace(
                    "SELECT s.id AS script_id",
                    "SELECT COUNT(*) as total",
                )
                .split("FROM")[1]
            )
            count_sql = "SELECT COUNT(*) as total FROM " + count_sql
            count_cursor = conn.execute(count_sql, params)
            count_result = count_cursor.fetchone()
            bible_total_count = count_result["total"] if count_result else 0

            # Convert rows to BibleSearchResult objects
            for row in rows:
                result = BibleSearchResult(
                    script_id=row["script_id"],
                    script_title=row["script_title"],
                    bible_id=row["bible_id"],
                    bible_title=row["bible_title"],
                    chunk_id=row["chunk_id"],
                    chunk_heading=row["chunk_heading"],
                    chunk_level=row["chunk_level"],
                    chunk_content=row["chunk_content"],
                    match_type="text",
                )
                bible_results.append(result)

        except sqlite3.Error as e:
            logger.error(
                "Database error during bible search",
                error=str(e),
                query=query.raw_query[:100] if query.raw_query else None,
                project=query.project,
            )
            # Return empty results for graceful degradation
        except Exception as e:
            logger.error(
                "Unexpected error searching bible content",
                error=str(e),
                error_type=type(e).__name__,
                query=query.raw_query[:100] if query.raw_query else None,
            )
            # Return empty results for graceful degradation

        return bible_results, bible_total_count
