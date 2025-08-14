"""Integration tests for the analyze CLI command."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app
from tests.utils import strip_ansi_codes

runner = CliRunner()

# Path to fixture files
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "fountain" / "test_data"


@pytest.fixture
def temp_fountain_files(tmp_path):
    """Copy fountain fixture files to temp directory for testing."""
    # Copy simple fountain file
    simple_source = FIXTURES_DIR / "simple_script.fountain"
    simple_file = tmp_path / "simple.fountain"
    shutil.copy2(simple_source, simple_file)

    # Copy file with existing metadata
    with_metadata_source = FIXTURES_DIR / "script_with_metadata.fountain"
    with_metadata = tmp_path / "with_metadata.fountain"
    shutil.copy2(with_metadata_source, with_metadata)

    # Create a subdirectory with another file
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    nested_source = FIXTURES_DIR / "nested_script.fountain"
    sub_file = subdir / "nested.fountain"
    shutil.copy2(nested_source, sub_file)

    return tmp_path


class TestAnalyzeCommand:
    """Test the analyze CLI command."""

    def test_analyze_help(self):
        """Test analyze command help."""
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        # Strip ANSI escape codes for reliable string matching
        clean_output = strip_ansi_codes(result.stdout)
        assert "Analyze Fountain files" in clean_output
        assert "--force" in clean_output
        assert "--dry-run" in clean_output
        assert "--analyzer" in clean_output

    def test_analyze_basic(self, temp_fountain_files):
        """Test basic analyze command."""
        result = runner.invoke(app, ["analyze", str(temp_fountain_files)])

        # Should succeed even if no updates needed
        if result.exit_code != 0:
            pass  # Debug info available in result object
        assert result.exit_code == 0
        assert "Total:" in result.stdout

    def test_analyze_force(self, temp_fountain_files):
        """Test analyze with force flag."""
        result = runner.invoke(app, ["analyze", str(temp_fountain_files), "--force"])

        assert result.exit_code == 0
        assert "Updated:" in result.stdout or "Would update:" in result.stdout

    def test_analyze_dry_run(self, temp_fountain_files):
        """Test analyze with dry run."""
        result = runner.invoke(
            app, ["analyze", str(temp_fountain_files), "--dry-run", "--force"]
        )

        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout
        assert "Would update:" in result.stdout

    def test_analyze_no_recursive(self, temp_fountain_files):
        """Test analyze without recursive search."""
        result = runner.invoke(
            app, ["analyze", str(temp_fountain_files), "--no-recursive", "--force"]
        )

        assert result.exit_code == 0
        # Should not include the nested file
        assert "nested.fountain" not in result.stdout

    def test_analyze_with_analyzer(self, temp_fountain_files):
        """Test analyze with specific analyzer."""
        result = runner.invoke(
            app,
            ["analyze", str(temp_fountain_files), "--force", "--analyzer", "themes"],
        )

        assert result.exit_code == 0

    def test_analyze_with_multiple_analyzers(self, temp_fountain_files):
        """Test analyze with multiple analyzers."""
        result = runner.invoke(
            app,
            [
                "analyze",
                str(temp_fountain_files),
                "--force",
                "--analyzer",
                "themes",
                "--analyzer",
                "character_analysis",
            ],
        )

        assert result.exit_code == 0

    def test_analyze_with_invalid_analyzer(self, temp_fountain_files):
        """Test analyze with invalid analyzer."""
        result = runner.invoke(
            app, ["analyze", str(temp_fountain_files), "--analyzer", "nonexistent"]
        )

        # Should show warning but continue
        assert result.exit_code == 0
        assert "Warning" in result.stdout
        assert "nonexistent" in result.stdout

    def test_analyze_no_files(self, tmp_path):
        """Test analyze with no fountain files."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = runner.invoke(app, ["analyze", str(empty_dir)])

        assert result.exit_code == 0
        # Strip ANSI escape codes for reliable string matching
        clean_output = strip_ansi_codes(result.stdout)
        assert "No files needed updating" in clean_output
        assert "Total: 0 scenes" in clean_output

    def test_analyze_current_directory(self, temp_fountain_files, monkeypatch):
        """Test analyze with no path argument (current directory)."""
        # IMPORTANT: Change to temp directory to avoid modifying repository files
        monkeypatch.chdir(temp_fountain_files)

        result = runner.invoke(app, ["analyze", "--dry-run"])

        # Should at least run without error
        assert result.exit_code == 0

    def test_analyze_updates_file(self, temp_fountain_files):
        """Test that analyze actually updates files."""
        runner = CliRunner()
        simple_file = temp_fountain_files / "simple.fountain"

        # Run analyze with force to ensure processing
        result = runner.invoke(
            app,
            ["analyze", str(simple_file), "--force"],
        )

        assert result.exit_code == 0

        # Check that metadata was added
        content = simple_file.read_text()
        assert "SCRIPTRAG-META-START" in content
        assert "analyzed_at" in content

    def test_analyze_with_errors_display(self, temp_fountain_files, monkeypatch):
        """Test that analyze displays errors correctly."""
        from unittest.mock import AsyncMock, MagicMock

        from scriptrag.api.analyze import AnalyzeResult, FileResult

        # Create a mock result with errors
        mock_result = AnalyzeResult(
            files=[
                FileResult(
                    path=temp_fountain_files / "file1.fountain",
                    updated=False,
                    error="Error 1",
                ),
                FileResult(
                    path=temp_fountain_files / "file2.fountain",
                    updated=False,
                    error="Error 2",
                ),
                FileResult(
                    path=temp_fountain_files / "file3.fountain",
                    updated=False,
                    error="Error 3",
                ),
                FileResult(
                    path=temp_fountain_files / "file4.fountain",
                    updated=False,
                    error="Error 4",
                ),
                FileResult(
                    path=temp_fountain_files / "file5.fountain",
                    updated=False,
                    error="Error 5",
                ),
                FileResult(
                    path=temp_fountain_files / "file6.fountain",
                    updated=False,
                    error="Error 6",
                ),
            ],
            errors=[
                "file1.fountain: Error 1",
                "file2.fountain: Error 2",
                "file3.fountain: Error 3",
                "file4.fountain: Error 4",
                "file5.fountain: Error 5",
                "file6.fountain: Error 6",
            ],
        )

        # Mock the analyze method
        mock_analyze_cmd = MagicMock()
        mock_analyze_cmd.analyze = AsyncMock(return_value=mock_result)
        mock_analyze_cmd.load_analyzer = MagicMock()

        # Patch the AnalyzeCommand.from_config
        def mock_from_config():
            return mock_analyze_cmd

        import scriptrag.api.analyze

        monkeypatch.setattr(
            scriptrag.api.analyze.AnalyzeCommand,
            "from_config",
            mock_from_config,
        )

        result = runner.invoke(app, ["analyze", str(temp_fountain_files)])

        assert result.exit_code == 0
        # Strip ANSI codes for reliable string matching
        clean_output = strip_ansi_codes(result.stdout)
        # Should show first 5 errors plus a count of remaining
        assert "Errors: 6" in clean_output
        assert "Error 1" in clean_output
        assert "Error 5" in clean_output
        assert "and 1 more" in clean_output

    def test_analyze_import_error(self, monkeypatch, tmp_path):
        """Test analyze handles import errors."""
        import builtins

        # Mock ImportError when importing AnalyzeCommand
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "scriptrag.api.analyze":
                raise ImportError("Test import error")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        result = runner.invoke(app, ["analyze", str(tmp_path)])

        assert result.exit_code == 1
        assert "Required components not available" in result.stdout

    def test_analyze_general_exception(self, temp_fountain_files, monkeypatch):
        """Test analyze handles general exceptions."""

        # Mock an exception in analyze method
        async def mock_analyze(*_args, **_kwargs):
            raise RuntimeError("Test runtime error")

        mock_analyze_cmd = MagicMock()
        mock_analyze_cmd.analyze = mock_analyze
        mock_analyze_cmd.load_analyzer = MagicMock()

        def mock_from_config():
            return mock_analyze_cmd

        import scriptrag.api.analyze

        monkeypatch.setattr(
            scriptrag.api.analyze.AnalyzeCommand,
            "from_config",
            mock_from_config,
        )

        result = runner.invoke(app, ["analyze", str(temp_fountain_files)])

        assert result.exit_code == 1
        assert "Error: Test runtime error" in result.stdout

    def test_analyze_general_exception_with_logging(
        self, temp_fountain_files, monkeypatch
    ):
        """Test analyze handles general exceptions and logs them properly."""
        # This ensures we hit line 142 specifically (the raise statement)
        from unittest.mock import MagicMock

        # Mock an exception that will be caught by the general exception handler
        async def mock_analyze_with_exception(*_args, **_kwargs):
            # Use asyncio.run to ensure we're in the right context for the CLI
            raise ValueError("Specific test exception for coverage")

        mock_analyze_cmd = MagicMock()
        mock_analyze_cmd.analyze = mock_analyze_with_exception
        mock_analyze_cmd.load_analyzer = MagicMock()

        def mock_from_config():
            return mock_analyze_cmd

        import scriptrag.api.analyze

        monkeypatch.setattr(
            scriptrag.api.analyze.AnalyzeCommand,
            "from_config",
            mock_from_config,
        )

        # Run the analyze command which should trigger the exception
        result = runner.invoke(app, ["analyze", str(temp_fountain_files)])

        # Verify the general exception handler was triggered
        assert result.exit_code == 1
        assert "Error: Specific test exception for coverage" in result.stdout

    def test_analyze_relative_path_display(self, temp_fountain_files, monkeypatch):
        """Test analyze displays relative paths when possible."""
        from unittest.mock import AsyncMock, MagicMock

        from scriptrag.api.analyze import AnalyzeResult, FileResult

        # Use monkeypatch.chdir for safer directory change
        monkeypatch.chdir(temp_fountain_files)

        # Create a mock result with a file in current dir
        mock_result = AnalyzeResult(
            files=[
                FileResult(
                    path=temp_fountain_files / "simple.fountain",
                    updated=True,
                    scenes_updated=2,
                ),
            ],
        )

        # Mock the analyze method
        mock_analyze_cmd = MagicMock()
        mock_analyze_cmd.analyze = AsyncMock(return_value=mock_result)
        mock_analyze_cmd.load_analyzer = MagicMock()

        def mock_from_config():
            return mock_analyze_cmd

        monkeypatch.setattr(
            "scriptrag.api.analyze.AnalyzeCommand.from_config",
            mock_from_config,
        )

        result = runner.invoke(app, ["analyze", "."])

        assert result.exit_code == 0
        # Should display relative path
        clean_output = strip_ansi_codes(result.stdout)
        assert "simple.fountain" in clean_output
        assert "2 scenes" in clean_output

    def test_analyze_absolute_path_fallback(self, temp_fountain_files, monkeypatch):
        """Test analyze falls back to absolute path when relative not possible."""
        from unittest.mock import AsyncMock, MagicMock

        from scriptrag.api.analyze import AnalyzeResult, FileResult

        # Create a mock result with a file in a different directory
        mock_result = AnalyzeResult(
            files=[
                FileResult(
                    path=Path("/absolute/path/to/file.fountain"),
                    updated=True,
                    scenes_updated=3,
                ),
            ],
        )

        # Mock the analyze method
        mock_analyze_cmd = MagicMock()
        mock_analyze_cmd.analyze = AsyncMock(return_value=mock_result)
        mock_analyze_cmd.load_analyzer = MagicMock()

        def mock_from_config():
            return mock_analyze_cmd

        import scriptrag.api.analyze

        monkeypatch.setattr(
            scriptrag.api.analyze.AnalyzeCommand,
            "from_config",
            mock_from_config,
        )

        result = runner.invoke(app, ["analyze", str(temp_fountain_files)])

        assert result.exit_code == 0
        # Strip ANSI codes for reliable string matching
        clean_output = strip_ansi_codes(result.stdout)
        # Should display absolute path (check for both Unix and Windows path separators)
        assert "file.fountain" in clean_output
        assert (
            "absolute/path/to" in clean_output or "absolute\\path\\to" in clean_output
        )
        assert "3 scenes" in clean_output
