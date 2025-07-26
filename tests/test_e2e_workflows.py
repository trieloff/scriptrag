"""End-to-end tests for common ScriptRAG workflows.

These tests simulate real user workflows from start to finish:
1. Uploading and parsing scripts
2. Building knowledge graphs
3. Searching for scenes and characters
4. Generating insights and visualizations
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from scriptrag.api.app import create_app
from scriptrag.cli import app as typer_app


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    with patch("scriptrag.database.embedding_pipeline.LLMClient") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def api_client(mock_llm_client):
    """Create API test client."""
    _ = mock_llm_client  # Mark as used
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def cli_runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_fountain_file(tmp_path):
    """Create a sample Fountain file."""
    script_content = """Title: The Heist
Author: Jane Doe
Draft: First

FADE IN:

INT. ABANDONED WAREHOUSE - NIGHT

A dimly lit warehouse. ALEX (30s, skilled thief) studies blueprints spread
across a dusty table.

MAYA (20s, tech expert) types rapidly on her laptop, multiple screens glowing.

MAYA
The security system resets every 3 hours. We have a 5-minute window.

ALEX
(focused)
That's all we need.

MARCUS (40s, getaway driver) enters, car keys jingling.

MARCUS
Vehicle's ready. Are we doing this?

Alex and Maya exchange determined looks.

ALEX
Tonight, we take back what's ours.

EXT. CORPORATE BUILDING - NIGHT

The team approaches a gleaming office tower. Security cameras sweep the perimeter.

MAYA
(whispering into earpiece)
Jamming their signals... now.

The cameras freeze. Alex moves swiftly to the service entrance.

INT. CORPORATE BUILDING - CORRIDOR - CONTINUOUS

Alex navigates through dark hallways, Maya's voice guiding through the earpiece.

MAYA (V.O.)
Left at the junction. Elevator's disabled. Take the stairs.

INT. CORPORATE BUILDING - SERVER ROOM - NIGHT

Alex reaches the server room. Maya's custom device blinks green - access granted.

ALEX
I'm in. Downloading now.

Suddenly, alarms blare. Red lights flash.

MAYA (V.O.)
(urgent)
They've detected us! Get out NOW!

Alex grabs the device and sprints for the exit.

EXT. CORPORATE BUILDING - NIGHT

Marcus's car screeches to a halt. Alex dives in. They speed away as security
floods the building.

INT. MARCUS'S CAR - MOVING - NIGHT

The team catches their breath. Alex holds up the device - mission complete.

MAYA
Did we get it all?

ALEX
Every last byte.

MARCUS
(grinning)
Just another Tuesday night.

FADE OUT.

THE END"""

    script_file = tmp_path / "the_heist.fountain"
    script_file.write_text(script_content)
    return script_file


class TestE2EScriptUploadWorkflow:
    """Test the complete script upload and processing workflow."""

    def test_api_script_upload_and_search(self, api_client, sample_fountain_file):
        """Test uploading a script via API and searching it."""
        # Step 1: Upload the script
        with sample_fountain_file.open() as f:
            script_content = f.read()

        upload_data = {
            "title": "The Heist",
            "content": script_content,
            "author": "Jane Doe",
        }

        response = api_client.post("/api/v1/scripts/upload", json=upload_data)
        assert response.status_code == 200

        script_data = response.json()
        script_id = script_data["id"]
        assert script_data["title"] == "The Heist"
        assert script_data["author"] == "Jane Doe"
        assert script_data["scene_count"] > 0

        # Step 2: List scripts to verify it's there
        response = api_client.get("/api/v1/scripts/")
        assert response.status_code == 200

        scripts = response.json()
        assert any(s["id"] == script_id for s in scripts)

        # Step 3: Get script details
        response = api_client.get(f"/api/v1/scripts/{script_id}")
        assert response.status_code == 200

        script_detail = response.json()
        assert script_detail["id"] == script_id
        assert len(script_detail["scenes"]) > 0
        assert len(script_detail["characters"]) >= 3  # Alex, Maya, Marcus

        # Step 4: Search for scenes
        search_data = {
            "query": "warehouse security heist",
            "limit": 5,
        }

        response = api_client.post("/api/v1/search/scenes", json=search_data)
        assert response.status_code == 200

        search_results = response.json()
        assert len(search_results["results"]) > 0
        assert search_results["results"][0]["script_id"] == script_id

    def test_cli_import_and_analyze_workflow(
        self, cli_runner, sample_fountain_file, tmp_path
    ):
        """Test importing and analyzing a script via CLI."""
        # Create a test database
        db_path = tmp_path / "test_cli.db"

        # Step 1: Initialize database
        result = cli_runner.invoke(
            typer_app,
            ["db", "init", "--path", str(db_path)],
        )
        assert result.exit_code == 0
        assert "Database initialized successfully" in result.stdout

        # Step 2: Import the script
        with patch("scriptrag.cli.get_database_path", return_value=db_path):
            result = cli_runner.invoke(
                typer_app,
                ["import", str(sample_fountain_file)],
            )

        assert result.exit_code == 0
        assert "Successfully imported" in result.stdout

        # Step 3: List scripts
        with patch("scriptrag.cli.get_database_path", return_value=db_path):
            result = cli_runner.invoke(typer_app, ["list"])

        assert result.exit_code == 0
        assert "The Heist" in result.stdout
        assert "Jane Doe" in result.stdout

        # Step 4: Analyze the script
        with patch("scriptrag.cli.get_database_path", return_value=db_path):
            result = cli_runner.invoke(
                typer_app,
                ["analyze", "The Heist"],
            )

        assert result.exit_code == 0
        assert "scenes" in result.stdout
        assert "characters" in result.stdout


class TestE2ECharacterAnalysisWorkflow:
    """Test character analysis and relationship workflows."""

    def test_character_relationships_via_api(self, api_client):
        """Test analyzing character relationships through the API."""
        # First, create a script with complex character interactions
        script_content = """Title: Complex Relationships
