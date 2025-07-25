"""Command-line interface for ScriptRAG.

This module provides a comprehensive CLI for ScriptRAG operations including
script parsing, searching, configuration management, and development utilities.
"""

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from . import ScriptRAG
from .config import (
    create_default_config,
    get_settings,
    load_settings,
    setup_logging_for_environment,
)

# Create main Typer app
app = typer.Typer(
    name="scriptrag",
    help="ScriptRAG: A Graph-Based Screenwriting Assistant",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Create console for rich output
console = Console()


# Global options
@app.callback()
def main(
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress output except errors",
    ),
    environment: str = typer.Option(
        "development",
        "--env",
        "-e",
        help="Environment (development, testing, production)",
    ),
):
    """ScriptRAG: A Graph-Based Screenwriting Assistant.

    [bold green]Features:[/bold green]
    • Parse screenplays in Fountain format
    • Build and query graph databases
    • Semantic search with local LLMs
    • Scene management and timeline analysis
    • MCP server for AI assistant integration
    """
    # Set up logging level based on options
    if quiet:
        log_level = "ERROR"
    elif verbose:
        log_level = "DEBUG"
    else:
        log_level = "INFO"

    # Load configuration
    if config_file:
        settings = load_settings(config_file)
    else:
        settings = get_settings()

    # Override environment if specified
    settings.environment = environment
    settings.logging.level = log_level

    # Set up logging
    setup_logging_for_environment(
        environment=settings.environment,
        log_file=settings.get_log_file_path(),
    )


# Configuration commands
config_app = typer.Typer(
    name="config",
    help="Configuration management commands",
    rich_markup_mode="rich",
)
app.add_typer(config_app)


@config_app.command("init")
def config_init(
    output: Path = typer.Option(
        Path("config.yaml"),
        "--output",
        "-o",
        help="Output path for configuration file",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing configuration file",
    ),
):
    """Initialize a new configuration file with default settings."""
    if output.exists() and not force:
        print(f"Configuration file already exists: {output}", file=sys.stderr)
        print("Use --force to overwrite", file=sys.stderr)
        raise typer.Exit(1)

    try:
        create_default_config(output)
        console.print(f"[green]✓[/green] Created configuration file: {output}")
        console.print("[dim]Edit the file to customize your settings[/dim]")
    except Exception as e:
        print(f"Error creating configuration: {e}", file=sys.stderr)
        raise typer.Exit(1)


@config_app.command("show")
def config_show(
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    section: str | None = typer.Option(
        None,
        "--section",
        "-s",
        help="Show only specific section (database, llm, logging, etc.)",
    ),
):
    """Display current configuration settings."""
    try:
        if config_file:
            settings = load_settings(config_file)
        else:
            settings = get_settings()

        if section:
            # Show specific section
            section_data = getattr(settings, section, None)
            if section_data is None:
                print(f"Unknown section: {section}", file=sys.stderr)
                raise typer.Exit(1)

            table = Table(title=f"Configuration: {section}")
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="green")

            for key, value in section_data.dict().items():
                table.add_row(key, str(value))

            console.print(table)
        else:
            # Show all settings
            config_dict = settings.dict()
            console.print(
                Panel(
                    Syntax(
                        str(config_dict),
                        "python",
                        theme="monokai",
                        line_numbers=True,
                    ),
                    title="ScriptRAG Configuration",
                    border_style="blue",
                )
            )

    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        raise typer.Exit(1)


@config_app.command("validate")
def config_validate(
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file to validate",
    ),
):
    """Validate configuration file."""
    try:
        if config_file:
            settings = load_settings(config_file)
            console.print(
                f"[green]✓[/green] Configuration file is valid: {config_file}"
            )
        else:
            settings = get_settings()
            console.print("[green]✓[/green] Current configuration is valid")

        # Show summary
        table = Table(title="Configuration Summary")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")

        table.add_row("Environment", settings.environment)
        table.add_row("Database Path", str(settings.get_database_path()))
        table.add_row("LLM Endpoint", settings.llm.endpoint)
        table.add_row("Log Level", settings.logging.level)

        console.print(table)

    except Exception as e:
        print(f"✗ Configuration validation failed: {e}", file=sys.stderr)
        raise typer.Exit(1)


# Script management commands
script_app = typer.Typer(
    name="script",
    help="Screenplay parsing and management commands",
    rich_markup_mode="rich",
)
app.add_typer(script_app)


