"""Development and debugging commands for ScriptRAG CLI."""

from pathlib import Path
from typing import Annotated

import requests
import typer
from rich.console import Console
from rich.table import Table as RichTable

from scriptrag.config import create_default_config, get_logger, get_settings

console = Console()
dev_app = typer.Typer(
    name="dev",
    help="Development and debugging commands",
    rich_markup_mode="rich",
)


@dev_app.command("init")
def dev_init(
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force initialization even if files exist",
        ),
    ] = False,
) -> None:
    """Initialize development environment with sample data."""
    console.print("[blue]Initializing development environment...[/blue]")

    # Create sample directories
    dirs_to_create = [
        "data/scripts",
        "data/databases",
        "logs",
        "temp",
    ]

    for dir_path in dirs_to_create:
        path = Path(dir_path)
        if path.exists() and not force:
            console.print(f"[yellow]Directory exists:[/yellow] {path}")
        else:
            path.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]Created:[/green] {path}")

    # Create sample config if it doesn't exist
    config_path = Path("config.yaml")
    if not config_path.exists() or force:
        try:
            create_default_config(config_path)
            console.print(f"[green]Created:[/green] {config_path}")
        except Exception as e:
            logger = get_logger(__name__)
            logger.error("Error creating config", error=str(e))
            console.print(f"[red]Error creating config:[/red] {e}")

    console.print("[green]✓[/green] Development environment initialized")


@dev_app.command("status")
def dev_status() -> None:
    """Show development environment status."""
    console.print("[bold blue]Development Environment Status[/bold blue]")

    # Check key files and directories
    checks = [
        ("Configuration", Path("config.yaml")),
        ("Scripts directory", Path("data/scripts")),
        ("Database directory", Path("data/databases")),
        ("Logs directory", Path("logs")),
    ]

    table = RichTable(show_header=True, header_style="bold blue")
    table.add_column("Component")
    table.add_column("Status")
    table.add_column("Path")

    for name, path in checks:
        status = "[green]✓ Exists[/green]" if path.exists() else "[red]✗ Missing[/red]"
        table.add_row(name, status, str(path))

    console.print(table)


@dev_app.command("test-llm")
def dev_test_llm() -> None:
    """Test LLM connection and basic functionality."""
    console.print("[blue]Testing LLM connection...[/blue]")

    try:
        settings = get_settings()

        # Test embeddings endpoint
        embed_url = f"{settings.llm.endpoint}/embeddings"
        embed_data = {"input": "test", "model": settings.llm.embedding_model}

        console.print(f"[dim]Testing embeddings: {embed_url}[/dim]")
        embed_response = requests.post(embed_url, json=embed_data, timeout=10)

        if embed_response.status_code == 200:
            console.print("[green]✓[/green] Embeddings endpoint working")
        else:
            console.print(
                f"[red]✗[/red] Embeddings endpoint error: {embed_response.status_code}"
            )

        # Test completion endpoint
        completion_url = f"{settings.llm.endpoint}/chat/completions"
        completion_data = {
            "model": settings.llm.default_model,
            "messages": [{"role": "user", "content": "Say 'test successful'"}],
            "max_tokens": 10,
        }

        console.print(f"[dim]Testing completions: {completion_url}[/dim]")
        completion_response = requests.post(
            completion_url, json=completion_data, timeout=10
        )

        if completion_response.status_code == 200:
            console.print("[green]✓[/green] Completion endpoint working")
            result = completion_response.json()
            if result.get("choices"):
                message = result["choices"][0]["message"]["content"]
                console.print(f"[dim]Response: {message.strip()}[/dim]")
        else:
            console.print(
                f"[red]✗[/red] Completion endpoint error: "
                f"{completion_response.status_code}"
            )

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("LLM test failed", error=str(e))
        console.print(f"[red]✗[/red] LLM test failed: {e}")
        raise typer.Exit(1) from e
