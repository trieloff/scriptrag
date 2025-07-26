"""Comprehensive tests for scene management API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from scriptrag.api.app import create_app


@pytest.fixture
def mock_llm_client():
    """Mock LLM client to avoid initialization errors in tests."""
    with patch("scriptrag.database.embedding_pipeline.LLMClient") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_db_ops():
    """Mock database operations."""
    with patch("scriptrag.api.v1.endpoints.scenes.DatabaseOperations") as _:
        mock_instance = AsyncMock()
        yield mock_instance


@pytest.fixture
def client(mock_llm_client):
    """Create test client with mocked dependencies."""
    _ = mock_llm_client  # Mark as used
    app = create_app()
    with TestClient(app) as client:
        yield client


class TestSceneEndpoints:
    """Test suite for scene management endpoints."""

    def test_get_scene_success(self, client):
        """Test successful scene retrieval."""
        scene_id = str(uuid4())
        script_id = str(uuid4())

        # Mock the database response
        mock_scene = {
            "id": scene_id,
            "script_id": script_id,
            "scene_number": 1,
            "heading": "INT. COFFEE SHOP - DAY",
            "content": "The coffee shop buzzes with activity.",
            "character_count": 3,
            "word_count": 6,
            "page_start": 1.0,
            "page_end": 1.5,
            "has_embedding": True,
        }

        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_scene.return_value = mock_scene
            mock_get_db.return_value = mock_db

            response = client.get(f"/api/v1/scenes/{scene_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == scene_id
            assert data["script_id"] == script_id
            assert data["scene_number"] == 1
            assert data["heading"] == "INT. COFFEE SHOP - DAY"
            mock_db.get_scene.assert_called_once_with(scene_id)

    def test_get_scene_not_found(self, client):
        """Test getting non-existent scene."""
        scene_id = str(uuid4())

        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_scene.return_value = None
            mock_get_db.return_value = mock_db

            response = client.get(f"/api/v1/scenes/{scene_id}")

            assert response.status_code == 404
            assert "Scene not found" in response.json()["detail"]

    def test_get_scene_database_error(self, client):
        """Test database error during scene retrieval."""
        scene_id = str(uuid4())

        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_scene.side_effect = Exception("Database connection failed")
            mock_get_db.return_value = mock_db

            response = client.get(f"/api/v1/scenes/{scene_id}")

            assert response.status_code == 500
            assert "Failed to get scene" in response.json()["detail"]

    def test_create_scene_success(self, client):
        """Test successful scene creation."""
        script_id = str(uuid4())
        scene_id = str(uuid4())

        scene_data = {
            "scene_number": 5,
            "heading": "EXT. BEACH - SUNSET",
            "content": "Waves crash against the shore as the sun sets.",
        }

        mock_script = {"id": script_id, "title": "Test Script"}
        mock_scene = {
            "id": scene_id,
            "script_id": script_id,
            "scene_number": 5,
            "heading": "EXT. BEACH - SUNSET",
            "content": "Waves crash against the shore as the sun sets.",
            "character_count": 0,
            "word_count": 9,
            "page_start": 5.0,
            "page_end": 5.2,
            "has_embedding": False,
        }

        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_script.return_value = mock_script
            mock_db.create_scene.return_value = scene_id
            mock_db.get_scene.return_value = mock_scene
            mock_get_db.return_value = mock_db

            response = client.post(
                f"/api/v1/scenes/?script_id={script_id}", json=scene_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == scene_id
            assert data["script_id"] == script_id
            assert data["scene_number"] == 5
            assert data["heading"] == "EXT. BEACH - SUNSET"

            # Verify method calls
            mock_db.get_script.assert_called_once_with(script_id)
            mock_db.create_scene.assert_called_once_with(
                script_id=script_id,
                scene_number=5,
                heading="EXT. BEACH - SUNSET",
                content="Waves crash against the shore as the sun sets.",
            )

    def test_create_scene_script_not_found(self, client):
        """Test scene creation with non-existent script."""
        script_id = str(uuid4())

        scene_data = {
            "scene_number": 1,
            "heading": "INT. ROOM - DAY",
            "content": "A simple room.",
        }

        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_script.return_value = None
            mock_get_db.return_value = mock_db

            response = client.post(
                f"/api/v1/scenes/?script_id={script_id}", json=scene_data
            )

            assert response.status_code == 404
            assert "Script not found" in response.json()["detail"]

    def test_create_scene_database_error(self, client):
        """Test database error during scene creation."""
        script_id = str(uuid4())

        scene_data = {
            "scene_number": 1,
            "heading": "INT. ROOM - DAY",
            "content": "A simple room.",
        }

        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_script.return_value = {"id": script_id}
            mock_db.create_scene.side_effect = Exception("Database write failed")
            mock_get_db.return_value = mock_db

            response = client.post(
                f"/api/v1/scenes/?script_id={script_id}", json=scene_data
            )

            assert response.status_code == 500
            assert "Failed to create scene" in response.json()["detail"]

    def test_update_scene_success(self, client):
        """Test successful scene update."""
        scene_id = str(uuid4())
        script_id = str(uuid4())

        update_data = {
            "scene_number": 3,
            "heading": "INT. OFFICE - NIGHT",
            "content": "The office is dimly lit.",
        }

        mock_original_scene = {
            "id": scene_id,
            "script_id": script_id,
            "scene_number": 2,
            "heading": "INT. OFFICE - DAY",
            "content": "The office bustles with activity.",
            "character_count": 5,
            "word_count": 6,
            "page_start": 2.0,
            "page_end": 2.5,
            "has_embedding": True,
        }

        mock_updated_scene = {
            **mock_original_scene,
            "scene_number": 3,
            "heading": "INT. OFFICE - NIGHT",
            "content": "The office is dimly lit.",
            "word_count": 5,
        }

        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_scene.side_effect = [mock_original_scene, mock_updated_scene]
            mock_db.update_scene.return_value = None
            mock_get_db.return_value = mock_db

            response = client.patch(f"/api/v1/scenes/{scene_id}", json=update_data)

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == scene_id
            assert data["scene_number"] == 3
            assert data["heading"] == "INT. OFFICE - NIGHT"
            assert data["content"] == "The office is dimly lit."

            mock_db.update_scene.assert_called_once_with(
                scene_id=scene_id,
                scene_number=3,
                heading="INT. OFFICE - NIGHT",
                content="The office is dimly lit.",
            )

    def test_update_scene_not_found(self, client):
        """Test updating non-existent scene."""
        scene_id = str(uuid4())

        update_data = {
            "scene_number": 1,
            "heading": "INT. ROOM - DAY",
            "content": "Updated content.",
        }

        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_scene.return_value = None
            mock_get_db.return_value = mock_db

            response = client.patch(f"/api/v1/scenes/{scene_id}", json=update_data)

            assert response.status_code == 404
            assert "Scene not found" in response.json()["detail"]

    def test_delete_scene_success(self, client):
        """Test successful scene deletion."""
        scene_id = str(uuid4())

        mock_scene = {
            "id": scene_id,
            "script_id": str(uuid4()),
            "scene_number": 1,
            "heading": "INT. ROOM - DAY",
        }

        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_scene.return_value = mock_scene
            mock_db.delete_scene.return_value = None
            mock_get_db.return_value = mock_db

            response = client.delete(f"/api/v1/scenes/{scene_id}")

            assert response.status_code == 200
            assert (
                f"Scene {scene_id} deleted successfully" in response.json()["message"]
            )
            mock_db.delete_scene.assert_called_once_with(scene_id)

    def test_delete_scene_not_found(self, client):
        """Test deleting non-existent scene."""
        scene_id = str(uuid4())

        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_scene.return_value = None
            mock_get_db.return_value = mock_db

            response = client.delete(f"/api/v1/scenes/{scene_id}")

            assert response.status_code == 404
            assert "Scene not found" in response.json()["detail"]

    def test_inject_scene_after_success(self, client):
        """Test successful scene injection after another scene."""
        ref_scene_id = str(uuid4())
        script_id = str(uuid4())
        new_scene_id = str(uuid4())

        scene_data = {
            "scene_number": 99,  # Will be overridden
            "heading": "INT. HALLWAY - DAY",
            "content": "A long hallway stretches ahead.",
        }

        mock_ref_scene = {
            "id": ref_scene_id,
            "script_id": script_id,
            "scene_number": 5,
            "heading": "INT. ROOM - DAY",
        }

        mock_new_scene = {
            "id": new_scene_id,
            "script_id": script_id,
            "scene_number": 6,
            "heading": "INT. HALLWAY - DAY",
            "content": "A long hallway stretches ahead.",
            "character_count": 0,
            "word_count": 6,
            "page_start": 6.0,
            "page_end": 6.2,
            "has_embedding": False,
        }

        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_scene.side_effect = [mock_ref_scene, mock_new_scene]
            mock_db.shift_scene_numbers.return_value = None
            mock_db.create_scene.return_value = new_scene_id
            mock_get_db.return_value = mock_db

            response = client.post(
                f"/api/v1/scenes/{ref_scene_id}/inject-after", json=scene_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == new_scene_id
            assert data["scene_number"] == 6
            assert data["heading"] == "INT. HALLWAY - DAY"

            # Verify method calls
            mock_db.shift_scene_numbers.assert_called_once_with(
                script_id=script_id, from_scene_number=6
            )
            mock_db.create_scene.assert_called_once_with(
                script_id=script_id,
                scene_number=6,
                heading="INT. HALLWAY - DAY",
                content="A long hallway stretches ahead.",
            )

    def test_inject_scene_after_ref_not_found(self, client):
        """Test scene injection with non-existent reference scene."""
        ref_scene_id = str(uuid4())

        scene_data = {
            "scene_number": 1,
            "heading": "INT. ROOM - DAY",
            "content": "Content.",
        }

        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_scene.return_value = None
            mock_get_db.return_value = mock_db

            response = client.post(
                f"/api/v1/scenes/{ref_scene_id}/inject-after", json=scene_data
            )

            assert response.status_code == 404
            assert "Reference scene not found" in response.json()["detail"]

    def test_inject_scene_after_database_error(self, client):
        """Test database error during scene injection."""
        ref_scene_id = str(uuid4())
        script_id = str(uuid4())

        scene_data = {
            "scene_number": 1,
            "heading": "INT. ROOM - DAY",
            "content": "Content.",
        }

        mock_ref_scene = {
            "id": ref_scene_id,
            "script_id": script_id,
            "scene_number": 5,
        }

        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_scene.return_value = mock_ref_scene
            mock_db.shift_scene_numbers.side_effect = Exception("Database error")
            mock_get_db.return_value = mock_db

            response = client.post(
                f"/api/v1/scenes/{ref_scene_id}/inject-after", json=scene_data
            )

            assert response.status_code == 500
            assert "Failed to inject scene" in response.json()["detail"]


class TestSceneEndpointValidation:
    """Test input validation for scene endpoints."""

    def test_create_scene_invalid_data(self, client):
        """Test scene creation with invalid data."""
        script_id = str(uuid4())

        # Missing required fields
        invalid_data = {
            "scene_number": -1,  # Invalid: must be positive
            # Missing heading and content
        }

        response = client.post(
            f"/api/v1/scenes/?script_id={script_id}", json=invalid_data
        )

        assert response.status_code == 422  # Validation error

    def test_update_scene_partial_data(self, client):
        """Test scene update with partial data."""
        scene_id = str(uuid4())

        # Partial update should be allowed
        partial_data = {
            "heading": "INT. NEW LOCATION - DAY",
            # Other fields can be omitted
        }

        mock_scene = {
            "id": scene_id,
            "script_id": str(uuid4()),
            "scene_number": 1,
            "heading": "INT. OLD LOCATION - DAY",
            "content": "Content",
            "character_count": 0,
            "word_count": 1,
            "page_start": 1.0,
            "page_end": 1.1,
            "has_embedding": False,
        }

        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_scene.side_effect = [
                mock_scene,
                {**mock_scene, "heading": "INT. NEW LOCATION - DAY"},
            ]
            mock_db.update_scene.return_value = None
            mock_get_db.return_value = mock_db

            response = client.patch(f"/api/v1/scenes/{scene_id}", json=partial_data)

            assert response.status_code == 200
            data = response.json()
            assert data["heading"] == "INT. NEW LOCATION - DAY"
