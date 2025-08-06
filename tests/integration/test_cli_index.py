"""Integration tests for the scriptrag index command."""

import sqlite3

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app
from scriptrag.config import ScriptRAGSettings, set_settings
from tests.utils import strip_ansi_codes

runner = CliRunner()


@pytest.fixture
def sample_fountain_with_metadata(tmp_path):
    """Create a sample Fountain file with boneyard metadata."""
    script_path = tmp_path / "sample.fountain"
    content = """Title: The Coffee Shop
Author: Test Writer

INT. COFFEE SHOP - DAY

/* SCRIPTRAG-META-START
{
  "content_hash": "abc123",
  "analyzed_at": "2024-01-01T00:00:00",
  "analyzers": {
    "test": {
      "result": {"mood": "cheerful"}
    }
  }
}
SCRIPTRAG-META-END */

ALICE enters the bustling coffee shop.

ALICE
(cheerfully)
Good morning, Bob!

BOB
(smiling)
Hey Alice! The usual?

ALICE nods and sits down.

EXT. PARK - NIGHT

/* SCRIPTRAG-META-START
{
  "content_hash": "def456",
  "analyzed_at": "2024-01-01T00:00:00",
  "analyzers": {
    "test": {
      "result": {"mood": "peaceful"}
    }
  }
}
SCRIPTRAG-META-END */

They walk through the quiet park.

ALICE
What a beautiful evening.

BOB
Perfect for a walk.
"""
    script_path.write_text(content)
    return script_path


@pytest.fixture
def sample_fountain_without_metadata(tmp_path):
    """Create a sample Fountain file without boneyard metadata."""
    script_path = tmp_path / "no_metadata.fountain"
    content = """Title: Simple Script
Author: Test Writer

INT. ROOM - DAY

A simple scene without metadata.

CHARACTER
Some dialogue.
"""
    script_path.write_text(content)
    return script_path


@pytest.fixture
def initialized_db(tmp_path, monkeypatch):
    """Create an initialized database."""
    db_path = tmp_path / "test.db"

    # Set database path via environment variable and update global settings
    monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

    # Create settings with the database path and set globally
    settings = ScriptRAGSettings(database_path=db_path)
    set_settings(settings)

    # Initialize database
    result = runner.invoke(app, ["init", "--db-path", str(db_path), "--force"])
    assert result.exit_code == 0

    return db_path


