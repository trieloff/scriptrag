"""Unit tests for MCP scene management tools."""
# ruff: noqa: S105,S106

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.api.scene_management import (
    AddSceneResult,
    BibleReadResult,
    DeleteSceneResult,
    ReadSceneResult,
    UpdateSceneResult,
)
from scriptrag.mcp.tools.scene import register_scene_tools
from scriptrag.parser import Scene


@pytest.fixture
def mock_scene_api():
    """Create a mock SceneManagementAPI."""
    with patch("scriptrag.mcp.tools.scene.SceneManagementAPI") as mock_class:
        mock_api = MagicMock()
        mock_class.return_value = mock_api
        yield mock_api


@pytest.fixture
def sample_scene():
    """Create a sample scene for testing."""
    return Scene(
        number=5,
        heading="INT. COFFEE SHOP - DAY",
        content="Walter enters, looking tired.\n\nWALTER\nI need coffee.",
        original_text="Walter enters, looking tired.\n\nWALTER\nI need coffee.",
        content_hash="test_hash_123",
        location="COFFEE SHOP",
        time_of_day="DAY",
    )


class TestSceneReadTool:
    """Test the scriptrag_scene_read MCP tool."""

    @pytest.mark.asyncio
    async def test_read_scene_success(self, mock_scene_api, sample_scene):
        """Test successful scene read."""
        # Setup mock response

        from mcp.server import FastMCP

        expires_at = datetime.now(UTC)
        mock_result = ReadSceneResult(
            success=True,
            error=None,
            scene=sample_scene,
            session_token="fake-test-token-not-real",
            expires_at=expires_at,
        )
        mock_scene_api.read_scene = AsyncMock(return_value=mock_result)

        # Register tools and execute
        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_read",
            {
                "project": "breaking_bad",
                "scene_number": 5,
                "season": 1,
                "episode": 1,
                "reader_id": "test_reader",
            },
        )

        result = response[1]  # Raw dictionary result

        # Verify result structure
        assert result["success"] is True
        assert result["error"] is None
        assert result["scene"]["number"] == 5
        assert result["scene"]["heading"] == "INT. COFFEE SHOP - DAY"
        assert result["scene"]["content"] == sample_scene.content
        assert result["scene"]["location"] == "COFFEE SHOP"
        assert result["scene"]["time_of_day"] == "DAY"
        assert result["session_token"] == "fake-test-token-not-real"
        assert result["expires_at"] == expires_at.isoformat()

        # Verify API was called correctly
        mock_scene_api.read_scene.assert_called_once()
        call_args = mock_scene_api.read_scene.call_args[0]
        scene_id = call_args[0]
        reader_id = call_args[1]

        assert scene_id.project == "breaking_bad"
        assert scene_id.scene_number == 5
        assert scene_id.season == 1
        assert scene_id.episode == 1
        assert reader_id == "test_reader"

    @pytest.mark.asyncio
    async def test_read_scene_feature_film(self, mock_scene_api, sample_scene):
        """Test reading scene from feature film (no season/episode)."""
        from mcp.server import FastMCP

        mock_result = ReadSceneResult(
            success=True,
            error=None,
            scene=sample_scene,
            session_token="fake-token-test-456",
            expires_at=None,
        )
        mock_scene_api.read_scene = AsyncMock(return_value=mock_result)

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_read",
            {
                "project": "inception",
                "scene_number": 42,
            },
        )

        result = response[1]
        assert result["success"] is True
        assert result["expires_at"] is None

        # Verify scene identifier was created correctly
        call_args = mock_scene_api.read_scene.call_args[0]
        scene_id = call_args[0]
        assert scene_id.project == "inception"
        assert scene_id.scene_number == 42
        assert scene_id.season is None
        assert scene_id.episode is None

    @pytest.mark.asyncio
    async def test_read_scene_not_found(self, mock_scene_api):
        """Test reading non-existent scene."""
        from mcp.server import FastMCP

        mock_result = ReadSceneResult(
            success=False,
            error="Scene not found",
            scene=None,
            session_token=None,
            expires_at=None,
        )
        mock_scene_api.read_scene = AsyncMock(return_value=mock_result)

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_read",
            {
                "project": "test_project",
                "scene_number": 999,
            },
        )

        result = response[1]
        assert result["success"] is False
        assert result["error"] == "Scene not found"
        assert result["scene"] is None
        assert result["session_token"] is None

    @pytest.mark.asyncio
    async def test_read_scene_exception_handling(self, mock_scene_api):
        """Test exception handling in scene read."""
        from mcp.server import FastMCP

        # Setup API to raise exception
        mock_scene_api.read_scene = AsyncMock(side_effect=Exception("Database error"))

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_read",
            {
                "project": "test_project",
                "scene_number": 1,
            },
        )

        result = response[1]
        assert result["success"] is False
        assert "Database error" in result["error"]
        assert result["scene"] is None
        assert result["session_token"] is None


