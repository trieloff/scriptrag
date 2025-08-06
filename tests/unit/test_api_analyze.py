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
        analyze_command.load_analyzer("props_inventory")

        assert len(analyze_command.analyzers) == 1
        assert analyze_command.analyzers[0].name == "props_inventory"

    def test_load_analyzer_unknown(self, analyze_command):
        """Test loading an unknown analyzer."""
        with pytest.raises(ValueError, match="Unknown analyzer: unknown"):
            analyze_command.load_analyzer("unknown")

    def test_load_analyzer_duplicate(self, analyze_command):
        """Test loading the same analyzer twice."""
        analyze_command.load_analyzer("props_inventory")
        analyze_command.load_analyzer("props_inventory")

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
    async def test_analyze_with_progress_callback(
        self, analyze_command, temp_fountain_file
    ):
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


class TestAnalyzeCommandBranchCoverage:
    """Test edge cases and branch coverage for AnalyzeCommand."""

    @pytest.mark.asyncio
    async def test_analyze_exception_handling(self, analyze_command, tmp_path):
        """Test analyze handles exceptions during operation."""
        # Mock the lister to raise an exception
        with patch("scriptrag.api.analyze.ScriptLister") as mock_lister:
            mock_lister.return_value.list_scripts.side_effect = RuntimeError(
                "Listing failed"
            )

            result = await analyze_command.analyze(path=tmp_path)

            assert len(result.errors) == 1
            assert "Analyze failed: Listing failed" in result.errors[0]

    @pytest.mark.asyncio
    async def test_analyzer_with_initialize_and_cleanup(self, temp_fountain_file):
        """Test analyzer with initialize and cleanup methods."""

        class AnalyzerWithLifecycle(BaseSceneAnalyzer):
            name = "lifecycle"
            initialized = False
            cleaned_up = False

            async def initialize(self):
                self.initialized = True

            async def analyze(self, _scene: dict) -> dict:
                return {"initialized": self.initialized}

            async def cleanup(self):
                self.cleaned_up = True

        analyzer = AnalyzerWithLifecycle()
        cmd = AnalyzeCommand(analyzers=[analyzer])

        result = await cmd.analyze(
            path=temp_fountain_file.parent,
            force=True,
        )

        assert analyzer.initialized
        assert analyzer.cleaned_up
        assert result.files[0].updated

    @pytest.mark.asyncio
    async def test_analyzer_with_version(self, temp_fountain_file):
        """Test analyzer with version attribute."""

        class AnalyzerWithVersion(BaseSceneAnalyzer):
            name = "versioned"
            version = "1.2.3"

            async def analyze(self, _scene: dict) -> dict:
                return {"test": True}

        analyzer = AnalyzerWithVersion()
        cmd = AnalyzeCommand(analyzers=[analyzer])

        await cmd.analyze(
            path=temp_fountain_file.parent,
            force=True,
        )

        # Check that version was included in metadata
        content = temp_fountain_file.read_text()
        assert "1.2.3" in content

    @pytest.mark.asyncio
    async def test_analyzer_failure_handling(self, temp_fountain_file):
        """Test handling of analyzer failures."""

        class FailingAnalyzer(BaseSceneAnalyzer):
            name = "failing"

            async def analyze(self, _scene: dict) -> dict:
                raise RuntimeError("Analyzer failed")

        analyzer = FailingAnalyzer()
        cmd = AnalyzeCommand(analyzers=[analyzer])

        # Should still complete without errors in result
        result = await cmd.analyze(
            path=temp_fountain_file.parent,
            force=True,
        )

        assert len(result.errors) == 0  # Analyzer errors are logged but not returned
        assert result.files[0].updated  # File should still be processed

    def test_file_needs_update_with_script(self, analyze_command):
        """Test _file_needs_update with Script object."""
        from scriptrag.parser import Scene, Script

        # Create scenes with and without metadata
        scene1 = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="Test",
            content_hash="abc123",
            boneyard_metadata=None,  # No metadata
        )
        scene2 = Scene(
            number=2,
            heading="EXT. TEST - NIGHT",
            content="Test content 2",
            original_text="Test 2",
            content_hash="def456",
            boneyard_metadata={"analyzed_at": "2024-01-01"},  # Has metadata
        )

        script = Script(
            title="Test Script",
            author="Test Author",
            scenes=[scene1, scene2],
        )

        # Should return True because scene1 needs update
        assert analyze_command._file_needs_update(Path("test.fountain"), script) is True

    def test_file_needs_update_all_scenes_updated(self, analyze_command):
        """Test _file_needs_update when all scenes are up to date."""
        from scriptrag.parser import Scene, Script

        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="Test",
            content_hash="abc123",
            boneyard_metadata={"analyzed_at": "2024-01-01", "analyzers": {}},
        )

        script = Script(
            title="Test Script",
            author="Test Author",
            scenes=[scene],
        )

        # Should return False because all scenes are up to date
        assert (
            analyze_command._file_needs_update(Path("test.fountain"), script) is False
        )

    def test_file_needs_update_non_script(self, analyze_command):
        """Test _file_needs_update with non-Script object."""
        # Should return False for non-Script objects
        assert (
            analyze_command._file_needs_update(Path("test.fountain"), "not a script")
            is False
        )

    def test_scene_needs_update_non_scene(self, analyze_command):
        """Test _scene_needs_update with non-Scene object."""
        # Should return False for non-Scene objects
        assert analyze_command._scene_needs_update("not a scene") is False

    def test_scene_needs_update_no_analyzers_in_metadata(self, analyze_command):
        """Test _scene_needs_update when metadata has no analyzers key."""
        from scriptrag.parser import Scene

        analyze_command.analyzers.append(MockAnalyzer())

        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="Test",
            content_hash="abc123",
            boneyard_metadata={"analyzed_at": "2024-01-01"},  # No 'analyzers' key
        )

        # Should return False since there's no analyzers key to check
        assert analyze_command._scene_needs_update(scene) is False

    def test_load_analyzer_import_error(self, analyze_command, monkeypatch):
        """Test load_analyzer when builtin analyzers can't be imported."""
        import builtins

        # Mock ImportError when importing builtin analyzers
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "scriptrag.analyzers" in name:
                raise ImportError("Cannot import analyzers")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        with pytest.raises(ValueError, match="Unknown analyzer: nop"):
            analyze_command.load_analyzer("nop")

    @pytest.mark.asyncio
    async def test_process_file_exception(self, analyze_command, tmp_path):
        """Test _process_file exception handling."""
        bad_file = tmp_path / "bad.fountain"
        bad_file.write_text("Invalid content")

        with patch("scriptrag.api.analyze.FountainParser") as mock_parser:
            mock_parser.return_value.parse_file.side_effect = RuntimeError(
                "Parse failed"
            )

            with pytest.raises(RuntimeError, match="Parse failed"):
                await analyze_command._process_file(
                    bad_file, force=False, dry_run=False
                )


