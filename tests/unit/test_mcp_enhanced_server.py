"""Unit tests for enhanced MCP server implementation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.mcp.enhanced_server import (
    ScriptRAGMCPServer,
    create_enhanced_server,
)
from scriptrag.mcp.protocol import CacheConfig, RateLimitConfig


@pytest.mark.asyncio
class TestScriptRAGMCPServer:
    """Test the ScriptRAG-specific MCP server."""

    async def test_server_initialization(self):
        """Test server initialization."""
        server = ScriptRAGMCPServer(
            name="test",
            enable_websocket=False,
        )

        assert server.mcp.name == "test"
        assert server.enable_websocket is False
        assert len(server.websocket_clients) == 0

    async def test_server_with_websocket_enabled(self):
        """Test server with WebSocket support enabled."""
        server = ScriptRAGMCPServer(
            name="test",
            enable_websocket=True,
        )

        assert server.enable_websocket is True

    @patch("scriptrag.mcp.enhanced_server.register_search_tool")
    @patch("scriptrag.mcp.enhanced_server.register_query_tools")
    @patch("scriptrag.mcp.enhanced_server.register_scene_tools")
    async def test_scriptrag_tools_registration(
        self, mock_scene, mock_query, mock_search
    ):
        """Test that ScriptRAG tools are registered."""
        server = ScriptRAGMCPServer(name="test")

        # Verify all tool modules were called
        mock_search.assert_called_once_with(server.mcp)
        mock_query.assert_called_once_with(server.mcp)
        mock_scene.assert_called_once_with(server.mcp)

    async def test_streaming_tools_registration(self):
        """Test that streaming tools are registered."""
        server = ScriptRAGMCPServer(name="test")

        # Get registered tools
        tools = await server.mcp.list_tools()
        tool_names = [t.name for t in tools]

        # Check streaming tools
        assert "scriptrag_stream_scenes" in tool_names
        assert "scriptrag_read_stream" in tool_names

    async def test_introspection_tools_registration(self):
        """Test that introspection tools are registered."""
        server = ScriptRAGMCPServer(name="test")

        # Get registered tools
        tools = await server.mcp.list_tools()
        tool_names = [t.name for t in tools]

        # Check introspection tools
        assert "scriptrag_discover_tools" in tool_names
        assert "scriptrag_tool_help" in tool_names

    @patch("scriptrag.api.DatabaseOperations")
    async def test_stream_scenes_non_streaming(self, mock_db_ops_class):
        """Test stream_scenes tool in non-streaming mode."""
        # Setup mock
        mock_db_ops = MagicMock()
        mock_db_ops_class.return_value = mock_db_ops

        mock_scene = MagicMock()
        mock_scene.id = 1
        mock_scene.content = "test"
        mock_db_ops.get_scenes_for_script.return_value = [mock_scene]

        server = ScriptRAGMCPServer(name="test")

        # Call the tool
        result = await server.mcp.call_tool(
            "scriptrag_stream_scenes",
            {"script_id": 1, "stream": False},
        )

        # Extract result
        data = result[1]

        assert data["success"] is True
        assert data["script_id"] == 1
        assert len(data["scenes"]) == 1
        assert data["total_count"] == 1

    @patch("scriptrag.api.DatabaseOperations")
    async def test_stream_scenes_streaming_mode(self, mock_db_ops_class):
        """Test stream_scenes tool in streaming mode."""
        # Setup mock
        mock_db_ops = MagicMock()
        mock_db_ops_class.return_value = mock_db_ops

        mock_scenes = []
        for i in range(5):
            scene = MagicMock()
            scene.id = i
            scene.content = f"scene{i}"
            mock_scenes.append(scene)

        mock_db_ops.get_scenes_for_script.return_value = mock_scenes

        server = ScriptRAGMCPServer(name="test")

        # Call the tool with streaming
        result = await server.mcp.call_tool(
            "scriptrag_stream_scenes",
            {"script_id": 1, "stream": True, "chunk_size": 2},
        )

        # Extract result
        data = result[1]

        assert data["success"] is True
        assert "stream_id" in data
        assert "Streaming scenes" in data["message"]

    async def test_read_stream_tool(self):
        """Test reading from a stream."""
        server = ScriptRAGMCPServer(name="test")

        # Create a stream first
        stream_id = "test-stream"
        await server.streaming_handler.create_stream(stream_id)

        # Send some data
        await server.streaming_handler.send_chunk(stream_id, {"data": "chunk1"})
        await server.streaming_handler.close_stream(stream_id)

        # Read stream
        result = await server.mcp.call_tool(
            "scriptrag_read_stream",
            {"stream_id": stream_id, "timeout": 1.0},
        )

        data = result[1]
        assert data["success"] is True
        assert data["chunk"] == {"data": "chunk1"}

    async def test_read_stream_not_found(self):
        """Test reading from non-existent stream."""
        server = ScriptRAGMCPServer(name="test")

        result = await server.mcp.call_tool(
            "scriptrag_read_stream",
            {"stream_id": "nonexistent", "timeout": 1.0},
        )

        data = result[1]
        assert data["success"] is False
        assert "not found" in data["error"]

    async def test_discover_tools(self):
        """Test tool discovery."""
        server = ScriptRAGMCPServer(name="test")

        # Discover all tools
        result = await server.mcp.call_tool(
            "scriptrag_discover_tools",
            {"include_params": True},
        )

        data = result[1]
        assert data["success"] is True
        assert data["total_tools"] > 0
        assert "tools" in data
        assert "tools_by_category" in data
        assert "categories" in data

    async def test_discover_tools_by_category(self):
        """Test tool discovery filtered by category."""
        server = ScriptRAGMCPServer(name="test")

        # Discover only mcp tools
        result = await server.mcp.call_tool(
            "scriptrag_discover_tools",
            {"category": "mcp", "include_params": False},
        )

        data = result[1]
        assert data["success"] is True

        # All tools should be mcp category
        for tool in data["tools"]:
            assert tool["category"] == "mcp"

    async def test_tool_help(self):
        """Test getting help for a specific tool."""
        server = ScriptRAGMCPServer(name="test")

        # Get help for a known tool
        result = await server.mcp.call_tool(
            "scriptrag_tool_help",
            {"tool_name": "scriptrag_mcp_stats"},
        )

        data = result[1]
        assert data["success"] is True
        assert data["tool"]["name"] == "scriptrag_mcp_stats"
        assert "description" in data["tool"]

    async def test_tool_help_not_found(self):
        """Test getting help for non-existent tool."""
        server = ScriptRAGMCPServer(name="test")

        result = await server.mcp.call_tool(
            "scriptrag_tool_help",
            {"tool_name": "nonexistent_tool"},
        )

        data = result[1]
        assert data["success"] is False
        assert "not found" in data["error"]

    async def test_broadcast_event_without_websocket(self):
        """Test that broadcast does nothing when WebSocket is disabled."""
        server = ScriptRAGMCPServer(name="test", enable_websocket=False)

        # Should not raise error
        await server.broadcast_event("test_event", {"data": "test"})

    async def test_websocket_handler_disabled(self):
        """Test WebSocket handler when disabled."""
        server = ScriptRAGMCPServer(name="test", enable_websocket=False)

        mock_websocket = MagicMock()
        mock_websocket.send_json = AsyncMock()

        await server.handle_websocket(mock_websocket, "/")

        # Should send error message
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert "error" in call_args
        assert "not enabled" in call_args["error"]


class TestCreateEnhancedServer:
    """Test server creation factory."""

    def test_create_with_defaults(self):
        """Test creating server with default configs."""
        server = create_enhanced_server()

        assert server.mcp.name == "scriptrag"
        assert server.enable_websocket is False
        assert server.rate_limiter.config.requests_per_minute == 100
        assert server.cache.config.ttl_seconds == 600

    def test_create_with_custom_configs(self):
        """Test creating server with custom configs."""
        rate_config = RateLimitConfig(requests_per_minute=50)
        cache_config = CacheConfig(ttl_seconds=300)

        server = create_enhanced_server(
            enable_websocket=True,
            rate_limit_config=rate_config,
            cache_config=cache_config,
        )

        assert server.enable_websocket is True
        assert server.rate_limiter.config.requests_per_minute == 50
        assert server.cache.config.ttl_seconds == 300


@pytest.mark.asyncio
class TestMonitoringTools:
    """Test monitoring and stats tools."""

    async def test_mcp_stats_tool(self):
        """Test getting MCP statistics."""
        server = ScriptRAGMCPServer(name="test")

        # Make some activity
        server.metrics.record_operation("test_op", 0.5)
        server.metrics.record_cache_hit()
        server.session_manager.create_session("client1")

        # Get stats
        result = await server.mcp.call_tool("scriptrag_mcp_stats", {})

        data = result[1]
        assert data["success"] is True
        assert "performance" in data
        assert "sessions" in data
        assert "cache" in data
        assert "streaming" in data

    async def test_cache_clear_tool(self):
        """Test clearing the cache."""
        server = ScriptRAGMCPServer(name="test")

        # Add to cache
        server.cache.set("op", {}, {"data": "test"})
        assert len(server.cache.cache) == 1

        # Clear cache
        result = await server.mcp.call_tool("scriptrag_mcp_cache_clear", {})

        data = result[1]
        assert data["success"] is True
        assert len(server.cache.cache) == 0

    async def test_session_info_tool(self):
        """Test getting session information."""
        server = ScriptRAGMCPServer(name="test")

        # Create session
        session = server.session_manager.create_session("client1")
        session.query_cache["key"] = "value"

        # Get session info
        result = await server.mcp.call_tool(
            "scriptrag_mcp_session_info",
            {"client_id": "client1"},
        )

        data = result[1]
        assert data["success"] is True
        assert data["session"]["session_id"] == session.session_id
        assert data["session"]["cache_entries"] == 1
        assert "rate_limits" in data


class TestMainFunction:
    """Test the main entry point."""

    @patch("scriptrag.mcp.enhanced_server.create_enhanced_server")
    @patch("scriptrag.mcp.enhanced_server.argparse.ArgumentParser")
    def test_main_without_websocket(self, mock_parser_class, mock_create):
        """Test main function without WebSocket."""
        from scriptrag.mcp.enhanced_server import main

        # Mock arguments
        mock_args = MagicMock()
        mock_args.websocket = False
        mock_args.rate_limit = 50
        mock_args.cache_ttl = 300

        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser

        # Mock server
        mock_server = MagicMock()
        mock_create.return_value = mock_server

        # Call main
        main()

        # Verify server creation
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["enable_websocket"] is False
        assert call_kwargs["rate_limit_config"].requests_per_minute == 50
        assert call_kwargs["cache_config"].ttl_seconds == 300

        # Verify run was called
        mock_server.mcp.run.assert_called_once()

    @patch("scriptrag.mcp.enhanced_server.asyncio.run")
    @patch("scriptrag.mcp.enhanced_server.create_enhanced_server")
    @patch("scriptrag.mcp.enhanced_server.argparse.ArgumentParser")
    def test_main_with_websocket(
        self, mock_parser_class, mock_create, mock_asyncio_run
    ):
        """Test main function with WebSocket enabled."""
        from scriptrag.mcp.enhanced_server import main

        # Mock arguments
        mock_args = MagicMock()
        mock_args.websocket = True
        mock_args.ws_host = "0.0.0.0"  # noqa: S104
        mock_args.ws_port = 9000
        mock_args.rate_limit = 100
        mock_args.cache_ttl = 600

        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser

        # Mock server
        mock_server = MagicMock()
        mock_create.return_value = mock_server

        # Call main
        main()

        # Verify server creation with WebSocket
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["enable_websocket"] is True

        # Verify asyncio.run was called with WebSocket server
        mock_asyncio_run.assert_called_once()


class TestIntegrationScenarios:
    """Test integration scenarios."""

    @pytest.mark.asyncio
    async def test_caching_with_rate_limiting(self):
        """Test that caching and rate limiting work together."""
        rate_config = RateLimitConfig(requests_per_minute=3)
        cache_config = CacheConfig(ttl_seconds=300)

        server = ScriptRAGMCPServer(
            name="test",
            rate_limit_config=rate_config,
            cache_config=cache_config,
        )

        # Create a mock tool
        async def test_tool(value: int) -> dict:
            return {"success": True, "value": value}

        # Register with caching
        wrapped = server.wrap_tool_with_features(test_tool, enable_cache=True)
        server.mcp.tool()(wrapped)

        # First call - executes and caches
        result1 = await wrapped(client_id="test", value=1)
        assert result1["success"] is True

        # Second call with same params - from cache (no rate limit)
        result2 = await wrapped(client_id="test", value=1)
        assert result2["success"] is True

        # Different params - executes
        result3 = await wrapped(client_id="test", value=2)
        assert result3["success"] is True

        # Another different param - executes
        result4 = await wrapped(client_id="test", value=3)
        assert result4["success"] is True

        # Now we've hit rate limit (3 actual executions)
        result5 = await wrapped(client_id="test", value=4)
        assert result5["success"] is False
        assert "Rate limit" in result5["error"]

        # But cached value still works
        result6 = await wrapped(client_id="test", value=1)
        assert result6["success"] is True  # From cache

    @pytest.mark.asyncio
    async def test_session_persistence_across_calls(self):
        """Test that session state persists across tool calls."""
        server = ScriptRAGMCPServer(name="test")

        # First tool call creates session
        session1 = server.session_manager.get_session("client1")
        session1.context["preference"] = "dark_mode"

        # Second tool call should get same session
        session2 = server.session_manager.get_session("client1")
        assert session2.session_id == session1.session_id
        assert session2.context["preference"] == "dark_mode"
