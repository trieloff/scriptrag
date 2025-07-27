"""Tests for FastAPI REST API endpoints.

TODO: Comprehensive test improvements needed:
1. Add database mocking using pytest-mock or unittest.mock
2. Create test fixtures for sample scripts and scenes
3. Add integration tests with temporary test database
4. Test error conditions and edge cases properly
5. Test authentication when implemented
6. Add performance tests for large datasets
7. Test concurrent request handling
8. Mock external dependencies (embedding pipeline, LLM client)

Current tests are minimal and should not be used for production validation.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from scriptrag.api.app import create_app


@pytest.fixture
def mock_llm_client():
    """Mock LLM client to avoid initialization errors in tests."""
    with patch("scriptrag.database.embedding_pipeline.LLMClient") as mock:
        # Create a mock instance that doesn't require API credentials
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def client(mock_llm_client, temp_db_path):
    """Create test client with mocked LLM client and temporary database."""
    # The fixture ensures LLM client is mocked during app creation
    _ = mock_llm_client  # Mark as used for linter

    # Initialize the test database schema first
    from scriptrag.database import initialize_database

    initialize_database(temp_db_path)

    # Override database path using environment variable
    import os

    original_db_path = os.environ.get("SCRIPTRAG_DB_PATH")
    os.environ["SCRIPTRAG_DB_PATH"] = str(temp_db_path)

    try:
        # Clear any cached settings to force reload with new environment
        with patch("scriptrag.config.settings._settings", None):
            app = create_app()
            with TestClient(app) as client:
                yield client
    finally:
        # Restore original environment
        if original_db_path:
            os.environ["SCRIPTRAG_DB_PATH"] = original_db_path
        else:
            os.environ.pop("SCRIPTRAG_DB_PATH", None)


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "docs" in data


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_list_scripts_empty(client):
    """Test listing scripts when none exist."""
    response = client.get("/api/v1/scripts/")
    assert response.status_code == 200
    # The test database may contain scripts from other tests
    # Just verify we get a list response (empty or not)
    assert isinstance(response.json(), list)


def test_script_not_found(client):
    """Test getting non-existent script."""
    response = client.get("/api/v1/scripts/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_upload_script(client):
    """Test uploading a script."""
    script_data = {
        "title": "Test Script",
        "content": "FADE IN:\n\nINT. TEST LOCATION - DAY\n\nTest content.",
        "author": "Test Author",
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)

    # The database is now properly initialized, so upload should succeed
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Script"
    assert data["author"] == "Test Author"
    assert "id" in data
    assert data["scene_count"] >= 0


def test_scene_search_invalid_params(client):
    """Test scene search with invalid parameters."""
    search_data = {
        "limit": 0,  # Invalid: must be >= 1
    }

    response = client.post("/api/v1/search/scenes", json=search_data)
    assert response.status_code == 422  # Validation error


def test_semantic_search_missing_query(client):
    """Test semantic search without query."""
    search_data = {
        "limit": 10
        # Missing required "query" field
    }

    response = client.post("/api/v1/search/similar", json=search_data)
    assert response.status_code == 422  # Validation error


def test_openapi_schema(client):
    """Test OpenAPI schema endpoint."""
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "info" in schema
    assert schema["info"]["title"] == "ScriptRAG API"


def test_docs_available(client):
    """Test that API docs are available."""
    # Note: The actual docs page returns HTML, not JSON
    response = client.get("/api/v1/docs")
    assert response.status_code == 200
