"""Table output formatter for CLI."""

import csv
import io
from typing import Any

from rich.table import Table

from scriptrag.cli.formatters.base import OutputFormat, OutputFormatter


class TableFormatter(OutputFormatter[list[dict[str, Any]]]):
    """Formatter for tabular data output."""

    def format(
        self, data: list[dict[str, Any]], format_type: OutputFormat = OutputFormat.TABLE
    ) -> str:
        """Format tabular data.

        Args:
            data: List of dictionaries to format as table
            format_type: Output format type

        Returns:
            Formatted string
        """
        if not data:
            return "No data to display"

        if format_type == OutputFormat.CSV:
            return self._format_csv(data)
        if format_type == OutputFormat.MARKDOWN:
            return self._format_markdown(data)
        return self._format_table(data)

    def _format_table(self, data: list[dict[str, Any]]) -> str:
        """Format as Rich table."""
        if not data:
            return ""

        # Get columns from first row
        columns = list(data[0].keys())

        # Create table
        table = Table(show_header=True, header_style="bold magenta")

        # Add columns
        for col in columns:
            table.add_column(col.replace("_", " ").title())

        # Add rows
        for row in data:
            table.add_row(*[str(row.get(col, "")) for col in columns])

        # Convert to string
        string_io = io.StringIO()
        from rich.console import Console

        temp_console = Console(file=string_io, force_terminal=True)
        temp_console.print(table)
        return string_io.getvalue()

    def _format_csv(self, data: list[dict[str, Any]]) -> str:
        """Format as CSV."""
        if not data:
            return ""

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()

    def _format_markdown(self, data: list[dict[str, Any]]) -> str:
        """Format as Markdown table."""
        if not data:
            return ""

        columns = list(data[0].keys())
        lines = []

        # Header
        header = "| " + " | ".join(columns) + " |"
        separator = "| " + " | ".join(["---"] * len(columns)) + " |"
        lines.append(header)
        lines.append(separator)

        # Rows
        for row in data:
            row_str = "| " + " | ".join(str(row.get(col, "")) for col in columns) + " |"
            lines.append(row_str)

        return "\n".join(lines)

    def create_summary_table(
        self,
        title: str,
        data: dict[str, Any],
        format_type: OutputFormat = OutputFormat.TABLE,
    ) -> str:
        """Create a summary table from key-value pairs.

        Args:
            title: Table title
            data: Dictionary of key-value pairs
            format_type: Output format type

        Returns:
            Formatted string
        """
        if format_type == OutputFormat.TABLE:
            table = Table(title=title, show_header=False)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")

            for key, value in data.items():
                table.add_row(key.replace("_", " ").title(), str(value))

            # Convert to string
            string_io = io.StringIO()
            from rich.console import Console

            temp_console = Console(file=string_io, force_terminal=True)
            temp_console.print(table)
            return string_io.getvalue()
        # Simple text format
        lines = [f"{title}:", ""]
        for key, value in data.items():
            lines.append(f"  {key.replace('_', ' ').title()}: {value}")
        return "\n".join(lines)
