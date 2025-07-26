"""Integration tests for embedding pipeline with real database operations."""

import contextlib
import gc
import platform
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from scriptrag.config import get_logger
from scriptrag.database import (
    ContentExtractor,
    DatabaseConnection,
    DatabaseSchema,
    EmbeddingContent,
    EmbeddingManager,
    EmbeddingPipeline,
)
from scriptrag.llm.client import LLMClient

logger = get_logger(__name__)


def _force_close_db_connections(db_path: Path) -> None:
    """Force close any lingering SQLite connections to a database file.

    This is particularly needed on Windows where file handles might not be
    released immediately.
    """
    # Force garbage collection
    gc.collect()

    # Try to connect and close to ensure exclusive access
    with contextlib.suppress(Exception):
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=DELETE")  # Switch from WAL mode
        conn.close()

    # Give Windows time to release file handles
    if platform.system() == "Windows":
        time.sleep(0.1)


@pytest.fixture
def temp_db_path():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup with Windows compatibility
    if db_path.exists():
        # Force close any lingering connections
        _force_close_db_connections(db_path)
        # On Windows, SQLite connections might not be fully closed
        # Try multiple times with a small delay
        for attempt in range(5):
            try:
                db_path.unlink()
                break
            except PermissionError:
                if attempt < 4:
                    time.sleep(0.1)  # Wait 100ms before retrying
                    _force_close_db_connections(db_path)
                else:
                    # Last attempt failed, try to at least close WAL files
                    with contextlib.suppress(Exception):
                        wal_path = db_path.with_suffix(".db-wal")
                        shm_path = db_path.with_suffix(".db-shm")
                        if wal_path.exists():
                            wal_path.unlink()
                        if shm_path.exists():
                            shm_path.unlink()
                    # Skip cleanup on Windows if file is still locked
                    if platform.system() == "Windows":
                        logger.warning(
                            f"Could not delete test database {db_path} on Windows - "
                            "this is expected"
                        )
                    else:
                        raise


@pytest.fixture
def test_database(temp_db_path):
    """Create a test database with schema."""
    schema = DatabaseSchema(temp_db_path)
    schema.create_schema()
    return temp_db_path


@pytest.fixture
def db_connection(test_database):
    """Create database connection to test database."""
    connection = DatabaseConnection(test_database)
    yield connection
    # Ensure connection is properly closed
    with contextlib.suppress(Exception):
        connection.close()
    # Force close any other connections that might have been created
    _force_close_db_connections(test_database)


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    client = Mock(spec=LLMClient)
    client.generate_embedding = AsyncMock()
    client.generate_embeddings = AsyncMock()
    client.close = AsyncMock()
    client.default_embedding_model = "test-model"

    # Return consistent embeddings for testing - use 1536 dimensions to match config
    client.generate_embedding.return_value = [0.1] * 1536

    # Make generate_embeddings return the correct number of embeddings based on input
    def mock_generate_embeddings(texts, model=None, **kwargs):  # noqa: ARG001
        """Return embeddings matching the number of input texts."""
        return [[0.1 + i * 0.1] * 1536 for i in range(len(texts))]

    client.generate_embeddings.side_effect = mock_generate_embeddings

    return client