class TestSceneAddTool:
    """Test the scriptrag_scene_add MCP tool."""

    @pytest.mark.asyncio
    async def test_add_scene_after(self, mock_scene_api):
        """Test adding scene after reference scene."""
        from mcp.server import FastMCP

        created_scene = Scene(
            number=6,
            heading="INT. NEW SCENE - DAY",
            content="New scene content",
            original_text="New scene content",
            content_hash="new_hash",
        )

        mock_result = AddSceneResult(
            success=True,
            error=None,
            created_scene=created_scene,
            renumbered_scenes=[7, 8, 9],
        )
        mock_scene_api.add_scene = AsyncMock(return_value=mock_result)

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_add",
            {
                "project": "breaking_bad",
                "content": "INT. NEW SCENE - DAY\n\nNew scene content",
                "after_scene": 5,
                "season": 1,
                "episode": 2,
            },
        )

        result = response[1]
        assert result["success"] is True
        assert result["error"] is None
        assert result["created_scene"]["number"] == 6
        assert result["created_scene"]["heading"] == "INT. NEW SCENE - DAY"
        assert result["renumbered_scenes"] == [7, 8, 9]

        # Verify API call
        mock_scene_api.add_scene.assert_called_once()
        call_args = mock_scene_api.add_scene.call_args[0]
        scene_id, content, position = call_args
        assert scene_id.project == "breaking_bad"
        assert scene_id.scene_number == 5
        assert content == "INT. NEW SCENE - DAY\n\nNew scene content"
        assert position == "after"

    @pytest.mark.asyncio
    async def test_add_scene_before(self, mock_scene_api):
        """Test adding scene before reference scene."""
        from mcp.server import FastMCP

        created_scene = Scene(
            number=5,
            heading="INT. NEW SCENE - DAY",
            content="New scene content",
            original_text="New scene content",
            content_hash="new_hash",
        )

        mock_result = AddSceneResult(
            success=True,
            error=None,
            created_scene=created_scene,
            renumbered_scenes=[6, 7, 8],
        )
        mock_scene_api.add_scene = AsyncMock(return_value=mock_result)

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_add",
            {
                "project": "inception",
                "content": "EXT. CITY - NIGHT\n\nCobb walks",
                "before_scene": 10,
            },
        )

        result = response[1]
        assert result["success"] is True
        assert result["created_scene"]["number"] == 5
        assert result["renumbered_scenes"] == [6, 7, 8]

        # Verify position was set correctly
        call_args = mock_scene_api.add_scene.call_args[0]
        position = call_args[2]
        assert position == "before"

    @pytest.mark.asyncio
    async def test_add_scene_no_position(self, mock_scene_api):
        """Test validation when no position specified."""
        from mcp.server import FastMCP

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_add",
            {
                "project": "test_project",
                "content": "INT. SCENE - DAY\n\nContent",
            },
        )

        result = response[1]
        assert result["success"] is False
        assert "Must specify either after_scene or before_scene" in result["error"]
        assert result["created_scene"] is None
        assert result["renumbered_scenes"] == []

        # API should not be called
        mock_scene_api.add_scene.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_scene_both_positions(self, mock_scene_api):
        """Test validation when both positions specified."""
        from mcp.server import FastMCP

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_add",
            {
                "project": "test_project",
                "content": "INT. SCENE - DAY\n\nContent",
                "after_scene": 5,
                "before_scene": 10,
            },
        )

        result = response[1]
        assert result["success"] is False
        assert "Cannot specify both after_scene and before_scene" in result["error"]
        mock_scene_api.add_scene.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_scene_api_error(self, mock_scene_api):
        """Test handling API errors."""
        from mcp.server import FastMCP

        mock_result = AddSceneResult(
            success=False,
            error="Invalid Fountain format: Missing scene heading",
            created_scene=None,
            renumbered_scenes=[],
        )
        mock_scene_api.add_scene = AsyncMock(return_value=mock_result)

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_add",
            {
                "project": "test_project",
                "content": "Invalid content",
                "after_scene": 5,
            },
        )

        result = response[1]
        assert result["success"] is False
        assert "Invalid Fountain format" in result["error"]
        assert result["created_scene"] is None

    @pytest.mark.asyncio
    async def test_add_scene_exception(self, mock_scene_api):
        """Test exception handling."""
        from mcp.server import FastMCP

        mock_scene_api.add_scene = AsyncMock(side_effect=Exception("API failure"))

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_add",
            {
                "project": "test_project",
                "content": "INT. SCENE - DAY\n\nContent",
                "after_scene": 5,
            },
        )

        result = response[1]
        assert result["success"] is False
        assert "API failure" in result["error"]


