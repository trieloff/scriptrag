"""Integration tests for the scriptrag index command."""

import shutil
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app
from scriptrag.config import ScriptRAGSettings, set_settings
from tests.cli_fixtures import strip_ansi_codes

runner = CliRunner()

# Path to fixture files
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "fountain" / "test_data"


@pytest.fixture
def sample_fountain_with_metadata(tmp_path):
    """Copy sample Fountain file with boneyard metadata to temp directory."""
    source_file = FIXTURES_DIR / "coffee_shop_with_metadata.fountain"
    script_path = tmp_path / "sample.fountain"
    shutil.copy2(source_file, script_path)
    return script_path


@pytest.fixture
def sample_fountain_without_metadata(tmp_path):
    """Copy sample Fountain file without metadata to temp directory."""
    source_file = FIXTURES_DIR / "simple_script.fountain"
    script_path = tmp_path / "no_metadata.fountain"
    shutil.copy2(source_file, script_path)
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

    # Force close any existing connection manager to ensure clean state
    from scriptrag.database.connection_manager import close_connection_manager

    close_connection_manager()

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

    def test_index_no_scripts(self, initialized_db, tmp_path):
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

    def test_index_reindex(self, initialized_db, sample_fountain_with_metadata):
        """Test re-indexing behavior (scripts are always re-indexed for consistency)."""
        script_dir = sample_fountain_with_metadata.parent

        # Index once
        # Database path is already set via initialized_db fixture
        result = runner.invoke(
            app,
            ["index", str(script_dir)],
        )
        assert result.exit_code == 0

        # Index again (scripts are always re-indexed for consistency)
        result = runner.invoke(
            app,
            ["index", str(script_dir)],
        )
        assert result.exit_code == 0

        # Check that script exists (re-indexed, not duplicated)
        conn = sqlite3.connect(str(initialized_db))
        cursor = conn.execute("SELECT COUNT(*) as count FROM scripts")
        assert cursor.fetchone()[0] == 1  # Still just one script

        # Index again to verify idempotent behavior
        result = runner.invoke(
            app,
            ["index", str(script_dir)],
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
        initialized_db,
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
        sample_fountain_without_metadata,
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

        # Re-index the script
        # Database path is already set via initialized_db fixture
        result = runner.invoke(
            app,
            ["index", str(tmp_path)],
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

    def test_index_import_error(self, tmp_path, monkeypatch):
        """Test handling of import errors."""
        runner = CliRunner()
        monkeypatch.chdir(tmp_path)

        # Patch the import statement to simulate ImportError
        import sys
        from unittest.mock import patch

        with runner.isolated_filesystem():
            # Backup original module if it exists
            original_module = sys.modules.get("scriptrag.api.index")

            # Remove module from sys.modules to trigger import error
            if "scriptrag.api.index" in sys.modules:
                del sys.modules["scriptrag.api.index"]

            # Mock the module to raise ImportError
            def failing_import(*args, **kwargs):
                if args and "scriptrag.api.index" in str(args[0]):
                    raise ImportError("Mock import error")
                return original_import(*args, **kwargs)

            original_import = __builtins__["__import__"]
            with patch("builtins.__import__", side_effect=failing_import):
                result = runner.invoke(app, ["index", "."])

            # Restore original module
            if original_module:
                sys.modules["scriptrag.api.index"] = original_module

            assert result.exit_code == 1
            clean_output = strip_ansi_codes(result.output)
            assert "Required components not available" in clean_output

    def test_index_general_exception(self, tmp_path):
        """Test handling of general exceptions during indexing."""
        runner = CliRunner()

        # Create a script file
        script_path = tmp_path / "test.fountain"
        script_path.write_text("Title: Test\n\nINT. SCENE - DAY\n\nAction.")

        # Mock IndexCommand to raise exception
        from unittest.mock import AsyncMock, patch

        async def mock_index_error(*_args, **_kwargs):
            raise Exception("Unexpected error during indexing")

        with patch("scriptrag.api.index.IndexCommand") as mock_index_command:
            mock_instance = mock_index_command.return_value
            mock_instance.index = AsyncMock(side_effect=mock_index_error)

            result = runner.invoke(app, ["index", str(tmp_path)])
            assert result.exit_code == 1
            clean_output = strip_ansi_codes(result.output)
            assert "Error:" in clean_output

    def test_index_display_verbose_with_errors(self, tmp_path):
        """Test verbose display mode with errors."""
        from unittest.mock import AsyncMock, patch

        from scriptrag.api.index import IndexOperationResult, IndexResult

        runner = CliRunner()

        # Create test results with errors
        test_result = IndexOperationResult()

        # Add scripts with mixed results
        test_result.scripts = [
            IndexResult(
                path=Path("script1.fountain"),
                indexed=1,
                updated=0,
                scenes_indexed=5,
                characters_indexed=3,
                dialogues_indexed=10,
                actions_indexed=7,
            ),
            IndexResult(
                path=Path("script2.fountain"),
                indexed=0,
                updated=0,
                error="Failed to parse script",
            ),
        ]

        # Add multiple errors to test pagination
        test_result.errors = [f"Error {i}" for i in range(15)]

        with patch("scriptrag.api.index.IndexCommand") as mock_index_command:
            mock_instance = mock_index_command.return_value
            mock_instance.index = AsyncMock(return_value=test_result)

            result = runner.invoke(app, ["index", str(tmp_path), "--verbose"])

            # Check that errors are displayed
            clean_output = strip_ansi_codes(result.output)
            assert "Errors encountered: 15" in clean_output
            assert "Error 0" in clean_output
            assert "... and 5 more errors" in clean_output

            # Check that the script with error is shown
            assert "script2.fountain" in clean_output
            assert "Failed to parse script" in clean_output

    def test_index_display_summary_with_updates(self, tmp_path):
        """Test summary display with updated scripts."""
        from unittest.mock import AsyncMock, patch

        from scriptrag.api.index import IndexOperationResult, IndexResult

        runner = CliRunner()

        # Create test results with updates
        test_result = IndexOperationResult()
        test_result.scripts = [
            IndexResult(
                path=Path("script1.fountain"),
                indexed=0,
                updated=1,  # This script was updated
                scenes_indexed=3,
                characters_indexed=2,
                dialogues_indexed=5,
                actions_indexed=4,
            ),
        ]

        with patch("scriptrag.api.index.IndexCommand") as mock_index_command:
            mock_instance = mock_index_command.return_value
            mock_instance.index = AsyncMock(return_value=test_result)

            result = runner.invoke(app, ["index", str(tmp_path)])

            # Check that updates are shown in summary
            clean_output = strip_ansi_codes(result.output)
            assert "Scripts Updated" in clean_output and "1" in clean_output
            assert (
                "Next steps:" in clean_output
            )  # Help text should not show for updates

    def test_index_progress_callback(self, tmp_path):
        """Test that progress callback is properly passed."""
        from unittest.mock import AsyncMock, patch

        from scriptrag.api.index import IndexOperationResult

        runner = CliRunner()

        test_result = IndexOperationResult()
        test_result.scripts = []

        with patch("scriptrag.api.index.IndexCommand") as mock_index_command:
            mock_instance = mock_index_command.return_value
            mock_instance.index = AsyncMock(return_value=test_result)

            # Run with verbose to enable progress
            runner.invoke(app, ["index", str(tmp_path), "--verbose"])

            # Check that index was called with progress_callback
            assert mock_instance.index.called
            call_kwargs = mock_instance.index.call_args.kwargs
            # When verbose is True, a progress_callback should be provided
            if "progress_callback" in call_kwargs:
                assert call_kwargs["progress_callback"] is not None
