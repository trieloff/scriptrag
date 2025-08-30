"""Configuration display commands."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from scriptrag.config import ScriptRAGSettings, get_settings

console = Console()


def config_show(
    section: Annotated[
        str | None,
        typer.Argument(
            help="Configuration section to show (database, llm, search, log, etc.)",
        ),
    ] = None,
    sources: Annotated[
        bool,
        typer.Option(
            "--sources",
            "-s",
            help="Show configuration sources and precedence",
        ),
    ] = False,
) -> None:
    """Display current configuration settings.

    Shows the effective configuration after merging all sources.
    Optionally filter by section or show configuration sources.

    Examples:
        scriptrag config show                # Show all settings
        scriptrag config show database       # Show database settings
        scriptrag config show llm           # Show LLM settings
        scriptrag config show --sources     # Show config precedence
    """
    try:
        settings = get_settings()

        if sources:
            _show_config_sources()
            return

        if section:
            _show_config_section(settings, section)
        else:
            _show_config_tree(settings)

    except Exception as e:
        console.print(
            f"[red]Error:[/red] Failed to show configuration: {e}",
            style="bold",
        )
        raise typer.Exit(1) from e


def _show_config_tree(settings: ScriptRAGSettings) -> None:
    """Display configuration as a tree structure."""
    tree = Tree("[bold cyan]ScriptRAG Configuration[/bold cyan]")

    # Group settings by prefix
    groups: dict[str, list[tuple[str, Any]]] = {}
    for field_name in settings.model_fields:
        value = getattr(settings, field_name)
        if value is None:
            continue

        # Determine group
        if field_name.startswith("database_"):
            group = "database"
        elif field_name.startswith("llm_"):
            group = "llm"
        elif field_name.startswith("search_"):
            group = "search"
        elif field_name.startswith("log_"):
            group = "logging"
        elif field_name.startswith("bible_"):
            group = "bible"
        else:
            group = "application"

        if group not in groups:
            groups[group] = []
        groups[group].append((field_name, value))

    # Add groups to tree
    for group_name, items in sorted(groups.items()):
        branch = tree.add(f"[bold]{group_name}[/bold]")
        for field_name, value in sorted(items):
            # Format value
            value_str = str(value)
            branch.add(f"{field_name}: [green]{value_str}[/green]")

    console.print(tree)


def _show_config_section(settings: ScriptRAGSettings, section: str) -> None:
    """Display a specific configuration section."""
    section_lower = section.lower()

    # Collect fields for the section
    fields = []
    for field_name in settings.model_fields:
        if field_name.startswith(f"{section_lower}_") or (
            section_lower == "application"
            and not any(
                field_name.startswith(prefix)
                for prefix in ["database_", "llm_", "search_", "log_", "bible_"]
            )
        ):
            value = getattr(settings, field_name)
            if value is not None:
                fields.append((field_name, value))

    if not fields:
        console.print(f"[yellow]No settings found for section: {section}[/yellow]")
        return

    # Display as table
    table = Table(title=f"{section.title()} Configuration", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    for field_name, value in sorted(fields):
        value_str = str(value)
        table.add_row(field_name, value_str)

    console.print(table)


def _show_config_sources() -> None:
    """Display configuration sources and files."""
    sources = Tree("[bold cyan]Configuration Sources[/bold cyan]")

    # Check for config files
    config_locations = [
        Path.home() / ".config" / "scriptrag" / "config.yaml",
        Path.home() / ".config" / "scriptrag" / "config.json",
        Path.home() / ".config" / "scriptrag" / "config.toml",
        Path.cwd() / "scriptrag.yaml",
        Path.cwd() / "scriptrag.json",
        Path.cwd() / "scriptrag.toml",
        Path.cwd() / ".env",
    ]

    found_configs = sources.add("[bold]Configuration Files[/bold]")
    for path in config_locations:
        if path.exists():
            found_configs.add(f"[green]✓[/green] {path}")

    # Environment variables
    env_vars = sources.add("[bold]Environment Variables[/bold]")
    for key in sorted(os.environ):
        if key.startswith("SCRIPTRAG_"):
            env_vars.add(f"{key} = {os.environ[key]}")

    console.print(sources)
