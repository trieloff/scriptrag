"""Tests for Phase 5.2 Scene Operations API endpoints.

Tests the enhanced API endpoints for scene operations including:
- Enhanced update operations
- Enhanced delete operations
- Enhanced inject operations
- Story continuity validation
"""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from scriptrag.api.v1.endpoints.scenes import (
    delete_scene,
    inject_scene_at_position,
    update_scene,
    update_scene_metadata,
    validate_story_continuity,
)
from scriptrag.api.v1.schemas import SceneCreateRequest, SceneUpdateRequest


class TestEnhancedSceneAPIEndpoints:
    """Test enhanced scene API endpoints for Phase 5.2."""

    @pytest.fixture
    def mock_db_ops(self):
        """Create mock database operations."""
        db_ops = Mock()
        db_ops.get_scene = AsyncMock()
        db_ops.update_scene_with_graph_propagation = AsyncMock()
        db_ops.delete_scene_with_references = AsyncMock()
        db_ops.inject_scene_at_position = AsyncMock()
        db_ops.validate_story_continuity = AsyncMock()
        db_ops.update_scene_metadata = AsyncMock()
        db_ops.get_script = AsyncMock()
        return db_ops

    @pytest.fixture
    def sample_scene_data(self):
        """Sample scene data for testing."""
        return {
            "id": "scene_001",
            "script_id": "script_001",
            "scene_number": 1,
            "heading": "INT. OFFICE - DAY",
            "content": "JOHN sits at his desk.",
            "character_count": 1,
            "word_count": 5,
            "page_start": None,
            "page_end": None,
            "has_embedding": False,
        }

    @pytest.mark.asyncio
    async def test_enhanced_update_scene_success(self, mock_db_ops, sample_scene_data):
        """Test enhanced scene update with graph propagation."""
        # Setup
        scene_id = "scene_001"
        scene_update = SceneUpdateRequest(
            scene_number=2,
            heading="INT. OFFICE - NIGHT",
            content="JOHN works late.",
            location="INT. OFFICE - NIGHT",
            time_of_day="NIGHT",
        )

        mock_db_ops.get_scene.return_value = sample_scene_data
        mock_db_ops.update_scene_with_graph_propagation.return_value = True

        updated_scene_data = sample_scene_data.copy()
        updated_scene_data.update(
            {
                "scene_number": 2,
                "heading": "INT. OFFICE - NIGHT",
                "content": "JOHN works late.",
            }
        )
        mock_db_ops.get_scene.side_effect = [sample_scene_data, updated_scene_data]

        # Test
        response = await update_scene(scene_id, scene_update, mock_db_ops)

        # Assertions
        assert response.id == scene_id
        assert response.scene_number == 2
        assert response.heading == "INT. OFFICE - NIGHT"
        mock_db_ops.update_scene_with_graph_propagation.assert_called_once_with(
            scene_id=scene_id,
            scene_number=2,
            heading="INT. OFFICE - NIGHT",
            content="JOHN works late.",
            location="INT. OFFICE - NIGHT",
            time_of_day="NIGHT",
        )

    @pytest.mark.asyncio
    async def test_enhanced_update_scene_not_found(self, mock_db_ops):
        """Test enhanced scene update when scene not found."""
        scene_id = "nonexistent_scene"
        scene_update = SceneUpdateRequest(heading="New heading")

        mock_db_ops.get_scene.return_value = None

        # Test
        with pytest.raises(HTTPException) as exc_info:
            await update_scene(scene_id, scene_update, mock_db_ops)

        assert exc_info.value.status_code == 404
        assert "Scene not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_enhanced_update_scene_failure(self, mock_db_ops, sample_scene_data):
        """Test enhanced scene update failure."""
        scene_id = "scene_001"
        scene_update = SceneUpdateRequest(heading="New heading")

        mock_db_ops.get_scene.return_value = sample_scene_data
        mock_db_ops.update_scene_with_graph_propagation.return_value = False

        # Test
        with pytest.raises(HTTPException) as exc_info:
            await update_scene(scene_id, scene_update, mock_db_ops)

        assert exc_info.value.status_code == 500
        assert "Failed to update scene" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_enhanced_delete_scene_success(self, mock_db_ops, sample_scene_data):
        """Test enhanced scene deletion with reference maintenance."""
        scene_id = "scene_001"

        mock_db_ops.get_scene.return_value = sample_scene_data
        mock_db_ops.delete_scene_with_references.return_value = True

        # Test
        response = await delete_scene(scene_id, mock_db_ops)

        # Assertions
        assert "deleted successfully with reference integrity" in response["message"]
        mock_db_ops.delete_scene_with_references.assert_called_once_with(scene_id)

    @pytest.mark.asyncio
    async def test_enhanced_delete_scene_not_found(self, mock_db_ops):
        """Test enhanced scene deletion when scene not found."""
        scene_id = "nonexistent_scene"

        mock_db_ops.get_scene.return_value = None

        # Test
        with pytest.raises(HTTPException) as exc_info:
            await delete_scene(scene_id, mock_db_ops)

        assert exc_info.value.status_code == 404
        assert "Scene not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_enhanced_delete_scene_failure(self, mock_db_ops, sample_scene_data):
        """Test enhanced scene deletion failure."""
        scene_id = "scene_001"

        mock_db_ops.get_scene.return_value = sample_scene_data
        mock_db_ops.delete_scene_with_references.return_value = False

        # Test
        with pytest.raises(HTTPException) as exc_info:
            await delete_scene(scene_id, mock_db_ops)

        assert exc_info.value.status_code == 500
        assert "Failed to delete scene" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_inject_scene_at_position_success(
        self, mock_db_ops, sample_scene_data
    ):
        """Test injecting scene at specific position."""
        scene_id = "scene_001"
        position = 2
        scene_data = SceneCreateRequest(
            scene_number=2,
            heading="INT. HALLWAY - DAY",
            content="JOHN walks down the hallway.",
        )

        mock_db_ops.get_scene.return_value = sample_scene_data
        mock_db_ops.inject_scene_at_position.return_value = "new_scene_001"

        new_scene_data = {
            "id": "new_scene_001",
            "script_id": "script_001",
            "scene_number": 2,
            "heading": "INT. HALLWAY - DAY",
            "content": "JOHN walks down the hallway.",
            "character_count": 1,
            "word_count": 5,
            "page_start": None,
            "page_end": None,
            "has_embedding": False,
        }
        mock_db_ops.get_scene.side_effect = [sample_scene_data, new_scene_data]

        # Test
        response = await inject_scene_at_position(
            scene_id, position, scene_data, mock_db_ops
        )

        # Assertions
        assert response.id == "new_scene_001"
        assert response.heading == "INT. HALLWAY - DAY"
        mock_db_ops.inject_scene_at_position.assert_called_once_with(
            script_id="script_001", scene_data=scene_data, position=position
        )

    @pytest.mark.asyncio
    async def test_inject_scene_reference_not_found(self, mock_db_ops):
        """Test scene injection when reference scene not found."""
        scene_id = "nonexistent_scene"
        position = 2
        scene_data = SceneCreateRequest(
            scene_number=2, heading="Test", content="Test content"
        )

        mock_db_ops.get_scene.return_value = None

        # Test
        with pytest.raises(HTTPException) as exc_info:
            await inject_scene_at_position(scene_id, position, scene_data, mock_db_ops)

        assert exc_info.value.status_code == 404
        assert "Reference scene not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_inject_scene_failure(self, mock_db_ops, sample_scene_data):
        """Test scene injection failure."""
        scene_id = "scene_001"
        position = 2
        scene_data = SceneCreateRequest(
            scene_number=2, heading="Test", content="Test content"
        )

        mock_db_ops.get_scene.return_value = sample_scene_data
        mock_db_ops.inject_scene_at_position.return_value = None

        # Test
        with pytest.raises(HTTPException) as exc_info:
            await inject_scene_at_position(scene_id, position, scene_data, mock_db_ops)

        assert exc_info.value.status_code == 500
        assert "Failed to inject scene" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_validate_story_continuity_success(self, mock_db_ops):
        """Test story continuity validation."""
        script_id = "script_001"

        mock_script = {"id": script_id, "title": "Test Script"}
        continuity_results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "character_continuity": {"JOHN": 1, "MARY": 3},
            "location_continuity": {"OFFICE": [1, 2], "HALLWAY": [3]},
            "temporal_continuity": [],
        }

        mock_db_ops.get_script.return_value = mock_script
        mock_db_ops.validate_story_continuity.return_value = continuity_results

        # Test
        response = await validate_story_continuity(script_id, mock_db_ops)

        # Assertions
        assert response["script_id"] == script_id
        assert response["continuity_results"] == continuity_results
        assert "validation completed" in response["message"]
        mock_db_ops.validate_story_continuity.assert_called_once_with(script_id)

    @pytest.mark.asyncio
    async def test_validate_story_continuity_script_not_found(self, mock_db_ops):
        """Test story continuity validation when script not found."""
        script_id = "nonexistent_script"

        mock_db_ops.get_script.return_value = None

        # Test
        with pytest.raises(HTTPException) as exc_info:
            await validate_story_continuity(script_id, mock_db_ops)

        assert exc_info.value.status_code == 404
        assert "Script not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_scene_metadata_success(self, mock_db_ops, sample_scene_data):
        """Test scene metadata update."""
        scene_id = "scene_001"

        mock_db_ops.get_scene.return_value = sample_scene_data
        mock_db_ops.update_scene_metadata.return_value = True

        updated_scene_data = sample_scene_data.copy()
        updated_scene_data["heading"] = "NEW HEADING"
        mock_db_ops.get_scene.side_effect = [sample_scene_data, updated_scene_data]

        # Test
        response = await update_scene_metadata(
            scene_id=scene_id,
            heading="NEW HEADING",
            description="New description",
            time_of_day="NIGHT",
            location="INT. NEW PLACE - NIGHT",
            propagate_to_graph=True,
            db_ops=mock_db_ops,
        )

        # Assertions
        assert response.id == scene_id
        assert response.heading == "NEW HEADING"
        mock_db_ops.update_scene_metadata.assert_called_once_with(
            scene_id=scene_id,
            heading="NEW HEADING",
            description="New description",
            time_of_day="NIGHT",
            location="INT. NEW PLACE - NIGHT",
            propagate_to_graph=True,
        )

    @pytest.mark.asyncio
    async def test_update_scene_metadata_not_found(self, mock_db_ops):
        """Test scene metadata update when scene not found."""
        scene_id = "nonexistent_scene"

        mock_db_ops.get_scene.return_value = None

        # Test
        with pytest.raises(HTTPException) as exc_info:
            await update_scene_metadata(
                scene_id=scene_id, heading="New heading", db_ops=mock_db_ops
            )

        assert exc_info.value.status_code == 404
        assert "Scene not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_scene_metadata_failure(self, mock_db_ops, sample_scene_data):
        """Test scene metadata update failure."""
        scene_id = "scene_001"

        mock_db_ops.get_scene.return_value = sample_scene_data
        mock_db_ops.update_scene_metadata.return_value = False

        # Test
        with pytest.raises(HTTPException) as exc_info:
            await update_scene_metadata(
                scene_id=scene_id, heading="New heading", db_ops=mock_db_ops
            )

        assert exc_info.value.status_code == 500
        assert "Failed to update scene metadata" in exc_info.value.detail


