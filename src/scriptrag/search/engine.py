"""Search engine for executing queries."""

import json
import sqlite3
import time
from collections.abc import Generator
from contextlib import contextmanager

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.search.builder import QueryBuilder
from scriptrag.search.models import SearchQuery, SearchResponse, SearchResult

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

    @contextmanager
    def get_read_only_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a read-only database connection with context manager.

        Yields:
            Read-only SQLite connection
        """
        conn = None
        try:
            # Validate database path to prevent path traversal
            db_path_resolved = self.db_path.resolve()
            if not str(db_path_resolved).startswith(
                str(self.settings.database_path.parent.resolve())
            ):
                raise ValueError("Invalid database path detected")

            # Open connection in read-only mode
            uri = f"file:{db_path_resolved}?mode=ro"
            conn = sqlite3.connect(
                uri,
                uri=True,
                timeout=self.settings.database_timeout,
                check_same_thread=False,
            )

            # Configure for read-only access
            conn.execute("PRAGMA query_only = ON")
            conn.execute(f"PRAGMA cache_size = {self.settings.database_cache_size}")
            conn.execute(f"PRAGMA temp_store = {self.settings.database_temp_store}")

            # Enable JSON support
            conn.row_factory = sqlite3.Row

            yield conn
        finally:
            if conn:
                conn.close()

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
            results = []
            for idx, row in enumerate(rows):
                # Parse metadata for season/episode with error handling
                metadata = {}
                if row["script_metadata"]:
                    try:
                        metadata = json.loads(row["script_metadata"])
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(
                            f"Failed to parse metadata for script {row['script_id']}",
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

            # Check if vector search is needed
            search_methods = ["sql"]
            if query.needs_vector_search:
                # TODO: Implement vector search integration
                search_methods.append("vector")
                logger.info("Vector search requested but not yet implemented")

            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000

            # Create response
            response = SearchResponse(
                query=query,
                results=results,
                total_count=total_count,
                has_more=(total_count > query.offset + query.limit),
                execution_time_ms=execution_time_ms,
                search_methods=search_methods,
            )

            logger.info(
                f"Search completed: {len(results)} results found "
                f"(total: {total_count}) in {execution_time_ms:.2f}ms"
            )

            return response

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
