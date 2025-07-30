"""Tests for API input validation.

This module tests validation for screenplay uploads to ensure:
- Titles are not empty or just whitespace
- Content is valid Fountain format
- Author field validation
- File upload validation
- Edge cases and security considerations
"""

from unittest.mock import MagicMock, patch

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
def client(mock_llm_client, temp_db_path):
    """Create test client with mocked LLM client and temporary database."""
    _ = mock_llm_client  # Mark as used for linter

    from scriptrag.database import initialize_database

    initialize_database(temp_db_path)

    import os

    original_db_path = os.environ.get("SCRIPTRAG_DB_PATH")
    os.environ["SCRIPTRAG_DB_PATH"] = str(temp_db_path)

    try:
        with patch("scriptrag.config.settings._settings", None):
            app = create_app()
            with TestClient(app) as client:
                yield client
    finally:
        if original_db_path:
            os.environ["SCRIPTRAG_DB_PATH"] = original_db_path
        else:
            os.environ.pop("SCRIPTRAG_DB_PATH", None)


class TestScriptUploadValidation:
    """Test script upload validation."""

    def test_upload_empty_title(self, client):
        """Test uploading script with empty title."""
        script_data = {
            "title": "",
            "content": "FADE IN:\n\nINT. TEST - DAY\n\nTest content.",
            "author": "Test Author",
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        # Check for either Pydantic's min_length error or our custom validator
        assert any(
            (
                (
                    "title" in str(error).lower()
                    or ("loc" in str(error) and "'title'" in str(error))
                )
                and (
                    "at least 1 character" in str(error).lower()
                    or "empty" in str(error).lower()
                )
            )
            for error in errors
        )

    def test_upload_whitespace_title(self, client):
        """Test uploading script with whitespace-only title."""
        script_data = {
            "title": "   \t\n  ",
            "content": "FADE IN:\n\nINT. TEST - DAY\n\nTest content.",
            "author": "Test Author",
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        # Our custom validator should catch whitespace-only titles
        assert any(
            "title" in str(error).lower()
            and ("whitespace" in str(error).lower() or "empty" in str(error).lower())
            for error in errors
        )

    def test_upload_title_too_long(self, client):
        """Test uploading script with excessively long title."""
        script_data = {
            "title": "A" * 201,  # 201 characters
            "content": "FADE IN:\n\nINT. TEST - DAY\n\nTest content.",
            "author": "Test Author",
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(
            "title" in str(error).lower() and "200" in str(error) for error in errors
        )

    def test_upload_title_special_chars_only(self, client):
        """Test uploading script with title containing only special characters."""
        script_data = {
            "title": "!!!@@@###$$$",
            "content": "FADE IN:\n\nINT. TEST - DAY\n\nTest content.",
            "author": "Test Author",
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(
            "title" in str(error).lower() and "alphanumeric" in str(error).lower()
            for error in errors
        )

    def test_upload_empty_content(self, client):
        """Test uploading script with empty content."""
        script_data = {"title": "Test Script", "content": "", "author": "Test Author"}

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(
            (
                (
                    "content" in str(error).lower()
                    or ("loc" in str(error) and "'content'" in str(error))
                )
                and (
                    "at least 1 character" in str(error).lower()
                    or "empty" in str(error).lower()
                )
            )
            for error in errors
        )

    def test_upload_whitespace_content(self, client):
        """Test uploading script with whitespace-only content."""
        script_data = {
            "title": "Test Script",
            "content": "   \t\n  ",
            "author": "Test Author",
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(
            "content" in str(error).lower() and "whitespace" in str(error).lower()
            for error in errors
        )

    def test_upload_content_too_large(self, client):
        """Test uploading script with excessively large content."""
        # Create content larger than 10MB (reasonable limit for a screenplay)
        script_data = {
            "title": "Test Script",
            "content": "FADE IN:\n\n" + "A" * (10 * 1024 * 1024 + 1),  # 10MB + 1 byte
            "author": "Test Author",
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(
            (
                (
                    "content" in str(error).lower()
                    or ("loc" in str(error) and "'content'" in str(error))
                )
                and (
                    "10485760" in str(error)
                    or "at most" in str(error).lower()
                    or "size" in str(error).lower()
                )
            )
            for error in errors
        )

    def test_upload_invalid_fountain_format(self, client):
        """Test uploading script with no recognizable Fountain elements."""
        script_data = {
            "title": "Test Script",
            "content": "This is just plain text with no screenplay formatting.",
            "author": "Test Author",
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(
            "fountain" in str(error).lower() or "screenplay" in str(error).lower()
            for error in errors
        )

    def test_upload_minimal_valid_fountain(self, client):
        """Test uploading script with minimal valid Fountain content."""
        script_data = {
            "title": "Test Script",
            "content": "INT. LOCATION - DAY",  # Minimal scene heading
            "author": "Test Author",
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Script"

    def test_upload_author_whitespace(self, client):
        """Test uploading script with whitespace-only author."""
        script_data = {
            "title": "Test Script",
            "content": "FADE IN:\n\nINT. TEST - DAY\n\nTest content.",
            "author": "   \t\n  ",
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(
            "author" in str(error).lower() and "whitespace" in str(error).lower()
            for error in errors
        )

    def test_upload_author_too_long(self, client):
        """Test uploading script with excessively long author name."""
        script_data = {
            "title": "Test Script",
            "content": "FADE IN:\n\nINT. TEST - DAY\n\nTest content.",
            "author": "A" * 101,  # 101 characters
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(
            "author" in str(error).lower() and "100" in str(error) for error in errors
        )

    def test_upload_author_special_chars_only(self, client):
        """Test uploading script with author containing only special characters."""
        script_data = {
            "title": "Test Script",
            "content": "FADE IN:\n\nINT. TEST - DAY\n\nTest content.",
            "author": "!!!@@@###$$$",
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(
            "author" in str(error).lower() and "alphanumeric" in str(error).lower()
            for error in errors
        )

    def test_upload_author_optional(self, client):
        """Test uploading script without author (should be valid)."""
        script_data = {
            "title": "Test Script",
            "content": "FADE IN:\n\nINT. TEST - DAY\n\nTest content.",
            # No author field
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Script"
        assert data["author"] is None

    def test_upload_valid_script(self, client):
        """Test uploading a valid script with all fields."""
        script_data = {
            "title": "The Great Adventure",
            "content": """FADE IN:

INT. COFFEE SHOP - DAY

A cozy neighborhood coffee shop. SARAH (30s), a writer, sits at a corner table.

SARAH
(to herself)
Just one more scene...

She types frantically, then pauses, looking satisfied.

FADE OUT.""",
            "author": "Jane Doe",
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "The Great Adventure"
        assert data["author"] == "Jane Doe"
        assert data["scene_count"] >= 1

    def test_upload_fountain_with_dialogue(self, client):
        """Test that content with dialogue is recognized as valid Fountain."""
        script_data = {
            "title": "Dialogue Test",
            "content": """CHARACTER NAME
This is dialogue.

ANOTHER CHARACTER
This is more dialogue.""",
            "author": "Test Author",
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Dialogue Test"

    def test_upload_fountain_with_action(self, client):
        """Test that content with action lines is recognized as valid Fountain."""
        script_data = {
            "title": "Action Test",
            "content": """The sun rises over the city.

A car speeds down the highway.

CUT TO:""",
            "author": "Test Author",
        }

        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Action Test"


class TestScriptFileUploadValidation:
    """Test script file upload validation."""

    def test_upload_file_wrong_extension(self, client):
        """Test uploading file with wrong extension."""
        from io import BytesIO

        file_content = b"Some content"
        file = ("test.txt", BytesIO(file_content), "text/plain")

        response = client.post("/api/v1/scripts/upload-file", files={"file": file})
        assert response.status_code == 400
        assert "fountain" in response.json()["detail"].lower()

    def test_upload_file_valid_fountain(self, client):
        """Test uploading valid .fountain file."""
        from io import BytesIO

        file_content = b"""FADE IN:

INT. TEST LOCATION - DAY

Test content."""
        file = ("test_script.fountain", BytesIO(file_content), "text/plain")

        response = client.post("/api/v1/scripts/upload-file", files={"file": file})
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "test_script"  # Extracted from filename


class TestSceneValidation:
    """Test scene creation and update validation."""

    @pytest.fixture
    def sample_script_id(self, client):
        """Create a sample script and return its ID."""
        script_data = {
            "title": "Test Script",
            "content": "INT. TEST - DAY\n\nTest content.",
            "author": "Test Author",
        }
        response = client.post("/api/v1/scripts/upload", json=script_data)
        return response.json()["id"]

    def test_create_scene_invalid_heading(self, client, sample_script_id):
        """Test creating scene with empty heading."""
        scene_data = {"scene_number": 1, "heading": "", "content": "Some content."}

        response = client.post(
            f"/api/v1/scenes/?script_id={sample_script_id}", json=scene_data
        )
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(
            (
                (
                    "heading" in str(error).lower()
                    or ("loc" in str(error) and "'heading'" in str(error))
                )
                and (
                    "at least 1 character" in str(error).lower()
                    or "empty" in str(error).lower()
                )
            )
            for error in errors
        )

    def test_create_scene_negative_number(self, client, sample_script_id):
        """Test creating scene with negative scene number."""
        scene_data = {
            "scene_number": -1,
            "heading": "INT. TEST - DAY",
            "content": "Some content.",
        }

        response = client.post(
            f"/api/v1/scenes/?script_id={sample_script_id}", json=scene_data
        )
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("scene_number" in str(error).lower() for error in errors)


class TestSearchValidation:
    """Test search endpoint validation."""

    def test_scene_search_limit_too_high(self, client):
        """Test scene search with limit exceeding maximum."""
        search_data = {"query": "test", "limit": 101}  # Max is 100

        response = client.post("/api/v1/search/scenes", json=search_data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("limit" in str(error).lower() for error in errors)

    def test_scene_search_negative_offset(self, client):
        """Test scene search with negative offset."""
        search_data = {"query": "test", "offset": -1}

        response = client.post("/api/v1/search/scenes", json=search_data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("offset" in str(error).lower() for error in errors)

    def test_semantic_search_invalid_threshold(self, client):
        """Test semantic search with invalid similarity threshold."""
        search_data = {"query": "test", "threshold": 1.5}  # Should be 0.0-1.0

        response = client.post("/api/v1/search/similar", json=search_data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("threshold" in str(error).lower() for error in errors)