class TestSceneUpdateTool:
    """Test the scriptrag_scene_update MCP tool."""

    @pytest.mark.asyncio
    async def test_update_scene_success(self, mock_scene_api):
        """Test successful scene update."""
        from mcp.server import FastMCP

        updated_scene = Scene(
            number=5,
            heading="INT. UPDATED SCENE - DAY",
            content="Updated content here",
            original_text="Updated content here",
            content_hash="updated_hash",
        )

        mock_result = UpdateSceneResult(
            success=True,
            error=None,
            updated_scene=updated_scene,
            validation_errors=[],
        )
        mock_scene_api.update_scene = AsyncMock(return_value=mock_result)

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_update",
            {
                "project": "breaking_bad",
                "scene_number": 5,
                "content": "INT. UPDATED SCENE - DAY\n\nUpdated content here",
                "session_token": "fake-valid-token",
                "season": 1,
                "episode": 1,
                "reader_id": "test_reader",
            },
        )

        result = response[1]
        assert result["success"] is True
        assert result["error"] is None
        assert result["updated_scene"]["number"] == 5
        assert result["updated_scene"]["heading"] == "INT. UPDATED SCENE - DAY"
        assert result["updated_scene"]["content"] == "Updated content here"
        assert result["validation_errors"] == []

        # Verify API call
        mock_scene_api.update_scene.assert_called_once()
        call_args = mock_scene_api.update_scene.call_args[0]
        scene_id, content, token, reader_id = call_args
        assert scene_id.project == "breaking_bad"
        assert scene_id.scene_number == 5
        assert content == "INT. UPDATED SCENE - DAY\n\nUpdated content here"
        assert token == "fake-valid-token"
        assert reader_id == "test_reader"

    @pytest.mark.asyncio
    async def test_update_scene_invalid_session(self, mock_scene_api):
        """Test update with invalid session token."""
        from mcp.server import FastMCP

        mock_result = UpdateSceneResult(
            success=False,
            error="Session token not found or expired",
            updated_scene=None,
            validation_errors=["SESSION_INVALID"],
        )
        mock_scene_api.update_scene = AsyncMock(return_value=mock_result)

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_update",
            {
                "project": "test_project",
                "scene_number": 5,
                "content": "INT. SCENE - DAY\n\nContent",
                "session_token": "fake-invalid-token",
            },
        )

        result = response[1]
        assert result["success"] is False
        assert "Session token not found or expired" in result["error"]
        assert result["updated_scene"] is None
        assert "SESSION_INVALID" in result["validation_errors"]

    @pytest.mark.asyncio
    async def test_update_scene_concurrent_modification(self, mock_scene_api):
        """Test concurrent modification detection."""
        from mcp.server import FastMCP

        mock_result = UpdateSceneResult(
            success=False,
            error="Scene was modified by another process",
            updated_scene=None,
            validation_errors=["CONCURRENT_MODIFICATION"],
        )
        mock_scene_api.update_scene = AsyncMock(return_value=mock_result)

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_update",
            {
                "project": "test_project",
                "scene_number": 5,
                "content": "INT. SCENE - DAY\n\nContent",
                "session_token": "fake-valid-session-token",
            },
        )

        result = response[1]
        assert result["success"] is False
        assert "modified by another process" in result["error"]
        assert "CONCURRENT_MODIFICATION" in result["validation_errors"]

    @pytest.mark.asyncio
    async def test_update_scene_exception(self, mock_scene_api):
        """Test exception handling."""
        from mcp.server import FastMCP

        mock_scene_api.update_scene = AsyncMock(side_effect=Exception("Update failed"))

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_update",
            {
                "project": "test_project",
                "scene_number": 5,
                "content": "INT. SCENE - DAY\n\nContent",
                "session_token": "fake-session-token",
            },
        )

        result = response[1]
        assert result["success"] is False
        assert "Update failed" in result["error"]
        assert result["validation_errors"] == ["EXCEPTION"]


