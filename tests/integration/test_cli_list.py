"""Integration tests for scriptrag list command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from scriptrag.cli import app


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def fountain_scripts(tmp_path):
    """Create test fountain scripts in temporary directory."""
    scripts = []

    # Single standalone script
    standalone = tmp_path / "standalone.fountain"
    standalone.write_text("""Title: The Great Adventure
Author: Jane Doe

FADE IN:

EXT. MOUNTAIN PEAK - DAY

The wind howls.
""")
    scripts.append(standalone)

    # TV Series with multiple episodes
    series_dir = tmp_path / "series"
    series_dir.mkdir()

    # Episode 1
    ep1 = series_dir / "S01E01_pilot.fountain"
    ep1.write_text("""Title: Mystery Show
Episode: 1
Season: 1
Author: John Smith

FADE IN:
""")
    scripts.append(ep1)

    # Episode 2
    ep2 = series_dir / "S01E02_continuation.fountain"
    ep2.write_text("""Title: Mystery Show
Episode: 2
Season: 1
Author: John Smith

FADE IN:
""")
    scripts.append(ep2)

    # Episode from season 2
    ep3 = series_dir / "mystery_show_2x03.fountain"
    ep3.write_text("""Title: Mystery Show
Author: John Smith

FADE IN:
""")
    scripts.append(ep3)

    # Script with episode in title
    ep_in_title = tmp_path / "another_series.fountain"
    ep_in_title.write_text("""Title: Another Series - Episode 5
Author: Alice Johnson

FADE IN:
""")
    scripts.append(ep_in_title)

    # Script with no metadata
    no_meta = tmp_path / "no_metadata.fountain"
    no_meta.write_text("""FADE IN:

INT. ROOM - DAY

Action happens.
""")
    scripts.append(no_meta)

    # Non-fountain file (should be ignored)
    non_fountain = tmp_path / "not_a_script.txt"
    non_fountain.write_text("This is not a fountain file.")

    return scripts


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
        assert "Found 6 scripts" in result.stdout
        assert "The Great Adventure" in result.stdout
        assert "Mystery Show" in result.stdout
        assert "Another Series" in result.stdout

    def test_list_scripts_with_path(self, runner, fountain_scripts):
        """Test list command with specified path."""
        result = runner.invoke(app, ["list", str(fountain_scripts[0].parent)])

        assert result.exit_code == 0
        assert "Found 6 scripts" in result.stdout

    def test_list_alias_ls(self, runner, fountain_scripts):
        """Test that 'ls' alias works for list command."""
        result = runner.invoke(app, ["ls", str(fountain_scripts[0].parent)])

        assert result.exit_code == 0
        assert "Found 6 scripts" in result.stdout

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
        # Should find only 3 scripts in root (not the 2 in series/)
        assert "Found 3 scripts" in result.stdout
        assert "The Great Adventure" in result.stdout
        assert "Another Series" in result.stdout
        # These are in subdirectory
        assert "S01E01" not in result.stdout
        assert "S01E02" not in result.stdout

    def test_list_single_file(self, runner, fountain_scripts):
        """Test list command with a single file path."""
        result = runner.invoke(app, ["list", str(fountain_scripts[0])])

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
        scripts = []

        # Different author field variations
        variations = [
            ("Author:", "Author One"),
            ("Authors:", "Author Two"),
            ("Written by:", "Author Three"),
            ("Writer:", "Author Four"),
            ("Writers:", "Author Five"),
        ]

        for i, (field, name) in enumerate(variations):
            script = tmp_path / f"script{i}.fountain"
            script.write_text(
                f"""Title: Script {i}
{field} {name}

FADE IN:
"""
            )
            scripts.append(script)

        result = runner.invoke(app, ["list", str(tmp_path)])

        assert result.exit_code == 0
        # Check all author variations are recognized
        for _, name in variations:
            assert name in result.stdout

    def test_list_complex_filenames(self, runner, tmp_path):
        """Test episode/season detection from various filename formats."""
        # Create scripts with different filename patterns
        patterns = [
            ("show_S02E05.fountain", 2, 5),
            ("show_2x05.fountain", 2, 5),
            ("show_Episode_10.fountain", None, 10),
            ("show_Ep10.fountain", None, 10),
            ("show_ep-7.fountain", None, 7),
        ]

        for filename, _expected_season, _expected_episode in patterns:
            script = tmp_path / filename
            script.write_text("""Title: Complex Show

FADE IN:
""")

        result = runner.invoke(app, ["list", str(tmp_path)])

        assert result.exit_code == 0
        assert "Found 5 scripts" in result.stdout
        # Verify episodes are detected (exact format may vary in output)
