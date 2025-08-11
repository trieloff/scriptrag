"""Basic integration tests for ScriptRAG workflow.

This module tests the basic workflow of ScriptRAG:
1. Parse a Fountain screenplay file
2. Index the screenplay into the database
3. Query the indexed content
"""

import sqlite3

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app
from scriptrag.config import ScriptRAGSettings, set_settings
from scriptrag.parser import FountainParser
from tests.utils import strip_ansi_codes

runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_settings():
    """Reset settings before and after each test."""
    set_settings(None)
    yield
    set_settings(None)


@pytest.fixture
def test_screenplay(tmp_path):
    """Create a simple test screenplay."""
    script_path = tmp_path / "test_script.fountain"
    content = """Title: Basic Workflow Test
Author: Test Suite
Draft date: 2024-01-01

INT. OFFICE - DAY

A simple test scene.

ALICE
Hello, this is a test.

BOB
Indeed it is.

They continue working.

FADE OUT.
"""
    script_path.write_text(content)
    return script_path


@pytest.fixture
def initialized_database(tmp_path):
    """Create and initialize a test database."""
    db_path = tmp_path / "test.db"

    # Create settings and initialize database
    settings = ScriptRAGSettings(database_path=db_path)
    set_settings(settings)

    # Initialize database using CLI
    result = runner.invoke(app, ["init", "--db-path", str(db_path), "--force"])
    assert result.exit_code == 0

    return db_path


@pytest.mark.integration
class TestBasicWorkflow:
    """Test the basic ScriptRAG workflow."""

    def test_parse_index_query_workflow(self, test_screenplay, initialized_database):
        """Test parsing, indexing and querying a screenplay.

        This test validates the core workflow:
        1. Parse a Fountain file
        2. Index it into the database
        3. Verify the content is indexed correctly
        """
        # Step 1: Parse the screenplay
        parser = FountainParser()
        script = parser.parse_file(test_screenplay)

        # Verify parsing worked
        assert script is not None
        assert script.title == "Basic Workflow Test"
        assert script.author == "Test Suite"
        assert len(script.scenes) == 1
        assert script.scenes[0].heading == "INT. OFFICE - DAY"

        # Step 2: Analyze the screenplay first (required before indexing)
        result = runner.invoke(app, ["analyze", str(test_screenplay.parent)])
        assert result.exit_code == 0

        # Step 3: Index the screenplay using the CLI
        result = runner.invoke(app, ["index", str(test_screenplay.parent)])
        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.stdout)
        assert "Indexed 1 script" in clean_output or "1" in clean_output

        # Step 4: Verify database contains the indexed content
        conn = sqlite3.connect(initialized_database)
        cursor = conn.cursor()

        # Check scripts table
        cursor.execute(
            "SELECT title, author FROM scripts WHERE title = ?",
            ("Basic Workflow Test",),
        )
        script_row = cursor.fetchone()
        assert script_row is not None
        assert script_row[0] == "Basic Workflow Test"
        assert script_row[1] == "Test Suite"

        # Check scenes table
        cursor.execute(
            """
            SELECT s.heading, s.content
            FROM scenes s
            JOIN scripts sc ON s.script_id = sc.id
            WHERE sc.title = ?
        """,
            ("Basic Workflow Test",),
        )
        scene_rows = cursor.fetchall()
        assert len(scene_rows) == 1
        assert scene_rows[0][0] == "INT. OFFICE - DAY"
        assert "simple test scene" in scene_rows[0][1].lower()

        # Check characters are indexed
        cursor.execute(
            """
            SELECT DISTINCT c.name
            FROM characters c
            JOIN scripts s ON c.script_id = s.id
            WHERE s.title = ?
            ORDER BY c.name
        """,
            ("Basic Workflow Test",),
        )
        characters = [row[0] for row in cursor.fetchall()]
        assert "ALICE" in characters
        assert "BOB" in characters

        conn.close()

    def test_cli_workflow(self, test_screenplay, tmp_path, monkeypatch):
        """Test the complete CLI workflow."""
        db_path = tmp_path / "workflow.db"

        # Set the database path in environment
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize database
        result = runner.invoke(app, ["init", "--db-path", str(db_path), "--force"])
        assert result.exit_code == 0
        assert "Database initialized" in strip_ansi_codes(result.stdout)

        # Analyze the screenplay first
        result = runner.invoke(app, ["analyze", str(test_screenplay.parent)])
        assert result.exit_code == 0

        # Index the screenplay
        result = runner.invoke(app, ["index", str(test_screenplay.parent)])
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "Scripts Indexed" in output and "1" in output

        # Verify script is indexed by querying the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM scripts")
        count = cursor.fetchone()[0]
        assert count == 1
        conn.close()