class TestSceneDeleteTool:
    """Test the scriptrag_scene_delete MCP tool."""

    @pytest.mark.asyncio
    async def test_delete_scene_success(self, mock_scene_api):
        """Test successful scene deletion."""
        from mcp.server import FastMCP

        mock_result = DeleteSceneResult(
            success=True,
            error=None,
            renumbered_scenes=[6, 7, 8, 9],
        )
        mock_scene_api.delete_scene = AsyncMock(return_value=mock_result)

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_delete",
            {
                "project": "breaking_bad",
                "scene_number": 5,
                "season": 1,
                "episode": 1,
                "confirm": True,
            },
        )

        result = response[1]
        assert result["success"] is True
        assert result["error"] is None
        assert result["renumbered_scenes"] == [6, 7, 8, 9]

        # Verify API call
        mock_scene_api.delete_scene.assert_called_once()
        call_args = mock_scene_api.delete_scene.call_args[0]
        scene_id = call_args[0]
        assert scene_id.project == "breaking_bad"
        assert scene_id.scene_number == 5
        # Check confirm keyword argument
        call_kwargs = mock_scene_api.delete_scene.call_args[1]
        assert call_kwargs["confirm"] is True

    @pytest.mark.asyncio
    async def test_delete_scene_no_confirm(self, mock_scene_api):
        """Test deletion requires confirmation."""
        from mcp.server import FastMCP

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_delete",
            {
                "project": "test_project",
                "scene_number": 5,
                "confirm": False,
            },
        )

        result = response[1]
        assert result["success"] is False
        assert "Deletion requires confirm=True" in result["error"]
        assert result["renumbered_scenes"] == []

        # API should not be called
        mock_scene_api.delete_scene.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_scene_not_found(self, mock_scene_api):
        """Test deleting non-existent scene."""
        from mcp.server import FastMCP

        mock_result = DeleteSceneResult(
            success=False,
            error="Scene not found",
            renumbered_scenes=[],
        )
        mock_scene_api.delete_scene = AsyncMock(return_value=mock_result)

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_delete",
            {
                "project": "test_project",
                "scene_number": 999,
                "confirm": True,
            },
        )

        result = response[1]
        assert result["success"] is False
        assert "Scene not found" in result["error"]
        assert result["renumbered_scenes"] == []

    @pytest.mark.asyncio
    async def test_delete_scene_exception(self, mock_scene_api):
        """Test exception handling."""
        from mcp.server import FastMCP

        mock_scene_api.delete_scene = AsyncMock(side_effect=Exception("Delete failed"))

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_scene_delete",
            {
                "project": "test_project",
                "scene_number": 5,
                "confirm": True,
            },
        )

        result = response[1]
        assert result["success"] is False
        assert "Delete failed" in result["error"]


