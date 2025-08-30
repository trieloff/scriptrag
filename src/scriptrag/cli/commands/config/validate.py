"""Configuration validation command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from scriptrag.config import ScriptRAGSettings, get_settings

console = Console()


def config_validate(
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file to validate",
        ),
    ] = None,
    show_defaults: Annotated[
        bool,
        typer.Option(
            "--show-defaults",
            "-d",
            help="Show default values for unset options",
        ),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: table, json, or yaml",
        ),
    ] = "table",
) -> None:
    """Validate configuration and show effective settings.

    Shows the final configuration after merging all sources:
    1. CLI arguments
    2. Config files
    3. Environment variables
    4. Default values

    Examples:
        scriptrag config validate                   # Show current config
        scriptrag config validate -c myconfig.yaml  # Validate specific file
        scriptrag config validate --format json     # Output as JSON
        scriptrag config validate --show-defaults   # Include all defaults
    """
    try:
        # Load configuration
        if config:
            if not config.exists():
                console.print(f"[red]Error: Config file not found: {config}[/red]")
                raise typer.Exit(1)

            console.print(f"[cyan]Validating config file: {config}[/cyan]")
            settings = ScriptRAGSettings.from_file(config)
        else:
            console.print("[cyan]Loading effective configuration...[/cyan]")
            settings = get_settings()

        # Validate the configuration (Pydantic already does this)
        console.print("[green]✓[/green] Configuration is valid")

        # Show effective configuration
        if output_format == "json":
            config_dict = settings.model_dump()
            if not show_defaults:
                # Filter out defaults
                config_dict = _filter_non_defaults(config_dict, settings)
            console.print_json(data=config_dict)

        elif output_format == "yaml":
            config_dict = settings.model_dump()
            if not show_defaults:
                config_dict = _filter_non_defaults(config_dict, settings)
            yaml_str = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
            syntax = Syntax(yaml_str, "yaml", theme="monokai")
            console.print(syntax)

        else:  # table format
            _show_config_table(settings, show_defaults)

    except Exception as e:
        console.print(
            f"[red]Error:[/red] Configuration validation failed: {e}",
            style="bold",
        )
        raise typer.Exit(1) from e


def _show_config_table(settings: ScriptRAGSettings, show_defaults: bool) -> None:
    """Display configuration as a formatted table."""
    table = Table(title="Effective Configuration", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Type", style="yellow")

    # Get all fields
    for field_name, field_info in settings.model_fields.items():
        value = getattr(settings, field_name)

        # Skip None values unless showing defaults
        if value is None and not show_defaults:
            continue

        # Format value for display
        if isinstance(value, Path):
            value_str = str(value)
        elif value is None:
            value_str = "[dim]<not set>[/dim]"
        else:
            value_str = str(value)

        # Get field type
        field_type = (
            getattr(field_info.annotation, "__name__", str(field_info.annotation))
            if field_info.annotation
            else "Any"
        )

        table.add_row(field_name, value_str, field_type)

    console.print(table)


def _filter_non_defaults(config_dict: dict, settings: ScriptRAGSettings) -> dict:
    """Filter out settings that are at their default values."""
    # Create a default instance
    _ = settings  # Mark as intentionally unused (needed for interface consistency)
    defaults = ScriptRAGSettings()
    filtered = {}

    for key, value in config_dict.items():
        default_value = getattr(defaults, key, None)
        if value != default_value:
            filtered[key] = value

    return filtered
