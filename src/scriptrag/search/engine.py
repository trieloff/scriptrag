"""Search engine for executing queries."""

import json
import sqlite3
import time
from contextlib import AbstractContextManager

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.database.readonly import get_read_only_connection
from scriptrag.search.builder import QueryBuilder
from scriptrag.search.models import (
    BibleSearchResult,
    SearchQuery,
    SearchResponse,
    SearchResult,
)

logger = get_logger(__name__)


class SearchEngine:
    """Execute search queries against the database."""

    def __init__(self, settings: ScriptRAGSettings | None = None):
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

    def get_read_only_connection(self) -> AbstractContextManager[sqlite3.Connection]:
        """Get a read-only database connection.

        Returns:
            Database connection in read-only mode
        """
        # Validate database path to prevent path traversal
        db_path_resolved = self.db_path.resolve()
        # Get the expected parent directory from the original settings path
        expected_parent = self.settings.database_path.parent.resolve()

        if not str(db_path_resolved).startswith(str(expected_parent)):
            raise ValueError("Invalid database path detected")

        return get_read_only_connection(self.settings)

    def search(self, query: SearchQuery) -> SearchResponse:
        """Execute a search query.

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
            raise FileNotFoundError(
                f"Database not found at {self.db_path}. "
                "Please run 'scriptrag init' first."
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
                total_count = count_cursor.fetchone()["total"]

                # Convert rows to SearchResult objects
                for idx, row in enumerate(rows):
                    # Parse metadata for season/episode with error handling
                    metadata = {}
                    if row["script_metadata"]:
                        try:
                            metadata = json.loads(row["script_metadata"])
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.warning(
                                f"Failed to parse metadata for script "
                                f"{row['script_id']}",
                                extra={
                                    "row_index": idx,
                                    "script_id": row["script_id"],
                                    "error": str(e),
                                },
                            )
                            metadata = {}

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
                        match_type=self._determine_match_type(query),
                    )
                    results.append(result)

            # Search bible content if include_bible is True or only_bible is True
            if query.include_bible or query.only_bible:
                bible_results, bible_total_count = self._search_bible_content(
                    conn, query
                )

            # Check if vector search is needed
            search_methods = ["sql"]
            if query.needs_vector_search:
                # TODO: Implement vector search integration
                search_methods.append("vector")
                logger.info("Vector search requested but not yet implemented")

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
            bible_total_count = count_cursor.fetchone()["total"]

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

        except Exception as e:
            logger.error(f"Error searching bible content: {e}")

        return bible_results, bible_total_count

    def _determine_match_type(self, query: SearchQuery) -> str:
        """Determine the type of match based on query.

        Args:
            query: Search query

        Returns:
            Match type string
        """
        if query.dialogue:
            return "dialogue"
        if query.action:
            return "action"
        if query.text_query:
            return "text"
        if query.characters:
            return "character"
        if query.locations:
            return "location"
        return "text"
