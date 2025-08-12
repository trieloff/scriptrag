"""Unit tests for MCP server."""

import json
from unittest.mock import MagicMock, patch

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
        mock_api = MagicMock()
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
            has_more=False,
            execution_time_ms=123.0,
            search_methods=["text"],
        )
        mock_api.search.return_value = mock_response

        yield mock_api


@pytest.fixture
def mock_query_api():
    """Create a mock QueryAPI."""
    with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_class:
        mock_api = MagicMock()
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

    # The tool is registered via decorator, so we call it directly
    from scriptrag.mcp.tools.search import scriptrag_search

    # Execute the tool
    result = await scriptrag_search(
        query="test query",
        character="ALICE",
        limit=10,
        offset=0,
    )

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
    from mcp import FastMCP

    # Configure mock to raise exception
    mock_search_api.search.side_effect = Exception("Search failed")

    mcp = FastMCP("test")
    register_search_tool(mcp)

    # Get the registered tool
    tool_func = None
    for name, func in mcp._tools.items():
        if "scriptrag_search" in name:
            tool_func = func
            break

    # Execute the tool
    result = await tool_func(query="test query")

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

    # Get the registered tool
    tool_func = None
    for name, func in mcp._tools.items():
        if "scriptrag_search" in name:
            tool_func = func
            break

    # Test fuzzy and strict conflict
    result = await tool_func(
        query="test",
        fuzzy=True,
        strict=True,
    )
    assert result["success"] is False
    assert "Cannot use both fuzzy and strict" in result["error"]

    # Test bible options conflict
    result = await tool_func(
        query="test",
        include_bible=False,
        only_bible=True,
    )
    assert result["success"] is False
    assert "Cannot use both no_bible and only_bible" in result["error"]


@pytest.mark.asyncio
async def test_query_tools_registration(mock_query_api):
    """Test dynamic query tool registration."""
    from mcp.server import FastMCP

    mcp = FastMCP("test")
    register_query_tools(mcp)

    # Check that tools were registered
    tool_names = list(mcp._tools.keys())

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
    tool_func = None
    for name, func in mcp._tools.items():
        if "scriptrag_query_test_query" in name:
            tool_func = func
            break

    assert tool_func is not None

    # Execute the tool
    result = await tool_func(param1="test_value", limit=5)

    # Verify result
    assert result["success"] is True
    assert result["query"] == "test-query"
    assert "results" in result
    assert len(result["results"]) == 1
    assert result["results"][0]["name"] == "Test Result"


@pytest.mark.asyncio
async def test_query_tool_error_handling(mock_query_api):
    """Test query tool error handling."""
    from mcp import FastMCP

    # Configure mock to raise exception
    mock_query_api.execute_query.side_effect = Exception("Query failed")

    mcp = FastMCP("test")
    register_query_tools(mcp)

    # Find the test query tool
    tool_func = None
    for name, func in mcp._tools.items():
        if "scriptrag_query_test_query" in name:
            tool_func = func
            break

    # Execute the tool
    result = await tool_func(param1="test_value")

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
    tool_func = None
    for name, func in mcp._tools.items():
        if "scriptrag_query_list" in name:
            tool_func = func
            break

    assert tool_func is not None

    # Execute the tool
    result = await tool_func()

    # Verify result
    assert result["success"] is True
    assert "queries" in result
    assert len(result["queries"]) == 1
    assert result["queries"][0]["name"] == "test-query"


@pytest.mark.asyncio
async def test_no_queries_available():
    """Test behavior when no queries are available."""
    with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_class:
        mock_api = MagicMock()
        mock_class.return_value = mock_api
        mock_api.list_queries.return_value = []
        mock_api.loader.reload_queries.return_value = None

        from mcp import FastMCP

        from scriptrag.mcp.tools.query import register_query_tools

        mcp = FastMCP("test")
        register_query_tools(mcp)

        # Should only have the list tool
        tool_names = list(mcp._tools.keys())
        assert any("scriptrag_query_list" in name for name in tool_names)

        # Find the list tool
        tool_func = None
        for name, func in mcp._tools.items():
            if "scriptrag_query_list" in name:
                tool_func = func
                break

        # Execute the tool
        result = await tool_func()

        # Verify empty result
        assert result["success"] is True
        assert result["queries"] == []
        assert "No queries found" in result["message"]


def test_create_server():
    """Test server creation."""
    with patch("scriptrag.mcp.tools.search.register_search_tool") as mock_search:
        with patch("scriptrag.mcp.tools.query.register_query_tools") as mock_query:
            server = create_server()

            # Verify server was created
            assert server is not None
            assert server.name == "scriptrag-mcp"

            # Verify tools were registered
            mock_search.assert_called_once()
            mock_query.assert_called_once()


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
