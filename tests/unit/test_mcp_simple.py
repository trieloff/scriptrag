"""Simple MCP server tests."""

from unittest.mock import MagicMock, patch

import pytest

from scriptrag.mcp.server import create_server
from scriptrag.query import QuerySpec


def test_create_server():
    """Test that the MCP server can be created."""
    with patch("scriptrag.mcp.tools.search.register_search_tool") as mock_search:
        with patch("scriptrag.mcp.tools.query.register_query_tools") as mock_query:
            server = create_server()

            # Verify server was created
            assert server is not None
            assert server.name == "scriptrag"

            # Verify tools were registered
            mock_search.assert_called_once()
            mock_query.assert_called_once()


@pytest.mark.asyncio
async def test_mcp_server_tools_registered():
    """Test that tools are properly registered."""
    with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_api_class:
        # Mock the query API
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api
        mock_api.list_queries.return_value = [
            QuerySpec(
                name="test-query",
                description="Test query",
                sql="SELECT 1",
                params=[],
            )
        ]
        mock_api.loader.reload_queries.return_value = None

        # Create server
        server = create_server()

        # Check that we can list tools
        tools = await server.list_tools()
        assert tools is not None

        # Should have at least the search tool and query list tool
        tool_names = [t.name for t in tools]
        assert any("scriptrag_search" in name for name in tool_names)
        assert any("scriptrag_query_list" in name for name in tool_names)
