"""Tests for ScriptRAG MCP Server."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.mcp.models import (
    CharacterSummary,
    DialogueSearchResult,
    SceneSummary,
    ScriptMetadata,
)
from scriptrag.mcp.tools.get_character import scriptrag_get_character
from scriptrag.mcp.tools.get_scene import scriptrag_get_scene
from scriptrag.mcp.tools.get_script import scriptrag_get_script
from scriptrag.mcp.tools.import_script import scriptrag_import_script
from scriptrag.mcp.tools.list_characters import scriptrag_list_characters
from scriptrag.mcp.tools.list_scenes import scriptrag_list_scenes
from scriptrag.mcp.tools.list_scripts import scriptrag_list_scripts
from scriptrag.mcp.tools.search_dialogue import scriptrag_search_dialogue


@pytest.mark.asyncio
async def test_import_script_success():
    """Test successful script import."""
    with patch("scriptrag.mcp.tools.import_script.validate_file_path") as mock_validate:
        mock_validate.return_value = MagicMock(suffix=".fountain", stem="test_script")

        with patch("scriptrag.mcp.tools.import_script.IndexCommand") as mock_index:
            mock_cmd = MagicMock()
            mock_index.from_config.return_value = mock_cmd

            # Mock successful index result
            mock_result = MagicMock()
            mock_result.errors = []
            mock_result.scripts = [
                MagicMock(
                    script_id=1,
                    scenes_indexed=10,
                    characters_indexed=5,
                    error=None,
                )
            ]

            with patch(
                "scriptrag.mcp.tools.import_script.AsyncAPIWrapper"
            ) as mock_wrapper:
                wrapper_instance = MagicMock()
                wrapper_instance.run_sync = AsyncMock(return_value=mock_result)
                mock_wrapper.return_value = wrapper_instance

                result = await scriptrag_import_script("/path/to/script.fountain")

                assert result.success is True
                assert result.script_id == 1
                assert result.scenes_imported == 10
                assert result.characters_indexed == 5
                assert "Successfully imported" in result.message


@pytest.mark.asyncio
async def test_import_script_invalid_file():
    """Test script import with invalid file type."""
    with patch("scriptrag.mcp.tools.import_script.validate_file_path") as mock_validate:
        mock_validate.return_value = MagicMock(suffix=".pdf")

        result = await scriptrag_import_script("/path/to/script.pdf")

        assert result.success is False
        assert "must be a Fountain format file" in result.message


@pytest.mark.asyncio
async def test_list_scripts_success():
    """Test listing scripts."""
    with patch("scriptrag.mcp.tools.list_scripts.ScriptLister") as mock_lister:
        mock_lister_instance = MagicMock()
        mock_lister.return_value = mock_lister_instance

        # Mock script data
        mock_scripts = [
            MagicMock(
                script_id=1,
                title="Script One",
                path="/path/one.fountain",
                scene_count=10,
                character_count=5,
                created_at="2024-01-01",
                updated_at=None,
            ),
            MagicMock(
                script_id=2,
                title="Script Two",
                path="/path/two.fountain",
                scene_count=20,
                character_count=8,
                created_at="2024-01-02",
                updated_at="2024-01-03",
            ),
        ]

        with patch("scriptrag.mcp.tools.list_scripts.AsyncAPIWrapper") as mock_wrapper:
            wrapper_instance = MagicMock()
            wrapper_instance.run_sync = AsyncMock(return_value=mock_scripts)
            mock_wrapper.return_value = wrapper_instance

            result = await scriptrag_list_scripts(limit=10, offset=0)

            assert result.success is True
            assert len(result.scripts) == 2
            assert result.total_count == 2
            assert result.has_more is False
            assert result.scripts[0].title == "Script One"
            assert result.scripts[1].title == "Script Two"


@pytest.mark.asyncio
async def test_get_script_by_id():
    """Test getting script by ID."""
    with patch("scriptrag.mcp.tools.get_script.DatabaseOperations") as mock_db:
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance

        # Mock script record
        mock_script = MagicMock(
            id=1,
            title="Test Script",
            file_path="/path/test.fountain",
            content_hash="abc123",
            metadata={"author": "Test Author"},
            created_at="2024-01-01",
            updated_at=None,
        )

        # Mock scenes
        mock_scenes = [
            MagicMock(
                id=1,
                script_id=1,
                scene_number=1,
                heading="INT. ROOM - DAY",
                characters=["ALICE", "BOB"],
                dialogue_count=5,
            )
        ]

        with patch("scriptrag.mcp.tools.get_script.AsyncAPIWrapper") as mock_wrapper:
            wrapper_instance = MagicMock()
            wrapper_instance.run_sync = AsyncMock(
                side_effect=[mock_script, mock_scenes]
            )
            mock_wrapper.return_value = wrapper_instance

            result = await scriptrag_get_script(script_id=1)

            assert result.success is True
            assert result.script.script_id == 1
            assert result.script.title == "Test Script"
            assert len(result.scenes) == 1
            assert result.character_count == 2
            assert result.total_scenes == 1


@pytest.mark.asyncio
async def test_list_scenes_with_filters():
    """Test listing scenes with filters."""
    with patch("scriptrag.mcp.tools.list_scenes.DatabaseOperations") as mock_db:
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance

        # Mock scenes
        mock_scenes = [
            MagicMock(
                id=1,
                script_id=1,
                scene_number=1,
                heading="INT. OFFICE - DAY",
                characters=["ALICE", "BOB"],
                dialogue_count=10,
            ),
            MagicMock(
                id=2,
                script_id=1,
                scene_number=2,
                heading="EXT. PARK - NIGHT",
                characters=["ALICE"],
                dialogue_count=5,
            ),
        ]

        with patch("scriptrag.mcp.tools.list_scenes.AsyncAPIWrapper") as mock_wrapper:
            wrapper_instance = MagicMock()
            wrapper_instance.run_sync = AsyncMock(return_value=mock_scenes)
            mock_wrapper.return_value = wrapper_instance

            # Test with character filter
            result = await scriptrag_list_scenes(script_id=1, character="ALICE")

            assert result.success is True
            assert len(result.scenes) == 2
            assert result.total_count == 2


@pytest.mark.asyncio
async def test_search_dialogue():
    """Test dialogue search."""
    with patch("scriptrag.mcp.tools.search_dialogue.SearchAPI") as mock_search:
        mock_search_instance = MagicMock()
        mock_search.return_value = mock_search_instance

        # Mock search results
        mock_results = {
            "results": [
                {
                    "scene_id": 1,
                    "script_id": 1,
                    "scene_number": 1,
                    "character": "ALICE",
                    "dialogue": "Hello, Bob!",
                    "score": 0.95,
                }
            ]
        }

        with patch(
            "scriptrag.mcp.tools.search_dialogue.AsyncAPIWrapper"
        ) as mock_wrapper:
            wrapper_instance = MagicMock()
            wrapper_instance.run_sync = AsyncMock(return_value=mock_results)
            mock_wrapper.return_value = wrapper_instance

            result = await scriptrag_search_dialogue(query="Hello", character="ALICE")

            assert result.success is True
            assert len(result.results) == 1
            assert result.results[0].character == "ALICE"
            assert result.results[0].dialogue == "Hello, Bob!"
            assert result.query_info.query == "Hello"


@pytest.mark.asyncio
async def test_list_characters():
    """Test listing characters."""
    with patch("scriptrag.mcp.tools.list_characters.DatabaseOperations") as mock_db:
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance

        # Mock character data
        mock_characters = [
            MagicMock(
                name="ALICE",
                dialogue_count=25,
                scene_count=10,
                first_appearance=1,
                last_appearance=10,
            ),
            MagicMock(
                name="BOB",
                dialogue_count=20,
                scene_count=8,
                first_appearance=2,
                last_appearance=9,
            ),
        ]

        with patch(
            "scriptrag.mcp.tools.list_characters.AsyncAPIWrapper"
        ) as mock_wrapper:
            wrapper_instance = MagicMock()
            wrapper_instance.run_sync = AsyncMock(return_value=mock_characters)
            mock_wrapper.return_value = wrapper_instance

            result = await scriptrag_list_characters(min_lines=10, sort_by="lines")

            assert result.success is True
            assert len(result.characters) == 2
            assert result.characters[0].name == "ALICE"
            assert result.characters[0].dialogue_count == 25
            assert result.characters[1].name == "BOB"


@pytest.mark.asyncio
async def test_get_character_details():
    """Test getting character details."""
    with patch("scriptrag.mcp.tools.get_character.DatabaseOperations") as mock_db:
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance

        # Mock character data
        mock_character = MagicMock(
            name="ALICE",
            dialogue_lines=["Hello!", "How are you?", "Goodbye!"],
            metadata={"role": "protagonist"},
        )

        # Mock scenes
        mock_scenes = [
            MagicMock(
                id=1,
                scene_number=1,
                heading="INT. ROOM - DAY",
                content="ALICE\nHello!\n\nBOB\nHi there!",
            )
        ]

        # Mock relationships
        mock_relationships = [
            {"character2": "BOB", "shared_scenes": 5, "interactions": 10, "type": None}
        ]

        with patch("scriptrag.mcp.tools.get_character.AsyncAPIWrapper") as mock_wrapper:
            wrapper_instance = MagicMock()
            wrapper_instance.run_sync = AsyncMock(
                side_effect=[mock_character, mock_scenes, mock_relationships]
            )
            mock_wrapper.return_value = wrapper_instance

            result = await scriptrag_get_character(
                character_name="Alice", include_relationships=True
            )

            assert result.success is True
            assert result.character.name == "ALICE"
            assert result.dialogue_stats.total_lines == 3
            assert len(result.scene_appearances) == 1
            assert len(result.relationships) == 1
            assert result.relationships[0].character2 == "BOB"


@pytest.mark.asyncio
async def test_get_scene_with_dialogue():
    """Test getting scene with dialogue breakdown."""
    with patch("scriptrag.mcp.tools.get_scene.DatabaseOperations") as mock_db:
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance

        # Mock scene
        mock_scene = MagicMock(
            id=1,
            script_id=1,
            scene_number=1,
            heading="INT. OFFICE - DAY",
            content="ALICE\nHello, Bob!\n\nBOB\nHi Alice! How are you?\n\nThey shake hands.",
            characters=["ALICE", "BOB"],
            metadata={"duration": "2 pages"},
        )

        with patch("scriptrag.mcp.tools.get_scene.AsyncAPIWrapper") as mock_wrapper:
            wrapper_instance = MagicMock()
            wrapper_instance.run_sync = AsyncMock(return_value=mock_scene)
            mock_wrapper.return_value = wrapper_instance

            result = await scriptrag_get_scene(scene_id=1, include_dialogue=True)

            assert result.success is True
            assert result.scene.scene_id == 1
            assert result.scene.heading == "INT. OFFICE - DAY"
            assert len(result.dialogue_lines) == 2
            assert result.dialogue_lines[0].character == "ALICE"
            assert result.dialogue_lines[0].text == "Hello, Bob!"
            assert result.dialogue_lines[1].character == "BOB"
            assert len(result.action_lines) == 1


def test_model_creation():
    """Test Pydantic model creation."""
    # Test ScriptMetadata
    script = ScriptMetadata(
        script_id=1,
        title="Test Script",
        file_path="/path/test.fountain",
        scene_count=10,
        character_count=5,
        created_at="2024-01-01",
    )
    assert script.script_id == 1
    assert script.title == "Test Script"

    # Test SceneSummary
    scene = SceneSummary(
        scene_id=1,
        script_id=1,
        scene_number=1,
        heading="INT. ROOM - DAY",
        location="ROOM",
        time_of_day="DAY",
        character_count=2,
        dialogue_count=5,
    )
    assert scene.scene_id == 1
    assert scene.location == "ROOM"

    # Test CharacterSummary
    character = CharacterSummary(
        name="ALICE",
        dialogue_count=25,
        scene_count=10,
        first_appearance_scene=1,
        last_appearance_scene=10,
    )
    assert character.name == "ALICE"
    assert character.dialogue_count == 25

    # Test DialogueSearchResult
    dialogue = DialogueSearchResult(
        scene_id=1,
        script_id=1,
        scene_number=1,
        character="ALICE",
        dialogue="Hello!",
        match_score=0.95,
    )
    assert dialogue.character == "ALICE"
    assert dialogue.match_score == 0.95
