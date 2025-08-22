"""Enhanced MCP Server with full protocol support and advanced features."""

import asyncio
from typing import Any

from scriptrag.config import get_logger
from scriptrag.mcp.protocol import (
    CacheConfig,
    EnhancedMCPServer,
    RateLimitConfig,
    StreamingMode,
)
from scriptrag.mcp.tools.query import register_query_tools
from scriptrag.mcp.tools.scene import register_scene_tools
from scriptrag.mcp.tools.search import register_search_tool

logger = get_logger(__name__)


class ScriptRAGMCPServer(EnhancedMCPServer):
    """ScriptRAG-specific MCP server with all features enabled."""

    def __init__(
        self,
        name: str = "scriptrag",
        enable_websocket: bool = False,
        rate_limit_config: RateLimitConfig | None = None,
        cache_config: CacheConfig | None = None,
    ):
        """Initialize the ScriptRAG MCP server.

        Args:
            name: Server name for MCP protocol
            enable_websocket: Enable WebSocket support for real-time updates
            rate_limit_config: Rate limiting configuration
            cache_config: Cache configuration
        """
        super().__init__(name, rate_limit_config, cache_config)

        self.enable_websocket = enable_websocket
        self.websocket_clients: dict[str, Any] = {}

        # Register ScriptRAG-specific tools
        self._register_scriptrag_tools()

        # Register streaming tools
        self._register_streaming_tools()

        # Register introspection tools
        self._register_introspection_tools()

    def _register_scriptrag_tools(self) -> None:
        """Register all ScriptRAG tools with enhanced features."""
        # Register existing tools through the MCP instance
        register_search_tool(self.mcp)
        register_query_tools(self.mcp)
        register_scene_tools(self.mcp)

        logger.info("Registered ScriptRAG tools")

    def _register_streaming_tools(self) -> None:
        """Register tools that support streaming responses."""

        @self.mcp.tool()
        async def scriptrag_stream_scenes(
            script_id: int,
            stream: bool = True,
            chunk_size: int = 10,
        ) -> dict[str, Any]:
            """Stream scenes from a script for large screenplays.

            This tool streams scenes in chunks, useful for processing
            large scripts without loading everything into memory at once.

            Args:
                script_id: ID of the script to stream scenes from
                stream: Enable streaming mode
                chunk_size: Number of scenes per chunk

            Returns:
                Stream ID for retrieving chunks or full result if not streaming
            """
            if not stream:
                # Non-streaming mode - return all at once
                # For now, return empty result as scene listing needs proper API
                # TODO: Implement proper scene listing API
                scenes: list[Any] = []
                return {
                    "success": True,
                    "script_id": script_id,
                    "scenes": [{"id": s.id, "content": s.content} for s in scenes],
                    "total_count": len(scenes),
                }

            # Streaming mode
            import uuid

            stream_id = str(uuid.uuid4())

            async def scene_streamer() -> None:
                """Stream scenes in chunks."""
                # For now, return empty result as scene listing needs proper API
                # TODO: Implement proper scene listing API

                try:
                    scenes: list[Any] = []
                    total = len(scenes)

                    # Send initial metadata
                    await self.streaming_handler.send_chunk(
                        stream_id,
                        {
                            "type": "metadata",
                            "total_scenes": total,
                            "chunk_size": chunk_size,
                        },
                    )

                    # Stream scenes in chunks
                    for i in range(0, total, chunk_size):
                        chunk = scenes[i : i + chunk_size]
                        await self.streaming_handler.send_chunk(
                            stream_id,
                            {
                                "type": "scenes",
                                "chunk_index": i // chunk_size,
                                "scenes": [
                                    {"id": s.id, "content": s.content} for s in chunk
                                ],
                            },
                        )

                        # Small delay to prevent overwhelming
                        await asyncio.sleep(0.1)

                    # Send completion signal
                    await self.streaming_handler.send_chunk(
                        stream_id,
                        {
                            "type": "complete",
                            "total_streamed": total,
                        },
                    )

                finally:
                    await self.streaming_handler.close_stream(stream_id)

            # Create stream
            await self.streaming_handler.create_stream(stream_id, StreamingMode.CHUNKED)

            # Start streaming task
            _ = asyncio.create_task(scene_streamer())  # noqa: RUF006

            return {
                "success": True,
                "stream_id": stream_id,
                "message": f"Streaming scenes from script {script_id}",
            }

        @self.mcp.tool()
        async def scriptrag_read_stream(
            stream_id: str,
            timeout: float = 5.0,
        ) -> dict[str, Any]:
            """Read chunks from an active stream.

            Args:
                stream_id: ID of the stream to read from
                timeout: Timeout in seconds for reading

            Returns:
                Next chunk from the stream or completion status
            """
            try:
                chunks = []
                async for chunk in self.streaming_handler.read_stream(
                    stream_id, timeout
                ):
                    chunks.append(chunk)
                    # Return first chunk immediately for responsive UI
                    if len(chunks) == 1:
                        return {
                            "success": True,
                            "chunk": chunk,
                            "has_more": True,
                        }

                # No more chunks
                return {
                    "success": True,
                    "chunk": None,
                    "has_more": False,
                    "message": "Stream completed",
                }

            except ValueError as e:
                return {
                    "success": False,
                    "error": str(e),
                }

    def _register_introspection_tools(self) -> None:
        """Register tool discovery and introspection capabilities."""

        @self.mcp.tool()
        async def scriptrag_discover_tools(
            category: str | None = None,
            include_params: bool = True,
        ) -> dict[str, Any]:
            """Discover available MCP tools with detailed information.

            This tool provides comprehensive information about all available
            tools, their parameters, and usage examples.

            Args:
                category: Filter by tool category (search, query, scene, etc.)
                include_params: Include parameter details in response

            Returns:
                Dictionary with tool information
            """
            tools_info = []

            # Get all registered tools
            tools = await self.mcp.list_tools()

            for tool in tools:
                # Parse tool category from name
                tool_category = None
                if tool.name.startswith("scriptrag_"):
                    parts = tool.name.split("_")
                    if len(parts) > 1:
                        tool_category = parts[1]

                # Filter by category if specified
                if category and tool_category != category:
                    continue

                tool_info = {
                    "name": tool.name,
                    "category": tool_category,
                    "description": tool.description or "No description available",
                }

                if include_params and hasattr(tool, "inputSchema"):
                    # Extract parameter information from schema
                    schema = tool.inputSchema
                    if schema and "properties" in schema:
                        params = []
                        for param_name, param_schema in schema["properties"].items():
                            param_info = {
                                "name": param_name,
                                "type": param_schema.get("type", "unknown"),
                                "description": param_schema.get("description", ""),
                                "required": param_name in schema.get("required", []),
                            }

                            # Add additional schema info
                            if "enum" in param_schema:
                                param_info["choices"] = param_schema["enum"]
                            if "default" in param_schema:
                                param_info["default"] = param_schema["default"]

                            params.append(param_info)

                        tool_info["parameters"] = params

                tools_info.append(tool_info)

            # Group by category
            categorized: dict[str, list[Any]] = {}
            for tool in tools_info:
                cat = tool.get("category", "uncategorized")
                if cat not in categorized:
                    categorized[cat] = []
                categorized[cat].append(tool)

            return {
                "success": True,
                "total_tools": len(tools_info),
                "categories": list(categorized.keys()),
                "tools": tools_info,
                "tools_by_category": categorized,
            }

        @self.mcp.tool()
        async def scriptrag_tool_help(tool_name: str) -> dict[str, Any]:
            """Get detailed help for a specific tool.

            Args:
                tool_name: Name of the tool to get help for

            Returns:
                Detailed tool documentation and usage examples
            """
            tools = await self.mcp.list_tools()

            for tool in tools:
                if tool.name == tool_name:
                    help_info = {
                        "name": tool.name,
                        "description": tool.description or "No description available",
                    }

                    # Add parameter details if available
                    if hasattr(tool, "inputSchema"):
                        schema = tool.inputSchema
                        if schema:
                            help_info["input_schema"] = schema

                            # Generate usage example
                            if "properties" in schema:
                                example_params = {}
                                for param, info in schema["properties"].items():
                                    if "default" in info:
                                        example_params[param] = info["default"]
                                    elif info.get("type") == "string":
                                        example_params[param] = f"<{param}>"
                                    elif info.get("type") == "number":
                                        example_params[param] = 0
                                    elif info.get("type") == "boolean":
                                        example_params[param] = False

                                help_info["example_usage"] = {
                                    "tool": tool_name,
                                    "params": example_params,
                                }

                    # Add category-specific tips
                    if "search" in tool_name:
                        help_info["tips"] = [
                            "Use fuzzy=True for semantic search",
                            "CAPS words are detected as characters/locations",
                            "Quoted text is detected as dialogue",
                        ]
                    elif "query" in tool_name:
                        help_info["tips"] = [
                            "Use limit parameter to control result size",
                            "Check scriptrag_discover_tools for available queries",
                        ]
                    elif "stream" in tool_name:
                        help_info["tips"] = [
                            "Use streaming for large datasets",
                            "Read stream chunks with scriptrag_read_stream",
                        ]

                    return {
                        "success": True,
                        "tool": help_info,
                    }

            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found",
                "suggestion": "Use scriptrag_discover_tools to list available tools",
            }

    async def handle_websocket(self, websocket: Any, path: str) -> None:  # noqa: ARG002
        """Handle WebSocket connections for real-time updates."""
        if not self.enable_websocket:
            await websocket.send_json({"error": "WebSocket support is not enabled"})
            return

        client_id = websocket.request_headers.get("X-Client-Id", "anonymous")
        self.websocket_clients[client_id] = websocket

        try:
            # Send welcome message
            await websocket.send_json(
                {
                    "type": "connected",
                    "client_id": client_id,
                    "message": "Connected to ScriptRAG MCP WebSocket",
                }
            )

            # Handle incoming messages
            async for message in websocket:
                data = message if isinstance(message, dict) else {"raw": message}

                # Process different message types
                if data.get("type") == "subscribe":
                    # Subscribe to specific events
                    stream_id = data.get("stream_id")
                    if stream_id:
                        # Forward stream chunks via WebSocket
                        async for chunk in self.streaming_handler.read_stream(
                            stream_id
                        ):
                            await websocket.send_json(
                                {
                                    "type": "stream_chunk",
                                    "stream_id": stream_id,
                                    "chunk": chunk,
                                }
                            )

                elif data.get("type") == "ping":
                    # Respond to ping
                    await websocket.send_json(
                        {
                            "type": "pong",
                            "timestamp": data.get("timestamp"),
                        }
                    )

        except Exception as e:
            logger.error(f"WebSocket error for client {client_id}: {e}")
        finally:
            # Clean up
            if client_id in self.websocket_clients:
                del self.websocket_clients[client_id]

    async def broadcast_event(self, event_type: str, data: Any) -> None:
        """Broadcast an event to all connected WebSocket clients."""
        if not self.enable_websocket:
            return

        message = {
            "type": "event",
            "event_type": event_type,
            "data": data,
        }

        # Send to all connected clients
        disconnected = []
        for client_id, websocket in self.websocket_clients.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to client {client_id}: {e}")
                disconnected.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected:
            del self.websocket_clients[client_id]

    async def run_with_websocket(
        self, host: str = "localhost", port: int = 8765
    ) -> None:
        """Run the MCP server with WebSocket support."""
        if not self.enable_websocket:
            raise ValueError("WebSocket support is not enabled")

        import websockets

        # Start WebSocket server
        websocket_server = await websockets.serve(self.handle_websocket, host, port)

        logger.info(f"WebSocket server started on ws://{host}:{port}")

        # Run cleanup task periodically
        async def cleanup_task() -> None:
            while True:
                await asyncio.sleep(3600)  # Every hour
                await self.cleanup()

        # Run both MCP and WebSocket servers
        await asyncio.gather(
            self.mcp.run(),
            websocket_server.wait_closed(),
            cleanup_task(),
        )


