"""MCP Server for ScriptRAG."""

from mcp.server import FastMCP

from scriptrag.config import get_logger

logger = get_logger(__name__)


def create_server() -> FastMCP:
    """Create and configure the MCP server.

    Returns:
        Configured FastMCP server instance
    """
    mcp = FastMCP("scriptrag")

    # Import and register tools
    from scriptrag.mcp.tools.query import register_query_tools
    from scriptrag.mcp.tools.search import register_search_tool

    # Register the search tool
    register_search_tool(mcp)

    # Register dynamic query tools
    register_query_tools(mcp)

    return mcp


def main() -> None:
    """Main entry point for MCP server."""
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()
