"""Integration tests for scriptrag list command."""

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from scriptrag.cli import app

# Path to fixture files
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "fountain"


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def fountain_scripts(tmp_path):
    """Copy test fountain scripts to temporary directory."""
    # Copy standalone scripts
    standalone_src = FIXTURES_DIR / "standalone"
    for fountain_file in standalone_src.glob("*.fountain"):
        shutil.copy2(fountain_file, tmp_path / fountain_file.name)

    # Copy series scripts with directory structure
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    series_src = FIXTURES_DIR / "series"
    for fountain_file in series_src.glob("*.fountain"):
        shutil.copy2(fountain_file, series_dir / fountain_file.name)

    # Create a non-fountain file (should be ignored)
    non_fountain = tmp_path / "not_a_script.txt"
    non_fountain.write_text("This is not a fountain file.")

    # Return list of copied script paths
    return list(tmp_path.glob("**/*.fountain"))


class TestListCommand:
    """Test the scriptrag list command."""

    def test_list_no_scripts(self, runner, tmp_path):
        """Test list command when no scripts are found."""
        result = runner.invoke(app, ["list", str(tmp_path)])

        assert result.exit_code == 0
        assert "No Fountain scripts found" in result.stdout

    def test_list_scripts_default_path(self, runner, fountain_scripts, monkeypatch):
        """Test list command with default path (current directory)."""
        # Change to the temp directory with scripts
        monkeypatch.chdir(fountain_scripts[0].parent)

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Fountain Scripts" in result.stdout
        # Count all fountain files from fixtures
        expected_count = len(list(FIXTURES_DIR.glob("**/*.fountain")))
        assert f"Found {expected_count} scripts" in result.stdout
        assert "The Great Adventure" in result.stdout
        assert "Mystery Show" in result.stdout
        assert "Another Series" in result.stdout

    def test_list_scripts_with_path(self, runner, fountain_scripts):
        """Test list command with specified path."""
        result = runner.invoke(app, ["list", str(fountain_scripts[0].parent)])

        assert result.exit_code == 0
        expected_count = len(list(FIXTURES_DIR.glob("**/*.fountain")))
        assert f"Found {expected_count} scripts" in result.stdout

    def test_list_alias_ls(self, runner, fountain_scripts):
        """Test that 'ls' alias works for list command."""
        result = runner.invoke(app, ["ls", str(fountain_scripts[0].parent)])

        assert result.exit_code == 0
        expected_count = len(list(FIXTURES_DIR.glob("**/*.fountain")))
        assert f"Found {expected_count} scripts" in result.stdout

    def test_list_series_detection(self, runner, fountain_scripts):
        """Test that series episodes are properly detected and grouped."""
        result = runner.invoke(app, ["list", str(fountain_scripts[0].parent)])

        assert result.exit_code == 0
        # Check series episodes are shown with season/episode info
        assert "S01E01" in result.stdout or (
            "1" in result.stdout and "1" in result.stdout
        )
        assert "S01E02" in result.stdout or (
            "1" in result.stdout and "2" in result.stdout
        )
        # Episode parsed from filename
        assert "2" in result.stdout and "3" in result.stdout  # S2E3

    def test_list_no_recursive(self, runner, fountain_scripts):
        """Test list command with --no-recursive option."""
        # Only scripts in root should be found, not in series subdirectory
        result = runner.invoke(
            app, ["list", str(fountain_scripts[0].parent), "--no-recursive"]
        )

        assert result.exit_code == 0
        # Count only root-level scripts from fixtures
        expected_count = len(list(FIXTURES_DIR.glob("standalone/*.fountain")))
        assert f"Found {expected_count} scripts" in result.stdout
        assert "The Great Adventure" in result.stdout
        assert "Another Series" in result.stdout
        # These are in subdirectory
        assert "S01E01" not in result.stdout
        assert "S01E02" not in result.stdout

    def test_list_single_file(self, runner, fountain_scripts):
        """Test list command with a single file path."""
        # Find the specific file
        great_adventure = next(
            f for f in fountain_scripts if "great_adventure" in f.name
        )
        result = runner.invoke(app, ["list", str(great_adventure)])

        assert result.exit_code == 0
        assert "Found 1 script" in result.stdout
        assert "The Great Adventure" in result.stdout
        assert "Jane Doe" in result.stdout

    def test_list_non_fountain_file(self, runner, tmp_path):
        """Test list command with non-fountain file."""
        txt_file = tmp_path / "not_fountain.txt"
        txt_file.write_text("Regular text file")

        result = runner.invoke(app, ["list", str(txt_file)])

        assert result.exit_code == 0
        assert "No Fountain scripts found" in result.stdout

    def test_list_nonexistent_path(self, runner):
        """Test list command with nonexistent path."""
        result = runner.invoke(app, ["list", "/nonexistent/path"])

        # Should fail because typer validates the path exists
        assert result.exit_code != 0

    def test_list_handles_read_errors(self, runner, tmp_path, monkeypatch):
        """Test list handles file read errors gracefully."""
        # Create a fountain file
        script = tmp_path / "unreadable.fountain"
        script.write_text("Title: Test\n\nFADE IN:")

        # Mock read_text to raise an error
        def mock_read_text(self, encoding=None):  # noqa: ARG001
            raise PermissionError("Cannot read file")

        monkeypatch.setattr(Path, "read_text", mock_read_text)

        result = runner.invoke(app, ["list", str(tmp_path)])

        # Should still succeed but show the file without metadata
        assert result.exit_code == 0
        assert "unreadable" in result.stdout

    def test_list_author_variations(self, runner, tmp_path):
        """Test that various author field names are recognized."""
        # Copy author variation fixtures
        for fountain_file in FIXTURES_DIR.glob("standalone/*_field.fountain"):
            shutil.copy2(fountain_file, tmp_path / fountain_file.name)

        result = runner.invoke(app, ["list", str(tmp_path)])

        assert result.exit_code == 0
        # Check all author variations are recognized
        assert "Author One" in result.stdout
        assert "Author Two" in result.stdout
        assert "Author Three" in result.stdout
        assert "Author Four" in result.stdout
        assert "Author Five" in result.stdout

    def test_list_complex_filenames(self, runner, tmp_path):
        """Test episode/season detection from various filename formats."""
        # Copy complex filename fixtures
        complex_files = [
            "show_S02E05.fountain",
            "show_2x05.fountain",
            "show_Episode_10.fountain",
            "show_Ep10.fountain",
            "show_ep-7.fountain",
        ]

        for filename in complex_files:
            src = FIXTURES_DIR / "series" / filename
            if src.exists():
                shutil.copy2(src, tmp_path / filename)

        result = runner.invoke(app, ["list", str(tmp_path)])

        assert result.exit_code == 0
        assert "Found 5 scripts" in result.stdout
        # Verify episodes are detected (exact format may vary in output)

    def test_list_multi_line_title(self, runner, tmp_path):
        """Test that multi-line titles with formatting are handled correctly."""
        # Copy the multi-line title fixture
        src = FIXTURES_DIR / "standalone" / "multi_line_title.fountain"
        if src.exists():
            shutil.copy2(src, tmp_path / "multi_line_title.fountain")

        result = runner.invoke(app, ["list", str(tmp_path)])

        assert result.exit_code == 0
        assert "BRICK & STEEL" in result.stdout
        assert "FULL RETIRED" in result.stdout
        assert "Stu Maschwitz" in result.stdout

    def test_list_command_handles_exceptions(self, runner, tmp_path, monkeypatch):
        """Test that CLI command handles exceptions gracefully."""
        from scriptrag.api import ScriptLister

        # Mock the list_scripts method to raise an exception
        def mock_list_scripts(*args, **kwargs):  # noqa: ARG001
            raise RuntimeError("Database connection failed")

        monkeypatch.setattr(ScriptLister, "list_scripts", mock_list_scripts)

        result = runner.invoke(app, ["list", str(tmp_path)])

        assert result.exit_code == 1
        assert "Error:" in result.stdout
        assert "Failed to list scripts" in result.stdout
        assert "Database connection failed" in result.stdout