@script_app.command("parse")
def script_parse(
    script_path: Path = typer.Argument(
        ...,
        help="Path to Fountain screenplay file",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    output_db: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output database path (default: from config)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing database",
    ),
):
    """Parse a Fountain screenplay into the graph database."""
    try:
        settings = get_settings()
        if output_db:
            settings.database.path = output_db

        # Initialize ScriptRAG
        scriptrag = ScriptRAG(config=settings)

        console.print(f"[blue]Parsing screenplay:[/blue] {script_path}")
        console.print(f"[blue]Database:[/blue] {settings.get_database_path()}")

        # TODO: Implement actual parsing when parser is ready
        scriptrag.parse_fountain(str(script_path))

        console.print("[green]✓[/green] Screenplay parsed successfully")

    except NotImplementedError:
        console.print("[yellow]⚠[/yellow] Parser not yet implemented")
        console.print("This command will be available in Phase 2 of development")
    except Exception as e:
        print(f"Error parsing screenplay: {e}", file=sys.stderr)
        raise typer.Exit(1)


@script_app.command("info")
def script_info(
    script_path: Path | None = typer.Argument(
        None,
        help="Path to Fountain screenplay file",
    ),
):
    """Display information about a screenplay or database."""
    if script_path:
        # Show info about a specific script file
        if not script_path.exists():
            print(f"Script file not found: {script_path}", file=sys.stderr)
            raise typer.Exit(1)

        # Basic file info for now
        stat = script_path.stat()
        console.print(
            Panel(
                f"[bold]File:[/bold] {script_path}\n"
                f"[bold]Size:[/bold] {stat.st_size:,} bytes\n"
                f"[bold]Modified:[/bold] {stat.st_mtime}",
                title="Screenplay Information",
                border_style="blue",
            )
        )
    else:
        # Show database info
        settings = get_settings()
        db_path = settings.get_database_path()

        if db_path.exists():
            stat = db_path.stat()
            console.print(
                Panel(
                    f"[bold]Database:[/bold] {db_path}\n"
                    f"[bold]Size:[/bold] {stat.st_size:,} bytes\n"
                    f"[bold]Modified:[/bold] {stat.st_mtime}",
                    title="Database Information",
                    border_style="green",
                )
            )
        else:
            console.print(
                "[yellow]No database found. Use 'scriptrag script parse' to create one.[/yellow]"
            )


# Search commands
search_app = typer.Typer(
    name="search",
    help="Search and query commands",
    rich_markup_mode="rich",
)
app.add_typer(search_app)


@search_app.command("scenes")
def search_scenes(
    query: str = typer.Argument(..., help="Search query"),
    character: str | None = typer.Option(
        None, "--character", "-c", help="Filter by character"
    ),
    location: str | None = typer.Option(
        None, "--location", "-l", help="Filter by location"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results to return"),
):
    """Search for scenes matching criteria."""
    try:
        settings = get_settings()
        scriptrag = ScriptRAG(config=settings)

        console.print(f"[blue]Searching scenes:[/blue] {query}")
        if character:
            console.print(f"[blue]Character filter:[/blue] {character}")
        if location:
            console.print(f"[blue]Location filter:[/blue] {location}")

        # TODO: Implement actual search when ready
        results = scriptrag.search_scenes(
            query=query,
            character=character,
            location=location,
            limit=limit,
        )

        # For now, handle the None return
        results = results or []
        console.print(f"[green]Found {len(results)} scenes[/green]")

    except NotImplementedError:
        console.print("[yellow]⚠[/yellow] Search not yet implemented")
        console.print("This command will be available in Phase 4 of development")
    except Exception as e:
        print(f"Error searching scenes: {e}", file=sys.stderr)
        raise typer.Exit(1)


# Development commands
dev_app = typer.Typer(
    name="dev",
    help="Development and debugging commands",
    rich_markup_mode="rich",
)
app.add_typer(dev_app)


@dev_app.command("init")
def dev_init(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing files",
    ),
):
    """Initialize development environment."""
    console.print("[blue]Initializing ScriptRAG development environment...[/blue]")

    # Create directories
    dirs_to_create = [
        Path("data"),
        Path("cache"),
        Path("logs"),
        Path("temp"),
        Path("scripts"),
        Path("exports"),
    ]

    for dir_path in dirs_to_create:
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]✓[/green] Created directory: {dir_path}")
        else:
            console.print(f"[dim]Directory exists: {dir_path}[/dim]")

    # Create default config if it doesn't exist
    config_path = Path("config.yaml")
    if not config_path.exists() or force:
        create_default_config(config_path)
        console.print(f"[green]✓[/green] Created configuration: {config_path}")
    else:
        console.print(f"[dim]Configuration exists: {config_path}[/dim]")

    # Create .env file if it doesn't exist
    env_path = Path(".env")
    env_example = Path(".env.example")
    if not env_path.exists() and env_example.exists():
        env_path.write_text(env_example.read_text())
        console.print(f"[green]✓[/green] Created environment file: {env_path}")

    console.print("\n[bold green]Development environment ready![/bold green]")
    console.print("[dim]Next steps:[/dim]")
    console.print("1. Edit [cyan]config.yaml[/cyan] to customize settings")
    console.print("2. Edit [cyan].env[/cyan] for environment-specific values")
    console.print("3. Start LMStudio at http://localhost:1234")
    console.print(
        "4. Parse a screenplay: [cyan]scriptrag script parse screenplay.fountain[/cyan]"
    )


