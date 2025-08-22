"""Unit tests for the analyze API."""

from pathlib import Path
from unittest.mock import patch

import pytest

from scriptrag.analyzers.base import BaseSceneAnalyzer
from scriptrag.api.analyze import AnalyzeCommand
from scriptrag.api.analyze_helpers import file_needs_update, scene_needs_update
from scriptrag.api.analyze_results import AnalyzeResult, FileResult


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
def temp_fountain_file(tmp_path, request):
    """Copy test fountain file to temp directory with unique name per test."""
    fixtures_dir = Path(__file__).parent.parent / "fixtures" / "fountain" / "test_data"
    source_file = fixtures_dir / "test_script.fountain"

    # Ensure we're reading from the correct location (absolute path)
    source_file = source_file.resolve()

    # Use a unique filename based on the test name to avoid any collision
    test_name = request.node.name.replace("[", "_").replace("]", "_").replace(" ", "_")
    # Add timestamp and random suffix to ensure uniqueness even in parallel execution
    import random
    import time

    unique_suffix = f"{int(time.time() * 1000)}_{random.randint(1000, 9999)}"  # noqa: S311
    file_path = tmp_path / f"{test_name}_{unique_suffix}_test_script.fountain"

    # Ensure temp path is fully resolved to avoid any path confusion
    file_path = file_path.resolve()

    # Read content and write fresh to avoid any metadata issues
    # Use explicit encoding to ensure consistent behavior across platforms
    content = source_file.read_text(encoding="utf-8")

    # Double-check that source content is clean (no metadata)
    if "SCRIPTRAG-META-START" in content:
        # The source fixture is contaminated - try to extract clean content
        import warnings

        warnings.warn(
            f"Source fixture file is contaminated with metadata: {source_file}\n"
            f"Attempting to extract clean content...",
            stacklevel=2,
        )
        # Extract content before metadata section
        content = content.split("SCRIPTRAG-META-START")[0].rstrip()

    # Write to temp file with explicit encoding
    file_path.write_text(content, encoding="utf-8")

    # Verify the written file is clean
    written_content = file_path.read_text(encoding="utf-8")
    assert "SCRIPTRAG-META-START" not in written_content, (
        f"Written file has metadata immediately after creation: {file_path}"
    )

    # Ensure we return the temp file, not the source
    assert file_path != source_file, "Fixture must return temp file, not source!"
    assert str(tmp_path) in str(file_path), "File must be in temp directory!"

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
        """Test loading a markdown-based analyzer."""
        # Mock the AgentLoader to test markdown agent loading
        with patch("scriptrag.agents.AgentLoader") as mock_loader_class:
            mock_loader = mock_loader_class.return_value
            mock_analyzer = MockAnalyzer()
            mock_analyzer.name = "props-inventory"
            mock_loader.load_agent.return_value = mock_analyzer

            analyze_command.load_analyzer("props-inventory")

            assert len(analyze_command.analyzers) == 1
            assert analyze_command.analyzers[0].name == "props-inventory"

    def test_load_analyzer_unknown(self, analyze_command):
        """Test loading an unknown analyzer."""
        with pytest.raises(ValueError, match="Unknown analyzer: unknown"):
            analyze_command.load_analyzer("unknown")

    def test_load_analyzer_duplicate(self, analyze_command):
        """Test loading the same analyzer twice."""
        # Use mock analyzer for testing duplicate loading
        mock_analyzer = MockAnalyzer()
        mock_analyzer.name = "test-duplicate"
        analyze_command.analyzers.append(mock_analyzer)

        # Try to load the same analyzer again
        analyze_command.load_analyzer("test-duplicate")

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
        # Check initial file content
        initial_content = temp_fountain_file.read_text()
        assert "SCRIPTRAG-META-START" not in initial_content, (
            f"File already has metadata before test! Content:\n{initial_content}"
        )

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

        assert scene_needs_update(scene, analyze_command.analyzers) is True

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

        assert scene_needs_update(scene, analyze_command.analyzers) is True

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

        assert scene_needs_update(scene, analyze_command.analyzers) is True

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

        assert scene_needs_update(scene, analyze_command.analyzers) is False


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
        assert (
            file_needs_update(script, analyze_command.analyzers, Path("test.fountain"))
            is True
        )

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
        """Test scene_needs_update with non-Scene object."""
        # Should return False for non-Scene objects
        assert scene_needs_update("not a scene", analyze_command.analyzers) is False

    def test_scene_needs_update_no_analyzers_in_metadata(self, analyze_command):
        """Test scene_needs_update when metadata has no analyzers key."""
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
        assert scene_needs_update(scene, analyze_command.analyzers) is False

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

            async def analyze(self, scene):
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


