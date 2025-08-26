"""Query result formatter for CLI."""

import json
from typing import Any

from scriptrag.cli.formatters.base import OutputFormat, OutputFormatter
from scriptrag.cli.formatters.table_formatter import TableFormatter


class QueryResultFormatter(OutputFormatter[list[dict[str, Any]]]):
    """Formatter for SQL query results."""

    def __init__(self) -> None:
        """Initialize query formatter."""
        super().__init__()
        self.table_formatter = TableFormatter()

    def format(
        self, data: list[dict[str, Any]], format_type: OutputFormat = OutputFormat.TABLE
    ) -> str:
        """Format query results.

        Args:
            data: Query result rows
            format_type: Output format type

        Returns:
            Formatted string
        """
        if not data:
            return self._format_empty_result(format_type)

        if format_type == OutputFormat.JSON:
            return json.dumps(data, default=str, indent=2)
        if format_type in (OutputFormat.TABLE, OutputFormat.CSV, OutputFormat.MARKDOWN):
            return self.table_formatter.format(data, format_type)
        # Default text format
        return self._format_text(data)

    def _format_empty_result(self, format_type: OutputFormat) -> str:
        """Format empty query result."""
        if format_type == OutputFormat.JSON:
            return json.dumps([], indent=2)
        return "[dim]No results found[/dim]"

    def _format_text(self, data: list[dict[str, Any]]) -> str:
        """Format as simple text output."""
        lines = []
        for i, row in enumerate(data, 1):
            lines.append(f"Row {i}:")
            for key, value in row.items():
                lines.append(f"  {key}: {value}")
            lines.append("")
        return "\n".join(lines)

    def format_query_info(
        self, query_name: str, description: str, parameters: list[str] | None = None
    ) -> str:
        """Format query information display.

        Args:
            query_name: Name of the query
            description: Query description
            parameters: List of query parameters

        Returns:
            Formatted string
        """
        lines = [
            f"[bold cyan]{query_name}[/bold cyan]",
            f"[dim]{description}[/dim]",
        ]

        if parameters:
            lines.append("\n[yellow]Parameters:[/yellow]")
            for param in parameters:
                lines.append(f"  • {param}")

        return "\n".join(lines)

    def format_execution_stats(
        self, row_count: int, execution_time: float | None = None
    ) -> str:
        """Format query execution statistics.

        Args:
            row_count: Number of rows returned
            execution_time: Query execution time in seconds

        Returns:
            Formatted string
        """
        stats = f"[dim]Returned {row_count} row{'s' if row_count != 1 else ''}"
        if execution_time is not None:
            stats += f" in {execution_time:.3f}s"
        stats += "[/dim]"
        return stats