@dev_app.command("status")
def dev_status() -> None:
    """Show development environment status."""
    settings = get_settings()

    # Check configuration
    table = Table(title="ScriptRAG Development Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Details", style="dim")

    # Configuration
    config_path = Path("config.yaml")
    config_status = "✓ Found" if config_path.exists() else "✗ Missing"
    table.add_row("Configuration", config_status, str(config_path))

    # Database
    db_path = settings.get_database_path()
    db_status = "✓ Found" if db_path.exists() else "✗ Missing"
    table.add_row("Database", db_status, str(db_path))

    # Directories
    for dir_name, dir_path in [
        ("Data", settings.paths.data_dir),
        ("Cache", settings.paths.cache_dir),
        ("Logs", settings.paths.logs_dir),
        ("Scripts", settings.paths.scripts_dir),
    ]:
        dir_status = "✓ Found" if dir_path.exists() else "✗ Missing"
        table.add_row(dir_name, dir_status, str(dir_path))

    # LLM endpoint (basic check)
    import httpx

    try:
        response = httpx.get(f"{settings.llm.endpoint}/models", timeout=5.0)
        llm_status = "✓ Connected" if response.status_code == 200 else "⚠ Error"
    except Exception:
        llm_status = "✗ Unreachable"

    table.add_row("LLM Endpoint", llm_status, settings.llm.endpoint)

    console.print(table)


@dev_app.command("test-llm")
def dev_test_llm() -> None:
    """Test LLM connection and functionality."""
    settings = get_settings()

    console.print(f"[blue]Testing LLM connection:[/blue] {settings.llm.endpoint}")

    import httpx

    try:
        # Test models endpoint
        with console.status("Checking models endpoint..."):
            response = httpx.get(f"{settings.llm.endpoint}/models", timeout=10.0)

        if response.status_code == 200:
            console.print("[green]✓[/green] Models endpoint accessible")
            models = response.json().get("data", [])
            console.print(f"[dim]Available models: {len(models)}[/dim]")
        else:
            console.print(f"[red]✗[/red] Models endpoint error: {response.status_code}")

        # Test simple completion
        with console.status("Testing completion..."):
            completion_response = httpx.post(
                f"{settings.llm.endpoint}/chat/completions",
                json={
                    "model": settings.llm.default_model,
                    "messages": [{"role": "user", "content": "Hello, test message."}],
                    "max_tokens": 10,
                },
                timeout=30.0,
            )

        if completion_response.status_code == 200:
            console.print("[green]✓[/green] Completion endpoint working")
            result = completion_response.json()
            message = (
                result.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            console.print(f"[dim]Response: {message.strip()}[/dim]")
        else:
            console.print(
                f"[red]✗[/red] Completion endpoint error: {completion_response.status_code}"
            )

    except Exception as e:
        console.print(f"[red]✗ Connection failed: {e}[/red]")
        console.print(
            "[dim]Make sure LMStudio is running at the configured endpoint[/dim]"
        )


# Server commands
server_app = typer.Typer(
    name="server",
    help="MCP server management commands",
    rich_markup_mode="rich",
)
app.add_typer(server_app)


@server_app.command("start")
def server_start(
    host: str | None = typer.Option(None, "--host", "-h", help="Server host"),
    port: int | None = typer.Option(None, "--port", "-p", help="Server port"),
    config_file: Path | None = typer.Option(
        None, "--config", "-c", help="Configuration file"
    ),
):
    """Start the MCP server."""
    console.print("[blue]Starting ScriptRAG MCP server...[/blue]")

    # TODO: Implement actual MCP server startup
    console.print("[yellow]⚠[/yellow] MCP server not yet implemented")
    console.print("This command will be available in Phase 7 of development")


if __name__ == "__main__":
    app()
