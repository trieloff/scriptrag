"""Unit tests for MCP server."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.mcp.server import create_server
from scriptrag.mcp.tools.query import register_query_tools
from scriptrag.mcp.tools.search import register_search_tool
from scriptrag.query import ParamSpec, QuerySpec
from scriptrag.search.models import (
    SearchMode,
    SearchQuery,
    SearchResponse,
    SearchResult,
)


@pytest.fixture
def mock_search_api():
    """Create a mock SearchAPI."""
    with patch("scriptrag.mcp.tools.search.SearchAPI") as mock_class:
        mock_api = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_class.from_config.return_value = mock_api

        # Configure search response
        query = SearchQuery(
            raw_query="test query",
            text_query="test query",
            mode=SearchMode.AUTO,
        )

        mock_response = SearchResponse(
            query=query,
            results=[
                SearchResult(
                    script_id=1,
                    script_title="Test Script",
                    script_author="Test Author",
                    scene_id=1,
                    scene_number=1,
                    scene_heading="INT. TEST LOCATION - DAY",
                    scene_location="TEST LOCATION",
                    scene_time="DAY",
                    scene_content="Test scene content",
                    season=1,
                    episode=1,
                    match_type="text",
                    relevance_score=0.95,
                    matched_text="test query",
                    character_name="ALICE",
                )
            ],
            total_count=1,
            bible_results=[],
            bible_total_count=0,
            has_more=False,
            execution_time_ms=123.0,
            search_methods=["text"],
        )
        # Use AsyncMock for async method
        mock_api.search_async = AsyncMock(return_value=mock_response)

        yield mock_api


@pytest.fixture
def mock_query_api():
    """Create a mock QueryAPI."""
    with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_class:
        mock_api = MagicMock(
            spec=[
                "content",
                "model",
                "provider",
                "usage",
                "list_queries",
                "loader",
                "execute_query",
            ]
        )
        mock_class.return_value = mock_api
        mock_class.from_config.return_value = mock_api

        # Configure query specs
        test_spec = QuerySpec(
            name="test-query",
            description="Test query",
            sql="SELECT * FROM test",
            params=[
                ParamSpec(
                    name="param1",
                    type="str",
                    required=False,
                    default="default",
                    help="Test parameter",
                )
            ],
        )

        mock_api.list_queries.return_value = [test_spec]
        mock_api.loader = MagicMock(spec=["reload_queries"])
        mock_api.loader.reload_queries.return_value = None
        mock_api.execute_query.return_value = json.dumps(
            [{"id": 1, "name": "Test Result"}]
        )

        yield mock_api


@pytest.mark.asyncio
async def test_search_tool_success(mock_search_api):
    """Test successful search tool execution."""
    from mcp.server import FastMCP

    mcp = FastMCP("test")
    register_search_tool(mcp)

    # Execute the tool via MCP protocol
    response = await mcp.call_tool(
        "scriptrag_search",
        {
            "query": "test query",
            "character": "ALICE",
            "limit": 10,
            "offset": 0,
        },
    )

    # Extract result - call_tool returns tuple (text_content_list, raw_result)
    result = response[1]  # Use the raw dictionary result

    # Verify result structure
    assert result["success"] is True
    assert result["query"]["raw_query"] == "test query"
    assert result["total_count"] == 1
    assert len(result["results"]) == 1

    # Verify result content
    first_result = result["results"][0]
    assert first_result["scene_id"] == 1
    assert first_result["script_title"] == "Test Script"
    assert first_result["character_name"] == "ALICE"
    assert first_result["scene_content"] == "Test scene content"


@pytest.mark.asyncio
async def test_search_tool_error_handling(mock_search_api):
    """Test search tool error handling."""
    from mcp.server import FastMCP

    # Configure mock to raise exception - must use AsyncMock for async method
    mock_search_api.search_async = AsyncMock(side_effect=Exception("Search failed"))

    mcp = FastMCP("test")
    register_search_tool(mcp)

    # Execute the tool via MCP protocol
    response = await mcp.call_tool("scriptrag_search", {"query": "test query"})

    # Extract result - call_tool returns tuple (text_content_list, raw_result)
    result = response[1]  # Use the raw dictionary result

    # Verify error response
    assert result["success"] is False
    assert "error" in result
    assert "Search failed" in result["error"]


@pytest.mark.asyncio
async def test_search_tool_conflicting_options():
    """Test search tool with conflicting options."""
    from mcp.server import FastMCP

    mcp = FastMCP("test")
    register_search_tool(mcp)

    # Test fuzzy and strict conflict
    response = await mcp.call_tool(
        "scriptrag_search",
        {
            "query": "test",
            "fuzzy": True,
            "strict": True,
        },
    )

    result_data = response[1]  # Use the raw dictionary result
    assert result_data["success"] is False
    assert "Cannot use both fuzzy and strict" in result_data["error"]

    # Test bible options conflict
    response = await mcp.call_tool(
        "scriptrag_search",
        {
            "query": "test",
            "include_bible": False,
            "only_bible": True,
        },
    )
    result_data = response[1]  # Use the raw dictionary result
    assert result_data["success"] is False
    assert "Cannot use both no_bible and only_bible" in result_data["error"]


@pytest.mark.asyncio
async def test_query_tools_registration(mock_query_api):
    """Test dynamic query tool registration."""
    from mcp.server import FastMCP

    mcp = FastMCP("test")
    register_query_tools(mcp)

    # Check that tools were registered
    tools = await mcp.list_tools()
    tool_names = [tool.name for tool in tools]

    # Should have the query list tool
    assert any("scriptrag_query_list" in name for name in tool_names)

    # Should have the dynamic query tool
    assert any("scriptrag_query_test_query" in name for name in tool_names)


@pytest.mark.asyncio
async def test_query_tool_execution(mock_query_api):
    """Test query tool execution."""
    from mcp.server import FastMCP

    mcp = FastMCP("test")
    register_query_tools(mcp)

    # Find the test query tool
    tools = await mcp.list_tools()
    test_tool_name = None
    for tool in tools:
        if "scriptrag_query_test_query" in tool.name:
            test_tool_name = tool.name
            break

    assert test_tool_name is not None

    # Execute the tool - query tools expect kwargs wrapper
    response = await mcp.call_tool(
        test_tool_name, {"kwargs": {"param1": "test_value", "limit": 5}}
    )

    # Extract result - call_tool returns tuple (text_content_list, raw_result)
    result = response[1]  # Use the raw dictionary result

    # Verify result
    assert result["success"] is True
    assert result["query"] == "test-query"
    assert "results" in result
    assert len(result["results"]) == 1
    assert result["results"][0]["name"] == "Test Result"


@pytest.mark.asyncio
async def test_query_tool_error_handling(mock_query_api):
    """Test query tool error handling."""
    from mcp.server import FastMCP

    # Configure mock to raise exception
    mock_query_api.execute_query.side_effect = Exception("Query failed")

    mcp = FastMCP("test")
    register_query_tools(mcp)

    # Find the test query tool
    tools = await mcp.list_tools()
    test_tool_name = None
    for tool in tools:
        if "scriptrag_query_test_query" in tool.name:
            test_tool_name = tool.name
            break

    # Execute the tool - query tools expect kwargs wrapper
    response = await mcp.call_tool(test_tool_name, {"kwargs": {"param1": "test_value"}})

    # Extract result - call_tool returns tuple (text_content_list, raw_result)
    result = response[1]  # Use the raw dictionary result

    # Verify error response
    assert result["success"] is False
    assert "error" in result
    assert "Query failed" in result["error"]


@pytest.mark.asyncio
async def test_query_list_tool(mock_query_api):
    """Test query list tool."""
    from mcp.server import FastMCP

    mcp = FastMCP("test")
    register_query_tools(mcp)

    # Find the list tool
    tools = await mcp.list_tools()
    list_tool_name = None
    for tool in tools:
        if "scriptrag_query_list" in tool.name:
            list_tool_name = tool.name
            break

    assert list_tool_name is not None

    # Execute the tool
    response = await mcp.call_tool(list_tool_name, {})

    # Extract result - call_tool returns tuple (text_content_list, raw_result)
    result = response[1]  # Use the raw dictionary result

    # Verify result
    assert result["success"] is True
    assert "queries" in result
    assert len(result["queries"]) == 1
    assert result["queries"][0]["name"] == "test-query"


@pytest.mark.asyncio
async def test_no_queries_available():
    """Test behavior when no queries are available."""
    with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_class:
        mock_api = MagicMock(
            spec=["content", "model", "provider", "usage", "list_queries", "loader"]
        )
        mock_class.return_value = mock_api
        mock_api.list_queries.return_value = []
        mock_api.loader = MagicMock(spec=["reload_queries"])
        mock_api.loader.reload_queries.return_value = None

        from mcp.server import FastMCP

        from scriptrag.mcp.tools.query import register_query_tools

        mcp = FastMCP("test")
        register_query_tools(mcp)

        # Should only have the list tool
        tools = await mcp.list_tools()
        tool_names = [tool.name for tool in tools]
        assert any("scriptrag_query_list" in name for name in tool_names)

        # Find the list tool
        list_tool_name = None
        for tool in tools:
            if "scriptrag_query_list" in tool.name:
                list_tool_name = tool.name
                break

        # Execute the tool
        response = await mcp.call_tool(list_tool_name, {})

        # Extract result - call_tool returns tuple (text_content_list, raw_result)
        result = response[1]  # Use the raw dictionary result

        # Verify empty result
        assert result["success"] is True
        assert result["queries"] == []
        assert "No queries found" in result["message"]


def test_create_server():
    """Test server creation."""
    with patch("scriptrag.mcp.tools.search.register_search_tool") as mock_search:
        with patch("scriptrag.mcp.tools.query.register_query_tools") as mock_query:
            with patch("scriptrag.mcp.tools.scene.register_scene_tools") as mock_scene:
                server = create_server()

                # Verify server was created
                assert server is not None
                assert server.name == "scriptrag"

                # Verify all tools were registered
                mock_search.assert_called_once()
                mock_query.assert_called_once()
                mock_scene.assert_called_once()


def test_utils_format_error():
    """Test error formatting utility."""
    from scriptrag.mcp.utils import format_error

    error = ValueError("Test error")
    result = format_error(error)

    assert result["success"] is False
    assert result["error"] == "Test error"
    assert result["error_type"] == "ValueError"


def test_utils_format_success():
    """Test success formatting utility."""
    from scriptrag.mcp.utils import format_success

    data = {"test": "data"}
    result = format_success(data, extra_field="extra")

    assert result["success"] is True
    assert result["data"] == data
    assert result["extra_field"] == "extra"


def test_main_function():
    """Test the main function."""
    from scriptrag.mcp.server import main

    with patch("scriptrag.mcp.server.create_server") as mock_create:
        mock_server = MagicMock(spec=["content", "model", "provider", "usage", "run"])
        mock_create.return_value = mock_server

        # Call main function
        main()

        # Verify server was created and run
        mock_create.assert_called_once()
        mock_server.run.assert_called_once()


def test_main_block_execution():
    """Test the __main__ block execution path."""
    # We can verify the module structure without executing subprocess
    # The __main__ block simply calls main(), so we test main() function exists
    import scriptrag.mcp.server

    # Verify the main function exists and is callable
    assert hasattr(scriptrag.mcp.server, "main")
    assert callable(scriptrag.mcp.server.main)

    # Verify the module can be imported successfully
    # This ensures the __main__ block structure is syntactically correct
    import importlib

    module = importlib.import_module("scriptrag.mcp.server")
    assert module is not None


@pytest.mark.asyncio
async def test_scene_tools_integration():
    """Test that scene tools are properly integrated into the server."""
    with patch("scriptrag.mcp.tools.search.register_search_tool"):
        with patch("scriptrag.mcp.tools.query.register_query_tools"):
            with patch("scriptrag.mcp.tools.scene.register_scene_tools"):
                server = create_server()

                # Verify server was created successfully
                assert server is not None
                assert server.name == "scriptrag"


def test_import_scene_tools():
    """Test that scene tools module can be imported successfully."""
    # This ensures the import path in create_server works
    from scriptrag.mcp.tools.scene import register_scene_tools

    assert callable(register_scene_tools)


def test_server_module_exports():
    """Test that server module exports the expected functions."""
    import scriptrag.mcp.server as server_module

    # Verify main exports
    assert hasattr(server_module, "create_server")
    assert hasattr(server_module, "main")
    assert callable(server_module.create_server)
    assert callable(server_module.main)