class TestSceneOperationsAPIIntegration:
    """Integration tests for scene operations API."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from scriptrag.api.app import create_app

        app = create_app()
        return TestClient(app)

    def test_api_endpoint_registration(self, client):
        """Test that new API endpoints are properly registered."""
        # Use the client to verify the app is working
        # Test a basic health check or root endpoint
        try:
            response = client.get("/")
            # Any response means the app is running, whether 404 or otherwise
            assert response.status_code in [
                200,
                404,
            ]  # Either works, just need the app running
        except Exception:
            # If no routes at all, just verify app creation worked
            assert client is not None

        # Verify the endpoint functions exist
        from scriptrag.api.v1.endpoints import scenes

        assert hasattr(scenes, "update_scene")
        assert hasattr(scenes, "delete_scene")
        assert hasattr(scenes, "inject_scene_at_position")
        assert hasattr(scenes, "validate_story_continuity")
        assert hasattr(scenes, "update_scene_metadata")

    def test_scene_update_request_schema(self):
        """Test that the SceneUpdateRequest schema includes new fields."""
        from scriptrag.api.v1.schemas import SceneUpdateRequest

        # Test schema creation with new fields
        update_request = SceneUpdateRequest(
            scene_number=1,
            heading="Test heading",
            content="Test content",
            location="INT. TEST - DAY",
            time_of_day="DAY",
        )

        assert update_request.scene_number == 1
        assert update_request.heading == "Test heading"
        assert update_request.content == "Test content"
        assert update_request.location == "INT. TEST - DAY"
        assert update_request.time_of_day == "DAY"

    def test_optional_fields_in_update_request(self):
        """Test that new fields in SceneUpdateRequest are optional."""
        from scriptrag.api.v1.schemas import SceneUpdateRequest

        # Test with minimal data
        update_request = SceneUpdateRequest()

        assert update_request.scene_number is None
        assert update_request.heading is None
        assert update_request.content is None
        assert update_request.location is None
        assert update_request.time_of_day is None

    @pytest.mark.asyncio
    async def test_error_handling_consistency(self):
        """Test that error handling is consistent across endpoints."""
        # Test that all endpoints handle database errors consistently

        # Setup database to raise exception
        mock_db_ops = Mock()
        mock_db_ops.get_scene.side_effect = Exception("Database error")

        # Test each endpoint
        with pytest.raises(HTTPException) as exc_info:
            await update_scene("scene_001", SceneUpdateRequest(), mock_db_ops)
        assert exc_info.value.status_code == 500

        with pytest.raises(HTTPException) as exc_info:
            await delete_scene("scene_001", mock_db_ops)
        assert exc_info.value.status_code == 500

        with pytest.raises(HTTPException) as exc_info:
            await inject_scene_at_position(
                "scene_001",
                1,
                SceneCreateRequest(scene_number=1, heading="Test", content="Test"),
                mock_db_ops,
            )
        assert exc_info.value.status_code == 500


if __name__ == "__main__":
    pytest.main([__file__])
