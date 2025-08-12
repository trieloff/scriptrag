"""MCP server command for ScriptRAG."""

from typing import Annotated

import typer

from scriptrag.config import get_logger

logger = get_logger(__name__)


def mcp_command(
    host: Annotated[str, typer.Option("--host", help="Host to bind to")] = "localhost",
    port: Annotated[int, typer.Option("--port", help="Port to bind to")] = 5173,
) -> None:
    """Run the ScriptRAG MCP (Model Context Protocol) server.

    This starts an MCP server that exposes ScriptRAG's search and query
    capabilities to MCP-compatible clients like Claude Desktop.

    Example:
        scriptrag mcp
        scriptrag mcp --host 0.0.0.0 --port 8080
    """
    try:
        # Import here to avoid circular dependencies
        from scriptrag.mcp.server import main as mcp_main

        logger.info("Starting MCP server", host=host, port=port)

        # The MCP server main function handles its own event loop
        mcp_main()

    except ImportError as e:
        logger.error("Failed to import MCP server", error=str(e))
        raise typer.Exit(1) from e
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
        raise typer.Exit(0) from None
    except Exception as e:
        logger.error("MCP server failed", error=str(e))
        raise typer.Exit(1) from e
