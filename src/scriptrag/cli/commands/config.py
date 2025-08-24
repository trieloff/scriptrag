"""Configuration management commands."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

from scriptrag.config import ScriptRAGSettings, get_settings
from scriptrag.config.template import (
    get_default_config_path,
)

console = Console()

# Create config subapp
config_app = typer.Typer(
    name="config",
    help="Manage ScriptRAG configuration",
    pretty_exceptions_enable=False,
)


@config_app.command(name="init")
def config_init(
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output path for config (default: ~/.config/scriptrag/config.yaml)",
        ),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Config file format",
        ),
    ] = "yaml",
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite existing config file",
        ),
    ] = False,
    env: Annotated[
        str | None,
        typer.Option(
            "--env",
            "-e",
            help="Environment preset: dev, prod, or ci",
        ),
    ] = None,
) -> None:
    """Generate a configuration file template with all available settings.

    Examples:
        scriptrag config init                      # Generate default config
        scriptrag config init --env dev            # Generate development config
        scriptrag config init -o myconfig.yaml     # Specify output path
        scriptrag config init --format json        # Generate JSON format
    """
    try:
        # Determine output path
        if output:
            output_path = output
        else:
            # Use default path with appropriate extension
            base_path = get_default_config_path()
            if output_format == "json":
                output_path = base_path.with_suffix(".json")
            elif output_format == "toml":
                output_path = base_path.with_suffix(".toml")
            else:
                output_path = base_path

        # Check if file exists and confirm overwrite
        if (
            output_path.exists()
            and not force
            and not typer.confirm(
                f"Configuration file already exists at {output_path}. Overwrite?"
            )
        ):
            console.print("[yellow]Config generation cancelled.[/yellow]")
            raise typer.Exit(0)

        # Generate config based on environment preset
        console.print(f"[green]Generating {env or 'default'} configuration...[/green]")

        if env == "dev":
            config_content = _generate_dev_config()
        elif env == "prod":
            config_content = _generate_prod_config()
        elif env == "ci":
            config_content = _generate_ci_config()
        else:
            # Use existing template generator for default
            from scriptrag.config.template import generate_config_template

            config_content = generate_config_template()

        # Write config file based on format
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_format == "json":
            # Convert YAML to JSON
            config_dict = yaml.safe_load(config_content)
            # Remove comment keys
            config_dict = {
                k: v
                for k, v in config_dict.items()
                if not k.startswith("#") and v is not None
            }
            output_path.write_text(json.dumps(config_dict, indent=2), encoding="utf-8")
        elif output_format == "toml":
            # Convert YAML to TOML
            import tomli_w

            config_dict = yaml.safe_load(config_content)
            # Remove comment keys
            config_dict = {
                k: v
                for k, v in config_dict.items()
                if not k.startswith("#") and v is not None
            }
            output_path.write_text(tomli_w.dumps(config_dict), encoding="utf-8")
        else:
            # Write YAML directly
            output_path.write_text(config_content, encoding="utf-8")

        console.print(f"[green]✓[/green] Configuration file generated at {output_path}")
        console.print("[dim]Edit this file to customize your ScriptRAG settings.[/dim]")

    except Exception as e:
        console.print(
            f"[red]Error:[/red] Failed to generate config: {e}",
            style="bold",
        )
        raise typer.Exit(1) from e


@config_app.command(name="validate")
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


@config_app.command(name="show")
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


@config_app.command(name="precedence")
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
    import os

    env_vars = sources.add("[bold]Environment Variables[/bold]")
    for key in sorted(os.environ):
        if key.startswith("SCRIPTRAG_"):
            env_vars.add(f"{key} = {os.environ[key]}")

    console.print(sources)


def _filter_non_defaults(config_dict: dict, settings: ScriptRAGSettings) -> dict:  # noqa: ARG001
    """Filter out settings that are at their default values."""
    # Create a default instance
    defaults = ScriptRAGSettings()
    filtered = {}

    for key, value in config_dict.items():
        default_value = getattr(defaults, key, None)
        if value != default_value:
            filtered[key] = value

    return filtered


def _generate_dev_config() -> str:
    """Generate development environment configuration."""
    return """# ScriptRAG Development Configuration
# Optimized for local development and testing

# Database - Use local SQLite with debugging enabled
database_path: "./dev/scriptrag.db"
database_timeout: 60.0
database_wal_mode: true
database_foreign_keys: true
database_journal_mode: "WAL"
database_synchronous: "NORMAL"
database_cache_size: -4000  # 4MB cache for development

