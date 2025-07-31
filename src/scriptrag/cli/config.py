"""Configuration management commands for ScriptRAG CLI."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from scriptrag.config import (
    create_default_config,
    get_logger,
    get_settings,
    load_settings,
)

# Create config command group
config_app = typer.Typer(
    name="config",
    help="Configuration management commands",
    rich_markup_mode="rich",
)

console = Console()


@config_app.command("init")
def config_init(
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output path for configuration file",
        ),
    ] = Path("config.yaml"),
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite existing configuration file",
        ),
    ] = False,
) -> None:
    """Initialize a new configuration file with default settings."""
    logger = get_logger(__name__)

    if output.exists() and not force:
        logger.error("Configuration file already exists", path=str(output))
        console.print(f"[red]Configuration file already exists: {output}[/red]")
        console.print("[yellow]Use --force to overwrite[/yellow]")
        raise typer.Exit(1)

    try:
        create_default_config(output)
        logger.info("Configuration file created", path=str(output))
        console.print(f"[green]✓[/green] Configuration created: {output}")
        console.print("[dim]Edit the file to customize your settings[/dim]")
    except Exception as e:
        logger.error("Error creating configuration", error=str(e))
        console.print(f"[red]Error creating configuration: {e}[/red]")
        raise typer.Exit(1) from e


@config_app.command("show")
def config_show(
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file",
        ),
    ] = None,
    section: Annotated[
        str | None,
        typer.Option(
            "--section",
            "-s",
            help="Show only specific section (database, llm, logging, etc.)",
        ),
    ] = None,
) -> None:
    """Display current configuration settings."""
    try:
        settings = load_settings(config_file) if config_file else get_settings()

        if section:
            # Show specific section
            if hasattr(settings, section):
                section_data = getattr(settings, section)
                console.print(f"[bold blue]{section}:[/bold blue]")
                if hasattr(section_data, "model_dump"):
                    # Pydantic model
                    for key, value in section_data.model_dump().items():
                        console.print(f"  {key}: {value}")
                else:
                    # Regular value
                    console.print(f"  {section_data}")
            else:
                available_sections = [
                    attr
                    for attr in dir(settings)
                    if not attr.startswith("_") and attr != "model_dump"
                ]
                console.print(f"[red]Unknown section: {section}[/red]")
                console.print(f"Available sections: {', '.join(available_sections)}")
                raise typer.Exit(1)
        else:
            # Show all configuration
            console.print("[bold blue]Current Configuration:[/bold blue]")
            if hasattr(settings, "model_dump"):
                config_dict = settings.model_dump()
                for section_name, section_data in config_dict.items():
                    console.print(f"\n[bold]{section_name}:[/bold]")
                    if isinstance(section_data, dict):
                        for key, value in section_data.items():
                            console.print(f"  {key}: {value}")
                    else:
                        console.print(f"  {section_data}")

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Error loading configuration", error=str(e))
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1) from e


@config_app.command("validate")
def config_validate(
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file to validate",
        ),
    ] = None,
) -> None:
    """Validate configuration file."""
    try:
        if config_file:
            settings = load_settings(config_file)
            console.print(
                f"[green]✓[/green] Configuration file is valid: {config_file}"
            )
        else:
            settings = get_settings()
            console.print("[green]✓[/green] Default configuration is valid")

        # Additional validation checks
        errors = []

        # Check database path
        if hasattr(settings, "database") and hasattr(settings.database, "path"):
            db_path = Path(settings.database.path)
            if not db_path.parent.exists():
                errors.append(f"Database directory does not exist: {db_path.parent}")

        if errors:
            console.print("[yellow]⚠[/yellow] Configuration warnings:")
            for error in errors:
                console.print(f"  • {error}")
        else:
            console.print("[green]✓[/green] All configuration checks passed")

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Error validating configuration", error=str(e))
        console.print(f"[red]Error validating configuration: {e}[/red]")
        raise typer.Exit(1) from e
