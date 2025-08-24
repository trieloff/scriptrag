"""Configuration initialization command."""

import json
import tempfile
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console

from scriptrag.config.template import get_default_config_path

from .templates import get_template_config

console = Console()

# Security warning to add to all templates
SECURITY_WARNING = """# SECURITY WARNING: Never commit real API keys to version control!
# Always use environment variables: ${VAR_NAME}
# Never replace ${OPENAI_API_KEY} with actual keys in this file
# Use .env files or environment variables for sensitive data

"""


def validate_output_path(path: Path, force: bool = False) -> Path:
    """Validate output path is safe and accessible.

    Args:
        path: Path to validate
        force: Skip confirmation for system paths

    Returns:
        Validated path

    Raises:
        typer.Exit: If path is invalid or user cancels
    """
    resolved = path.resolve()

    # Check if path is in a system directory (outside home and tmp)
    # Get temp directory in a secure way
    temp_dir = Path(tempfile.gettempdir())

    try:
        is_system_path = (
            resolved.is_absolute()
            and not resolved.is_relative_to(Path.home())
            and not resolved.is_relative_to(temp_dir)
        )
    except (ValueError, AttributeError):
        # is_relative_to can raise ValueError on some Python versions
        is_system_path = (
            resolved.is_absolute()
            and not str(resolved).startswith(str(Path.home()))
            and not str(resolved).startswith(str(temp_dir))
        )

    if (
        is_system_path
        and not force
        and not typer.confirm(
            f"Write configuration to system path {resolved}? "
            f"(Consider using a path in your home directory instead)"
        )
    ):
        console.print("[yellow]Configuration generation cancelled.[/yellow]")
        raise typer.Exit(0)

    # Ensure parent directory exists or can be created
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        console.print(f"[red]Error: Cannot create directory: {e}[/red]")
        raise typer.Exit(1) from e

    return resolved


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
            output_path = validate_output_path(output, force)
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

        # Get the appropriate template
        config_content = get_template_config(env)

        # Add security warning to the beginning
        config_content = SECURITY_WARNING + config_content

        # Write config file based on format
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_format == "json":
            # Convert YAML to JSON
            config_dict = yaml.safe_load(config_content)
            # Remove comment keys
            config_dict = {
                k: v
                for k, v in config_dict.items()
                if not isinstance(k, str) or not k.startswith("#")
            }
            output_path.write_text(json.dumps(config_dict, indent=2), encoding="utf-8")
        elif output_format == "toml":
            # Import tomli_w with error handling
            try:
                import tomli_w
            except ImportError:
                console.print(
                    "[red]Error: tomli_w package required for TOML output[/red]\n"
                    "[yellow]Install with: pip install tomli-w[/yellow]"
                )
                raise typer.Exit(1) from None

            # Convert YAML to TOML
            config_dict = yaml.safe_load(config_content)
            # Remove comment keys
            config_dict = {
                k: v
                for k, v in config_dict.items()
                if not isinstance(k, str) or not k.startswith("#")
            }
            output_path.write_text(tomli_w.dumps(config_dict), encoding="utf-8")
        else:
            # Write YAML directly
            output_path.write_text(config_content, encoding="utf-8")

        console.print(f"[green]✓[/green] Configuration file generated at {output_path}")
        console.print("[dim]Edit this file to customize your ScriptRAG settings.[/dim]")
        console.print(
            "[yellow]⚠️  Never commit API keys directly in config files![/yellow]"
        )

    except (typer.Exit, typer.Abort):
        # Re-raise Typer control flow exceptions
        raise
    except Exception as e:
        console.print(
            f"[red]Error:[/red] Failed to generate config: {e}",
            style="bold",
        )
        raise typer.Exit(1) from e
