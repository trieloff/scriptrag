"""Query result formatter."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

from scriptrag.config import get_logger
from scriptrag.search.formatter import ResultFormatter
from scriptrag.search.models import SearchQuery, SearchResponse, SearchResult

logger = get_logger(__name__)


class QueryFormatter:
    """Format query results for display."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize formatter.

        Args:
            console: Rich console for output
        """
        self.console = console or Console()
        self.result_formatter = ResultFormatter(console=self.console)

    def format_results(
        self,
        rows: list[dict[str, Any]],
        query_name: str,
        execution_time_ms: float,
        output_json: bool = False,
        limit: int | None = None,
        offset: int | None = None,
    ) -> str | None:
        """Format query results for display.

        Args:
            rows: Query result rows
            query_name: Name of the executed query
            execution_time_ms: Query execution time in milliseconds
            output_json: Output as JSON instead of formatted display
            limit: Limit used in query
            offset: Offset used in query

        Returns:
            JSON string if output_json is True, None otherwise
        """
        logger.debug(
            "Formatting query results",
            query_name=query_name,
            row_count=len(rows),
            execution_time_ms=execution_time_ms,
            output_json=output_json,
            limit=limit,
            offset=offset,
        )

        if output_json:
            return self._format_json(rows, query_name, execution_time_ms)

        if not rows:
            logger.debug(f"No results found for query '{query_name}'")
            self.console.print(
                f"[yellow]No results found for query '{query_name}'.[/yellow]",
                style="bold",
            )
            return None

        # Check if results look like scenes
        if self._is_scene_like(rows):
            self._format_as_scenes(rows, query_name, execution_time_ms, limit, offset)
        else:
            self._format_as_table(rows, query_name, execution_time_ms)

        return None

    def _is_scene_like(self, rows: list[dict[str, Any]]) -> bool:
        """Check if results look like scene data.

        Args:
            rows: Result rows

        Returns:
            True if rows look like scenes
        """
        if not rows:
            return False

        # Check first row for scene-like columns
        first_row = rows[0]
        scene_columns = {
            "script_title",
            "scene_number",
            "scene_heading",
            "scene_content",
        }
        row_columns = set(first_row.keys())

        # Must have at least 3 of the 4 key scene columns
        matching = len(scene_columns & row_columns)
        is_scene = matching >= 3

        logger.debug(
            "Checking if results are scene-like",
            is_scene=is_scene,
            matching_columns=matching,
            total_columns=len(row_columns),
        )

        return is_scene

    def _format_as_scenes(
        self,
        rows: list[dict[str, Any]],
        query_name: str,
        execution_time_ms: float,
        limit: int | None,
        offset: int | None,
    ) -> None:
        """Format results as scenes using ResultFormatter.

        Args:
            rows: Result rows
            query_name: Query name
            execution_time_ms: Execution time
            limit: Query limit
            offset: Query offset
        """
        logger.debug(
            "Formatting query results as scenes",
            query_name=query_name,
            row_count=len(rows),
        )

        # Convert rows to SearchResult objects
        results = []
        for row in rows:
            # Handle different query result types
            scene_content = row.get("scene_content", "")

            # For character dialogue queries, include dialogue information
            if "dialogue" in row and "character" in row:
                character = row.get("character", "")
                dialogue = row.get("dialogue", "")
                parenthetical = row.get("parenthetical", "")

                # Format dialogue content for display
                dialogue_content = f"{character}: {dialogue}"
                if parenthetical:
                    dialogue_content = f"{character} ({parenthetical}): {dialogue}"

                # Use dialogue content if scene_content is empty
                if not scene_content:
                    scene_content = dialogue_content
                else:
                    scene_content += f"\n\n{dialogue_content}"

            result = SearchResult(
                script_id=row.get("script_id", 0),
                script_title=row.get("script_title", ""),
                script_author=row.get("script_author", ""),
                scene_id=row.get("scene_id", 0),
                scene_number=row.get("scene_number", 0),
                scene_heading=row.get("scene_heading", ""),
                scene_location=row.get("scene_location"),
                scene_time=row.get("scene_time"),
                scene_content=scene_content,
                season=row.get("season"),
                episode=row.get("episode"),
                match_type="query",
            )
            results.append(result)

        # Create a mock SearchQuery and SearchResponse
        mock_query = SearchQuery(
            raw_query=f"Query: {query_name}",
            text_query=f"Query: {query_name}",
            limit=limit or len(results),
            offset=offset or 0,
        )

        # Determine if there are more results (heuristic)
        has_more = len(results) == limit if limit else False

        response = SearchResponse(
            query=mock_query,
            results=results,
            total_count=len(results) + (1 if has_more else 0),
            has_more=has_more,
            execution_time_ms=execution_time_ms,
            search_methods=["sql"],
        )

        # Use ResultFormatter to display
        self.result_formatter.format_results(response)

    def _format_as_table(
        self,
        rows: list[dict[str, Any]],
        query_name: str,
        execution_time_ms: float,
    ) -> None:
        """Format results as a generic table.

        Args:
            rows: Result rows
            query_name: Query name
            execution_time_ms: Execution time
        """
        logger.debug(
            "Formatting query results as table",
            query_name=query_name,
            row_count=len(rows),
            column_count=len(rows[0]) if rows else 0,
        )

        # Display query info
        self.console.print(
            f"[bold]Query:[/bold] [cyan]{query_name}[/cyan] - "
            f"[dim]{len(rows)} rows in {execution_time_ms:.2f}ms[/dim]\n"
        )

        if not rows:
            return

        # Create table with overflow handling
        table = Table(show_header=True, header_style="bold magenta")

        # Add columns based on first row with proper overflow handling
        first_row = rows[0]
        for column in first_row:
            # For title columns, prevent truncation
            if "title" in column.lower() or "name" in column.lower():
                table.add_column(column, overflow="fold", no_wrap=False)
            else:
                table.add_column(column)

        # Add rows
        for row in rows:
            # Convert all values to strings, handling None
            row_values = [str(v) if v is not None else "" for v in row.values()]
            table.add_row(*row_values)

        self.console.print(table)

    def _format_json(
        self,
        rows: list[dict[str, Any]],
        query_name: str,
        execution_time_ms: float,
    ) -> str:
        """Format results as JSON.

        Args:
            rows: Result rows
            query_name: Query name
            execution_time_ms: Execution time

        Returns:
            JSON string
        """
        logger.debug(
            "Formatting query results as JSON",
            query_name=query_name,
            row_count=len(rows),
        )

        data = {
            "query": query_name,
            "results": rows,
            "count": len(rows),
            "execution_time_ms": execution_time_ms,
        }
        return json.dumps(data, indent=2, default=str)
