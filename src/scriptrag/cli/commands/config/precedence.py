"""Configuration precedence explanation command."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def config_precedence() -> None:
    """Explain configuration precedence and override rules.

    Shows how settings are resolved from multiple sources
    and provides examples of each override level.
    """
    panel = Panel.fit(
        """[bold cyan]Configuration Precedence (highest to lowest):[/bold cyan]

1. [bold]CLI Arguments[/bold] - Command-line flags
   Example: scriptrag index --db-path /custom/path.db

2. [bold]Config Files[/bold] - YAML, TOML, or JSON files
   Example: scriptrag --config myconfig.yaml
   Multiple files: Later files override earlier ones

3. [bold]Environment Variables[/bold] - SCRIPTRAG_* prefixed
   Example: export SCRIPTRAG_DATABASE_PATH=/data/scripts.db

4. [bold].env File[/bold] - Environment file in current directory
   Example: SCRIPTRAG_LOG_LEVEL=DEBUG in .env file

5. [bold]Default Values[/bold] - Built-in defaults
   Defined in ScriptRAGSettings class

[dim]Use 'scriptrag config validate' to see the effective configuration[/dim]""",
        title="Configuration Precedence",
        border_style="cyan",
    )
    console.print(panel)

    # Show examples
    console.print("\n[bold]Examples:[/bold]\n")

    examples = Table(show_header=True, header_style="bold cyan")
    examples.add_column("Source", style="cyan")
    examples.add_column("Setting Method")
    examples.add_column("Example")

    examples.add_row(
        "CLI",
        "Command flag",
        "scriptrag init --db-path /custom/db.sqlite",
    )
    examples.add_row(
        "Config File",
        "YAML file",
        "database_path: /data/scriptrag.db",
    )
    examples.add_row(
        "Environment",
        "Export variable",
        "export SCRIPTRAG_DATABASE_PATH=/var/db.sqlite",
    )
    examples.add_row(
        ".env File",
        "File in directory",
        "SCRIPTRAG_LOG_LEVEL=DEBUG",
    )

    console.print(examples)
