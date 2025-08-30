"""Query API facade."""

from __future__ import annotations

from typing import Any

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.query import QueryEngine, QueryFormatter, QueryLoader, QuerySpec

logger = get_logger(__name__)


class QueryAPI:
    """High-level API for query operations."""

    def __init__(self, settings: ScriptRAGSettings | None = None) -> None:
        """Initialize query API.

        Args:
            settings: Configuration settings
        """
        if settings is None:
            from scriptrag.config import get_settings

            settings = get_settings()

        self.settings = settings
        self.loader = QueryLoader(settings)
        # CRITICAL: Don't pass settings to QueryEngine - let it get fresh settings
        # This ensures integration tests that modify environment variables work
        self.engine = QueryEngine()
        self.formatter = QueryFormatter()

    def list_queries(self) -> list[QuerySpec]:
        """List all available queries.

        Example:
            >>> api = QueryAPI()
            >>> queries = api.list_queries()
            >>> for query in queries:
            ...     print(f"{query.name}: {query.description}")

        Returns:
            List of query specifications
        """
        return self.loader.list_queries()

    def get_query(self, name: str) -> QuerySpec | None:
        """Get a query by name.

        Args:
            name: Query name

        Returns:
            Query specification or None if not found
        """
        return self.loader.get_query(name)

    def execute_query(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        output_json: bool = False,
    ) -> str | None:
        """Execute a query by name.

        Examples:
            >>> api = QueryAPI()
            >>> # Execute a simple query
            >>> api.execute_query("character_lines")
            >>> # With parameters
            >>> api.execute_query("character_lines", {"character": "ALICE"})
            >>> # With pagination
            >>> api.execute_query("scenes", limit=10, offset=20)
            >>> # Get JSON output
            >>> json_result = api.execute_query("scenes", output_json=True)

        Args:
            name: Query name
            params: Query parameters
            limit: Row limit
            offset: Row offset
            output_json: Return JSON instead of formatted display

        Returns:
            JSON string if output_json is True, None otherwise

        Raises:
            ValueError: If query not found or execution fails
        """
        # Get query spec
        spec = self.loader.get_query(name)
        if not spec:
            raise ValueError(f"Query '{name}' not found")

        # Execute query
        try:
            rows, execution_time = self.engine.execute(spec, params, limit, offset)
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

        # Format results
        return self.formatter.format_results(
            rows=rows,
            query_name=name,
            execution_time_ms=execution_time,
            output_json=output_json,
            limit=limit,
            offset=offset,
        )

    def reload_queries(self) -> None:
        """Reload queries from disk."""
        self.loader.discover_queries(force_reload=True)
