"""MCP server commands for ScriptRAG CLI."""

import contextlib
from collections.abc import Callable
from typing import Annotated, Any

import typer
from rich.console import Console

console = Console()
server_app = typer.Typer(
    name="server",
    help="MCP server commands",
    rich_markup_mode="rich",
)

# Optional imports for server functionality
create_app: Callable[[], Any] | None = None
with contextlib.suppress(ImportError):
    from scriptrag.api.app import create_app


@server_app.command("start")
def server_start() -> None:
    """Start the MCP server."""
    console.print("[blue]Starting ScriptRAG MCP server...[/blue]")
    console.print("[yellow]⚠[/yellow] MCP server functionality is not yet implemented")
    console.print("This command will be available in Phase 5 of development")


@server_app.command("api")
def server_api(
    host: Annotated[
        str, typer.Option("--host", "-h", help="API host address")
    ] = "127.0.0.1",  # Use localhost by default for security
    port: Annotated[int, typer.Option("--port", "-p", help="API port number")] = 8000,
    reload: Annotated[
        bool, typer.Option("--reload", "-r", help="Enable auto-reload")
    ] = False,
) -> None:
    """Start the REST API server."""
    console.print("[blue]Starting ScriptRAG REST API server...[/blue]")
    console.print(f"[dim]Host: {host}:{port}[/dim]")
    console.print(f"[dim]Docs: http://{host}:{port}/api/v1/docs[/dim]")

    if create_app is None:
        console.print(
            "[red]Error: API server is not available. Install with 'api' extra.[/red]"
        )
        raise typer.Exit(1)

    try:
        import uvicorn
    except ImportError:
        console.print(
            "[red]Error: uvicorn is not installed. "
            "Install with 'pip install uvicorn'.[/red]"
        )
        raise typer.Exit(1) from None

    app = create_app()
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info" if reload else "warning",
    )