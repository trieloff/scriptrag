"""Result formatter for search functionality."""

from rich.console import Console
from rich.panel import Panel

from scriptrag.search.models import SearchResponse, SearchResult


class ResultFormatter:
    """Format search results for display."""

    def __init__(self, console: Console | None = None):
        """Initialize formatter.

        Args:
            console: Rich console for output
        """
        self.console = console or Console()

    def format_results(self, response: SearchResponse, verbose: bool = False) -> None:
        """Format and display search results.

        Args:
            response: Search response with results
            verbose: Show detailed information
        """
        if not response.results:
            self.console.print(
                "[yellow]No results found for your search.[/yellow]",
                style="bold",
            )
            return

        # Display search info
        self._display_search_info(response)

        # Display each result
        for i, result in enumerate(response.results, 1):
            self._display_result(result, i, verbose)

        # Display pagination info
        self._display_pagination_info(response)

    def _display_search_info(self, response: SearchResponse) -> None:
        """Display search query information.

        Args:
            response: Search response
        """
        query_parts = []

        if response.query.project:
            query_parts.append(f"Project: [cyan]{response.query.project}[/cyan]")

        if response.query.characters:
            chars = ", ".join(response.query.characters)
            query_parts.append(f"Character(s): [green]{chars}[/green]")

        if response.query.dialogue:
            query_parts.append(
                f'Dialogue: [yellow]"{response.query.dialogue}"[/yellow]'
            )

        if response.query.parenthetical:
            query_parts.append(
                f"Parenthetical: [dim]({response.query.parenthetical})[/dim]"
            )

        if response.query.text_query:
            query_parts.append(f"Text: [white]{response.query.text_query}[/white]")

        if response.query.season_start is not None:
            if response.query.season_end != response.query.season_start:
                range_str = (
                    f"S{response.query.season_start}E{response.query.episode_start}-"
                    f"S{response.query.season_end}E{response.query.episode_end}"
                )
            else:
                range_str = (
                    f"S{response.query.season_start}E{response.query.episode_start}"
                )
            query_parts.append(f"Range: [magenta]{range_str}[/magenta]")

        if query_parts:
            self.console.print(f"[bold]Search:[/bold] {' | '.join(query_parts)}")

        # Display execution info
        info_parts = [f"Found {response.total_count} results"]
        if response.execution_time_ms:
            info_parts.append(f"in {response.execution_time_ms:.2f}ms")
        if response.search_methods:
            methods = ", ".join(response.search_methods)
            info_parts.append(f"using {methods}")

        self.console.print(f"[dim]{' '.join(info_parts)}[/dim]\n")

    def _display_result(self, result: SearchResult, index: int, verbose: bool) -> None:
        """Display a single search result.

        Args:
            result: Search result to display
            index: Result index (1-based)
            verbose: Show detailed information
        """
        # Build title with metadata
        title_parts = [f"[bold]{index}.[/bold]"]
        title_parts.append(f"[cyan]{result.script_title}[/cyan]")

        if result.season is not None and result.episode is not None:
            title_parts.append(f"[magenta]S{result.season}E{result.episode}[/magenta]")

        title_parts.append(f"[yellow]Scene {result.scene_number}[/yellow]")

        if result.script_author:
            title_parts.append(f"[dim]by {result.script_author}[/dim]")

        title = " - ".join(title_parts)

        # Build content
        content_lines = []

        # Scene heading
        content_lines.append(f"[bold]{result.scene_heading}[/bold]")

        if result.scene_location:
            content_lines.append(f"[dim]Location: {result.scene_location}[/dim]")

        if result.scene_time:
            content_lines.append(f"[dim]Time: {result.scene_time}[/dim]")

        content_lines.append("")  # Empty line

        # Scene content (truncated if not verbose)
        if verbose:
            content_lines.append(result.scene_content)
        else:
            # Show first few lines
            lines = result.scene_content.split("\n")
            preview_lines = lines[:5]
            if len(lines) > 5:
                preview_lines.append("[dim]...[/dim]")
            content_lines.extend(preview_lines)

        # Create panel for result
        panel = Panel(
            "\n".join(content_lines),
            title=title,
            title_align="left",
            border_style="blue" if index == 1 else "dim",
            padding=(1, 2),
        )

        self.console.print(panel)

    def _display_pagination_info(self, response: SearchResponse) -> None:
        """Display pagination information.

        Args:
            response: Search response
        """
        if response.has_more:
            shown = len(response.results)
            total = response.total_count
            next_offset = response.query.offset + response.query.limit

            self.console.print(
                f"\n[yellow]Showing {shown} of {total} results. "
                f"Use --offset {next_offset} to see more.[/yellow]"
            )

    def format_brief(self, response: SearchResponse) -> str:
        """Format results as brief text summary.

        Args:
            response: Search response

        Returns:
            Brief text summary
        """
        if not response.results:
            return "No results found."

        lines = []
        for i, result in enumerate(response.results, 1):
            project_info = f"{result.script_title}"
            if result.season is not None:
                project_info += f" S{result.season}E{result.episode}"

            lines.append(
                f"{i}. {project_info} - Scene {result.scene_number}: "
                f"{result.scene_heading}"
            )

        if response.has_more:
            lines.append(
                f"... and {response.total_count - len(response.results)} more results"
            )

        return "\n".join(lines)
