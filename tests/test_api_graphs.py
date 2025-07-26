"""Comprehensive tests for graph visualization API endpoints."""

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
def client(mock_llm_client):
    """Create test client with mocked dependencies."""
    _ = mock_llm_client  # Mark as used
    app = create_app()
    with TestClient(app) as client:
        yield client


class TestCharacterGraphEndpoint:
    """Test suite for character graph endpoint."""

    def test_get_character_graph_success(self, client):
        """Test successful character graph retrieval."""
        script_id = str(uuid4())

        request_data = {
            "character_name": "JOHN",
            "script_id": script_id,
            "depth": 2,
            "min_interaction_count": 1,
        }

        mock_graph_data = {
            "nodes": [
                {
                    "id": "char_john",
                    "type": "character",
                    "label": "JOHN",
                    "properties": {"appearances": 15},
                },
                {
                    "id": "char_sarah",
                    "type": "character",
                    "label": "SARAH",
                    "properties": {"appearances": 8},
                },
                {
                    "id": "scene_001",
                    "type": "scene",
                    "label": "INT. COFFEE SHOP - DAY",
                    "properties": {"scene_number": 1},
                },
            ],
            "edges": [
                {
                    "source": "char_john",
                    "target": "char_sarah",
                    "type": "INTERACTS_WITH",
                    "weight": 5.0,
                    "properties": {"scene_count": 3},
                },
                {
                    "source": "char_john",
                    "target": "scene_001",
                    "type": "APPEARS_IN",
                    "weight": 1.0,
                },
            ],
        }

        with patch("scriptrag.api.v1.endpoints.graphs.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_character_graph.return_value = mock_graph_data
            mock_get_db.return_value = mock_db

            response = client.post("/api/v1/graphs/characters", json=request_data)

            assert response.status_code == 200
            data = response.json()

            # Check response structure
            assert data["status"] == "success"
            assert len(data["nodes"]) == 3
            assert len(data["edges"]) == 2

            # Check metadata
            assert data["metadata"]["character"] == "JOHN"
            assert data["metadata"]["total_nodes"] == 3
            assert data["metadata"]["total_edges"] == 2
            assert data["metadata"]["depth"] == 2

            # Check node details
            john_node = next(n for n in data["nodes"] if n["label"] == "JOHN")
            assert john_node["type"] == "character"
            assert john_node["properties"]["appearances"] == 15

            # Verify method call
            mock_db.get_character_graph.assert_called_once_with(
                character_name="JOHN",
                script_id=script_id,
                depth=2,
                min_interaction_count=1,
            )

    def test_get_character_graph_empty_result(self, client):
        """Test character graph with no interactions."""
        script_id = str(uuid4())

        request_data = {
            "character_name": "MINOR_CHARACTER",
            "script_id": script_id,
            "depth": 1,
            "min_interaction_count": 5,
        }

        mock_graph_data = {
            "nodes": [
                {
                    "id": "char_minor",
                    "type": "character",
                    "label": "MINOR_CHARACTER",
                    "properties": {"appearances": 1},
                }
            ],
            "edges": [],
        }

        with patch("scriptrag.api.v1.endpoints.graphs.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_character_graph.return_value = mock_graph_data
            mock_get_db.return_value = mock_db

            response = client.post("/api/v1/graphs/characters", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert len(data["nodes"]) == 1
            assert len(data["edges"]) == 0

    def test_get_character_graph_database_error(self, client):
        """Test database error during character graph retrieval."""
        request_data = {
            "character_name": "JOHN",
            "script_id": str(uuid4()),
            "depth": 2,
        }

        with patch("scriptrag.api.v1.endpoints.graphs.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_character_graph.side_effect = Exception(
                "Database connection failed"
            )
            mock_get_db.return_value = mock_db

            response = client.post("/api/v1/graphs/characters", json=request_data)

            assert response.status_code == 500
            assert "Failed to get character graph" in response.json()["detail"]

    def test_get_character_graph_validation_error(self, client):
        """Test validation error for character graph request."""
        # Missing required fields
        request_data = {
            "character_name": "JOHN",
            # Missing script_id
        }

        response = client.post("/api/v1/graphs/characters", json=request_data)

        assert response.status_code == 422  # Validation error


class TestTimelineGraphEndpoint:
    """Test suite for timeline graph endpoint."""

    def test_get_timeline_graph_success(self, client):
        """Test successful timeline graph retrieval."""
        script_id = str(uuid4())

        request_data = {
            "script_id": script_id,
            "group_by": "act",
            "include_characters": True,
        }

        mock_script = {"id": script_id, "title": "Test Script"}
        mock_graph_data = {
            "nodes": [
                {
                    "id": "act_1",
                    "type": "act",
                    "label": "Act 1",
                    "properties": {"scene_count": 10},
                },
                {
                    "id": "act_2",
                    "type": "act",
                    "label": "Act 2",
                    "properties": {"scene_count": 20},
                },
                {
                    "id": "scene_001",
                    "type": "scene",
                    "label": "Opening Scene",
                    "properties": {"scene_number": 1},
                },
                {
                    "id": "char_protagonist",
                    "type": "character",
                    "label": "PROTAGONIST",
                    "properties": {},
                },
            ],
            "edges": [
                {
                    "source": "act_1",
                    "target": "scene_001",
                    "type": "CONTAINS",
                    "weight": 1.0,
                },
                {
                    "source": "scene_001",
                    "target": "act_2",
                    "type": "LEADS_TO",
                    "weight": 1.0,
                },
                {
                    "source": "char_protagonist",
                    "target": "scene_001",
                    "type": "APPEARS_IN",
                    "weight": 1.0,
                },
            ],
        }

        with patch("scriptrag.api.v1.endpoints.graphs.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_script.return_value = mock_script
            mock_db.get_timeline_graph.return_value = mock_graph_data
            mock_get_db.return_value = mock_db

            response = client.post("/api/v1/graphs/timeline", json=request_data)

            assert response.status_code == 200
            data = response.json()

            # Check response structure
            assert data["status"] == "success"
            assert len(data["nodes"]) == 4
            assert len(data["edges"]) == 3

            # Check metadata
            assert data["metadata"]["script_id"] == script_id
            assert data["metadata"]["script_title"] == "Test Script"
            assert data["metadata"]["group_by"] == "act"

            # Verify method calls
            mock_db.get_script.assert_called_once_with(script_id)
            mock_db.get_timeline_graph.assert_called_once_with(
                script_id=script_id,
                group_by="act",
                include_characters=True,
            )

    def test_get_timeline_graph_script_not_found(self, client):
        """Test timeline graph for non-existent script."""
        script_id = str(uuid4())

        request_data = {
            "script_id": script_id,
            "group_by": "scene",
        }

        with patch("scriptrag.api.v1.endpoints.graphs.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_script.return_value = None
            mock_get_db.return_value = mock_db

            response = client.post("/api/v1/graphs/timeline", json=request_data)

            assert response.status_code == 404
            assert "Script not found" in response.json()["detail"]

    def test_get_timeline_graph_different_groupings(self, client):
        """Test timeline graph with different grouping options."""
        script_id = str(uuid4())

        for group_by in ["scene", "location", "day"]:
            request_data = {
                "script_id": script_id,
                "group_by": group_by,
                "include_characters": False,
            }

            mock_script = {"id": script_id, "title": "Test Script"}
            mock_graph_data = {
                "nodes": [
                    {
                        "id": f"{group_by}_1",
                        "type": group_by,
                        "label": f"{group_by.capitalize()} 1",
                        "properties": {},
                    }
                ],
                "edges": [],
            }

            with patch("scriptrag.api.v1.endpoints.graphs.get_db_ops") as mock_get_db:
                mock_db = AsyncMock()
                mock_db.get_script.return_value = mock_script
                mock_db.get_timeline_graph.return_value = mock_graph_data
                mock_get_db.return_value = mock_db

                response = client.post("/api/v1/graphs/timeline", json=request_data)

                assert response.status_code == 200
                data = response.json()
                assert data["metadata"]["group_by"] == group_by


class TestLocationGraphEndpoint:
    """Test suite for location graph endpoint."""

    def test_get_location_graph_success(self, client):
        """Test successful location graph retrieval."""
        script_id = str(uuid4())

        mock_script = {"id": script_id, "title": "Test Script"}
        mock_graph_data = {
            "nodes": [
                {
                    "id": "loc_coffee_shop",
                    "type": "location",
                    "label": "COFFEE SHOP",
                    "properties": {"scene_count": 5},
                },
                {
                    "id": "loc_office",
                    "type": "location",
                    "label": "OFFICE",
                    "properties": {"scene_count": 8},
                },
                {
                    "id": "scene_001",
                    "type": "scene",
                    "label": "INT. COFFEE SHOP - DAY",
                    "properties": {"scene_number": 1},
                },
                {
                    "id": "scene_002",
                    "type": "scene",
                    "label": "INT. OFFICE - DAY",
                    "properties": {"scene_number": 2},
                },
            ],
            "edges": [
                {
                    "source": "loc_coffee_shop",
                    "target": "scene_001",
                    "type": "CONTAINS_SCENE",
                    "weight": 1.0,
                },
                {
                    "source": "loc_office",
                    "target": "scene_002",
                    "type": "CONTAINS_SCENE",
                    "weight": 1.0,
                },
                {
                    "source": "scene_001",
                    "target": "scene_002",
                    "type": "FOLLOWED_BY",
                    "weight": 1.0,
                    "properties": {"time_gap": "CONTINUOUS"},
                },
            ],
        }

        with patch("scriptrag.api.v1.endpoints.graphs.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_script.return_value = mock_script
            mock_db.get_location_graph.return_value = mock_graph_data
            mock_get_db.return_value = mock_db

            response = client.get(f"/api/v1/graphs/scripts/{script_id}/locations")

            assert response.status_code == 200
            data = response.json()

            # Check response structure
            assert data["status"] == "success"
            assert len(data["nodes"]) == 4
            assert len(data["edges"]) == 3

            # Check metadata
            assert data["metadata"]["script_id"] == script_id
            assert data["metadata"]["script_title"] == "Test Script"
            assert data["metadata"]["total_locations"] == 2

            # Check location nodes
            location_nodes = [n for n in data["nodes"] if n["type"] == "location"]
            assert len(location_nodes) == 2
            assert any(n["label"] == "COFFEE SHOP" for n in location_nodes)
            assert any(n["label"] == "OFFICE" for n in location_nodes)

            # Verify method calls
            mock_db.get_script.assert_called_once_with(script_id)
            mock_db.get_location_graph.assert_called_once_with(script_id)

    def test_get_location_graph_script_not_found(self, client):
        """Test location graph for non-existent script."""
        script_id = str(uuid4())

        with patch("scriptrag.api.v1.endpoints.graphs.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_script.return_value = None
            mock_get_db.return_value = mock_db

            response = client.get(f"/api/v1/graphs/scripts/{script_id}/locations")

            assert response.status_code == 404
            assert "Script not found" in response.json()["detail"]

    def test_get_location_graph_empty_script(self, client):
        """Test location graph for script with no scenes."""
        script_id = str(uuid4())

        mock_script = {"id": script_id, "title": "Empty Script"}
        mock_graph_data = {"nodes": [], "edges": []}

        with patch("scriptrag.api.v1.endpoints.graphs.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_script.return_value = mock_script
            mock_db.get_location_graph.return_value = mock_graph_data
            mock_get_db.return_value = mock_db

            response = client.get(f"/api/v1/graphs/scripts/{script_id}/locations")

            assert response.status_code == 200
            data = response.json()
            assert len(data["nodes"]) == 0
            assert len(data["edges"]) == 0
            assert data["metadata"]["total_locations"] == 0

    def test_get_location_graph_database_error(self, client):
        """Test database error during location graph retrieval."""
        script_id = str(uuid4())

        mock_script = {"id": script_id, "title": "Test Script"}

        with patch("scriptrag.api.v1.endpoints.graphs.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_script.return_value = mock_script
            mock_db.get_location_graph.side_effect = Exception("Database error")
            mock_get_db.return_value = mock_db

            response = client.get(f"/api/v1/graphs/scripts/{script_id}/locations")

            assert response.status_code == 500
            assert "Failed to get location graph" in response.json()["detail"]


class TestGraphNodeTypeConversion:
    """Test proper conversion of graph node types."""

    def test_node_type_conversion(self, client):
        """Test that node types are properly converted to enum values."""
        script_id = str(uuid4())

        request_data = {
            "script_id": script_id,
            "group_by": "scene",
        }

        mock_script = {"id": script_id, "title": "Test Script"}
        mock_graph_data = {
            "nodes": [
                {"id": "1", "type": "scene", "label": "Scene 1"},
                {"id": "2", "type": "character", "label": "JOHN"},
                {"id": "3", "type": "location", "label": "OFFICE"},
                {"id": "4", "type": "act", "label": "Act 1"},
            ],
            "edges": [],
        }

        with patch("scriptrag.api.v1.endpoints.graphs.get_db_ops") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_script.return_value = mock_script
            mock_db.get_timeline_graph.return_value = mock_graph_data
            mock_get_db.return_value = mock_db

            response = client.post("/api/v1/graphs/timeline", json=request_data)

            assert response.status_code == 200
            data = response.json()

            # Check that all node types are valid enum values
            node_types = {node["type"] for node in data["nodes"]}
            expected_types = {"scene", "character", "location", "act"}
            assert node_types == expected_types
