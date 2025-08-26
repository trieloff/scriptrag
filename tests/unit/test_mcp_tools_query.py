"""Comprehensive unit tests for MCP query tools."""

import json
from unittest.mock import MagicMock, patch

import pytest
from mcp.server import FastMCP

from scriptrag.mcp.tools.query import register_query_tools
from scriptrag.query import ParamSpec, QuerySpec


class TestRegisterQueryTools:
    """Test the register_query_tools function."""

    def test_register_query_tools_with_empty_queries(self):
        """Test register_query_tools when no queries are available."""
        # Arrange
        mock_mcp = MagicMock(spec=FastMCP)
        mock_tool_decorator = MagicMock(spec=object)
        mock_mcp.tool.return_value = mock_tool_decorator

        with patch("scriptrag.mcp.tools.query.get_settings") as mock_get_settings:
            with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_query_api_class:
                mock_api = MagicMock(spec=object)
                mock_api.list_queries.return_value = []
                mock_api.loader.reload_queries.return_value = None
                mock_query_api_class.return_value = mock_api

                # Act
                register_query_tools(mock_mcp)

                # Assert
                mock_get_settings.assert_called_once()
                mock_query_api_class.assert_called_once()
                mock_api.loader.reload_queries.assert_called_once()
                mock_api.list_queries.assert_called_once()
                # Should register placeholder tool for empty queries
                mock_mcp.tool.assert_called_once()
                mock_tool_decorator.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_queries_placeholder_tool_execution(self):
        """Test execution of placeholder tool when no queries are available."""
        # Arrange
        mcp = FastMCP("test")

        with patch("scriptrag.mcp.tools.query.get_settings") as mock_get_settings:
            with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_query_api_class:
                mock_api = MagicMock(spec=object)
                mock_api.list_queries.return_value = []
                mock_api.loader.reload_queries.return_value = None
                mock_query_api_class.return_value = mock_api

                # Act
                register_query_tools(mcp)

                # Find the empty list tool
                tools = await mcp.list_tools()
                empty_tool_name = None
                for tool in tools:
                    if "scriptrag_query_list_empty" in tool.name:
                        empty_tool_name = tool.name
                        break

                assert empty_tool_name is not None

                # Execute the tool
                response = await mcp.call_tool(empty_tool_name, {"kwargs": {}})
                result = response[1]  # Get raw result

                # Assert
                assert result["success"] is True
                assert result["queries"] == []
                assert "No queries found" in result["message"]

    def test_register_query_tools_with_queries(self):
        """Test register_query_tools with available queries."""
        # Arrange
        mock_mcp = MagicMock(spec=FastMCP)
        mock_tool_decorator = MagicMock(spec=object)
        mock_mcp.tool.return_value = mock_tool_decorator

        test_spec = QuerySpec(
            name="test-query",
            description="Test query description",
            sql="SELECT * FROM test WHERE id = :param1",
            params=[
                ParamSpec(
                    name="param1",
                    type="str",
                    required=True,
                    help="Test parameter",
                )
            ],
        )

        with patch("scriptrag.mcp.tools.query.get_settings") as mock_get_settings:
            with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_query_api_class:
                mock_api = MagicMock(spec=object)
                mock_api.list_queries.return_value = [test_spec]
                mock_api.loader.reload_queries.return_value = None
                mock_query_api_class.return_value = mock_api

                # Act
                register_query_tools(mock_mcp)

                # Assert
                mock_get_settings.assert_called_once()
                mock_query_api_class.assert_called_once()
                mock_api.loader.reload_queries.assert_called_once()
                mock_api.list_queries.assert_called_once()
                # Should register 2 tools: one for the query and one for list
                assert mock_mcp.tool.call_count == 2
                assert mock_tool_decorator.call_count == 2

    @pytest.mark.asyncio
    async def test_dynamic_query_tool_successful_execution(self):
        """Test successful execution of a dynamically created query tool."""
        # Arrange
        mcp = FastMCP("test")

        test_spec = QuerySpec(
            name="test-query",
            description="Test query description",
            sql="SELECT * FROM test WHERE id = :param1",
            params=[
                ParamSpec(
                    name="param1",
                    type="str",
                    required=True,
                    help="Test parameter",
                    default="default_value",
                )
            ],
        )

        with patch("scriptrag.mcp.tools.query.get_settings") as mock_get_settings:
            with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_query_api_class:
                mock_api = MagicMock(spec=object)
                mock_api.list_queries.return_value = [test_spec]
                mock_api.loader.reload_queries.return_value = None
                mock_query_api_class.return_value = mock_api

                # Mock the execution result
                test_result = [{"id": 1, "name": "Test Result"}]
                mock_api.execute_query.return_value = json.dumps(test_result)

                # Register tools
                register_query_tools(mcp)

                # Find the test query tool
                tools = await mcp.list_tools()
                test_tool_name = None
                for tool in tools:
                    if "scriptrag_query_test_query" in tool.name:
                        test_tool_name = tool.name
                        break

                assert test_tool_name is not None

                # Execute the tool
                response = await mcp.call_tool(
                    test_tool_name,
                    {"kwargs": {"param1": "test_value", "limit": 10, "offset": 5}},
                )
                result = response[1]  # Get raw result

                # Assert
                assert result["success"] is True
                assert result["query"] == "test-query"
                assert result["results"] == test_result

                # Verify API was called with correct parameters
                # kwargs wrapper means all params go to params, limit/offset are None
                mock_api.execute_query.assert_called_once_with(
                    name="test-query",
                    params={
                        "kwargs": {"param1": "test_value", "limit": 10, "offset": 5}
                    },
                    limit=None,
                    offset=None,
                    output_json=True,
                )

    @pytest.mark.asyncio
    async def test_dynamic_query_tool_with_no_results(self):
        """Test dynamic query tool when no results are returned."""
        # Arrange
        mcp = FastMCP("test")

        test_spec = QuerySpec(
            name="empty-query",
            description="Query that returns no results",
            sql="SELECT * FROM test WHERE 1=0",
            params=[],
        )

        with patch("scriptrag.mcp.tools.query.get_settings") as mock_get_settings:
            with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_query_api_class:
                mock_api = MagicMock(spec=object)
                mock_api.list_queries.return_value = [test_spec]
                mock_api.loader.reload_queries.return_value = None
                mock_query_api_class.return_value = mock_api

                # Mock empty result
                mock_api.execute_query.return_value = None

                # Register tools
                register_query_tools(mcp)

                # Find the empty query tool
                tools = await mcp.list_tools()
                empty_tool_name = None
                for tool in tools:
                    if "scriptrag_query_empty_query" in tool.name:
                        empty_tool_name = tool.name
                        break

                assert empty_tool_name is not None

                # Execute the tool
                response = await mcp.call_tool(empty_tool_name, {"kwargs": {}})
                result = response[1]  # Get raw result

                # Assert
                assert result["success"] is True
                assert result["query"] == "empty-query"
                assert result["results"] == []
                assert "No results found" in result["message"]

    @pytest.mark.asyncio
    async def test_dynamic_query_tool_error_handling(self):
        """Test error handling in dynamically created query tools."""
        # Arrange
        mcp = FastMCP("test")

        test_spec = QuerySpec(
            name="failing-query",
            description="Query that will fail",
            sql="INVALID SQL",
            params=[],
        )

        with patch("scriptrag.mcp.tools.query.get_settings") as mock_get_settings:
            with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_query_api_class:
                mock_api = MagicMock(spec=object)
                mock_api.list_queries.return_value = [test_spec]
                mock_api.loader.reload_queries.return_value = None
                mock_query_api_class.return_value = mock_api

                # Mock execution failure
                mock_api.execute_query.side_effect = RuntimeError(
                    "SQL execution failed"
                )

                # Register tools
                register_query_tools(mcp)

                # Find the failing query tool
                tools = await mcp.list_tools()
                failing_tool_name = None
                for tool in tools:
                    if "scriptrag_query_failing_query" in tool.name:
                        failing_tool_name = tool.name
                        break

                assert failing_tool_name is not None

                # Execute the tool
                response = await mcp.call_tool(failing_tool_name, {"kwargs": {}})
                result = response[1]  # Get raw result

                # Assert
                assert result["success"] is False
                assert "error" in result
                assert "SQL execution failed" in result["error"]
                assert result["query"] == "failing-query"

    @pytest.mark.asyncio
    async def test_query_list_tool_execution(self):
        """Test execution of the query list tool."""
        # Arrange
        mcp = FastMCP("test")

        test_specs = [
            QuerySpec(
                name="query-one",
                description="First test query",
                sql="SELECT 1",
                params=[
                    ParamSpec(
                        name="param1",
                        type="str",
                        required=True,
                        help="First parameter",
                        default="default1",
                        choices=["a", "b", "c"],
                    )
                ],
            ),
            QuerySpec(
                name="query-two",
                description="Second test query",
                sql="SELECT 2",
                params=[
                    ParamSpec(
                        name="param2",
                        type="int",
                        required=False,
                        help="Second parameter",
                    )
                ],
            ),
        ]

        with patch("scriptrag.mcp.tools.query.get_settings") as mock_get_settings:
            with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_query_api_class:
                mock_api = MagicMock(spec=object)
                mock_api.list_queries.return_value = test_specs
                mock_api.loader.reload_queries.return_value = None
                mock_query_api_class.return_value = mock_api

                # Register tools
                register_query_tools(mcp)

                # Find the list tool
                tools = await mcp.list_tools()
                list_tool_name = None
                for tool in tools:
                    if "scriptrag_query_list" in tool.name and "empty" not in tool.name:
                        list_tool_name = tool.name
                        break

                assert list_tool_name is not None

                # Execute the tool
                response = await mcp.call_tool(list_tool_name, {"kwargs": {}})
                result = response[1]  # Get raw result

                # Assert
                assert result["success"] is True
                assert "queries" in result
                assert len(result["queries"]) == 2

                # Verify first query details
                query_one = result["queries"][0]
                assert query_one["name"] == "query-one"
                assert query_one["description"] == "First test query"
                assert len(query_one["params"]) == 1
                param = query_one["params"][0]
                assert param["name"] == "param1"
                assert param["type"] == "str"
                assert param["required"] is True
                assert param["help"] == "First parameter"
                assert param["default"] == "default1"
                assert param["choices"] == ["a", "b", "c"]

                # Verify second query details
                query_two = result["queries"][1]
                assert query_two["name"] == "query-two"
                assert query_two["description"] == "Second test query"
                assert len(query_two["params"]) == 1
                param = query_two["params"][0]
                assert param["name"] == "param2"
                assert param["type"] == "int"
                assert param["required"] is False
                assert param["help"] == "Second parameter"
                assert param["default"] is None
                assert param["choices"] is None

    def test_create_query_tool_name_sanitization(self):
        """Test that query tool names are properly sanitized."""
        # Arrange
        mock_mcp = MagicMock(spec=FastMCP)
        mock_tool_decorator = MagicMock(spec=object)
        mock_mcp.tool.return_value = mock_tool_decorator

        test_spec = QuerySpec(
            name="test-query-with-dashes",
            description="Test query",
            sql="SELECT 1",
            params=[],
        )

        with patch("scriptrag.mcp.tools.query.get_settings") as mock_get_settings:
            with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_query_api_class:
                mock_api = MagicMock(spec=object)
                mock_api.list_queries.return_value = [test_spec]
                mock_api.loader.reload_queries.return_value = None
                mock_query_api_class.return_value = mock_api

                # Act
                register_query_tools(mock_mcp)

                # Assert - verify that the registered function has sanitized name
                assert (
                    mock_tool_decorator.call_count == 2
                )  # One for query, one for list
                registered_functions = [
                    call[0][0] for call in mock_tool_decorator.call_args_list
                ]

                # Find the query function (not the list function)
                query_function = None
                for func in registered_functions:
                    if (
                        hasattr(func, "__name__")
                        and "test_query_with_dashes" in func.__name__
                    ):
                        query_function = func
                        break

                assert query_function is not None
                assert (
                    "scriptrag_query_test_query_with_dashes" in query_function.__name__
                )

    def test_create_query_tool_docstring_generation(self):
        """Test that query tools generate proper docstrings."""
        # Arrange
        mock_mcp = MagicMock(spec=FastMCP)
        mock_tool_decorator = MagicMock(spec=object)
        mock_mcp.tool.return_value = mock_tool_decorator

        test_spec = QuerySpec(
            name="documented-query",
            description="A well-documented query",
            sql="SELECT * FROM test WHERE id = :param1 LIMIT :limit OFFSET :offset",
            params=[
                ParamSpec(
                    name="param1",
                    type="int",
                    required=True,
                    help="The ID to search for",
                    choices=["1", "2", "3"],
                    default=1,
                )
            ],
        )

        with patch("scriptrag.mcp.tools.query.get_settings") as mock_get_settings:
            with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_query_api_class:
                mock_api = MagicMock(spec=object)
                mock_api.list_queries.return_value = [test_spec]
                mock_api.loader.reload_queries.return_value = None
                mock_query_api_class.return_value = mock_api

                # Act
                register_query_tools(mock_mcp)

                # Assert - find and verify the query function's docstring
                registered_functions = [
                    call[0][0] for call in mock_tool_decorator.call_args_list
                ]
                query_function = None
                for func in registered_functions:
                    if (
                        hasattr(func, "__name__")
                        and "documented_query" in func.__name__
                    ):
                        query_function = func
                        break

                assert query_function is not None
                docstring = query_function.__doc__
                assert docstring is not None

                # Verify docstring contains expected elements
                assert "A well-documented query" in docstring
                assert "Args:" in docstring
                assert "param1: The ID to search for" in docstring
                assert "(type: int)" in docstring
                assert "(choices: 1, 2, 3)" in docstring
                assert "(default: 1)" in docstring
                assert "limit: Maximum number of rows to return" in docstring
                assert "offset: Number of rows to skip" in docstring
                assert "Returns:" in docstring
                assert "Dictionary containing query results" in docstring

    @pytest.mark.asyncio
    async def test_query_tool_parameter_extraction(self):
        """Test that query tools properly extract and handle parameters."""
        # Arrange
        mcp = FastMCP("test")

        test_spec = QuerySpec(
            name="param-test",
            description="Parameter extraction test",
            sql="SELECT * FROM test LIMIT :limit OFFSET :offset",
            params=[],
        )

        with patch("scriptrag.mcp.tools.query.get_settings") as mock_get_settings:
            with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_query_api_class:
                mock_api = MagicMock(spec=object)
                mock_api.list_queries.return_value = [test_spec]
                mock_api.loader.reload_queries.return_value = None
                mock_query_api_class.return_value = mock_api
                mock_api.execute_query.return_value = json.dumps([{"count": 5}])

                # Register tools
                register_query_tools(mcp)

                # Find the test tool
                tools = await mcp.list_tools()
                test_tool_name = None
                for tool in tools:
                    if "scriptrag_query_param_test" in tool.name:
                        test_tool_name = tool.name
                        break

                assert test_tool_name is not None

                # Execute with mixed parameters
                response = await mcp.call_tool(
                    test_tool_name,
                    {
                        "kwargs": {
                            "limit": 10,  # Should be extracted
                            "offset": 20,  # Should be extracted
                            "other_param": "value",  # Should go to params
                            "another": 123,  # Should go to params
                        }
                    },
                )
                result = response[1]  # Get raw result

                # Assert
                assert result["success"] is True

                # Verify API was called with correct parameter separation
                # kwargs wrapper means all params go to params, limit/offset are None
                mock_api.execute_query.assert_called_once_with(
                    name="param-test",
                    params={
                        "kwargs": {
                            "limit": 10,
                            "offset": 20,
                            "other_param": "value",
                            "another": 123,
                        }
                    },
                    limit=None,
                    offset=None,
                    output_json=True,
                )

    @pytest.mark.asyncio
    async def test_query_tool_json_parsing_error(self):
        """Test query tool handling of JSON parsing errors."""
        # Arrange
        mcp = FastMCP("test")

        test_spec = QuerySpec(
            name="json-error",
            description="Query with JSON error",
            sql="SELECT 1",
            params=[],
        )

        with patch("scriptrag.mcp.tools.query.get_settings") as mock_get_settings:
            with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_query_api_class:
                mock_api = MagicMock(spec=object)
                mock_api.list_queries.return_value = [test_spec]
                mock_api.loader.reload_queries.return_value = None
                mock_query_api_class.return_value = mock_api

                # Return invalid JSON
                mock_api.execute_query.return_value = "invalid json {{"

                # Register tools
                register_query_tools(mcp)

                # Find the test tool
                tools = await mcp.list_tools()
                test_tool_name = None
                for tool in tools:
                    if "scriptrag_query_json_error" in tool.name:
                        test_tool_name = tool.name
                        break

                assert test_tool_name is not None

                # Execute the tool
                response = await mcp.call_tool(test_tool_name, {"kwargs": {}})
                result = response[1]  # Get raw result

                # Assert - should handle JSON error gracefully
                assert result["success"] is False
                assert "error" in result
                assert result["query"] == "json-error"

    def test_register_query_tools_api_initialization_error(self):
        """Test register_query_tools when API initialization fails."""
        # Arrange
        mock_mcp = MagicMock(spec=FastMCP)

        with patch("scriptrag.mcp.tools.query.get_settings") as mock_get_settings:
            mock_get_settings.side_effect = RuntimeError("Settings error")

            # Act & Assert
            with pytest.raises(RuntimeError, match="Settings error"):
                register_query_tools(mock_mcp)

    def test_register_query_tools_loader_reload_error(self):
        """Test register_query_tools when loader reload fails."""
        # Arrange
        mock_mcp = MagicMock(spec=FastMCP)

        with patch("scriptrag.mcp.tools.query.get_settings") as mock_get_settings:
            with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_query_api_class:
                mock_api = MagicMock(spec=object)
                mock_api.loader.reload_queries.side_effect = RuntimeError(
                    "Reload error"
                )
                mock_query_api_class.return_value = mock_api

                # Act & Assert
                with pytest.raises(RuntimeError, match="Reload error"):
                    register_query_tools(mock_mcp)

    def test_register_query_tools_list_queries_error(self):
        """Test register_query_tools when list_queries fails."""
        # Arrange
        mock_mcp = MagicMock(spec=FastMCP)

        with patch("scriptrag.mcp.tools.query.get_settings") as mock_get_settings:
            with patch("scriptrag.mcp.tools.query.QueryAPI") as mock_query_api_class:
                mock_api = MagicMock(spec=object)
                mock_api.loader.reload_queries.return_value = None
                mock_api.list_queries.side_effect = RuntimeError("List error")
                mock_query_api_class.return_value = mock_api

                # Act & Assert
                with pytest.raises(RuntimeError, match="List error"):
                    register_query_tools(mock_mcp)
