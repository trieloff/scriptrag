"""Unit tests for the pull API."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.api.pull import FileResult, PullCommand, PullResult
from scriptrag.analyzers.base import BaseSceneAnalyzer


class MockAnalyzer(BaseSceneAnalyzer):
    """Mock analyzer for testing."""

    name = "mock_analyzer"

    async def analyze(self, scene: dict) -> dict:
        """Return mock analysis."""
        return {"mock_result": True, "scene_heading": scene.get("heading")}


@pytest.fixture
def pull_command():
    """Create a PullCommand instance for testing."""
    return PullCommand()


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


class TestPullCommand:
    """Test PullCommand class."""

    def test_init(self):
        """Test PullCommand initialization."""
        cmd = PullCommand()
        assert cmd.analyzers == []
        assert cmd._analyzer_registry == {}

    def test_from_config(self):
        """Test creating PullCommand from config."""
        cmd = PullCommand.from_config()
        assert isinstance(cmd, PullCommand)

    def test_register_analyzer(self, pull_command):
        """Test registering an analyzer."""
        pull_command.register_analyzer("test", MockAnalyzer)
        assert "test" in pull_command._analyzer_registry
        assert pull_command._analyzer_registry["test"] == MockAnalyzer

    def test_load_analyzer_registered(self, pull_command):
        """Test loading a registered analyzer."""
        pull_command.register_analyzer("test", MockAnalyzer)
        pull_command.load_analyzer("test")
        
        assert len(pull_command.analyzers) == 1
        assert isinstance(pull_command.analyzers[0], MockAnalyzer)
        assert pull_command.analyzers[0].name == "mock_analyzer"

    def test_load_analyzer_builtin(self, pull_command):
        """Test loading a built-in analyzer."""
        pull_command.load_analyzer("emotional_tone")
        
        assert len(pull_command.analyzers) == 1
        assert pull_command.analyzers[0].name == "emotional_tone"

    def test_load_analyzer_unknown(self, pull_command):
        """Test loading an unknown analyzer."""
        with pytest.raises(ValueError, match="Unknown analyzer: unknown"):
            pull_command.load_analyzer("unknown")

    def test_load_analyzer_duplicate(self, pull_command):
        """Test loading the same analyzer twice."""
        pull_command.load_analyzer("emotional_tone")
        pull_command.load_analyzer("emotional_tone")
        
        # Should only be loaded once
        assert len(pull_command.analyzers) == 1

    @pytest.mark.asyncio
    async def test_pull_no_files(self, pull_command, tmp_path):
        """Test pull with no fountain files."""
        result = await pull_command.pull(path=tmp_path)
        
        assert isinstance(result, PullResult)
        assert result.files == []
        assert result.errors == []
        assert result.total_files_updated == 0
        assert result.total_scenes_updated == 0

    @pytest.mark.asyncio
    async def test_pull_with_file(self, pull_command, temp_fountain_file):
        """Test pull with a fountain file."""
        # Add a mock analyzer
        pull_command.analyzers.append(MockAnalyzer())
        
        result = await pull_command.pull(
            path=temp_fountain_file.parent,
            force=True,  # Force processing
        )
        
        assert isinstance(result, PullResult)
        assert len(result.files) == 1
        assert result.files[0].path == temp_fountain_file
        assert result.files[0].updated
        assert result.files[0].scenes_updated == 2  # Two scenes in test file

    @pytest.mark.asyncio
    async def test_pull_dry_run(self, pull_command, temp_fountain_file):
        """Test pull in dry run mode."""
        result = await pull_command.pull(
            path=temp_fountain_file.parent,
            force=True,
            dry_run=True,
        )
        
        assert isinstance(result, PullResult)
        assert len(result.files) == 1
        assert result.files[0].updated
        
        # File should not have been modified
        content = temp_fountain_file.read_text()
        assert "SCRIPTRAG-META-START" not in content

    @pytest.mark.asyncio
    async def test_pull_with_progress_callback(self, pull_command, temp_fountain_file):
        """Test pull with progress callback."""
        progress_calls = []
        
        def progress_callback(pct: float, msg: str) -> None:
            progress_calls.append((pct, msg))
        
        await pull_command.pull(
            path=temp_fountain_file.parent,
            force=True,
            progress_callback=progress_callback,
        )
        
        assert len(progress_calls) > 0
        assert all(0 <= pct <= 1 for pct, _ in progress_calls)

    @pytest.mark.asyncio
    async def test_pull_with_error(self, pull_command, tmp_path):
        """Test pull with file processing error."""
        # Create a file that will cause an error
        bad_file = tmp_path / "bad.fountain"
        bad_file.write_text("This is not a valid fountain file")
        
        with patch("scriptrag.api.pull.FountainParser") as mock_parser:
            mock_parser.return_value.parse_file.side_effect = Exception("Parse error")
            
            result = await pull_command.pull(path=tmp_path)
            
            assert len(result.errors) == 1
            assert "Parse error" in result.errors[0]

    def test_scene_needs_update_no_metadata(self, pull_command):
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
        
        assert pull_command._scene_needs_update(scene) is True

    def test_scene_needs_update_missing_analyzed_at(self, pull_command):
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
        
        assert pull_command._scene_needs_update(scene) is True

    def test_scene_needs_update_new_analyzer(self, pull_command):
        """Test _scene_needs_update with new analyzer."""
        from scriptrag.parser import Scene
        
        pull_command.analyzers.append(MockAnalyzer())
        
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
        
        assert pull_command._scene_needs_update(scene) is True

    def test_scene_needs_update_up_to_date(self, pull_command):
        """Test _scene_needs_update with up-to-date scene."""
        from scriptrag.parser import Scene
        
        pull_command.analyzers.append(MockAnalyzer())
        
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
        
        assert pull_command._scene_needs_update(scene) is False


class TestPullResult:
    """Test PullResult class."""

    def test_empty_result(self):
        """Test empty PullResult."""
        result = PullResult()
        assert result.total_files_updated == 0
        assert result.total_scenes_updated == 0

    def test_result_with_files(self):
        """Test PullResult with files."""
        result = PullResult(
            files=[
                FileResult(Path("file1.fountain"), updated=True, scenes_updated=3),
                FileResult(Path("file2.fountain"), updated=False),
                FileResult(Path("file3.fountain"), updated=True, scenes_updated=2),
            ]
        )
        
        assert result.total_files_updated == 2
        assert result.total_scenes_updated == 5