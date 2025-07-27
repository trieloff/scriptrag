"""Tests for scene ordering API endpoints."""

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
def client(mock_llm_client):
    """Create test client with mocked LLM client."""
    # The fixture ensures LLM client is mocked during app creation
    _ = mock_llm_client  # Mark as used for linter
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def test_script_with_scenes(client: TestClient) -> dict:
    """Create a test script with multiple scenes."""
    # Upload a script
    script_content = """Title: Test Script
Author: Test Author

FADE IN:

INT. COFFEE SHOP - MORNING

Sarah enters, looking tired.

SARAH
I need coffee.

INT. OFFICE - DAY

Sarah meets her boss.

BOSS
Welcome to your first day.

INT. COFFEE SHOP - FLASHBACK - NIGHT

Years earlier. Sarah meets John.

JOHN
Is this seat taken?

INT. APARTMENT - EVENING

Sarah unpacks boxes in her new place.

INT. OFFICE - CONTINUOUS

The meeting continues.

BOSS (CONT'D)
Let me show you around.

FADE OUT.
"""

    response = client.post(
        "/api/v1/scripts/upload",
        json={
            "title": "Test Script",
            "content": script_content,
            "author": "Test Author",
        },
    )
    assert response.status_code == 200
    return response.json()


class TestSceneOrderingEndpoints:
    """Test scene ordering API endpoints."""

    def test_reorder_scenes(
        self,
        client: TestClient,
        test_script_with_scenes: dict,
    ) -> None:
        """Test reordering scenes endpoint."""
        script_id = test_script_with_scenes["id"]

        # Get current scenes
        response = client.get(f"/api/v1/scripts/{script_id}")
        assert response.status_code == 200
        script_data = response.json()
        scene_ids = [scene["id"] for scene in script_data["scenes"]]

        # Reverse the order
        reversed_ids = list(reversed(scene_ids))

        response = client.post(
            f"/api/v1/scenes/script/{script_id}/reorder",
            json={
                "scene_ids": reversed_ids,
                "order_type": "script",
            },
        )
        assert response.status_code == 200
        result = response.json()

        assert result["script_id"] == script_id
        assert result["order_type"] == "script"
        assert result["scene_ids"] == reversed_ids
        assert "Successfully reordered" in result["message"]

    def test_infer_temporal_order(
        self,
        client: TestClient,
        test_script_with_scenes: dict,
    ) -> None:
        """Test inferring temporal order endpoint."""
        script_id = test_script_with_scenes["id"]

        response = client.post(
            f"/api/v1/scenes/script/{script_id}/infer-temporal-order"
        )
        assert response.status_code == 200
        result = response.json()

        assert result["script_id"] == script_id
        assert "temporal_order" in result
        # Check if script was created with scenes
        if result["scene_count"] == 0:
            # Get script details to debug
            script_response = client.get(f"/api/v1/scripts/{script_id}")
            assert script_response.status_code == 200
            script_data = script_response.json()
            assert script_data.get("scene_count", 0) > 0, "Script has no scenes"
        assert result["scene_count"] > 0
        assert "Successfully inferred" in result["message"]

    def test_analyze_dependencies(
        self,
        client: TestClient,
        test_script_with_scenes: dict,
    ) -> None:
        """Test analyzing dependencies endpoint."""
        script_id = test_script_with_scenes["id"]

        response = client.post(
            f"/api/v1/scenes/script/{script_id}/analyze-dependencies"
        )
        assert response.status_code == 200
        result = response.json()

        assert result["script_id"] == script_id
        assert "dependencies_created" in result
        assert result["dependencies_created"] >= 0
        assert "Successfully analyzed" in result["message"]

    def test_get_scene_dependencies(
        self,
        client: TestClient,
        test_script_with_scenes: dict,
    ) -> None:
        """Test getting scene dependencies endpoint."""
        script_id = test_script_with_scenes["id"]

        # First analyze dependencies
        client.post(f"/api/v1/scenes/script/{script_id}/analyze-dependencies")

        # Get scenes
        response = client.get(f"/api/v1/scripts/{script_id}")
        script_data = response.json()
        scene_id = script_data["scenes"][0]["id"]

        # Get dependencies for a scene
        response = client.get(f"/api/v1/scenes/{scene_id}/dependencies?direction=both")
        assert response.status_code == 200
        result = response.json()

        assert result["scene_id"] == scene_id
        assert result["direction"] == "both"
        assert "dependencies" in result
        assert "dependency_count" in result

    def test_get_scene_dependencies_invalid_direction(
        self,
        client: TestClient,
        test_script_with_scenes: dict,
    ) -> None:
        """Test getting scene dependencies with invalid direction."""
        script_data = client.get(f"/api/v1/scripts/{test_script_with_scenes['id']}")
        scene_id = script_data.json()["scenes"][0]["id"]

        response = client.get(
            f"/api/v1/scenes/{scene_id}/dependencies?direction=invalid"
        )
        assert response.status_code == 400
        assert "Invalid direction" in response.json()["detail"]

    def test_calculate_logical_order(
        self,
        client: TestClient,
        test_script_with_scenes: dict,
    ) -> None:
        """Test calculating logical order endpoint."""
        script_id = test_script_with_scenes["id"]

        # First analyze dependencies
        client.post(f"/api/v1/scenes/script/{script_id}/analyze-dependencies")

        response = client.post(
            f"/api/v1/scenes/script/{script_id}/calculate-logical-order"
        )
        assert response.status_code == 200
        result = response.json()

        assert result["script_id"] == script_id
        assert "logical_order" in result
        assert result["scene_count"] > 0
        assert "Successfully calculated" in result["message"]

    def test_validate_ordering(
        self,
        client: TestClient,
        test_script_with_scenes: dict,
    ) -> None:
        """Test validating ordering endpoint."""
        script_id = test_script_with_scenes["id"]

        response = client.get(f"/api/v1/scenes/script/{script_id}/validate-ordering")
        assert response.status_code == 200
        result = response.json()

        assert "is_valid" in result
        assert "conflicts" in result
        assert "warnings" in result

    def test_ordering_nonexistent_script(
        self,
        client: TestClient,
    ) -> None:
        """Test ordering endpoints with nonexistent script."""
        fake_id = "nonexistent-script-id"

        # Test each endpoint
        endpoints = [
            (
                "POST",
                f"/api/v1/scenes/script/{fake_id}/reorder",
                {
                    "scene_ids": ["fake-1", "fake-2"],
                    "order_type": "script",
                },
            ),
            ("POST", f"/api/v1/scenes/script/{fake_id}/infer-temporal-order", None),
            ("POST", f"/api/v1/scenes/script/{fake_id}/analyze-dependencies", None),
            ("POST", f"/api/v1/scenes/script/{fake_id}/calculate-logical-order", None),
            ("GET", f"/api/v1/scenes/script/{fake_id}/validate-ordering", None),
        ]

        for method, url, json_data in endpoints:
            if method == "POST":
                response = client.post(url, json=json_data or {})
            else:
                response = client.get(url)

            assert response.status_code == 404
            assert "Script not found" in response.json()["detail"]

    def test_ordering_invalid_order_type(
        self,
        client: TestClient,
        test_script_with_scenes: dict,
    ) -> None:
        """Test reordering with invalid order type."""
        script_id = test_script_with_scenes["id"]

        response = client.post(
            f"/api/v1/scenes/script/{script_id}/reorder",
            json={
                "scene_ids": ["scene-1", "scene-2"],
                "order_type": "invalid_type",
            },
        )
        # The API should handle this gracefully
        assert response.status_code in [400, 500]
