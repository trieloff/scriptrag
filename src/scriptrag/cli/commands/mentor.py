"""Screenplay analysis mentors and automated feedback commands for ScriptRAG CLI."""

import asyncio
import json
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table as RichTable

from scriptrag.config import get_settings
from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.operations import GraphOperations
from scriptrag.mentors import MentorDatabaseOperations, get_mentor_registry
from scriptrag.mentors.base import MentorAnalysis, MentorResult

console = Console()
mentor_app = typer.Typer(
    name="mentor",
    help="Screenplay analysis mentors and automated feedback",
    rich_markup_mode="rich",
)


def get_latest_script_id(connection: DatabaseConnection) -> tuple[str, str] | None:
    """Get the latest script ID and title from the database."""
    result = connection.fetch_one(
        """
        SELECT id, title FROM scripts
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    return (result["id"], result["title"]) if result else None


@mentor_app.command("list")
def mentor_list() -> None:
    """List all available mentors."""
    try:
        registry = get_mentor_registry()
        mentors = registry.list_mentors()

        if not mentors:
            console.print("[yellow]No mentors available.[/yellow]")
            return

        table = RichTable(show_header=True, header_style="bold blue")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Version", style="yellow")
        table.add_column("Description", style="white")

        for mentor in mentors:
            table.add_row(
                str(mentor["name"]),
                str(mentor["type"]),
                str(mentor["version"]),
                (
                    str(mentor["description"])[:60]
                    + ("..." if len(str(mentor["description"])) > 60 else "")
                ),
            )

        console.print(table)
        console.print(f"\n[dim]Total mentors: {len(mentors)}[/dim]")

    except Exception as e:
        console.print(f"[red]Error listing mentors: {e}[/red]")
        raise typer.Exit(1) from e


@mentor_app.command("analyze")
def mentor_analyze(
    mentor_name: Annotated[
        str, typer.Argument(help="Name of the mentor to use for analysis")
    ],
    script_id: Annotated[
        str | None,
        typer.Option(
            "--script-id",
            "-s",
            help="Script ID to analyze (uses latest if not specified)",
        ),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config", "-c", help="Path to mentor configuration file (JSON/YAML)"
        ),
    ] = None,
    save_results: Annotated[
        bool,
        typer.Option("--save", help="Save analysis results to database"),
    ] = True,
) -> None:
    """Run mentor analysis on a screenplay."""
    try:
        settings = get_settings()
        db_path = Path(settings.database.path)

        if not db_path.exists():
            console.print(
                "[red]No database found. Use 'scriptrag script parse' first.[/red]"
            )
            raise typer.Exit(1)

        # Get mentor
        registry = get_mentor_registry()
        if not registry.is_registered(mentor_name):
            mentor_list = registry.list_mentors()
            available = ", ".join([str(m["name"]) for m in mentor_list])
            console.print(f"[red]Mentor '{mentor_name}' not found.[/red]")
            console.print(f"Available mentors: {available}")
            raise typer.Exit(1)

        # Load configuration if provided
        config = {}
        if config_file:
            if config_file.suffix.lower() == ".json":
                config = json.loads(config_file.read_text())
            else:
                # Assume YAML
                import yaml

                config = yaml.safe_load(config_file.read_text())

        mentor = registry.get_mentor(mentor_name, config)

        # Get script ID
        connection = DatabaseConnection(str(db_path))
        if not script_id:
            result = get_latest_script_id(connection)
            if not result:
                console.print("[red]No scripts found in database.[/red]")
                raise typer.Exit(1)
            script_id, script_title = result
            console.print(f"[blue]Analyzing script:[/blue] {script_title}")
        else:
            console.print(f"[blue]Analyzing script ID:[/blue] {script_id}")

        # Run analysis
        console.print(f"[blue]Running {mentor_name} analysis...[/blue]")

        async def run_analysis() -> MentorResult:
            graph_ops = GraphOperations(connection)

            def progress_callback(pct: float, msg: str) -> None:
                # Simple progress display
                progress_bar = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
                console.print(f"\r[{progress_bar}] {msg}", end="")

            try:
                result = await mentor.analyze_script(
                    script_id=UUID(script_id),
                    db_operations=graph_ops,
                    progress_callback=progress_callback,
                )

                console.print("\n")  # New line after progress
                return result

            except Exception as e:
                console.print(f"\n[red]Analysis failed: {e}[/red]")
                raise

        analysis_result = asyncio.run(run_analysis())

        # Display results
        console.print("\n[bold green]Analysis Complete![/bold green]")
        console.print(
            f"[bold]Mentor:[/bold] {analysis_result.mentor_name} "
            f"v{analysis_result.mentor_version}"
        )
        if analysis_result.score is not None:
            console.print(f"[bold]Score:[/bold] {analysis_result.score:.1f}/100")
        console.print(
            f"[bold]Execution Time:[/bold] {analysis_result.execution_time_ms}ms"
        )
        console.print(f"\n[bold]Summary:[/bold]\n{analysis_result.summary}")

        # Show analysis breakdown
        if analysis_result.analyses:
            console.print(
                f"\n[bold blue]Detailed Analysis "
                f"({len(analysis_result.analyses)} findings):[/bold blue]"
            )

            # Group by severity
            by_severity: dict[str, list[MentorAnalysis]] = {}
            for analysis in analysis_result.analyses:
                severity = analysis.severity.value
                if severity not in by_severity:
                    by_severity[severity] = []
                by_severity[severity].append(analysis)

            severity_styles = {
                "error": "red",
                "warning": "yellow",
                "suggestion": "blue",
                "info": "green",
            }

            for severity, analyses in by_severity.items():
                style = severity_styles.get(severity, "white")
                console.print(
                    f"\n[bold {style}]{severity.upper()} "
                    f"({len(analyses)}):[/bold {style}]"
                )

                for analysis in analyses[:3]:  # Show first 3 of each type
                    console.print(f"  • [bold]{analysis.title}[/bold]")
                    console.print(f"    {analysis.description}")

                if len(analyses) > 3:
                    console.print(f"    [dim]... and {len(analyses) - 3} more[/dim]")

        # Save results if requested
        if save_results:
            mentor_db = MentorDatabaseOperations(connection)
            saved = mentor_db.store_mentor_result(analysis_result)
            if saved:
                console.print("\n[green]✓[/green] Results saved to database")
            else:
                console.print("\n[yellow]⚠[/yellow] Failed to save results to database")

    except Exception as e:
        console.print(f"[red]Error running analysis: {e}[/red]")
        raise typer.Exit(1) from e


@mentor_app.command("search")
def mentor_search(
    query: Annotated[str, typer.Argument(help="Search query for analysis findings")],
    mentor_name: Annotated[
        str | None,
        typer.Option("--mentor", "-m", help="Filter by mentor name"),
    ] = None,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filter by analysis category"),
    ] = None,
    severity: Annotated[
        str | None,
        typer.Option(
            "--severity",
            "-v",
            help="Filter by severity (error, warning, suggestion, info)",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Limit number of results"),
    ] = 20,
) -> None:
    """Search mentor analysis findings."""
    try:
        if limit < 1:
            console.print("[red]Error: Limit must be a positive number[/red]")
            raise typer.Exit(1)

        from scriptrag.mentors import AnalysisSeverity

        settings = get_settings()
        db_path = Path(settings.database.path)

        if not db_path.exists():
            console.print(
                "[red]No database found. Use 'scriptrag script parse' first.[/red]"
            )
            raise typer.Exit(1)

        connection = DatabaseConnection(str(db_path))
        mentor_db = MentorDatabaseOperations(connection)

        # Parse severity
        severity_enum = None
        if severity:
            try:
                severity_enum = AnalysisSeverity(severity.lower())
            except ValueError as err:
                console.print(f"[red]Invalid severity: {severity}[/red]")
                console.print("Valid severities: error, warning, suggestion, info")
                raise typer.Exit(1) from err

        # Search analyses
        console.print(f"[blue]Searching for:[/blue] {query}")

        results = mentor_db.search_analyses(
            query=query,
            mentor_name=mentor_name,
            category=category,
            severity=severity_enum,
            limit=limit,
        )

        if not results:
            console.print("[yellow]No matching analysis findings found.[/yellow]")
            return

        # Display results
        console.print(f"\n[bold]Found {len(results)} analysis findings:[/bold]")

        for i, analysis in enumerate(results, 1):
            severity_style = {
                "error": "red",
                "warning": "yellow",
                "suggestion": "blue",
                "info": "green",
            }.get(analysis.severity.value, "white")

            console.print(
                f"\n[bold cyan]{i}.[/bold cyan] [bold]{analysis.title}[/bold]"
            )
            console.print(f"   [bold]Mentor:[/bold] {analysis.mentor_name}")
            console.print(f"   [bold]Category:[/bold] {analysis.category}")
            console.print(
                f"   [bold]Severity:[/bold] [{severity_style}]"
                f"{analysis.severity.value}[/{severity_style}]"
            )
            console.print(f"   [bold]Description:[/bold] {analysis.description}")

            if analysis.recommendations:
                console.print(
                    f"   [bold]Recommendation:[/bold] {analysis.recommendations[0]}"
                )

    except Exception as e:
        console.print(f"[red]Error searching analyses: {e}[/red]")
        raise typer.Exit(1) from e
