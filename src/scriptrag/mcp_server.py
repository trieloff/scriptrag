"""MCP (Model Context Protocol) server for ScriptRAG - compatibility wrapper."""

import asyncio
import sys

from .config import get_settings, load_settings, setup_logging_for_environment
from .mcp.server import ScriptRAGMCPServer


async def run_server(
    config_path: str | None = None,
    log_level: str | None = None,
) -> None:
    """Run the MCP server.

    Args:
        config_path: Optional path to configuration file
        log_level: Optional log level override
    """
    # Setup environment
    setup_logging_for_environment()

    # Load configuration
    config = load_settings(config_path) if config_path else get_settings()

    # Override log level if provided
    if log_level:
        config.logging.level = log_level

    # Create and start server
    server = ScriptRAGMCPServer(config)

    try:
        await server.start()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        await server.stop()


def main() -> None:
    """Main entry point for MCP server."""
    import argparse

    parser = argparse.ArgumentParser(
        description="ScriptRAG MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override log level",
    )

    args = parser.parse_args()

    # Run the server
    try:
        asyncio.run(run_server(args.config, args.log_level))
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