Author: Test Author

INT. LIVING ROOM - DAY

ALICE, BOB, and CHARLIE sit in tense silence.

ALICE
We can't keep pretending everything's fine.

BOB
(to Charlie)
This is your fault.

CHARLIE
(defensive)
How is this my fault? You're the one who—

ALICE
(interrupting)
Stop! Both of you!

DAVID enters, sensing the tension.

DAVID
What's going on here?

ALICE
(to David)
They're at it again.

BOB
(to David)
Stay out of this.

CHARLIE
(to David)
Actually, we could use a mediator.

The group continues to argue, relationships straining."""

        # Upload the script
        upload_data = {
            "title": "Complex Relationships",
            "content": script_content,
            "author": "Test Author",
        }

        response = api_client.post("/api/v1/scripts/upload", json=upload_data)
        assert response.status_code == 200
        script_id = response.json()["id"]

        # Get character graph for Alice
        graph_request = {
            "character_name": "ALICE",
            "script_id": script_id,
            "depth": 2,
            "min_interaction_count": 1,
        }

        with patch("scriptrag.api.v1.endpoints.graphs.get_db_ops") as mock_get_db:
            mock_db = MagicMock()
            mock_db.get_character_graph.return_value = {
                "nodes": [
                    {"id": "char_alice", "type": "character", "label": "ALICE"},
                    {"id": "char_bob", "type": "character", "label": "BOB"},
                    {"id": "char_charlie", "type": "character", "label": "CHARLIE"},
                    {"id": "char_david", "type": "character", "label": "DAVID"},
                ],
                "edges": [
                    {
                        "source": "char_alice",
                        "target": "char_bob",
                        "type": "TALKS_TO",
                        "weight": 2,
                    },
                    {
                        "source": "char_alice",
                        "target": "char_charlie",
                        "type": "TALKS_TO",
                        "weight": 1,
                    },
                    {
                        "source": "char_alice",
                        "target": "char_david",
                        "type": "TALKS_TO",
                        "weight": 1,
                    },
                ],
            }
            mock_get_db.return_value = mock_db

            response = api_client.post("/api/v1/graphs/characters", json=graph_request)

        assert response.status_code == 200
        graph_data = response.json()

        # Verify character connections
        assert len(graph_data["nodes"]) == 4
        assert len(graph_data["edges"]) == 3
        assert graph_data["metadata"]["character"] == "ALICE"


class TestE2ESceneManagementWorkflow:
    """Test scene creation, editing, and reordering workflows."""

    def test_scene_crud_operations(self, api_client):
        """Test complete scene CRUD workflow."""
        # Create a script first
        script_data = {
            "title": "Scene Management Test",
            "content": (
                "Title: Scene Management Test\n\nINT. ROOM - DAY\n\nInitial scene."
            ),
            "author": "Test Author",
        }

        response = api_client.post("/api/v1/scripts/upload", json=script_data)
        assert response.status_code == 200
        script_id = response.json()["id"]

        # Mock database operations for scene management
        with patch("scriptrag.api.v1.endpoints.scenes.get_db_ops") as mock_get_db:
            mock_db = MagicMock()
            mock_db.get_script.return_value = {
                "id": script_id,
                "title": "Scene Management Test",
            }

            # Test 1: Create a new scene
            new_scene_id = "scene_new_001"
            mock_db.create_scene.return_value = new_scene_id
            mock_db.get_scene.return_value = {
                "id": new_scene_id,
                "script_id": script_id,
                "scene_number": 2,
                "heading": "EXT. GARDEN - DAY",
                "content": "A beautiful garden.",
                "character_count": 0,
                "word_count": 4,
                "page_start": 2.0,
                "page_end": 2.1,
                "has_embedding": False,
            }
            mock_get_db.return_value = mock_db

            scene_data = {
                "scene_number": 2,
                "heading": "EXT. GARDEN - DAY",
                "content": "A beautiful garden.",
            }

            response = api_client.post(
                f"/api/v1/scenes/?script_id={script_id}", json=scene_data
            )

            assert response.status_code == 200
            created_scene = response.json()
            assert created_scene["heading"] == "EXT. GARDEN - DAY"

            # Test 2: Update the scene
            mock_db.get_scene.side_effect = [
                created_scene,  # First call for checking existence
                {**created_scene, "heading": "EXT. GARDEN - SUNSET"},  # After update
            ]
            mock_db.update_scene.return_value = None

            update_data = {
                "heading": "EXT. GARDEN - SUNSET",
                "content": "A beautiful garden at sunset.",
            }

            response = api_client.patch(
                f"/api/v1/scenes/{new_scene_id}", json=update_data
            )

            assert response.status_code == 200
            updated_scene = response.json()
            assert updated_scene["heading"] == "EXT. GARDEN - SUNSET"

            # Test 3: Delete the scene
            mock_db.get_scene.side_effect = None
            mock_db.get_scene.return_value = created_scene
            mock_db.delete_scene.return_value = None

            response = api_client.delete(f"/api/v1/scenes/{new_scene_id}")

            assert response.status_code == 200
            assert "deleted successfully" in response.json()["message"]


class TestE2ESearchAndRetrievalWorkflow:
    """Test search and retrieval workflows."""

    def test_semantic_search_workflow(self, api_client):
        """Test semantic search across scripts."""
        # Upload multiple scripts with different themes
        scripts = [
            {
                "title": "Action Script",
                "content": """Title: Action Script