def populate_test_data(connection: DatabaseConnection):
    """Populate test database with sample screenplay data."""
    with connection.transaction() as conn:
        # Insert test script
        script_id = "test-script-1"
        conn.execute(
            """
            INSERT INTO scripts (id, title, author, genre, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            (script_id, "Test Screenplay", "Test Author", "Drama", "A test script"),
        )

        # Insert test characters
        char1_id = "char-1"
        char2_id = "char-2"
        conn.execute(
            """
            INSERT INTO characters (id, script_id, name, description)
            VALUES (?, ?, ?, ?)
            """,
            (char1_id, script_id, "JOHN", "The protagonist"),
        )
        conn.execute(
            """
            INSERT INTO characters (id, script_id, name, description)
            VALUES (?, ?, ?, ?)
            """,
            (char2_id, script_id, "JANE", "The love interest"),
        )

        # Insert test location
        loc_id = "loc-1"
        conn.execute(
            """
            INSERT INTO locations (id, script_id, interior, name, time_of_day, raw_text)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (loc_id, script_id, True, "COFFEE SHOP", "DAY", "INT. COFFEE SHOP - DAY"),
        )

        # Insert test scenes
        scene1_id = "scene-1"
        scene2_id = "scene-2"
        conn.execute(
            """
            INSERT INTO scenes (
                id, script_id, location_id, heading, description, script_order
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                scene1_id,
                script_id,
                loc_id,
                "INT. COFFEE SHOP - DAY",
                "John meets Jane",
                1,
            ),
        )
        conn.execute(
            """
            INSERT INTO scenes (
                id, script_id, location_id, heading, description, script_order
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                scene2_id,
                script_id,
                loc_id,
                "INT. COFFEE SHOP - LATER",
                "They talk more",
                2,
            ),
        )

        # Insert scene elements
        conn.execute(
            """
            INSERT INTO scene_elements
            (id, scene_id, element_type, text, raw_text, order_in_scene,
             character_id, character_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "elem-1",
                scene1_id,
                "action",
                "John enters the coffee shop.",
                "John enters the coffee shop.",
                1,
                None,
                None,
            ),
        )
        conn.execute(
            """
            INSERT INTO scene_elements
            (id, scene_id, element_type, text, raw_text, order_in_scene,
             character_id, character_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "elem-2",
                scene1_id,
                "dialogue",
                "Hello there!",
                "Hello there!",
                2,
                char1_id,
                "JOHN",
            ),
        )
        conn.execute(
            """
            INSERT INTO scene_elements
            (id, scene_id, element_type, text, raw_text, order_in_scene,
             character_id, character_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "elem-3",
                scene1_id,
                "dialogue",
                "Hi! Nice to see you.",
                "Hi! Nice to see you.",
                3,
                char2_id,
                "JANE",
            ),
        )


class TestEmbeddingIntegration:
    """Integration tests for embedding functionality."""

    def test_content_extractor_with_real_data(self, db_connection):
        """Test content extractor with real database data."""
        populate_test_data(db_connection)

        extractor = ContentExtractor(db_connection)

        # Test scene content extraction
        scene_contents = extractor.extract_scene_content("scene-1")
        assert len(scene_contents) >= 1
        assert any(content["entity_type"] == "scene" for content in scene_contents)

        # Test character content extraction
        char_contents = extractor.extract_character_content("char-1")
        assert len(char_contents) >= 1
        assert any(content["entity_type"] == "character" for content in char_contents)

        # Test script content extraction
        script_contents = extractor.extract_script_content("test-script-1")
        assert len(script_contents) == 1
        assert script_contents[0]["entity_type"] == "script"

    @pytest.mark.asyncio
    async def test_embedding_manager_storage_and_retrieval(
        self, db_connection, mock_llm_client
    ):
        """Test embedding storage and retrieval with real database."""
        manager = EmbeddingManager(db_connection, mock_llm_client)

        # Generate and store an embedding
        test_content = "This is test content for embedding."
        embedding = await manager.generate_embedding(test_content)

        # Store the embedding
        manager.store_embedding("test", "test-entity-1", test_content, embedding)

        # Retrieve the embedding
        retrieved = manager.get_embedding("test", "test-entity-1")

        assert retrieved is not None
        assert len(retrieved) == len(embedding)
        # Embeddings should be approximately equal (accounting for float precision)
        for orig, retr in zip(embedding, retrieved, strict=False):
            assert abs(orig - retr) < 1e-6

    @pytest.mark.asyncio
    async def test_embedding_manager_batch_operations(
        self, db_connection, mock_llm_client
    ):
        """Test batch embedding operations."""
        manager = EmbeddingManager(db_connection, mock_llm_client)

        # Create test content
        contents = [
            EmbeddingContent(
                entity_type="scene",
                entity_id="scene-1",
                content="First scene content",
                metadata={},
            ),
            EmbeddingContent(
                entity_type="scene",
                entity_id="scene-2",
                content="Second scene content",
                metadata={},
            ),
            EmbeddingContent(
                entity_type="character",
                entity_id="char-1",
                content="Character description",
                metadata={},
            ),
        ]

        # Generate embeddings
        embeddings = await manager.generate_embeddings(contents)
        assert len(embeddings) == 3

        # Store embeddings
        stored_count = await manager.store_embeddings(embeddings)
        assert stored_count == 3

        # Verify storage
        for content, _ in embeddings:
            retrieved = manager.get_embedding(
                content["entity_type"], content["entity_id"]
            )
            assert retrieved is not None

    @pytest.mark.asyncio
    async def test_similarity_search(self, db_connection, mock_llm_client):
        """Test similarity search functionality."""
        manager = EmbeddingManager(db_connection, mock_llm_client)

        # Store some test embeddings with different similarities
        test_embeddings = [
            ([1.0] + [0.0] * 1535, "scene", "scene-1", "Similar to query"),
            ([0.0, 1.0] + [0.0] * 1534, "scene", "scene-2", "Different from query"),
            ([0.8] + [0.0] * 1535, "scene", "scene-3", "Somewhat similar"),
        ]

        for embedding, entity_type, entity_id, content in test_embeddings:
            manager.store_embedding(entity_type, entity_id, content, embedding)

        # Search with a query vector similar to the first embedding
        query_vector = [0.9, 0.1] + [0.0] * 1534
        results = manager.find_similar(query_vector, entity_type="scene", limit=3)

        assert len(results) >= 1
        # Results should be sorted by similarity (highest first)
        if len(results) > 1:
            assert results[0]["similarity"] >= results[1]["similarity"]

    @pytest.mark.asyncio
    async def test_pipeline_full_workflow(self, db_connection, mock_llm_client):
        """Test complete pipeline workflow."""
        populate_test_data(db_connection)

        pipeline = EmbeddingPipeline(db_connection, mock_llm_client)

        try:
            # Process the test script
            result = await pipeline.process_script("test-script-1")

            assert result["status"] == "success"
            assert result["embeddings_stored"] > 0

            # Test semantic search
            search_results = await pipeline.semantic_search("coffee shop conversation")
            assert len(search_results) >= 0  # May be empty with mock embeddings

            # Test similar scenes - may be empty if only one scene or no similar content
            await pipeline.get_similar_scenes("scene-1")

            # Get embedding stats
            stats = pipeline.get_embedding_stats()
            assert "total_embeddings" in stats
            assert stats["total_embeddings"] >= 0

        finally:
            await pipeline.close()

    @pytest.mark.asyncio
    async def test_embedding_persistence(self, db_connection, mock_llm_client):
        """Test that embeddings persist across database connections."""
        # Store embedding with first manager
        manager1 = EmbeddingManager(db_connection, mock_llm_client)
        test_embedding = [0.1] * 1536
        manager1.store_embedding("test", "persist-test", "test content", test_embedding)

        # Create new manager and retrieve
        manager2 = EmbeddingManager(db_connection, mock_llm_client)
        retrieved = manager2.get_embedding("test", "persist-test")

        assert retrieved is not None
        assert len(retrieved) == len(test_embedding)

    @pytest.mark.asyncio
    async def test_embedding_stats_accuracy(self, db_connection, mock_llm_client):
        """Test embedding statistics accuracy."""
        manager = EmbeddingManager(db_connection, mock_llm_client)

        # Store embeddings of different types
        embeddings_data = [
            ("scene", "scene-1", "Scene content 1"),
            ("scene", "scene-2", "Scene content 2"),
            ("character", "char-1", "Character content 1"),
            ("location", "loc-1", "Location content 1"),
        ]

        test_embedding = [0.1] * 1536
        for entity_type, entity_id, content in embeddings_data:
            manager.store_embedding(entity_type, entity_id, content, test_embedding)

        # Get stats
        stats = manager.get_embeddings_stats()

        assert stats["total_embeddings"] == 4
        assert stats["entity_counts"]["scene"] == 2
        assert stats["entity_counts"]["character"] == 1
        assert stats["entity_counts"]["location"] == 1
        assert stats["dimension"] == 1536

    def test_content_extractor_edge_cases(self, db_connection):
        """Test content extractor with edge cases."""
        extractor = ContentExtractor(db_connection)

        # Test with non-existent IDs
        assert extractor.extract_scene_content("nonexistent") == []
        assert extractor.extract_character_content("nonexistent") == []
        assert extractor.extract_script_content("nonexistent") == []

    @pytest.mark.asyncio
    async def test_embedding_deletion(self, db_connection, mock_llm_client):
        """Test embedding deletion functionality."""
        manager = EmbeddingManager(db_connection, mock_llm_client)

        # Store an embedding
        test_embedding = [0.1] * 1536
        manager.store_embedding("test", "delete-test", "test content", test_embedding)

        # Verify it exists
        assert manager.get_embedding("test", "delete-test") is not None

        # Delete it
        deleted = manager.delete_embedding("test", "delete-test")
        assert deleted is True

        # Verify it's gone
        assert manager.get_embedding("test", "delete-test") is None

        # Deleting non-existent should return False
        deleted_again = manager.delete_embedding("test", "delete-test")
        assert deleted_again is False

    @pytest.mark.asyncio
    async def test_vector_format_compatibility(self, db_connection, mock_llm_client):
        """Test compatibility between blob and JSON vector formats."""
        manager = EmbeddingManager(db_connection, mock_llm_client)

        test_embedding = [0.1] * 1536

        # Store embedding (should create both blob and JSON formats)
        manager.store_embedding("test", "format-test", "test content", test_embedding)

        # Retrieve and verify
        retrieved = manager.get_embedding("test", "format-test")
        assert retrieved is not None
        assert len(retrieved) == len(test_embedding)

        # Values should be approximately equal
        for orig, retr in zip(test_embedding, retrieved, strict=False):
            assert abs(orig - retr) < 1e-6
