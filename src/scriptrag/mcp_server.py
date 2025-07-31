"""MCP (Model Context Protocol) server for ScriptRAG - compatibility wrapper."""

import asyncio
import sys

from scriptrag.config import get_settings, load_settings, setup_logging_for_environment
from scriptrag.mcp.server import ScriptRAGMCPServer


async def main() -> None:
    """Run the MCP server."""
    # Parse arguments if provided
    config_file = None
    if len(sys.argv) > 1:
        config_file = sys.argv[1]

    # Load configuration
    config = load_settings(config_file) if config_file else get_settings()

    # Setup logging
    setup_logging_for_environment(config)

    # Create and start server
    server = ScriptRAGMCPServer(config)
    await server.start()


def run_server() -> None:
    """Entry point for MCP server."""
    asyncio.run(main())


if __name__ == "__main__":
    run_server()
