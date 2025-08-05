"""Unit tests for the analyze API."""

from pathlib import Path
from unittest.mock import patch

import pytest

from scriptrag.analyzers.base import BaseSceneAnalyzer
from scriptrag.api.analyze import AnalyzeCommand, AnalyzeResult, FileResult


class MockAnalyzer(BaseSceneAnalyzer):
    """Mock analyzer for testing."""

    name = "mock_analyzer"

    async def analyze(self, scene: dict) -> dict:
        """Return mock analysis."""
        return {"mock_result": True, "scene_heading": scene.get("heading")}


@pytest.fixture
def analyze_command():
    """Create an AnalyzeCommand instance for testing."""
    return AnalyzeCommand()


@pytest.fixture
def temp_fountain_file(tmp_path):
    """Create a temporary fountain file."""
    content = """Title: Test Script
Author: Test Author

FADE IN:

INT. COFFEE SHOP - DAY

A cozy coffee shop. SARAH sits at a table.

SARAH
This is a test.

JOHN
(smiling)
Indeed it is.

EXT. PARK - DAY

John and Sarah walk through the park.

FADE OUT.
"""
    file_path = tmp_path / "test_script.fountain"
    file_path.write_text(content)
    return file_path


class TestAnalyzeCommand:
    """Test AnalyzeCommand class."""

    def test_init(self):
        """Test AnalyzeCommand initialization."""
        cmd = AnalyzeCommand()
        assert cmd.analyzers == []
        assert cmd._analyzer_registry == {}

    def test_from_config(self):
        """Test creating AnalyzeCommand from config."""
        cmd = AnalyzeCommand.from_config()
        assert isinstance(cmd, AnalyzeCommand)

    def test_register_analyzer(self, analyze_command):
        """Test registering an analyzer."""
        analyze_command.register_analyzer("test", MockAnalyzer)
        assert "test" in analyze_command._analyzer_registry
        assert analyze_command._analyzer_registry["test"] == MockAnalyzer

    def test_load_analyzer_registered(self, analyze_command):
        """Test loading a registered analyzer."""
        analyze_command.register_analyzer("test", MockAnalyzer)
        analyze_command.load_analyzer("test")

        assert len(analyze_command.analyzers) == 1
        assert isinstance(analyze_command.analyzers[0], MockAnalyzer)
        assert analyze_command.analyzers[0].name == "mock_analyzer"

    def test_load_analyzer_builtin(self, analyze_command):
        """Test loading a built-in analyzer."""
        analyze_command.load_analyzer("nop")

        assert len(analyze_command.analyzers) == 1
        assert analyze_command.analyzers[0].name == "nop"

    def test_load_analyzer_unknown(self, analyze_command):
        """Test loading an unknown analyzer."""
        with pytest.raises(ValueError, match="Unknown analyzer: unknown"):
            analyze_command.load_analyzer("unknown")

    def test_load_analyzer_duplicate(self, analyze_command):
        """Test loading the same analyzer twice."""
        analyze_command.load_analyzer("nop")
        analyze_command.load_analyzer("nop")

        # Should only be loaded once
        assert len(analyze_command.analyzers) == 1

    @pytest.mark.asyncio
    async def test_analyze_no_files(self, analyze_command, tmp_path):
        """Test analyze with no fountain files."""
        result = await analyze_command.analyze(path=tmp_path)

        assert isinstance(result, AnalyzeResult)
        assert result.files == []
        assert result.errors == []
        assert result.total_files_updated == 0
        assert result.total_scenes_updated == 0

    @pytest.mark.asyncio
    async def test_analyze_with_file(self, analyze_command, temp_fountain_file):
        """Test analyze with a fountain file."""
        # Add a mock analyzer
        analyze_command.analyzers.append(MockAnalyzer())

        result = await analyze_command.analyze(
            path=temp_fountain_file.parent,
            force=True,  # Force processing
        )

        assert isinstance(result, AnalyzeResult)
        assert len(result.files) == 1
        assert result.files[0].path == temp_fountain_file
        assert result.files[0].updated
        assert result.files[0].scenes_updated == 2  # Two scenes in test file

    @pytest.mark.asyncio
    async def test_analyze_dry_run(self, analyze_command, temp_fountain_file):
        """Test analyze in dry run mode."""
        result = await analyze_command.analyze(
            path=temp_fountain_file.parent,
            force=True,
            dry_run=True,
        )

        assert isinstance(result, AnalyzeResult)
        assert len(result.files) == 1
        assert result.files[0].updated

        # File should not have been modified
        content = temp_fountain_file.read_text()
        assert "SCRIPTRAG-META-START" not in content

    @pytest.mark.asyncio
    async def test_analyze_with_progress_callback(self, analyze_command, temp_fountain_file):
        """Test analyze with progress callback."""
        progress_calls = []

        def progress_callback(pct: float, msg: str) -> None:
            progress_calls.append((pct, msg))

        await analyze_command.analyze(
            path=temp_fountain_file.parent,
            force=True,
            progress_callback=progress_callback,
        )

        assert len(progress_calls) > 0
        assert all(0 <= pct <= 1 for pct, _ in progress_calls)

    @pytest.mark.asyncio
    async def test_analyze_with_error(self, analyze_command, tmp_path):
        """Test analyze with file processing error."""
        # Create a file that will cause an error
        bad_file = tmp_path / "bad.fountain"
        bad_file.write_text("This is not a valid fountain file")

        with patch("scriptrag.api.analyze.FountainParser") as mock_parser:
            mock_parser.return_value.parse_file.side_effect = Exception("Parse error")

            result = await analyze_command.analyze(path=tmp_path)

            assert len(result.errors) == 1
            assert "Parse error" in result.errors[0]

    def test_scene_needs_update_no_metadata(self, analyze_command):
        """Test _scene_needs_update with no metadata."""
        from scriptrag.parser import Scene

        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="Test",
            content_hash="abc123",
            boneyard_metadata=None,
        )

        assert analyze_command._scene_needs_update(scene) is True

    def test_scene_needs_update_missing_analyzed_at(self, analyze_command):
        """Test _scene_needs_update with missing analyzed_at."""
        from scriptrag.parser import Scene

        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="Test",
            content_hash="abc123",
            boneyard_metadata={"some": "data"},
        )

        assert analyze_command._scene_needs_update(scene) is True

    def test_scene_needs_update_new_analyzer(self, analyze_command):
        """Test _scene_needs_update with new analyzer."""
        from scriptrag.parser import Scene

        analyze_command.analyzers.append(MockAnalyzer())

        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="Test",
            content_hash="abc123",
            boneyard_metadata={
                "analyzed_at": "2024-01-01",
                "analyzers": {"other_analyzer": {}},
            },
        )

        assert analyze_command._scene_needs_update(scene) is True

    def test_scene_needs_update_up_to_date(self, analyze_command):
        """Test _scene_needs_update with up-to-date scene."""
        from scriptrag.parser import Scene

        analyze_command.analyzers.append(MockAnalyzer())

        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="Test",
            content_hash="abc123",
            boneyard_metadata={
                "analyzed_at": "2024-01-01",
                "analyzers": {"mock_analyzer": {}},
            },
        )

        assert analyze_command._scene_needs_update(scene) is False


class TestAnalyzeResult:
    """Test AnalyzeResult class."""

    def test_empty_result(self):
        """Test empty AnalyzeResult."""
        result = AnalyzeResult()
        assert result.total_files_updated == 0
        assert result.total_scenes_updated == 0

    def test_result_with_files(self):
        """Test AnalyzeResult with files."""
        result = AnalyzeResult(
            files=[
                FileResult(Path("file1.fountain"), updated=True, scenes_updated=3),
                FileResult(Path("file2.fountain"), updated=False),
                FileResult(Path("file3.fountain"), updated=True, scenes_updated=2),
            ]
        )

        assert result.total_files_updated == 2
        assert result.total_scenes_updated == 5
