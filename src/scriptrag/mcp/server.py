"""MCP Server for ScriptRAG."""

import os
from typing import Any

from mcp.server import FastMCP

from scriptrag.config import get_logger
from scriptrag.mcp.protocol import CacheConfig, RateLimitConfig

logger = get_logger(__name__)


def create_server() -> FastMCP:
    """Create and configure the MCP server.

    Returns:
        Configured FastMCP server instance
    """
    # Check if enhanced mode is enabled
    use_enhanced = os.environ.get("SCRIPTRAG_MCP_ENHANCED", "false").lower() == "true"

    if use_enhanced:
        # Use enhanced server with full features
        from scriptrag.mcp.enhanced_server import create_enhanced_server

        # Get configuration from environment
        rate_limit = int(os.environ.get("SCRIPTRAG_MCP_RATE_LIMIT", "100"))
        cache_ttl = int(os.environ.get("SCRIPTRAG_MCP_CACHE_TTL", "600"))
        enable_ws = os.environ.get("SCRIPTRAG_MCP_WEBSOCKET", "false").lower() == "true"

        rate_config = RateLimitConfig(requests_per_minute=rate_limit)
        cache_config = CacheConfig(ttl_seconds=cache_ttl)

        enhanced_server = create_enhanced_server(
            enable_websocket=enable_ws,
            rate_limit_config=rate_config,
            cache_config=cache_config,
        )

        logger.info(
            f"Created enhanced MCP server with rate_limit={rate_limit}/min, "
            f"cache_ttl={cache_ttl}s, websocket={enable_ws}"
        )

        return enhanced_server.get_mcp_instance()

    # Use basic server (backward compatible)
    mcp = FastMCP("scriptrag")

    # Import and register tools
    from scriptrag.mcp.tools.query import register_query_tools
    from scriptrag.mcp.tools.scene import register_scene_tools
    from scriptrag.mcp.tools.search import register_search_tool

    # Register the search tool
    register_search_tool(mcp)

    # Register dynamic query tools
    register_query_tools(mcp)

    # Register scene management tools
    register_scene_tools(mcp)

    logger.info(
        "Created basic MCP server (set SCRIPTRAG_MCP_ENHANCED=true for full features)"
    )

    return mcp


def create_enhanced_server_direct(
    rate_limit: int | None = None,
    cache_ttl: int | None = None,
    enable_websocket: bool = False,
) -> Any:
    """Create an enhanced MCP server directly.

    This function provides direct access to the enhanced server
    for applications that want to use the full feature set.

    Args:
        rate_limit: Requests per minute limit
        cache_ttl: Cache TTL in seconds
        enable_websocket: Enable WebSocket support

    Returns:
        ScriptRAGMCPServer instance with all features
    """
    from scriptrag.mcp.enhanced_server import create_enhanced_server

    rate_config = None
    if rate_limit:
        rate_config = RateLimitConfig(requests_per_minute=rate_limit)

    cache_config = None
    if cache_ttl:
        cache_config = CacheConfig(ttl_seconds=cache_ttl)

    return create_enhanced_server(
        enable_websocket=enable_websocket,
        rate_limit_config=rate_config,
        cache_config=cache_config,
    )


def main() -> None:
    """Main entry point for MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="ScriptRAG MCP Server")
    parser.add_argument(
        "--enhanced",
        action="store_true",
        help="Use enhanced server with full protocol support",
    )
    parser.add_argument(
        "--websocket",
        action="store_true",
        help="Enable WebSocket support (requires --enhanced)",
    )
    parser.add_argument(
        "--ws-host",
        default="localhost",
        help="WebSocket host (requires --enhanced --websocket)",
    )
    parser.add_argument(
        "--ws-port",
        type=int,
        default=8765,
        help="WebSocket port (requires --enhanced --websocket)",
    )

    args = parser.parse_args()

    if args.enhanced:
        # Use enhanced server with CLI options
        from scriptrag.mcp.enhanced_server import main as enhanced_main

        # Set environment to use enhanced mode
        os.environ["SCRIPTRAG_MCP_ENHANCED"] = "true"
        if args.websocket:
            os.environ["SCRIPTRAG_MCP_WEBSOCKET"] = "true"

        # Run enhanced server main
        enhanced_main()
    else:
        # Run basic server
        server = create_server()
        server.run()


if __name__ == "__main__":
    main()
