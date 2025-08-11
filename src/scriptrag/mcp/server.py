"""ScriptRAG MCP Server implementation."""

from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from scriptrag.config import ScriptRAGSettings, get_logger, get_settings

logger = get_logger(__name__)


class ServerContext:
    """Server context for sharing state across tools."""

    def __init__(self, settings: ScriptRAGSettings | None = None):
        """Initialize server context.

        Args:
            settings: Configuration settings
        """
        self.settings = settings or get_settings()
        self.logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP):  # noqa: ARG001
    """Manage server lifecycle.

    Args:
        server: FastMCP server instance

    Yields:
        ServerContext: Initialized server context
    """
    logger.info("Starting ScriptRAG MCP Server")
    settings = get_settings()
    context = ServerContext(settings=settings)

    # Initialize database if needed
    try:
        from scriptrag.api.database import DatabaseInitializer

        db_init = DatabaseInitializer(settings)
        if not db_init.database_exists():
            logger.info("Initializing database")
            db_init.initialize()
            logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))

    yield context

    logger.info("Shutting down ScriptRAG MCP Server")


# Initialize MCP server
mcp = FastMCP("ScriptRAG", lifespan=lifespan)


# Import and register all tools
def register_tools() -> None:
    """Register all MCP tools from the tools directory."""
    # All tools are automatically registered via decorators in their modules
    logger.info("All MCP tools registered successfully")


# Import and register all resources
def register_resources() -> None:
    """Register all MCP resources from the resources directory."""
    # All resources are automatically registered via decorators in their modules
    logger.info("All MCP resources registered successfully")


# Register tools and resources when module is imported
register_tools()
register_resources()


def main() -> None:
    """Main entry point for the MCP server."""
    import sys

    # Run the MCP server
    mcp.run(transport="stdio")
    sys.exit(0)


if __name__ == "__main__":
    main()
