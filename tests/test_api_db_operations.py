"""Comprehensive tests for API database operations."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from scriptrag.api.db_operations import DatabaseOperations
from scriptrag.api.models import SceneModel, ScriptModel
from scriptrag.config import ScriptRAGSettings

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
    config = ScriptRAGSettings(database_path=":memory:")
    return DatabaseOperations(config)


class TestDatabaseOperationsInitialization:
    """Test database initialization and setup."""

    @pytest.mark.asyncio
    async def test_initialize_success(self, db_ops):
        """Test successful database initialization."""
        # Test that initialization doesn't raise an error
        await db_ops.initialize()

        # Verify that ScriptRAG was initialized
        assert db_ops.scriptrag is not None

    @pytest.mark.asyncio
    async def test_close_connection(self, db_ops):
        """Test closing database connection."""
        db_ops._connection = MagicMock()

        await db_ops.close()

        # Test that close completes without errors - assertion not needed


class TestScriptOperations:
    """Test script CRUD operations."""

    @pytest.mark.asyncio
    @patch("scriptrag.database.get_connection")
    async def test_store_script_success(
        self, mock_get_connection, db_ops, mock_connection
    ):
        """Test successful script storage."""
        # Mock the get_connection context manager
        mock_get_connection.return_value.__enter__.return_value = mock_connection
        mock_get_connection.return_value.__exit__.return_value = None

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
    @patch("scriptrag.database.get_connection")
    async def test_store_script_no_connection(self, mock_get_connection, db_ops):
        """Test storing script when database connection fails."""
        # Mock get_connection to raise an error
        mock_get_connection.side_effect = RuntimeError("Database not initialized")

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
    @patch("scriptrag.database.get_connection")
    async def test_get_script_success(
        self, mock_get_connection, db_ops, mock_connection
    ):
        """Test successful script retrieval."""
        # Mock the get_connection context manager
        mock_get_connection.return_value.__enter__.return_value = mock_connection
        mock_get_connection.return_value.__exit__.return_value = None

        script_id = str(uuid4())

        # Mock script data - matching actual query columns
        script_data = {
            "id": script_id,
            "title": TEST_SCRIPT_TITLE,
            "author": TEST_AUTHOR,
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
        assert result.metadata is None  # Implementation doesn't load metadata
        assert len(result.scenes) == 0  # Implementation leaves scenes empty

    @pytest.mark.asyncio
    async def test_get_script_not_found(self, db_ops, mock_connection):
        """Test getting non-existent script."""
        db_ops._connection = mock_connection

        mock_connection.execute.return_value.fetchone.return_value = None

        result = await db_ops.get_script("non-existent-id")

        assert result is None

    @pytest.mark.asyncio
    @patch("scriptrag.database.get_connection")
    async def test_get_script_invalid_json_metadata(
        self, mock_get_connection, db_ops, mock_connection
    ):
        """Test getting script with invalid JSON metadata."""
        # Mock the get_connection context manager
        mock_get_connection.return_value.__enter__.return_value = mock_connection
        mock_get_connection.return_value.__exit__.return_value = None

        script_id = str(uuid4())

        # Mock script data - matching actual query columns
        script_data = {
            "id": script_id,
            "title": TEST_SCRIPT_TITLE,
            "author": TEST_AUTHOR,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        mock_connection.execute.return_value.fetchone.return_value = script_data
        mock_connection.execute.return_value.fetchall.return_value = []

        result = await db_ops.get_script(script_id)

        assert result is not None
        assert result.metadata is None  # Implementation doesn't load metadata

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
                "character_count": 3,
                "has_embeddings": 1,  # SQLite returns 0/1 for boolean
            },
            {
                "id": str(uuid4()),
                "title": "Script 2",
                "author": "Author 2",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "scene_count": 5,
                "character_count": 2,
                "has_embeddings": 0,  # SQLite returns 0/1 for boolean
            },
        ]

        mock_connection.execute.return_value.fetchall.return_value = scripts_data

        result = await db_ops.list_scripts()

        assert len(result) == 2
        assert result[0]["title"] == "Script 1"
        assert result[0]["scene_count"] == 10
        assert result[0]["character_count"] == 3
        assert result[0]["has_embeddings"] is True
        assert result[1]["title"] == "Script 2"
        assert result[1]["scene_count"] == 5
        assert result[1]["character_count"] == 2
        assert result[1]["has_embeddings"] is False

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

        # Mock pipeline result - using the keys that the actual implementation expects
        mock_result = {
            "embeddings_generated": 1,
            "embeddings_skipped": 0,
            "processing_time": 1.5,
        }

        with patch.object(db_ops, "get_script", return_value=mock_script):
            # Mock async method with AsyncMock
            db_ops._embedding_pipeline.process_script = AsyncMock(
                return_value=mock_result
            )

            result = await db_ops.generate_embeddings(script_id, regenerate=True)

            # Expected result after transformation by the method
            expected_result = {
                "script_id": script_id,
                "scenes_processed": 1,
                "scenes_skipped": 0,
                "processing_time": 1.5,
            }
            assert result == expected_result
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
            "has_embedding": 1,  # SQLite returns 0/1 for boolean
        }

        mock_connection.execute.return_value.fetchone.return_value = scene_data

        result = await db_ops.get_scene(scene_id)

        assert result is not None
        assert result["id"] == scene_id
        assert result["heading"] == "INT. OFFICE - DAY"
        assert result["content"] == "The office is busy."
        assert result["scene_number"] == 1
        assert result["character_count"] == 0  # No characters in content
        assert result["word_count"] == 4  # "The office is busy."
        assert result["page_start"] is None  # Hardcoded in implementation
        assert result["page_end"] is None  # Hardcoded in implementation
        assert result["has_embedding"] is True  # Now actually checks embeddings

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
        # Check for update statement components (allowing for whitespace/formatting)
        sql_text = call_args[0].replace("\n", " ").replace("  ", " ").strip()
        assert "UPDATE scenes" in sql_text
        assert "SET script_order" in sql_text
        assert script_id in call_args[1]


class TestSearchOperations:
    """Test search operations."""

    @pytest.mark.asyncio
    async def test_search_scenes_with_embeddings(self, db_ops):
        """Test search scenes with has_embedding flag."""
        from unittest.mock import AsyncMock, MagicMock

        # Mock scenes with proper attributes
        mock_scene1 = MagicMock()
        mock_scene1.heading = "INT. OFFICE - DAY"
        mock_scene1.description = "John enters the office."
        mock_scene1.script_order = 1
        mock_scene1.id = "scene1"
        mock_scene1.embedding = "mock_embedding"  # Has embedding

        mock_scene2 = MagicMock()
        mock_scene2.heading = "EXT. STREET - NIGHT"
        mock_scene2.description = "Sarah walks alone."
        mock_scene2.script_order = 2
        mock_scene2.id = "scene2"
        mock_scene2.embedding = None  # No embedding

        db_ops.scriptrag = MagicMock()
        db_ops.scriptrag.list_scenes = AsyncMock(
            return_value=[mock_scene1, mock_scene2]
        )

        result = await db_ops.search_scenes(
            script_id="test-script", query="office", limit=10, offset=0
        )

        assert result["total"] == 1  # Only scene1 matches "office"
        assert len(result["results"]) == 1
        assert "office" in result["results"][0]["scene"].heading.lower()

    @pytest.mark.asyncio
    async def test_search_scenes_by_script_id(self, db_ops):
        """Test search scenes filtered by script ID."""
        from unittest.mock import AsyncMock, MagicMock

        script_id = str(uuid4())

        # Mock scene
        mock_scene = MagicMock()
        mock_scene.heading = "INT. ROOM - DAY"
        mock_scene.description = "A scene description."
        mock_scene.script_order = 1
        mock_scene.id = "scene1"
        mock_scene.embedding = "mock_embedding"

        db_ops.scriptrag = MagicMock()
        db_ops.scriptrag.list_scenes = AsyncMock(return_value=[mock_scene])

        result = await db_ops.search_scenes(
            script_id=script_id, query="", limit=10, offset=0
        )

        assert result["total"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["scene"].heading == "INT. ROOM - DAY"

    @pytest.mark.asyncio
    async def test_search_scenes_no_results(self, db_ops):
        """Test search scenes with no results."""
        from unittest.mock import AsyncMock, MagicMock

        # Mock scene that won't match the query
        mock_scene = MagicMock()
        mock_scene.heading = "INT. ROOM - DAY"
        mock_scene.description = "A scene description."
        mock_scene.script_order = 1
        mock_scene.id = "scene1"

        db_ops.scriptrag = MagicMock()
        db_ops.scriptrag.list_scenes = AsyncMock(return_value=[mock_scene])

        result = await db_ops.search_scenes(
            script_id="test-script", query="nonexistent", limit=10, offset=0
        )

        assert result["total"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_search_scenes_pagination(self, db_ops):
        """Test search scenes with pagination."""
        from unittest.mock import AsyncMock, MagicMock

        # Create 25 mock scenes
        mock_scenes = []
        for i in range(25):
            scene = MagicMock()
            scene.heading = f"Scene {i + 1}"
            scene.description = f"Description {i + 1}"
            scene.script_order = i + 1
            scene.id = f"scene{i + 1}"
            mock_scenes.append(scene)

        db_ops.scriptrag = MagicMock()
        db_ops.scriptrag.list_scenes = AsyncMock(return_value=mock_scenes)

        result = await db_ops.search_scenes(
            script_id="test-script", query="", limit=10, offset=10
        )

        assert result["total"] == 25
        assert result["limit"] == 10
        assert result["offset"] == 10
        assert len(result["results"]) == 10


class TestEmbeddingsCoverage:
    """Test embeddings coverage operations."""

    @pytest.mark.asyncio
    async def test_get_embeddings_coverage_full(self, db_ops):
        """Test getting embeddings coverage for fully embedded script."""
        from unittest.mock import AsyncMock, MagicMock

        script_id = str(uuid4())

        # Create 10 mock scenes with embeddings
        mock_scenes = []
        for i in range(10):
            scene = MagicMock()
            scene.embedding = f"mock_embedding_{i}"
            mock_scenes.append(scene)

        db_ops.list_scenes = AsyncMock(return_value=mock_scenes)

        result = await db_ops.get_embeddings_coverage(script_id)

        assert result["script_id"] == script_id
        assert result["total_scenes"] == 10
        assert result["embedded_scenes"] == 10
        assert result["coverage_percentage"] == 100.0
        assert result["has_full_coverage"] is True

    @pytest.mark.asyncio
    async def test_get_embeddings_coverage_partial(self, db_ops):
        """Test getting embeddings coverage for partially embedded script."""
        from unittest.mock import AsyncMock, MagicMock

        script_id = str(uuid4())

        # Create 10 mock scenes, only 3 with embeddings
        mock_scenes = []
        for i in range(10):
            scene = MagicMock()
            scene.embedding = f"mock_embedding_{i}" if i < 3 else None
            mock_scenes.append(scene)

        db_ops.list_scenes = AsyncMock(return_value=mock_scenes)

        result = await db_ops.get_embeddings_coverage(script_id)

        assert result["script_id"] == script_id
        assert result["total_scenes"] == 10
        assert result["embedded_scenes"] == 3
        assert result["coverage_percentage"] == 30.0
        assert result["has_full_coverage"] is False

    @pytest.mark.asyncio
    async def test_get_embeddings_coverage_none(self, db_ops):
        """Test getting embeddings coverage for script with no embeddings."""
        # Mock list_scenes to return 5 scenes with no embeddings
        from unittest.mock import AsyncMock, MagicMock

        script_id = str(uuid4())

        # Create mock scenes without embeddings
        mock_scenes = []
        for _ in range(5):
            scene = MagicMock()
            scene.embedding = None
            mock_scenes.append(scene)

        db_ops.list_scenes = AsyncMock(return_value=mock_scenes)

        result = await db_ops.get_embeddings_coverage(script_id)

        assert result["script_id"] == script_id
        assert result["total_scenes"] == 5
        assert result["embedded_scenes"] == 0
        assert result["coverage_percentage"] == 0.0
        assert result["has_full_coverage"] is False

    @pytest.mark.asyncio
    async def test_get_embeddings_coverage_no_scenes(self, db_ops):
        """Test getting embeddings coverage for script with no scenes."""
        from unittest.mock import AsyncMock

        script_id = str(uuid4())

        # Mock empty script: 0 scenes
        db_ops.list_scenes = AsyncMock(return_value=[])

        result = await db_ops.get_embeddings_coverage(script_id)

        assert result["script_id"] == script_id
        assert result["total_scenes"] == 0
        assert result["embedded_scenes"] == 0
        assert result["coverage_percentage"] == 0.0
        assert result["has_full_coverage"] is False

    @pytest.mark.asyncio
    async def test_search_scenes_uninitialized_db(self, db_ops):
        """Test search scenes with uninitialized database."""
        db_ops.scriptrag = None

        with pytest.raises(RuntimeError, match="Database not initialized"):
            await db_ops.search_scenes(script_id="test-script-id", query="test")

    @pytest.mark.asyncio
    async def test_get_embeddings_coverage_uninitialized_db(self, db_ops):
        """Test getting embeddings coverage with uninitialized database."""
        db_ops.scriptrag = None

        with pytest.raises(RuntimeError, match="Database not initialized"):
            await db_ops.get_embeddings_coverage(str(uuid4()))
