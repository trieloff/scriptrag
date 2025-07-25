"""MCP (Model Context Protocol) server for ScriptRAG.

This module provides an MCP server that exposes ScriptRAG functionality
to AI assistants and other MCP-compatible clients.
"""

import asyncio
import sys
from pathlib import Path

from . import ScriptRAG
from .config import (
    ScriptRAGSettings,
    get_logger,
    get_settings,
    load_settings,
    setup_logging_for_environment,
)


class ScriptRAGMCPServer:
    """MCP server for ScriptRAG functionality."""

    def __init__(self, config: ScriptRAGSettings):
        """Initialize the MCP server.

        Args:
            config: ScriptRAG configuration settings
        """
        self.config = config
        self.logger = get_logger(__name__)
        self.scriptrag = ScriptRAG(config=config)

        self.logger.info(
            "ScriptRAG MCP server initialized",
            host=config.mcp.host,
            port=config.mcp.port,
            max_resources=config.mcp.max_resources,
        )

    async def start(self) -> None:
        """Start the MCP server."""
        self.logger.info(
            "Starting MCP server",
            host=self.config.mcp.host,
            port=self.config.mcp.port,
        )

        # TODO: Implement actual MCP server
        # This will be implemented in Phase 7 of the project
        # The server should expose the following MCP tools:
        # - scriptrag.parse_script
        # - scriptrag.search_scenes
        # - scriptrag.get_character_info
        # - scriptrag.analyze_timeline
        # - scriptrag.update_scene
        # - scriptrag.delete_scene
        # - scriptrag.inject_scene
        # - scriptrag.get_graph_neighborhood
        # - scriptrag.export_data

        raise NotImplementedError(
            "MCP server implementation is planned for Phase 7. "
            "Please refer to the project roadmap in README.md"
        )

    async def stop(self) -> None:
        """Stop the MCP server."""
        self.logger.info("Stopping MCP server")
        # TODO: Implement cleanup logic

    def get_available_tools(self) -> list[str]:
        """Get list of available MCP tools.

        Returns:
            List of tool names that will be available
        """
        if self.config.mcp.enable_all_tools:
            return [
                "parse_script",
                "search_scenes",
                "get_character_info",
                "analyze_timeline",
                "update_scene",
                "delete_scene",
                "inject_scene",
                "get_graph_neighborhood",
                "export_data",
                "list_scripts",
                "get_scene_details",
                "get_character_relationships",
                "analyze_plot_structure",
                "validate_script_continuity",
            ]
        return self.config.mcp.enabled_tools

    def get_available_resources(self) -> list[str]:
        """Get list of available MCP resources.

        Returns:
            List of resource types that will be exposed
        """
        return [
            "screenplay",
            "scene",
            "character",
            "location",
            "timeline",
            "graph",
            "metadata",
        ]


async def run_server(
    config: ScriptRAGSettings | None = None,
    config_file: Path | None = None,
) -> None:
    """Run the MCP server.

    Args:
        config: ScriptRAG configuration
        config_file: Path to configuration file
    """
    # Load configuration
    if config:
        settings = config
    elif config_file:
        settings = load_settings(config_file)
    else:
        settings = get_settings()

    # Set up logging
    setup_logging_for_environment(
        environment=settings.environment,
        log_file=settings.get_log_file_path(),
    )

    logger = get_logger(__name__)

    server = None
    try:
        # Create and start server
        server = ScriptRAGMCPServer(settings)
        await server.start()

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error("MCP server error", error=str(e), exc_info=True)
        raise
    finally:
        if server is not None:
            await server.stop()


def main(
    config_file: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Main entry point for the MCP server.

    Args:
        config_file: Path to configuration file
        host: Override server host
        port: Override server port
    """
    try:
        # Load settings
        settings = load_settings(Path(config_file)) if config_file else get_settings()

        # Apply command line overrides
        if host:
            settings.mcp.host = host
        if port:
            settings.mcp.port = port

        # Run the server
        asyncio.run(run_server(config=settings))

    except NotImplementedError as e:
        print(f"MCP Server: {e}", file=sys.stderr)
        print(
            "\nThe MCP server will be implemented in Phase 7 of the project.",
            file=sys.stderr,
        )
        print(
            "Current development is focused on core components (Phases 1-3).",
            file=sys.stderr,
        )
        print("\nAvailable commands for current phase:", file=sys.stderr)
        print("  scriptrag config init     # Create configuration")
        print("  scriptrag dev init        # Set up development environment")
        print("  scriptrag dev status      # Check environment status")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting MCP server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