def create_enhanced_server(
    enable_websocket: bool = False,
    rate_limit_config: RateLimitConfig | None = None,
    cache_config: CacheConfig | None = None,
) -> ScriptRAGMCPServer:
    """Create an enhanced MCP server with full features.

    Args:
        enable_websocket: Enable WebSocket support for real-time updates
        rate_limit_config: Custom rate limiting configuration
        cache_config: Custom cache configuration

    Returns:
        Configured ScriptRAGMCPServer instance
    """
    # Default configurations
    if rate_limit_config is None:
        rate_limit_config = RateLimitConfig(
            requests_per_minute=100,
            requests_per_hour=2000,
            burst_size=20,
            cooldown_seconds=30,
        )

    if cache_config is None:
        cache_config = CacheConfig(
            ttl_seconds=600,  # 10 minutes
            max_size=200,
            enable_compression=True,
        )

    server = ScriptRAGMCPServer(
        name="scriptrag",
        enable_websocket=enable_websocket,
        rate_limit_config=rate_limit_config,
        cache_config=cache_config,
    )

    logger.info(
        f"Created enhanced MCP server with "
        f"WebSocket={'enabled' if enable_websocket else 'disabled'}, "
        f"rate_limit={rate_limit_config.requests_per_minute}/min, "
        f"cache_ttl={cache_config.ttl_seconds}s"
    )

    return server


def main() -> None:
    """Main entry point for enhanced MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="ScriptRAG Enhanced MCP Server")
    parser.add_argument(
        "--websocket",
        action="store_true",
        help="Enable WebSocket support for real-time updates",
    )
    parser.add_argument(
        "--ws-host",
        default="localhost",
        help="WebSocket server host (default: localhost)",
    )
    parser.add_argument(
        "--ws-port",
        type=int,
        default=8765,
        help="WebSocket server port (default: 8765)",
    )
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=100,
        help="Requests per minute rate limit (default: 100)",
    )
    parser.add_argument(
        "--cache-ttl",
        type=int,
        default=600,
        help="Cache TTL in seconds (default: 600)",
    )

    args = parser.parse_args()

    # Configure server
    rate_config = RateLimitConfig(requests_per_minute=args.rate_limit)
    cache_config = CacheConfig(ttl_seconds=args.cache_ttl)

    server = create_enhanced_server(
        enable_websocket=args.websocket,
        rate_limit_config=rate_config,
        cache_config=cache_config,
    )

    # Run server
    if args.websocket:
        asyncio.run(server.run_with_websocket(args.ws_host, args.ws_port))
    else:
        server.mcp.run()


if __name__ == "__main__":
    main()