# Application
app_name: "scriptrag-dev"
metadata_scan_size: 0  # Read entire file in dev
skip_boneyard_filter: true  # Skip filtering for testing
debug: true

# Logging - Verbose for development
log_level: "DEBUG"
log_format: "console"
log_file: "./dev/logs/scriptrag.log"
log_file_rotation: "1 hour"
log_file_retention: "1 day"

# Search - Relaxed thresholds for testing
search_vector_threshold: 5
search_vector_similarity_threshold: 0.2
search_vector_result_limit_factor: 0.7
search_vector_min_results: 10
search_thread_timeout: 600.0  # 10 minutes for debugging

# LLM - Local development with Ollama
llm_provider: "openai"
llm_endpoint: "http://localhost:11434/v1"
llm_model: "llama2"
llm_embedding_model: "nomic-embed-text"
llm_embedding_dimensions: 768
llm_temperature: 0.9
llm_max_tokens: 4096
llm_force_static_models: true  # Use static models in dev
llm_model_cache_ttl: 60  # Short cache for development

# Bible/Embeddings
bible_embeddings_path: "./dev/embeddings/bible"
bible_max_file_size: 52428800  # 50MB for testing large files
bible_llm_context_limit: 4000  # Larger context for testing
"""


def _generate_prod_config() -> str:
    """Generate production environment configuration."""
    return """# ScriptRAG Production Configuration
# Optimized for production deployment

# Database - Production settings with high performance
database_path: "/var/lib/scriptrag/scriptrag.db"
database_timeout: 30.0
database_wal_mode: true
database_foreign_keys: true
database_journal_mode: "WAL"
database_synchronous: "FULL"  # Data safety in production
database_cache_size: -64000  # 64MB cache
database_temp_store: "MEMORY"

# Application
app_name: "scriptrag"
metadata_scan_size: 10240
skip_boneyard_filter: false
debug: false

# Logging - Production logging
log_level: "WARNING"
log_format: "json"  # Structured logs for monitoring
log_file: "/var/log/scriptrag/scriptrag.log"
log_file_rotation: "1 day"
log_file_retention: "30 days"

# Search - Optimized for production
search_vector_threshold: 10
search_vector_similarity_threshold: 0.3
search_vector_result_limit_factor: 0.5
search_vector_min_results: 5
search_thread_timeout: 300.0

# LLM - Production API configuration
llm_provider: "openai"
llm_endpoint: "https://api.openai.com/v1"
llm_api_key: "${OPENAI_API_KEY}"  # From environment
llm_model: "gpt-4"
llm_embedding_model: "text-embedding-3-small"
llm_embedding_dimensions: 1536
llm_temperature: 0.7
llm_max_tokens: 2048
llm_force_static_models: false
llm_model_cache_ttl: 3600

# Bible/Embeddings
bible_embeddings_path: "/var/lib/scriptrag/embeddings/bible"
bible_max_file_size: 10485760  # 10MB limit
bible_llm_context_limit: 2000
"""


def _generate_ci_config() -> str:
    """Generate CI/testing environment configuration."""
    return """# ScriptRAG CI/Testing Configuration
# Optimized for continuous integration and automated testing

# Database - In-memory for fast tests
database_path: ":memory:"
database_timeout: 10.0
database_wal_mode: false  # Not applicable for :memory:
database_foreign_keys: true
database_journal_mode: "MEMORY"
database_synchronous: "OFF"  # Speed over safety in CI
database_cache_size: -2000
database_temp_store: "MEMORY"

# Application
app_name: "scriptrag-test"
metadata_scan_size: 10240
skip_boneyard_filter: true  # Skip for test speed
debug: false

# Logging - Minimal for CI
log_level: "ERROR"
log_format: "console"
# No log file in CI
log_file_rotation: "1 hour"
log_file_retention: "1 hour"

# Search - Fast settings for CI
search_vector_threshold: 5
search_vector_similarity_threshold: 0.1
search_vector_result_limit_factor: 0.5
search_vector_min_results: 3
search_thread_timeout: 30.0  # Short timeout for CI

# LLM - Disabled for CI (use mocks)
# llm_provider: none
# No LLM configuration for CI tests
llm_temperature: 0.0
llm_force_static_models: true
llm_model_cache_ttl: 0  # No caching in CI

# Bible/Embeddings
bible_embeddings_path: "/tmp/embeddings/bible"
bible_max_file_size: 1048576  # 1MB for test files
bible_llm_context_limit: 1000

"""
