"""Comprehensive tests for embedding generation API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_llm_client():
    """Mock LLM client to avoid initialization errors in tests."""
    with patch("scriptrag.database.embedding_pipeline.LLMClient") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def client(mock_llm_client):
    """Create test client with mocked dependencies."""
    _ = mock_llm_client  # Mark as used

    from fastapi import FastAPI

    from scriptrag.api.db_operations import DatabaseOperations
    from scriptrag.api.v1.api import api_router

    # Create app without lifespan to avoid database initialization
    app = FastAPI(
        title="ScriptRAG API",
        description="Graph-Based Screenwriting Assistant REST API",
        version="1.0.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
    )

    # Include API routers
    app.include_router(api_router, prefix="/api/v1")

    # Manually set up app state with mocked database operations
    mock_db_ops = AsyncMock(spec=DatabaseOperations)
    app.state.db_ops = mock_db_ops
    app.state.settings = None  # Not needed for embedding tests

    with TestClient(app) as client:
        # Store original client for reuse
        client._original_mock = mock_db_ops
        yield client


class TestEmbeddingGenerationEndpoint:
    """Test suite for embedding generation endpoint."""

    def test_generate_embeddings_success(self, client):
        """Test successful embedding generation for a script."""
        script_id = str(uuid4())

        request_data = {"regenerate": False}

        mock_script = {
            "id": script_id,
            "title": "Test Script",
            "author": "Test Author",
        }

        mock_result = {
            "scenes_processed": 10,
            "scenes_skipped": 2,
            "processing_time": 5.4,
        }

        # Configure the mock database operations from the client fixture
        mock_db_ops = client.app.state.db_ops
        mock_db_ops.get_script.return_value = mock_script
        mock_db_ops.generate_embeddings.return_value = mock_result

        response = client.post(
            f"/api/v1/embeddings/scripts/{script_id}/generate", json=request_data
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert data["status"] == "success"
        assert data["message"] == "Embeddings generated successfully"
        assert data["script_id"] == script_id
        assert data["scenes_processed"] == 10
        assert data["scenes_skipped"] == 2
        assert data["processing_time"] == 5.4

        # Verify method calls
        mock_db_ops.get_script.assert_called_once_with(script_id)
        mock_db_ops.generate_embeddings.assert_called_once_with(
            script_id, regenerate=False
        )

    def test_generate_embeddings_with_regenerate(self, client):
        """Test embedding generation with regenerate flag."""
        script_id = str(uuid4())

        # Reset mock state for clean test
        client.app.state.db_ops.reset_mock()

        request_data = {"regenerate": True}

        mock_script = {"id": script_id, "title": "Test Script"}
        mock_result = {
            "scenes_processed": 15,
            "scenes_skipped": 0,
            "processing_time": 8.2,
        }

        # Configure the mock that's already set up in the client fixture
        client.app.state.db_ops.get_script.return_value = mock_script
        client.app.state.db_ops.generate_embeddings.return_value = mock_result

        response = client.post(
            f"/api/v1/embeddings/scripts/{script_id}/generate", json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["scenes_processed"] == 15
        assert data["scenes_skipped"] == 0

        # Verify regenerate was passed correctly
        client.app.state.db_ops.generate_embeddings.assert_called_once_with(
            script_id, regenerate=True
        )

    def test_generate_embeddings_script_not_found(self, client):
        """Test embedding generation for non-existent script."""
        script_id = str(uuid4())

        # Reset mock state for clean test
        client.app.state.db_ops.reset_mock()

        request_data = {"regenerate": False}

        # Configure the mock to raise ValueError for script not found
        client.app.state.db_ops.generate_embeddings.side_effect = ValueError(
            f"Script {script_id} not found"
        )

        response = client.post(
            f"/api/v1/embeddings/scripts/{script_id}/generate", json=request_data
        )

        assert response.status_code == 404
        assert "Script not found" in response.json()["detail"]

    def test_generate_embeddings_processing_error(self, client):
        """Test error during embedding generation."""
        script_id = str(uuid4())

        # Reset mock state for clean test
        client.app.state.db_ops.reset_mock()

        request_data = {"regenerate": False}

        mock_script = {"id": script_id, "title": "Test Script"}

        # Configure the mock that's already set up in the client fixture
        client.app.state.db_ops.get_script.return_value = mock_script
        client.app.state.db_ops.generate_embeddings.side_effect = Exception(
            "Embedding model unavailable"
        )

        response = client.post(
            f"/api/v1/embeddings/scripts/{script_id}/generate", json=request_data
        )

        assert response.status_code == 500
        assert "Failed to generate embeddings" in response.json()["detail"]

    def test_generate_embeddings_default_regenerate(self, client):
        """Test embedding generation with default regenerate value."""
        script_id = str(uuid4())

        # Reset mock state for clean test
        client.app.state.db_ops.reset_mock()

        # Empty request body - should use default regenerate=False
        request_data = {}

        mock_script = {"id": script_id, "title": "Test Script"}
        mock_result = {
            "scenes_processed": 5,
            "scenes_skipped": 5,
            "processing_time": 2.1,
        }

        # Configure the mock that's already set up in the client fixture
        client.app.state.db_ops.get_script.return_value = mock_script
        client.app.state.db_ops.generate_embeddings.return_value = mock_result

        response = client.post(
            f"/api/v1/embeddings/scripts/{script_id}/generate", json=request_data
        )

        assert response.status_code == 200
        # Verify default regenerate=False was used
        client.app.state.db_ops.generate_embeddings.assert_called_once_with(
            script_id, regenerate=False
        )


class TestEmbeddingStatusEndpoint:
    """Test suite for embedding status endpoint."""

    def test_get_embedding_status_complete(self, client):
        """Test embedding status for fully processed script."""
        script_id = str(uuid4())

        # Reset mock state for clean test
        client.app.state.db_ops.reset_mock()

        # Mock script with all scenes having embeddings
        mock_scenes = [
            MagicMock(embedding={"vector": [0.1, 0.2, 0.3]}),
            MagicMock(embedding={"vector": [0.4, 0.5, 0.6]}),
            MagicMock(embedding={"vector": [0.7, 0.8, 0.9]}),
        ]

        mock_script = MagicMock()
        mock_script.id = script_id
        mock_script.title = "Test Script"
        mock_script.scenes = mock_scenes

        # Configure the mock that's already set up in the client fixture
        client.app.state.db_ops.get_script.return_value = mock_script

        response = client.get(f"/api/v1/embeddings/scripts/{script_id}/status")

        assert response.status_code == 200
        data = response.json()

        assert data["script_id"] == script_id
        assert data["total_scenes"] == 3
        assert data["scenes_with_embeddings"] == 3
        assert data["completion_percentage"] == 100.0
        assert data["is_complete"] is True

    def test_get_embedding_status_partial(self, client):
        """Test embedding status for partially processed script."""
        script_id = str(uuid4())

        # Mock script with some scenes having embeddings
        mock_scenes = [
            MagicMock(embedding={"vector": [0.1, 0.2, 0.3]}),
            MagicMock(embedding=None),
            MagicMock(embedding={"vector": [0.7, 0.8, 0.9]}),
            MagicMock(embedding=None),
        ]

        mock_script = MagicMock()
        mock_script.id = script_id
        mock_script.title = "Test Script"
        mock_script.scenes = mock_scenes

        # Configure the mock that's already set up in the client fixture
        client.app.state.db_ops.get_script.return_value = mock_script

        response = client.get(f"/api/v1/embeddings/scripts/{script_id}/status")

        assert response.status_code == 200
        data = response.json()

        assert data["script_id"] == script_id
        assert data["total_scenes"] == 4
        assert data["scenes_with_embeddings"] == 2
        assert data["completion_percentage"] == 50.0
        assert data["is_complete"] is False

    def test_get_embedding_status_no_scenes(self, client):
        """Test embedding status for script with no scenes."""
        script_id = str(uuid4())

        mock_script = MagicMock()
        mock_script.id = script_id
        mock_script.title = "Empty Script"
        mock_script.scenes = []

        # Configure the mock that's already set up in the client fixture
        client.app.state.db_ops.get_script.return_value = mock_script

        response = client.get(f"/api/v1/embeddings/scripts/{script_id}/status")

        assert response.status_code == 200
        data = response.json()

        assert data["total_scenes"] == 0
        assert data["scenes_with_embeddings"] == 0
        assert data["completion_percentage"] == 0
        assert data["is_complete"] is True  # Empty script is considered complete

    def test_get_embedding_status_script_not_found(self, client):
        """Test embedding status for non-existent script."""
        script_id = str(uuid4())

        # Configure the mock that's already set up in the client fixture
        client.app.state.db_ops.get_script.return_value = None

        response = client.get(f"/api/v1/embeddings/scripts/{script_id}/status")

        assert response.status_code == 404
        assert "Script not found" in response.json()["detail"]

    def test_get_embedding_status_database_error(self, client):
        """Test database error during status retrieval."""
        script_id = str(uuid4())

        # Configure the mock that's already set up in the client fixture
        client.app.state.db_ops.get_script.side_effect = Exception(
            "Database connection lost"
        )

        response = client.get(f"/api/v1/embeddings/scripts/{script_id}/status")

        assert response.status_code == 500
        assert "Failed to get embedding status" in response.json()["detail"]

    def test_get_embedding_status_no_embeddings(self, client):
        """Test embedding status for script with no embeddings generated."""
        script_id = str(uuid4())

        # Mock script with scenes but no embeddings
        mock_scenes = [
            MagicMock(embedding=None),
            MagicMock(embedding=None),
            MagicMock(embedding=None),
        ]

        mock_script = MagicMock()
        mock_script.id = script_id
        mock_script.title = "Test Script"
        mock_script.scenes = mock_scenes

        # Configure the mock that's already set up in the client fixture
        client.app.state.db_ops.get_script.return_value = mock_script

        response = client.get(f"/api/v1/embeddings/scripts/{script_id}/status")

        assert response.status_code == 200
        data = response.json()

        assert data["total_scenes"] == 3
        assert data["scenes_with_embeddings"] == 0
        assert data["completion_percentage"] == 0.0
        assert data["is_complete"] is False