class TestAnalyzeCommandBrittleMode:
    """Test brittle mode functionality for 99% coverage."""

    @pytest.mark.asyncio
    async def test_analyze_brittle_mode_file_processing_failure(self, tmp_path):
        """Test brittle=True propagates exceptions when file processing fails."""
        from scriptrag.api.analyze import AnalyzeCommand

        cmd = AnalyzeCommand()

        # Create a file that will cause a parsing error
        bad_file = tmp_path / "bad.fountain"
        bad_file.write_text("Invalid fountain content")

        # Mock parser to raise an exception
        with patch("scriptrag.api.analyze.FountainParser") as mock_parser:
            mock_parser.return_value.parse_file.side_effect = RuntimeError(
                "Parse failed"
            )

            # Mock ScriptLister to return our bad file
            with patch("scriptrag.api.analyze.ScriptLister") as mock_lister:
                from scriptrag.api.list import FountainMetadata

                mock_lister.return_value.list_scripts.return_value = [
                    FountainMetadata(file_path=bad_file, title="Bad Script")
                ]

                # Test brittle=True - should propagate exception
                with pytest.raises(RuntimeError, match="Parse failed"):
                    await cmd.analyze(path=tmp_path, brittle=True)

    @pytest.mark.asyncio
    async def test_analyze_brittle_mode_operation_failure(self, tmp_path):
        """Test brittle=True propagates exceptions at operation level."""
        from scriptrag.api.analyze import AnalyzeCommand

        cmd = AnalyzeCommand()

        # Mock ScriptLister to raise an exception during the main operation
        with patch("scriptrag.api.analyze.ScriptLister") as mock_lister:
            mock_lister.return_value.list_scripts.side_effect = RuntimeError(
                "Listing failed"
            )

            # Test brittle=True - should propagate exception
            with pytest.raises(RuntimeError, match="Listing failed"):
                await cmd.analyze(path=tmp_path, brittle=True)

    @pytest.mark.asyncio
    async def test_analyze_brittle_mode_analyzer_failure(self, temp_fountain_file):
        """Test brittle=True causes analyzer exceptions to propagate (lines 302-307)."""
        from scriptrag.analyzers.base import BaseSceneAnalyzer
        from scriptrag.api.analyze import AnalyzeCommand

        class BrittleFailingAnalyzer(BaseSceneAnalyzer):
            name = "brittle_failing"

            async def analyze(self, scene: dict) -> dict:
                raise RuntimeError("Analyzer failed in brittle mode")

        cmd = AnalyzeCommand(analyzers=[BrittleFailingAnalyzer()])

        # Test brittle=True - should propagate analyzer exception
        with pytest.raises(RuntimeError, match="Analyzer failed in brittle mode"):
            await cmd.analyze(path=temp_fountain_file.parent, force=True, brittle=True)

    @pytest.mark.asyncio
    async def test_analyze_brittle_false_file_processing_failure(self, tmp_path):
        """Test brittle=False logs and continues when file processing fails."""
        from scriptrag.api.analyze import AnalyzeCommand

        cmd = AnalyzeCommand()

        # Create a file that will cause a parsing error
        bad_file = tmp_path / "bad.fountain"
        bad_file.write_text("Invalid fountain content")

        # Mock parser to raise an exception
        with patch("scriptrag.api.analyze.FountainParser") as mock_parser:
            mock_parser.return_value.parse_file.side_effect = RuntimeError(
                "Parse failed"
            )

            # Mock ScriptLister to return our bad file
            with patch("scriptrag.api.analyze.ScriptLister") as mock_lister:
                from scriptrag.api.list import FountainMetadata

                mock_lister.return_value.list_scripts.return_value = [
                    FountainMetadata(file_path=bad_file, title="Bad Script")
                ]

                # Test brittle=False - should not raise, but capture error
                result = await cmd.analyze(path=tmp_path, brittle=False)

                assert len(result.errors) == 1
                assert "Parse failed" in result.errors[0]
                assert len(result.files) == 1
                assert result.files[0].error == "Parse failed"
                assert not result.files[0].updated

    @pytest.mark.asyncio
    async def test_analyze_brittle_false_operation_failure(self, tmp_path):
        """Test brittle=False (default) logs and continues when operation fails."""
        from scriptrag.api.analyze import AnalyzeCommand

        cmd = AnalyzeCommand()

        # Mock ScriptLister to raise an exception during the main operation
        with patch("scriptrag.api.analyze.ScriptLister") as mock_lister:
            mock_lister.return_value.list_scripts.side_effect = RuntimeError(
                "Listing failed"
            )

            # Test brittle=False - should not raise, but capture error
            result = await cmd.analyze(path=tmp_path, brittle=False)

            assert len(result.errors) == 1
            assert "Analyze failed: Listing failed" in result.errors[0]

    @pytest.mark.asyncio
    async def test_analyze_brittle_false_analyzer_failure(self, temp_fountain_file):
        """Test brittle=False (default) logs and continues when analyzer fails."""
        from scriptrag.analyzers.base import BaseSceneAnalyzer
        from scriptrag.api.analyze import AnalyzeCommand

        class NonBrittleFailingAnalyzer(BaseSceneAnalyzer):
            name = "non_brittle_failing"

            async def analyze(self, scene: dict) -> dict:
                raise RuntimeError("Analyzer failed in non-brittle mode")

        cmd = AnalyzeCommand(analyzers=[NonBrittleFailingAnalyzer()])

        # Test brittle=False - should not raise, but log warning and continue
        result = await cmd.analyze(
            path=temp_fountain_file.parent, force=True, brittle=False
        )

        # Should still complete successfully
        assert len(result.errors) == 0  # Analyzer failures are warned but not in errors
        assert len(result.files) == 1
        assert result.files[0].updated  # File should still be processed

    def test_load_analyzer_builtin_success(self, analyze_command):
        """Test loading a built-in analyzer successfully (lines 109-112)."""
        # Mock the builtin analyzers module
        mock_analyzer_class = MockAnalyzer

        with patch(
            "scriptrag.analyzers.builtin.BUILTIN_ANALYZERS",
            {"test_builtin": mock_analyzer_class},
        ):
            analyze_command.load_analyzer("test_builtin")

            assert len(analyze_command.analyzers) == 1
            assert isinstance(analyze_command.analyzers[0], MockAnalyzer)

    def test_load_analyzer_builtin_import_error(self, analyze_command):
        """Test builtin analyzer loading with ImportError (lines 113-114)."""
        import builtins

        # Mock ImportError when trying to import builtin analyzers
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "scriptrag.analyzers.builtin" in name:
                raise ImportError("Cannot import builtin analyzers")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", mock_import):
            # Should fall back to agent loading and eventually fail
            with pytest.raises(ValueError, match="Unknown analyzer: nonexistent"):
                analyze_command.load_analyzer("nonexistent")

    @pytest.mark.asyncio
    async def test_dry_run_with_script_context(self, temp_fountain_file):
        """Test dry run mode sets script context on analyzers (line 243)."""
        from scriptrag.analyzers.base import BaseSceneAnalyzer
        from scriptrag.api.analyze import AnalyzeCommand

        class ScriptContextAnalyzer(BaseSceneAnalyzer):
            name = "script_context"
            script = None  # Will be set by analyze command

            async def analyze(self, scene: dict) -> dict:
                return {"has_script_context": self.script is not None}

        analyzer = ScriptContextAnalyzer()
        cmd = AnalyzeCommand(analyzers=[analyzer])

        # Test dry run mode - should set script context but not write
        result = await cmd.analyze(
            path=temp_fountain_file.parent, force=True, dry_run=True
        )

        # Analyzer should have received script context
        assert analyzer.script is not None
        assert result.files[0].updated  # Shows scenes would be updated
        assert result.files[0].scenes_updated == 2  # Two scenes in test file

        # But file should not actually be modified
        content = temp_fountain_file.read_text()
        assert "SCRIPTRAG-META-START" not in content
