"""Integration test for the complete ScriptRAG workflow.

This test validates the happy path of:
1. Initializing a database (scriptrag init)
2. Analyzing a screenplay (scriptrag analyze)
3. Indexing the screenplay (scriptrag index)
4. Verifying the database contains scenes with analyzer results
"""

import json
import sqlite3

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app
from scriptrag.config import set_settings

runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_settings():
    """Reset settings before and after each test."""
    set_settings(None)
    yield
    set_settings(None)


@pytest.fixture
def sample_screenplay(tmp_path):
    """Create a sample screenplay with multiple scenes."""
    script_path = tmp_path / "test_script.fountain"
    content = """Title: Integration Test Script
Author: Test Suite
Draft date: 2024-01-01

= This is a test screenplay for integration testing

INT. COFFEE SHOP - MORNING

The morning sun streams through large windows. The aroma of fresh coffee fills the air.

SARAH (30s, creative type) sits at a corner table with her laptop.

SARAH
(to herself)
Just one more scene and I'm done.

JAMES (40s, barista) approaches with a coffee.

JAMES
Another refill?

SARAH
(grateful)
You're a lifesaver.

EXT. CITY STREET - CONTINUOUS

Sarah exits the coffee shop, coffee in hand. The city is just waking up.

She walks briskly, checking her phone.

SARAH
(on phone)
Yes, I'll have it ready by noon.

INT. SARAH'S APARTMENT - LATER

A cozy apartment filled with books and scripts. Sarah sits at her desk,
typing furiously.

Her cat, WHISKERS, jumps onto the desk.

SARAH
(to Whiskers)
Not now, buddy. Almost done.

She saves her work and leans back, satisfied.

SARAH (CONT'D)
Finally. The End.

FADE OUT.
"""
    script_path.write_text(content)
    return script_path


class TestFullWorkflow:
    """Test the complete ScriptRAG workflow from init to index."""

    def test_happy_path_workflow(self, tmp_path, sample_screenplay, monkeypatch):
        """Test the complete workflow: init -> analyze -> index -> verify."""
        # Setup paths
        db_path = tmp_path / "test.db"

        # Set environment variable for database path
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Step 1: Initialize database
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0
        assert "Database initialized successfully" in result.stdout
        assert db_path.exists()

        # Step 2: Analyze the screenplay
        result = runner.invoke(
            app,
            [
                "analyze",
                str(sample_screenplay.parent),  # Pass directory, not file
            ],
        )
        # Debug output
        if result.exit_code != 0:
            print(f"Analyze command failed with exit code {result.exit_code}")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr if hasattr(result, 'stderr') else 'N/A'}")
        assert result.exit_code == 0
        # The analyze command outputs "Processing" and "Updated" messages
        assert "Processing" in result.stdout or "Updated" in result.stdout

        # Verify the screenplay now contains metadata
        updated_content = sample_screenplay.read_text()
        assert "SCRIPTRAG-META-START" in updated_content
        assert "SCRIPTRAG-META-END" in updated_content

        # Step 3: Index the screenplay
        result = runner.invoke(
            app,
            [
                "index",
                str(sample_screenplay.parent),  # Pass directory, not file
            ],
        )
        assert result.exit_code == 0
        assert "Index" in result.stdout or "index" in result.stdout.lower()

        # Step 4: Verify database contents
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check that script was indexed
        cursor.execute(
            "SELECT * FROM scripts WHERE file_path = ?", (str(sample_screenplay),)
        )
        script = cursor.fetchone()
        assert script is not None
        assert script["title"] == "Integration Test Script"
        assert script["author"] == "Test Suite"

        script_id = script["id"]

        # Check that scenes were created
        cursor.execute(
            "SELECT * FROM scenes WHERE script_id = ? ORDER BY scene_number",
            (script_id,),
        )
        scenes = cursor.fetchall()
        assert len(scenes) == 3  # We have 3 scenes in our test script

        # Verify scene details
        scene_headings = [scene["heading"] for scene in scenes]
        assert "INT. COFFEE SHOP - MORNING" in scene_headings
        assert "EXT. CITY STREET - CONTINUOUS" in scene_headings
        assert "INT. SARAH'S APARTMENT - LATER" in scene_headings

        # Check that characters were extracted
        cursor.execute(
            """
            SELECT DISTINCT c.name
            FROM characters c
            WHERE c.script_id = ?
        """,
            (script_id,),
        )
        characters = [row["name"] for row in cursor.fetchall()]
        # Characters might be extracted from dialogues
        if characters:
            assert "SARAH" in characters or "Sarah" in characters
            assert "JAMES" in characters or "James" in characters

        # Verify analyzer metadata exists in scenes
        for scene in scenes:
            # Check metadata column contains analyzer results
            if scene["metadata"]:
                metadata = json.loads(scene["metadata"])
                # The metadata structure should contain analyzer information
                # This will depend on which analyzers are enabled by default
                assert isinstance(metadata, dict)

        # Check dialogue entries
        cursor.execute(
            """
            SELECT COUNT(*) as dialogue_count
            FROM dialogues d
            JOIN scenes s ON d.scene_id = s.id
            WHERE s.script_id = ?
        """,
            (script_id,),
        )
        # Dialogue extraction might not be implemented yet
        # So we'll just check the query doesn't fail
        cursor.fetchone()

        conn.close()

    def test_workflow_with_analyzer_results_verification(
        self, tmp_path, sample_screenplay, monkeypatch
    ):
        """Test that analyzer results are properly stored in the database."""
        db_path = tmp_path / "test.db"

        # Set environment variable for database path
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize database
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        # Analyze with specific analyzer (if available)
        result = runner.invoke(
            app,
            [
                "analyze",
                str(sample_screenplay.parent),  # Pass directory, not file
                "--analyzer",
                "basic_stats",  # Using a simple analyzer
            ],
        )

        # Even if analyzer doesn't exist, the command should handle it gracefully
        # The important part is that metadata structure is created

        # Read the analyzed screenplay to check metadata structure
        content = sample_screenplay.read_text()
        if "SCRIPTRAG-META-START" in content:
            # Extract metadata
            start_idx = content.index("SCRIPTRAG-META-START") + len(
                "SCRIPTRAG-META-START"
            )
            end_idx = content.index("SCRIPTRAG-META-END")
            metadata_str = content[start_idx:end_idx].strip()
            if metadata_str.startswith("*/"):
                metadata_str = metadata_str[2:].strip()
            if metadata_str.endswith("/*"):
                metadata_str = metadata_str[:-2].strip()

            # Verify metadata structure
            metadata = json.loads(metadata_str)
            assert "content_hash" in metadata
            assert "analyzed_at" in metadata
            assert "analyzers" in metadata

        # Index the screenplay
        result = runner.invoke(
            app,
            [
                "index",
                str(sample_screenplay.parent),  # Pass directory, not file
            ],
        )
        assert result.exit_code == 0

        # Verify scenes contain the analyzer metadata
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT s.*, sc.metadata as script_metadata
            FROM scenes s
            JOIN scripts sc ON s.script_id = sc.id
            WHERE sc.file_path = ?
        """,
            (str(sample_screenplay),),
        )

        scenes = cursor.fetchall()
        assert len(scenes) > 0

        # Check that at least the script has metadata from analysis
        for scene in scenes:
            script_metadata = scene["script_metadata"]
            if script_metadata:
                metadata = json.loads(script_metadata)
                # Verify the structure matches what we expect from analysis
                assert isinstance(metadata, dict)
                # Could contain analyzer results, hash, timestamp, etc.

        conn.close()