class TestBaseSceneAnalyzer:
    """Test BaseSceneAnalyzer properties."""

    def test_requires_llm_default(self):
        """Test that requires_llm returns False by default."""
        analyzer = MockAnalyzer()
        assert analyzer.requires_llm is False

    def test_version_default(self):
        """Test that version returns default value."""
        analyzer = MockAnalyzer()
        assert analyzer.version == "1.0.0"

    def test_config_initialization(self):
        """Test analyzer config initialization."""
        # Test with no config
        analyzer1 = MockAnalyzer()
        assert analyzer1.config == {}

        # Test with config
        config = {"key": "value"}
        analyzer2 = MockAnalyzer(config=config)
        assert analyzer2.config == config


class TestAnalyzeCommandMissingCoverage:
    """Tests to cover missing lines and branches."""

    @pytest.mark.asyncio
    async def test_process_file_skip_when_up_to_date(self, tmp_path):
        """Test that file is skipped when it doesn't need update (line 211)."""
        from scriptrag.api.analyze import AnalyzeCommand
        from scriptrag.parser import Scene, Script

        cmd = AnalyzeCommand()

        # Register an analyzer
        from scriptrag.analyzers.base import BaseSceneAnalyzer

        class TestAnalyzer(BaseSceneAnalyzer):
            @property
            def name(self):
                return "test"

            @property
            def version(self):
                return "1.0"

            async def analyze(self, scene):  # noqa: ARG002
                return {"test": "data"}

        cmd.register_analyzer("test", TestAnalyzer())

        # Create test file
        test_file = tmp_path / "test_script.fountain"
        test_file.write_text("Script content")

        # Create a script with scenes that have up-to-date metadata
        scene = Scene(
            number=1,
            heading="INT. OFFICE - DAY",
            content="Scene content",
            original_text="Original",
            content_hash="hash1",
            boneyard_metadata={
                "analyzed_at": "2024-01-01T00:00:00",
                "analyzers": {"test": {"version": "1.0"}},
            },
        )

        script = Script(
            title="Test Script",
            author="Test Author",
            scenes=[scene],
        )

        # Mock parser to return the script with up-to-date metadata
        with patch("scriptrag.api.analyze.FountainParser") as mock_parser:
            mock_parser.return_value.parse_file.return_value = script

            # Process without force - should skip (line 211)
            result = await cmd._process_file(test_file, force=False, dry_run=False)

            # File should NOT be updated
            assert not result.updated
            assert result.error is None
