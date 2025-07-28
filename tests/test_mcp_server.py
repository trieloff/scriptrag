"""Tests for the MCP server implementation."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import mcp.types as types
import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.mcp_server import ScriptRAGMCPServer
from scriptrag.models import Script


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=ScriptRAGSettings)
    mcp_settings = MagicMock()
    mcp_settings.host = "localhost"
    mcp_settings.port = 8080
    mcp_settings.max_resources = 1000
    mcp_settings.enable_all_tools = True
    settings.mcp = mcp_settings
    return settings


@pytest.fixture
def mcp_server(mock_settings):
    """Create MCP server instance for testing."""
    with patch("scriptrag.mcp_server.ScriptRAG"):
        return ScriptRAGMCPServer(mock_settings)


class TestScriptRAGMCPServer:
    """Test ScriptRAGMCPServer class."""

    def test_initialization(self, mock_settings):
        """Test server initialization."""
        with patch("scriptrag.mcp_server.ScriptRAG") as mock_scriptrag:
            server = ScriptRAGMCPServer(mock_settings)

            assert server.config == mock_settings
            assert server.scriptrag is not None
            assert server.server is not None
            assert server._scripts_cache == {}
            mock_scriptrag.assert_called_once_with(config=mock_settings)

    def test_get_available_tools_all_enabled(self, mcp_server):
        """Test getting available tools when all are enabled."""
        tools = mcp_server.get_available_tools()

        assert len(tools) == 23  # 11 original + 5 mentor tools + 7 bible tools
        tool_names = [t["name"] for t in tools]
        assert "parse_script" in tool_names
        assert "search_scenes" in tool_names
        assert "get_character_info" in tool_names
        assert "analyze_timeline" in tool_names
        assert "list_scripts" in tool_names

    def test_get_available_tools_filtered(self, mcp_server):
        """Test getting available tools with filtering."""
        mcp_server.config.mcp.enable_all_tools = False
        mcp_server.config.mcp.enabled_tools = ["parse_script", "search_scenes"]

        tools = mcp_server.get_available_tools()

        assert len(tools) == 2
        tool_names = [t["name"] for t in tools]
        assert "parse_script" in tool_names
        assert "search_scenes" in tool_names

    def test_get_available_resources(self, mcp_server):
        """Test getting available resources."""
        resources = mcp_server.get_available_resources()

        assert len(resources) == 5
        assert resources[0]["uri"] == "screenplay://list"
        assert resources[1]["uri"] == "screenplay://{script_id}"
        assert resources[2]["uri"] == "scene://{script_id}/{scene_id}"
        assert resources[3]["uri"] == "character://{script_id}/{character_name}"
        assert resources[4]["uri"] == "timeline://{script_id}"

    @pytest.mark.asyncio
    async def test_handle_list_tools(self, mcp_server):
        """Test handling list tools request."""
        request = types.ListToolsRequest(method="tools/list")
        result = await mcp_server._handle_list_tools(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.ListToolsResult)
        assert (
            len(result.root.tools) == 23
        )  # 11 original + 5 mentor tools + 7 bible tools
        assert all(isinstance(tool, types.Tool) for tool in result.root.tools)

    @pytest.mark.asyncio
    async def test_tool_parse_script(self, mcp_server, tmp_path):
        """Test parse script tool."""
        # Create a temporary fountain file
        test_file = tmp_path / "test.fountain"
        test_file.write_text(
            "Title: Test Script\n\nFADE IN:\n\n"
            "INT. ROOM - DAY\n\nTest scene.\n\nFADE OUT."
        )

        # Mock the scriptrag.parse_fountain method
        mock_script = Script(title="Test Script", source_file=str(test_file))
        mcp_server.scriptrag.parse_fountain = MagicMock(return_value=mock_script)

        args = {"path": str(test_file), "title": "Override Title"}
        result = await mcp_server._tool_parse_script(args)

        assert result["title"] == "Override Title"
        assert result["source_file"] == str(test_file)
        assert len(mcp_server._scripts_cache) == 1
        # Check that a script was added to cache
        script_id = next(iter(mcp_server._scripts_cache.keys()))
        assert script_id.startswith("script_")
        assert result["script_id"] == script_id

        mcp_server.scriptrag.parse_fountain.assert_called_once_with(str(test_file))

    @pytest.mark.asyncio
    async def test_tool_parse_script_no_path(self, mcp_server):
        """Test parse script tool without path."""
        with pytest.raises(ValueError, match="path is required"):
            await mcp_server._tool_parse_script({})

    @pytest.mark.asyncio
    async def test_tool_search_scenes(self, mcp_server):
        """Test search scenes tool."""
        # Add a script to cache first
        script = Script(title="Test Script", source_file="test.fountain")
        mcp_server._scripts_cache["script_0"] = script

        args = {
            "script_id": "script_0",
            "query": "coffee",
            "location": "INT. CAFE",
            "characters": ["JOHN", "MARY"],
            "limit": 5,
        }

        result = await mcp_server._tool_search_scenes(args)

        assert result["script_id"] == "script_0"
        assert result["results"] == []
        assert result["total_matches"] == 0
        assert result["search_criteria"]["query"] == "coffee"
        assert result["search_criteria"]["location"] == "INT. CAFE"
        assert result["search_criteria"]["characters"] == ["JOHN", "MARY"]

    @pytest.mark.asyncio
    async def test_tool_search_scenes_no_script_id(self, mcp_server):
        """Test search scenes tool without script_id."""
        with pytest.raises(ValueError, match="script_id is required"):
            await mcp_server._tool_search_scenes({})

    @pytest.mark.asyncio
    async def test_tool_get_character_info(self, mcp_server):
        """Test get character info tool."""
        # Add a script to cache first
        script = Script(title="Test Script", source_file="test.fountain")
        mcp_server._scripts_cache["script_0"] = script

        args = {"script_id": "script_0", "character_name": "JOHN"}

        result = await mcp_server._tool_get_character_info(args)

        assert result["script_id"] == "script_0"
        assert result["character_name"] == "JOHN"
        assert result["scenes_count"] == 0
        assert result["dialogue_lines"] == 0
        assert result["relationships"] == []

    @pytest.mark.asyncio
    async def test_tool_analyze_timeline(self, mcp_server):
        """Test analyze timeline tool."""
        # Add a script to cache first
        script = Script(title="Test Script", source_file="test.fountain")
        mcp_server._scripts_cache["script_0"] = script

        args = {"script_id": "script_0", "include_flashbacks": False}

        result = await mcp_server._tool_analyze_timeline(args)

        assert result["script_id"] == "script_0"
        assert result["timeline_type"] == "linear"
        assert result["flashbacks_detected"] is None
        assert result["time_periods"] == []

    @pytest.mark.asyncio
    async def test_tool_list_scripts(self, mcp_server):
        """Test list scripts tool."""
        # Add some scripts to cache
        script1 = Script(title="Script 1", source_file="script1.fountain")
        script2 = Script(title="Script 2", source_file="script2.fountain")
        mcp_server._scripts_cache = {"script_0": script1, "script_1": script2}

        result = await mcp_server._tool_list_scripts({})

        assert result["total"] == 2
        assert len(result["scripts"]) == 2
        assert result["scripts"][0]["script_id"] == "script_0"
        assert result["scripts"][0]["title"] == "Script 1"
        assert result["scripts"][1]["script_id"] == "script_1"
        assert result["scripts"][1]["title"] == "Script 2"

    @pytest.mark.asyncio
    async def test_handle_tool_call_success(self, mcp_server):
        """Test handling successful tool call."""
        # Mock parse_script tool
        mcp_server._tool_parse_script = AsyncMock(return_value={"script_id": "test"})

        request = types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="parse_script", arguments={"path": "/test.fountain"}
            ),
        )

        result = await mcp_server._handle_tool_call(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.CallToolResult)
        assert not result.root.isError
        assert len(result.root.content) == 1
        assert isinstance(result.root.content[0], types.TextContent)
        assert "script_id" in result.root.content[0].text

    @pytest.mark.asyncio
    async def test_handle_tool_call_unknown_tool(self, mcp_server):
        """Test handling unknown tool call."""
        request = types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(name="unknown_tool", arguments={}),
        )

        result = await mcp_server._handle_tool_call(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.CallToolResult)
        assert result.root.isError
        assert "Unknown tool" in result.root.content[0].text

    @pytest.mark.asyncio
    async def test_handle_list_resources(self, mcp_server):
        """Test handling list resources request."""
        # Add a script to cache
        script = Script(title="Test Script", source_file="test.fountain")
        mcp_server._scripts_cache = {"script_0": script}

        request = types.ListResourcesRequest(method="resources/list")
        result = await mcp_server._handle_list_resources(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.ListResourcesResult)
        assert len(result.root.resources) == 2
        assert str(result.root.resources[0].uri) == "screenplay://list"
        assert str(result.root.resources[1].uri) == "screenplay://script_0"
        assert "Test Script" in result.root.resources[1].name

    @pytest.mark.asyncio
    async def test_handle_read_resource_list(self, mcp_server):
        """Test reading screenplay list resource."""
        # Add scripts to cache
        script1 = Script(title="Script 1", source_file="script1.fountain")
        mcp_server._scripts_cache = {"script_0": script1}

        request = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(
                uri=types.AnyUrl("screenplay://list")
            ),
        )

        result = await mcp_server._handle_read_resource(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.ReadResourceResult)
        assert len(result.root.contents) == 1
        content = json.loads(result.root.contents[0].text)
        assert len(content["scripts"]) == 1
        assert content["scripts"][0]["script_id"] == "script_0"

    @pytest.mark.asyncio
    async def test_handle_read_resource_script(self, mcp_server):
        """Test reading specific script resource."""
        script = Script(title="Test Script", source_file="test.fountain")
        mcp_server._scripts_cache = {"script_0": script}

        request = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(
                uri=types.AnyUrl("screenplay://script_0")
            ),
        )

        result = await mcp_server._handle_read_resource(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.ReadResourceResult)
        content = json.loads(result.root.contents[0].text)
        assert content["script_id"] == "script_0"
        assert content["title"] == "Test Script"

    @pytest.mark.asyncio
    async def test_handle_read_resource_unknown(self, mcp_server):
        """Test reading unknown resource."""
        request = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(
                uri=types.AnyUrl("unknown://resource")
            ),
        )

        with pytest.raises(ValueError, match="Unknown resource URI"):
            await mcp_server._handle_read_resource(request)

    @pytest.mark.asyncio
    async def test_handle_list_prompts(self, mcp_server):
        """Test handling list prompts request."""
        request = types.ListPromptsRequest(method="prompts/list")
        result = await mcp_server._handle_list_prompts(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.ListPromptsResult)
        assert len(result.root.prompts) == 3
        prompt_names = [p.name for p in result.root.prompts]
        assert "analyze_script_structure" in prompt_names
        assert "character_arc_analysis" in prompt_names
        assert "scene_improvement_suggestions" in prompt_names

    @pytest.mark.asyncio
    async def test_handle_get_prompt(self, mcp_server):
        """Test handling get prompt request."""
        request = types.GetPromptRequest(
            method="prompts/get",
            params=types.GetPromptRequestParams(
                name="analyze_script_structure", arguments={"script_id": "script_0"}
            ),
        )

        result = await mcp_server._handle_get_prompt(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.GetPromptResult)
        assert len(result.root.messages) == 1
        assert "three-act structure" in result.root.messages[0].content.text
        assert "script_0" in result.root.messages[0].content.text

    @pytest.mark.asyncio
    async def test_handle_get_prompt_unknown(self, mcp_server):
        """Test handling unknown prompt request."""
        request = types.GetPromptRequest(
            method="prompts/get",
            params=types.GetPromptRequestParams(name="unknown_prompt", arguments={}),
        )

        with pytest.raises(ValueError, match="Unknown prompt"):
            await mcp_server._handle_get_prompt(request)

    def test_get_version(self, mcp_server):
        """Test getting server version."""
        version = mcp_server._get_version()
        assert isinstance(version, str)
        assert version == "0.1.0"

    @pytest.mark.asyncio
    async def test_stop(self, mcp_server):
        """Test stopping the server."""
        # Add some cache data
        mcp_server._scripts_cache = {"script_0": MagicMock()}

        await mcp_server.stop()

        assert mcp_server._scripts_cache == {}
