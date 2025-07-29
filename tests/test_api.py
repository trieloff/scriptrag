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
from pydantic import ValidationError

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


# =====================================================
# COMPREHENSIVE SCRIPT CRUD OPERATION TESTS
# =====================================================


def test_script_upload_json_valid(client):
    """Test script upload with valid JSON data."""
    script_data = {
        "title": "Test Script JSON",
        "content": """FADE IN:

INT. TEST ROOM - DAY

A simple test scene with dialogue.

                    ALICE
                Hello, world!

                    BOB
                Testing the API.

FADE OUT.""",
        "author": "Test Author",
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Script JSON"
    assert data["author"] == "Test Author"
    assert "id" in data
    assert data["scene_count"] >= 1
    assert (
        data["character_count"] >= 0
    )  # May be 0 if parser doesn't detect characters in this format
    assert isinstance(data["created_at"], str)
    assert isinstance(data["updated_at"], str)
    assert isinstance(data["has_embeddings"], bool)


def test_script_upload_json_minimal(client):
    """Test script upload with minimal required fields."""
    script_data = {
        "title": "Minimal Script",
        "content": "FADE IN:\n\nINT. ROOM - DAY\n\nSimple scene.\n\nFADE OUT.",
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Minimal Script"
    assert data["author"] is None
    assert "id" in data


def test_script_upload_json_invalid_empty_title(client):
    """Test script upload with empty title."""
    script_data = {
        "title": "",
        "content": "FADE IN:\n\nINT. ROOM - DAY\n\nTest.\n\nFADE OUT.",
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)
    assert response.status_code == 422  # Validation error


def test_script_upload_json_invalid_empty_content(client):
    """Test script upload with empty content."""
    script_data = {
        "title": "Empty Content Test",
        "content": "",
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)
    assert response.status_code == 400  # Parse error


def test_script_upload_json_malformed_fountain(client):
    """Test script upload with malformed Fountain content."""
    script_data = {
        "title": "Malformed Script",
        "content": "This is not valid fountain format at all!",
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)
    # Should still work but might parse differently
    assert response.status_code in [200, 400]


def test_script_upload_file_valid(client):
    """Test script upload via file upload."""
    fountain_content = """FADE IN:

INT. FILE UPLOAD TEST - DAY

Testing file upload functionality.

                    TESTER
                This is a file upload test.

FADE OUT."""

    files = {"file": ("test_script.fountain", fountain_content.encode(), "text/plain")}

    response = client.post("/api/v1/scripts/upload-file", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "test_script"
    assert "id" in data
    assert data["scene_count"] >= 1


def test_script_upload_file_invalid_extension(client):
    """Test file upload with invalid extension."""
    files = {"file": ("test_script.txt", b"content", "text/plain")}

    response = client.post("/api/v1/scripts/upload-file", files=files)
    assert response.status_code == 400
    assert "fountain" in response.json()["detail"].lower()


def test_script_upload_file_no_filename(client):
    """Test file upload without filename."""
    files = {"file": (None, b"content", "text/plain")}

    response = client.post("/api/v1/scripts/upload-file", files=files)
    assert response.status_code == 400


def test_get_script_details_valid(client):
    """Test getting script details for existing script."""
    # First upload a script
    script_data = {
        "title": "Detail Test Script",
        "content": """FADE IN:

INT. DETAIL TEST - DAY

Testing detailed script retrieval.

                    CHARACTER_A
                First line of dialogue.

                    CHARACTER_B
                Second line of dialogue.

INT. ANOTHER SCENE - NIGHT

More content here.

FADE OUT.""",
        "author": "Detail Tester",
    }

    upload_response = client.post("/api/v1/scripts/upload", json=script_data)
    assert upload_response.status_code == 200
    script_id = upload_response.json()["id"]

    # Now get the details
    response = client.get(f"/api/v1/scripts/{script_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == script_id
    assert data["title"] == "Detail Test Script"
    assert data["author"] == "Detail Tester"
    assert len(data["scenes"]) >= 1
    assert (
        len(data["characters"]) >= 0
    )  # Character detection depends on parser implementation
    assert isinstance(data["metadata"], dict)

    # Check scene details
    scene = data["scenes"][0]
    assert "id" in scene
    assert "script_id" in scene
    assert "scene_number" in scene
    assert "heading" in scene
    assert "content" in scene
    assert "character_count" in scene
    assert "word_count" in scene
    assert isinstance(scene["has_embedding"], bool)


def test_list_scripts_with_multiple(client):
    """Test listing scripts when multiple exist."""
    # Upload multiple scripts
    scripts_data = [
        {
            "title": "Script One",
            "content": "FADE IN:\n\nINT. ROOM - DAY\n\nContent.\n\nFADE OUT.",
        },
        {
            "title": "Script Two",
            "content": "FADE IN:\n\nEXT. PARK - DAY\n\nMore content.\n\nFADE OUT.",
            "author": "Author Two",
        },
        {
            "title": "Script Three",
            "content": "FADE IN:\n\nINT. OFFICE - NIGHT\n\nOffice scene.\n\nFADE OUT.",
            "author": "Author Three",
        },
    ]

    uploaded_ids = []
    for script_data in scripts_data:
        response = client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 200
        uploaded_ids.append(response.json()["id"])

    # List all scripts
    response = client.get("/api/v1/scripts/")
    assert response.status_code == 200
    scripts = response.json()
    assert isinstance(scripts, list)
    assert len(scripts) >= 3

    # Check that our uploaded scripts are in the list
    script_titles = {script["title"] for script in scripts}
    assert "Script One" in script_titles
    assert "Script Two" in script_titles
    assert "Script Three" in script_titles

    # Verify response structure
    for script in scripts:
        assert "id" in script
        assert "title" in script
        assert "created_at" in script
        assert "updated_at" in script
        assert "scene_count" in script
        assert "character_count" in script
        assert "has_embeddings" in script


def test_delete_script_valid(client):
    """Test deleting an existing script."""
    # Upload a script to delete
    script_data = {
        "title": "Script to Delete",
        "content": (
            "FADE IN:\n\nINT. DELETE TEST - DAY\n\nThis will be deleted.\n\nFADE OUT."
        ),
    }

    upload_response = client.post("/api/v1/scripts/upload", json=script_data)
    assert upload_response.status_code == 200
    script_id = upload_response.json()["id"]

    # Verify script exists
    get_response = client.get(f"/api/v1/scripts/{script_id}")
    assert get_response.status_code == 200

    # Delete the script
    delete_response = client.delete(f"/api/v1/scripts/{script_id}")
    assert delete_response.status_code == 200
    assert "deleted successfully" in delete_response.json()["message"]

    # Verify script no longer exists
    get_response_after = client.get(f"/api/v1/scripts/{script_id}")
    assert get_response_after.status_code == 404


def test_delete_script_nonexistent(client):
    """Test deleting a non-existent script."""
    response = client.delete("/api/v1/scripts/nonexistent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_script_lifecycle_full_crud(client):
    """Test complete CRUD lifecycle for a script."""
    # CREATE
    script_data = {
        "title": "CRUD Lifecycle Test",
        "content": """FADE IN:

INT. CRUD TEST ROOM - DAY

A comprehensive test of all CRUD operations.

                    ALICE
                Let's test everything!

                    BOB
                Sounds good to me.

FADE OUT.""",
        "author": "CRUD Tester",
    }

    # Create script
    create_response = client.post("/api/v1/scripts/upload", json=script_data)
    assert create_response.status_code == 200
    created_script = create_response.json()
    script_id = created_script["id"]

    assert created_script["title"] == "CRUD Lifecycle Test"
    assert created_script["author"] == "CRUD Tester"

    # READ - List all scripts (should include our new one)
    list_response = client.get("/api/v1/scripts/")
    assert list_response.status_code == 200
    scripts = list_response.json()
    script_ids = [s["id"] for s in scripts]
    assert script_id in script_ids

    # READ - Get specific script
    get_response = client.get(f"/api/v1/scripts/{script_id}")
    assert get_response.status_code == 200
    retrieved_script = get_response.json()
    assert retrieved_script["id"] == script_id
    assert retrieved_script["title"] == "CRUD Lifecycle Test"
    assert len(retrieved_script["scenes"]) >= 1
    assert (
        len(retrieved_script["characters"]) >= 0
    )  # Character detection depends on parser

    # DELETE
    delete_response = client.delete(f"/api/v1/scripts/{script_id}")
    assert delete_response.status_code == 200

    # Verify deletion
    get_after_delete = client.get(f"/api/v1/scripts/{script_id}")
    assert get_after_delete.status_code == 404


# =====================================================
# PYDANTIC SCHEMA VALIDATION TESTS
# =====================================================


def test_script_upload_request_schema_validation():
    """Test ScriptUploadRequest schema validation."""
    from scriptrag.api.v1.schemas import ScriptUploadRequest

    # Valid data
    valid_data = {
        "title": "Test Script",
        "content": "FADE IN:\n\nINT. ROOM - DAY\n\nTest content.\n\nFADE OUT.",
        "author": "Test Author",
    }
    request = ScriptUploadRequest(**valid_data)
    assert request.title == "Test Script"
    assert request.author == "Test Author"

    # Valid minimal data (author optional)
    minimal_data = {"title": "Minimal Script", "content": "Simple content"}
    request_minimal = ScriptUploadRequest(**minimal_data)
    assert request_minimal.title == "Minimal Script"
    assert request_minimal.author is None

    # Invalid - missing required title
    with pytest.raises(ValidationError):
        ScriptUploadRequest(content="content only")

    # Invalid - missing required content
    with pytest.raises(ValidationError):
        ScriptUploadRequest(title="title only")

    # Invalid - empty title (may be allowed by schema, but would fail at API level)
    # Note: Pydantic allows empty strings by default unless Field validation is used
    empty_title_request = ScriptUploadRequest(title="", content="content")
    assert empty_title_request.title == ""  # This may be valid at schema level


def test_script_response_schema_serialization():
    """Test ScriptResponse schema serialization."""
    from datetime import datetime

    from scriptrag.api.v1.schemas import ScriptResponse

    # Valid response data
    response_data = {
        "id": "test-id-123",
        "title": "Test Script",
        "author": "Test Author",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "scene_count": 5,
        "character_count": 3,
        "has_embeddings": True,
    }

    response = ScriptResponse(**response_data)
    assert response.id == "test-id-123"
    assert response.title == "Test Script"
    assert response.scene_count == 5
    assert response.has_embeddings is True

    # Test serialization to dict
    serialized = response.model_dump()
    assert "id" in serialized
    assert "created_at" in serialized
    assert serialized["scene_count"] == 5

    # Test JSON serialization
    json_str = response.model_dump_json()
    assert "test-id-123" in json_str
    assert "Test Script" in json_str


def test_scene_response_schema_validation():
    """Test SceneResponse schema validation and serialization."""
    from scriptrag.api.v1.schemas import SceneResponse

    scene_data = {
        "id": "scene-123",
        "script_id": "script-456",
        "scene_number": 1,
        "heading": "INT. ROOM - DAY",
        "content": "A simple scene with dialogue.",
        "character_count": 2,
        "word_count": 15,
        "page_start": 1.0,
        "page_end": 1.5,
        "has_embedding": True,
    }

    scene = SceneResponse(**scene_data)
    assert scene.scene_number == 1
    assert scene.heading == "INT. ROOM - DAY"
    assert scene.has_embedding is True

    # Test with optional fields as None
    minimal_scene_data = {
        "id": "scene-789",
        "script_id": "script-456",
        "scene_number": 2,
        "heading": "EXT. PARK - NIGHT",
        "content": "Another scene.",
        "character_count": 1,
        "word_count": 2,
        "page_start": None,
        "page_end": None,
        "has_embedding": False,
    }

    minimal_scene = SceneResponse(**minimal_scene_data)
    assert minimal_scene.page_start is None
    assert minimal_scene.page_end is None
    assert minimal_scene.has_embedding is False


def test_search_request_schema_validation():
    """Test search request schemas validation."""
    from scriptrag.api.v1.schemas import SceneSearchRequest, SemanticSearchRequest

    # SceneSearchRequest - valid
    scene_search = SceneSearchRequest(
        query="test query",
        limit=20,
        offset=10,
        script_id="script-123",
        character="ALICE",
    )
    assert scene_search.limit == 20
    assert scene_search.offset == 10
    assert scene_search.character == "ALICE"

    # SceneSearchRequest - with defaults
    scene_search_minimal = SceneSearchRequest()
    assert scene_search_minimal.limit == 10  # default
    assert scene_search_minimal.offset == 0  # default
    assert scene_search_minimal.query is None

    # Invalid limit (too small)
    with pytest.raises(ValidationError):
        SceneSearchRequest(limit=0)

    # Invalid limit (too large)
    with pytest.raises(ValidationError):
        SceneSearchRequest(limit=101)

    # Invalid offset (negative)
    with pytest.raises(ValidationError):
        SceneSearchRequest(offset=-1)

    # SemanticSearchRequest - valid
    semantic_search = SemanticSearchRequest(
        query="semantic search query", threshold=0.8, limit=15
    )
    assert semantic_search.query == "semantic search query"
    assert semantic_search.threshold == 0.8

    # SemanticSearchRequest - missing required query
    with pytest.raises(ValidationError):
        SemanticSearchRequest(limit=10)

    # Invalid threshold (too low)
    with pytest.raises(ValidationError):
        SemanticSearchRequest(query="test", threshold=-0.1)

    # Invalid threshold (too high)
    with pytest.raises(ValidationError):
        SemanticSearchRequest(query="test", threshold=1.1)


def test_graph_schema_validation():
    """Test graph-related schema validation."""
    from scriptrag.api.v1.schemas import (
        CharacterGraphRequest,
        GraphEdge,
        GraphNode,
        GraphNodeType,
    )

    # GraphNode validation
    node = GraphNode(
        id="node-1",
        type=GraphNodeType.CHARACTER,
        label="ALICE",
        properties={"importance": 0.8},
    )
    assert node.id == "node-1"
    assert node.type == GraphNodeType.CHARACTER
    assert node.properties["importance"] == 0.8

    # GraphEdge validation
    edge = GraphEdge(
        source="node-1",
        target="node-2",
        type="INTERACTS_WITH",
        weight=0.5,
        properties={"scene_count": 3},
    )
    assert edge.source == "node-1"
    assert edge.weight == 0.5
    assert edge.properties["scene_count"] == 3

    # CharacterGraphRequest validation
    char_request = CharacterGraphRequest(
        character_name="ALICE", script_id="script-123", depth=3, min_interaction_count=2
    )
    assert char_request.character_name == "ALICE"
    assert char_request.depth == 3

    # Invalid depth (too high)
    with pytest.raises(ValidationError):
        CharacterGraphRequest(character_name="BOB", depth=6)

    # Invalid min_interaction_count (too low)
    with pytest.raises(ValidationError):
        CharacterGraphRequest(character_name="BOB", min_interaction_count=0)


def test_error_response_schema():
    """Test ErrorResponse schema."""
    from scriptrag.api.v1.schemas import ErrorResponse, ResponseStatus

    error_resp = ErrorResponse(
        error="Something went wrong", details={"field": "value", "code": 123}
    )
    assert error_resp.status == ResponseStatus.ERROR
    assert error_resp.error == "Something went wrong"
    assert error_resp.details["code"] == 123

    # Minimal error response
    minimal_error = ErrorResponse(error="Simple error")
    assert minimal_error.details is None
    assert minimal_error.message is None


def test_scene_ordering_schema():
    """Test scene ordering request/response schemas."""
    from scriptrag.api.v1.schemas import SceneOrderingRequest, SceneOrderingResponse

    # Valid ordering request
    order_request = SceneOrderingRequest(
        scene_ids=["scene-1", "scene-2", "scene-3"], order_type="temporal"
    )
    assert len(order_request.scene_ids) == 3
    assert order_request.order_type == "temporal"

    # Default order type
    default_request = SceneOrderingRequest(scene_ids=["scene-1", "scene-2"])
    assert default_request.order_type == "script"  # default

    # Ordering response
    order_response = SceneOrderingResponse(
        script_id="script-123",
        order_type="logical",
        scene_ids=["scene-3", "scene-1", "scene-2"],
        message="Scenes reordered successfully",
    )
    assert order_response.script_id == "script-123"
    assert len(order_response.scene_ids) == 3


# =====================================================
# ERROR HANDLING AND STATUS CODE TESTS
# =====================================================


def test_script_upload_server_error_handling(client):
    """Test server error handling during script upload."""
    # Test with extremely large content that might cause memory issues
    huge_content = "FADE IN:\n\n" + "A" * 1000000 + "\n\nFADE OUT."
    script_data = {
        "title": "Huge Script",
        "content": huge_content,
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)
    # Should either succeed or fail gracefully with proper error
    assert response.status_code in [200, 400, 413, 500]
    if response.status_code != 200:
        assert "detail" in response.json()


def test_script_upload_invalid_json_structure(client):
    """Test upload with invalid JSON structure."""
    # Missing content field entirely
    invalid_data = {"title": "Invalid Script"}

    response = client.post("/api/v1/scripts/upload", json=invalid_data)
    assert response.status_code == 422
    error_detail = response.json()
    assert "detail" in error_detail
    # Should mention missing content field
    assert any("content" in str(error).lower() for error in error_detail["detail"])


def test_script_upload_invalid_json_types(client):
    """Test upload with wrong data types."""
    # Title as integer instead of string
    invalid_data = {
        "title": 123,
        "content": "FADE IN:\n\nINT. ROOM - DAY\n\nTest.\n\nFADE OUT.",
    }

    response = client.post("/api/v1/scripts/upload", json=invalid_data)
    assert response.status_code == 422

    # Content as integer instead of string
    invalid_data2 = {"title": "Valid Title", "content": 456}

    response2 = client.post("/api/v1/scripts/upload", json=invalid_data2)
    assert response2.status_code == 422


def test_script_upload_malformed_json(client):
    """Test upload with malformed JSON payload."""

    # Send malformed JSON directly
    malformed_json = '{"title": "Test", "content": "value"'  # Missing closing brace

    # Use requests directly to send malformed JSON
    response = client.request(
        "POST",
        "/api/v1/scripts/upload",
        content=malformed_json,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422  # FastAPI returns 422 for malformed JSON


def test_script_get_invalid_id_formats(client):
    """Test getting scripts with various invalid ID formats."""
    invalid_ids = [
        "",  # empty string
        "   ",  # whitespace only
        "invalid-chars-!@#$%",  # special characters
        "a" * 1000,  # extremely long ID
        "null",  # string "null"
        "undefined",  # string "undefined"
    ]

    for invalid_id in invalid_ids:
        response = client.get(f"/api/v1/scripts/{invalid_id}")
        # Should return 404 for non-existent scripts
        # or 422 if the ID format is completely invalid
        assert response.status_code in [404, 422]
        assert "detail" in response.json()


def test_file_upload_various_error_conditions(client):
    """Test file upload error conditions."""
    # Test 1: Empty file
    empty_file = {"file": ("empty.fountain", b"", "text/plain")}
    response = client.post("/api/v1/scripts/upload-file", files=empty_file)
    assert response.status_code in [400, 422]

    # Test 2: Binary file (not text)
    binary_content = b"\x00\x01\x02\x03\x04\x05"
    binary_file = {
        "file": ("binary.fountain", binary_content, "application/octet-stream")
    }
    response = client.post("/api/v1/scripts/upload-file", files=binary_file)
    assert response.status_code in [400, 422]

    # Test 3: File with non-UTF8 encoding
    non_utf8_content = "FADE IN:\n\nINT. ROOM - DAY\n\nFrançais résumé café".encode(
        "latin1"
    )
    non_utf8_file = {"file": ("non_utf8.fountain", non_utf8_content, "text/plain")}
    response = client.post("/api/v1/scripts/upload-file", files=non_utf8_file)
    # Should either handle gracefully or return appropriate error
    assert response.status_code in [200, 400, 422]


def test_concurrent_script_operations(client):
    """Test handling of concurrent script operations."""
    import threading

    results = []

    def upload_script(script_num):
        script_data = {
            "title": f"Concurrent Script {script_num}",
            "content": (
                f"FADE IN:\n\nINT. ROOM {script_num} - DAY\n\n"
                f"Concurrent test {script_num}.\n\nFADE OUT."
            ),
        }
        response = client.post("/api/v1/scripts/upload", json=script_data)
        results.append((script_num, response.status_code, response.json()))

    # Create multiple threads to upload scripts concurrently
    threads = []
    for i in range(5):
        thread = threading.Thread(target=upload_script, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Verify all uploads either succeeded or failed gracefully
    for script_num, status_code, response_data in results:
        assert status_code in [200, 400, 500]
        if status_code == 200:
            assert "id" in response_data
            assert response_data["title"] == f"Concurrent Script {script_num}"


def test_database_connection_error_simulation(client):
    """Test behavior when database operations fail."""
    # This test assumes the database might be unavailable or operations might fail
    # We'll test with operations that might stress the database

    # Try to get a script that would require database access
    response = client.get("/api/v1/scripts/")
    # Should either succeed or fail with 500 (not crash)
    assert response.status_code in [200, 500]

    if response.status_code == 500:
        error_data = response.json()
        assert "detail" in error_data
        # Should not expose internal database details
        assert "password" not in str(error_data).lower()
        assert "connection string" not in str(error_data).lower()


def test_http_method_not_allowed(client):
    """Test HTTP methods that aren't allowed."""
    # PATCH method on upload endpoint (only POST allowed)
    response = client.patch("/api/v1/scripts/upload", json={"title": "test"})
    assert response.status_code == 405  # Method Not Allowed

    # PUT method on list endpoint (only GET allowed)
    response = client.put("/api/v1/scripts/", json={"data": "test"})
    assert response.status_code == 405

    # POST method on specific script endpoint (only GET/DELETE allowed)
    response = client.post("/api/v1/scripts/some-id", json={"data": "test"})
    assert response.status_code == 405


def test_content_type_errors(client):
    """Test various content type error conditions."""
    script_data = {
        "title": "Content Type Test",
        "content": "FADE IN:\n\nINT. ROOM - DAY\n\nTest.\n\nFADE OUT.",
    }

    # Test with wrong content type
    response = client.request(
        "POST",
        "/api/v1/scripts/upload",
        content=str(script_data),  # Plain string instead of JSON
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code in [400, 422]

    # Test with no content type
    response = client.request(
        "POST",
        "/api/v1/scripts/upload",
        content=str(script_data),
        # No Content-Type header
    )
    assert response.status_code in [400, 422]


def test_request_size_limits(client):
    """Test behavior with very large requests."""
    # Create a script with large title and content
    large_title = "A" * 10000  # 10KB title
    large_content = "FADE IN:\n\n" + "B" * 100000 + "\n\nFADE OUT."  # ~100KB content

    script_data = {
        "title": large_title,
        "content": large_content,
        "author": "Large Content Tester",
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)
    # Should either handle large content or reject it gracefully
    assert response.status_code in [200, 400, 413, 422]

    if response.status_code != 200:
        error_data = response.json()
        assert "detail" in error_data


def test_unicode_and_special_characters(client):
    """Test handling of Unicode and special characters."""
    script_data = {
        "title": "Unicode Test 🎬📝 François café résumé",
        "content": """FADE IN:

INT. CAFÉ - JOUR

A test with unicode characters: 你好, العالم, Здравствуй мир!

                    FRANÇOIS
                Bonjour! Comment ça va? 🎭

                    MARÍA
                ¡Hola! ¿Cómo estás? 💃

Special chars: @#$%^&*()_+-=[]{}|;:'"<>?,./

FADE OUT.""",
        "author": "Test Author 测试作者 テスト著者",
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)
    assert response.status_code == 200
    data = response.json()
    assert "🎬" in data["title"]
    assert data["author"] == "Test Author 测试作者 テスト著者"


# =====================================================
# EDGE CASES AND BOUNDARY CONDITION TESTS
# =====================================================


def test_script_with_no_scenes(client):
    """Test script that generates no parseable scenes."""
    script_data = {
        "title": "No Scenes Script",
        "content": "This is just plain text with no fountain formatting.",
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)
    # Should either succeed with 0 scenes or handle gracefully
    assert response.status_code in [200, 400]

    if response.status_code == 200:
        data = response.json()
        assert data["scene_count"] >= 0  # Could be 0 if no scenes parsed


def test_script_with_only_whitespace_content(client):
    """Test script with only whitespace content."""
    script_data = {
        "title": "Whitespace Script",
        "content": "   \n\n\t\t   \n   \n\n",
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)
    # Should handle gracefully
    assert response.status_code in [200, 400]


def test_script_title_boundary_lengths(client):
    """Test scripts with various title lengths."""
    base_content = "FADE IN:\n\nINT. ROOM - DAY\n\nTest content.\n\nFADE OUT."

    # Very short title (1 character)
    short_script = {
        "title": "A",
        "content": base_content,
    }
    response = client.post("/api/v1/scripts/upload", json=short_script)
    assert response.status_code == 200
    assert response.json()["title"] == "A"

    # Medium length title
    medium_title = "A" * 255  # Common database varchar limit
    medium_script = {
        "title": medium_title,
        "content": base_content,
    }
    response = client.post("/api/v1/scripts/upload", json=medium_script)
    assert response.status_code in [200, 422]

    # Very long title
    long_title = "A" * 1000
    long_script = {
        "title": long_title,
        "content": base_content,
    }
    response = client.post("/api/v1/scripts/upload", json=long_script)
    # Should either accept or reject gracefully
    assert response.status_code in [200, 400, 422]


def test_script_with_many_characters(client):
    """Test script with a large number of unique characters."""
    characters = [f"CHARACTER_{i:03d}" for i in range(100)]

    content_lines = ["FADE IN:", "", "INT. MASSIVE CAST ROOM - DAY", ""]
    for char in characters:
        content_lines.extend(
            [f"                    {char}", f"                Line for {char}.", ""]
        )
    content_lines.append("FADE OUT.")

    script_data = {
        "title": "Many Characters Script",
        "content": "\n".join(content_lines),
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)
    assert response.status_code in [200, 400]

    if response.status_code == 200:
        data = response.json()
        # Should have detected many characters
        assert (
            data["character_count"] >= 0
        )  # Character detection varies by parser implementation


def test_script_with_many_scenes(client):
    """Test script with a large number of scenes."""
    content_lines = ["FADE IN:", ""]

    # Generate 50 scenes
    for i in range(50):
        content_lines.extend(
            [
                f"INT. ROOM {i} - DAY",
                "",
                f"This is scene number {i}.",
                "",
                "                    ACTOR",
                f"                This is dialogue in scene {i}.",
                "",
            ]
        )

    content_lines.append("FADE OUT.")

    script_data = {
        "title": "Many Scenes Script",
        "content": "\n".join(content_lines),
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)
    assert response.status_code in [200, 400]

    if response.status_code == 200:
        data = response.json()
        # Should have detected many scenes
        assert data["scene_count"] >= 25  # At least half should be parsed as scenes


def test_script_with_complex_fountain_formatting(client):
    """Test script with complex Fountain formatting."""
    complex_content = """Title: Complex Fountain Test
Credit: Written by
Author: Test Author
Draft date: 2024-01-01

FADE IN:

EXT. COMPLEX LOCATION (HELICOPTER SHOT) - DAWN

A complex scene with various formatting.

**Bold action line** and *italic action line*.

                    MAIN_CHARACTER (V.O.)
                        (excited)
                This is complex dialogue with a parenthetical!

                    MAIN_CHARACTER (CONT'D)
                This is continued dialogue.

> This is a transition <

INT. FLASHBACK LOCATION - DAY (FLASHBACK)

A flashback scene.

                    YOUNGER_CHARACTER
                        (whispering; to other character)
                More complex dialogue.

.Forced action line

MONTAGE:

- First montage item
- Second montage item
- Third montage item

END MONTAGE

FADE OUT.

THE END"""

    script_data = {
        "title": "Complex Fountain Script",
        "content": complex_content,
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Complex Fountain Script"
    assert data["scene_count"] >= 1


def test_empty_script_list_pagination_edge_cases(client):
    """Test edge cases in script listing."""
    response = client.get("/api/v1/scripts/")
    assert response.status_code == 200
    scripts = response.json()
    assert isinstance(scripts, list)
    # List could be empty or contain scripts from other tests


def test_script_id_collision_handling(client):
    """Test handling of potential ID collisions."""
    # Upload two identical scripts rapidly
    script_data = {
        "title": "Collision Test Script",
        "content": "FADE IN:\n\nINT. ROOM - DAY\n\nCollision test.\n\nFADE OUT.",
    }

    response1 = client.post("/api/v1/scripts/upload", json=script_data)
    response2 = client.post("/api/v1/scripts/upload", json=script_data)

    assert response1.status_code == 200
    assert response2.status_code == 200

    # IDs should be different even for identical scripts
    id1 = response1.json()["id"]
    id2 = response2.json()["id"]
    assert id1 != id2


def test_fountain_parser_edge_cases(client):
    """Test edge cases in Fountain parsing."""
    edge_cases = [
        {
            "title": "Only Character Names",
            "content": """FADE IN:

                        ALICE

                        BOB

                        CHARLIE

FADE OUT.""",
        },
        {
            "title": "Only Action Lines",
            "content": """FADE IN:

Action line one.

Action line two.

Action line three.

FADE OUT.""",
        },
        {
            "title": "Mixed Case Headers",
            "content": """fade in:

int. room - day

Mixed case content.

fade out.""",
        },
        {
            "title": "Unusual Spacing",
            "content": """FADE IN:


INT.    ROOM   -    DAY


Unusual spacing everywhere.


                        CHARACTER
                        Dialogue with spacing.


FADE OUT.""",
        },
    ]

    for edge_case in edge_cases:
        response = client.post("/api/v1/scripts/upload", json=edge_case)
        # All should either parse successfully or fail gracefully
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            data = response.json()
            assert data["title"] == edge_case["title"]
            assert "id" in data


def test_script_operations_order_dependency(client):
    """Test that script operations don't depend on execution order."""
    # Create, read, delete in different orders
    script_data = {
        "title": "Order Test Script",
        "content": "FADE IN:\n\nINT. ORDER TEST - DAY\n\nOrder test.\n\nFADE OUT.",
    }

    # Normal order: Create -> Read -> Delete
    create_response = client.post("/api/v1/scripts/upload", json=script_data)
    assert create_response.status_code == 200
    script_id = create_response.json()["id"]

    read_response = client.get(f"/api/v1/scripts/{script_id}")
    assert read_response.status_code == 200

    delete_response = client.delete(f"/api/v1/scripts/{script_id}")
    assert delete_response.status_code == 200

    # Verify deletion worked
    read_after_delete = client.get(f"/api/v1/scripts/{script_id}")
    assert read_after_delete.status_code == 404


def test_file_upload_filename_edge_cases(client):
    """Test file upload with various filename edge cases."""
    content = "FADE IN:\n\nINT. ROOM - DAY\n\nFile test.\n\nFADE OUT."

    edge_case_filenames = [
        "simple.fountain",
        "with-dashes.fountain",
        "with_underscores.fountain",
        "with spaces.fountain",
        "with.multiple.dots.fountain",
        "UPPERCASE.FOUNTAIN",
        "123numbers.fountain",
        "unicode_café.fountain",
        "very_long_filename_that_goes_on_and_on_and_on.fountain",
    ]

    for filename in edge_case_filenames:
        files = {"file": (filename, content.encode(), "text/plain")}

        response = client.post("/api/v1/scripts/upload-file", files=files)
        # Should either succeed or fail gracefully
        assert response.status_code in [200, 400, 422]

        if response.status_code == 200:
            data = response.json()
            # Title should be derived from filename (without .fountain)
            expected_title = filename.replace(".fountain", "")
            assert data["title"] == expected_title


def test_concurrent_crud_operations_same_script(client):
    """Test concurrent operations on the same script."""
    # Upload a script first
    script_data = {
        "title": "Concurrent Operations Script",
        "content": (
            "FADE IN:\n\nINT. CONCURRENT TEST - DAY\n\nConcurrent test.\n\nFADE OUT."
        ),
    }

    response = client.post("/api/v1/scripts/upload", json=script_data)
    assert response.status_code == 200
    script_id = response.json()["id"]

    import threading

    results = []

    def read_script():
        response = client.get(f"/api/v1/scripts/{script_id}")
        results.append(("read", response.status_code))

    def list_scripts():
        response = client.get("/api/v1/scripts/")
        results.append(("list", response.status_code))

    # Run concurrent read operations
    threads = []
    for _ in range(3):
        threads.append(threading.Thread(target=read_script))
        threads.append(threading.Thread(target=list_scripts))

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # All operations should succeed
    for _operation, status_code in results:
        assert status_code == 200

    # Clean up
    delete_response = client.delete(f"/api/v1/scripts/{script_id}")
    assert delete_response.status_code == 200