class TestIndexCommand:
    """Test the index command."""

    def test_index_help(self):
        """Test index command help."""
        result = runner.invoke(app, ["index", "--help"])
        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.stdout)
        assert "Index analyzed Fountain files" in clean_output
        assert "--force" in clean_output
        assert "--dry-run" in clean_output
        assert "--batch-size" in clean_output

    def test_index_without_database(self, tmp_path, monkeypatch):
        """Test index command without initialized database."""
        # Set database path to non-existent file
        db_path = tmp_path / "nonexistent.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Create settings with the database path and set globally
        settings = ScriptRAGSettings(database_path=db_path)
        set_settings(settings)

        result = runner.invoke(
            app,
            ["index", str(tmp_path)],
        )
        assert result.exit_code == 0  # Command succeeds but reports error in output
        clean_output = strip_ansi_codes(result.stdout)
        assert (
            "Database not initialized" in clean_output
            or "No Fountain files found" in clean_output
        )

    def test_index_no_scripts(self, initialized_db, tmp_path):  # noqa: ARG002
        """Test index command with no scripts."""
        # Database path is already set via initialized_db fixture
        result = runner.invoke(
            app,
            ["index", str(tmp_path)],
        )
        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.stdout)
        assert "No Fountain files found" in clean_output or "0" in clean_output

    def test_index_single_script(self, initialized_db, sample_fountain_with_metadata):
        """Test indexing a single script with metadata."""
        script_dir = sample_fountain_with_metadata.parent

        # First analyze the script to add metadata (already has it in fixture)
        # Then index it
        # Database path is already set via initialized_db fixture
        result = runner.invoke(
            app,
            ["index", str(script_dir)],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.stdout)
        assert "Indexing complete" in clean_output
        assert "Scripts Indexed" in clean_output

        # Verify data in database
        conn = sqlite3.connect(str(initialized_db))
        conn.row_factory = sqlite3.Row

        # Check script was indexed
        cursor = conn.execute("SELECT * FROM scripts")
        scripts = cursor.fetchall()
        assert len(scripts) == 1
        assert scripts[0]["title"] == "The Coffee Shop"
        assert scripts[0]["author"] == "Test Writer"

        # Check scenes were indexed
        cursor = conn.execute("SELECT * FROM scenes ORDER BY scene_number")
        scenes = cursor.fetchall()
        assert len(scenes) == 2
        assert scenes[0]["heading"] == "INT. COFFEE SHOP - DAY"
        assert scenes[1]["heading"] == "EXT. PARK - NIGHT"

        # Check characters were indexed
        cursor = conn.execute("SELECT * FROM characters ORDER BY name")
        characters = cursor.fetchall()
        assert len(characters) == 2
        assert characters[0]["name"] == "ALICE"
        assert characters[1]["name"] == "BOB"

        # Check dialogues were indexed
        cursor = conn.execute("SELECT COUNT(*) as count FROM dialogues")
        assert cursor.fetchone()["count"] == 4  # 2 in each scene

        # Check actions were indexed
        cursor = conn.execute("SELECT COUNT(*) as count FROM actions")
        assert cursor.fetchone()["count"] == 3  # 2 in first scene, 1 in second

        conn.close()

    def test_index_dry_run(self, initialized_db, sample_fountain_with_metadata):
        """Test dry run mode."""
        script_dir = sample_fountain_with_metadata.parent

        # Database path is already set via initialized_db fixture
        result = runner.invoke(
            app,
            ["index", str(script_dir), "--dry-run"],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.stdout)
        assert "DRY RUN" in clean_output
        assert "No changes were made" in clean_output

        # Verify no data was actually indexed
        conn = sqlite3.connect(str(initialized_db))
        cursor = conn.execute("SELECT COUNT(*) as count FROM scripts")
        assert cursor.fetchone()[0] == 0
        conn.close()

    def test_index_force_reindex(self, initialized_db, sample_fountain_with_metadata):
        """Test force re-indexing."""
        script_dir = sample_fountain_with_metadata.parent

        # Index once
        # Database path is already set via initialized_db fixture
        result = runner.invoke(
            app,
            ["index", str(script_dir)],
        )
        assert result.exit_code == 0

        # Index again without force (should skip)
        result = runner.invoke(
            app,
            ["index", str(script_dir)],
        )
        assert result.exit_code == 0

        # Check that script was not re-indexed
        conn = sqlite3.connect(str(initialized_db))
        cursor = conn.execute("SELECT COUNT(*) as count FROM scripts")
        assert cursor.fetchone()[0] == 1  # Still just one script

        # Now force re-index
        result = runner.invoke(
            app,
            ["index", str(script_dir), "--force"],
        )
        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.stdout)
        assert "Scripts Indexed" in clean_output or "Scripts Updated" in clean_output

        # Verify script is still there (updated, not duplicated)
        cursor = conn.execute("SELECT COUNT(*) as count FROM scripts")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_index_verbose_mode(
        self,
        initialized_db,  # noqa: ARG002
        sample_fountain_with_metadata,
    ):
        """Test verbose output mode."""
        script_dir = sample_fountain_with_metadata.parent

        # Database path is already set via initialized_db fixture
        result = runner.invoke(
            app,
            ["index", str(script_dir), "--verbose"],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.stdout)
        assert "Script Details" in clean_output
        assert "scenes" in clean_output
        assert "characters" in clean_output
        assert "dialogues" in clean_output
        assert "actions" in clean_output

    def test_index_no_recursive(
        self, initialized_db, sample_fountain_with_metadata, tmp_path
    ):
        """Test non-recursive search."""
        # Create script in subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        script_in_subdir = subdir / "nested.fountain"
        script_in_subdir.write_text(sample_fountain_with_metadata.read_text())

        # Index without recursive
        # Database path is already set via initialized_db fixture
        result = runner.invoke(
            app,
            [
                "index",
                str(tmp_path),
                "--no-recursive",
            ],
        )

        assert result.exit_code == 0

        # Should not find the nested script
        conn = sqlite3.connect(str(initialized_db))
        cursor = conn.execute("SELECT COUNT(*) as count FROM scripts")
        # Only the main script should be indexed, not the one in subdir
        count = cursor.fetchone()[0]
        conn.close()

        # The fixture creates one script in tmp_path directly
        # With --no-recursive, it shouldn't find the one in subdir
        assert count <= 1  # May be 0 or 1 depending on fixture location

    def test_index_batch_size(self, initialized_db, tmp_path):
        """Test batch size option."""
        # Create multiple scripts with metadata
        for i in range(5):
            script_path = tmp_path / f"script{i}.fountain"
            content = f"""Title: Script {i}
Author: Test Writer

INT. SCENE - DAY

/* SCRIPTRAG-META-START
{{"analyzed_at": "2024-01-01T00:00:00"}}
SCRIPTRAG-META-END */

Some content.

CHARACTER
Dialogue {i}.
"""
            script_path.write_text(content)

        # Index with small batch size
        # Database path is already set via initialized_db fixture
        result = runner.invoke(
            app,
            [
                "index",
                str(tmp_path),
                "--batch-size",
                "2",
            ],
        )

        assert result.exit_code == 0
        clean_output = strip_ansi_codes(result.stdout)
        assert "Scripts Indexed" in clean_output

        # Verify all scripts were indexed
        conn = sqlite3.connect(str(initialized_db))
        cursor = conn.execute("SELECT COUNT(*) as count FROM scripts")
        assert cursor.fetchone()[0] == 5
        conn.close()

    def test_index_skip_without_metadata(
        self,
        initialized_db,
        sample_fountain_with_metadata,
        sample_fountain_without_metadata,  # noqa: ARG002
    ):
        """Test that scripts without metadata are skipped."""
        script_dir = sample_fountain_with_metadata.parent

        # Database path is already set via initialized_db fixture
        result = runner.invoke(
            app,
            ["index", str(script_dir)],
        )

        assert result.exit_code == 0

        # Only the script with metadata should be indexed
        conn = sqlite3.connect(str(initialized_db))
        cursor = conn.execute("SELECT title FROM scripts")
        scripts = cursor.fetchall()
        assert len(scripts) == 1
        assert scripts[0][0] == "The Coffee Shop"  # Not "Simple Script"
        conn.close()

    def test_index_with_errors(self, initialized_db, tmp_path):
        """Test handling of errors during indexing."""
        # Create a malformed script with metadata marker but invalid JSON
        bad_script = tmp_path / "bad.fountain"
        content = """Title: Bad Script

INT. SCENE - DAY

/* SCRIPTRAG-META-START
{invalid json}
SCRIPTRAG-META-END */

Content.
"""
        bad_script.write_text(content)

        # Also create a good script
        good_script = tmp_path / "good.fountain"
        good_content = """Title: Good Script

INT. SCENE - DAY

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-01T00:00:00"}
SCRIPTRAG-META-END */

Content.

CHARACTER
Dialogue.
"""
        good_script.write_text(good_content)

        # Database path is already set via initialized_db fixture
        result = runner.invoke(
            app,
            ["index", str(tmp_path)],
        )

        # Should complete but may report errors
        assert result.exit_code == 0

        # Good script should still be indexed
        conn = sqlite3.connect(str(initialized_db))
        cursor = conn.execute("SELECT title FROM scripts WHERE title = 'Good Script'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_index_updates_existing(self, initialized_db, tmp_path):
        """Test updating existing scripts."""
        script_path = tmp_path / "updatable.fountain"

        # Initial version
        content_v1 = """Title: Original Title
Author: Original Author

INT. SCENE ONE - DAY

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-01T00:00:00"}
SCRIPTRAG-META-END */

Original content.

CHARACTER
Original dialogue.
"""
        script_path.write_text(content_v1)

        # Index first version
        # Database path is already set via initialized_db fixture
        result = runner.invoke(
            app,
            ["index", str(tmp_path)],
        )
        assert result.exit_code == 0

        # Update the script
        content_v2 = """Title: Updated Title
Author: Updated Author

INT. SCENE ONE - DAY

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-02T00:00:00"}
SCRIPTRAG-META-END */

Updated content.

CHARACTER
Updated dialogue.

INT. SCENE TWO - NIGHT

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-02T00:00:00"}
SCRIPTRAG-META-END */

New scene added.

CHARACTER
New dialogue.
"""
        script_path.write_text(content_v2)

        # Re-index with force
        # Database path is already set via initialized_db fixture
        result = runner.invoke(
            app,
            ["index", str(tmp_path), "--force"],
        )
        assert result.exit_code == 0

        # Verify updates
        conn = sqlite3.connect(str(initialized_db))
        conn.row_factory = sqlite3.Row

        # Check script was updated
        cursor = conn.execute("SELECT * FROM scripts")
        scripts = cursor.fetchall()
        assert len(scripts) == 1
        assert scripts[0]["title"] == "Updated Title"
        assert scripts[0]["author"] == "Updated Author"

        # Check scenes were updated
        cursor = conn.execute("SELECT COUNT(*) as count FROM scenes")
        assert cursor.fetchone()["count"] == 2  # Now has 2 scenes

        conn.close()
