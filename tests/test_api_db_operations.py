"""Comprehensive tests for API database operations."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from scriptrag.api.db_operations import DatabaseOperations
from scriptrag.api.models import SceneModel, ScriptModel

# Test constants
TEST_SCRIPT_TITLE = "Test Script"
TEST_AUTHOR = "Test Author"
SAMPLE_EMBEDDING = [0.1, 0.2, 0.3, 0.4, 0.5]
TEST_DB_PATH = "sqlite+aiosqlite:///test.db"


def assert_error_response(response, status_code, error_substring):
    """Standardized error response assertion."""
    assert response.status_code == status_code
    error_detail = response.json()["detail"]
    assert error_substring.lower() in error_detail.lower()


@pytest.fixture
def mock_connection():
    """Mock database connection."""
    connection = MagicMock()

    # Create a mock context manager for transactions
    transaction_mock = MagicMock()
    transaction_mock.__enter__ = MagicMock(return_value=connection)
    transaction_mock.__exit__ = MagicMock(return_value=None)
    connection.transaction.return_value = transaction_mock

    # Create a mock context manager for get_connection
    get_conn_mock = MagicMock()
    get_conn_mock.__enter__ = MagicMock(return_value=connection)
    get_conn_mock.__exit__ = MagicMock(return_value=None)
    connection.get_connection.return_value = get_conn_mock

    return connection


@pytest.fixture
def db_ops():
    """Create DatabaseOperations instance."""
    return DatabaseOperations(TEST_DB_PATH)


class TestDatabaseOperationsInitialization:
    """Test database initialization and setup."""

    @pytest.mark.asyncio
    async def test_initialize_success(self, db_ops):
        """Test successful database initialization."""
        with (
            patch("scriptrag.api.db_operations.initialize_database") as mock_init_db,
            patch("scriptrag.api.db_operations.DatabaseConnection") as mock_conn_class,
            patch("scriptrag.api.db_operations.GraphOperations") as mock_graph_class,
            patch("scriptrag.api.db_operations.EmbeddingPipeline") as mock_embed_class,
        ):
            # Setup mocks
            mock_connection = MagicMock()
            mock_conn_class.return_value = mock_connection

            await db_ops.initialize()

            # Verify initialization
            mock_init_db.assert_called_once_with("test.db")
            mock_conn_class.assert_called_once_with("test.db")
            mock_graph_class.assert_called_once_with(mock_connection)
            mock_embed_class.assert_called_once_with(mock_connection)

            assert db_ops._connection is not None
            assert db_ops._graph_ops is not None
            assert db_ops._embedding_pipeline is not None

    @pytest.mark.asyncio
    async def test_close_connection(self, db_ops):
        """Test closing database connection."""
        db_ops._connection = MagicMock()

        await db_ops.close()

        # Test that close completes without errors - assertion not needed


class TestScriptOperations:
    """Test script CRUD operations."""

    @pytest.mark.asyncio
    async def test_store_script_success(self, db_ops, mock_connection):
        """Test successful script storage."""
        db_ops._connection = mock_connection

        # Create test script
        scenes = [
            SceneModel(
                id="",
                script_id="",
                scene_number=1,
                heading="INT. COFFEE SHOP - DAY",
                content="A busy coffee shop.",
                characters={"JOHN", "SARAH"},
            ),
            SceneModel(
                id="",
                script_id="",
                scene_number=2,
                heading="EXT. STREET - DAY",
                content="John walks down the street.",
                characters={"JOHN"},
            ),
        ]

        script = ScriptModel(
            id="",
            title=TEST_SCRIPT_TITLE,
            author=TEST_AUTHOR,
            metadata={"genre": "Drama"},
            scenes=scenes,
            characters={"JOHN", "SARAH"},
        )

        # Mock execute to capture the script ID
        script_id = None

        def capture_script_id(*args):
            nonlocal script_id
            if "INSERT INTO scripts" in args[0]:
                script_id = args[1][0]
            return MagicMock()

        mock_connection.execute.side_effect = capture_script_id

        result = await db_ops.store_script(script)

        # Verify script was inserted
        assert result is not None
        assert isinstance(result, str)

        # Verify correct number of execute calls (1 for script + 2 for scenes)
        assert mock_connection.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_store_script_no_connection(self, db_ops):
        """Test storing script without database connection."""
        db_ops._connection = None

        script = ScriptModel(
            id="",
            title="Test",
            author="Test",
            metadata={},
            scenes=[],
            characters=set(),
        )

        with pytest.raises(RuntimeError, match="Database not initialized"):
            await db_ops.store_script(script)

    @pytest.mark.asyncio
    async def test_get_script_success(self, db_ops, mock_connection):
        """Test successful script retrieval."""
        db_ops._connection = mock_connection

        script_id = str(uuid4())

        # Mock script data
        script_data = {
            "id": script_id,
            "title": TEST_SCRIPT_TITLE,
            "author": TEST_AUTHOR,
            "metadata_json": json.dumps({"genre": "Drama"}),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        # Mock scenes data
        scenes_data = [
            {
                "id": str(uuid4()),
                "script_id": script_id,
                "script_order": 1,
                "heading": "INT. COFFEE SHOP - DAY",
                "description": "JOHN enters the coffee shop.",
            },
            {
                "id": str(uuid4()),
                "script_id": script_id,
                "script_order": 2,
                "heading": "EXT. STREET - DAY",
                "description": "SARAH walks down the street.",
            },
        ]

        # Setup mock returns
        mock_connection.execute.return_value.fetchone.return_value = script_data
        mock_connection.execute.return_value.fetchall.return_value = scenes_data

        result = await db_ops.get_script(script_id)

        assert result is not None
        assert result.id == script_id
        assert result.title == TEST_SCRIPT_TITLE
        assert result.author == "Test Author"
        assert result.metadata == {"genre": "Drama"}
        assert len(result.scenes) == 2
        assert result.scenes[0].heading == "INT. COFFEE SHOP - DAY"

    @pytest.mark.asyncio
    async def test_get_script_not_found(self, db_ops, mock_connection):
        """Test getting non-existent script."""
        db_ops._connection = mock_connection

        mock_connection.execute.return_value.fetchone.return_value = None

        result = await db_ops.get_script("non-existent-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_script_invalid_json_metadata(self, db_ops, mock_connection):
        """Test getting script with invalid JSON metadata."""
        db_ops._connection = mock_connection

        script_id = str(uuid4())

        # Mock script data with invalid JSON
        script_data = {
            "id": script_id,
            "title": TEST_SCRIPT_TITLE,
            "author": TEST_AUTHOR,
            "metadata_json": "invalid json {",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        mock_connection.execute.return_value.fetchone.return_value = script_data
        mock_connection.execute.return_value.fetchall.return_value = []

        result = await db_ops.get_script(script_id)

        assert result is not None
        assert result.metadata == {}  # Should default to empty dict

    @pytest.mark.asyncio
    async def test_list_scripts_success(self, db_ops, mock_connection):
        """Test listing all scripts."""
        db_ops._connection = mock_connection

        # Mock scripts data
        scripts_data = [
            {
                "id": str(uuid4()),
                "title": "Script 1",
                "author": "Author 1",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "scene_count": 10,
            },
            {
                "id": str(uuid4()),
                "title": "Script 2",
                "author": "Author 2",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "scene_count": 5,
            },
        ]

        mock_connection.execute.return_value.fetchall.return_value = scripts_data

        result = await db_ops.list_scripts()

        assert len(result) == 2
        assert result[0]["title"] == "Script 1"
        assert result[0]["scene_count"] == 10
        assert result[1]["title"] == "Script 2"
        assert result[1]["scene_count"] == 5

    @pytest.mark.asyncio
    async def test_list_scripts_empty(self, db_ops, mock_connection):
        """Test listing scripts when none exist."""
        db_ops._connection = mock_connection

        mock_connection.execute.return_value.fetchall.return_value = []

        result = await db_ops.list_scripts()

        assert result == []

    @pytest.mark.asyncio
    async def test_delete_script_success(self, db_ops, mock_connection):
        """Test successful script deletion."""
        db_ops._connection = mock_connection

        script_id = str(uuid4())

        await db_ops.delete_script(script_id)

        # Verify delete was called
        mock_connection.execute.assert_called_once_with(
            "DELETE FROM scripts WHERE id = ?", (script_id,)
        )


class TestEmbeddingOperations:
    """Test embedding generation operations."""

    @pytest.mark.asyncio
    async def test_generate_embeddings_success(self, db_ops, mock_connection):
        """Test successful embedding generation."""
        db_ops._connection = mock_connection
        db_ops._embedding_pipeline = MagicMock()

        script_id = str(uuid4())

        # Mock script retrieval
        mock_script = ScriptModel(
            id=script_id,
            title=TEST_SCRIPT_TITLE,
            author=TEST_AUTHOR,
            metadata={},
            scenes=[
                SceneModel(
                    id=str(uuid4()),
                    script_id=script_id,
                    scene_number=1,
                    heading="INT. ROOM - DAY",
                    content="Test content",
                    characters=set(),
                )
            ],
            characters=set(),
        )

        # Mock pipeline result
        mock_result = {
            "scenes_processed": 1,
            "scenes_skipped": 0,
            "processing_time": 1.5,
        }

        with patch.object(db_ops, "get_script", return_value=mock_script):
            db_ops._embedding_pipeline.process_script.return_value = mock_result

            result = await db_ops.generate_embeddings(script_id, regenerate=True)

            assert result == mock_result
            db_ops._embedding_pipeline.process_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embeddings_no_pipeline(self, db_ops):
        """Test embedding generation without pipeline initialized."""
        db_ops._embedding_pipeline = None

        with pytest.raises(RuntimeError, match="Database not initialized"):
            await db_ops.generate_embeddings("script-id")


class TestHelperMethods:
    """Test helper methods."""

    def test_extract_characters(self, db_ops):
        """Test character extraction from content."""
        # Test with character dialogue
        content = """
        JOHN
        Hello there!

        SARAH
        Hi John, how are you?

        JOHN (CONT'D)
        I'm doing great!
        """

        characters = db_ops._extract_characters(content)

        assert characters == {"JOHN", "SARAH"}

    def test_extract_characters_empty(self, db_ops):
        """Test character extraction from empty content."""
        characters = db_ops._extract_characters("")
        assert characters == set()

    def test_extract_characters_no_dialogue(self, db_ops):
        """Test character extraction from action only."""
        content = "The room is dark and empty."
        characters = db_ops._extract_characters(content)
        assert characters == set()

    def test_extract_characters_with_parentheticals(self, db_ops):
        """Test character extraction with parentheticals."""
        content = """
        JOHN (angry)
        Get out!

        SARAH (O.S.)
        I'm leaving!

        NARRATOR (V.O.)
        And so it ended.
        """

        characters = db_ops._extract_characters(content)

        assert characters == {"JOHN", "SARAH", "NARRATOR"}


class TestSceneOperations:
    """Test scene CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_scene_success(self, db_ops, mock_connection):
        """Test successful scene retrieval."""
        db_ops._connection = mock_connection

        scene_id = str(uuid4())
        scene_data = {
            "id": scene_id,
            "script_id": str(uuid4()),
            "script_order": 1,
            "heading": "INT. OFFICE - DAY",
            "description": "The office is busy.",
            "character_count": 2,
            "word_count": 50,
            "page_start": 1.0,
            "page_end": 2.5,
            "has_embedding": 1,
        }

        mock_connection.execute.return_value.fetchone.return_value = scene_data

        result = await db_ops.get_scene(scene_id)

        assert result is not None
        assert result["id"] == scene_id
        assert result["heading"] == "INT. OFFICE - DAY"
        assert result["has_embedding"] is True

    @pytest.mark.asyncio
    async def test_create_scene_success(self, db_ops, mock_connection):
        """Test successful scene creation."""
        db_ops._connection = mock_connection

        script_id = str(uuid4())
        scene_id = await db_ops.create_scene(
            script_id=script_id,
            scene_number=5,
            heading="EXT. PARK - DAY",
            content="A peaceful park scene.",
        )

        assert scene_id is not None
        assert isinstance(scene_id, str)

    @pytest.mark.asyncio
    async def test_update_scene_success(self, db_ops, mock_connection):
        """Test successful scene update."""
        db_ops._connection = mock_connection

        scene_id = str(uuid4())

        await db_ops.update_scene(
            scene_id=scene_id,
            scene_number=3,
            heading="INT. UPDATED LOCATION - NIGHT",
            content="Updated content.",
        )

        # Verify update was called
        assert mock_connection.execute.called

    @pytest.mark.asyncio
    async def test_delete_scene_success(self, db_ops, mock_connection):
        """Test successful scene deletion."""
        db_ops._connection = mock_connection

        scene_id = str(uuid4())

        await db_ops.delete_scene(scene_id)

        # Verify delete was called
        mock_connection.execute.assert_called_once_with(
            "DELETE FROM scenes WHERE id = ?", (scene_id,)
        )

    @pytest.mark.asyncio
    async def test_shift_scene_numbers_success(self, db_ops, mock_connection):
        """Test shifting scene numbers."""
        db_ops._connection = mock_connection

        script_id = str(uuid4())

        await db_ops.shift_scene_numbers(script_id, from_scene_number=5)

        # Verify update was called with correct parameters
        mock_connection.execute.assert_called_once()
        call_args = mock_connection.execute.call_args[0]
        assert "UPDATE scenes SET script_order" in call_args[0]
        assert script_id in call_args[1]
        assert 5 in call_args[1]
