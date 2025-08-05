"""Integration tests for the pull CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app

runner = CliRunner()


@pytest.fixture
def temp_fountain_files(tmp_path):
    """Create temporary fountain files for testing."""
    # Create a simple fountain file
    simple_file = tmp_path / "simple.fountain"
    simple_file.write_text("""Title: Simple Script
Author: Test Author

INT. ROOM - DAY

A simple scene.

CHARACTER
Some dialogue.
""")

    # Create a file with existing metadata
    with_metadata = tmp_path / "with_metadata.fountain"
    with_metadata.write_text("""Title: Script with Metadata
Author: Test Author

INT. ROOM - DAY

A scene with existing metadata.

/* SCRIPTRAG-META-START
{
    "content_hash": "abc123",
    "analyzed_at": "2024-01-01T00:00:00",
    "analyzers": {
        "emotional_tone": {
            "version": "1.0.0",
            "result": {"primary_emotion": "neutral"}
        }
    }
}
SCRIPTRAG-META-END */
""")

    # Create a subdirectory with another file
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    sub_file = subdir / "nested.fountain"
    sub_file.write_text("""Title: Nested Script

EXT. PARK - DAY

An outdoor scene.
""")

    return tmp_path


class TestPullCommand:
    """Test the pull CLI command."""

    def test_pull_help(self):
        """Test pull command help."""
        result = runner.invoke(app, ["pull", "--help"])
        assert result.exit_code == 0
        assert "Pull and update metadata" in result.stdout
        assert "--force" in result.stdout
        assert "--dry-run" in result.stdout
        assert "--analyzer" in result.stdout

    def test_pull_basic(self, temp_fountain_files):
        """Test basic pull command."""
        result = runner.invoke(app, ["pull", str(temp_fountain_files)])
        
        # Should succeed even if no updates needed
        if result.exit_code != 0:
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            print(f"Exception: {result.exception}")
        assert result.exit_code == 0
        assert "Total:" in result.stdout

    def test_pull_force(self, temp_fountain_files):
        """Test pull with force flag."""
        result = runner.invoke(app, ["pull", str(temp_fountain_files), "--force"])
        
        assert result.exit_code == 0
        assert "Updated:" in result.stdout or "Would update:" in result.stdout

    def test_pull_dry_run(self, temp_fountain_files):
        """Test pull with dry run."""
        result = runner.invoke(app, ["pull", str(temp_fountain_files), "--dry-run", "--force"])
        
        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout
        assert "Would update:" in result.stdout

    def test_pull_no_recursive(self, temp_fountain_files):
        """Test pull without recursive search."""
        result = runner.invoke(app, ["pull", str(temp_fountain_files), "--no-recursive", "--force"])
        
        assert result.exit_code == 0
        # Should not include the nested file
        assert "nested.fountain" not in result.stdout

    def test_pull_with_analyzer(self, temp_fountain_files):
        """Test pull with specific analyzer."""
        result = runner.invoke(
            app, 
            ["pull", str(temp_fountain_files), "--force", "--analyzer", "themes"]
        )
        
        assert result.exit_code == 0

    def test_pull_with_multiple_analyzers(self, temp_fountain_files):
        """Test pull with multiple analyzers."""
        result = runner.invoke(
            app, 
            [
                "pull", 
                str(temp_fountain_files), 
                "--force",
                "--analyzer", "themes",
                "--analyzer", "character_analysis",
            ]
        )
        
        assert result.exit_code == 0

    def test_pull_with_invalid_analyzer(self, temp_fountain_files):
        """Test pull with invalid analyzer."""
        result = runner.invoke(
            app, 
            ["pull", str(temp_fountain_files), "--analyzer", "nonexistent"]
        )
        
        # Should show warning but continue
        assert result.exit_code == 0
        assert "Warning" in result.stdout
        assert "nonexistent" in result.stdout

    def test_pull_no_files(self, tmp_path):
        """Test pull with no fountain files."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        result = runner.invoke(app, ["pull", str(empty_dir)])
        
        assert result.exit_code == 0
        assert "No files needed updating" in result.stdout
        assert "Total: 0 scenes" in result.stdout

    def test_pull_current_directory(self):
        """Test pull with no path argument (current directory)."""
        result = runner.invoke(app, ["pull", "--dry-run"])
        
        # Should at least run without error
        assert result.exit_code == 0

    def test_pull_updates_file(self, temp_fountain_files):
        """Test that pull actually updates files."""
        simple_file = temp_fountain_files / "simple.fountain"
        
        # Run pull with force to ensure processing
        result = runner.invoke(
            app, 
            ["pull", str(simple_file), "--force", "--analyzer", "emotional_tone"]
        )
        
        assert result.exit_code == 0
        
        # Check that metadata was added
        content = simple_file.read_text()
        assert "SCRIPTRAG-META-START" in content
        assert "emotional_tone" in content
        assert "analyzed_at" in content

    @pytest.mark.skipif(not Path(".git").exists(), reason="Not in a git repository")
    def test_pull_with_git_detection(self, temp_fountain_files):
        """Test pull with git change detection."""
        # This test only runs if we're in a git repo
        result = runner.invoke(app, ["pull", str(temp_fountain_files)])
        
        assert result.exit_code == 0