INT. WAREHOUSE - NIGHT

Explosions rock the building. HERO fights through enemies.

HERO
This ends tonight!""",
                "author": "Action Author",
            },
            {
                "title": "Romance Script",
                "content": """Title: Romance Script

EXT. PARK - SUNSET

LOVER1 and LOVER2 walk hand in hand.

LOVER1
I've never felt this way before.

LOVER2
Neither have I.""",
                "author": "Romance Author",
            },
            {
                "title": "Mystery Script",
                "content": """Title: Mystery Script

INT. LIBRARY - NIGHT

DETECTIVE examines clues by candlelight.

DETECTIVE
The answer is hidden in these pages.""",
                "author": "Mystery Author",
            },
        ]

        script_ids = []
        for script in scripts:
            response = api_client.post("/api/v1/scripts/upload", json=script)
            assert response.status_code == 200
            script_ids.append(response.json()["id"])

        # Test different search queries
        test_queries = [
            ("explosion fight action", "Action Script"),
            ("love romance sunset", "Romance Script"),
            ("mystery clues detective", "Mystery Script"),
            ("night darkness", None),  # Should match multiple
        ]

        for query, expected_title in test_queries:
            search_data = {"query": query, "limit": 10}

            response = api_client.post("/api/v1/search/scenes", json=search_data)
            assert response.status_code == 200

            results = response.json()["results"]

            if expected_title:
                # Should find the specific script
                matching_results = [r for r in results if r["script_id"] in script_ids]
                assert len(matching_results) > 0
            else:
                # Should find multiple scripts
                unique_scripts = {
                    r["script_id"] for r in results if r["script_id"] in script_ids
                }
                assert len(unique_scripts) >= 2


class TestE2EBulkOperationsWorkflow:
    """Test bulk import and processing workflows."""

    def test_bulk_import_tv_series(self, cli_runner, tmp_path):
        """Test importing an entire TV series."""
        # Create a mock TV series structure
        series_dir = tmp_path / "BreakingBad"
        series_dir.mkdir()

        episodes = [
            ("S01E01_Pilot.fountain", "Pilot"),
            ("S01E02_CatsInTheBag.fountain", "Cat's in the Bag"),
            ("S01E03_AndTheBagInTheRiver.fountain", "And the Bag's in the River"),
            ("S02E01_SevenThirtySeven.fountain", "Seven Thirty-Seven"),
        ]

        for filename, title in episodes:
            episode_file = series_dir / filename
            episode_file.write_text(
                f"""Title: {title}
Series: Breaking Bad

FADE IN:

INT. RV - DAY

Episode content here.

FADE OUT."""
            )

        # Create test database
        db_path = tmp_path / "test_bulk.db"

        # Initialize database
        result = cli_runner.invoke(
            typer_app,
            ["db", "init", "--path", str(db_path)],
        )
        assert result.exit_code == 0

        # Bulk import the series
        with patch("scriptrag.cli.get_database_path", return_value=db_path):
            result = cli_runner.invoke(
                typer_app,
                ["import", str(series_dir), "--recursive"],
            )

        assert result.exit_code == 0
        assert "Successfully imported 4" in result.stdout

        # Verify series structure
        with patch("scriptrag.cli.get_database_path", return_value=db_path):
            result = cli_runner.invoke(typer_app, ["list"])

        assert result.exit_code == 0
        assert "Pilot" in result.stdout
        assert "Cat's in the Bag" in result.stdout
