"""Comprehensive unit tests for MCP search tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server import FastMCP

from scriptrag.mcp.tools.search import register_search_tool
from scriptrag.search.models import (
    BibleSearchResult,
    SearchMode,
    SearchQuery,
    SearchResponse,
    SearchResult,
)


class TestRegisterSearchTool:
    """Test the register_search_tool function."""

    def test_register_search_tool_registration(self):
        """Test that register_search_tool registers the search tool."""
        # Arrange
        mock_mcp = MagicMock(spec=FastMCP)
        mock_tool_decorator = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_mcp.tool.return_value = mock_tool_decorator

        # Act
        register_search_tool(mock_mcp)

        # Assert
        mock_mcp.tool.assert_called_once()
        mock_tool_decorator.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_tool_successful_execution(self):
        """Test successful execution of the search tool."""
        # Arrange
        mcp = FastMCP("test")

        # Mock search response
        query = SearchQuery(
            raw_query="test query",
            text_query="test query",
            mode=SearchMode.AUTO,
        )

        search_result = SearchResult(
            script_id=1,
            script_title="Test Script",
            script_author="Test Author",
            scene_id=101,
            scene_number=5,
            scene_heading="INT. TEST ROOM - DAY",
            scene_location="TEST ROOM",
            scene_time="DAY",
            scene_content="This is test scene content.",
            season=1,
            episode=2,
            match_type="text",
            relevance_score=0.85,
            matched_text="test query",
            character_name="ALICE",
        )

        bible_result = BibleSearchResult(
            script_id=1,
            script_title="Test Script",
            bible_id=201,
            bible_title="Test Bible",
            chunk_id=301,
            chunk_heading="Test Chapter",
            chunk_level=2,
            chunk_content="This is test bible content.",
            match_type="text",
            relevance_score=0.75,
            matched_text="test query",
        )

        mock_response = SearchResponse(
            query=query,
            results=[search_result],
            total_count=1,
            bible_results=[bible_result],
            bible_total_count=1,
            has_more=False,
            execution_time_ms=123.45,
            search_methods=["text", "vector"],
        )

        with patch("scriptrag.mcp.tools.search.SearchAPI") as mock_search_api_class:
            mock_api = MagicMock(spec=["content", "model", "provider", "usage"])
            mock_api.search_async = AsyncMock(return_value=mock_response)
            mock_search_api_class.from_config.return_value = mock_api

            # Register the search tool
            register_search_tool(mcp)

            # Find the search tool
            tools = await mcp.list_tools()
            search_tool_name = None
            for tool in tools:
                if "scriptrag_search" in tool.name:
                    search_tool_name = tool.name
                    break

            assert search_tool_name is not None

            # Execute the tool
            response = await mcp.call_tool(
                search_tool_name,
                {
                    "query": "test query",
                    "character": "ALICE",
                    "limit": 10,
                    "offset": 0,
                    "fuzzy": True,
                },
            )

            result = response[1]  # Get raw result

            # Assert
            assert result["success"] is True
            assert result["query"]["raw_query"] == "test query"
            assert result["query"]["text_query"] == "test query"
            assert result["query"]["mode"] == "auto"
            assert result["total_count"] == 1
            assert result["bible_total_count"] == 1
            assert result["has_more"] is False
            assert result["execution_time_ms"] == 123.45
            assert result["search_methods"] == ["text", "vector"]

            # Verify scene result
            assert len(result["results"]) == 1
            scene = result["results"][0]
            assert scene["script_id"] == 1
            assert scene["script_title"] == "Test Script"
            assert scene["script_author"] == "Test Author"
            assert scene["scene_id"] == 101
            assert scene["scene_number"] == 5
            assert scene["scene_heading"] == "INT. TEST ROOM - DAY"
            assert scene["scene_location"] == "TEST ROOM"
            assert scene["scene_time"] == "DAY"
            assert scene["scene_content"] == "This is test scene content."
            assert scene["season"] == 1
            assert scene["episode"] == 2
            assert scene["match_type"] == "text"
            assert scene["relevance_score"] == 0.85
            assert scene["matched_text"] == "test query"
            assert scene["character_name"] == "ALICE"

            # Verify bible result
            assert len(result["bible_results"]) == 1
            bible = result["bible_results"][0]
            assert bible["script_id"] == 1
            assert bible["script_title"] == "Test Script"
            assert bible["bible_id"] == 201
            assert bible["bible_title"] == "Test Bible"
            assert bible["chunk_id"] == 301
            assert bible["chunk_heading"] == "Test Chapter"
            assert bible["chunk_level"] == 2
            assert bible["chunk_content"] == "This is test bible content."
            assert bible["match_type"] == "text"
            assert bible["relevance_score"] == 0.75
            assert bible["matched_text"] == "test query"

            # Verify API was called correctly
            mock_api.search_async.assert_called_once_with(
                query="test query",
                character="ALICE",
                dialogue=None,
                parenthetical=None,
                project=None,
                range_str=None,
                fuzzy=True,
                strict=False,
                limit=10,
                offset=0,
                include_bible=True,
                only_bible=False,
            )

    @pytest.mark.asyncio
    async def test_search_tool_with_all_parameters(self):
        """Test search tool with all possible parameters."""
        # Arrange
        mcp = FastMCP("test")

        query = SearchQuery(
            raw_query="comprehensive test",
            text_query="comprehensive test",
            mode=SearchMode.STRICT,
        )

        mock_response = SearchResponse(
            query=query,
            results=[],
            total_count=0,
            bible_results=[],
            bible_total_count=0,
            has_more=False,
            execution_time_ms=50.0,
            search_methods=["text"],
        )

        with patch("scriptrag.mcp.tools.search.SearchAPI") as mock_search_api_class:
            mock_api = MagicMock(spec=["content", "model", "provider", "usage"])
            mock_api.search_async = AsyncMock(return_value=mock_response)
            mock_search_api_class.from_config.return_value = mock_api

            # Register the search tool
            register_search_tool(mcp)

            # Find the search tool
            tools = await mcp.list_tools()
            search_tool_name = None
            for tool in tools:
                if "scriptrag_search" in tool.name:
                    search_tool_name = tool.name
                    break

            # Execute with all parameters
            response = await mcp.call_tool(
                search_tool_name,
                {
                    "query": "comprehensive test",
                    "character": "BOB",
                    "dialogue": "Hello world",
                    "parenthetical": "(whispering)",
                    "location": "OFFICE",
                    "project": "Test Project",
                    "scene_range": "s1e1-s1e5",
                    "fuzzy": False,
                    "strict": True,
                    "limit": 25,
                    "offset": 10,
                    "include_bible": False,
                    "only_bible": False,
                },
            )

            result = response[1]

            # Assert
            assert result["success"] is True
            assert result["total_count"] == 0
            assert result["results"] == []
            assert result["bible_results"] == []

            # Verify API was called with all parameters
            mock_api.search_async.assert_called_once_with(
                query="comprehensive test",
                character="BOB",
                dialogue="Hello world",
                parenthetical="(whispering)",
                project="Test Project",
                range_str="s1e1-s1e5",
                fuzzy=False,
                strict=True,
                limit=25,
                offset=10,
                include_bible=False,
                only_bible=False,
            )

    @pytest.mark.asyncio
    async def test_search_tool_conflicting_fuzzy_strict_options(self):
        """Test search tool validation of conflicting fuzzy/strict options."""
        # Arrange
        mcp = FastMCP("test")
        register_search_tool(mcp)

        # Find the search tool
        tools = await mcp.list_tools()
        search_tool_name = None
        for tool in tools:
            if "scriptrag_search" in tool.name:
                search_tool_name = tool.name
                break

        # Execute with conflicting options
        response = await mcp.call_tool(
            search_tool_name,
            {
                "query": "test",
                "fuzzy": True,
                "strict": True,
            },
        )

        result = response[1]

        # Assert
        assert result["success"] is False
        assert "Cannot use both fuzzy and strict" in result["error"]

    @pytest.mark.asyncio
    async def test_search_tool_conflicting_bible_options(self):
        """Test search tool validation of conflicting bible options."""
        # Arrange
        mcp = FastMCP("test")
        register_search_tool(mcp)

        # Find the search tool
        tools = await mcp.list_tools()
        search_tool_name = None
        for tool in tools:
            if "scriptrag_search" in tool.name:
                search_tool_name = tool.name
                break

        # Execute with conflicting options
        response = await mcp.call_tool(
            search_tool_name,
            {
                "query": "test",
                "include_bible": False,
                "only_bible": True,
            },
        )

        result = response[1]

        # Assert
        assert result["success"] is False
        assert "Cannot use both no_bible and only_bible" in result["error"]

    @pytest.mark.asyncio
    async def test_search_tool_error_handling(self):
        """Test search tool error handling when SearchAPI fails."""
        # Arrange
        mcp = FastMCP("test")

        with patch("scriptrag.mcp.tools.search.SearchAPI") as mock_search_api_class:
            mock_api = MagicMock(spec=["content", "model", "provider", "usage"])
            mock_api.search_async = AsyncMock(
                side_effect=RuntimeError("Search engine failed")
            )
            mock_search_api_class.from_config.return_value = mock_api

            # Register the search tool
            register_search_tool(mcp)

            # Find the search tool
            tools = await mcp.list_tools()
            search_tool_name = None
            for tool in tools:
                if "scriptrag_search" in tool.name:
                    search_tool_name = tool.name
                    break

            # Execute the tool
            response = await mcp.call_tool(search_tool_name, {"query": "test query"})

            result = response[1]

            # Assert
            assert result["success"] is False
            assert "error" in result
            assert "Search engine failed" in result["error"]

    @pytest.mark.asyncio
    async def test_search_tool_with_optional_fields_missing(self):
        """Test search tool with search results missing optional fields."""
        # Arrange
        mcp = FastMCP("test")

        query = SearchQuery(
            raw_query="minimal test",
            text_query="minimal test",
            mode=SearchMode.AUTO,
        )

        # Create result without optional fields
        search_result = SearchResult(
            script_id=1,
            script_title="Test Script",
            script_author="Test Author",
            scene_id=101,
            scene_number=5,
            scene_heading="INT. TEST ROOM - DAY",
            scene_location="TEST ROOM",
            scene_time="DAY",
            scene_content="This is test scene content.",
            season=1,
            episode=2,
            match_type="text",
            relevance_score=0.85,
            matched_text=None,  # Optional field
            character_name=None,  # Optional field
        )

        bible_result = BibleSearchResult(
            script_id=1,
            script_title="Test Script",
            bible_id=201,
            bible_title="Test Bible",
            chunk_id=301,
            chunk_heading="Test Chapter",
            chunk_level=2,
            chunk_content="This is test bible content.",
            match_type="text",
            relevance_score=0.75,
            matched_text=None,  # Optional field
        )

        mock_response = SearchResponse(
            query=query,
            results=[search_result],
            total_count=1,
            bible_results=[bible_result],
            bible_total_count=1,
            has_more=False,
            execution_time_ms=123.45,
            search_methods=["text"],
        )

        with patch("scriptrag.mcp.tools.search.SearchAPI") as mock_search_api_class:
            mock_api = MagicMock(spec=["content", "model", "provider", "usage"])
            mock_api.search_async = AsyncMock(return_value=mock_response)
            mock_search_api_class.from_config.return_value = mock_api

            # Register the search tool
            register_search_tool(mcp)

            # Find the search tool
            tools = await mcp.list_tools()
            search_tool_name = None
            for tool in tools:
                if "scriptrag_search" in tool.name:
                    search_tool_name = tool.name
                    break

            # Execute the tool
            response = await mcp.call_tool(search_tool_name, {"query": "minimal test"})

            result = response[1]

            # Assert
            assert result["success"] is True
            assert len(result["results"]) == 1
            assert len(result["bible_results"]) == 1

            # Verify scene result without optional fields
            scene = result["results"][0]
            assert "matched_text" not in scene  # Should not be included
            assert "character_name" not in scene  # Should not be included
            assert scene["scene_id"] == 101  # Required fields still present

            # Verify bible result without optional fields
            bible = result["bible_results"][0]
            assert "matched_text" not in bible  # Should not be included
            assert bible["bible_id"] == 201  # Required fields still present

    @pytest.mark.asyncio
    async def test_search_tool_with_optional_fields_present(self):
        """Test search tool with search results containing optional fields."""
        # Arrange
        mcp = FastMCP("test")

        query = SearchQuery(
            raw_query="complete test",
            text_query="complete test",
            mode=SearchMode.AUTO,
        )

        # Create result with optional fields
        search_result = SearchResult(
            script_id=1,
            script_title="Test Script",
            script_author="Test Author",
            scene_id=101,
            scene_number=5,
            scene_heading="INT. TEST ROOM - DAY",
            scene_location="TEST ROOM",
            scene_time="DAY",
            scene_content="This is test scene content.",
            season=1,
            episode=2,
            match_type="text",
            relevance_score=0.85,
            matched_text="highlighted text",  # Optional field
            character_name="CHARLIE",  # Optional field
        )

        bible_result = BibleSearchResult(
            script_id=1,
            script_title="Test Script",
            bible_id=201,
            bible_title="Test Bible",
            chunk_id=301,
            chunk_heading="Test Chapter",
            chunk_level=2,
            chunk_content="This is test bible content.",
            match_type="text",
            relevance_score=0.75,
            matched_text="bible highlight",  # Optional field
        )

        mock_response = SearchResponse(
            query=query,
            results=[search_result],
            total_count=1,
            bible_results=[bible_result],
            bible_total_count=1,
            has_more=False,
            execution_time_ms=123.45,
            search_methods=["text"],
        )

        with patch("scriptrag.mcp.tools.search.SearchAPI") as mock_search_api_class:
            mock_api = MagicMock(spec=["content", "model", "provider", "usage"])
            mock_api.search_async = AsyncMock(return_value=mock_response)
            mock_search_api_class.from_config.return_value = mock_api

            # Register the search tool
            register_search_tool(mcp)

            # Find the search tool
            tools = await mcp.list_tools()
            search_tool_name = None
            for tool in tools:
                if "scriptrag_search" in tool.name:
                    search_tool_name = tool.name
                    break

            # Execute the tool
            response = await mcp.call_tool(search_tool_name, {"query": "complete test"})

            result = response[1]

            # Assert
            assert result["success"] is True
            assert len(result["results"]) == 1
            assert len(result["bible_results"]) == 1

            # Verify scene result with optional fields
            scene = result["results"][0]
            assert scene["matched_text"] == "highlighted text"  # Should be included
            assert scene["character_name"] == "CHARLIE"  # Should be included
            assert scene["scene_id"] == 101  # Required fields still present

            # Verify bible result with optional fields
            bible = result["bible_results"][0]
            assert bible["matched_text"] == "bible highlight"  # Should be included
            assert bible["bible_id"] == 201  # Required fields still present

    @pytest.mark.asyncio
    async def test_search_tool_empty_results(self):
        """Test search tool with empty results."""
        # Arrange
        mcp = FastMCP("test")

        query = SearchQuery(
            raw_query="empty test",
            text_query="empty test",
            mode=SearchMode.AUTO,
        )

        mock_response = SearchResponse(
            query=query,
            results=[],
            total_count=0,
            bible_results=[],
            bible_total_count=0,
            has_more=False,
            execution_time_ms=10.0,
            search_methods=["text"],
        )

        with patch("scriptrag.mcp.tools.search.SearchAPI") as mock_search_api_class:
            mock_api = MagicMock(spec=["content", "model", "provider", "usage"])
            mock_api.search_async = AsyncMock(return_value=mock_response)
            mock_search_api_class.from_config.return_value = mock_api

            # Register the search tool
            register_search_tool(mcp)

            # Find the search tool
            tools = await mcp.list_tools()
            search_tool_name = None
            for tool in tools:
                if "scriptrag_search" in tool.name:
                    search_tool_name = tool.name
                    break

            # Execute the tool
            response = await mcp.call_tool(search_tool_name, {"query": "empty test"})

            result = response[1]

            # Assert
            assert result["success"] is True
            assert result["total_count"] == 0
            assert result["bible_total_count"] == 0
            assert result["results"] == []
            assert result["bible_results"] == []
            assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_search_tool_api_initialization_error(self):
        """Test search tool when SearchAPI initialization fails."""
        # Arrange
        mcp = FastMCP("test")

        with patch("scriptrag.mcp.tools.search.SearchAPI") as mock_search_api_class:
            mock_search_api_class.from_config.side_effect = RuntimeError(
                "API init failed"
            )

            # Register the search tool
            register_search_tool(mcp)

            # Find the search tool
            tools = await mcp.list_tools()
            search_tool_name = None
            for tool in tools:
                if "scriptrag_search" in tool.name:
                    search_tool_name = tool.name
                    break

            # Execute the tool
            response = await mcp.call_tool(search_tool_name, {"query": "test"})

            result = response[1]

            # Assert
            assert result["success"] is False
            assert "API init failed" in result["error"]

    @pytest.mark.parametrize(
        "params,expected_error",
        [
            # Fuzzy and strict conflict
            (
                {"query": "test", "fuzzy": True, "strict": True},
                "Cannot use both fuzzy and strict",
            ),
            # Bible options conflict
            (
                {"query": "test", "include_bible": False, "only_bible": True},
                "Cannot use both no_bible and only_bible",
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_search_tool_parameter_validation(self, params, expected_error):
        """Test search tool parameter validation with various invalid combinations."""
        # Arrange
        mcp = FastMCP("test")
        register_search_tool(mcp)

        # Find the search tool
        tools = await mcp.list_tools()
        search_tool_name = None
        for tool in tools:
            if "scriptrag_search" in tool.name:
                search_tool_name = tool.name
                break

        # Execute with invalid parameters
        response = await mcp.call_tool(search_tool_name, params)
        result = response[1]

        # Assert
        assert result["success"] is False
        assert expected_error in result["error"]

    @pytest.mark.asyncio
    async def test_search_tool_default_parameters(self):
        """Test search tool with default parameter values."""
        # Arrange
        mcp = FastMCP("test")

        query = SearchQuery(
            raw_query="default test",
            text_query="default test",
            mode=SearchMode.AUTO,
        )

        mock_response = SearchResponse(
            query=query,
            results=[],
            total_count=0,
            bible_results=[],
            bible_total_count=0,
            has_more=False,
            execution_time_ms=15.0,
            search_methods=["text"],
        )

        with patch("scriptrag.mcp.tools.search.SearchAPI") as mock_search_api_class:
            mock_api = MagicMock(spec=["content", "model", "provider", "usage"])
            mock_api.search_async = AsyncMock(return_value=mock_response)
            mock_search_api_class.from_config.return_value = mock_api

            # Register the search tool
            register_search_tool(mcp)

            # Find the search tool
            tools = await mcp.list_tools()
            search_tool_name = None
            for tool in tools:
                if "scriptrag_search" in tool.name:
                    search_tool_name = tool.name
                    break

            # Execute with minimal parameters (testing defaults)
            response = await mcp.call_tool(search_tool_name, {"query": "default test"})

            result = response[1]

            # Assert
            assert result["success"] is True

            # Verify API was called with default values
            mock_api.search_async.assert_called_once_with(
                query="default test",
                character=None,  # Default
                dialogue=None,  # Default
                parenthetical=None,  # Default
                project=None,  # Default
                range_str=None,  # Default
                fuzzy=False,  # Default
                strict=False,  # Default
                limit=5,  # Default
                offset=0,  # Default
                include_bible=True,  # Default
                only_bible=False,  # Default
            )