class TestSceneBibleReadTool:
    """Test the scriptrag_bible_read MCP tool."""

    @pytest.mark.asyncio
    async def test_read_bible_content(self, mock_scene_api):
        """Test reading specific bible content."""
        from mcp.server import FastMCP

        mock_result = BibleReadResult(
            success=True,
            error=None,
            content=(
                "# Character Bible\n\n"
                "Walter White is a high school chemistry teacher..."
            ),
            bible_files=None,
        )
        mock_scene_api.read_bible = AsyncMock(return_value=mock_result)

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_bible_read",
            {
                "project": "breaking_bad",
                "bible_name": "characters.md",
            },
        )

        result = response[1]
        assert result["success"] is True
        assert result["error"] is None
        assert "Walter White is a high school" in result["content"]
        assert result["bible_name"] == "characters.md"

        # Verify API call
        mock_scene_api.read_bible.assert_called_once_with(
            "breaking_bad", "characters.md"
        )

    @pytest.mark.asyncio
    async def test_list_bible_files(self, mock_scene_api):
        """Test listing available bible files."""
        from mcp.server import FastMCP

        bible_files = [
            {"name": "characters.md", "path": "bibles/characters.md", "size": 1024},
            {"name": "world.md", "path": "bibles/world.md", "size": 2048},
        ]

        mock_result = BibleReadResult(
            success=True,
            error=None,
            content=None,
            bible_files=bible_files,
        )
        mock_scene_api.read_bible = AsyncMock(return_value=mock_result)

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_bible_read",
            {
                "project": "inception",
            },
        )

        result = response[1]
        assert result["success"] is True
        assert result["error"] is None
        assert result["bible_files"] == bible_files
        assert "content" not in result  # Content not included when listing

        # Verify API call with None bible_name
        mock_scene_api.read_bible.assert_called_once_with("inception", None)

    @pytest.mark.asyncio
    async def test_read_bible_not_found(self, mock_scene_api):
        """Test reading non-existent bible."""
        from mcp.server import FastMCP

        mock_result = BibleReadResult(
            success=False,
            error="Bible file not found: missing.md",
            content=None,
            bible_files=None,
        )
        mock_scene_api.read_bible = AsyncMock(return_value=mock_result)

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_bible_read",
            {
                "project": "test_project",
                "bible_name": "missing.md",
            },
        )

        result = response[1]
        assert result["success"] is False
        assert "Bible file not found" in result["error"]

    @pytest.mark.asyncio
    async def test_read_bible_exception(self, mock_scene_api):
        """Test exception handling."""
        from mcp.server import FastMCP

        mock_scene_api.read_bible = AsyncMock(
            side_effect=Exception("File system error")
        )

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        response = await mcp.call_tool(
            "scriptrag_bible_read",
            {
                "project": "test_project",
                "bible_name": "test.md",
            },
        )

        result = response[1]
        assert result["success"] is False
        assert "File system error" in result["error"]


class TestSceneToolsRegistration:
    """Test scene tools registration."""

    @pytest.mark.asyncio
    async def test_all_tools_registered(self):
        """Test that all scene tools are registered."""
        from mcp.server import FastMCP

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        tools = await mcp.list_tools()
        tool_names = [tool.name for tool in tools]

        expected_tools = [
            "scriptrag_scene_read",
            "scriptrag_scene_add",
            "scriptrag_scene_update",
            "scriptrag_scene_delete",
            "scriptrag_bible_read",
        ]

        for tool_name in expected_tools:
            assert tool_name in tool_names, f"Tool {tool_name} not registered"

    @pytest.mark.asyncio
    async def test_tool_descriptions(self):
        """Test that tools have proper descriptions."""
        from mcp.server import FastMCP

        mcp = FastMCP("test")
        register_scene_tools(mcp)

        tools = await mcp.list_tools()
        tools_by_name = {tool.name: tool for tool in tools}

        # Check that key tools have descriptions
        read_tool = tools_by_name["scriptrag_scene_read"]
        assert "Read a scene" in read_tool.description
        assert "session token" in read_tool.description

        add_tool = tools_by_name["scriptrag_scene_add"]
        assert "Add a new scene" in add_tool.description
        assert "automatic renumbering" in add_tool.description

        update_tool = tools_by_name["scriptrag_scene_update"]
        assert "Update scene content" in update_tool.description
        assert "validation" in update_tool.description

        delete_tool = tools_by_name["scriptrag_scene_delete"]
        assert "Delete a scene" in delete_tool.description
        assert "automatic renumbering" in delete_tool.description

        bible_tool = tools_by_name["scriptrag_bible_read"]
        assert "Read script bible" in bible_tool.description
        assert "markdown" in bible_tool.description.lower()
