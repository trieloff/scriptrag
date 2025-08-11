"""MCP server command for ScriptRAG."""

import typer

from scriptrag.config import get_logger

logger = get_logger(__name__)


def mcp_command(
    ctx: typer.Context,  # noqa: ARG001
) -> None:
    """Run the ScriptRAG MCP server for AI assistant integration.

    The MCP (Model Context Protocol) server exposes ScriptRAG functionality
    through a standardized protocol that can be used by AI assistants like Claude.

    Examples:
        Start the MCP server:
        $ scriptrag mcp

        Use with Claude Desktop by adding to configuration:
        {
            "mcpServers": {
                "scriptrag": {
                    "command": "scriptrag",
                    "args": ["mcp"]
                }
            }
        }
    """
    try:
        logger.info("Starting ScriptRAG MCP server...")

        # Import and run the MCP server
        from scriptrag.mcp.server import main

        main()
    except ImportError as e:
        logger.error(f"Failed to import MCP server: {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        logger.error(f"MCP server error: {e}")
        raise typer.Exit(1) from e
